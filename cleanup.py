from datetime import datetime
from models import SessionLocal, Session, OTP, Room
from sqlalchemy import delete
def main():
    db = SessionLocal()
    now = datetime.utcnow()
    db.execute(delete(Session).where(Session.expires_at < now))
    db.execute(delete(OTP).where(OTP.expires_at < now))
    db.execute(delete(Room).where(Room.expires_at < now))
    db.commit()
    db.close()
if __name__ == "__main__":
    main()
