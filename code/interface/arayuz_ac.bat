@echo off
cd /d %~dp0

echo Gerekli paketler yukleniyor...
npm install && (
  echo Sunucu baslatiliyor...
  node server_deneme.js
)

pause
