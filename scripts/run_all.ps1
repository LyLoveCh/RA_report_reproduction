param(
  [switch]$WithD4j,
  [switch]$OnlyMini,
  [switch]$SkipOfficial
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  py -3 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -U pip
  .\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
}
$argsList = @()
if ($WithD4j) { $argsList += "--with-d4j" }
if ($OnlyMini) { $argsList += "--only-mini" }
if ($SkipOfficial) { $argsList += "--skip-official" }
& .\.venv\Scripts\python.exe scripts\run_reproduction.py @argsList
exit $LASTEXITCODE
