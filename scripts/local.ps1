<#
  ShaOn Voice AI - LOCAL PREVIEW (double-click ShaOn-Local.bat).
  Opens the full app on THIS PC only: no passcode screen; Settings (API key, model, spend cap), Agent Studio, Knowledge
  and Call Logs all work directly. The server listens on 127.0.0.1 and refuses anything that arrives through a proxy or
  tunnel, so this mode can never be shared. For a public link use ShaOn-Share.bat (passcodes, key editing locked).
  Updates in place: rebuilds the web app when its code changed, reinstalls Python packages only if imports fail.
  Works in Windows PowerShell 5.1 and PowerShell 7. ASCII-only on purpose.
#>
param(
  [int]$Port = 8000,
  [switch]$NoBrowser,
  [int]$RunSeconds = 0   # testing only: stop after N seconds
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$OnWindows = ($PSVersionTable.PSEdition -eq "Desktop") -or ($IsWindows -eq $true)
$LogDir = Join-Path $Root "data/local"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Say([string]$msg, [string]$color = "Gray") { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) -ForegroundColor $color }
function Fail([string]$msg) { Write-Host ""; Write-Host "  $msg" -ForegroundColor Red; Write-Host ""; exit 1 }
function Get-Url([string]$url, [int]$timeout = 5) { try { return [int](Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout).StatusCode } catch { return 0 } }
function Full([string]$p) { return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($p) }
function Read-Text([string]$p) { if (Test-Path $p) { return [System.IO.File]::ReadAllText((Full $p)).Trim() } return "" }
function Quiet([string]$exe, [string[]]$argv) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try { $o = & $exe @argv 2>&1 | ForEach-Object { "$_" }; Add-Content -Path (Join-Path $LogDir "launcher.log") -Value $o; return $LASTEXITCODE }
  finally { $ErrorActionPreference = $old }
}

Write-Host ""
Write-Host "  ShaOn Voice AI - local preview (this PC only, no passcode)" -ForegroundColor Cyan
Write-Host "  -----------------------------------------------------------" -ForegroundColor Cyan

# ---------------------------------------------------------------- python
if ($OnWindows) { $Py = Join-Path $Root ".venv\Scripts\python.exe" } else { $Py = Join-Path $Root ".venv/bin/python" }
if ($env:PYTHON) { $Py = $env:PYTHON }
if (-not (Test-Path $Py)) { Fail "No Python environment in this folder (.venv). Run ShaOn-Install.bat once first." }
if ((Quiet $Py @("-c", "import fastapi, pipecat, cryptography, segno, anthropic")) -ne 0) {
  Say "Python packages are missing or outdated; installing the pinned set (a few minutes) ..." "Yellow"
  $code = Quiet $Py @("-m", "pip", "install", "--disable-pip-version-check", "-c", "deploy/requirements-cpu.txt", "-e", ".[app,stt-whisper,mms,tts-kokoro,retrieval]")
  if ($code -ne 0) { Fail "pip install failed. Details: data\local\launcher.log  (or run ShaOn-Install.bat)" }
}
Say "Python: $Py" "Green"

# ---------------------------------------------------------------- web app (rebuild when web/ changed since the last build)
$webRev = ""
if (Get-Command git -ErrorAction SilentlyContinue) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  $webRev = (& git -C $Root rev-parse "HEAD:web" 2>$null | Out-String).Trim()
  $ErrorActionPreference = $old
}
$mark = Join-Path $Root "web/out/.shaon-build"
$needBuild = -not (Test-Path (Join-Path $Root "web/out/index.html"))
if ($webRev -and (Read-Text $mark) -ne $webRev) { $needBuild = $true }
if ($needBuild) {
  $npm = $null
  if ($OnWindows) { $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue }
  if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
  if (-not $npm) { Fail "The web app needs a (re)build but Node.js is missing:  winget install OpenJS.NodeJS.LTS" }
  Push-Location (Join-Path $Root "web")
  try {
    $lockSha = (Get-FileHash "package-lock.json" -Algorithm SHA256).Hash
    if (-not (Test-Path "node_modules") -or (Read-Text "node_modules/.shaon-lock") -ne $lockSha) {
      Say "Installing web dependencies (npm ci) ..." "Yellow"
      if ((Quiet $npm.Source @("ci", "--no-audit", "--no-fund")) -ne 0) { Fail "npm ci failed. Details: data\local\launcher.log" }
      [System.IO.File]::WriteAllText((Full "node_modules/.shaon-lock"), $lockSha)
    }
    Say "Building the web app (production) ..." "Yellow"
    if ((Quiet $npm.Source @("run", "build")) -ne 0 -or -not (Test-Path "out/index.html")) { Fail "Web build failed. Details: data\local\launcher.log" }
    if ($webRev) { [System.IO.File]::WriteAllText((Full "out/.shaon-build"), $webRev) }
  } finally { Pop-Location }
}
Say "Web app: production build" "Green"

# ---------------------------------------------------------------- configuration: explicit, so stale settings cannot re-create a gate
# The app IGNORES ADMIN_PASSWORD / VISITOR_PASSCODE / ALLOW_KEY_EDIT in local preview (also from .env), and refuses to
# start if SHAON_EXPOSED is on at the same time. Your stored key, model and spend history are never touched.
foreach ($n in @("ADMIN_PASSWORD", "VISITOR_PASSCODE", "SHAON_SHARE_HOST_FILE", "ALLOWED_ORIGINS", "SPEND_CAP_USD")) { Remove-Item "Env:$n" -ErrorAction SilentlyContinue }
$env:SHAON_LOCAL_PREVIEW = "1"; $env:SHAON_EXPOSED = "0"; $env:ALLOW_KEY_EDIT = "true"; $env:TRANSPORT = "both"
$env:SHAON_SELF_URL = "http://127.0.0.1:$Port"; $env:PYTHONIOENCODING = "utf-8"
$env:SHAON_PRELOAD = ((& $Py scripts/share_helper.py preload) | Out-String).Trim()
& $Py scripts/fetch_models.py --check *> $null
if ($LASTEXITCODE -eq 0) { $env:HF_HUB_OFFLINE = "1"; Say "Models: all downloaded" "Green" }
else { Say "Some language models are not downloaded yet: those languages show as 'missing' in the app (ShaOn-Install.bat downloads them)." "Yellow" }

$base = "http://127.0.0.1:$Port"
if ((Get-Url "$base/health" 2) -ne 0) {
  Fail "Port $Port is already in use. If ShaOn is already running, close that window first (or run: scripts\local.ps1 -Port 8010)."
}
$out = Join-Path $LogDir "server.out.log"; $err = Join-Path $LogDir "server.err.log"
$server = Start-Process -FilePath $Py -ArgumentList @("-m", "uvicorn", "--factory", "api.main:create_app", "--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning") `
  -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -NoNewWindow
try {
  $up = $false
  for ($i = 0; $i -lt 120; $i++) { if ($server.HasExited) { break }; if ((Get-Url "$base/health" 3) -eq 200) { $up = $true; break }; Start-Sleep -Seconds 1 }
  if (-not $up) { Get-Content $err -Tail 20 -ErrorAction SilentlyContinue | Write-Host; Fail "The app did not start. Log: $err" }
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "   ShaOn is running:   $base/" -ForegroundColor White
  Write-Host "   Settings (key, model, spend cap):  $base/settings/" -ForegroundColor White
  Write-Host "   No passcode. Only this PC can open it. Keep this window open; Ctrl+C stops it." -ForegroundColor Gray
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host ""
  if ($OnWindows -and -not $NoBrowser) { try { Start-Process "$base/" } catch {} }
  $started = Get-Date; $last = Get-Date "2000-01-01"
  while ($true) {
    Start-Sleep -Seconds 3
    if ($RunSeconds -gt 0 -and ((Get-Date) - $started).TotalSeconds -ge $RunSeconds) { break }
    if ($server.HasExited) { Get-Content $err -Tail 15 -ErrorAction SilentlyContinue | Write-Host; Fail "The app stopped. Log: $err" }
    if (((Get-Date) - $last).TotalSeconds -ge 60) { Say ("status | " + ((& $Py scripts/share_helper.py status $Port) -join " ")) "Gray"; $last = Get-Date }
  }
}
finally {
  if ($server -and -not $server.HasExited) { try { Stop-Process -Id $server.Id -Force } catch {} }
  Say "Stopped." "Yellow"
}
