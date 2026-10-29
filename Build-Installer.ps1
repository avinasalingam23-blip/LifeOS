param([string]$IsccPath)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $IsccPath) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $IsccPath = $command.Source }
    $locations = @(
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path $PSScriptRoot '.test-artifacts\installer-build-01\compiler\ISCC.exe')
    )
    foreach ($location in $locations) {
        if (-not $IsccPath -and (Test-Path -LiteralPath $location)) { $IsccPath = $location }
    }
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath)) {
    throw 'Inno Setup compiler not found. Obtain it from https://jrsoftware.org/isdl.php, then pass -IsccPath. This script does not install tools or rebuild the app.'
}
& '.\.venv\Scripts\python.exe' tools\build_installer.py --compiler $IsccPath
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed; review the project-local build log.' }
