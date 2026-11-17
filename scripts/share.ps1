<#
  ShaOn Voice AI - share by public link at $0 (DEPLOY.md, docs/SHARE.md).
  Runs on YOUR PC: starts the voice app in production mode, warms up the speech models, opens a Cloudflare
  Quick Tunnel, checks the public URL answers /health, then prints the link, the visitor passcode and a QR code.
  Works in Windows PowerShell 5.1 (double-click ShaOn-Share.bat) and PowerShell 7 (also macOS/Linux via share.sh).
  Keep this window open while people use the link. Ctrl+C or closing the window ends the link.
  This file is ASCII-only on purpose (Windows PowerShell 5.1 reads scripts without a BOM as ANSI).
#>
param(
  [int]$Port = 8000,
  [int]$MaxCalls = 2,
  [int]$MaxCallSeconds = 300,
  [string]$Cloudflared = "",
  [string]$PublicUrlOverride = "",   # testing only: check this base URL instead of the tunnel URL
  [int]$RunSeconds = 0,              # testing only: stop after N seconds
  [switch]$SkipWarmup
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$OnWindows = ($PSVersionTable.PSEdition -eq "Desktop") -or ($IsWindows -eq $true)
$ShareDir = Join-Path $Root "data/share"
New-Item -ItemType Directory -Force -Path $ShareDir | Out-Null
$HostFile = Join-Path $ShareDir "share_host.txt"
$LinkFile = Join-Path $Root "share-link.txt"
$QrFile = Join-Path $Root "share-qr.png"

function Say([string]$msg, [string]$color = "Gray") { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) -ForegroundColor $color }
function Fail([string]$msg) { Write-Host ""; Write-Host "  $msg" -ForegroundColor Red; Write-Host ""; exit 1 }
function Write-NoBom([string]$path, [string]$text) { [System.IO.File]::WriteAllText($path, $text) }  # UTF-8 without BOM

function Get-Url([string]$url, [int]$timeout = 8) {
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout; return [int]$r.StatusCode } catch { return 0 }
}

# ---------------------------------------------------------------- 1. prerequisites
Write-Host ""
Write-Host "  ShaOn Voice AI - share by link" -ForegroundColor Cyan
Write-Host "  ------------------------------" -ForegroundColor Cyan
if ($OnWindows) { $Py = Join-Path $Root ".venv\Scripts\python.exe" } else { $Py = Join-Path $Root ".venv/bin/python" }
if ($env:PYTHON) { $Py = $env:PYTHON }
if (-not (Test-Path $Py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmd) { Fail "Python not found. Follow docs/RUNBOOK.md (Python 3.12 + a .venv in the project folder)." }
  $Py = $cmd.Source
}
$ver = (& $Py -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null)
if (-not $ver) { Fail "Could not run Python at $Py" }
$parts = $ver.Split(".")
if ([int]$parts[0] -ne 3 -or [int]$parts[1] -lt 10 -or [int]$parts[1] -gt 12) { Fail "Python $ver found; ShaOn needs Python 3.10-3.12 (3.12 recommended)." }
Say "Python $ver ($Py)" "Green"
& $Py -c "import fastapi, pipecat, cryptography, segno" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Python packages missing. Run:  $Py -m pip install -e "".[app,stt-whisper,tts-kokoro]""" }

if (-not (Test-Path (Join-Path $Root "web/out/index.html"))) {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "The web app is not built and Node.js is missing. Install it:  winget install OpenJS.NodeJS.LTS" }
  Say "Building the web app (production, one time)..." "Yellow"
  Push-Location (Join-Path $Root "web")
  if (-not (Test-Path "node_modules")) { & npm ci --no-audit --no-fund | Out-Null }
  & npm run build | Out-Null
  Pop-Location
  if (-not (Test-Path (Join-Path $Root "web/out/index.html"))) { Fail "Web build failed. Run 'cd web; npm run build' to see why." }
}
Say "Web app: production build (served by the app itself, one origin)" "Green"

if (-not $Cloudflared) {
  $c = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($c) { $Cloudflared = $c.Source }
  elseif ($OnWindows) {
    foreach ($p in @("$env:ProgramFiles\cloudflared\cloudflared.exe", "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe")) {
      if ($p -and (Test-Path $p)) { $Cloudflared = $p; break }
    }
  }
}
if (-not $Cloudflared) {
  Write-Host ""
  Write-Host "  cloudflared (free, from Cloudflare) is not installed. Install it with:" -ForegroundColor Yellow
  if ($OnWindows) { Write-Host "      winget install Cloudflare.cloudflared" -ForegroundColor White }
  else { Write-Host "      macOS: brew install cloudflared    Linux: see developers.cloudflare.com (cloudflared downloads)" -ForegroundColor White }
  Write-Host "  then close this window and double-click ShaOn-Share.bat again." -ForegroundColor Yellow
  Write-Host ""
  exit 1
}
Say "cloudflared: $Cloudflared" "Green"

# ---------------------------------------------------------------- 2. passcodes (new every launch)
$Visitor = (& $Py scripts/share_helper.py passcode).Trim()
$Admin = $env:ADMIN_PASSWORD
if (-not $Admin -and (Test-Path (Join-Path $Root ".env"))) {
  $m = Select-String -Path (Join-Path $Root ".env") -Pattern '^ADMIN_PASSWORD=(.+)$' | Select-Object -First 1
  if ($m) { $Admin = $m.Matches[0].Groups[1].Value.Trim().Trim('"') }
}
if (-not $Admin -or $Admin.Length -lt 12) { $Admin = ((& $Py scripts/share_helper.py passcode).Trim() + "-" + (& $Py scripts/share_helper.py passcode).Trim()) }

# ---------------------------------------------------------------- 3. start the app (production, exposed mode)
$env:SHAON_EXPOSED = "1"; $env:ALLOW_KEY_EDIT = "false"; $env:TRANSPORT = "both"
$env:VISITOR_PASSCODE = $Visitor; $env:ADMIN_PASSWORD = $Admin
$env:SHAON_MAX_CALLS = "$MaxCalls"; $env:SHAON_MAX_CALL_SECONDS = "$MaxCallSeconds"
$env:SHAON_SHARE_HOST_FILE = $HostFile; $env:SHAON_SELF_URL = "http://127.0.0.1:$Port"
$env:SHAON_PRELOAD = "lid,stt:en,stt:ja,stt:hi,stt:bn,stt:kn,tts:en,tts:ja,tts:hi,tts:bn,tts:kn"
$env:PYTHONIOENCODING = "utf-8"
Write-NoBom $HostFile ""
if ((Get-Url "http://127.0.0.1:$Port/health" 2) -ne 0) { Fail "Port $Port is already in use (is ShaOn already running?). Close it or run: scripts\share.ps1 -Port 8010" }

$ServerOut = Join-Path $ShareDir "server.out.log"; $ServerErr = Join-Path $ShareDir "server.err.log"
$server = Start-Process -FilePath $Py -ArgumentList @("-m", "uvicorn", "--factory", "api.main:create_app", "--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning") `
  -RedirectStandardOutput $ServerOut -RedirectStandardError $ServerErr -PassThru -NoNewWindow
$tunnel = $null
$Url = ""

function Stop-All {
  if ($tunnel -and -not $tunnel.HasExited) { try { Stop-Process -Id $tunnel.Id -Force } catch {} }
  if ($server -and -not $server.HasExited) { try { Stop-Process -Id $server.Id -Force } catch {} }
  try { Write-NoBom $HostFile "" } catch {}
}

function Start-Tunnel {
  $log = Join-Path $ShareDir ("tunnel-" + (Get-Date -Format "HHmmss") + ".log")
  $p = Start-Process -FilePath $Cloudflared -ArgumentList @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Port") `
    -RedirectStandardError $log -RedirectStandardOutput ($log + ".out") -PassThru -NoNewWindow
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if ($p.HasExited) { break }
    $hit = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return @{ Proc = $p; Url = $hit.Matches[0].Value } }
  }
  try { Stop-Process -Id $p.Id -Force } catch {}
  return @{ Proc = $null; Url = "" }
}

function Publish([string]$url) {
  $hostName = ([System.Uri]$url).Host
  Write-NoBom $HostFile $hostName              # the app accepts this Host/Origin from now on (and nothing else public)
  $link = "$url/call/"
  $base = $url; if ($PublicUrlOverride) { $base = $PublicUrlOverride }
  Say "Waiting until the public link answers /health ..." "Yellow"
  $ok = $false
  for ($i = 0; $i -lt 45; $i++) { if ((Get-Url "$base/health" 8) -eq 200) { $ok = $true; break }; Start-Sleep -Seconds 2 }
  if (-not $ok) { Say "The public link did not answer yet (Cloudflare can take a minute). Will keep checking." "Yellow" }
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "   SHARE THIS LINK:   $link" -ForegroundColor White
  Write-Host "   VISITOR PASSCODE:  $Visitor" -ForegroundColor White
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "   Admin passcode (Studio, Settings, Knowledge, Logs - do NOT share): $Admin" -ForegroundColor DarkYellow
  Write-Host "   The link works only while this PC is awake and this window is open." -ForegroundColor Gray
  Write-Host ""
  & $Py scripts/share_helper.py qr $link $QrFile
  Write-Host ""
  $txt = "ShaOn Voice AI - share link`r`n`r`nLink:     $link`r`nPasscode: $Visitor`r`n`r`nCreated:  $(Get-Date -Format 'yyyy-MM-dd HH:mm')`r`n" +
         "Works only while the host PC is on and the ShaOn window is open. A new link and passcode are made every launch.`r`n" +
         "QR code:  share-qr.png`r`n"
  Write-NoBom $LinkFile $txt
  Say "Saved share-link.txt and share-qr.png (link + visitor passcode only)" "Gray"
  return $link
}

try {
  # wait for the app
  Say "Starting the voice app on 127.0.0.1:$Port ..." "Yellow"
  $up = $false
  for ($i = 0; $i -lt 90; $i++) {
    if ($server.HasExited) { break }
    if ((Get-Url "http://127.0.0.1:$Port/health" 3) -eq 200) { $up = $true; break }
    Start-Sleep -Seconds 1
  }
  if (-not $up) { Get-Content $ServerErr -Tail 20 -ErrorAction SilentlyContinue | Write-Host; Fail "The app did not start. Log: $ServerErr" }
  Say "App is up." "Green"

  # ------------------------------------------------------------ 4. warm up the models
  if (-not $SkipWarmup) {
    Say "Warming up speech models so the first caller does not wait (first time: downloads)..." "Yellow"
    $last = ""
    $deadline = (Get-Date).AddMinutes(10)
    while ((Get-Date) -lt $deadline) {
      $line = (& $Py scripts/share_helper.py ready $Port) -join " "
      $code = $LASTEXITCODE
      if ($line -ne $last) { Say "  $line" "Gray"; $last = $line }
      if ($code -eq 0) { break }
      Start-Sleep -Seconds 3
    }
    if ($code -ne 0) { Say "Some languages are not ready (see above). Visitors see this on the Get-ready screen." "Yellow" } else { Say "All languages ready." "Green" }
  }

  # ------------------------------------------------------------ 5. tunnel + link
  Say "Opening a Cloudflare Quick Tunnel ..." "Yellow"
  $t = Start-Tunnel
  if (-not $t.Url) { Fail "cloudflared did not give a link. Check your internet connection and try again." }
  $tunnel = $t.Proc; $Url = $t.Url
  $null = Publish $Url

  # ------------------------------------------------------------ 6. stay open: status + tunnel watchdog
  $started = Get-Date; $fails = 0; $lastStatus = Get-Date "2000-01-01"
  while ($true) {
    Start-Sleep -Seconds 5
    if ($RunSeconds -gt 0 -and ((Get-Date) - $started).TotalSeconds -ge $RunSeconds) { Say "Test run finished." "Gray"; break }
    if ($server.HasExited) {
      Get-Content $ServerErr -Tail 15 -ErrorAction SilentlyContinue | Write-Host
      Fail "The voice app stopped. The link is dead. Log: $ServerErr"
    }
    $base = $Url; if ($PublicUrlOverride) { $base = $PublicUrlOverride }
    $tunnelOk = (-not $tunnel.HasExited) -and ((Get-Url "$base/health" 8) -eq 200)
    if ($tunnelOk) { $fails = 0 } else { $fails++ }
    if ($tunnel.HasExited -or $fails -ge 3) {
      Write-Host ""
      Say "TUNNEL DROPPED. The old link is DEAD: $Url/call/" "Red"
      if (-not $tunnel.HasExited) { try { Stop-Process -Id $tunnel.Id -Force } catch {} }
      $t = Start-Tunnel
      if (-not $t.Url) { Say "Could not reopen the tunnel; retrying in 15 s..." "Red"; Start-Sleep -Seconds 15; continue }
      $tunnel = $t.Proc; $Url = $t.Url; $fails = 0
      Say "NEW LINK (send this one; the passcode is unchanged):" "Green"
      $null = Publish $Url
      continue
    }
    if (((Get-Date) - $lastStatus).TotalSeconds -ge 30) {
      $st = (& $Py scripts/share_helper.py status $Port) -join " "
      Say ("tunnel up | " + $st) "Gray"
      $lastStatus = Get-Date
    }
  }
}
finally {
  Stop-All
  Say "Stopped. The link no longer works." "Yellow"
}
