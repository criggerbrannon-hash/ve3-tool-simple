@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title VE3 - Update Tool

echo ============================================
echo   VE3 TOOL - CAP NHAT PHIEN BAN MOI
echo ============================================
echo.

:: Check git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git chua duoc cai dat!
    echo         Tai tai: https://git-scm.com/downloads
    pause
    exit /b 1
)

:: Show current branch and version
echo [INFO] Branch hien tai:
git branch --show-current
echo.
echo [INFO] Phien ban hien tai:
git log -1 --format="  Commit: %%h - %%s (%%cr)"
echo.

:: Ask for branch
echo ============================================
echo   CHON BRANCH DE CAP NHAT:
echo ============================================
echo   1. main (chinh thuc)
echo   2. master
echo   3. Nhap branch khac (vd: claude/fix-video-reload-DtCEu)
echo   4. Giu nguyen branch hien tai
echo ============================================
echo.
set /p choice="Lua chon (1-4): "

if "%choice%"=="1" (
    set BRANCH=main
) else if "%choice%"=="2" (
    set BRANCH=master
) else if "%choice%"=="3" (
    set /p BRANCH="Nhap ten branch: "
) else if "%choice%"=="4" (
    for /f "tokens=*" %%a in ('git branch --show-current') do set BRANCH=%%a
) else (
    echo [ERROR] Lua chon khong hop le!
    pause
    exit /b 1
)

echo.
echo [*] Branch duoc chon: %BRANCH%
echo.

:: Fetch latest
echo [*] Dang kiem tra ban cap nhat tu origin/%BRANCH%...
git fetch origin %BRANCH% 2>nul

if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay branch: %BRANCH%
    echo.
    echo [INFO] Cac branch co san:
    git branch -r | findstr /V "HEAD"
    pause
    exit /b 1
)

:: Checkout branch if different
for /f "tokens=*" %%a in ('git branch --show-current') do set CURRENT=%%a
if not "%CURRENT%"=="%BRANCH%" (
    echo [*] Dang chuyen sang branch %BRANCH%...
    git stash >nul 2>&1
    git checkout %BRANCH% 2>nul || git checkout -b %BRANCH% origin/%BRANCH%
)

:: Show changes
echo.
echo [INFO] Cac thay doi moi:
git log HEAD..origin/%BRANCH% --oneline 2>nul
echo.

:: Check if updates available
git status -uno | findstr /C:"behind" >nul
if %errorlevel% equ 0 (
    echo [!] Co ban cap nhat moi!
    echo.

    :: Confirm update
    set /p confirm="Ban co muon cap nhat? (Y/N): "
    if /i "!confirm!"=="Y" (
        echo.
        echo [*] Dang cap nhat...

        :: Pull latest
        git pull origin %BRANCH%

        if %errorlevel% equ 0 (
            echo.
            echo ============================================
            echo   [OK] CAP NHAT THANH CONG!
            echo ============================================
            echo.
            echo [INFO] Phien ban moi:
            git log -1 --format="  Commit: %%h - %%s (%%cr)"
            echo.
            git stash pop >nul 2>&1
        ) else (
            echo.
            echo [ERROR] Cap nhat that bai!
            git stash pop >nul 2>&1
        )
    ) else (
        echo [INFO] Huy cap nhat.
        git stash pop >nul 2>&1
    )
) else (
    :: Force pull anyway
    echo [*] Dang dong bo voi origin/%BRANCH%...
    git pull origin %BRANCH%

    echo.
    echo ============================================
    echo   [OK] DA DONG BO THANH CONG!
    echo ============================================
    echo.
    git log -1 --format="  Commit: %%h - %%s (%%cr)"
    git stash pop >nul 2>&1
)

echo.
pause
