import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np, cv2
from datetime import datetime, timezone, timedelta
from app.services.pipeline import *
from app.services.verification import *
from app.cryptography.signing import *
import test_watermark as tw
WK, NOW = b"wm-secret", datetime(2026, 11, 6, tzinfo=timezone.utc)

def issue():
    ref = wm_ref(WK, "N-1", 1); raw = cv2.imencode(".png", tw.doc())[1].tobytes()
    dist, _ = embed_for_file(raw, "n.png", ref, 1, WK)
    priv, pub = generate_keypair(); keys = KeyRegistry(); kid = keys.register(pub)
    m = build_manifest(notice_id="N-1", institution_id="I", document_hash=sha256_hex(dist), issued_at=NOW.isoformat(),
                       expires_at=(NOW + timedelta(days=9)).isoformat(), category="exam", version=1, key_id=kid)
    return dist, ref, keys, {"N-1": NoticeRecord(m, sign_manifest(m, priv), "")}
def jpg(a, q, f=1.0):
    a = cv2.resize(a, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f != 1 else a
    return cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()

def test_demo1_distributed_file_is_green():
    dist, ref, keys, reg = issue()
    assert verify_upload(dist, reg, keys, qr_notice_id="N-1", now=NOW).status == GREEN
def test_demo3_whatsapp_compression_yellow():
    dist, ref, keys, reg = issue(); orig = cv2.imdecode(np.frombuffer(dist, np.uint8), 1)
    up = cv2.imdecode(np.frombuffer(jpg(orig, 55, 0.75), np.uint8), 1)
    ev = image_evidence(up, orig, WK, ref); assert ev["watermark_ok"]
    r = verify_upload(b"x", reg, keys, qr_notice_id="N-1", watermark_notice_id="N-1" if ev["watermark_ok"] else None,
                      image_similarity=ev["similarity"], changed_regions=len(ev["boxes"]), now=NOW)
    assert r.status == YELLOW, (r.status, ev["boxes"])
def test_demo2_edited_image_is_red_with_region():
    dist, ref, keys, reg = issue(); orig = cv2.imdecode(np.frombuffer(dist, np.uint8), 1); t = orig.copy()
    cv2.rectangle(t, (40, 300), (1000, 340), (255,255,255), -1)
    cv2.putText(t, "exams begin 20 Dec", (40, 335), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20,20,20), 2)
    ev = image_evidence(cv2.imdecode(np.frombuffer(jpg(t, 80), np.uint8), 1), orig, WK, ref)
    assert ev["boxes"]
def test_copied_qr_on_fake_image_not_authenticated():
    dist, ref, keys, reg = issue(); orig = cv2.imdecode(np.frombuffer(dist, np.uint8), 1)
    fake = np.full(orig.shape, 255, np.uint8); cv2.putText(fake, "HOLIDAY TOMORROW", (60, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 4)
    ev = image_evidence(fake, orig, WK, ref); assert not ev["watermark_ok"]
    r = verify_upload(b"x", reg, keys, qr_notice_id="N-1", image_similarity=ev["similarity"], now=NOW)
    assert r.status in (BLACK, RED)

def test_edited_date_forces_red_even_with_watermark():
    dist, ref, keys, reg = issue(); orig = cv2.imdecode(np.frombuffer(dist, np.uint8), 1); t = orig.copy()
    cv2.rectangle(t, (40, 300), (1000, 340), (255,255,255), -1)
    cv2.putText(t, "exams begin 20 Dec", (40, 335), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20,20,20), 2)
    ev = image_evidence(cv2.imdecode(np.frombuffer(jpg(t, 80), np.uint8), 1), orig, WK, ref)
    r = verify_upload(b"x", reg, keys, qr_notice_id="N-1", watermark_notice_id="N-1", image_similarity=ev["similarity"], changed_regions=len(ev["boxes"]), now=NOW)
    assert r.status == RED
def test_stamp_qr_places_code_and_watermark_survives():
    enc = getattr(cv2, "QRCodeEncoder", None)
    if enc is None: return
    qr = enc.create().encode("https://x.test/verify/N-1?v=1"); qr = cv2.imencode(".png", cv2.resize(qr, (200, 200), interpolation=cv2.INTER_NEAREST))[1].tobytes()
    raw = cv2.imencode(".png", tw.doc())[1].tobytes(); ref = wm_ref(WK, "N-1", 1)
    d, _ = embed_for_file(raw, "n.png", ref, 1, WK, qr); img = cv2.imdecode(np.frombuffer(d, np.uint8), 1)
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(img); assert "/verify/N-1" in txt
    from app.watermarking.dwt_dct import extract; assert extract(img, WK) == (ref, 1)
