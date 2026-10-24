"""유튜브 영상을 가장 좋은 화질로 내려받는 간단한 프로그램.

사용법:
    python download.py                  (실행 후 주소를 붙여넣기)
    python download.py 주소             (주소를 바로 넣기)
    python download.py 주소 --mp3       (소리만 mp3로 받기)
"""
import sys
from pathlib import Path

from yt_dlp import YoutubeDL

SAVE_DIR = Path.home() / "Downloads" / "유튜브"


def download(url, only_audio=False):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(SAVE_DIR / "%(title)s.%(ext)s"),
        "noplaylist": True,
    }
    if only_audio:
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        # 영상 최고화질 + 소리 최고음질을 받아서 mp4 하나로 합침
        options["format"] = "bestvideo+bestaudio/best"
        options["merge_output_format"] = "mp4"

    with YoutubeDL(options) as ydl:
        ydl.download([url])
    print(f"\n완료! 저장 위치: {SAVE_DIR}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only_audio = "--mp3" in sys.argv
    url = args[0] if args else input("유튜브 주소를 붙여넣으세요: ").strip()
    if not url:
        print("주소가 비어 있어요.")
        return
    try:
        download(url, only_audio)
    except Exception as e:
        print(f"\n받기에 실패했어요: {e}")


if __name__ == "__main__":
    main()
