from pydantic import BaseModel,EmailStr
from datetime import datetime
from typing import Optional, List


# ---------- INPUT SCHEMAS ----------

class SupplierAccountCreate(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    plant_name:str

class AdminPasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ---------- OUTPUT SCHEMAS ----------

class SupplierOut(BaseModel):
    supplier_id: int
    supplier_name: str
    email: str
    
    class Config:
        from_attributes = True


class ChangeDocOut(BaseModel):
    category: str
    file_path: str

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email:EmailStr
    
class VerifyOtpRequest(BaseModel):
    email:EmailStr
    otp:str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str
    confirm_password:str
    
class SubmissionOut(BaseModel):
    submission_id: int
    month: int
    year: int
    upload_date: Optional[datetime] = None
    file_path: Optional[str] = None
    is_submitted: bool
    man_change: bool
    machine_change: bool
    method_change: bool
    material_change: bool
    plant_op_change: bool
    change_docs: List[ChangeDocOut] = []

    class Config:
        from_attributes = True