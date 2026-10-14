@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher not found. Install Python 3.11 x64 from python.org.
    exit /b 1
)

py -3.11 --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 not found. Install Python 3.11 x64 from python.org.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PYTHON%" -m pip install -r voice_changer_build_requirements.txt
if errorlevel 1 exit /b 1

"%PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --name AURELIA_Voice ^
    --collect-all av ^
    --collect-all ctranslate2 ^
    --collect-all edge_tts ^
    --collect-all faster_whisper ^
    --collect-all huggingface_hub ^
    --collect-all spellchecker ^
    --collect-all sounddevice ^
    --collect-all tokenizers ^
    --collect-all websockets ^
    --hidden-import ctranslate2 ^
    --hidden-import av ^
    aurelia_voice_changer.py
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\AURELIA_Voice\*' -DestinationPath 'AURELIA_Voice_Windows.zip' -Force"
if errorlevel 1 exit /b 1

echo.
echo EXE: dist\AURELIA_Voice\AURELIA_Voice.exe
echo Portable package: AURELIA_Voice_Windows.zip