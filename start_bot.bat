@echo off
echo.
echo ===================================
echo  STARTING GOLD BOT TRADING SYSTEM
echo ===================================
echo.

echo [1/3] Starting MetaTrader 5 Terminal...
start "" "C:\Program Files\MetaTrader 5\terminal64.exe"

echo.
echo [2/3] Waiting 45 seconds for MT5 to initialize and connect...
timeout /t 45 /nobreak

echo.
echo [3/3] Starting the GoldBot script via PM2...
cd C:\Users\Administrator\Documents\GitHub\goldiebot-backend
pm2 start ecosystem.config.js

echo.
echo ===================================
echo      STARTUP SEQUENCE COMPLETE
echo ===================================