"""OpenCV forensics: normalisation, ORB feature alignment (handles rotation, perspective, crop,
screenshots), SSIM, and difference-map generation. Similarity here is evidence only, never proof."""
import numpy as np, cv2
W = 1024

def normalise(img):
    h, w = img.shape[:2]
    return cv2.resize(img, (W, max(16, round(h * W / w))), interpolation=cv2.INTER_AREA)

def preprocess(img):
    g = cv2.cvtColor(normalise(img), cv2.COLOR_BGR2GRAY)
    return cv2.fastNlMeansDenoising(g, None, 7, 7, 21)

def align(original, uploaded, min_inliers=15):
    """Warp `uploaded` into the original's frame. Returns (aligned_bgr, inliers) or (None, 0)."""
    o, u = normalise(original), normalise(uploaded)
    go, gu = cv2.cvtColor(o, cv2.COLOR_BGR2GRAY), cv2.cvtColor(u, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(5000); ko, do = orb.detectAndCompute(go, None); ku, du = orb.detectAndCompute(gu, None)
    if do is None or du is None or len(ko) < 8 or len(ku) < 8: return None, 0
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(du, do, k=2)
    good = [m for p in pairs if len(p) == 2 for m, n in [p] if m.distance < 0.75 * n.distance]
    if len(good) < min_inliers: return None, 0
    src = np.float32([ku[m.queryIdx].pt for m in good]); dst = np.float32([ko[m.trainIdx].pt for m in good])
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    inl = int(mask.sum()) if mask is not None else 0
    if H is None or inl < min_inliers: return None, inl
    size = (o.shape[1], o.shape[0]); warped = cv2.warpPerspective(u, H, size, borderValue=(255, 255, 255))
    try:  # sub-pixel ECC refinement keeps the watermark's 8x8 block grid registered
        Hr = np.eye(3, dtype=np.float32); gw = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        _, Hr = cv2.findTransformECC(go, gw, Hr, cv2.MOTION_HOMOGRAPHY,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6), None, 5)
        warped = cv2.warpPerspective(warped, Hr, size, flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                                     borderValue=(255, 255, 255))
    except cv2.error: pass
    return warped, inl

def ssim_map(a, b):
    a, b = a.astype(np.float64), b.astype(np.float64); C1, C2 = (0.01*255)**2, (0.03*255)**2
    g = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    ma, mb = g(a), g(b); va, vb, cov = g(a*a) - ma*ma, g(b*b) - mb*mb, g(a*b) - ma*mb
    return ((2*ma*mb + C1) * (2*cov + C2)) / ((ma*ma + mb*mb + C1) * (va + vb + C2))

def compare(original, aligned, min_area=150):
    """Returns (mean_ssim, boxes[(x,y,w,h)], diff_overlay_bgr)."""
    o = normalise(original); a = cv2.resize(aligned, (o.shape[1], o.shape[0]))
    go, ga = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in (o, a))
    go, ga = cv2.GaussianBlur(go, (3, 3), 0), cv2.GaussianBlur(ga, (3, 3), 0)
    m = ssim_map(go, ga); bad = ((1 - m) > 0.6).astype(np.uint8) * 255
    bad = cv2.dilate(bad, np.ones((9, 25), np.uint8))
    cs, _ = cv2.findContours(bad, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cs if cv2.contourArea(c) >= min_area]
    ov = a.copy()
    for x, y, w, h in boxes: cv2.rectangle(ov, (x, y), (x + w, y + h), (0, 0, 255), 3)
    return float(m.mean()), boxes, ov
