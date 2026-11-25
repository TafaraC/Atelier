[CmdletBinding()]
param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\Atelier'), [switch]$SkipShortcut)
$ErrorActionPreference = 'Stop'
$runtime = (Get-Command python -CommandType Application | Select-Object -First 1).Source
& $runtime -c 'import sys, tkinter, sqlite3; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or later with Tcl/Tk support.' }
$windowed = Join-Path (Split-Path $runtime) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $windowed)) { throw 'The Python installation needs pythonw.exe.' }
$package = Join-Path $Destination 'atelier'
New-Item -ItemType Directory -Force -Path $package | Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'atelier') -Filter '*.py' -File |
    Copy-Item -Destination $package -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $Destination -Force
if (-not $SkipShortcut) {
    $programs = [Environment]::GetFolderPath('Programs')
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $programs 'Atelier.lnk'))
    $shortcut.TargetPath = $windowed
    $shortcut.Arguments = '-m atelier'
    $shortcut.WorkingDirectory = $Destination
    $shortcut.Save()
}
Write-Output "Installed Atelier in $Destination"

