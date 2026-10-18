from passlib.context import CryptContext
import secrets
from sqlalchemy.orm import Session
from datetime import datetime,timedelta
from models import User_Session,Users
#Password Hashing and Verifier
pwd_context=CryptContext(schemes=['bcrypt'],deprecated='auto')

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain_password,stored_hash):
    return pwd_context.verify(plain_password,stored_hash)

#Creating Sessions 

def generate_session_token():
    return secrets.token_hex(32)

def create_session(user_id: int, db: Session):
    user = db.query(Users).filter(Users.id == user_id).first()

    token = generate_session_token()
    created_at = datetime.utcnow()

    if user.role.lower() == "admin":
        expires_at = created_at + timedelta(minutes=30)
    else:
        expires_at = created_at + timedelta(minutes=120)

    db_session = User_Session(
        session_id=token,
        user_id=user_id,
        created_at=created_at,
        expires_at=expires_at
    )

    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return token

def current_user(session_id: str, db: Session):
    session = db.query(User_Session).filter(   
        User_Session.session_id == session_id  
    ).first()                                  

    if session is None:
        return None

    if datetime.utcnow() > session.expires_at:  
        db.delete(session)                      
        db.commit()                             
        return None                             

    user = db.query(Users).filter(
        Users.id == session.user_id
    ).first()

    if user is None:
        return None

    # Refresh session timeout
    now = datetime.utcnow()

    if user.role.lower() == "admin":
        session.expires_at = now + timedelta(minutes=30)
    else:
        session.expires_at = now + timedelta(hours=24)

    db.commit()

    return user

def destroy_session(session_id:str,db:Session):
    session=db.query(User_Session).filter(User_Session.session_id==session_id).first()
    if session is None:
        return None
    db.delete(session)
    db.commit()
