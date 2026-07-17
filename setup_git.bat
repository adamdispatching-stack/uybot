@echo off
cd /d "%~dp0"
set REPO=https://github.com/adamdispatching-stack/uybot.git

where git >nul 2>&1
if errorlevel 1 (
    echo Git is not installed. Download it from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo ============================================
echo  FIRST-TIME SETUP - run this only once
echo  Repo: %REPO%
echo ============================================
echo.

git init
git branch -M main
git add -A
git commit -m "first deploy"
git remote remove origin >nul 2>&1
git remote add origin %REPO%
git push -u origin main

if errorlevel 1 (
    echo.
    echo !!! PUSH FAILED - if a GitHub sign-in window appeared, sign in
    echo !!! and run this file again. Also check your internet connection.
) else (
    echo.
    echo ============================================
    echo  Done! From now on just double-click deploy.bat
    echo ============================================
)
pause
