@echo off
chcp 65001 >nul
pip install -U yt-dlp pyinstaller
pyinstaller --onefile --noconsole --name "유튜브다운로더" "%~dp0gui.py"
echo.
echo 완료! dist 폴더 안의 유튜브다운로더.exe 를 쓰세요.
pause
