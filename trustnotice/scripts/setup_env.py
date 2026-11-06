"""One-time local setup: writes backend/.env with fresh Ed25519 keys, JWT secret and an admin login.
Usage (from project root):  python scripts/setup_env.py [--out backend/.env]"""
import argparse, secrets, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from app.cryptography.signing import generate_keypair

ap = argparse.ArgumentParser(); ap.add_argument("--out", default="backend/.env"); a = ap.parse_args()
out = pathlib.Path(a.out)
if out.exists(): sys.exit(f"{out} already exists; refusing to overwrite (it holds your signing keys).")
priv, pub = generate_keypair(); pw = secrets.token_urlsafe(12)
out.write_text(f"""DATABASE_URL=sqlite:///./trustnotice.db
JWT_SECRET={secrets.token_hex(32)}
ED25519_PRIVATE_KEY={priv}
ED25519_PUBLIC_KEY={pub}
STORAGE_PATH=./storage
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
ADMIN_EMAIL=admin@college.edu
ADMIN_PASSWORD={pw}
""")
print(f"Wrote {out}\nAdmin login: admin@college.edu / {pw}\n(Keep this file private; it is git-ignored.)")
