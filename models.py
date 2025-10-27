from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DB_URL = "sqlite:///app.db"
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

def now():
    return datetime.utcnow()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(64), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, default=lambda: now() + timedelta(days=10))
    user = relationship("User")

class OTP(Base):
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), index=True, nullable=False)
    code = Column(String(10), nullable=False)
    purpose = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, default=lambda: now() + timedelta(minutes=10))
    __table_args__ = (UniqueConstraint("email", "code", "purpose", name="uq_email_code"),)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, index=True, nullable=False)
    owner = Column(String(64), nullable=False)
    date_iso = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, default=lambda: now() + timedelta(days=10))

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    name = Column(String(128), nullable=False)
    unit = Column(String(32), default="adet")
    amount = Column(String(32), default="1")
    cat = Column(String(64), default="Diğer")
    who = Column(String(64), default="")
    state = Column(String(16), default="needed")
    created_at = Column(DateTime, default=now)

def init_db():
    Base.metadata.create_all(bind=engine)
