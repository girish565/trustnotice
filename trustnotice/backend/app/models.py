import os, datetime as dt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
Base = declarative_base()

def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url

engine = create_engine(normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./trustnotice.db")))
Session = sessionmaker(bind=engine)
now = lambda: dt.datetime.now(dt.timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True); name = Column(String); email = Column(String, unique=True, index=True)
    password_hash = Column(String); role = Column(String, default="admin"); created_at = Column(DateTime, default=now)
    department = Column(String, nullable=True); academic_year = Column(String, nullable=True)
    student_id = Column(String, unique=True, nullable=True); class_name = Column(String, nullable=True)
class Institution(Base):
    __tablename__ = "institutions"
    id = Column(Integer, primary_key=True); institution_name = Column(String); institution_code = Column(String, unique=True)
    public_key = Column(String); created_at = Column(DateTime, default=now)
class SigningKey(Base):
    __tablename__ = "signing_keys"
    id = Column(Integer, primary_key=True); institution_id = Column(Integer, ForeignKey("institutions.id"))
    key_id = Column(String, unique=True, index=True); public_key = Column(String); status = Column(String, default="active")
    created_at = Column(DateTime, default=now); revoked_at = Column(DateTime, nullable=True)
class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True); notice_id = Column(String, unique=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id")); title = Column(String); department = Column(String)
    category = Column(String); issue_date = Column(String); expiry_date = Column(String); description = Column(Text, default="")
    original_file_path = Column(String); authenticated_file_path = Column(String); sha256_hash = Column(String, index=True)
    signature = Column(Text); manifest = Column(Text); text = Column(Text, default=""); key_id = Column(String)
    version = Column(Integer, default=1); status = Column(String, default="active"); created_at = Column(DateTime, default=now)
    priority = Column(String, default="normal"); audience = Column(String, default="all")
    academic_year = Column(String, nullable=True); is_emergency = Column(Boolean, default=False)
    has_attachment = Column(Boolean, default=False)
    attachment_path = Column(String, nullable=True); revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(Text, nullable=True); replacement_notice_id = Column(String, nullable=True)
    replaces_notice_id = Column(String, nullable=True)
class VerificationLog(Base):
    __tablename__ = "verification_logs"
    id = Column(Integer, primary_key=True); notice_id = Column(String, index=True); uploaded_file_hash = Column(String)
    verification_status = Column(String); watermark_detected = Column(Boolean); signature_valid = Column(Boolean)
    similarity_score = Column(Float, nullable=True); tampering_detected = Column(Boolean)
    verification_timestamp = Column(DateTime, default=now)
class NoticeVersion(Base):
    __tablename__ = "notice_versions"
    id = Column(Integer, primary_key=True); notice_id = Column(String, index=True); version_number = Column(Integer)
    previous_version_id = Column(Integer, nullable=True); content_hash = Column(String); signature = Column(Text)
    created_at = Column(DateTime, default=now)
class AuditLog(Base):  # append-only: app never updates/deletes
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True); actor = Column(String); action = Column(String); target = Column(String)
    at = Column(DateTime, default=now); details = Column(Text, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True); kind = Column(String, index=True)
    title = Column(String); message = Column(Text); notice_id = Column(String, index=True)
    priority = Column(String, default="normal"); created_at = Column(DateTime, default=now)

class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    id = Column(Integer, primary_key=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    delivered_at = Column(DateTime, default=now)
    read_at = Column(DateTime, nullable=True); acknowledged_at = Column(DateTime, nullable=True)

class WebSocketTicket(Base):
    __tablename__ = "websocket_tickets"
    id = Column(Integer, primary_key=True); token_hash = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    expires_at = Column(DateTime); used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
