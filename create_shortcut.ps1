# Creates "Movie Poster Explorer" shortcuts on the Desktop and in the Start Menu
# that run the silent launcher (no console window) with the app icon.
#
#   powershell -ExecutionPolicy Bypass -File .\create_shortcut.ps1

$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbs     = Join-Path $project 'Launch MovieProject (silent).vbs'
$icon    = Join-Path $project 'static\icon.ico'
$name    = 'Movie Poster Explorer'

foreach ($f in @($vbs, $icon)) {
    if (-not (Test-Path -LiteralPath $f)) { throw "Missing $f" }
}

# Target wscript.exe (not the .vbs itself) so Windows offers "Pin to taskbar"
$wscript = Join-Path $env:WINDIR 'System32\wscript.exe'

$targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs')
)

$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $targets) {
    $lnkPath = Join-Path $dir "$name.lnk"
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath       = $wscript
    $lnk.Arguments        = '"' + $vbs + '"'
    $lnk.WorkingDirectory = $project
    $lnk.IconLocation     = "$icon,0"
    $lnk.Description      = 'Open the Movie Poster Explorer library'
    $lnk.Save()
    Write-Host "Created $lnkPath"
}

Write-Host ''
Write-Host 'To pin it: right-click the Desktop shortcut (Windows 11: Show more options) -> Pin to taskbar.'
