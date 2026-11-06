"""Verification engine. Authenticity comes ONLY from a valid Ed25519 signature over the
manifest plus a content check. QR/watermark only *locate* the registered notice."""
import difflib, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.cryptography.signing import KeyRegistry, sha256_hex, verify_manifest

GREEN, YELLOW, RED, BLACK = "GREEN", "YELLOW", "RED", "BLACK"
TEXT_MATCH = 0.97     # normalized text similarity treated as unchanged
IMAGE_MATCH = 0.90    # structural similarity treated as same visual content

@dataclass
class NoticeRecord:
    manifest: dict
    signature: str
    original_text: str = ""
    status: str = "active"          # active | revoked

@dataclass
class Report:
    status: str
    validity: str = "VALID"         # VALID | REVOKED | EXPIRED | UNKNOWN
    notice_id: str | None = None
    signature_valid: bool = False
    watermark_detected: bool = False
    exact_hash_match: bool = False
    content_similarity: float | None = None
    changes: list = field(default_factory=list)
    reasons: list = field(default_factory=list)

def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()

def _token_changes(orig: str, new: str) -> list:
    a, b = _norm(orig).split(), _norm(new).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op != "equal":
            out.append({"original": " ".join(a[i1:i2]), "uploaded": " ".join(b[j1:j2])})
    return out

def verify_upload(file_bytes: bytes, registry: dict, keys: KeyRegistry, *, qr_notice_id=None,
                  watermark_notice_id=None, extracted_text=None, image_similarity=None, changed_regions=0,
                  now: datetime | None = None) -> Report:
    now = now or datetime.now(timezone.utc)
    rep = Report(status=BLACK)
    rep.watermark_detected = watermark_notice_id is not None

    ids = {i for i in (qr_notice_id, watermark_notice_id) if i}
    if len(ids) > 1:
        rep.reasons.append("QR and watermark point to different notices; evidence conflicts.")
        return rep
    if not ids:
        rep.validity = "UNKNOWN"
        rep.reasons.append("No QR or watermark linked this file to a registered notice. "
                           "This does not by itself prove it is fake.")
        return rep
    nid = ids.pop(); rep.notice_id = nid
    rec = registry.get(nid)
    if rec is None:
        rep.validity = "UNKNOWN"; rep.reasons.append("Notice ID is not in the registry."); return rep

    # 1. Signature + key checks (mandatory)
    kid = rec.manifest.get("key_id"); pub = keys.get(kid)
    if pub is None or keys.is_revoked(kid):
        rep.reasons.append("Signing key unknown or revoked."); return rep
    rep.signature_valid = verify_manifest(rec.manifest, rec.signature, pub)
    if not rep.signature_valid:
        rep.reasons.append("Registry record failed signature verification."); return rep

    # 2. Validity state
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    expires_at = rec.manifest.get("expires_at")
    exp = datetime.fromisoformat(expires_at) if expires_at else None
    exp = exp.replace(tzinfo=timezone.utc) if exp and exp.tzinfo is None else exp.astimezone(timezone.utc) if exp else None
    rep.validity = "REVOKED" if rec.status == "revoked" else "EXPIRED" if exp and now > exp else "VALID"

    # 3. Content integrity
    if sha256_hex(file_bytes) == rec.manifest["document_hash"]:
        rep.exact_hash_match = True; rep.status = GREEN; rep.content_similarity = 1.0
        rep.reasons.append("File is byte-identical to the signed original."); return rep

    if extracted_text is not None and rec.original_text:
        sim = difflib.SequenceMatcher(None, _norm(rec.original_text), _norm(extracted_text)).ratio()
        rep.content_similarity = round(sim, 4)
        changes = _token_changes(rec.original_text, extracted_text)
        critical = any(re.search(r"\d", c["original"] + c["uploaded"]) for c in changes)
        if sim >= TEXT_MATCH and not critical:
            rep.status = YELLOW
            rep.reasons.append("Text matches the original but the file was re-encoded; "
                               "hash cannot be confirmed.")
        else:
            rep.status = RED; rep.changes = changes
            rep.reasons.append("Content does not match the registered notice "
                               "(modified, or a genuine QR reused on another document).")
        return rep

    if image_similarity is not None:
        rep.content_similarity = round(image_similarity, 4)
        if changed_regions:
            rep.status = RED; rep.reasons.append(f"{changed_regions} region(s) of the image differ from the registered notice.")
        elif image_similarity >= IMAGE_MATCH and rep.watermark_detected:
            rep.status = YELLOW
            rep.reasons.append("Watermark and visual similarity identify the source; "
                               "exact integrity not provable after transformation.")
        elif image_similarity < IMAGE_MATCH:
            rep.status = RED; rep.reasons.append("Visual content differs from the registered notice.")
        else:
            rep.reasons.append("QR alone with unconfirmed visual match is insufficient.")
        return rep

    rep.reasons.append("Source found but no content could be compared; cannot authenticate.")
    return rep
