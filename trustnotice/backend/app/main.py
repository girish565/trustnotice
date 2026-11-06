import os, json, io, hashlib, secrets, datetime as dt, uuid, re
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import jwt, qrcode
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy import case, func, inspect, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.models import *
from app.cryptography.signing import *
from app.services.verification import NoticeRecord, verify_upload
from app.services import pipeline as pl
import cv2, numpy as np, time, collections

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret")
if len(JWT_SECRET.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET must contain at least 32 bytes. Configure a strong secret in backend/.env.")
STORE = Path(os.getenv("STORAGE_PATH", "./storage")); STORE.mkdir(exist_ok=True)
FRONT = os.getenv("FRONTEND_URL", "http://localhost:5173"); MAX_MB = 10
EMERGENCY_CATEGORIES = {
    "college_holiday", "examination_cancellation", "examination_postponement",
    "emergency_closure", "important_announcement", "fee_deadline",
    "weather_emergency", "other",
}
@asynccontextmanager
async def lifespan(_app):
    seed()
    yield

app = FastAPI(title="TRUSTNOTICE", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[FRONT], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)

def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(16); return salt + "$" + hashlib.scrypt(p.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
def check_pw(p, h): return secrets.compare_digest(hash_pw(p, h.split("$")[0]), h)
def db():
    s = Session()
    try: yield s
    finally: s.close()
def admin(cred=Depends(bearer), s=Depends(db)):
    if cred is None:
        raise HTTPException(401, "Invalid or missing token")
    try: data = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401, "Invalid or missing token")
    subject = data.get("sub")
    if not subject: raise HTTPException(401, "Invalid or missing token")
    u = s.query(User).filter_by(email=subject).first()
    if not u or u.role != "admin": raise HTTPException(403, "Administrator access required")
    return u

def current_user(cred=Depends(bearer), s=Depends(db)):
    if cred is None:
        raise HTTPException(401, "Invalid or missing token")
    try: data = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401, "Invalid or missing token")
    subject = data.get("sub")
    u = s.query(User).filter_by(email=subject).first() if subject else None
    if not u: raise HTTPException(401, "Invalid or missing token")
    return u

def student_user(u=Depends(current_user)):
    if u.role != "student": raise HTTPException(403, "Student access required")
    return u

# --- signing key: from env, else generated for dev ---
PRIV = os.getenv("ED25519_PRIVATE_KEY"); PUB = os.getenv("ED25519_PUBLIC_KEY")
if bool(PRIV) != bool(PUB):
    raise RuntimeError("ED25519_PRIVATE_KEY and ED25519_PUBLIC_KEY must be configured together.")
if not PRIV:
    PRIV, PUB = generate_keypair()
else:
    try:
        if not secrets.compare_digest(public_key_for(PRIV), PUB):
            raise RuntimeError("ED25519_PRIVATE_KEY does not match ED25519_PUBLIC_KEY.")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Ed25519 keys must be valid base64-encoded raw keys.") from exc
KEY_ID = key_id_for(PUB)
WM_KEY = hashlib.sha256(b"wm|" + PRIV.encode()).digest()  # watermark key derived server-side, never exposed
_hits = collections.defaultdict(list)
def limit(req: Request):  # simple per-IP rate limit for public endpoints (use Redis in production)
    ip, t = req.client.host, time.time(); _hits[ip] = [x for x in _hits[ip] if t - x < 60]
    if len(_hits[ip]) >= 30: raise HTTPException(429, "Too many requests; try again in a minute")
    _hits[ip].append(t)

def seed():
    Base.metadata.create_all(engine)
    additions = {
        "notices": {
            "description": "TEXT NOT NULL DEFAULT ''", "priority": "VARCHAR DEFAULT 'normal'",
            "audience": "VARCHAR DEFAULT 'all'", "academic_year": "VARCHAR",
            "is_emergency": "BOOLEAN NOT NULL DEFAULT FALSE", "has_attachment": "BOOLEAN NOT NULL DEFAULT FALSE",
            "attachment_path": "VARCHAR",
            "revoked_at": "TIMESTAMP", "revocation_reason": "TEXT",
            "replacement_notice_id": "VARCHAR", "replaces_notice_id": "VARCHAR",
        },
        "users": {"department": "VARCHAR", "academic_year": "VARCHAR", "student_id": "VARCHAR",
                  "class_name": "VARCHAR"},
        "audit_log": {"details": "TEXT"},
        "notifications": {"priority": "VARCHAR DEFAULT 'normal'"},
        "notification_recipients": {"delivered_at": "TIMESTAMP"},
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            present = {column["name"] for column in inspect(engine).get_columns(table)}
            for name, sql_type in columns.items():
                if name not in present:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
    s = Session()
    inst = s.query(Institution).first()
    if not inst:
        inst = Institution(institution_name="Demo College", institution_code="DEMO", public_key=PUB); s.add(inst); s.flush()
    cur = s.query(SigningKey).filter_by(key_id=KEY_ID).first()
    if not cur: s.add(SigningKey(institution_id=inst.id, key_id=KEY_ID, public_key=PUB))
    elif cur.status == "revoked": raise RuntimeError("ED25519 key configured for signing has been revoked; configure a new key pair.")
    for k in s.query(SigningKey).filter(SigningKey.key_id != KEY_ID, SigningKey.status == "active"): k.status = "retired"  # rotation
    em, pw = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if em and pw and not s.query(User).filter_by(email=em).first():
        s.add(User(name="Administrator", email=em, password_hash=hash_pw(pw), role="admin"))
    s.commit(); s.close()

class Login(BaseModel): email: str; password: str

@app.post("/api/auth/login")
def login(b: Login, request: Request, s=Depends(db), _=Depends(limit)):
    u = s.query(User).filter_by(email=b.email).first()
    if not u or not check_pw(b.password, u.password_hash): raise HTTPException(401, "Incorrect email or password")
    tok = jwt.encode({"sub": u.email, "exp": now() + dt.timedelta(hours=8)}, JWT_SECRET)
    return {"access_token": tok, "role": u.role}

@app.get("/api/auth/me")
def me(u=Depends(current_user)):
    return {"email": u.email, "name": u.name, "role": u.role,
            "department": u.department, "academic_year": u.academic_year}

def extract_text(data: bytes, name: str = "") -> str:
    if data.startswith(b"%PDF-"):
        import pymupdf as fitz
        with fitz.open(stream=data, filetype="pdf") as d: return "\n".join(p.get_text() for p in d)
    return ""

def validate_notice_dates(issue_date: str, expiry_date: str) -> None:
    try:
        issued = dt.date.fromisoformat(issue_date)
        expires = dt.date.fromisoformat(expiry_date)
    except (TypeError, ValueError):
        raise HTTPException(422, "Issue and expiry dates must be valid ISO dates (YYYY-MM-DD).")
    if expires < issued:
        raise HTTPException(422, "Expiry date must be on or after the issue date.")

def validate_optional_notice_dates(issue_date: str, expiry_date: str | None) -> None:
    try:
        issued = dt.date.fromisoformat(issue_date)
    except (TypeError, ValueError):
        raise HTTPException(422, "Issue date must be a valid ISO date (YYYY-MM-DD).")
    if expiry_date:
        try:
            expires = dt.date.fromisoformat(expiry_date)
        except (TypeError, ValueError):
            raise HTTPException(422, "Expiry date must be a valid ISO date (YYYY-MM-DD).")
        if expires < issued:
            raise HTTPException(422, "Expiry date must be on or after the issue date.")

def make_qr(notice_id, version) -> bytes:
    img = qrcode.make(f"{os.getenv('FRONTEND_URL', FRONT)}/verify/{notice_id}?v={version}")
    b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()

def read_upload(f: UploadFile):
    data = f.file.read(MAX_MB * 2**20 + 1)
    if len(data) > MAX_MB * 2**20: raise HTTPException(413, f"File exceeds {MAX_MB} MB")
    if data.startswith(b"%PDF-"):
        try:
            import pymupdf as fitz
            with fitz.open(stream=data, filetype="pdf") as document:
                if document.needs_pass or not document.page_count:
                    raise HTTPException(415, "The uploaded PDF is encrypted or has no pages.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(415, "The uploaded PDF is unreadable.") from exc
    elif data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        if cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) is None:
            raise HTTPException(415, "The uploaded image is unreadable.")
    else:
        raise HTTPException(415, "Only readable PDF, PNG or JPG files are accepted.")
    return data

def issue(s, u, inst, nid, version, title, department, category, issue_date, expiry_date, data, filename):
    ref = pl.wm_ref(WM_KEY, nid, version); qrb = make_qr(nid, version)
    try: wdata, ext = pl.embed_for_file(data, filename, ref, version, WM_KEY, qrb)
    except Exception as e: raise HTTPException(422, f"Could not process document: {e}")
    m = build_manifest(notice_id=nid, institution_id=inst.institution_code, document_hash=sha256_hex(wdata),
                       issued_at=issue_date, expires_at=expiry_date, category=category, version=version, key_id=KEY_ID)
    sig = sign_manifest(m, PRIV); orig = STORE / f"{nid}_v{version}_original_{uuid.uuid4().hex[:6]}"; orig.write_bytes(data)
    auth = STORE / f"{nid}_v{version}_authenticated.{ext}"; auth.write_bytes(wdata)
    (STORE / f"{nid}_qr.png").write_bytes(qrb)
    return m, sig, str(orig), str(auth), ext

def emergency_document(title: str, description: str, category: str, priority: str,
                       issue_date: str, expiry_date: str | None,
                       attachment: bytes | None = None) -> bytes:
    import pymupdf as fitz
    document = fitz.open()
    page = document.new_page()
    page.insert_text((60, 70), "EMERGENCY NOTICE", fontsize=20, color=(0.7, 0.1, 0.1))
    lines = [f"Title: {title}", f"Category: {category}", f"Priority: {priority.upper()}",
             f"Issued: {issue_date}", f"Expires: {expiry_date or 'Until revoked'}", "", description]
    y = 115
    for line in lines:
        for start in range(0, max(1, len(line)), 95):
            page.insert_text((60, y), line[start:start + 95], fontsize=11)
            y += 18
    if attachment:
        if attachment.startswith(b"%PDF-"):
            with fitz.open(stream=attachment, filetype="pdf") as attached:
                document.insert_pdf(attached)
        else:
            page = document.new_page()
            page.insert_image(page.rect, stream=attachment)
    return document.tobytes()

def targeted_students(s, audience: str, department: str | None,
                      academic_year: str | None, class_name: str | None = None,
                      selected_student_ids: list[int] | None = None):
    query = s.query(User).filter_by(role="student")
    if audience in ("department", "department_year"):
        query = query.filter(User.department == department)
    if audience in ("year", "department_year"):
        query = query.filter(User.academic_year == academic_year)
    if audience == "class":
        query = query.filter(User.class_name == class_name)
    if audience == "selected":
        query = query.filter(User.id.in_(selected_student_ids or []))
    return query.all()

def create_notification(s, *, kind: str, title: str, message: str,
                        notice_id: str, recipients, priority: str = "normal"):
    notification = Notification(kind=kind, title=title, message=message,
                                notice_id=notice_id, priority=priority)
    s.add(notification); s.flush()
    for recipient in recipients:
        s.add(NotificationRecipient(notification_id=notification.id, user_id=recipient.id,
                                    delivered_at=now()))
    return notification

def notify_notice_recipients(s, notice_id: str, *, kind: str, title: str, message: str,
                             delivery_notice_id: str | None = None):
    user_ids = {row[0] for row in s.query(NotificationRecipient.user_id)
                .join(Notification, Notification.id == NotificationRecipient.notification_id)
                .filter(Notification.notice_id == notice_id, Notification.kind == "emergency").all()}
    if user_ids:
        create_notification(s, kind=kind, title=title, message=message,
                            notice_id=delivery_notice_id or notice_id,
                            priority=(s.query(Notice).filter_by(notice_id=notice_id).first().priority or "normal"),
                            recipients=s.query(User).filter(User.id.in_(user_ids)).all())

def notification_json(notification: Notification, recipient: NotificationRecipient):
    return {"id": recipient.id, "kind": notification.kind, "title": notification.title,
            "message": notification.message, "notice_id": notification.notice_id,
            "priority": notification.priority or "normal",
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
            "delivered_at": recipient.delivered_at.isoformat() if recipient.delivered_at else None,
            "read": recipient.read_at is not None, "read_at": recipient.read_at.isoformat() if recipient.read_at else None,
            "acknowledged": recipient.acknowledged_at is not None,
            "acknowledged_at": recipient.acknowledged_at.isoformat() if recipient.acknowledged_at else None}

@app.post("/api/admin/students", status_code=201)
def create_student(name: str = Form(...), email: str = Form(...), password: str = Form(...),
                   student_id: str = Form(...), department: str = Form(...),
                   academic_year: str = Form(...), class_name: str | None = Form(None),
                   u=Depends(admin), s=Depends(db)):
    name, email, student_id = name.strip(), email.strip().lower(), student_id.strip()
    department, academic_year = department.strip(), academic_year.strip()
    class_name = class_name.strip() if class_name and class_name.strip() else None
    if not name or not department or not academic_year or not student_id:
        raise HTTPException(422, "Name, student ID, department, and academic year are required.")
    if len(password) < 12:
        raise HTTPException(422, "Student password must be at least 12 characters.")
    if class_name and len(class_name) > 120:
        raise HTTPException(422, "Class/cohort must be at most 120 characters.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "A valid email address is required.")
    if s.query(User).filter((User.email == email) | (User.student_id == student_id)).first():
        raise HTTPException(409, "Email or student ID is already registered.")
    student = User(name=name, email=email, password_hash=hash_pw(password), role="student",
                   student_id=student_id, department=department, academic_year=academic_year,
                   class_name=class_name)
    s.add(student); s.flush()
    s.add(AuditLog(actor=u.email, action="create-student", target=student.email,
                   details=json.dumps({"student_id": student_id, "department": department,
                                       "academic_year": academic_year, "class_name": class_name})))
    s.commit()
    return {"id": student.id, "name": student.name, "email": student.email,
            "student_id": student.student_id, "department": student.department,
            "academic_year": student.academic_year, "class_name": student.class_name}

@app.get("/api/admin/students")
def list_students(u=Depends(admin), s=Depends(db)):
    return [{"id": user.id, "name": user.name, "email": user.email,
             "student_id": user.student_id, "department": user.department,
             "academic_year": user.academic_year, "class_name": user.class_name}
            for user in s.query(User).filter_by(role="student").order_by(User.id.desc()).all()]

@app.post("/api/notices/emergency")
@app.post("/api/admin/emergencies")
def create_emergency(title: str = Form(...), description: str = Form(...),
                     category: str = Form(...), priority: str = Form(...),
                     audience: str = Form("all"), department: str | None = Form(None),
                     academic_year: str | None = Form(None), issue_date: str = Form(...),
                     expiry_date: str | None = Form(None), attachment: UploadFile | None = File(None),
                     replaces_notice_id: str | None = Form(None),
                     class_name: str | None = Form(None),
                     selected_student_ids: list[int] = Form([]),
                     u=Depends(admin), s=Depends(db)):
    title, description, category = title.strip(), description.strip(), category.strip()
    department = department.strip() if department else None
    academic_year = academic_year.strip() if academic_year else None
    class_name = class_name.strip() if class_name else None
    expiry_date = expiry_date.strip() or None if expiry_date else None
    if not title or len(title) > 200 or not description or len(description) > 10000 or not category or len(category) > 80:
        raise HTTPException(422, "Title, description, and category are required and are limited to 200, 10000, and 80 characters.")
    if category not in EMERGENCY_CATEGORIES:
        raise HTTPException(422, f"Category must be one of: {', '.join(sorted(EMERGENCY_CATEGORIES))}.")
    if priority not in {"normal", "high", "critical"}:
        raise HTTPException(422, "Priority must be normal, high, or critical.")
    if audience not in {"all", "department", "year", "department_year", "class", "selected"}:
        raise HTTPException(422, "Audience must be all, department, year, department_year, class, or selected.")
    if audience in {"department", "department_year"} and not department:
        raise HTTPException(422, "Department is required for this audience.")
    if audience in {"year", "department_year"} and not academic_year:
        raise HTTPException(422, "Academic year is required for this audience.")
    if audience == "all" and (department or academic_year):
        raise HTTPException(422, "Department and academic year must match the selected audience.")
    if audience == "department" and academic_year:
        raise HTTPException(422, "Academic year is not used by a department-only audience.")
    if audience == "year" and department:
        raise HTTPException(422, "Department is not used by an academic-year-only audience.")
    if audience == "class" and not class_name:
        raise HTTPException(422, "Class/cohort is required for this audience.")
    if audience == "selected" and not selected_student_ids:
        raise HTTPException(422, "Select at least one student.")
    if audience in {"all", "department", "year", "department_year"} and class_name:
        raise HTTPException(422, "Class/cohort must match the selected audience.")
    if audience != "selected" and selected_student_ids:
        raise HTTPException(422, "Selected student IDs must match the selected audience.")
    if audience != "class" and class_name:
        raise HTTPException(422, "Class/cohort must match the selected audience.")
    if audience in {"class", "selected"} and (department or academic_year):
        raise HTTPException(422, "Department and academic year must match the selected audience.")
    if len(set(selected_student_ids)) != len(selected_student_ids) or any(
        student_id <= 0 for student_id in selected_student_ids
    ):
        raise HTTPException(422, "Selected student IDs must be unique valid student account IDs.")
    if (department and len(department) > 120) or (academic_year and len(academic_year) > 32):
        raise HTTPException(422, "Department or academic year is too long.")
    validate_optional_notice_dates(issue_date, expiry_date)
    original_notice = None
    if replaces_notice_id:
        original_notice = s.query(Notice).filter_by(notice_id=replaces_notice_id, is_emergency=True).first()
        if not original_notice:
            raise HTTPException(404, "The emergency notice to replace was not found.")
        if original_notice.status == "revoked":
            raise HTTPException(409, "A revoked notice cannot be replaced.")
    attachment_data = read_upload(attachment) if attachment else None
    recipients = targeted_students(s, audience, department, academic_year, class_name,
                                   selected_student_ids)
    if audience == "selected" and len(recipients) != len(selected_student_ids):
        raise HTTPException(422, "Every selected ID must belong to an existing student account.")
    if not recipients:
        raise HTTPException(422, "No student accounts match the selected audience.")
    main_data = emergency_document(title, description, category, priority, issue_date, expiry_date, attachment_data)
    inst = s.query(Institution).first()
    nid = f"{inst.institution_code}-{dt.date.today().year}-{uuid.uuid4().hex[:8].upper()}"
    manifest, signature, original_path, authenticated_path, _ = issue(
        s, u, inst, nid, 1, title, department or "", category, issue_date, expiry_date,
        main_data, f"{nid}.pdf")
    notice = Notice(notice_id=nid, institution_id=inst.id, title=title, department=department or "",
                    category=category, issue_date=issue_date, expiry_date=expiry_date,
                    description=description, original_file_path=original_path,
                    authenticated_file_path=authenticated_path, sha256_hash=manifest["document_hash"],
                    signature=signature, manifest=json.dumps(manifest), text=description, key_id=KEY_ID,
                    priority=priority, audience=audience, academic_year=academic_year,
                    is_emergency=True, has_attachment=bool(attachment_data),
                    replaces_notice_id=original_notice.notice_id if original_notice else None)
    s.add(notice)
    s.add(NoticeVersion(notice_id=nid, version_number=1,
                        content_hash=manifest["document_hash"], signature=signature))
    create_notification(s, kind="emergency", title=title,
                        message=description, notice_id=nid, recipients=recipients,
                        priority=priority)
    s.add(AuditLog(actor=u.email, action="create-emergency", target=nid,
                   details=json.dumps({"priority": priority, "audience": audience,
                                       "department": department, "academic_year": academic_year,
                                       "recipient_count": len(recipients)})))
    if original_notice:
        original_notice.replacement_notice_id = nid
        original_notice.status = "revoked"
        original_notice.revoked_at = now()
        original_notice.revocation_reason = f"Replaced by emergency notice {nid}."
        notify_notice_recipients(s, original_notice.notice_id, kind="notice_replaced",
                                 title="Emergency notice replaced",
                                 message=f"{original_notice.title} was replaced by {title} ({nid}).",
                                 delivery_notice_id=nid)
        s.add(AuditLog(actor=u.email, action="replace-emergency",
                       target=original_notice.notice_id,
                       details=json.dumps({"replacement_notice_id": nid})))
    s.commit()
    return {"notice_id": nid, "version": 1, "sha256": manifest["document_hash"],
            "recipient_count": len(recipients), "replacement_notice_id": nid if original_notice else None}

@app.post("/api/notices/create")
def create(title: str = Form(...), department: str = Form(...), category: str = Form(...), issue_date: str = Form(...),
           expiry_date: str = Form(...), description: str = Form(""), file: UploadFile = File(...), u=Depends(admin), s=Depends(db)):
    validate_notice_dates(issue_date, expiry_date)
    data = read_upload(file); inst = s.query(Institution).first()
    nid = f"{inst.institution_code}-{dt.date.today().year}-{uuid.uuid4().hex[:8].upper()}"
    m, sig, op, ap, ext = issue(s, u, inst, nid, 1, title, department, category, issue_date, expiry_date, data, file.filename)
    s.add(Notice(notice_id=nid, institution_id=inst.id, title=title, department=department, category=category, issue_date=issue_date,
                 expiry_date=expiry_date, description=description, original_file_path=op, authenticated_file_path=ap, sha256_hash=m["document_hash"], signature=sig,
                 manifest=json.dumps(m), text=extract_text(data, file.filename), key_id=KEY_ID))
    s.add(NoticeVersion(notice_id=nid, version_number=1, content_hash=m["document_hash"], signature=sig))
    s.add(AuditLog(actor=u.email, action="create", target=nid)); s.commit()
    return {"notice_id": nid, "sha256": m["document_hash"], "key_id": KEY_ID, "qr": f"/api/notices/{nid}/qr", "download": f"/api/notices/{nid}/download"}

@app.get("/api/notices/{notice_id}/download")
def download(notice_id: str, u=Depends(admin), s=Depends(db)):
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n: raise HTTPException(404, "Notice not found")
    return FileResponse(n.authenticated_file_path, filename=Path(n.authenticated_file_path).name)

@app.post("/api/notices/{notice_id}/new-version")
def new_version(notice_id: str, title: str = Form(...), department: str = Form(...), category: str = Form(...), issue_date: str = Form(...),
                expiry_date: str = Form(...), description: str = Form(""), file: UploadFile = File(...), u=Depends(admin), s=Depends(db)):
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n: raise HTTPException(404, "Notice not found")
    validate_notice_dates(issue_date, expiry_date)
    data = read_upload(file); v = n.version + 1; inst = s.query(Institution).first()
    m, sig, op, ap, ext = issue(s, u, inst, notice_id, v, title, department, category, issue_date, expiry_date, data, file.filename)
    prev = s.query(NoticeVersion).filter_by(notice_id=notice_id, version_number=n.version).first()
    n.version, n.title, n.department, n.category, n.issue_date, n.expiry_date, n.description = v, title, department, category, issue_date, expiry_date, description
    n.original_file_path, n.authenticated_file_path, n.sha256_hash, n.signature, n.manifest, n.status = op, ap, m["document_hash"], sig, json.dumps(m), "active"
    n.text = extract_text(data, file.filename)
    s.add(NoticeVersion(notice_id=notice_id, version_number=v, previous_version_id=prev.id if prev else None, content_hash=m["document_hash"], signature=sig))
    s.add(AuditLog(actor=u.email, action=f"new-version-{v}", target=notice_id)); s.commit()
    return {"notice_id": notice_id, "version": v, "sha256": m["document_hash"]}

@app.get("/api/notices/{notice_id}/qr")
def qr(notice_id: str, s=Depends(db)):
    if not s.query(Notice).filter_by(notice_id=notice_id).first():
        raise HTTPException(404, "Notice not found")
    path = STORE / f"{notice_id}_qr.png"
    if not path.is_file():
        raise HTTPException(404, "QR code not found")
    return FileResponse(path, media_type="image/png")
@app.get("/api/notices")
def list_notices(u=Depends(admin), s=Depends(db)):
    results = []
    delivery_counts = {
        notice_id: (total or 0, delivered or 0, read or 0, acknowledged or 0)
        for notice_id, total, delivered, read, acknowledged in s.query(
            Notification.notice_id,
            func.count(NotificationRecipient.id),
            func.sum(case((NotificationRecipient.delivered_at.is_not(None), 1), else_=0)),
            func.sum(case((NotificationRecipient.read_at.is_not(None), 1), else_=0)),
            func.sum(case((NotificationRecipient.acknowledged_at.is_not(None), 1), else_=0)),
        ).join(Notification, Notification.id == NotificationRecipient.notification_id
        ).filter(Notification.kind == "emergency"
        ).group_by(Notification.notice_id).all()
    }
    for n in s.query(Notice).order_by(Notice.id.desc()):
        total, delivered, read, acknowledged = delivery_counts.get(n.notice_id, (0, 0, 0, 0)) if n.is_emergency else (0, 0, 0, 0)
        results.append(dict(notice_id=n.notice_id, title=n.title, status=n.status, version=n.version,
                            issue_date=n.issue_date, is_emergency=bool(n.is_emergency),
                            priority=n.priority or "normal", audience=n.audience or "all",
                            recipient_count=total, delivered_count=delivered,
                            read_count=read, acknowledged_count=acknowledged,
                            revoked_at=n.revoked_at.isoformat() if n.revoked_at else None,
                            revocation_reason=n.revocation_reason,
                            replacement_notice_id=n.replacement_notice_id))
    return results
@app.get("/api/notices/{notice_id}")
def get_notice(notice_id: str, s=Depends(db)):  # public: no file paths / internals
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n: raise HTTPException(404, "Notice not found")
    return dict(notice_id=n.notice_id, title=n.title, department=n.department, issue_date=n.issue_date,
                expiry_date=n.expiry_date, description=n.description or "", status=n.status, version=n.version,
                signature_key=n.key_id, is_emergency=bool(n.is_emergency), priority=n.priority or "normal",
                revoked_at=n.revoked_at.isoformat() if n.revoked_at else None,
                revocation_reason=n.revocation_reason, replacement_notice_id=n.replacement_notice_id)

@app.get("/api/notices/{notice_id}/status")
def notice_status(notice_id: str, s=Depends(db)):
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    return {"notice_id": n.notice_id, "status": n.status,
            "verification": "RED" if n.status == "revoked" else "VALID",
            "revoked_at": n.revoked_at.isoformat() if n.revoked_at else None,
            "revocation_reason": n.revocation_reason,
            "replacement_notice_id": n.replacement_notice_id}

@app.post("/api/notices/{notice_id}/revoke")
def revoke(notice_id: str, reason: str | None = Form(None), u=Depends(admin), s=Depends(db)):
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n: raise HTTPException(404, "Notice not found")
    if n.status == "revoked":
        raise HTTPException(409, "Notice is already revoked.")
    reason = (reason or ("Replaced by " + n.replacement_notice_id if n.replacement_notice_id else "Revoked by administrator.")).strip()
    if not reason or len(reason) > 1000:
        raise HTTPException(422, "A revocation reason of at most 1000 characters is required.")
    n.status, n.revoked_at, n.revocation_reason = "revoked", now(), reason
    if n.is_emergency:
        notify_notice_recipients(s, notice_id, kind="notice_revoked",
                                 title="Emergency notice revoked", message=reason)
    s.add(AuditLog(actor=u.email, action="revoke", target=notice_id, details=json.dumps({"reason": reason})))
    s.commit()
    return {"status": "revoked", "revoked_at": n.revoked_at.isoformat(), "reason": reason}

@app.get("/api/notifications")
@app.get("/api/student/notifications")
def student_notifications(u=Depends(student_user), s=Depends(db), unread_only: bool = False):
    query = s.query(NotificationRecipient, Notification).join(
        Notification, Notification.id == NotificationRecipient.notification_id
    ).filter(NotificationRecipient.user_id == u.id)
    if unread_only: query = query.filter(NotificationRecipient.read_at.is_(None))
    rows = query.order_by(NotificationRecipient.id.desc()).limit(200).all()
    return [notification_json(notification, recipient) for recipient, notification in rows]

@app.get("/api/notifications/unread-count")
def unread_notification_count(u=Depends(student_user), s=Depends(db)):
    count = s.query(func.count(NotificationRecipient.id)).filter_by(
        user_id=u.id, read_at=None).scalar() or 0
    return {"unread_count": count}

@app.patch("/api/notifications/read-all")
@app.post("/api/student/notifications/read-all")
def read_all_notifications(u=Depends(student_user), s=Depends(db)):
    changed = s.query(NotificationRecipient).filter_by(user_id=u.id, read_at=None).update(
        {NotificationRecipient.read_at: now()}, synchronize_session=False)
    if changed:
        s.add(AuditLog(actor=u.email, action="notifications-read-all", target=u.email,
                       details=json.dumps({"updated": changed})))
    s.commit()
    return {"updated": changed}

@app.patch("/api/notifications/{recipient_id}/read")
@app.post("/api/student/notifications/{recipient_id}/read")
def read_notification(recipient_id: int, u=Depends(student_user), s=Depends(db)):
    recipient = s.query(NotificationRecipient).filter_by(id=recipient_id, user_id=u.id).first()
    if not recipient: raise HTTPException(404, "Notification not found.")
    if not recipient.read_at:
        recipient.read_at = now()
        s.add(AuditLog(actor=u.email, action="notification-read", target=str(recipient_id)))
        s.commit()
    return {"read": True, "read_at": recipient.read_at.isoformat()}

@app.post("/api/notifications/{recipient_id}/acknowledge")
@app.post("/api/student/notifications/{recipient_id}/acknowledge")
def acknowledge_notification(recipient_id: int, u=Depends(student_user), s=Depends(db)):
    recipient = s.query(NotificationRecipient).filter_by(id=recipient_id, user_id=u.id).first()
    if not recipient: raise HTTPException(404, "Notification not found.")
    if not recipient.acknowledged_at:
        recipient.acknowledged_at = now()
        s.add(AuditLog(actor=u.email, action="notification-acknowledge", target=str(recipient_id)))
        s.commit()
    return {"acknowledged": True, "acknowledged_at": recipient.acknowledged_at.isoformat()}

@app.get("/api/student/emergencies")
def student_emergencies(u=Depends(student_user), s=Depends(db)):
    rows = s.query(NotificationRecipient, Notification).join(
        Notification, Notification.id == NotificationRecipient.notification_id
    ).filter(NotificationRecipient.user_id == u.id,
             Notification.kind.in_(["emergency", "notice_replaced"])).order_by(
        NotificationRecipient.id.desc()).limit(200).all()
    active = []
    for recipient, notification in rows:
        joined = s.query(Notice, Institution).outerjoin(
            Institution, Institution.id == Notice.institution_id
        ).filter(Notice.notice_id == notification.notice_id).first()
        notice, institution = joined if joined else (None, None)
        if not notice or not notice.is_emergency: continue
        is_expired = False
        if notice.expiry_date:
            is_expired = dt.date.fromisoformat(notice.expiry_date) < dt.datetime.now(dt.timezone.utc).date()
        active.append({**notification_json(notification, recipient), "department": notice.department,
                       "category": notice.category, "institution_name": institution.institution_name if institution else None,
                       "priority": notice.priority or "normal", "status": notice.status,
                       "issue_date": notice.issue_date, "expiry_date": notice.expiry_date,
                       "has_attachment": bool(notice.has_attachment or notice.attachment_path),
                       "is_active": notice.status == "active" and not is_expired,
                       "replacement_notice_id": notice.replacement_notice_id})
    return active

@app.post("/api/notifications/socket-ticket")
def create_socket_ticket(u=Depends(student_user), s=Depends(db)):
    s.query(WebSocketTicket).filter(WebSocketTicket.expires_at <= now()).delete(synchronize_session=False)
    ticket = secrets.token_urlsafe(32)
    s.add(WebSocketTicket(token_hash=hashlib.sha256(ticket.encode()).hexdigest(),
                          user_id=u.id, expires_at=now() + dt.timedelta(seconds=60)))
    s.commit()
    return {"ticket": ticket}

@app.get("/api/student/notices/{notice_id}/download")
def student_notice_download(notice_id: str, u=Depends(student_user), s=Depends(db)):
    allowed = s.query(NotificationRecipient.id).join(
        Notification, Notification.id == NotificationRecipient.notification_id
    ).filter(NotificationRecipient.user_id == u.id, Notification.notice_id == notice_id,
              Notification.kind.in_(["emergency", "notice_replaced"])).first()
    notice = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not allowed or not notice or not notice.is_emergency:
        raise HTTPException(404, "Notice not found.")
    return FileResponse(notice.authenticated_file_path, filename=Path(notice.authenticated_file_path).name)

@app.get("/api/admin/notifications/analytics")
@app.get("/api/admin/emergency-analytics")
def emergency_analytics(u=Depends(admin), s=Depends(db)):
    emergencies = s.query(Notice).filter_by(is_emergency=True)
    total = emergencies.count()
    notification_rows = s.query(NotificationRecipient, Notification).join(
        Notification, Notification.id == NotificationRecipient.notification_id
    ).filter(Notification.kind.in_(["emergency", "notice_replaced"])).all()
    emergency_rows = [(row, notification) for row, notification in notification_rows
                      if notification.kind == "emergency"]
    replacement_deliveries = sum(notification.kind == "notice_replaced"
                                  for _, notification in notification_rows)
    return {"emergencies": total,
            "students_targeted": len({row.user_id for row, _ in emergency_rows}),
            "recipient_deliveries": len(emergency_rows),
            "delivered": sum(row.delivered_at is not None for row, _ in notification_rows),
            "read": sum(row.read_at is not None for row, _ in notification_rows),
            "replacement_deliveries": replacement_deliveries,
            "unread": sum(row.read_at is None for row, _ in notification_rows),
            "acknowledged": sum(row.acknowledged_at is not None for row, _ in emergency_rows),
            "pending_acknowledgements": sum(row.acknowledged_at is None for row, _ in emergency_rows),
            "failed_deliveries": sum(row.delivered_at is None for row, _ in notification_rows),
            "by_priority": {priority: emergencies.filter_by(priority=priority).count()
                            for priority in ("critical", "high", "normal", "low")},
            "revoked": emergencies.filter_by(status="revoked").count()}

@app.get("/api/admin/audit-log")
def audit_log(u=Depends(admin), s=Depends(db)):
    return [{"actor": row.actor, "action": row.action, "target": row.target,
             "details": row.details, "at": row.at.isoformat() if row.at else None}
            for row in s.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()]

@app.websocket("/api/notifications/ws")
async def notification_socket(websocket: WebSocket, ticket: str, after: int = 0):
    with Session() as session:
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        grant = session.query(WebSocketTicket).filter_by(token_hash=digest).first()
        if grant:
            consumed = session.query(WebSocketTicket).filter(
                WebSocketTicket.id == grant.id, WebSocketTicket.used_at.is_(None),
                WebSocketTicket.expires_at > now()
            ).update({WebSocketTicket.used_at: now()}, synchronize_session=False)
            session.commit()
            user = session.query(User).filter_by(id=grant.user_id, role="student").first() if consumed else None
            user_id = user.id if user else None
        else:
            user_id = None
    if user_id is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    cursor = max(0, after)
    try:
        while True:
            with Session() as session:
                rows = session.query(NotificationRecipient, Notification).join(
                    Notification, Notification.id == NotificationRecipient.notification_id
                ).filter(NotificationRecipient.user_id == user_id,
                         NotificationRecipient.id > cursor).order_by(NotificationRecipient.id).limit(100).all()
                for recipient, notification in rows:
                    await websocket.send_json(notification_json(notification, recipient))
                    cursor = recipient.id
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return

def _registry(s, nid):
    keys = KeyRegistry()
    for k in s.query(SigningKey):
        keys.register(k.public_key)
        if k.status == "revoked": keys.revoke(k.key_id)
    n = s.query(Notice).filter_by(notice_id=nid).first() if nid else None
    reg = {nid: NoticeRecord(json.loads(n.manifest), n.signature, n.text, n.status)} if n else {}
    return reg, keys

def detect_qr_id(data: bytes):
    try:
        import re
        is_pdf = data.startswith(b"%PDF-")
        img = pl.first_page_image(data, is_pdf)
        if img is None: return None
        txt, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        m = re.search(r"/verify/([A-Za-z0-9\-]+)", txt or ""); return m.group(1) if m else None
    except cv2.error: return None

@app.post("/api/verify/upload")
def verify(request: Request, file: UploadFile = File(...), notice_id: str | None = Form(None), s=Depends(db), _=Depends(limit)):
    data = read_upload(file); is_pdf = data.startswith(b"%PDF-")
    up = pl.first_page_image(data, is_pdf)
    qr_id = detect_qr_id(data)
    qid = notice_id or qr_id
    by_wm = False
    if not qid and up is not None:  # no readable QR: try blind watermark recovery, then registry lookup
        from app.watermarking.dwt_dct import extract
        got = extract(up, WM_KEY)
        if got:
            for cand in s.query(Notice):
                if pl.wm_ref(WM_KEY, cand.notice_id, got[1]) == got[0]: qid, by_wm = cand.notice_id, True; break
    reg, keys = _registry(s, qid); n = s.query(Notice).filter_by(notice_id=qid).first() if qid else None
    ev, wm_id = None, (qid if by_wm else None)
    if n and up is not None and not (sha256_hex(data) == n.sha256_hash):
        orig = pl.first_page_image(Path(n.authenticated_file_path).read_bytes(), n.authenticated_file_path.endswith(".pdf"))
        ev = pl.image_evidence(up, orig, WM_KEY, pl.wm_ref(WM_KEY, qid, n.version))
        wm_id = qid if (ev["watermark_ok"] or by_wm) else None
    r = verify_upload(data, reg, keys, qr_notice_id=qid, watermark_notice_id=wm_id, extracted_text=(extract_text(data) or None) if is_pdf else None,
                      image_similarity=ev["similarity"] if ev and not is_pdf else None,
                      changed_regions=len(ev["boxes"]) if ev and not is_pdf else 0)
    s.add(VerificationLog(notice_id=r.notice_id, uploaded_file_hash=sha256_hex(data), verification_status=r.status,
        watermark_detected=r.watermark_detected, signature_valid=r.signature_valid, similarity_score=r.content_similarity, tampering_detected=r.status == "RED")); s.commit()
    out = dict(r.__dict__); out["suspicious_regions"] = ev["boxes"] if ev else []
    out["qr_detected"] = qr_id is not None
    out["qr_matches_notice"] = bool(qr_id and qid == qr_id)
    if n: out["notice"] = dict(title=n.title, department=n.department, issue_date=n.issue_date,
                               version=n.version, is_pdf=n.authenticated_file_path.lower().endswith(".pdf"))
    return out

@app.post("/api/verify/qr")
def verify_qr(request: Request, file: UploadFile = File(...), s=Depends(db), _=Depends(limit)):
    qid = detect_qr_id(read_upload(file))
    if not qid: raise HTTPException(422, "No readable QR code found in the image")
    return get_notice(qid, s)

@app.get("/api/verify/{notice_id}")
def verify_record(notice_id: str, s=Depends(db)):
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n: raise HTTPException(404, "Notice not found in registry")
    reg, keys = _registry(s, notice_id); rec = reg[notice_id]
    ok = verify_manifest(rec.manifest, rec.signature, keys.get(rec.manifest["key_id"]) or "")
    exp = dt.datetime.fromisoformat(n.expiry_date) if n.expiry_date else None
    exp = exp.replace(tzinfo=dt.timezone.utc) if exp and exp.tzinfo is None else exp.astimezone(dt.timezone.utc) if exp else None
    return dict(notice_id=notice_id, title=n.title, version=n.version, signature_valid=ok,
                validity="REVOKED" if n.status == "revoked" else "EXPIRED" if exp and now() > exp else "VALID",
                revoked_at=n.revoked_at.isoformat() if n.revoked_at else None,
                revocation_reason=n.revocation_reason, replacement_notice_id=n.replacement_notice_id,
                note="This confirms the registry record only. Upload the document to verify its content.")

@app.post("/api/watermark/embed")
def wm_embed(file: UploadFile = File(...), notice_id: str = Form(...), version: int = Form(1), u=Depends(admin)):
    data, _ = pl.embed_for_file(read_upload(file), file.filename, pl.wm_ref(WM_KEY, notice_id, version), version, WM_KEY)
    return Response(data, media_type="application/octet-stream")

@app.post("/api/watermark/extract")
def wm_extract(request: Request, file: UploadFile = File(...), s=Depends(db), _=Depends(limit)):
    from app.watermarking.dwt_dct import extract
    d = read_upload(file); img = pl.first_page_image(d, d[:4] == b"%PDF"); got = extract(img, WM_KEY)
    if not got: return {"detected": False, "note": "No recoverable watermark. This alone does not prove a notice is fake."}
    for n in s.query(Notice):
        if pl.wm_ref(WM_KEY, n.notice_id, got[1]) == got[0]:
            return {"detected": True, "notice_id": n.notice_id, "version": got[1], "note": "Watermark is a pointer only; verify the document to authenticate."}
    return {"detected": True, "notice_id": None, "note": "Watermark found but matches no registered notice."}

class Reg(BaseModel): name: str; email: str; password: str
@app.post("/api/auth/register")
def register(b: Reg, u=Depends(admin), s=Depends(db)):  # only an existing admin can create admins
    if len(b.password) < 10: raise HTTPException(422, "Password must be at least 10 characters")
    if s.query(User).filter_by(email=b.email).first(): raise HTTPException(409, "Email already registered")
    s.add(User(name=b.name, email=b.email, password_hash=hash_pw(b.password), role="admin"))
    s.add(AuditLog(actor=u.email, action="register-admin", target=b.email)); s.commit(); return {"ok": True}

@app.get("/api/admin/keys")
def list_keys(u=Depends(admin), s=Depends(db)):
    return [dict(key_id=k.key_id, status=k.status, current=k.key_id == KEY_ID, created_at=str(k.created_at), revoked_at=str(k.revoked_at) if k.revoked_at else None)
            for k in s.query(SigningKey).order_by(SigningKey.id.desc())]

@app.post("/api/admin/keys/{key_id}/revoke")
def revoke_key(key_id: str, u=Depends(admin), s=Depends(db)):
    """Revoking a key makes every notice signed with it fail verification. Rotation = deploy a new
    ED25519 key pair (old key becomes 'retired' but stays verifiable); revoke only if compromised."""
    k = s.query(SigningKey).filter_by(key_id=key_id).first()
    if not k: raise HTTPException(404, "Key not found")
    if k.key_id == KEY_ID: raise HTTPException(409, "This is the active signing key. Deploy a new key pair first, then revoke the old one.")
    k.status, k.revoked_at = "revoked", now(); s.add(AuditLog(actor=u.email, action="revoke-key", target=key_id)); s.commit()
    return {"status": "revoked", "key_id": key_id}

@app.get("/api/admin/dashboard")
def dash(u=Depends(admin), s=Depends(db)):
    c = lambda q: q.scalar() or 0
    return dict(total_notices=c(s.query(func.count(Notice.id))), revoked=c(s.query(func.count(Notice.id)).filter_by(status="revoked")),
                verified=c(s.query(func.count(VerificationLog.id)).filter(VerificationLog.verification_status.in_(["GREEN", "YELLOW"]))),
                suspicious=c(s.query(func.count(VerificationLog.id)).filter(VerificationLog.verification_status.in_(["RED", "BLACK"]))))
@app.get("/api/admin/verification-logs")
def logs(u=Depends(admin), s=Depends(db)):
    return [dict(notice_id=l.notice_id, status=l.verification_status, at=str(l.verification_timestamp))
            for l in s.query(VerificationLog).order_by(VerificationLog.id.desc()).limit(100)]

@app.get("/api/verify/{notice_id}/original")
def original(notice_id: str, s=Depends(db)):  # the distributed (official) copy is public by design
    n = s.query(Notice).filter_by(notice_id=notice_id).first()
    if not n or n.status == "revoked": raise HTTPException(404, "Official copy not available")
    return FileResponse(n.authenticated_file_path)

@app.get("/api/public/stats")
def public_stats(s=Depends(db)):
    return dict(notices=s.query(func.count(Notice.id)).scalar() or 0, verifications=s.query(func.count(VerificationLog.id)).scalar() or 0,
                flagged=s.query(func.count(VerificationLog.id)).filter(VerificationLog.verification_status == "RED").scalar() or 0)
