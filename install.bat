@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ============================================================
echo   NOVEL TRANSLATOR - INSTALLER
echo   Checks and installs all required components
echo ============================================================
echo.

:: ============================================================
:: STEP 1: Python
:: ============================================================
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo  Download Python at: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    goto INSTALL_FAILED
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK] %%v

:: ============================================================
:: STEP 2: Python packages (requests — core dependency)
:: ============================================================
echo.
echo [2/5] Checking Python packages...

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo  [!] requests not found. Installing...
    pip install requests
    if errorlevel 1 (
        echo  [ERROR] Failed to install requests.
        goto INSTALL_FAILED
    )
    echo  [OK] requests installed
) else (
    echo  [OK] requests
)

:: ============================================================
:: STEP 3: Gemini CLI
:: ============================================================
echo.
echo [3/5] Checking Gemini CLI...

set "GEMINI_FOUND=false"
where gemini >nul 2>&1     && set "GEMINI_FOUND=true"
where gemini-cli >nul 2>&1 && set "GEMINI_FOUND=true"

if "!GEMINI_FOUND!"=="true" (
    echo  [OK] Gemini CLI found
    goto GEMINI_DONE
)

echo  [!] Gemini CLI not found.
echo.
echo      Gemini CLI is required for:
echo        - Novel research / character analysis (Hybrid mode)
echo        - Primary translation engine (Gemini-only mode)
echo      Without it, only Ollama-only mode will work.
echo.
echo      Install via npm:
echo        npm install -g @google/gemini-cli
echo.
set /p CONT_NO_GEMINI="  Continue without Gemini CLI? (Y/N, default=Y): "
if /i "!CONT_NO_GEMINI!"=="N" goto INSTALL_FAILED
echo  [INFO] Continuing without Gemini CLI.

:GEMINI_DONE

:: ============================================================
:: STEP 4: Ollama
:: ============================================================
echo.
echo [4/5] Checking Ollama...

set "OLLAMA_FOUND=false"
ollama --version >nul 2>&1
if not errorlevel 1 (
    set "OLLAMA_FOUND=true"
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo  [OK] Ollama: %%v
) else (
    echo  [!] Ollama not found.
    echo.
    set /p INSTALL_OLLAMA="  Install Ollama via winget? (Y/N, default=Y): "
    if /i "!INSTALL_OLLAMA!"=="N" (
        echo  [INFO] Skipped. Install manually: https://ollama.com/download
        goto STEP5
    )
    echo  Installing Ollama...
    winget install --id Ollama.Ollama -e --silent
    if errorlevel 1 (
        echo  [WARN] winget failed. Download manually: https://ollama.com/download
        goto STEP5
    )
    for /f "tokens=*" %%P in ('powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable(\"PATH\",\"Machine\")"') do set "PATH=%%P;%PATH%"
    ollama --version >nul 2>&1
    if errorlevel 1 (
        echo  [OK] Ollama installed. Please re-run install.bat to pull models.
        goto STEP5
    )
    set "OLLAMA_FOUND=true"
    echo  [OK] Ollama installed
)

:: Start Ollama service if needed
ollama list >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Starting Ollama service...
    start /b ollama serve >nul 2>&1
    timeout /t 3 >nul
)

:: ============================================================
:: GPU Detection (for model recommendations)
:: ============================================================
echo.
echo  Detecting GPU...
set "GPU_NAME=CPU only"
set "GPU_VENDOR=unknown"
set "VRAM=0"
set "OLLAMA_RECOMMENDED=qwen2.5:3b"
set "OLLAMA_REASON=no GPU detected"
set "NLLB_RECOMMENDED=600M"

for /f "tokens=1,2 delims==" %%K in ('python "%SCRIPT_DIR%\check_gpu.py" detect 2^>nul') do (
    if "%%K"=="GPU_NAME"           set "GPU_NAME=%%L"
    if "%%K"=="GPU_VENDOR"         set "GPU_VENDOR=%%L"
    if "%%K"=="VRAM"               set "VRAM=%%L"
    if "%%K"=="OLLAMA_RECOMMENDED" set "OLLAMA_RECOMMENDED=%%L"
    if "%%K"=="OLLAMA_REASON"      set "OLLAMA_REASON=%%L"
    if "%%K"=="NLLB_RECOMMENDED"   set "NLLB_RECOMMENDED=%%L"
)

if "!GPU_VENDOR!"=="nvidia" (
    echo  [GPU] !GPU_NAME! — VRAM: !VRAM! GB
) else if "!GPU_VENDOR!"=="amd" (
    echo  [GPU] !GPU_NAME! (AMD)
) else (
    echo  [GPU] No discrete GPU detected — CPU mode
)

echo  Recommended model(s): !OLLAMA_RECOMMENDED!
echo  Reason: !OLLAMA_REASON!

:: Check which models are already pulled
set "OLL_ST_1= " & set "OLL_ST_2= " & set "OLL_ST_3= "
set "OLL_ST_4= " & set "OLL_ST_5= " & set "OLL_ST_6= "
set "OLL_ST_7= " & set "OLL_ST_8= " & set "OLL_ST_9= "
set "OLL_ST_10= "

for /f "skip=1 tokens=1" %%M in ('ollama list 2^>nul') do (
    if "%%M"=="qwen2.5:7b"           set "OLL_ST_1=[pulled]"
    if "%%M"=="qwen2.5:3b"           set "OLL_ST_2=[pulled]"
    if "%%M"=="gemma2:9b"            set "OLL_ST_3=[pulled]"
    if "%%M"=="gemma3:9b"            set "OLL_ST_4=[pulled]"
    if "%%M"=="gemma3:12b"           set "OLL_ST_5=[pulled]"
    if "%%M"=="dolphin-mistral:7b"   set "OLL_ST_6=[pulled]"
    if "%%M"=="dolphin-llama3:8b"    set "OLL_ST_7=[pulled]"
    if "%%M"=="aya:8b"               set "OLL_ST_8=[pulled]"
    if "%%M"=="exaone3.5:7.8b"       set "OLL_ST_9=[pulled]"
    if "%%M"=="translategemma:12b"   set "OLL_ST_10=[pulled]"
)

:OLLAMA_MODEL_LOOP
echo.
echo  Ollama models for translation:
echo  ------------------------------------------------------------------------------------
echo   No  Model                 Size    Best for                 Low-censor  Status
echo  ------------------------------------------------------------------------------------
echo   [1] qwen2.5:7b            ~4.7GB  Chinese novels           No          !OLL_ST_1!
echo   [2] qwen2.5:3b            ~2.0GB  Chinese (lighter)        No          !OLL_ST_2!
echo   [3] gemma2:9b             ~5.4GB  General                  No          !OLL_ST_3!
echo   [4] gemma3:9b             ~5.4GB  General (newer)          No          !OLL_ST_4!
echo   [5] gemma3:12b            ~8.1GB  General (best)           No          !OLL_ST_5!
echo   [6] dolphin-mistral:7b    ~4.1GB  Low-censor (English)     Yes         !OLL_ST_6!
echo   [7] dolphin-llama3:8b     ~4.7GB  Low-censor (English)     Yes         !OLL_ST_7!
echo   [8] aya:8b                ~4.8GB  Japanese novels          No          !OLL_ST_8!
echo   [9] exaone3.5:7.8b        ~4.7GB  Korean novels            No          !OLL_ST_9!
echo  [10] translategemma:12b    ~8.1GB  Translation-optimized    No          !OLL_ST_10!
echo  ------------------------------------------------------------------------------------
echo   [S] Skip / Done
echo  ------------------------------------------------------------------------------------
echo.
echo  Priority used by translator (per source language):
echo    Chinese  : qwen3 ^> translategemma ^> gemma3 ^> qwen2.5 ^> gemma2 ^> dolphin
echo    Japanese : aya ^> qwen3 ^> translategemma ^> gemma3 ^> qwen2.5
echo    Korean   : exaone ^> aya ^> qwen3 ^> translategemma ^> gemma3
echo    Other    : translategemma ^> gemma3 ^> qwen3 ^> qwen2.5 ^> gemma2
echo.
echo  GPU recommendation: !OLLAMA_RECOMMENDED!  (!OLLAMA_REASON!)
echo  Tip: translategemma:12b is fine-tuned for translation (55 languages).
echo       Install qwen2.5:7b or higher for best Chinese novel quality.
echo.

set /p OLLAMA_CHOICE="  Choose model to pull [1-9 / S, default=S]: "
if "!OLLAMA_CHOICE!"=="" goto STEP5
if /i "!OLLAMA_CHOICE!"=="S" goto STEP5

set "OLLAMA_MODEL="
if "!OLLAMA_CHOICE!"=="1"  set "OLLAMA_MODEL=qwen2.5:7b"
if "!OLLAMA_CHOICE!"=="2"  set "OLLAMA_MODEL=qwen2.5:3b"
if "!OLLAMA_CHOICE!"=="3"  set "OLLAMA_MODEL=gemma2:9b"
if "!OLLAMA_CHOICE!"=="4"  set "OLLAMA_MODEL=gemma3:9b"
if "!OLLAMA_CHOICE!"=="5"  set "OLLAMA_MODEL=gemma3:12b"
if "!OLLAMA_CHOICE!"=="6"  set "OLLAMA_MODEL=dolphin-mistral:7b"
if "!OLLAMA_CHOICE!"=="7"  set "OLLAMA_MODEL=dolphin-llama3:8b"
if "!OLLAMA_CHOICE!"=="8"  set "OLLAMA_MODEL=aya:8b"
if "!OLLAMA_CHOICE!"=="9"  set "OLLAMA_MODEL=exaone3.5:7.8b"
if "!OLLAMA_CHOICE!"=="10" set "OLLAMA_MODEL=translategemma:12b"

if "!OLLAMA_MODEL!"=="" goto OLLAMA_MODEL_LOOP

echo.
echo  Pulling !OLLAMA_MODEL!...
ollama pull !OLLAMA_MODEL!
if errorlevel 1 (
    echo  [ERROR] Failed to pull !OLLAMA_MODEL!
) else (
    echo  [OK] !OLLAMA_MODEL! ready
    :: Update status markers
    if "!OLLAMA_MODEL!"=="qwen2.5:7b"        set "OLL_ST_1=[pulled]"
    if "!OLLAMA_MODEL!"=="qwen2.5:3b"        set "OLL_ST_2=[pulled]"
    if "!OLLAMA_MODEL!"=="gemma2:9b"         set "OLL_ST_3=[pulled]"
    if "!OLLAMA_MODEL!"=="gemma3:9b"         set "OLL_ST_4=[pulled]"
    if "!OLLAMA_MODEL!"=="gemma3:12b"        set "OLL_ST_5=[pulled]"
    if "!OLLAMA_MODEL!"=="dolphin-mistral:7b"  set "OLL_ST_6=[pulled]"
    if "!OLLAMA_MODEL!"=="dolphin-llama3:8b"  set "OLL_ST_7=[pulled]"
    if "!OLLAMA_MODEL!"=="aya:8b"             set "OLL_ST_8=[pulled]"
    if "!OLLAMA_MODEL!"=="exaone3.5:7.8b"     set "OLL_ST_9=[pulled]"
    if "!OLLAMA_MODEL!"=="translategemma:12b" set "OLL_ST_10=[pulled]"
)
goto OLLAMA_MODEL_LOOP

:: ============================================================
:: STEP 5: NLLB (last-resort fallback, optional)
:: ============================================================
:STEP5
echo.
echo [5/5] Checking NLLB (last-resort fallback, optional)...
echo  Used only when ALL Ollama models fail to translate a chunk.
echo  Pure translation model — no context awareness.
echo.

set "NLLB_PKG_OK=false"
python -c "import transformers, torch, sentencepiece" >nul 2>&1 && set "NLLB_PKG_OK=true"

if "!NLLB_PKG_OK!"=="true" (
    echo  [OK] NLLB packages already installed (transformers, torch, sentencepiece)
    goto NLLB_MODEL_CHECK
)

echo  Missing: one or more of: transformers, torch, sentencepiece
echo.
set /p INSTALL_NLLB="  Install NLLB packages? (Y/N, default=Y): "
if /i "!INSTALL_NLLB!"=="N" (
    echo  [INFO] Skipped. NLLB fallback will be disabled.
    goto NLLB_DONE
)
echo  Installing packages...
pip install transformers sentencepiece
if errorlevel 1 (
    echo  [WARN] Package install may have issues. Check output above.
) else (
    echo  [OK] transformers + sentencepiece installed
)

:: Detect GPU for correct torch build
set "TORCH_URL=none"
set "TORCH_TAG=cpu"
for /f "tokens=1,2 delims==" %%K in ('python "%SCRIPT_DIR%\check_gpu.py" detect 2^>nul') do (
    if "%%K"=="TORCH_TAG" set "TORCH_TAG=%%L"
    if "%%K"=="TORCH_URL" set "TORCH_URL=%%L"
)

if "!TORCH_TAG!"=="cpu" (
    echo  Installing torch (CPU version)...
    pip install torch --index-url https://download.pytorch.org/whl/cpu
) else (
    echo  Installing torch (!TORCH_TAG! — GPU accelerated)...
    pip install torch --index-url !TORCH_URL!
)
if errorlevel 1 (
    echo  [WARN] torch install failed. Try manually: pip install torch
) else (
    echo  [OK] torch installed (!TORCH_TAG!)
)

python -c "import transformers, torch, sentencepiece" >nul 2>&1 && set "NLLB_PKG_OK=true"
if "!NLLB_PKG_OK!"=="true" (
    echo  [OK] All NLLB packages verified
) else (
    echo  [WARN] Some packages still missing. NLLB fallback may not work.
)

:NLLB_MODEL_CHECK

if "!NLLB_PKG_OK!"=="false" goto NLLB_DONE

:: Get NLLB recommendation based on GPU (reuse detect mode, no torch needed)
set "NLLB_RECOMMENDED=600M"
for /f "tokens=1,2 delims==" %%K in ('python "%SCRIPT_DIR%\check_gpu.py" detect 2^>nul') do (
    if "%%K"=="NLLB_RECOMMENDED" set "NLLB_RECOMMENDED=%%L"
)

:: Check if NLLB model is already downloaded
set "HF_HUB=%USERPROFILE%\.cache\huggingface\hub"
set "NLLB_600M_DIR=!HF_HUB!\models--facebook--nllb-200-distilled-600M"
set "NLLB_1B3_DIR=!HF_HUB!\models--facebook--nllb-200-distilled-1.3B"
set "NLLB_3B3_DIR=!HF_HUB!\models--facebook--nllb-200-3.3B"

set "NLLB_600M_ST=             "
set "NLLB_1B3_ST=             "
set "NLLB_3B3_ST=             "
if exist "!NLLB_600M_DIR!\" set "NLLB_600M_ST=[downloaded]  "
if exist "!NLLB_1B3_DIR!\"  set "NLLB_1B3_ST=[downloaded]  "
if exist "!NLLB_3B3_DIR!\"  set "NLLB_3B3_ST=[downloaded]  "

:NLLB_MODEL_LOOP
echo.
echo  NLLB Models (stored in: !HF_HUB!\):
echo  -----------------------------------------------------------------
echo   [1] nllb-200-distilled-600M   ~2.4 GB   lightweight             !NLLB_600M_ST!
echo   [2] nllb-200-distilled-1.3B   ~5.0 GB   balanced               !NLLB_1B3_ST!
echo   [3] nllb-200-3.3B             ~13 GB    best quality (VRAM 8GB+)!NLLB_3B3_ST!
echo   [S] Skip
echo  -----------------------------------------------------------------
echo   GPU recommendation: !NLLB_RECOMMENDED! model
echo  -----------------------------------------------------------------
echo.
set /p NLLB_DL="  Choose [1-3 / S, default=!NLLB_RECOMMENDED:~0,1!]: "
if "!NLLB_DL!"=="" (
    if "!NLLB_RECOMMENDED!"=="3.3B" (
        set "NLLB_DL=3"
    ) else if "!NLLB_RECOMMENDED!"=="1.3B" (
        set "NLLB_DL=2"
    ) else (
        set "NLLB_DL=1"
    )
)
if /i "!NLLB_DL!"=="S" goto NLLB_DONE
if "!NLLB_DL!"=="1" goto NLLB_DL_600M
if "!NLLB_DL!"=="2" goto NLLB_DL_1B3
if "!NLLB_DL!"=="3" goto NLLB_DL_3B3
goto NLLB_MODEL_LOOP

:NLLB_DL_600M
echo.
echo  Downloading nllb-200-distilled-600M (may take several minutes)...
python -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; AutoTokenizer.from_pretrained('facebook/nllb-200-distilled-600M'); AutoModelForSeq2SeqLM.from_pretrained('facebook/nllb-200-distilled-600M')"
if errorlevel 1 (
    echo  [ERROR] Download failed. Check internet connection and retry.
    goto NLLB_MODEL_LOOP
)
echo  [OK] nllb-200-distilled-600M downloaded
echo 600M> "%SCRIPT_DIR%\.nllb"
goto NLLB_DONE

:NLLB_DL_1B3
echo.
echo  Downloading nllb-200-distilled-1.3B (may take several minutes)...
python -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; AutoTokenizer.from_pretrained('facebook/nllb-200-distilled-1.3B'); AutoModelForSeq2SeqLM.from_pretrained('facebook/nllb-200-distilled-1.3B')"
if errorlevel 1 (
    echo  [ERROR] Download failed. Check internet connection and retry.
    goto NLLB_MODEL_LOOP
)
echo  [OK] nllb-200-distilled-1.3B downloaded
echo 1.3B> "%SCRIPT_DIR%\.nllb"
goto NLLB_DONE

:NLLB_DL_3B3
echo.
echo  Downloading nllb-200-3.3B (~13 GB, may take a while)...
python -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; AutoTokenizer.from_pretrained('facebook/nllb-200-3.3B'); AutoModelForSeq2SeqLM.from_pretrained('facebook/nllb-200-3.3B')"
if errorlevel 1 (
    echo  [ERROR] Download failed. Check internet connection and retry.
    goto NLLB_MODEL_LOOP
)
echo  [OK] nllb-200-3.3B downloaded
echo 3.3B> "%SCRIPT_DIR%\.nllb"

:NLLB_DONE

:: ============================================================
:: FINISH
:: ============================================================
echo.
echo ============================================================
echo  Installation Summary
echo ============================================================

:: Python
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Python      : %%v

:: Gemini
if "!GEMINI_FOUND!"=="true" (
    echo  Gemini CLI  : [OK]
) else (
    echo  Gemini CLI  : [NOT FOUND] — Hybrid/Gemini modes disabled
)

:: GPU
if "!GPU_DEVICE!"=="cuda" (
    echo  GPU         : !GPU_NAME! — !VRAM! GB VRAM
) else if "!GPU_DEVICE!"=="mps" (
    echo  GPU         : Apple Silicon (MPS)
) else (
    echo  GPU         : None (CPU mode)
)

:: Ollama + pulled models
if "!OLLAMA_FOUND!"=="true" (
    echo  Ollama      : [OK]
    echo  Models pulled:
    for /f "skip=1 tokens=1,2" %%M in ('ollama list 2^>nul') do (
        echo    - %%M  %%N
    )
) else (
    echo  Ollama      : [NOT FOUND] — install from https://ollama.com/download
)

:: NLLB
set "NLLB_STATUS=not installed"
if exist "%SCRIPT_DIR%\.nllb" (
    for /f "usebackq tokens=*" %%N in ("%SCRIPT_DIR%\.nllb") do set "NLLB_STATUS=%%N model"
) else if "!NLLB_PKG_OK!"=="true" (
    set "NLLB_STATUS=packages installed, model not downloaded"
)
echo  NLLB        : !NLLB_STATUS!

echo.
echo  Run the tool: python main.py   or   run.bat
echo ============================================================
echo.
pause
exit /b 0

:INSTALL_FAILED
echo.
echo ============================================================
echo  [FAILED] Installation incomplete.
echo  Fix the error above, then run install.bat again.
echo ============================================================
echo.
pause
exit /b 1
