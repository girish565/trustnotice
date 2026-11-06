import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np, cv2
from app.watermarking.dwt_dct import embed, extract

def doc():
    im = np.full((1400, 1024, 3), 255, np.uint8)
    for i in range(18): cv2.putText(im, f"Notice line {i}: exams begin 12 Dec", (40, 80 + i*70), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2)
    return im
KEY, REF = b"k1", bytes(range(1, 9))

def test_roundtrip_and_invisible():
    o = doc(); w = embed(o, REF, 2, KEY)
    assert extract(w, KEY) == (REF, 2); base = np.clip(8 + o * (239/255), 0, 255).astype(int); assert np.abs(w.astype(int) - base).mean() < 2
def test_jpeg_q50():
    w = embed(doc(), REF, 1, KEY); j = cv2.imdecode(cv2.imencode(".jpg", w, [cv2.IMWRITE_JPEG_QUALITY, 50])[1], 1)
    assert extract(j, KEY) == (REF, 1)
def test_whatsapp_resize():
    w = embed(doc(), REF, 1, KEY); s = cv2.resize(w, None, fx=0.75, fy=0.75, interpolation=cv2.INTER_AREA)
    j = cv2.imdecode(cv2.imencode(".jpg", s, [cv2.IMWRITE_JPEG_QUALITY, 60])[1], 1)
    assert extract(j, KEY) == (REF, 1)
def test_wrong_key_fails():
    assert extract(embed(doc(), REF, 1, KEY), b"other") != (REF, 1)
