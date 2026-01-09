@echo off
chcp 65001 >nul
title VE3 - Setup Worker (Image/Video)

:: Use pushd for UNC path support
pushd "%~dp0"

echo ============================================
echo   VE3 TOOL - SETUP MAY AO (WORKER)
echo   Dung cho: run_worker.bat
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python chua duoc cai dat!
    echo         Tai tai: https://www.python.org/downloads/
    echo         Nho tick "Add Python to PATH" khi cai!
    popd
    pause
    exit /b 1
)
echo [OK] Python da cai

:: Install dependencies for worker
echo.
echo [1/2] Cai thu vien co ban...
pip install pyyaml openpyxl requests pillow pyperclip pyautogui websocket-client -q
echo [OK] Thu vien co ban

echo.
echo [2/2] Cai thu vien Chrome automation...
pip install selenium webdriver-manager undetected-chromedriver DrissionPage -q
echo [OK] Chrome automation

:: Install Chrome Portable if .paf exists and Chrome not installed
echo.
echo [*] Kiem tra Chrome Portable...
if exist "GoogleChromePortable\GoogleChromePortable.exe" (
    echo [OK] Chrome Portable da cai
    echo     %CD%\GoogleChromePortable\GoogleChromePortable.exe
    goto :check_done
)

:: Try to install from .paf file
for %%f in (GoogleChromePortable*.paf.exe) do (
    echo [*] Tim thay file cai dat: %%f
    echo.
    echo     Dang mo trinh cai dat Chrome Portable...
    echo     Hay chon thu muc cai dat la: %CD%
    echo.
    start /wait "" "%%f"
    if exist "GoogleChromePortable\GoogleChromePortable.exe" (
        echo [OK] Da cai Chrome Portable thanh cong!
        echo     %CD%\GoogleChromePortable\GoogleChromePortable.exe
        goto :check_done
    )
)

:: Check other Chrome locations
if exist "%USERPROFILE%\Documents\GoogleChromePortable\GoogleChromePortable.exe" (
    echo [OK] Chrome Portable (Documents) da cai
    echo     %USERPROFILE%\Documents\GoogleChromePortable\GoogleChromePortable.exe
    goto :check_done
)

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [OK] Chrome da cai (Program Files)
    goto :check_done
)

if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [OK] Chrome da cai (Program Files x86)
    goto :check_done
)

if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    echo [OK] Chrome da cai (LocalAppData)
    goto :check_done
)

:: No Chrome found
echo [!] Chua tim thay Chrome!
echo.
echo     Cach 1: Copy file GoogleChromePortable*.paf.exe vao thu muc tool
echo             Chay lai SETUP_WORKER.bat de cai tu dong
echo.
echo     Cach 2: Copy thu muc GoogleChromePortable vao:
echo             %CD%\GoogleChromePortable\
echo.
echo     Cach 3: Cai Chrome binh thuong

:check_done
echo.
echo ============================================
echo   HOAN TAT SETUP MAY AO!
echo ============================================
echo.
echo   Cac lenh co the chay:
echo   - run_worker.bat   : 1 Chrome (full man hinh)
echo   - run_2worker.bat  : 2 Chrome (chia doi)
echo   - run_3worker.bat  : 3 Chrome (grid)
echo.
echo ============================================

popd
pause
