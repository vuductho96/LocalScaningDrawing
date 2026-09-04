@echo off
chcp 65001 >nul
title AutoScanText - OCR Ban Ve Ky Thuat & Dung Sai
echo ======================================================================
echo          AUTOSCANTEXT - HE THONG OCR BAN VE KY THUAT
echo ======================================================================
echo  [+] Dang khoi dong Web Server tai: http://localhost:8000
echo  [+] Trinh duyet se tu dong mo len trong giay lat...
echo  [+] De dung server: Nhan Ctrl + C
echo ======================================================================

cd /d "%~dp0"
start "" http://localhost:8000
python app.py
pause
