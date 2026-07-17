@echo off
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo Git is not installed. Download it from https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist ".git" (
    echo This folder is not connected to GitHub yet.
    echo Run setup_git.bat first ^(one time only^).
    pause
    exit /b 1
)

echo ============================================
echo  Deploying to GitHub - Railway...
echo ============================================

git add -A

set deploymsg=%*
if "%deploymsg%"=="" set deploymsg=update %date% %time%

git commit -m "%deploymsg%"
git push origin main

if errorlevel 1 (
    echo.
    echo !!! PUSH FAILED - check internet / GitHub sign-in and try again.
) else (
    echo.
    echo OK - pushed. Railway will redeploy automatically in about a minute.
)
pause
