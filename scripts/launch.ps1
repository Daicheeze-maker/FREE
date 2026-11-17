# Opens ClipForge AI in its own app window (Microsoft Edge app mode) and stops the engine when the
# window is closed. Started by the "ClipForge AI" shortcut through ClipForge.vbs (no console window).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$pyw = Join-Path $backend ".venv\Scripts\pythonw.exe"
$data = if ($env:CLIPFORGE_DATA) { $env:CLIPFORGE_DATA } else { Join-Path $env:LOCALAPPDATA "ClipForge" }
$logs = Join-Path $data "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$errLog = Join-Path $logs "engine-errors.log"
$port = 8756
$url = "http://127.0.0.1:$port/"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Fail($msg) {
    [System.Windows.Forms.MessageBox]::Show($msg, "ClipForge AI", "OK", "Error") | Out-Null
    exit 1
}
function PortOpen {
    try { $c = New-Object Net.Sockets.TcpClient("127.0.0.1", $port); $c.Close(); return $true } catch { return $false }
}

if (-not (Test-Path $pyw)) {
    Fail "ClipForge is not set up yet.`n`nOpen the 'scripts' folder, right-click setup-windows.ps1 and choose 'Run with PowerShell'."
}

# Start the engine unless one is already running (e.g. the icon was clicked twice).
$engine = $null
if (-not (PortOpen)) {
    $engine = Start-Process -FilePath $pyw -ArgumentList "-m", "clipforge.main", "--port", "$port" `
        -WorkingDirectory $backend -PassThru -RedirectStandardError $errLog `
        -RedirectStandardOutput (Join-Path $logs "engine-output.log")

    # Small "Starting..." window while the engine loads.
    $splash = New-Object System.Windows.Forms.Form
    $splash.Text = "ClipForge AI"
    $splash.Size = New-Object System.Drawing.Size(360, 130)
    $splash.StartPosition = "CenterScreen"
    $splash.FormBorderStyle = "FixedDialog"
    $splash.ControlBox = $false
    $splash.TopMost = $true
    $splash.BackColor = [System.Drawing.Color]::FromArgb(14, 15, 17)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Starting ClipForge AI..."
    $label.ForeColor = [System.Drawing.Color]::FromArgb(230, 232, 235)
    $label.Font = New-Object System.Drawing.Font("Segoe UI", 11)
    $label.AutoSize = $false
    $label.Dock = "Fill"
    $label.TextAlign = "MiddleCenter"
    $splash.Controls.Add($label)
    $splash.Show()

    $t0 = Get-Date
    while (-not (PortOpen)) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 200
        $secs = ((Get-Date) - $t0).TotalSeconds
        if ($secs -gt 20) { $label.Text = "Still starting... the first start can take up to a minute." }
        if ($engine.HasExited -or $secs -gt 150) {
            $splash.Close()
            $detail = if (Test-Path $errLog) { (Get-Content $errLog -Tail 8) -join "`n" } else { "" }
            Fail "The ClipForge engine did not start.`n`n$detail`n`nFull details: $errLog"
        }
    }
    $splash.Close()
}

# Edge is part of Windows 10/11. A separate profile folder makes this window its own process, so we
# can tell when it is closed and stop the engine.
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) {
    # No Edge: use the default browser. The engine then keeps running until you sign out or restart.
    Start-Process $url
    exit 0
}

$appProfile = Join-Path $data "app-window"
Start-Process -FilePath $edge -ArgumentList @(
    "--app=$url", "--user-data-dir=`"$appProfile`"", "--window-size=1440,900",
    "--no-first-run", "--no-default-browser-check")

function WindowOpen {
    [bool](Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" |
           Where-Object { $_.CommandLine -like "*$appProfile*" })
}
Start-Sleep -Seconds 5
while (WindowOpen) { Start-Sleep -Seconds 2 }

# Window closed: stop the engine we started (an engine started by someone else is left alone).
if ($engine -and -not $engine.HasExited) { Stop-Process -Id $engine.Id -Force }
