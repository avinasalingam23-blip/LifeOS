param([switch]$GuiCheck)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
Set-Location -LiteralPath $projectRoot

function Assert-ProjectPath([string]$Candidate) {
    $resolved = [IO.Path]::GetFullPath($Candidate)
    $prefix = $projectRoot.TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build path is outside the project: $resolved"
    }
    return $resolved
}

$buildId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$jobRoot = Assert-ProjectPath (Join-Path $projectRoot "build\package-$buildId")
$stagedDist = Join-Path $jobRoot 'dist'
$stagedApp = Join-Path $stagedDist 'LifeOS'
$destination = Assert-ProjectPath (Join-Path $projectRoot 'dist\LifeOS')
$previousCache = $env:PYINSTALLER_CONFIG_DIR
try {
    & '.\.venv\Scripts\python.exe' -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed; build stopped.' }
    & '.\.venv\Scripts\python.exe' -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $jobRoot 'cache'
    & '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --distpath $stagedDist --workpath (Join-Path $jobRoot 'work') LifeOS.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable packaging failed; previous output is intact.' }
    if ($GuiCheck) {
        $profilePath = Join-Path $jobRoot 'frozen-gui-check'
        $check = Start-Process -FilePath (Join-Path $stagedApp 'LifeOS.exe') -ArgumentList @('--smoke-test','--data-dir',('"' + $profilePath + '"')) -WindowStyle Hidden -PassThru -Wait
        if ($check.ExitCode -ne 0) { throw 'Packaged GUI checks failed; previous output is intact.' }
        $results = Get-Content -LiteralPath (Join-Path $profilePath 'smoke-results.json') -Raw | ConvertFrom-Json
        if ($results.result -ne 'PASS' -or -not $results.frozen -or $results.themes_checked -ne 2) {
            throw 'Packaged GUI verification incomplete; previous output is intact.'
        }
    }
    Copy-Item -LiteralPath 'PORTABLE_README.txt' -Destination (Join-Path $stagedApp 'README.txt')
    if (Test-Path -LiteralPath $destination) {
        $archive = Assert-ProjectPath (Join-Path $projectRoot "dist\archive\LifeOS-$buildId")
        New-Item -ItemType Directory -Path (Split-Path -Parent $archive) -Force | Out-Null
        Move-Item -LiteralPath $destination -Destination $archive
        Write-Host "Previous package preserved at $archive"
    }
    $checkedStage = Assert-ProjectPath $stagedApp
    Move-Item -LiteralPath $checkedStage -Destination $destination
    Write-Host "Built $destination\LifeOS.exe. Keep the entire folder, including _internal."
}
finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
}
