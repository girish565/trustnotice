"""API-level tests. Skipped automatically when fastapi/httpx/sqlalchemy aren't installed."""
import os, sys, tempfile; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
pytest.importorskip("fastapi"); pytest.importorskip("httpx"); pytest.importorskip("sqlalchemy"); pytest.importorskip("qrcode")
import numpy as np, cv2, pymupdf as fitz
os.environ.update(DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/t.db", STORAGE_PATH=tempfile.mkdtemp(),
                  JWT_SECRET="test-secret-at-least-32-bytes-long-for-hs256",
                  ADMIN_EMAIL="a@t.edu", ADMIN_PASSWORD="correct-horse-battery")
from fastapi.testclient import TestClient
from app.main import app
import test_watermark as tw

@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client: yield client
def auth(c):
    t = c.post("/api/auth/login", json={"email": "a@t.edu", "password": "correct-horse-battery"}).json()["access_token"]; return {"Authorization": f"Bearer {t}"}
PNG = cv2.imencode(".png", tw.doc())[1].tobytes()
FORM = dict(title="Exams", department="CS", category="exam", issue_date="2026-11-01", expiry_date="2099-01-01")
def make_pdf():
    d = fitz.open(); p = d.new_page(width=612, height=792); p.insert_text((72, 80), "Official examination schedule")
    return d.tobytes()

def test_login_rejects_bad_password(c): assert c.post("/api/auth/login", json={"email": "a@t.edu", "password": "nope"}).status_code == 401
def test_legacy_postgres_url_is_normalized():
    from app.models import normalize_database_url
    assert normalize_database_url("postgres://trust:secret@db.example/trustnotice") == "postgresql://trust:secret@db.example/trustnotice"
    assert normalize_database_url("sqlite:///./trustnotice.db") == "sqlite:///./trustnotice.db"
def test_login_is_rate_limited(c):
    from app.main import _hits
    _hits["testclient"] = []
    try:
        for _ in range(30):
            assert c.post("/api/auth/login", json={"email": "missing@t.edu", "password": "nope"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "missing@t.edu", "password": "nope"}).status_code == 429
    finally:
        _hits["testclient"] = []
def test_admin_routes_require_token(c):
    assert c.get("/api/notices").status_code in (401, 403); assert c.post("/api/notices/X/revoke").status_code in (401, 403)
def test_rejects_non_document_upload(c):
    assert c.post("/api/notices/create", headers=auth(c), data=FORM, files={"file": ("x.png", b"not an image")}).status_code == 415
def test_rejects_invalid_notice_dates(c):
    form = {**FORM, "issue_date": "2026-12-01", "expiry_date": "2026-11-30"}
    r = c.post("/api/notices/create", headers=auth(c), data=form, files={"file": ("n.png", PNG)})
    assert r.status_code == 422 and "Expiry date" in r.json()["detail"]
def test_upload_content_is_detected_independently_of_filename(c):
    r = c.post("/api/notices/create", headers=auth(c), data=FORM, files={"file": ("notice.pdf", PNG)})
    assert r.status_code == 200, r.text
    nid = r.json()["notice_id"]
    dist = c.get(f"/api/notices/{nid}/download", headers=auth(c)).content
    v = c.post("/api/verify/upload", files={"file": ("distributed.pdf", dist)})
    assert v.status_code == 200 and v.json()["status"] == "GREEN"
def test_pdf_issue_and_verify_with_embedded_qr(c):
    r = c.post("/api/notices/create", headers=auth(c), data=FORM, files={"file": ("notice.png", make_pdf())})
    assert r.status_code == 200, r.text
    nid = r.json()["notice_id"]
    dist = c.get(f"/api/notices/{nid}/download", headers=auth(c)).content
    v = c.post("/api/verify/upload", files={"file": ("distributed.png", dist)})
    assert v.status_code == 200 and v.json()["status"] == "GREEN", v.text
def test_notice_description_and_corrected_version(c):
    h = auth(c)
    r = c.post("/api/notices/create", headers=h, data={**FORM, "description": "First issue"},
               files={"file": ("n.png", PNG)})
    assert r.status_code == 200, r.text
    nid = r.json()["notice_id"]
    corrected = {**FORM, "title": "Corrected exams", "description": "Updated schedule"}
    v = c.post(f"/api/notices/{nid}/new-version", headers=h, data=corrected, files={"file": ("n.png", PNG)})
    assert v.status_code == 200 and v.json()["version"] == 2, v.text
    record = c.get(f"/api/notices/{nid}").json()
    assert record["title"] == "Corrected exams" and record["description"] == "Updated schedule"
def test_unknown_notice_qr_is_not_served(c):
    assert c.get("/api/notices/unknown/qr").status_code == 404
def test_issue_verify_revoke_flow(c):
    h = auth(c); r = c.post("/api/notices/create", headers=h, data=FORM, files={"file": ("n.png", PNG)}); assert r.status_code == 200, r.text
    nid = r.json()["notice_id"]; dist = c.get(f"/api/notices/{nid}/download", headers=h).content
    v = c.post("/api/verify/upload", files={"file": ("d.png", dist)}).json(); assert v["status"] == "GREEN" and v["signature_valid"]
    assert c.get(f"/api/verify/{nid}").json()["validity"] == "VALID"
    c.post(f"/api/notices/{nid}/revoke", headers=h); assert c.get(f"/api/verify/{nid}").json()["validity"] == "REVOKED"
def test_unrelated_image_is_unverified_not_fake(c):
    v = c.post("/api/verify/upload", files={"file": ("u.png", PNG)}).json(); assert v["status"] == "BLACK"
def test_cannot_revoke_active_signing_key(c):
    k = [x for x in c.get("/api/admin/keys", headers=auth(c)).json() if x["current"]][0]
    assert c.post(f"/api/admin/keys/{k['key_id']}/revoke", headers=auth(c)).status_code == 409

def create_student(c, student_id, email, department, year, class_name=None):
    response = c.post("/api/admin/students", headers=auth(c), data={
        "name": student_id, "email": email, "password": "secure-student-password",
        "student_id": student_id, "department": department, "academic_year": year,
        "class_name": class_name or f"{department}-{year}",
    })
    assert response.status_code == 201, response.text
    token = c.post("/api/auth/login", json={
        "email": email, "password": "secure-student-password",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def create_emergency(c, **overrides):
    data = {
        "title": "Campus safety notice", "description": "Use the north exit.",
        "category": "other", "priority": "critical", "audience": "department_year",
        "department": "CS", "academic_year": "2026", "issue_date": "2026-11-06",
        "expiry_date": "",
    }
    data.update(overrides)
    response = c.post("/api/admin/emergencies", headers=auth(c), data=data)
    assert response.status_code == 200, response.text
    return response.json()

def test_emergency_audience_inbox_and_private_read_ack(c):
    cs = create_student(c, "CS-E-001", "cs-emergency@t.edu", "CS", "2026")
    other = create_student(c, "BIO-E-001", "bio-emergency@t.edu", "BIO", "2026")
    emergency = create_emergency(c)
    assert emergency["recipient_count"] == 1
    assert c.get("/api/student/notifications", headers=cs).status_code == 200
    assert c.get("/api/admin/dashboard", headers=cs).status_code == 403
    own = [n for n in c.get("/api/student/notifications", headers=cs).json()
           if n["notice_id"] == emergency["notice_id"]][0]
    assert own["read"] is False and own["acknowledged"] is False
    assert not any(n["notice_id"] == emergency["notice_id"]
                   for n in c.get("/api/student/notifications", headers=other).json())
    assert c.post(f"/api/student/notifications/{own['id']}/acknowledge", headers=cs).status_code == 200
    after_ack = [n for n in c.get("/api/student/notifications", headers=cs).json()
                 if n["id"] == own["id"]][0]
    assert after_ack["acknowledged"] is True and after_ack["read"] is False
    assert c.post(f"/api/student/notifications/{own['id']}/read", headers=other).status_code == 404
    assert c.post(f"/api/student/notifications/{own['id']}/read", headers=cs).status_code == 200
    notice = c.get(f"/api/student/emergencies", headers=cs).json()
    assert any(n["notice_id"] == emergency["notice_id"] and n["is_active"] for n in notice)
    assert c.get(f"/api/student/notices/{emergency['notice_id']}/download", headers=cs).status_code == 200
    assert c.get(f"/api/student/notices/{emergency['notice_id']}/download", headers=other).status_code == 404

def test_emergency_revoke_replacement_and_optional_expiry(c):
    student = create_student(c, "EM-E-001", "emergency-replace@t.edu", "CS", "2026")
    create_student(c, "EM-E-002", "emergency-new-audience@t.edu", "BIO", "2026")
    original = create_emergency(c, audience="department", department="CS", academic_year="")
    original_notice = c.get(f"/api/verify/{original['notice_id']}").json()
    assert original_notice["validity"] == "VALID"
    replacement = create_emergency(c, title="Updated safety notice", audience="department",
                                   department="BIO", academic_year="",
                                   replaces_notice_id=original["notice_id"])
    old_status = c.get(f"/api/verify/{original['notice_id']}").json()
    assert old_status["validity"] == "REVOKED"
    assert old_status["replacement_notice_id"] == replacement["notice_id"]
    assert old_status["revocation_reason"]
    assert c.get(f"/api/notices/{original['notice_id']}/qr").status_code == 200
    assert c.get(f"/api/verify/{replacement['notice_id']}").json()["validity"] == "VALID"
    assert c.get(f"/api/student/notices/{replacement['notice_id']}/download", headers=student).status_code == 200
    inbox = c.get("/api/student/notifications", headers=student).json()
    assert any(n["notice_id"] == replacement["notice_id"] and n["kind"] == "notice_replaced" for n in inbox)
    assert c.get("/api/admin/emergency-analytics", headers=auth(c)).status_code == 200

def test_manual_emergency_revocation_records_reason_and_notifies(c):
    student = create_student(c, "EM-E-003", "emergency-revoke@t.edu", "CS", "2026")
    emergency = create_emergency(c, audience="department", department="CS", academic_year="")
    result = c.post(f"/api/notices/{emergency['notice_id']}/revoke",
                    headers=auth(c), data={"reason": "Evacuation order lifted."})
    assert result.status_code == 200
    record = c.get(f"/api/verify/{emergency['notice_id']}").json()
    assert record["validity"] == "REVOKED" and record["revocation_reason"] == "Evacuation order lifted."
    own = c.get("/api/student/notifications", headers=student).json()
    assert any(n["notice_id"] == emergency["notice_id"] and n["kind"] == "notice_revoked" for n in own)
    assert c.get(f"/api/notices/{emergency['notice_id']}/status").json()["verification"] == "RED"

def test_requested_emergency_and_notification_endpoint_aliases(c):
    from app.main import _hits
    _hits["testclient"] = []
    student = create_student(c, "ALIAS-E-001", "emergency-alias@t.edu", "ALIAS", "2026")
    response = c.post("/api/notices/emergency", headers=auth(c), data={
        "title": "Alias test", "description": "Check the east entrance.",
        "category": "weather_emergency", "priority": "critical",
        "audience": "department", "department": "ALIAS", "academic_year": "",
        "issue_date": "2026-11-06", "expiry_date": "",
    })
    assert response.status_code == 200, response.text
    notice_id = response.json()["notice_id"]
    inbox = c.get("/api/notifications", headers=student)
    assert inbox.status_code == 200
    item = next(row for row in inbox.json() if row["notice_id"] == notice_id)
    assert item["priority"] == "critical" and item["delivered_at"] and not item["read"]
    assert c.get("/api/notifications/unread-count", headers=student).json()["unread_count"] == 1
    assert c.patch(f"/api/notifications/{item['id']}/read", headers=student).status_code == 200
    assert c.get("/api/notifications/unread-count", headers=student).json()["unread_count"] == 0
    assert c.patch("/api/notifications/read-all", headers=student).status_code == 200
    assert c.post(f"/api/notifications/{item['id']}/acknowledge", headers=student).status_code == 200
    analytics = c.get("/api/admin/notifications/analytics", headers=auth(c))
    assert analytics.status_code == 200
    assert analytics.json()["students_targeted"] >= 1
    assert analytics.json()["delivered"] >= 1 and analytics.json()["failed_deliveries"] == 0

def test_emergency_validates_audience_and_attachment(c):
    from app.main import _hits
    _hits["testclient"] = []
    base = {
        "title": "Safety", "description": "Use the north exit.", "category": "other",
        "priority": "critical", "audience": "department", "department": "",
        "academic_year": "", "issue_date": "2026-11-06", "expiry_date": "",
    }
    bad_scope = c.post("/api/admin/emergencies", headers=auth(c), data=base)
    assert bad_scope.status_code == 422 and "Department is required" in bad_scope.json()["detail"]
    bad_attachment = c.post("/api/admin/emergencies", headers=auth(c),
                            data={**base, "department": "CS"},
                            files={"attachment": ("bad.png", b"not an image")})
    assert bad_attachment.status_code == 415

def test_class_and_selected_audiences_target_only_student_accounts(c):
    class_a = create_student(c, "CLASS-A-001", "class-a1@t.edu", "CS", "2026", "CS-2026-A")
    classmate = create_student(c, "CLASS-A-002", "class-a2@t.edu", "BIO", "2025", "CS-2026-A")
    other_class = create_student(c, "CLASS-B-001", "class-b1@t.edu", "CS", "2026", "CS-2026-B")
    students = c.get("/api/admin/students", headers=auth(c)).json()
    ids_by_email = {item["email"]: item["id"] for item in students}

    class_notice = c.post("/api/admin/emergencies", headers=auth(c), data={
        "title": "Cohort alert", "description": "Class-only instructions.",
        "category": "fee_deadline", "priority": "high", "audience": "class",
        "class_name": "CS-2026-A", "issue_date": "2026-11-06", "expiry_date": "",
    })
    assert class_notice.status_code == 200, class_notice.text
    assert class_notice.json()["recipient_count"] == 2
    class_id = class_notice.json()["notice_id"]
    assert any(n["notice_id"] == class_id for n in c.get("/api/student/notifications", headers=class_a).json())
    assert any(n["notice_id"] == class_id for n in c.get("/api/student/notifications", headers=classmate).json())
    assert not any(n["notice_id"] == class_id for n in c.get("/api/student/notifications", headers=other_class).json())

    selected_ids = [ids_by_email["class-b1@t.edu"], ids_by_email["class-a2@t.edu"]]
    selected_notice = c.post("/api/admin/emergencies", headers=auth(c), data={
        "title": "Selected recipients", "description": "Only selected students.",
        "category": "weather_emergency", "priority": "normal", "audience": "selected",
        "issue_date": "2026-11-06", "expiry_date": "",
        "selected_student_ids": [str(student_id) for student_id in selected_ids],
    })
    assert selected_notice.status_code == 200, selected_notice.text
    assert selected_notice.json()["recipient_count"] == 2
    selected_id = selected_notice.json()["notice_id"]
    assert any(n["notice_id"] == selected_id for n in c.get("/api/student/notifications", headers=classmate).json())
    assert any(n["notice_id"] == selected_id for n in c.get("/api/student/notifications", headers=other_class).json())
    assert not any(n["notice_id"] == selected_id for n in c.get("/api/student/notifications", headers=class_a).json())

def test_class_selected_and_category_validation_reject_invalid_targets(c):
    from app.main import _hits, Session, User
    _hits["testclient"] = []
    create_student(c, "VALIDATE-001", "audience-validation@t.edu", "CS", "2026", "CS-1")
    with Session() as session:
        admin_id = session.query(User).filter_by(role="admin").first().id
    student_id = next(item["id"] for item in c.get("/api/admin/students", headers=auth(c)).json()
                      if item["email"] == "audience-validation@t.edu")
    base = {
        "title": "Validation alert", "description": "Instructions.", "category": "other",
        "priority": "high", "issue_date": "2026-11-06", "expiry_date": "",
    }
    no_class = c.post("/api/admin/emergencies", headers=auth(c),
                      data={**base, "audience": "class"})
    assert no_class.status_code == 422 and "Class/cohort is required" in no_class.json()["detail"]
    empty_selection = c.post("/api/admin/emergencies", headers=auth(c),
                             data={**base, "audience": "selected"})
    assert empty_selection.status_code == 422 and "Select at least one student" in empty_selection.json()["detail"]
    forged_user = c.post("/api/admin/emergencies", headers=auth(c), data={
        **base, "audience": "selected", "selected_student_ids": [str(admin_id)],
    })
    assert forged_user.status_code == 422 and "Every selected ID" in forged_user.json()["detail"]
    mixed_invalid = c.post("/api/admin/emergencies", headers=auth(c), data={
        **base, "audience": "selected",
        "selected_student_ids": [str(student_id), str(admin_id)],
    })
    assert mixed_invalid.status_code == 422 and "Every selected ID" in mixed_invalid.json()["detail"]
    invalid_category = c.post("/api/admin/emergencies", headers=auth(c), data={
        **base, "audience": "class", "class_name": "CS-1", "category": "unlisted-free-text",
    })
    assert invalid_category.status_code == 422 and "Category must be one of" in invalid_category.json()["detail"]

def test_emergency_attachment_is_embedded_in_signed_download(c):
    from app.main import _hits
    _hits["testclient"] = []
    student = create_student(c, "ATT-E-001", "emergency-attachment@t.edu", "ATT", "2026")
    response = c.post("/api/admin/emergencies", headers=auth(c), data={
        "title": "Attachment alert", "description": "Review the attached map.",
        "category": "other", "priority": "high", "audience": "department",
        "department": "ATT", "academic_year": "", "issue_date": "2026-11-06",
        "expiry_date": "",
    }, files={"attachment": ("map.png", PNG)})
    assert response.status_code == 200, response.text
    notice = response.json()
    signed = c.get(f"/api/student/notices/{notice['notice_id']}/download", headers=student)
    assert signed.status_code == 200 and signed.content.startswith(b"%PDF-")
    verification = c.post("/api/verify/upload", files={"file": ("signed.pdf", signed.content)})
    assert verification.status_code == 200 and verification.json()["status"] == "GREEN"
    assert c.get("/api/student/emergencies", headers=student).json()[0]["has_attachment"] is True

def test_student_websocket_uses_private_single_use_ticket(c):
    from starlette.websockets import WebSocketDisconnect
    from app.main import _hits
    _hits["testclient"] = []
    student = create_student(c, "WS-E-001", "emergency-ws@t.edu", "WS", "2026")
    emergency = create_emergency(c, audience="department", department="WS", academic_year="")
    ticket_response = c.post("/api/notifications/socket-ticket", headers=student)
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["ticket"]
    with c.websocket_connect(f"/api/notifications/ws?ticket={ticket}") as socket:
        message = socket.receive_json()
        assert message["notice_id"] == emergency["notice_id"]
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"/api/notifications/ws?ticket={ticket}"):
            pass
