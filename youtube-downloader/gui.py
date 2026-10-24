"""유튜브 다운로더 - 창 화면 버전 (주소 붙여넣고 버튼만 누르면 됩니다)."""
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from yt_dlp import YoutubeDL

SAVE_DIR = Path.home() / "Downloads" / "유튜브"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("유튜브 다운로더")
        self.geometry("560x260")
        self.resizable(False, False)

        tk.Label(self, text="유튜브 주소를 붙여넣으세요", font=("맑은 고딕", 11)).pack(pady=(18, 6))

        self.url = tk.StringVar()
        entry = tk.Entry(self, textvariable=self.url, width=60, font=("맑은 고딕", 10))
        entry.pack(padx=20)
        entry.focus()

        self.only_audio = tk.BooleanVar()
        tk.Checkbutton(self, text="소리만 mp3로 받기", variable=self.only_audio).pack(pady=8)

        self.button = tk.Button(self, text="다운로드", width=16, height=2, command=self.start)
        self.button.pack()

        self.bar = ttk.Progressbar(self, length=500, maximum=100)
        self.bar.pack(pady=(14, 4))
        self.status = tk.Label(self, text="대기 중", fg="gray")
        self.status.pack()

    def set_status(self, text):
        self.after(0, lambda: self.status.config(text=text))

    def on_progress(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                percent = d["downloaded_bytes"] * 100 / total
                self.after(0, lambda: self.bar.config(value=percent))
                self.set_status(f"받는 중... {percent:.0f}%")
        elif d["status"] == "finished":
            self.set_status("마무리 중... (영상과 소리 합치는 중)")

    def start(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning("알림", "유튜브 주소를 먼저 붙여넣어 주세요.")
            return
        self.button.config(state="disabled")
        self.bar.config(value=0)
        threading.Thread(target=self.run, args=(url,), daemon=True).start()

    def run(self, url):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        options = {
            "outtmpl": str(SAVE_DIR / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "progress_hooks": [self.on_progress],
            "quiet": True,
        }
        if self.only_audio.get():
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        else:
            options["format"] = "bestvideo+bestaudio/best"
            options["merge_output_format"] = "mp4"
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([url])
            self.after(0, lambda: self.bar.config(value=100))
            self.set_status("완료!")
            self.after(0, lambda: messagebox.showinfo("완료", f"저장했어요.\n\n{SAVE_DIR}"))
        except Exception as e:
            self.set_status("실패했어요")
            self.after(0, lambda: messagebox.showerror("실패", f"받기에 실패했어요.\n\n{e}"))
        finally:
            self.after(0, lambda: self.button.config(state="normal"))


if __name__ == "__main__":
    App().mainloop()
