"""Keyed invisible watermark: Haar DWT (LL band) -> 8x8 DCT -> QIM on a mid-frequency coefficient.
Bits are spread over many keyed-shuffled blocks (spread-spectrum style redundancy) and protected by
Reed-Solomon. The payload is a lookup reference only; authenticity comes from the Ed25519 signature.
Documents are normalised to a canonical width so resizing/screenshots can be re-normalised on extraction."""
import hashlib
import numpy as np, cv2
try:
    from reedsolo import RSCodec, ReedSolomonError
    _RS = RSCodec(10)
except ImportError:  # sandbox fallback only; real deployments install reedsolo
    class ReedSolomonError(Exception): ...
    class _Id:
        def encode(self, b): return bytes(b) + bytes(10)
        def decode(self, b): return (bytes(b[:-10]),)
    _RS = _Id()

CANON_W, DELTA, COEF = 1024, 56.0, (1, 2)

def auth_ref(manifest_bytes: bytes, signature_b64: str) -> bytes:
    """8-byte reference bound to the signed manifest + signature (for registry lookup)."""
    return hashlib.sha256(manifest_bytes + signature_b64.encode()).digest()[:8]

def _payload_bits(ref: bytes, version: int) -> np.ndarray:
    return np.unpackbits(np.frombuffer(bytes(_RS.encode(ref + bytes([version & 255]))), np.uint8))

def _norm(img):
    h, w = img.shape[:2]
    return cv2.resize(img, (CANON_W, max(16, round(h * CANON_W / w))), interpolation=cv2.INTER_AREA)

def _blocks(ll, key: bytes):
    by, bx = ll.shape[0] // 8, ll.shape[1] // 8
    order = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], "big")).permutation(by * bx)
    return by, bx, order

def embed(img_bgr: np.ndarray, ref: bytes, version: int, key: bytes) -> np.ndarray:
    img = _norm(img_bgr); h, w = img.shape[:2]; h2, w2 = h // 2 * 2, w // 2 * 2
    yuv = cv2.cvtColor(img[:h2, :w2], cv2.COLOR_BGR2YCrCb).astype(np.float32)
    Y = 8 + yuv[..., 0] * (239 / 255)                      # headroom so clipping can't erase the mark
    ll = (Y[0::2, 0::2] + Y[0::2, 1::2] + Y[1::2, 0::2] + Y[1::2, 1::2]) / 2
    bits = _payload_bits(ref, version); by, bx, order = _blocks(ll, key); new = ll.copy()
    for rank, blk in enumerate(order):
        b = bits[rank % len(bits)]; r, c = divmod(int(blk), bx)
        d = cv2.dct(ll[r*8:r*8+8, c*8:c*8+8].copy()); v = d[COEF]
        d[COEF] = np.round((v - b * DELTA / 2) / DELTA) * DELTA + b * DELTA / 2
        new[r*8:r*8+8, c*8:c*8+8] = cv2.idct(d)
    Y2 = Y + np.kron(new - ll, np.ones((2, 2), np.float32)) / 2   # exact Haar LL inverse of the change
    yuv[..., 0] = np.clip(Y2, 0, 255); return cv2.cvtColor(yuv.astype(np.uint8), cv2.COLOR_YCrCb2BGR)

def extract(img_bgr: np.ndarray, key: bytes):
    """Returns (ref_bytes, version) or None when the mark can't be recovered/validated."""
    img = _norm(img_bgr); h, w = img.shape[:2]; h2, w2 = h // 2 * 2, w // 2 * 2
    Y = cv2.cvtColor(img[:h2, :w2], cv2.COLOR_BGR2YCrCb)[..., 0].astype(np.float32)
    ll = (Y[0::2, 0::2] + Y[0::2, 1::2] + Y[1::2, 0::2] + Y[1::2, 1::2]) / 2
    n = 19 * 8; votes = np.zeros(n); by, bx, order = _blocks(ll, key)
    for rank, blk in enumerate(order):
        r, c = divmod(int(blk), bx); v = cv2.dct(ll[r*8:r*8+8, c*8:c*8+8].copy())[COEF]
        d0 = abs(v - np.round(v / DELTA) * DELTA); d1 = abs(v - (np.round((v - DELTA/2) / DELTA) * DELTA + DELTA/2))
        votes[rank % n] += d0 - d1
    try:
        data = _RS.decode(bytes(np.packbits((votes > 0).astype(np.uint8))))[0]
        return bytes(data[:8]), data[8]
    except (ReedSolomonError, IndexError, Exception): return None
