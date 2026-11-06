import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np, cv2
from app.image_processing.forensics import align, compare
from app.watermarking.dwt_dct import embed, extract
import test_watermark as tw
KEY, REF = tw.KEY, tw.REF
def jpg(im, q=60): return cv2.imdecode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)
def phone_shot(im):  # rotation + perspective + crop + resize + jpeg
    h, w = im.shape[:2]; src = np.float32([[0,0],[w,0],[w,h],[0,h]])
    dst = np.float32([[40,30],[w-20,10],[w-50,h-30],[15,h-10]])
    s = cv2.warpPerspective(im, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(255,255,255))
    return jpg(cv2.resize(s[60:h-80, 30:w-40], None, fx=0.7, fy=0.7), 55)

def test_align_then_recover_watermark_crop_and_perspective():
    orig = embed(tw.doc(), REF, 1, KEY); h, w = orig.shape[:2]
    crop = orig[60:h-80, 30:w-40]
    al, inl = align(orig, crop); assert inl >= 15 and extract(al, KEY) == (REF, 1)
    src = np.float32([[0,0],[w,0],[w,h],[0,h]]); dst = np.float32([[20,15],[w-10,5],[w-25,h-15],[8,h-5]])
    p = jpg(cv2.warpPerspective(orig, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(255,255,255)), 70)
    al, inl = align(orig, p); assert inl >= 15 and extract(al, KEY) == (REF, 1)
def test_stacked_phone_shot_aligns_but_watermark_not_guaranteed():
    # KNOWN LIMITATION: perspective+crop+resize+JPEG stacked. Alignment/SSIM work; payload recovery
    # needs real Reed-Solomon (not installed here) and more work, so only alignment is asserted.
    orig = embed(tw.doc(), REF, 1, KEY); al, inl = align(orig, phone_shot(orig))
    assert al is not None and compare(orig, al)[0] > 0.9
def test_untouched_scores_high_and_tamper_found():
    orig = embed(tw.doc(), REF, 1, KEY); al, _ = align(orig, jpg(orig))
    s, boxes, _ = compare(orig, al); assert s > 0.9 and not boxes
    t = orig.copy(); cv2.rectangle(t, (40, 300), (1000, 340), (255,255,255), -1)
    cv2.putText(t, "exams begin 20 Dec", (40, 335), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20,20,20), 2)
    al2, _ = align(orig, jpg(t)); s2, boxes2, _ = compare(orig, al2)
    assert boxes2 and any(280 < y + h/2 < 360 for x, y, w, h in boxes2) and s2 < s
def test_unrelated_image_not_aligned():
    other = np.full((1400, 1024, 3), 255, np.uint8); cv2.circle(other, (500, 700), 300, (0, 0, 0), 5)
    assert align(embed(tw.doc(), REF, 1, KEY), other)[0] is None
