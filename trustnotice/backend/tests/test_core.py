import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime, timezone, timedelta
import pytest
from app.cryptography.signing import *
from app.services.verification import *

TEXT = "Semester exams begin on 12 December 2026. Hall tickets issued from 1 December."
DOC = b"%PDF-original-bytes"
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)

@pytest.fixture
def env():
    priv, pub = generate_keypair(); keys = KeyRegistry(); kid = keys.register(pub)
    def issue(nid, text=TEXT, doc=DOC, exp=NOW + timedelta(days=30), status="active"):
        m = build_manifest(notice_id=nid, institution_id="INST1", document_hash=sha256_hex(doc),
            issued_at=NOW.isoformat(), expires_at=exp.isoformat(), category="exam", version=1, key_id=kid)
        return NoticeRecord(m, sign_manifest(m, priv), text, status)
    reg = {"N-EXAM": issue("N-EXAM")}
    return priv, keys, reg, issue

def test_canonical_json_order_independent():
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})

def test_sign_verify_and_tamper():
    priv, pub = generate_keypair(); m = {"notice_id": "X", "version": 1}
    assert public_key_for(priv) == pub
    sig = sign_manifest(m, priv)
    assert verify_manifest(m, sig, pub)
    assert not verify_manifest({**m, "version": 2}, sig, pub)
    assert not verify_manifest(m, sig, generate_keypair()[1])

def test_demo1_genuine_green(env):
    _, keys, reg, _ = env
    r = verify_upload(DOC, reg, keys, qr_notice_id="N-EXAM", now=NOW)
    assert r.status == GREEN and r.signature_valid and r.validity == "VALID"

def test_demo2_modified_date_red(env):
    _, keys, reg, _ = env
    fake = TEXT.replace("12 December", "20 December")
    r = verify_upload(b"edited", reg, keys, qr_notice_id="N-EXAM", extracted_text=fake, now=NOW)
    assert r.status == RED and r.changes

def test_demo3_recompressed_yellow(env):
    _, keys, reg, _ = env
    r = verify_upload(b"recompressed", reg, keys, watermark_notice_id="N-EXAM",
                      image_similarity=0.94, now=NOW)
    assert r.status == YELLOW

def test_demo4_copied_qr_red(env):
    _, keys, reg, _ = env
    r = verify_upload(b"fake", reg, keys, qr_notice_id="N-EXAM",
                      extracted_text="Holiday declared on 15 December for all departments.", now=NOW)
    assert r.status == RED

def test_qr_only_image_not_authenticated(env):
    _, keys, reg, _ = env
    r = verify_upload(b"img", reg, keys, qr_notice_id="N-EXAM", image_similarity=0.95, now=NOW)
    assert r.status == BLACK

def test_no_evidence_is_unverified_not_fake(env):
    _, keys, reg, _ = env
    r = verify_upload(b"x", reg, keys, now=NOW)
    assert r.status == BLACK and r.validity == "UNKNOWN"

def test_conflicting_qr_and_watermark(env):
    _, keys, reg, issue = env; reg["N-OTHER"] = issue("N-OTHER")
    r = verify_upload(b"x", reg, keys, qr_notice_id="N-EXAM", watermark_notice_id="N-OTHER", now=NOW)
    assert r.status == BLACK

def test_forged_registry_record_rejected(env):
    _, keys, reg, _ = env
    reg["N-EXAM"].manifest["document_hash"] = sha256_hex(b"forged")
    r = verify_upload(b"forged", reg, keys, qr_notice_id="N-EXAM", now=NOW)
    assert r.status == BLACK and not r.signature_valid

def test_revoked_key(env):
    _, keys, reg, _ = env; keys.revoke(reg["N-EXAM"].manifest["key_id"])
    assert verify_upload(DOC, reg, keys, qr_notice_id="N-EXAM", now=NOW).status == BLACK

def test_revoked_and_expired_states(env):
    _, keys, reg, issue = env
    reg["N-REV"] = issue("N-REV", status="revoked"); reg["N-OLD"] = issue("N-OLD", exp=NOW - timedelta(days=1))
    assert verify_upload(DOC, reg, keys, qr_notice_id="N-REV", now=NOW).validity == "REVOKED"
    assert verify_upload(DOC, reg, keys, qr_notice_id="N-OLD", now=NOW).validity == "EXPIRED"
