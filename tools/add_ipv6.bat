@echo off
:: Add IPv6 Address to Windows Interface
:: RUN AS ADMINISTRATOR!

echo ============================================
echo IPv6 Setup Script
echo ============================================
echo.

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run as Administrator!
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

:: Variables - EDIT THESE TO MATCH YOUR SETUP
set IPV6_ADDR=2001:ee0:b004:1f00::2
set IPV6_GATEWAY=2001:ee0:b004:1f00::1
set INTERFACE=Ethernet

echo Using:
echo   IP:      %IPV6_ADDR%
echo   Gateway: %IPV6_GATEWAY%
echo   Interface: %INTERFACE%
echo.

:: Delete old routes first (ignore errors)
echo Cleaning old routes...
netsh interface ipv6 delete route ::/0 "%INTERFACE%" >nul 2>&1

:: Add IPv6 address
echo Adding IPv6 address...
netsh interface ipv6 add address "%INTERFACE%" %IPV6_ADDR%

:: Add gateway route (SAME SUBNET as IP!)
echo Adding gateway route...
netsh interface ipv6 add route ::/0 "%INTERFACE%" %IPV6_GATEWAY%

echo.
echo Verifying address...
netsh interface ipv6 show addresses "%INTERFACE%" | findstr "2001:"

echo.
echo Verifying route...
netsh interface ipv6 show route | findstr "::/0"

echo.
echo Testing connectivity to Google DNS (2001:4860:4860::8888)...
ping -n 2 2001:4860:4860::8888

echo.
echo ============================================
echo If ping shows "Reply from", IPv6 is working!
echo ============================================
pause
