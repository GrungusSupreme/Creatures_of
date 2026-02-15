param(
    [string]$ShortcutName = "Creatures of Catan.lnk"
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetPath = Join-Path $projectRoot "Launch_Creatures_of_Catan.bat"

if (-not (Test-Path $targetPath)) {
    throw "Launcher file not found: $targetPath"
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath $ShortcutName

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "C:\Windows\System32\SHELL32.dll,220"
$shortcut.Description = "Launch Creatures of Catan"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath"
