@echo off
setlocal
cd /d "%~dp0"
where nvcc >nul 2>nul
if errorlevel 1 goto missing_cuda
where cl >nul 2>nul
if errorlevel 1 goto missing_buildtools
".venv\Scripts\python.exe" backend\check_ltx_setup.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install torch==2.7.1+cu128 torchvision==0.22.1+cu128 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r backend\requirements-ltx.txt packaging==25.0 wheel==0.45.1 ninja==1.11.1.4 setuptools==84.2.1
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --no-build-isolation "git+https://github.com/Lightricks/LTX-Video-Q8-Kernels.git@f3066edea210082799ca5a2bbf9ef0321c5dd8fc"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import torch,ltx_video,q8_kernels; assert torch.cuda.is_available(); print('CUDA:',torch.version.cuda,'GPU:',torch.cuda.get_device_name(0))"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
echo LTX dependencies are installed. Actual inference remains unverified until a real clip is tested.
echo Model weights require separate explicit authorization. Generation does not download weights.
pause
exit /b 0
:missing_cuda
echo Install NVIDIA CUDA Toolkit 12.8 or later and open an x64 Visual Studio Developer Command Prompt with CUDA on PATH.
exit /b 1
:missing_buildtools
echo Install Visual Studio 2022 Build Tools with Desktop development with C++ and open an x64 Visual Studio Developer Command Prompt with CUDA on PATH.
exit /b 1
:failed
echo LTX dependency setup failed. No model weights were downloaded. Read the error above.
pause
exit /b 1
