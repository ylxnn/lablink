$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
& "$projectRoot/.venv/Scripts/python.exe" "$projectRoot/scripts/start_lab.py"
