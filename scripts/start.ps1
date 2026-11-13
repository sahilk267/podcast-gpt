$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "`n=== Podcast GPT / Windows CPU Studio ===`n" -ForegroundColor Cyan

function Get-UsablePython {
  foreach ($version in @('3.11', '3.12', '3.10')) {
    try {
      & py "-$version" -c 'import sys; assert sys.version_info[:2] >= (3,10); print(sys.executable)' 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) { return @('py', "-$version") }
    } catch { }
  }
  try {
    & python -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12)' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return @('python') }
  } catch { }
  return $null
}

$python = Get-UsablePython
if (-not $python) {
  Write-Host 'Python 3.10-3.12 missing. Trying official winget package Python 3.11...' -ForegroundColor Yellow
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Python.Python.3.11 --exact --source winget --accept-package-agreements --accept-source-agreements
    $python = Get-UsablePython
  }
}
if (-not $python) {
  Write-Host 'Please install Python 3.11 (64-bit), then double-click START.bat again:' -ForegroundColor Red
  Write-Host 'https://www.python.org/downloads/release/python-3119/'
  exit 1
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  Write-Host 'Creating local Python environment...'
  if ($python.Length -eq 2) { & $python[0] $python[1] -m venv .venv }
  else { & $python[0] -m venv .venv }
  if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
}
$exe = (Resolve-Path '.venv\Scripts\python.exe').Path
$marker='.venv\requirements.sha256'
$hash=(Get-FileHash 'requirements.txt' -Algorithm SHA256).Hash
if (!(Test-Path $marker) -or (Get-Content $marker -Raw).Trim() -ne $hash) {
  Write-Host 'Installing/updating application dependencies (first run needs internet)...'
  & $exe -m pip install --disable-pip-version-check -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw 'pip install failed. Check network / antivirus / proxy.' }
  Set-Content -Path $marker -Value $hash
}
$port=8765
$baseUrl="http://127.0.0.1:$port"
try {
  $already=Invoke-WebRequest -Uri "$baseUrl/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
  if ($already.StatusCode -eq 200) {
    Write-Host 'Podcast GPT is already running. Opening browser...' -ForegroundColor Green
    Start-Process $baseUrl
    exit 0
  }
} catch { }
Write-Host "Starting local dashboard at $baseUrl" -ForegroundColor Green
$arguments=@('-m','uvicorn','podcast.app:app','--host','127.0.0.1','--port',"$port")
$proc=Start-Process -FilePath $exe -ArgumentList $arguments -PassThru -NoNewWindow
$ready=$false
for($attempt=0;$attempt -lt 40;$attempt++) {
  if ($proc.HasExited) { throw 'Server exited before becoming ready. See terminal errors.' }
  try {
    $reply=Invoke-WebRequest -Uri "$baseUrl/api/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
    if($reply.StatusCode -eq 200) { $ready=$true; break }
  } catch { }
  Start-Sleep -Milliseconds 500
}
if (!$ready) { throw 'Local server did not respond. Check local firewall/port 8765.' }
Start-Process $baseUrl
Write-Host 'App ready. Leave this terminal open while using Podcast GPT.' -ForegroundColor Green
Wait-Process -Id $proc.Id
