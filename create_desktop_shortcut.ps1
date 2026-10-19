$desktopPath = [Environment]::GetFolderPath("Desktop")
$projectPath = "C:\Users\User\Desktop\zeno-ai-assistant"
$shortcutPath = Join-Path $desktopPath "Zeno Desktop AI Assistant.lnk"
$pythonwPath = Join-Path $projectPath ".venv\Scripts\pythonw.exe"
$mainPath = Join-Path $projectPath "main.py"
$iconPath = Join-Path $projectPath "zeno_icon.ico"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$mainPath`""
$shortcut.WorkingDirectory = $projectPath
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Zeno Desktop AI Assistant"
$shortcut.Save()

Write-Host "Desktop shortcut created at: $shortcutPath"
