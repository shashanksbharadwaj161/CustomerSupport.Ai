# Install and share in two steps

Let a client or a friend talk to ShaOn from their own phone, using a link you send them.
Everything runs on **your Windows 10/11 PC**; a free Cloudflare "Quick Tunnel" gives it a temporary public https address.
Nothing costs money except the Claude API, and only after you paste your own key into ShaOn's Settings page.

> **Just testing on your own PC?** Double-click **`ShaOn-Local.bat`**: the full app opens with no passcode, and the API
> key, model and spend cap are editable in Settings. It answers only this PC (docs/RUNBOOK.md, "Local preview").
> Use the steps below only when someone else should open a link.

## Step 1 - get ShaOn and start the installer

**Easiest (one line).** Open PowerShell (Start menu > type `PowerShell` > Enter), paste this line, press Enter:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force; iwr -useb https://raw.githubusercontent.com/shashanksbharadwaj161/CustomerSupport.Ai/claude/sweet-ptolemy-7qza59/scripts/install.ps1 -OutFile "$env:TEMP\shaon-install.ps1"; & "$env:TEMP\shaon-install.ps1"
```

It installs into `C:\Users\<you>\ShaOn`. (`-Scope Process` relaxes the script policy for that one window only.)

**Or with a ZIP:** on the GitHub page of the repository, switch to the branch `claude/sweet-ptolemy-7qza59`, click
**Code > Download ZIP**, right-click the ZIP > **Extract All**, open the folder and double-click **`ShaOn-Install.bat`**.
If Windows says "Windows protected your PC", click **More info > Run anyway** (the file is a plain text script you can open in Notepad).

## Step 2 - wait for the link

The installer window does everything and ends with **the link, the visitor passcode and a QR code**:

1. Checks the PC and prints a table (Windows version, free disk, RAM, CPU/GPU, internet). It stops early with a plain
   explanation if the disk is too small (under 12 GB free).
2. Installs what is missing with winget: Git, Python 3.12, Node.js LTS, cloudflared, eSpeak NG, FFmpeg, the Visual C++ runtime.
   Windows may ask "Do you want to allow this app to make changes?" - click **Yes**.
3. Gets the code (or updates it with `git pull`), installs pinned Python packages, builds the web app.
4. Asks once for an optional Hugging Face token (better Hindi/Bengali/Kannada recognition) - just press **Enter** to skip.
5. Downloads the speech models with progress bars, then runs a self-test: one voice and one transcription per language.
6. **First run only - your Anthropic key:** a browser opens `http://127.0.0.1:8000/settings/` on your PC. Sign in with the
   admin passcode shown in the window, paste the key, press **Save** and **Test key**, then press Enter in the window.
   The key is never typed into the window, never logged and never sent through the tunnel. Also set a monthly spend limit
   for the key in the Anthropic Console; ShaOn itself stops at its own cap (10 USD by default, shown in Settings).
   No key yet? Type `skip`: calls then use scripted demo replies.
7. Opens the tunnel and prints **SHARE THIS LINK** + **VISITOR PASSCODE** + a QR code (also saved in `share-link.txt`
   and `share-qr.png`). Send the link and the passcode. Keep the **admin passcode** for yourself.

Sizes measured on the test machine: models 7.98 GB, Python environment 3.4 GB, web build 0.6 GB; download sizes of the
Windows tools and packages are estimates.

| | First run | Later runs |
|---|---|---|
| Download | about 10 GB (models 8 GB, Python packages ~1.5 GB, tools ~0.5 GB, web packages ~0.2 GB) | nothing (only updates) |
| Disk used | about 14 GB (models 8 GB, `.venv` 3.4 GB, web 0.6 GB, tools ~1 GB) | - |
| Time | 30-60 minutes on a typical home connection (mostly downloading) | 2-5 minutes (checks take seconds; loading the speech models takes the rest) |

Later, double-click **`ShaOn-Share.bat`** to share again (or `ShaOn-Install.bat`, which also updates the code first).
Every run makes a **new link and a new visitor passcode**.

## What your visitor sees
A passcode screen, then **Get ready** (test microphone, tap to hear a test sound - needed on iPhone - connection check,
which languages are ready), a banner saying it is a demo on a PC, then **Start call**.

## What the link does NOT give you
- **It dies when your laptop sleeps, loses internet, or you close the window.** Plug the laptop in and set
  Settings > System > Power > Screen and sleep > "When plugged in, put my device to sleep after" = **Never** while sharing.
  Closing the lid usually means sleep too (Control Panel > Power Options > "Choose what closing the lid does").
  After sleep, the old link is dead: the window prints a NEW link when the tunnel comes back.
- **The address changes every time** you start sharing, and when the tunnel drops (the window says the old link is DEAD
  and prints the new one in green).
- **Not for the public.** Quick Tunnels are a free testing service: no uptime guarantee, about 200 requests in flight at
  most. Only send the link to people you choose.
- **Not instant.** Without a GPU, expect about 3-6 seconds before each reply. The Bengali and Kannada voices are robotic
  test voices (MMS, non-commercial licence, demo only) - say so before the demo.
- **Limits:** at most 2 calls at the same time (others see "Agent is busy"), each call ends after 5 minutes. Change them
  with `scripts\share.ps1 -MaxCalls 3 -MaxCallSeconds 600`.

## While sharing
- A status line every 30 s: tunnel up, which languages are ready, active calls, Claude spend.
- The API key cannot be changed while sharing (protection). Stop sharing, start again, and the key step runs if no key is set.
- Website crawling is admin-only while sharing, with private/internal addresses blocked.
- Stop: press Ctrl+C in the window or close it. The link stops working immediately.

## If something goes wrong

| What you see | What to do |
|---|---|
| "winget (Windows Package Manager) is missing" | Install **App Installer** from the Microsoft Store: https://apps.microsoft.com/detail/9NBLGGH4NNS1 , then run again |
| Antivirus / SmartScreen blocks the .bat, Python or cloudflared | "More info > Run anyway"; in Windows Security allow the ShaOn folder (Virus & threat protection > Exclusions), then run again |
| "not enough free disk space" | Free space (Settings > System > Storage > Cleanup recommendations) or install on another drive: `scripts\install.ps1 -InstallDir D:\ShaOn` |
| "Port 8000 is already in use" | ShaOn is already running in another window: close it, or run `scripts\share.ps1 -Port 8010` |
| Model download stalls or stops | Close the window and run the installer again: finished files are kept and it continues where it stopped. Pause VPNs or "web protection" features, or try another network |
| "winget could not install ..." | Run the command it prints by hand in PowerShell; if it needs a restart, restart and run again |
| "... was installed but this window cannot see it yet" | Close the window and run the installer again |
| "could not download the code ... may be private" | Follow the sign-in steps it prints (GitHub sign-in window, or `gh auth login`), or use the ZIP download |
| "the self-test failed" | Run the installer again (it repairs packages and models); the table shows which language and why |
| Visitor: "Connection lost" | Your PC slept or the tunnel restarted: look in the window for the NEW link |
| Visitor: "Agent is busy" | Two calls are already running; wait, or start with `-MaxCalls 3` |
| Visitor hears nothing on iPhone | Ask them to tap "Play test sound" first and turn off silent mode |

Logs: the quiet installer steps write to `%TEMP%\shaon-install\install.log`; the running app writes to `data\share\`.
Neither contains the API key or the passcodes beyond what the window shows.
