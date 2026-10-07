"""AI 도구 모음 - 모두 numpy BGRA(uint8) 배열을 받아서 처리한다.

화질 개선 : Sub-pixel CNN 초해상도 (onnxruntime, models/ 폴더의 모델 사용)
배경 제거 : rembg (U2Net, models/u2net.onnx 사용)
텍스트 추출: Windows 내장 OCR (winrt)
얼굴 모자이크: OpenCV YuNet 얼굴 검출 
지우개    : OpenCV inpaint
"""
import asyncio
import os

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.environ.setdefault("U2NET_HOME", MODEL_DIR)  # (파일명: models/u2net.onnx)  # rembg 모델을 models/ 폴더에서 찾음

MAX_ENHANCE_PIXELS = 12_000_000  # 이보다 큰 사진은 2배 확대 대신 선명화만 수행


def _split(bgra):
    return np.ascontiguousarray(bgra[:, :, :3]), bgra[:, :, 3]


def _merge(bgr, alpha):
    return np.dstack([bgr, alpha])


def _sharpen(bgr, amount=0.5, sigma=1.2):
    blur = cv2.GaussianBlur(bgr, (0, 0), sigma)
    return cv2.addWeighted(bgr, 1 + amount, blur, -amount, 0)


# ---------------------------------------------------------------- 화질 개선
def enhance(bgra, progress=None):
    bgr, alpha = _split(bgra)
    h, w = bgr.shape[:2]
    model = os.path.join(MODEL_DIR, "super-resolution-10.onnx")

    if h * w > MAX_ENHANCE_PIXELS or not os.path.exists(model):
        out = _sharpen(cv2.bilateralFilter(bgr, 5, 20, 5), 0.8)
        if progress:
            progress(100)
        return _merge(out, alpha)

    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])

    def upsample(img):
        # 224x224 고정 입력, 3배 확대. 밝기(Y)만 신경망으로 확대하고 색차는 bicubic.
        ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        y = sess.run(None, {"input": ycc[None, None, :, :, 0].astype(np.float32) / 255})[0][0, 0]
        cc = cv2.resize(ycc[:, :, 1:], (672, 672), interpolation=cv2.INTER_CUBIC)
        up = np.dstack([np.clip(y * 255, 0, 255).astype(np.uint8), cc])
        return cv2.cvtColor(up, cv2.COLOR_YCrCb2BGR)

    T, pad, S = 224, 8, 3
    core = T - 2 * pad
    big = np.zeros((h * S, w * S, 3), np.uint8)
    coords = [(y, x) for y in range(0, h, core) for x in range(0, w, core)]
    for i, (y, x) in enumerate(coords):
        ch, cw = min(core, h - y), min(core, w - x)
        win = cv2.copyMakeBorder(
            bgr[max(0, y - pad):y + ch + pad, max(0, x - pad):x + cw + pad],
            0, 0, 0, 0, cv2.BORDER_REFLECT)
        ty0, tx0 = y - max(0, y - pad), x - max(0, x - pad)  # 창 안에서 코어의 시작 위치
        canvas = np.zeros((T, T, 3), np.uint8)
        canvas[:win.shape[0], :win.shape[1]] = win
        up = upsample(canvas)
        big[y * S:(y + ch) * S, x * S:(x + cw) * S] =             up[ty0 * S:(ty0 + ch) * S, tx0 * S:(tx0 + cw) * S]
        if progress:
            progress(int((i + 1) / len(coords) * 100))

    out = cv2.resize(big, (w * 2, h * 2), interpolation=cv2.INTER_AREA)  # 3배 -> 2배
    out = _sharpen(out, 0.3)
    alpha2 = cv2.resize(alpha, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    return _merge(out, alpha2)


# ---------------------------------------------------------------- 배경 제거
_bg_session = None


def remove_background(bgra, progress=None):
    global _bg_session
    from PIL import Image
    from rembg import new_session, remove

    if _bg_session is None:
        _bg_session = new_session("u2net")  # 최초 1회 모델 다운로드(~170MB)
    bgr, alpha = _split(bgra)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    res = remove(Image.fromarray(rgb), session=_bg_session)
    rgba = np.array(res.convert("RGBA"))
    out = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    out[:, :, 3] = cv2.min(out[:, :, 3], alpha)
    return out


# ---------------------------------------------------------------- 텍스트 추출
async def _ocr_async(png_bytes):
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    engines = []
    ko = Language("ko")
    if OcrEngine.is_language_supported(ko):
        engines.append(OcrEngine.try_create_from_language(ko))
    prof = OcrEngine.try_create_from_user_profile_languages()
    if prof is not None:
        engines.append(prof)
    for lang in OcrEngine.available_recognizer_languages:
        if lang.language_tag.lower().startswith("en"):
            engines.append(OcrEngine.try_create_from_language(lang))
            break
    engines = [e for e in engines if e is not None]
    if not engines:
        raise RuntimeError(
            "Windows OCR 언어팩이 없습니다.\n설정 > 시간 및 언어 > 언어 및 지역에서 '한국어'를 추가해 주세요."
        )

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png_bytes)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    for eng in engines:
        result = await eng.recognize_async(bitmap)
        text = "\n".join(line.text for line in result.lines).strip()
        if text:
            return text
    return ""


def extract_text(bgra, progress=None):
    bgr, _ = _split(bgra)
    h, w = bgr.shape[:2]
    limit = 2600  # OcrEngine.MaxImageDimension
    if max(h, w) > limit:
        s = limit / max(h, w)
        bgr = cv2.resize(bgr, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", bgr)
    return asyncio.run(_ocr_async(buf.tobytes()))


# ---------------------------------------------------------------- 얼굴 모자이크
def _detect_faces(bgr):
    h, w = bgr.shape[:2]
    scale = min(1.0, 1600 / max(h, w))
    small = cv2.resize(bgr, (int(w * scale), int(h * scale))) if scale < 1 else bgr
    sh, sw = small.shape[:2]
    boxes = []
    model = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
    try:
        with open(model, "rb") as f:
            buf = np.frombuffer(f.read(), np.uint8)
        det = cv2.FaceDetectorYN.create("onnx", buf, np.empty(0, np.uint8), (sw, sh), 0.6, 0.3, 5000)
        _, faces = det.detect(small)
        if faces is not None:
            boxes = [f[:4] / scale for f in faces]
    except Exception:
        boxes = []
    return boxes


def mosaic_faces(bgra, progress=None):
    bgr, alpha = _split(bgra)
    h, w = bgr.shape[:2]
    boxes = _detect_faces(bgr)
    out = bgr.copy()
    for x, y, bw, bh in boxes:
        m = 0.15
        x0, y0 = int(max(0, x - bw * m)), int(max(0, y - bh * m))
        x1, y1 = int(min(w, x + bw * (1 + m))), int(min(h, y + bh * (1 + m)))
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        roi = out[y0:y1, x0:x1]
        block = max(6, max(x1 - x0, y1 - y0) // 8)
        sm = cv2.resize(roi, (max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)),
                        interpolation=cv2.INTER_LINEAR)
        out[y0:y1, x0:x1] = cv2.resize(sm, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    return _merge(out, alpha), len(boxes)


# ---------------------------------------------------------------- 지우개
def inpaint(bgra, mask, progress=None):
    """mask: uint8 (0/255), 지울 영역."""
    bgr, alpha = _split(bgra)
    h, w = bgr.shape[:2]
    mask = cv2.dilate((mask > 127).astype(np.uint8) * 255, np.ones((5, 5), np.uint8))
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return bgra
    margin = 40
    x0, x1 = max(0, xs.min() - margin), min(w, xs.max() + margin + 1)
    y0, y1 = max(0, ys.min() - margin), min(h, ys.max() + margin + 1)
    out = bgr.copy()
    out[y0:y1, x0:x1] = cv2.inpaint(
        np.ascontiguousarray(bgr[y0:y1, x0:x1]),
        np.ascontiguousarray(mask[y0:y1, x0:x1]), 5, cv2.INPAINT_TELEA)
    return _merge(out, alpha)


