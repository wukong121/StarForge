# Prefer the project's environment, then an installed Python, then Codex's bundled runtime.
$projectPython = Join-Path $PSScriptRoot '../.venv/Scripts/python.exe'
$installedPython = Get-Command python -ErrorAction SilentlyContinue
$codexPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $projectPython) {
    $starforgePython = $projectPython
} elseif ($installedPython) {
    $starforgePython = $installedPython.Source
} elseif (Test-Path -LiteralPath $codexPython) {
    $starforgePython = $codexPython
} else {
    throw 'Install Python 3.11+ (ARM64 or x64), or create .venv before running StarForge.'
}
& $starforgePython @args
exit $LASTEXITCODE
