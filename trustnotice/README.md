# TRUSTNOTICE — AI-assisted notice authentication

*A watermark can be copied. A logo can be forged. A signature must be verified.*

Admins upload a notice; it is hashed (SHA-256), signed (Ed25519), stamped with a QR code and invisibly watermarked (DWT+DCT, keyed, Reed-Solomon). Students upload what they received and get **GREEN / YELLOW / RED / BLACK** plus revoked/expired state. Authenticity comes only from the signature plus a content check; QR and watermark merely *locate* the record.

## VS Code quickstart (no Docker, SQLite)
1. Open the `trustnotice` folder in VS Code. Needs Python 3.11+ and Node 18+.
2. Run task **Create backend environment**, then **Install backend** and **Install frontend** (Terminal > Run Task).
3. From the project root, run `backend\.venv\Scripts\python.exe scripts\setup_env.py` (creates `backend/.env` with keys and prints the admin login). Keep that password private.
4. Press **F5** (Backend FastAPI, API at http://localhost:8000/docs), then run task **Run frontend** (UI at http://localhost:5173).
5. Log in at /admin/login, issue a notice, then run `backend\.venv\Scripts\python.exe scripts\make_demos.py --email admin@college.edu --password <printed>` to produce the 5 demo files.
6. Tests: task **Run backend tests**.

## Run locally (Docker/Postgres)
```bash
# For a new Docker setup only; if backend/.env exists, merge these settings instead of overwriting it.
cp backend/.env.example backend/.env       # set unique JWT_SECRET, ADMIN_PASSWORD, and POSTGRES_PASSWORD
# Keep POSTGRES_PASSWORD and the password in DATABASE_URL in sync; use a URL-encoded password if needed.
# generate signing keys once and put them in .env:
python -c "from app.cryptography.signing import generate_keypair as g; print(g())"   # run inside backend/
docker compose up --build                   # API :8000 (docs at /docs), UI :5173
```
Without Docker on Windows PowerShell, from the project root:
```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# In a second terminal:
Set-Location frontend
npm install
npm run dev
```
The backend loads `backend/.env` automatically. Keep its Ed25519 keys stable; changing them retires the previous key and may affect verification of older notices.

## Tests
From the project root on Windows, run `backend\.venv\Scripts\python.exe -m pytest -q` — crypto, verification engine, watermark, forensics and API workflows.

## Demo (5 scenarios)
`python scripts/make_demos.py --email ... --password ...` issues a notice and writes files to `samples/`; upload each on the Verify page.

| File | Expected |
|---|---|
| 1_genuine.png | GREEN — authentic |
| 2_modified_date.png | RED — tampered, edited region boxed |
| 3_whatsapp_compressed.jpg | YELLOW — authentic, degraded (or GREEN-equivalent evidence) |
| 4_fake_with_copied_qr.png | RED/BLACK — copied QR does not authenticate |
| 5_screenshot_cropped.jpg | Source identified if evidence survives; otherwise honestly UNVERIFIED |

## Emergency alerts and student accounts
Student accounts are provisioned by an administrator; there is no public self-registration. In the admin dashboard, create each profile with a unique student ID, department, academic year, class/cohort, and a strong initial password, then deliver that password through a secure channel. Students sign in at `/student/login`; their inbox and dashboard only return their own recipient records.
Use **Emergency notice** in the admin dashboard to issue a notice. Categories are College Holiday, Examination Cancellation, Examination Postponement, Emergency Closure, Important Announcement, Fee Deadline, Weather Emergency, and Other. Choose an audience (all students, department, academic year, department + year, a class/cohort, or individually selected students), priority (critical, high, or normal), issue date, optional expiry, and optional PDF/image attachment. Class audiences resolve against the stored class/cohort profile value. Selected-student audiences accept only account IDs returned by the admin student directory and are revalidated as student accounts by the backend; empty, unknown, and non-student IDs are rejected. An emergency is signed and watermarked through the normal notice pipeline; the attachment is embedded in the signed PDF, or a signed PDF is generated from the notice text if no attachment is supplied. The chosen audience must match at least one provisioned student. Administrators can replace an active emergency with a new notice ID/signature/QR, or revoke it with a reason; the previous notice and QR remain verifiable as revoked. Original recipients receive replacement/revocation inbox entries. Read state and acknowledgement state are tracked independently.

Key endpoints (admin endpoints require an admin JWT; student notification endpoints require that student's JWT):
- `POST /api/admin/students`, `GET /api/admin/students`
- `POST /api/notices/emergency` (also available as `POST /api/admin/emergencies`)
- `GET /api/notifications`, `GET /api/notifications/unread-count`
- `PATCH /api/notifications/{notification_id}/read`, `PATCH /api/notifications/read-all`, `POST /api/notifications/{notification_id}/acknowledge`
- `GET /api/student/emergencies`, `GET /api/admin/notifications/analytics` (also `/api/admin/emergency-analytics`), `GET /api/admin/audit-log`
- `GET /api/notices/{notice_id}/status`, `POST /api/notices/{notice_id}/revoke`
- `POST /api/notifications/socket-ticket` then connect to `WS /api/notifications/ws?ticket=...` for private, reconnectable live alerts. Tickets are short-lived and single-use; the long-lived JWT is not placed in the WebSocket URL.

Existing SQLite/Postgres databases receive compatible additive student class/cohort and other emergency columns at startup; notification/recipient and WebSocket ticket tables are created through the existing SQLAlchemy `create_all` startup path.

WebSocket delivery reads the durable recipient inbox and polls for new rows every two seconds per connected client; there is no separate broker/background queue. A missed connection is recovered from the persisted inbox on reconnect.

## Deploy
- **Backend → Render:** `render.yaml` (Docker, Postgres, persistent disk). Set `ED25519_PRIVATE_KEY/PUBLIC_KEY`, `FRONTEND_URL`, `BACKEND_URL`, `ADMIN_*` in the dashboard. Never commit secrets.
- **Frontend → Vercel:** root `frontend/`; set the build environment variable `VITE_API_URL` to the deployed backend base URL (for example, `https://your-api.example.com`). Configure the backend `FRONTEND_URL` to the Vercel site URL so CORS allows the browser requests.
- QR links use `FRONTEND_URL`; set it to the final domain **before** issuing notices.

## Known limitations (honest baseline)
- Watermark survives JPEG (to q30) and 50–75% resizing. Cropping/rotation/perspective are handled by aligning to the registered original (needs the notice identified first); heavily stacked distortions (perspective + crop + resize + JPEG) may not recover the payload. Verdicts then degrade to UNVERIFIED rather than being forced.
- Robustness depends on image quality and transformations; passing local tests does not certify performance on every phone, screenshot, or compression pipeline.
- Visual comparison covers image notices; PDFs get text comparison. Only page 1 is aligned for multi-page PDFs.
- Key rotation: deploying a new ED25519 key pair retires the old key (still verifies earlier notices); a retired key can be revoked from the dashboard or `POST /api/admin/keys/{id}/revoke`, after which its notices fail verification. Keys are not generated in-app, by design (private keys stay in env/secrets manager).
- Rate limiting is in-memory per process; use Redis in production. No OCR is used for authenticity.
- Local backend tests and the frontend production build should be run before deployment; a live Render/Vercel deployment still requires configuring real service URLs and secrets.
