# 내 사진 뷰어

알씨 스타일의 광고 없는 사진 뷰어 + AI 도구 (PySide6).

- AI 화질 개선 / 배경 제거 / 텍스트 추출(Windows OCR) / 얼굴 모자이크 / 지우개
- 화살표·←/→ 로 이전/다음, 우클릭 메뉴(전체화면 X, 연속보기 S, 부드럽게 M, 배치 D, 인쇄 Ctrl+P, 파일속성)

## 실행
```
pip install PySide6 numpy opencv-python pillow rembg onnxruntime winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
python app.py [사진경로]
```
배경 제거 모델(u2net.onnx, 176MB)은 처음 사용할 때 `models/`에 자동으로 내려받습니다.

## exe / 설치 파일 만들기
```
python -m PyInstaller --noconfirm --windowed --icon app.ico --name 내사진뷰어 --add-data "models;models" --collect-all winrt --collect-submodules rembg --copy-metadata pymatting --copy-metadata rembg --copy-metadata onnxruntime --copy-metadata numpy --copy-metadata pillow --hidden-import onnxruntime --exclude-module torch --exclude-module torchvision --exclude-module PyQt6 --exclude-module matplotlib --exclude-module tkinter app.py
ISCC.exe installer.iss
```
