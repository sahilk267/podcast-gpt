$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host 'Optional SadTalker CPU setup. This downloads several GB and installs legacy Python packages.' -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git missing: https://git-scm.com/download/win' }
try { & py -3.8 --version; if ($LASTEXITCODE -ne 0) { throw 'Python 3.8 missing' } }
catch { throw 'Python 3.8.10 64-bit required for optional SadTalker. Install from https://www.python.org/downloads/release/python-3810/ then rerun.' }
if (-not (Test-Path third_party)) { New-Item -ItemType Directory -Path third_party | Out-Null }
if (-not (Test-Path third_party/SadTalker/inference.py)) {
  git clone --depth 1 https://github.com/OpenTalker/SadTalker.git third_party/SadTalker
  if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
}
if (-not (Test-Path '.venv38\Scripts\python.exe')) { & py -3.8 -m venv .venv38; if($LASTEXITCODE -ne 0){throw 'venv failed'} }
$exe=(Resolve-Path '.venv38\Scripts\python.exe').Path
& $exe -m pip install 'pip<25' 'setuptools<70' wheel
if ($LASTEXITCODE -ne 0) { throw 'Legacy pip setup failed' }
& $exe -m pip install 'torch==1.12.1+cpu' 'torchvision==0.13.1+cpu' 'torchaudio==0.12.1' --extra-index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch CPU install failed' }
Push-Location third_party/SadTalker
try {
 & $exe -m pip install -r requirements.txt
 if ($LASTEXITCODE -ne 0) { throw 'SadTalker requirements failed; see docs/SADTALKER.md' }
 New-Item -ItemType Directory -Force checkpoints,gfpgan/weights | Out-Null
 $base='https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc'
 $downloads=@(
   @("$base/SadTalker_V0.0.2_256.safetensors",'checkpoints/SadTalker_V0.0.2_256.safetensors'),
   @("$base/mapping_00109-model.pth.tar",'checkpoints/mapping_00109-model.pth.tar'),
   @("$base/mapping_00229-model.pth.tar",'checkpoints/mapping_00229-model.pth.tar'),
   @('https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth','gfpgan/weights/alignment_WFLW_4HG.pth'),
   @('https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth','gfpgan/weights/detection_Resnet50_Final.pth')
 )
 foreach($entry in $downloads){
   if(!(Test-Path $entry[1]) -or (Get-Item $entry[1]).Length -lt 100000){
     Write-Host "Downloading $($entry[1])"
     & curl.exe -L --fail --retry 3 --connect-timeout 30 -o $entry[1] $entry[0]
     if($LASTEXITCODE -ne 0){throw "Download failed: $($entry[1])"}
   }
 }
} finally { Pop-Location }
Write-Host 'AI engine installed. A short CPU inference test is still required.' -ForegroundColor Green
