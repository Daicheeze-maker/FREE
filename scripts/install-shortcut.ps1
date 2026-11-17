# Creates "ClipForge AI" shortcuts on the Desktop and in the Start menu.
$root = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $root "ClipForge.vbs"
$icon = Join-Path $root "src-tauri\icons\icon.ico"
$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "ClipForge AI.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "ClipForge AI.lnk")
)
foreach ($t in $targets) {
    $s = $shell.CreateShortcut($t)
    $s.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
    $s.Arguments = "`"$vbs`""
    $s.WorkingDirectory = $root
    $s.IconLocation = $icon
    $s.Description = "ClipForge AI - local AI video clipping studio"
    $s.Save()
}
Write-Host "Created the 'ClipForge AI' shortcut on your Desktop and in the Start menu." -ForegroundColor Green
