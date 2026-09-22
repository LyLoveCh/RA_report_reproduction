param(
  [switch]$Docker
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $env:OPENAI_API_KEY) {
  Write-Host "未设置 OPENAI_API_KEY。先执行:"
  Write-Host '  $env:OPENAI_API_KEY = "sk-..."'
  Write-Host "不要把 key 写进 Git。"
  exit 1
}

$ra = Join-Path $Root "vendor\RepairAgent\repair_agent"
if (-not (Test-Path (Join-Path $ra "repairagent.py"))) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Root "vendor") | Out-Null
  git clone --depth 1 https://github.com/sola-st/RepairAgent.git (Join-Path $Root "vendor\RepairAgent")
}

Set-Location $ra
Write-Host "只跑 Chart 1 / gpt-4o-mini / max-cycles 40"
$argList = @(
  "repairagent.py", "run",
  "--bugs", "Chart 1",
  "--model", "gpt-4o-mini",
  "--temperature", "0",
  "--max-cycles", "40"
)
if ($Docker) { $argList += "--docker" }
python @argList
exit $LASTEXITCODE
