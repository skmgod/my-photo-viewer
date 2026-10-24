# 유튜브 다운로더 (간단 버전)

## 처음 한 번만 준비
1. 파이썬 설치 (https://www.python.org)
2. 명령 창(cmd)에서: `pip install -U yt-dlp`
3. 영상과 소리를 합치려면 ffmpeg가 필요해요 (https://ffmpeg.org 에서 받아 설치)
   - 윈도우: 명령 창에 `winget install ffmpeg`

## 가장 쉬운 사용법
1. `설치.bat` 더블클릭 (처음 한 번만)
2. `실행.bat` 더블클릭 → 창이 뜨면 주소 붙여넣고 [다운로드] 클릭

## 명령 창으로 쓰기
- `python download.py` 실행 후 주소 붙여넣기
- 소리만 받기: `python download.py 주소 --mp3`
- 저장 위치: 내 컴퓨터의 `다운로드\유튜브` 폴더

## 주의
본인이 올린 영상이나 받아도 되는 영상에만 사용하세요.
다른 사람의 영상은 저작권 문제가 있을 수 있어요.

## EXE 파일 만들기
- 내 컴퓨터에서: `EXE만들기.bat` 더블클릭 → `dist` 폴더에 `유튜브다운로더.exe` 생성
- GitHub에서: 저장소의 Actions 탭 → "유튜브 다운로더 EXE 만들기" → Run workflow → 끝나면 Artifacts에서 내려받기
- EXE로 만들어도 영상 합치기용 ffmpeg는 컴퓨터에 따로 설치되어 있어야 해요.
