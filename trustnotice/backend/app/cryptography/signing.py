"""Ed25519 signing of canonical notice manifests + key registry with rotation/revocation."""
import base64, hashlib, json
from dataclasses import dataclass, field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_json(obj: dict) -> bytes:
    """Deterministic serialization: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def generate_keypair() -> tuple[str, str]:
    """Returns (private_b64, public_b64), raw 32-byte keys, base64."""
    sk = Ed25519PrivateKey.generate()
    raw = lambda k, enc, fmt, **kw: base64.b64encode(k.public_bytes(enc, fmt) if hasattr(k, "public_bytes") else k).decode()
    priv = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(priv).decode(), base64.b64encode(pub).decode()

def public_key_for(private_b64: str) -> str:
    """Derive the raw Ed25519 public key for a base64-encoded raw private key."""
    raw_private = base64.b64decode(private_b64, validate=True)
    private_key = Ed25519PrivateKey.from_private_bytes(raw_private)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.b64encode(public_key).decode()

def key_id_for(public_b64: str) -> str:
    return "key-" + sha256_hex(base64.b64decode(public_b64))[:16]

def build_manifest(*, notice_id, institution_id, document_hash, issued_at, expires_at,
                   category, version, key_id) -> dict:
    return {"notice_id": notice_id, "institution_id": institution_id,
            "document_hash": document_hash, "issued_at": issued_at, "expires_at": expires_at,
            "category": category, "version": version, "key_id": key_id}

def sign_manifest(manifest: dict, private_b64: str) -> str:
    sk = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_b64))
    return base64.b64encode(sk.sign(canonical_json(manifest))).decode()

def verify_manifest(manifest: dict, signature_b64: str, public_b64: str) -> bool:
    try:
        pk = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        pk.verify(base64.b64decode(signature_b64), canonical_json(manifest))
        return True
    except (InvalidSignature, ValueError):
        return False

@dataclass
class KeyRegistry:
    """Public keys by key_id. Rotation = register a new key; old ones stay verifiable
    unless revoked. Private keys never live here."""
    _keys: dict = field(default_factory=dict)
    _revoked: set = field(default_factory=set)

    def register(self, public_b64: str) -> str:
        kid = key_id_for(public_b64); self._keys[kid] = public_b64; return kid
    def revoke(self, key_id: str) -> None:
        self._revoked.add(key_id)
    def get(self, key_id: str):
        return self._keys.get(key_id)
    def is_revoked(self, key_id: str) -> bool:
        return key_id in self._revoked
