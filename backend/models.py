from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    supplier_id = Column(Integer, ForeignKey("supplier.supplier_id"), nullable=True)
    supplier = relationship("Suppliers", back_populates="users")
    password_reset = relationship(
    "PasswordReset",
    back_populates="user",
    uselist=False,
    cascade="all, delete-orphan")
class Suppliers(Base):
    __tablename__ = "supplier"
    supplier_id = Column(Integer, primary_key=True, unique=True)
    supplier_name = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    authorized_person_name = Column(String(255), nullable=False)
    contact_no = Column(String(10), nullable=False, default="0000000000")
    users = relationship("Users", back_populates="supplier")
    submissions = relationship("Submission", back_populates="supplier")

class Submission(Base):
    __tablename__ = "submission"
    submission_id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("supplier.supplier_id"))
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    upload_date = Column(DateTime, nullable=True)
    file_path = Column(String(255), nullable=True)
    is_submitted = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="Pending", nullable=False)
    
    # Standard 4M Change Flags Only
    man_change = Column(Boolean, default=False, nullable=False)
    machine_change = Column(Boolean, default=False, nullable=False)
    method_change = Column(Boolean, default=False, nullable=False)
    material_change = Column(Boolean, default=False, nullable=False)

    supplier = relationship("Suppliers", back_populates="submissions")
    change_docs = relationship("ChangeDocs", back_populates="submission")

    __table_args__ = (UniqueConstraint("supplier_id", "month", "year"),)

class User_Session(Base):
    __tablename__ = "Session"
    session_id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    user = relationship("Users")
    
class ReferenceTemplate(Base):
    __tablename__ = "reference_template"

    template_id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)

class ChangeDocs(Base):
    __tablename__ = "Change_Docs"
    change_doc_id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submission.submission_id"))
    category = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    submission = relationship("Submission", back_populates="change_docs")

class PasswordReset(Base):
    __tablename__='password_reset'
    id= Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    otp = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False)

    user = relationship("Users", back_populates="password_reset")

