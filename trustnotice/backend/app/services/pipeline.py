"""Glue: watermark+rasterise on issue, and image evidence on verify."""
import hmac, hashlib, io
import numpy as np, cv2
from app.watermarking.dwt_dct import embed, extract
from app.image_processing.forensics import align, compare

def wm_ref(key: bytes, notice_id: str, version: int) -> bytes:
    """Keyed 8-byte reference; bound to the signed manifest through notice_id+version."""
    return hmac.new(key, f"{notice_id}|{version}".encode(), hashlib.sha256).digest()[:8]

def _dec(b): return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
def _png(a): return cv2.imencode(".png", a)[1].tobytes()

def stamp_qr(img, qr_png):
    if not qr_png: return img
    q = _dec(qr_png); side = max(120, img.shape[1] // 7); q = cv2.resize(q, (side, side), interpolation=cv2.INTER_NEAREST)
    img = img.copy(); h, w = img.shape[:2]; m = side // 8
    img[h - side - m:h - m, w - side - m:w - m] = q; return img

def embed_for_file(data: bytes, filename: str, ref: bytes, version: int, key: bytes, qr_png: bytes = None):
    """Images -> watermarked PNG. PDFs -> each page rasterised, watermarked, rebuilt as a PDF
    (the untouched original is stored separately). Returns (bytes, ext)."""
    if data.startswith(b"%PDF-"):
        import pymupdf as fitz
        out = fitz.open()
        with fitz.open(stream=data, filetype="pdf") as src:
            for pg in src:
                pix = pg.get_pixmap(dpi=150)
                img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1]
                wm = embed(stamp_qr(np.ascontiguousarray(img), qr_png) if pg.number == 0 else np.ascontiguousarray(img), ref, version, key)
                p = out.new_page(width=pg.rect.width, height=pg.rect.height)
                p.insert_image(p.rect, stream=_png(wm))
        return out.tobytes(), "pdf"
    img = _dec(data)
    if img is None: raise ValueError("Unreadable image")
    return _png(embed(stamp_qr(img, qr_png), ref, version, key)), "png"

def first_page_image(data: bytes, is_pdf: bool):
    if not is_pdf: return _dec(data)
    import pymupdf as fitz
    with fitz.open(stream=data, filetype="pdf") as d:
        pix = d[0].get_pixmap(dpi=150)
        return np.ascontiguousarray(np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1])

def image_evidence(upload: np.ndarray, original: np.ndarray, key: bytes, expected_ref: bytes) -> dict:
    """Align to the registered original, try watermark recovery, score similarity, box differences."""
    al, inliers = align(original, upload)
    if al is None: return dict(aligned=False, watermark_ok=False, similarity=None, boxes=[], overlay=None)
    got = extract(al, key); sim, boxes, ov = compare(original, al)
    return dict(aligned=True, inliers=inliers, watermark_ok=bool(got and got[0] == expected_ref),
                similarity=sim, boxes=[tuple(map(int, b)) for b in boxes], overlay=ov)
