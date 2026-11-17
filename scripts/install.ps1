<#
  ShaOn Voice AI - one-command installer for a Windows PC (docs/SHARE.md). Double-click ShaOn-Install.bat.
  From nothing to a printed public link: checks the PC, installs what is missing (winget), gets the code, sets up
  Python + the web app, downloads the CPU demo models, runs a self-test, then starts scripts/share.ps1 in this window.
  Run it again any time: finished steps are skipped, so later runs reach the link in a few minutes.
  Free: the only money ShaOn can spend is the Claude API, and only after YOU paste a key in Settings (never here).
  Works in Windows PowerShell 5.1 and PowerShell 7. ASCII-only on purpose (5.1 reads BOM-less scripts as ANSI).

  Test hooks (used by tests/install/run_installer_test.py; ignore otherwise):
    SHAON_TEST_FACTS = path to a JSON file that replaces the PC checks (OS, disk, RAM, CPU, GPU, internet)
    SHAON_TEST_PATH_FILE = extra PATH entries to pick up after installs (stands in for the Windows registry PATH)
#>
param(
  [string]$RepoUrl = "https://github.com/shashanksbharadwaj161/CustomerSupport.Ai.git",
  [string]$Branch = "claude/sweet-ptolemy-7qza59",   # 'main' is used instead when it exists and contains this installer
  [string]$InstallDir = "",                          # where to clone when run outside a ShaOn folder (default: $HOME\ShaOn)
  [switch]$NoShare,                                  # stop after installing (do not start the share launcher)
  [switch]$NonInteractive,                           # never prompt (tests, unattended)
  [string[]]$ShareArgs = @()                         # passed to scripts/share.ps1
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"             # PS 5.1 Invoke-WebRequest is very slow with its progress bar
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
$OnWindows = ($PSVersionTable.PSEdition -eq "Desktop") -or ($IsWindows -eq $true)
$Started = Get-Date

function Say([string]$msg, [string]$color = "Gray") { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) -ForegroundColor $color }
function Step([string]$msg) { Write-Host ""; Write-Host ("== " + $msg) -ForegroundColor Cyan }
function Stop-Install([string]$what, [string[]]$fix) {
  Write-Host ""
  Write-Host "  INSTALL STOPPED: $what" -ForegroundColor Red
  foreach ($f in $fix) { Write-Host "    $f" -ForegroundColor White }
  Write-Host "  Fix that, then double-click ShaOn-Install.bat again (finished steps are skipped)." -ForegroundColor Gray
  Write-Host ""
  exit 1
}
# .NET resolves relative paths against the process folder, not PowerShell's location: always pass full paths
function Full([string]$path) { return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($path) }
function Write-NoBom([string]$path, [string]$text) { [System.IO.File]::WriteAllText((Full $path), $text) }
function Get-Sha([string]$text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  return ([System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text)))).Replace("-", "").ToLower()
}
function Get-FileText([string]$path) { if (Test-Path $path) { return [System.IO.File]::ReadAllText((Full $path)) } return "" }

# Run a native program quietly; output goes to a log. Returns the exit code. (PS 5.1 turns stderr into errors under
# ErrorActionPreference=Stop, so it is relaxed here.)
$LogDir = Join-Path ([System.IO.Path]::GetTempPath()) "shaon-install"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "install.log"
function Run-Quiet([string]$exe, [string[]]$argv) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try {
    Add-Content -Path $Log -Value ("`r`n> " + $exe + " " + ($argv -join " "))
    $out = & $exe @argv 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    if ($out) { Add-Content -Path $Log -Value $out }
    return $code
  } catch { Add-Content -Path $Log -Value ("" + $_); return 1 }
  finally { $ErrorActionPreference = $old }
}
# Run a native program attached to this console (live progress bars), returning ONLY its exit code.
# Start-Process does not quote arguments in PS 5.1, so paths with spaces (C:\Users\Jane Doe) are quoted here.
function Quote-Arg([string]$a) { if ($a -match '[\s"]') { return '"' + ($a -replace '"', '\"') + '"' } return $a }
function Run-Live([string]$exe, [string[]]$argv) {
  try {
    $p = Start-Process -FilePath $exe -ArgumentList (($argv | ForEach-Object { Quote-Arg $_ }) -join " ") -NoNewWindow -Wait -PassThru
    return [int]$p.ExitCode
  } catch { Write-Host ("" + $_); return 1 }
}
function Capture([string]$exe, [string[]]$argv) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try { $o = & $exe @argv 2>$null; if ($LASTEXITCODE -ne 0) { return "" }; return (($o | Out-String).Trim()) } catch { return "" }
  finally { $ErrorActionPreference = $old }
}

function Refresh-Path {
  $parts = @()
  if ($OnWindows) {
    $parts += [Environment]::GetEnvironmentVariable("Path", "Machine")
    $parts += [Environment]::GetEnvironmentVariable("Path", "User")
    $parts += (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
  }
  if ($env:SHAON_TEST_PATH_FILE -and (Test-Path $env:SHAON_TEST_PATH_FILE)) { $parts = @(Get-Content $env:SHAON_TEST_PATH_FILE) + $parts }
  $sep = [System.IO.Path]::PathSeparator
  $seen = @{}; $out = @()
  foreach ($p in (($parts + ($env:PATH -split [regex]::Escape($sep))) -split [regex]::Escape($sep))) {
    if ($p -and -not $seen.ContainsKey($p.ToLower())) { $seen[$p.ToLower()] = $true; $out += $p }
  }
  $env:PATH = $out -join $sep
}

Write-Host ""
Write-Host "  ShaOn Voice AI - installer" -ForegroundColor Cyan
Write-Host "  --------------------------" -ForegroundColor Cyan
Write-Host "  Log of quiet steps: $Log" -ForegroundColor DarkGray

# ================================================================ 0. where is the code?
$Root = ""
if ($PSScriptRoot) {
  $cand = Split-Path -Parent $PSScriptRoot
  if ((Test-Path (Join-Path $cand "pyproject.toml")) -and ((Get-FileText (Join-Path $cand "pyproject.toml")) -match "shaon-voice-ai")) { $Root = $cand }
}
$Bootstrap = -not $Root
if ($Bootstrap) {
  if (-not $InstallDir) { $InstallDir = Join-Path $HOME "ShaOn" }
  $Root = $InstallDir
}

# ================================================================ 1. preflight
Step "1/8  Checking this PC"
function Get-Facts {
  if ($env:SHAON_TEST_FACTS) { return (Get-Content $env:SHAON_TEST_FACTS -Raw | ConvertFrom-Json) }
  $f = [ordered]@{ os = "unknown"; build = 0; free_gb = 0; ram_gb = 0; cpu = "unknown"; cores = 0; gpu = "none found"; nvidia = $false; internet = $false }
  $drive = $Root; if (-not (Test-Path $drive)) { $drive = Split-Path -Parent $Root }; if (-not (Test-Path $drive)) { $drive = $HOME }
  try { $f.free_gb = [math]::Round(([System.IO.DriveInfo]::new((Resolve-Path $drive).Path)).AvailableFreeSpace / 1GB, 1) } catch {}
  if ($OnWindows) {
    try { $os = Get-CimInstance Win32_OperatingSystem; $f.os = "$($os.Caption) (build $($os.BuildNumber))"; $f.build = [int]$os.BuildNumber; $f.ram_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1) } catch {}
    try { $c = Get-CimInstance Win32_Processor | Select-Object -First 1; $f.cpu = $c.Name.Trim(); $f.cores = [int]$c.NumberOfLogicalProcessors } catch {}
    try { $g = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }); if ($g.Count) { $f.gpu = ($g -join ", ") }; $f.nvidia = ($f.gpu -match "NVIDIA") } catch {}
  } else {
    $f.os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
    try { $f.ram_gb = [math]::Round(([double]((Get-Content /proc/meminfo | Select-Object -First 1) -replace "[^0-9]", "")) / 1MB, 1) } catch {}
    try { $f.cpu = ((Get-Content /proc/cpuinfo | Where-Object { $_ -match "^model name" } | Select-Object -First 1) -split ":", 2)[1].Trim(); $f.cores = [Environment]::ProcessorCount } catch {}
  }
  foreach ($u in @("https://github.com", "https://huggingface.co")) {
    try { $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 15 -Method Head; $f.internet = $true; break } catch {}
  }
  return [pscustomobject]$f
}
$F = Get-Facts
$installedBefore = (Test-Path (Join-Path $Root ".venv")) -and (Test-Path (Join-Path $Root "data/install/selftest.ok"))
$rows = @()
$rows += [pscustomobject]@{ Check = "Windows"; Value = $F.os; Result = $(if ($OnWindows -and $F.build -gt 0 -and $F.build -lt 17763) { "STOP (need Windows 10 1809 or newer)" } else { "ok" }) }
$diskRes = "ok"
if ($F.free_gb -lt 12 -and -not $installedBefore) { $diskRes = "STOP (need about 20 GB, at least 12 GB)" }
elseif ($F.free_gb -lt 20 -and -not $installedBefore) { $diskRes = "low (about 20 GB recommended)" }
$rows += [pscustomobject]@{ Check = "Free disk"; Value = "$($F.free_gb) GB"; Result = $diskRes }
$rows += [pscustomobject]@{ Check = "Memory (RAM)"; Value = "$($F.ram_gb) GB"; Result = $(if ($F.ram_gb -lt 8) { "low (8 GB+ recommended; calls will be slow)" } else { "ok" }) }
$rows += [pscustomobject]@{ Check = "CPU"; Value = "$($F.cpu) ($($F.cores) threads)"; Result = "ok" }
$rows += [pscustomobject]@{ Check = "GPU"; Value = "$($F.gpu)"; Result = $(if ($F.nvidia) { "not used (CPU demo mode; GPU setup: docs/RUNBOOK.md)" } else { "not needed (CPU demo mode)" }) }
$rows += [pscustomobject]@{ Check = "Install folder"; Value = $Root; Result = $(if ($Root.Length -gt 120) { "long path (works; C:\ShaOn is safer)" } else { "ok" }) }
$rows += [pscustomobject]@{ Check = "Internet"; Value = $(if ($F.internet) { "github.com / huggingface.co reachable" } else { "not reachable" }); Result = $(if ($F.internet) { "ok" } else { "STOP" }) }
$rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
if ($rows | Where-Object { $_.Result -like "STOP*" -and $_.Check -eq "Windows" }) { Stop-Install "this Windows version is too old for winget." @("Update Windows (Settings > Windows Update), or use Windows 10 version 1809 or newer.") }
if ($diskRes -like "STOP*") {
  Stop-Install "not enough free disk space ($($F.free_gb) GB free)." @("ShaOn needs about 20 GB: Python packages ~5 GB, speech models ~6 GB, tools ~2 GB, plus room to work.",
    "Free space (Settings > System > Storage > Cleanup recommendations), or install elsewhere:  scripts\install.ps1 -InstallDir D:\ShaOn")
}
if (-not $F.internet) { Stop-Install "no internet connection." @("Connect to the internet (and allow PowerShell through any firewall), then run again.") }

# ================================================================ 2. tools (winget)
Step "2/8  Tools (Git, Python 3.12, Node.js, cloudflared, eSpeak NG, FFmpeg, VC++ runtime)"
Refresh-Path
function Find-Python312 {
  $c = @()
  if ($OnWindows) {
    $c += (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    $c += (Join-Path $env:ProgramFiles "Python312\python.exe")
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $p = Capture $py.Source @("-3.12", "-c", "import sys; print(sys.executable)"); if ($p) { $c = @($p) + $c } }
  } else {
    $g = Get-Command python3.12 -ErrorAction SilentlyContinue; if ($g) { $c += $g.Source }
  }
  foreach ($p in $c) {
    if ($p -and (Test-Path $p) -and ($p -notmatch "WindowsApps")) {   # never the Microsoft Store stub
      $v = Capture $p @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])")
      if ($v -match "^3\.12\.") { return @{ Path = $p; Version = $v } }
    }
  }
  return $null
}
function Get-NodeMajor { $n = Get-Command node -ErrorAction SilentlyContinue; if (-not $n) { return 0 }; $v = Capture $n.Source @("--version"); if ($v -match "^v(\d+)") { return [int]$Matches[1] }; return 0 }
function Find-Cloudflared {
  $c = Get-Command cloudflared -ErrorAction SilentlyContinue; if ($c) { return $c.Source }
  if ($OnWindows) { foreach ($p in @("$env:ProgramFiles\cloudflared\cloudflared.exe", "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe")) { if ($p -and (Test-Path $p)) { return $p } } }
  return ""
}
function Test-Espeak {
  if (Get-Command espeak-ng -ErrorAction SilentlyContinue) { return $true }
  if ($OnWindows) { foreach ($p in @("$env:ProgramFiles\eSpeak NG\espeak-ng.exe", "${env:ProgramFiles(x86)}\eSpeak NG\espeak-ng.exe")) { if ($p -and (Test-Path $p)) { return $true } } }
  return $false
}
function Test-VCRedist {
  if ($OnWindows) {
    try { $k = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction Stop; return ($k.Installed -eq 1 -and [int]$k.Major -ge 14 -and [int]$k.Minor -ge 30) } catch { return $false }
  }
  return [bool](Get-Command shaon-vcredist -ErrorAction SilentlyContinue)   # test stand-in
}
$Tools = @(
  @{ Name = "Git"; Id = "Git.Git"; Test = { [bool](Get-Command git -ErrorAction SilentlyContinue) }; Why = "gets and updates the ShaOn code" },
  @{ Name = "Python 3.12"; Id = "Python.Python.3.12"; Test = { [bool](Find-Python312) }; Why = "runs the voice app (Kokoro needs 3.10-3.12; 3.13+ is never used)" },
  @{ Name = "Node.js LTS"; Id = "OpenJS.NodeJS.LTS"; Test = { (Get-NodeMajor) -ge 20 }; Why = "builds the web app (needs 20+)" },
  @{ Name = "cloudflared"; Id = "Cloudflare.cloudflared"; Test = { [bool](Find-Cloudflared) }; Why = "free public link (Cloudflare Quick Tunnel)" },
  @{ Name = "eSpeak NG"; Id = "eSpeak-NG.eSpeak-NG"; Test = { Test-Espeak }; Why = "pronunciation for the Kokoro voices" },
  @{ Name = "FFmpeg"; Id = "Gyan.FFmpeg"; Test = { [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue) }; Why = "audio decoding" },
  @{ Name = "VC++ runtime"; Id = "Microsoft.VCRedist.2015+.x64"; Test = { Test-VCRedist }; Why = "needed by PyTorch / ONNX Runtime" }
)
$missing = @($Tools | Where-Object { -not (& $_.Test) })
foreach ($t in $Tools) { if ($missing -contains $t) { Say ("  {0,-13} missing  ({1})" -f $t.Name, $t.Why) "Yellow" } else { Say ("  {0,-13} present" -f $t.Name) "Green" } }
if ($missing.Count -gt 0) {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    Stop-Install "winget (Windows Package Manager) is missing, so the tools above cannot be installed automatically." @(
      "Install 'App Installer' from the Microsoft Store (free): https://apps.microsoft.com/detail/9NBLGGH4NNS1",
      "Then close this window and double-click ShaOn-Install.bat again.")
  }
  Say "Installing $($missing.Count) tool(s) with winget. Windows may ask 'Do you want to allow this app to make changes?' - click Yes." "Yellow"
  foreach ($t in $missing) {
    Say "  installing $($t.Name) ($($t.Id)) ..." "Yellow"
    $code = Run-Quiet $winget.Source @("install", "--id", $t.Id, "--exact", "--silent", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity", "--source", "winget")
    Refresh-Path
    # 0 = installed; -1978335189 = no applicable update / -1978335135 = already installed
    if ($code -ne 0 -and $code -ne -1978335189 -and $code -ne -1978335135 -and -not (& $t.Test)) {
      Stop-Install "winget could not install $($t.Name) (exit code $code)." @(
        "Try it by hand in a PowerShell window:  winget install --id $($t.Id) --exact",
        "If antivirus blocked it, allow the installer and run again. Details: $Log")
    }
    if (-not (& $t.Test)) {
      Stop-Install "$($t.Name) was installed but this window cannot see it yet." @("Close this window and double-click ShaOn-Install.bat again (a new window picks up the new PATH).")
    }
    Say "  $($t.Name) ready" "Green"
  }
}
$Py312 = Find-Python312
Say "Python $($Py312.Version) at $($Py312.Path)" "Gray"
$Git = (Get-Command git).Source

# ================================================================ 3. code
Step "3/8  ShaOn code"
function Pick-Branch {
  $heads = Capture $Git @("ls-remote", "--heads", $RepoUrl)
  $hasMain = $heads -match "refs/heads/main(\s|$)"
  if ($hasMain) {
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $tmp = Join-Path $LogDir ("probe-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    $ok = (Run-Quiet $Git @("clone", "--depth", "1", "--branch", "main", "--no-checkout", $RepoUrl, $tmp)) -eq 0
    if ($ok) { $ok = (Run-Quiet $Git @("-C", $tmp, "cat-file", "-e", "HEAD:scripts/install.ps1")) -eq 0 }
    try { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue } catch {}
    $ErrorActionPreference = $old
    if ($ok) { return @{ Name = "main"; Why = "main contains the installer (the work branch was merged)" } }
  }
  return @{ Name = $Branch; Why = $(if ($hasMain) { "main does not contain the installer yet" } else { "no main branch yet" }) }
}
function Clone-Help([string]$what) {
  Stop-Install "could not download the code ($what)." @(
    "If the repository is private, sign in to GitHub once:",
    "  1. Run:  git clone $RepoUrl `"$env:TEMP\shaon-test`"   - a GitHub sign-in window opens (Git Credential Manager).",
    "     Sign in with the GitHub account that can see the repository, then delete that test folder.",
    "  2. If no window opens:  winget install --id GitHub.cli --exact   then   gh auth login",
    "     (choose GitHub.com > HTTPS > Login with a web browser), then   gh auth setup-git",
    "  3. Double-click ShaOn-Install.bat again.",
    "Or download the code as a ZIP from the GitHub page (Code > Download ZIP), unzip it and double-click ShaOn-Install.bat inside.",
    "Details: $Log")
}
$isRepo = (Test-Path (Join-Path $Root ".git")) -and ((Capture $Git @("-C", $Root, "rev-parse", "--is-inside-work-tree")) -eq "true")
$scriptBefore = Get-FileText (Join-Path $Root "scripts/install.ps1")
if ($isRepo) {
  $cur = Capture $Git @("-C", $Root, "rev-parse", "--abbrev-ref", "HEAD")
  Say "Git checkout found (branch $cur). Updating with git pull --ff-only ..." "Gray"
  $code = Run-Quiet $Git @("-C", $Root, "pull", "--ff-only")
  if ($code -eq 0) { Say "Code is up to date (branch $cur)." "Green" }
  else { Say "Could not fast-forward (local changes or no network); using the code as it is. Details: $Log" "Yellow" }
} elseif ($Bootstrap -or -not (Test-Path (Join-Path $Root "pyproject.toml"))) {
  $b = Pick-Branch
  Say "Cloning branch $($b.Name) ($($b.Why)) into $Root ..." "Yellow"
  if ((Test-Path $Root) -and (Get-ChildItem $Root -Force | Select-Object -First 1)) {
    Stop-Install "the folder $Root already exists and is not a ShaOn checkout." @("Rename or delete it, or choose another folder:  scripts\install.ps1 -InstallDir D:\ShaOn")
  }
  $code = Run-Quiet $Git @("clone", "--branch", $b.Name, $RepoUrl, $Root)
  if ($code -ne 0) {
    $why = "git exit code $code"; $tail = (Get-Content $Log -Tail 5) -join " "
    if ($tail -match "Authentication|could not read Username|Repository not found|403|denied") { $why = "GitHub refused access: the repository may be private" }
    Clone-Help $why
  }
  Say "Code downloaded (branch $($b.Name))." "Green"
} else {
  # unzipped download: turn the folder into a git checkout in place, so later runs can 'git pull'
  $b = Pick-Branch
  Say "This folder is not a git checkout (ZIP download). Connecting it to branch $($b.Name) ($($b.Why)) ..." "Yellow"
  $ok = (Run-Quiet $Git @("-C", $Root, "init", "--quiet")) -eq 0
  if ($ok) { $null = Run-Quiet $Git @("-C", $Root, "remote", "remove", "origin"); $ok = (Run-Quiet $Git @("-C", $Root, "remote", "add", "origin", $RepoUrl)) -eq 0 }
  if ($ok) { $ok = (Run-Quiet $Git @("-C", $Root, "fetch", "origin", $b.Name)) -eq 0 }
  if (-not $ok) { Clone-Help "git fetch failed" }
  $null = Run-Quiet $Git @("-C", $Root, "checkout", "-f", "-B", $b.Name, "FETCH_HEAD")
  $null = Run-Quiet $Git @("-C", $Root, "branch", "--set-upstream-to", "origin/$($b.Name)")
  Say "Folder connected to branch $($b.Name)." "Green"
}
# a newer installer arrived with the code: continue with that one
$me = Join-Path $Root "scripts/install.ps1"
if ((Test-Path $me) -and (($Bootstrap) -or ((Get-FileText $me) -ne $scriptBefore -and $scriptBefore))) {
  if (-not $env:SHAON_INSTALL_REEXEC) {
    $env:SHAON_INSTALL_REEXEC = "1"
    Say "Continuing with the installer from the downloaded code ..." "Gray"
    $next = @{ RepoUrl = $RepoUrl; Branch = $Branch; ShareArgs = $ShareArgs }
    if ($NoShare) { $next.NoShare = $true }; if ($NonInteractive) { $next.NonInteractive = $true }
    & $me @next
    exit $LASTEXITCODE
  }
}
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "data/install") | Out-Null
$State = Join-Path $Root "data/install"
if (-not (Test-Path (Join-Path $Root ".env"))) { Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env") }
$envText = Get-FileText (Join-Path $Root ".env")
if ($envText -notmatch "(?m)^SHAON_DEVICE=cpu\s*$") {
  if ($envText -match "(?m)^SHAON_DEVICE=.*$") { $envText = $envText -replace "(?m)^SHAON_DEVICE=.*$", "SHAON_DEVICE=cpu" } else { $envText = $envText.TrimEnd() + "`nSHAON_DEVICE=cpu`n" }
  Write-NoBom (Join-Path $Root ".env") $envText
}
$env:SHAON_DEVICE = "cpu"

# ================================================================ 4. Python environment
Step "4/8  Python packages (pinned; first time about 3 GB, 10-20 minutes)"
if ($OnWindows) { $Py = Join-Path $Root ".venv\Scripts\python.exe" } else { $Py = Join-Path $Root ".venv/bin/python" }
if (Test-Path $Py) {
  $v = Capture $Py @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
  if ($v -ne "3.12") { Say "Existing .venv uses Python '$v'; recreating it with 3.12." "Yellow"; Remove-Item -Recurse -Force (Join-Path $Root ".venv") }
}
if (-not (Test-Path $Py)) {
  Say "Creating the virtual environment (.venv) ..." "Yellow"
  if ((Run-Quiet $Py312.Path @("-m", "venv", (Join-Path $Root ".venv"))) -ne 0 -or -not (Test-Path $Py)) { Stop-Install "could not create the Python environment." @("Details: $Log") }
}
$Extras = "app,stt-whisper,mms,tts-kokoro,retrieval"
$hfTokenFile = Join-Path $State "hf_token_asked"
$wantIndic = (Get-FileText $hfTokenFile).Trim() -eq "given"
if ($wantIndic) { $Extras = "$Extras,stt-indic" }
$depsSha = Get-Sha ((Get-FileText (Join-Path $Root "pyproject.toml")) + (Get-FileText (Join-Path $Root "deploy/requirements-cpu.txt")) + $Extras)
$depsMark = Join-Path $Root ".venv/shaon-deps.sha256"
$importOk = (Run-Quiet $Py @("-c", "import fastapi, pipecat, faster_whisper, kokoro, transformers, torch, segno, huggingface_hub")) -eq 0
if ($importOk -and ((Get-FileText $depsMark).Trim() -eq $depsSha)) {
  Say "Python packages already installed (pinned set unchanged) - skipped." "Green"
} else {
  $null = Run-Quiet $Py @("-m", "pip", "install", "--upgrade", "pip")
  $torchPin = (Select-String -Path (Join-Path $Root "deploy/requirements-cpu.txt") -Pattern "^torch==(.+)$" | Select-Object -First 1).Matches[0].Groups[1].Value
  Say "Installing PyTorch $torchPin (CPU build) ..." "Yellow"
  $code = Run-Live $Py @("-m", "pip", "install", "--disable-pip-version-check", "torch==$torchPin", "--index-url", "https://download.pytorch.org/whl/cpu")
  if ($code -ne 0) { Stop-Install "PyTorch did not install (pip exit $code)." @("Usually a network hiccup: run again (pip resumes from its cache).", "If antivirus quarantined files in .venv, allow the ShaOn folder and run again.") }
  Say "Installing ShaOn's Python packages ($Extras) ..." "Yellow"
  $code = Run-Live $Py @("-m", "pip", "install", "--disable-pip-version-check", "-c", "deploy/requirements-cpu.txt", "-e", ".[$Extras]")
  if ($code -ne 0) { Stop-Install "Python packages did not install (pip exit $code)." @("Scroll up for the first red 'ERROR' line from pip.", "Network problems: just run again. Disk full: free space and run again.") }
  if ((Run-Quiet $Py @("-c", "import fastapi, pipecat, faster_whisper, kokoro, transformers, torch, segno, huggingface_hub")) -ne 0) { Stop-Install "Python packages installed but do not import." @("Details: $Log") }
  Write-NoBom $depsMark $depsSha
  Say "Python packages ready." "Green"
}

# ================================================================ 5. web app
Step "5/8  Web app (production build)"
$webRev = Capture $Git @("-C", $Root, "rev-parse", "HEAD:web")
$buildMark = Join-Path $Root "web/out/.shaon-build"
if ((Test-Path (Join-Path $Root "web/out/index.html")) -and $webRev -and ((Get-FileText $buildMark).Trim() -eq $webRev)) {
  Say "Web app already built for this version - skipped." "Green"
} else {
  $npm = $null
  if ($OnWindows) { $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue }   # npm.cmd, not npm.ps1
  if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
  if (-not $npm) { Stop-Install "npm (part of Node.js) was not found." @("Close this window and run the installer again.") }
  Push-Location (Join-Path $Root "web")
  try {
    $lockSha = Get-Sha (Get-FileText "package-lock.json")
    if (-not (Test-Path "node_modules") -or ((Get-FileText "node_modules/.shaon-lock").Trim() -ne $lockSha)) {
      Say "Installing web dependencies (npm ci, pinned by package-lock.json) ..." "Yellow"
      if ((Run-Quiet $npm.Source @("ci", "--no-audit", "--no-fund")) -ne 0) { Stop-Install "npm ci failed." @("Usually a network hiccup: run again. Details: $Log") }
      Write-NoBom (Join-Path (Get-Location) "node_modules/.shaon-lock") $lockSha
    }
    Say "Building the web app ..." "Yellow"
    if ((Run-Quiet $npm.Source @("run", "build")) -ne 0 -or -not (Test-Path "out/index.html")) { Stop-Install "the web build failed." @("Details: $Log") }
    if ($webRev) { Write-NoBom (Join-Path (Get-Location) "out/.shaon-build") $webRev }
  } finally { Pop-Location }
  Say "Web app built." "Green"
}

# ================================================================ 6. models
Step "6/8  Speech models (CPU demo mode)"
if (-not (Test-Path $hfTokenFile)) {
  if ($NonInteractive) { Say "Optional Hugging Face token: skipped (non-interactive)." "Gray" }
  else {
    Write-Host "  Optional: a Hugging Face token unlocks IndicConformer (better Hindi/Bengali/Kannada recognition)." -ForegroundColor Gray
    Write-Host "  It needs a free account and accepting the model terms on huggingface.co. Most people skip this." -ForegroundColor Gray
    $tok = ""
    if ([Console]::IsInputRedirected) { $tok = Read-Host "  Hugging Face token (hf_...) or Enter to skip" }   # piped input (tests): no hidden prompt possible
    else {
      $sec = Read-Host "  Paste a Hugging Face token (hf_...) or press Enter to skip" -AsSecureString
      try { $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec); $tok = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b); [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) } catch {}
    }
    if ($tok -and $tok.Trim().StartsWith("hf_")) {
      $env:HF_TOKEN = $tok.Trim()   # this process only; saved by huggingface_hub in your user profile, never in the ShaOn folder
      $null = Run-Quiet $Py @("-c", "import os; from huggingface_hub import login; login(token=os.environ['HF_TOKEN'], add_to_git_credential=False)")
      Write-NoBom $hfTokenFile "given"
      $Extras = "$Extras,stt-indic"
      Say "Token saved for Hugging Face downloads. Installing the IndicConformer extras ..." "Green"
      $null = Run-Live $Py @("-m", "pip", "install", "--disable-pip-version-check", "-c", "deploy/requirements-cpu.txt", "-e", ".[$Extras]")
    } else { Write-NoBom $hfTokenFile "skipped"; Say "Skipped (you can add it later: delete data\install\hf_token_asked and run again)." "Gray" }
    $tok = $null
  }
}
$fetchArgs = @("scripts/fetch_models.py")
if ((Get-FileText $hfTokenFile).Trim() -eq "given") { $fetchArgs += "--optional" }
$code = Run-Live $Py $fetchArgs
if ($code -eq 3) { Stop-Install "not enough disk space for the models." @("Free space on this drive (see the sizes above) and run again: finished downloads are kept.") }
if ($code -ne 0) { Stop-Install "some model downloads did not finish." @("Run the installer again: it resumes where it stopped (partial files are kept).", "If it stalls repeatedly: check the connection, pause VPN/antivirus web filtering, or try another network.") }

# ================================================================ 7. doctor + self-test
Step "7/8  Doctor and self-test (one voice + one transcription per language, no Claude call)"
$null = Run-Live $Py @("scripts/doctor.py")
$selfMark = Join-Path $State "selftest.ok"
$selfSha = Get-Sha ($depsSha + (Capture $Git @("-C", $Root, "rev-parse", "HEAD")))
if ((Get-FileText $selfMark).Trim() -eq $selfSha) { Say "Self-test already passed for this version - skipped." "Green" }
else {
  $code = Run-Live $Py @("scripts/selftest.py")
  if ($code -ne 0) { Stop-Install "the self-test failed (see the table above for the language and the reason)." @("Run the installer again; it repairs missing packages and models.", "If the same language fails again, send the table above to whoever set up ShaOn.") }
  Write-NoBom $selfMark $selfSha
}

# ================================================================ 8. share
$mins = [math]::Round(((Get-Date) - $Started).TotalMinutes, 1)
Step "8/8  Installed in $mins min. Starting the share launcher ..."
if ($NoShare) { Say "Done (-NoShare). Start sharing any time: double-click ShaOn-Share.bat" "Green"; exit 0 }
$share = Join-Path $Root "scripts/share.ps1"
$sa = @{}
for ($i = 0; $i -lt $ShareArgs.Count; $i++) {
  $a = $ShareArgs[$i]
  if ($a -match "^-(\w+)$") {
    $name = $Matches[1]
    if ($i + 1 -lt $ShareArgs.Count -and $ShareArgs[$i + 1] -notmatch "^-\w+$") { $sa[$name] = $ShareArgs[$i + 1]; $i++ } else { $sa[$name] = $true }
  }
}
if ($NonInteractive) { $sa["NonInteractive"] = $true }
& $share @sa
exit $LASTEXITCODE
