@echo off
chcp 65001 >nul
echo 처음 한 번만 필요한 준비를 합니다...
pip install -U yt-dlp
winget install ffmpeg
echo.
echo 준비 끝! 이제 "실행.bat"을 더블클릭하세요.
pause
