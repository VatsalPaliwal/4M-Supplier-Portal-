# FastAPI core
from fastapi import FastAPI, Request, Response, Form, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, FileResponse,StreamingResponse,JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import RequestValidationError
# Database
from sqlalchemy.orm import Session
from database import get_db, Base, engine
from sqlalchemy.orm import joinedload

# Models
from models import Users, Suppliers, Submission, ChangeDocs,ReferenceTemplate,PasswordReset

# Schemas
from schemas import SupplierAccountCreate,ForgotPasswordRequest,VerifyOtpRequest,ResetPasswordRequest

# Auth helpers (your auth.py functions)
from auth import hash_password, verify_password, create_session, current_user, destroy_session

# Standard library
from datetime import datetime,timedelta
import os
import uuid
import shutil
from io import BytesIO
from pathlib import Path
import secrets
import traceback

# Sending Email

import smtplib
from smtplib import SMTPException
from email.message import EmailMessage

# Excel export
import pandas as pd
from openpyxl import Workbook
app=FastAPI()

Base.metadata.create_all(bind=engine)
BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(
    directory=BASE_DIR / "frontend" / "templates"
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend" / "static"),
    name="static"
)
def send_email(
    recipients: str,
    subject: str,
    body: str
):
    email = EmailMessage()
    email['From'] = 'vatsalpaliwal654@gmail.com'
    email['To'] = recipients
    email['Subject'] = subject
    email.set_content(body)
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(
            "vatsalpaliwal654@gmail.com",
            "xqal pmry iahv sjdo"
        )
        server.send_message(email)
    except SMTPException as e:
        # Catch invalid recipient errors (like 550 user unknown) or connection issues
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to send email. Please check if the email address is valid. Error: {str(e)}"
        )
    finally:
        try:
            server.quit()
        except:
            pass
        
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    titles = {401: "Unauthorized", 403: "Forbidden", 404: "Not Found"}
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "title": titles.get(exc.status_code, "Error"), "detail": exc.detail},
        status_code=exc.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 422,
            "title": "Invalid Input",
            "detail": "Please check the form and try again.",
        },
        status_code=422,
    )

@app.exception_handler(Exception)
async def internal_server_error_handler(request: Request, exc: Exception):
    # Check if the request expects JSON (like fetch requests from frontend)
    if "application/json" in request.headers.get("accept", "") or request.url.path in ["/forgot-password", "/login", "/verify-admin-otp", "/verify-otp", "/reset-password"]:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal Server Error: {str(exc)}"}
        )
        
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 500,
            "title": "Internal Server Error",
            "detail": "Something went wrong on the server.",
        },
        status_code=500,
    )
# Folder where uploaded PDFs get saved
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CATEGORY_LABELS = {
    "man_change": "Man Change",
    "machine_change": "Machine Change",
    "method_change": "Method Change",
    "material_change": "Material Change",
}

#Authentication

@app.get("/")
def login_page(request: Request,db: Session=Depends(get_db)):
    session_id=request.cookies.get("session_id")
    user=current_user(session_id,db)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request}
        )
    else:
        if user.role.lower() == "admin":
            return RedirectResponse(
                url="/admin/dashboard",
                status_code=303
            )
        elif user.role == "Supplier":
            return RedirectResponse(
                url="/supplier/upload",
                status_code=303
            )

@app.post("/login")
def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find user by email
    user = db.query(Users).filter(Users.email == email).first()

    # Email not found
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid email "
            }
        )

    # Verify password
    if not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Wrong password"
            }
        )
    session_id = create_session(user.id, db)
    role=user.role
    if role.capitalize()=="Supplier":
        session_id = create_session(user.id, db)
        response = RedirectResponse(url="/supplier/upload", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response

    elif role.lower()=="admin":
        otp=str(secrets.randbelow(900000) + 100000)
        now=datetime.utcnow()
        reset=db.query(PasswordReset).filter(PasswordReset.user_id==user.id).first()
        if reset is None:
            reset=PasswordReset(user_id=user.id,
                                otp=otp,
                                expires_at=now +timedelta(minutes=10),
                                used=False,
                                created_at=now)
            db.add(reset)
        else:
            reset.otp=otp
            reset.expires_at=now+timedelta(minutes=10)
            reset.used=False
            reset.created_at=now
        db.commit()
        subject = "4M Supplier Portal - Admin Login OTP"

        body = f"""
            Hello,
            
            A login attempt was made to your Admin account.
            
            Your login OTP is: {otp}
            
            This OTP is valid for 10 minutes.
            
            If this wasn't you, please ignore this email.
            
            Regards,
            4M Supplier Portal
            """
        try:
            send_email(
                recipients=user.email,
                subject=subject,
                body=body
            )

            return {"requires_2fa": True,"message": "OTP sent successfully."}                  

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account role is not configured correctly. Contact your administrator."}
        )
    
@app.post("/verify-admin-otp")
def verify_admin_otp(request:VerifyOtpRequest,response:Response,db:Session=Depends(get_db)):
    user=db.query(Users).filter(Users.email==request.email).first()
    if user is None:
        raise HTTPException(status_code=404,detail="No such Email found")

    reset = db.query(PasswordReset).filter(PasswordReset.user_id == user.id).first()
    if reset is None:
        raise HTTPException(
            status_code=404,
            detail="No OTP request found"
        )
    if reset.used:
        raise HTTPException(status_code=400,detail="Otp has already been used for verification")
    if reset.otp!=request.otp:
        raise HTTPException(status_code=400,detail="Invalid Otp")
    if datetime.utcnow()>reset.expires_at:
        raise HTTPException(status_code=400,detail="Otp has Expired")
    reset.used=True
    db.delete(reset)
    session_id = create_session(user.id, db)
    db.commit()
    response.set_cookie(key="session_id", value=session_id, httponly=True)
    return {"message": "OTP verified successfully."}

@app.post("/refresh-session")
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No active session found")
    
    # This automatically validates the session, deletes it if expired, 
    # OR extends its expires_at timestamp in the database if valid!
    user = current_user(session_id, db)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # Set the cookie expiration duration to match your user role timeout
    timeout_minutes = 30 if user.role.lower() == "admin" else 120
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=timeout_minutes * 60
    )

    return {"status": "success", "message": "Session extended"}

@app.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    if session_id:
        destroy_session(session_id, db)
        
    response = JSONResponse(content={"status": "success", "message": "Logged out successfully"})
    response.delete_cookie("session_id")
    return response

# Reset Password    
@app.get("/forgot-password")
def forgot_password_page(request: Request):
    try:
        return templates.TemplateResponse("forgot-password.html", {"request": request})
    except Exception as e:
        # This will forcefully print the entire stack trace to your terminal
        print("--- FORCED TRACEBACK START ---")
        traceback.print_exc()
        print("--- FORCED TRACEBACK END ---")
        raise e
    
@app.post("/forgot-password")
def request_otp(request:ForgotPasswordRequest,db:Session=Depends(get_db)):
    user=db.query(Users).filter(Users.email==request.email).first()
    now=datetime.utcnow()
    if user is None:
        raise HTTPException(status_code=404,detail="No such email")
    otp=str(secrets.randbelow(900000) + 100000)
    reset=db.query(PasswordReset).filter(PasswordReset.user_id==user.id).first()
    if reset is None:
        reset=PasswordReset(user_id=user.id,
                            otp=otp,
                            expires_at=now +timedelta(minutes=10),
                            used=False,
                            created_at=now)
        db.add(reset)
    else:
        reset.otp=otp
        reset.expires_at=now+timedelta(minutes=10)
        reset.used=False
        reset.created_at=now
    db.commit()
    subject = "4M Supplier Portal - Password Reset OTP"

    body = f"""
    Hello,

    You requested a password reset for your 4M Supplier Portal account.

    Your OTP is: {otp}

    This OTP is valid for 10 minutes.

    If you did not request a password reset, please ignore this email.

    Regards,
    4M Supplier Portal
    """
    try:
        send_email(
            recipients=user.email,
            subject=subject,
            body=body
        )

        return {"message": "OTP sent successfully."}                    
                                                           
    except Exception as e:
        print("--- FORCED TRACEBACK START ---")
        traceback.print_exc()
        print("--- FORCED TRACEBACK END ---")
        
        raise HTTPException(
            status_code=400,
            detail=f"Failed to send OTP email: {str(e)}"
        )

@app.post("/verify-otp")
def verify_otp(request:VerifyOtpRequest,db:Session=Depends(get_db)):
    user=db.query(Users).filter(Users.email==request.email).first()
    if user is None:
        raise HTTPException(status_code=404,detail="No such Email found")

    reset = db.query(PasswordReset).filter(PasswordReset.user_id == user.id).first()
    if reset is None:
        raise HTTPException(
            status_code=404,
            detail="No OTP request found"
        )
    if reset.used:
        raise HTTPException(status_code=400,detail="Otp has already been used for verification")
    if reset.otp!=request.otp:
        raise HTTPException(status_code=400,detail="Invalid Otp")
    if datetime.utcnow()>reset.expires_at:
        raise HTTPException(status_code=400,detail="Otp has Expired")
    reset.used=True
    db.commit()
    return {'message':"OTP Verified Successfully"}

@app.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user=db.query(Users).filter(Users.email==request.email).first()
    if user is None:
        raise HTTPException(status_code=404,detail="No such Email found")
    
    if request.new_password!=request.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords Do not match"
        )
    reset = db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id
    ).first() 

    if reset is None:
        raise HTTPException(
            status_code=404,
            detail="No password reset request found."
        )
    if not reset.used:
        raise HTTPException(
            status_code=400,
            detail="OTP has not been verified."
        )
    hashed_password = hash_password(request.new_password)
    user.password_hash = hashed_password
    db.delete(reset)
    db.commit()
    return {"message":"Password Changed Succesfully"}

#Supplier 

#Supplier Upload
@app.get("/supplier/upload")
def supplier_upload_page(
    request: Request,
    db: Session = Depends(get_db)):

    session_id=request.cookies.get("session_id")
    user=current_user(session_id,db)
    if user is None:
         return RedirectResponse(url="/")
    current_year = datetime.utcnow().year
    years = list(range(current_year - 1, current_year + 2))
    return templates.TemplateResponse(
    "supplier_upload.html",
    {
        "request": request,
        "supplier": user.supplier,
        "years": years,
        "Authorized Person Name":user.supplier.authorized_person_name
    }
    )

@app.post("/supplier/upload")
def upload(
    request: Request,
    month: int = Form(...),
    year: int = Form(...),
    man_change: str = Form(...),
    machine_change: str = Form(...),
    method_change: str = Form(...),
    material_change: str = Form(...),
    action: str = Form("upload"),  # Explicitly catches "draft" or "upload"
    main_pdf: UploadFile | None = File(None),
    man_change_pdf: UploadFile | None = File(None),
    machine_change_pdf: UploadFile | None = File(None),
    method_change_pdf: UploadFile | None = File(None),
    material_change_pdf: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    user = current_user(session_id, db)
    if user is None:
         return RedirectResponse(url="/", status_code=303)

    # STRICT VALIDATION: Only enforce required documents if action is final "upload"
    if action == "upload":
        if not main_pdf or not main_pdf.filename:
            return templates.TemplateResponse("supplier_upload.html", {"request": request, "supplier": user.supplier, "error": "Main document is required for final submission."})
        if man_change == "Yes" and (not man_change_pdf or not man_change_pdf.filename):
            return templates.TemplateResponse("supplier_upload.html", {"request": request, "supplier": user.supplier, "error": "Man change document is required."})
        if machine_change == "Yes" and (not machine_change_pdf or not machine_change_pdf.filename):
            return templates.TemplateResponse("supplier_upload.html", {"request": request, "supplier": user.supplier, "error": "Machine change document is required."})
        if method_change == "Yes" and (not method_change_pdf or not method_change_pdf.filename):
            return templates.TemplateResponse("supplier_upload.html", {"request": request, "supplier": user.supplier, "error": "Method change document is required."})
        if material_change == "Yes" and (not material_change_pdf or not material_change_pdf.filename):
            return templates.TemplateResponse("supplier_upload.html", {"request": request, "supplier": user.supplier, "error": "Material change document is required."})

    # Check if a submission already exists for this month/year
    submission = db.query(Submission).filter(
        Submission.supplier_id == user.supplier_id,
        Submission.month == month,
        Submission.year == year
    ).first()

    # Handle main file path safely (retain old path if updating a draft without a new file)
    main_file_path = submission.file_path if submission else ""
    if main_pdf and main_pdf.filename:
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}_{main_pdf.filename}"
        main_file_path = os.path.join(UPLOAD_DIR, unique_filename)
        with open(main_file_path, "wb") as buffer:
             shutil.copyfileobj(main_pdf.file, buffer)

    # CRITICAL: Set submission flags based on whether it's a draft or final upload
    is_submitted_flag = True if action == "upload" else False
    status_value = "Pending" if action == "upload" else "Draft"

    if submission is None:
        submission = Submission(
            supplier_id=user.supplier_id,
            month=month,
            year=year,
            upload_date=datetime.utcnow(),
            file_path=main_file_path,
            is_submitted=is_submitted_flag,
            status=status_value,
            man_change=(man_change == "Yes"),
            machine_change=(machine_change == "Yes"),
            method_change=(method_change == "Yes"),
            material_change=(material_change == "Yes"),
        )
        db.add(submission)
        db.flush()
    else:
        submission.upload_date = datetime.utcnow()
        if main_pdf and main_pdf.filename:
            submission.file_path = main_file_path
        submission.is_submitted = is_submitted_flag
        submission.status = status_value
        submission.man_change = (man_change == "Yes")
        submission.machine_change = (machine_change == "Yes")
        submission.method_change = (method_change == "Yes")
        submission.material_change = (material_change == "Yes")

    # Handle Change Documents safely for both drafts and uploads
    changes = [
        (man_change, man_change_pdf, "Man Change"),
        (machine_change, machine_change_pdf, "Machine Change"),
        (method_change, method_change_pdf, "Method Change"),
        (material_change, material_change_pdf, "Material Change"),
    ]
    
    for change, pdf, category in changes:
        if change == "Yes" and pdf is not None and pdf.filename:
            existing_doc = db.query(ChangeDocs).filter(
                ChangeDocs.submission_id == submission.submission_id,
                ChangeDocs.category == category
            ).first()

            uid = str(uuid.uuid4())
            fname = f"{uid}_{pdf.filename}"
            fpath = os.path.join(UPLOAD_DIR, fname)
            with open(fpath, "wb") as buffer:
                shutil.copyfileobj(pdf.file, buffer)

            if existing_doc:
                existing_doc.file_path = fpath
            else:
                change_doc = ChangeDocs(
                    submission_id=submission.submission_id,
                    category=category,
                    file_path=fpath
                )
                db.add(change_doc)
            
    db.commit()
    return RedirectResponse(url="/supplier/history", status_code=303)

#See Historical Data

@app.get("/supplier/history")
def history(
    request: Request,
    month: str | None = None,
    year: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    user = current_user(session_id, db)
    if user is None:
         return RedirectResponse(url="/", status_code=303)

    query = db.query(Submission).filter(Submission.supplier_id == user.supplier_id)

    # Safely validate and cast filters
    if year and year.isdigit():
        query = query.filter(Submission.year == int(year))
    if month and month.isdigit():
        query = query.filter(Submission.month == int(month))
    if status and status != "":
        query = query.filter(Submission.status == status)

    history_records = query.all()

    years_query = (
        db.query(Submission.year)
        .filter(Submission.supplier_id == user.supplier_id)
        .distinct()
        .order_by(Submission.year.desc())
        .all()
    )
    years = [y[0] for y in years_query if y[0] is not None]

    months_query = (
        db.query(Submission.month)
        .filter(Submission.supplier_id == user.supplier_id)
        .distinct()
        .order_by(Submission.month)
        .all()
    )
    months = [m[0] for m in months_query if m[0] is not None]

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": history_records,
        "years": years,
        "months": months,
        "month_names": month_names,
    })

#Download 

@app.get("/supplier/submission/{submission_id}/download")
def supplierdownload_submission(request:Request,submission_id:int,db: Session=Depends(get_db)):
    session_id=request.cookies.get("session_id")
    user=current_user(session_id,db)
    if user is None:
         return RedirectResponse(url="/",status_code=303)
    submission = (
    db.query(Submission)
    .filter(Submission.submission_id == submission_id)
    .first())
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.supplier_id != user.supplier_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(submission.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    return FileResponse(
        path=submission.file_path,
        media_type="application/pdf",
        filename=os.path.basename(submission.file_path)
    )

# Change Category Download 
@app.get("/supplier/submission/{submission_id}/attachment/{category}")
def supplier_download_attachment(request:Request,submission_id:int,category:str,db:Session=Depends(get_db)):
    session_id=request.cookies.get("session_id")
    user=current_user(session_id,db)
    if user is None:
         return RedirectResponse(url="/",status_code=303)
    submission = (
    db.query(Submission)
    .filter(Submission.submission_id == submission_id)
    .first())
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission.supplier_id != user.supplier_id:
        raise HTTPException(status_code=403, detail="Access denied")
    change_doc = (
    db.query(ChangeDocs)
    .filter(
        ChangeDocs.submission_id == submission_id,
        ChangeDocs.category == category
    )
    .first())
    if change_doc is None:
        raise HTTPException(status_code=404,detail="Attachment not found")
    if not os.path.exists(submission.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    return FileResponse(
    path=change_doc.file_path,
    media_type="application/pdf",
    filename=os.path.basename(change_doc.file_path))

# --- Supplier Route: Download Template (Serves file directly from path) ---
@app.get("/supplier/download-template")
async def supplier_download_template(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    user = current_user(session_id, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    template_record = db.query(ReferenceTemplate).first()                                                           
    if not template_record or not os.path.exists(template_record.file_path):                                        
        raise HTTPException(status_code=404, detail="Format reference template has not been uploaded by admin yet.")

    # FileResponse handles streaming files from disk natively and efficiently
    return FileResponse(
        path=template_record.file_path,
        filename=template_record.filename
    )

#Change Password

@app.get("/supplier/change-password")
def change_password_page(
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    user = current_user(session_id, db)

    if user is None:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request
        }
    )

@app.post("/supplier/change-password")
def change_password(request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)):
    session_id=request.cookies.get("session_id")
    user=current_user(session_id,db)
    if not verify_password(current_password, user.password_hash) :
                return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "error": "Wrong password"
            }
        )
    new_hash=hash_password(new_password)
    user.password_hash=new_hash
    db.commit()
    return RedirectResponse(
    url="/supplier/upload",
    status_code=303)

# Admin

@app.get("/admin/dashboard")
def admin_dashboard(
    request: Request,
    supplier: str = "All",
    year: str = "All",
    month: str = "All",
    status: str = "All",
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)
    if admin.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")

    suppliers = db.query(Suppliers).order_by(Suppliers.supplier_name).all()

    # Properly unpack row tuples into plain values
    years_query = db.query(Submission.year).distinct().order_by(Submission.year.desc()).all()
    years = [y[0] for y in years_query if y[0] is not None]

    months_query = db.query(Submission.month).distinct().order_by(Submission.month).all()
    months = [m[0] for m in months_query if m[0] is not None]

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    query = db.query(Submission).options(joinedload(Submission.supplier))

    # Safe parsing for supplier filter
    if supplier and supplier != "All" and supplier.isdigit():
        query = query.filter(Submission.supplier_id == int(supplier))

    # Safe parsing for year filter
    if year and year != "All" and year.isdigit():
        query = query.filter(Submission.year == int(year))

    # Safe parsing for month filter
    if month and month != "All" and month.isdigit():
        query = query.filter(Submission.month == int(month))

    # Safe parsing for status filter
    if status and status != "All":
        query = query.filter(Submission.status == status)

    query = query.order_by(Submission.year.desc(), Submission.month.desc(), Submission.upload_date.desc())
    submissions = query.all()

    return templates.TemplateResponse(
        "admin-dashboard.html",
        {
            "request": request,
            "admin": admin,
            "suppliers": suppliers,
            "submissions": submissions,
            "years": years,
            "months": months,
            "month_names": month_names,
            "selected_supplier": supplier,
            "selected_year": year,
            "selected_month": month,
            "selected_status": status,
        }
    )

@app.post("/admin/upload-template")
async def admin_upload_template(
    request: Request,
    template_file: UploadFile = File(...),  # <-- Changed from 'file' to 'template_file'
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)
    if admin is None or admin.role.lower() != "admin":
        return RedirectResponse(url="/", status_code=303)

    # Validate file extension to ensure it is an Excel file
    if not template_file.filename or not template_file.filename.lower().endswith(('.xlsx', '.xls')):
        return RedirectResponse(url="/admin/dashboard?error=invalid_template_format", status_code=303)

    # Save file to your existing UPLOAD_DIR
    unique_id = str(uuid.uuid4())
    unique_filename = f"{unique_id}_{template_file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(template_file.file, buffer)

    # Keep a single master template record (overwrite/update if one already exists)
    template_record = db.query(ReferenceTemplate).first()
    if template_record:
        if os.path.exists(template_record.file_path):
            os.remove(template_record.file_path)
            
        template_record.filename = template_file.filename
        template_record.file_path = file_path
    else:
        template_record = ReferenceTemplate(
            filename=template_file.filename,
            file_path=file_path
        )
        db.add(template_record)
    
    db.commit()
    return RedirectResponse(url="/admin/dashboard?success=template_updated", status_code=303)

# Admin Reset Password

@app.get("/admin/reset-password/{user_id}")
def reset_password_page(user_id,request:Request,db: Session=Depends(get_db)):
    session_id=request.cookies.get('session_id')
    admin=current_user(session_id,db)
    if admin is None:
         return RedirectResponse(url="/",status_code=303)
    if admin.role.lower()!="admin":
         raise HTTPException(status_code=403,detail="Only administrators can access this page.")
    user=db.query(Users).filter(Users.id==user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse(
    "admin-reset-password.html",
    {
        "request": request
    })
                                                                                                            
@app.post("/admin/reset-password/{user_id}")
def reset_password(user_id:int,request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)
    if admin.role.lower()!="admin":
         raise HTTPException(status_code=403,detail="Only administrators can access this page.")
    user=db.query(Users).filter(Users.id==user_id).first()
    if user is None:
        raise HTTPException(status_code=404,detail="No such User exists")
    new_hash=hash_password(new_password)
    user.password_hash=new_hash
    db.commit()
    return RedirectResponse(
    url="/admin/dashboard",
    status_code=303)


# Admin Add Supplier

@app.get("/admin/create-supplier")
def create_supplier_page(request: Request,db: Session=Depends(get_db)):
    session_id=request.cookies.get('session_id')
    admin=current_user(session_id,db)
    if admin is None:
         return RedirectResponse(url="/",status_code=303)
    if admin.role.lower()!="admin":
         raise HTTPException(status_code=403,detail="Only administrators can access this page.")
    return templates.TemplateResponse(
    "admin-create-supplier.html",
    {
        "request": request
    })
    
@app.post("/admin/create-supplier")
def create_supplier(
    request: Request,
    company_name: str = Form(...),
    email: str = Form(...),
    auth_name:str=Form(...),
    password: str = Form(...),
    contact_no:str=Form(...),
    db: Session = Depends(get_db)):
    try:
        session_id=request.cookies.get("session_id")
        admin=current_user(session_id,db)
        if admin.role.lower()!="admin":
            raise HTTPException(status_code=403,detail="Only admins can create suppliers. ")
        hashed_password = hash_password(password)
        supplier_row = Suppliers(
            supplier_name=company_name,
            email=email,
            authorized_person_name=auth_name,
            contact_no=contact_no
        )

        db.add(supplier_row)
        db.flush()

        user_row = Users(
            email=email,
            password_hash=hashed_password,
            role="Supplier",
            supplier_id=supplier_row.supplier_id
        )

        db.add(user_row)
        db.commit()

        return RedirectResponse(
            url="/admin/dashboard",
            status_code=303
        )
        pass
    except Exception as e:
            print("ERROR:", e)
            raise e
#Edit Supplier
@app.get("/admin/edit-supplier/{supplier_id}")
def edit_supplier_page(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)

    if admin.role.lower()!="admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")

    supplier = (
        db.query(Suppliers)
        .filter(Suppliers.supplier_id == supplier_id)
        .first()
    )

    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return templates.TemplateResponse(
        "admin-edit-supplier.html",
        {
            "request": request,
            "admin": admin,          
            "supplier": supplier,
        }
    )

@app.post("/admin/edit-supplier/{supplier_id}")
def edit_supplier(
    supplier_id: int,
    request: Request,
    supplier_name: str = Form(...),
    email: str = Form(...),
    authorized_person_name: str = Form(...),
    contact_no: str = Form(...),
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)
    if admin.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")

    supplier = db.query(Suppliers).filter(Suppliers.supplier_id == supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if not contact_no.isdigit() or len(contact_no) !=10:
        return templates.TemplateResponse(
            "admin-edit-supplier.html",
            {
                "request": request,
                "admin": admin,
                "supplier": supplier,
                "error": "Phone number must be exactly 10 digits." # Render error gracefully
            },
            status_code=400
        )
    supplier.supplier_name = supplier_name
    supplier.email = email
    supplier.authorized_person_name = authorized_person_name
    supplier.contact_no = contact_no
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

#Delete Supplier

@app.post("/admin/delete-supplier/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)

    if admin.role.lower()!="admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")
    user = (
    db.query(Users)
    .filter(Users.supplier_id == supplier_id)
    .first()
    )
    supplier = (
        db.query(Suppliers)
        .filter(Suppliers.supplier_id == supplier_id)
        .first()
    )
    if user:
        db.delete(user)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.delete(supplier)
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


# Approve Submission

@app.post("/admin/submission/{submission_id}/approve")
def admin_approve_submission(submission_id: int, request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)
    if admin is None or admin.role.lower() != "admin":
        return RedirectResponse(url="/", status_code=303)
        
    submission = db.query(Submission).filter(Submission.submission_id == submission_id).first()
    if submission:
        submission.status = "Approved"
        db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/admin/submission/{submission_id}/reject")
def admin_reject_submission(submission_id: int, request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)
    if admin is None or admin.role.lower() != "admin":
        return RedirectResponse(url="/", status_code=303)
        
    submission = db.query(Submission).filter(Submission.submission_id == submission_id).first()
    if submission:
        submission.status = "Rejected"
        db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)
# Download reports admin

@app.get("/admin/submission/{submission_id}/download")
def admin_download_submission(request:Request,submission_id:int,db: Session=Depends(get_db)):

    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)

    if admin.role.lower()!="admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")
    submission = (
    db.query(Submission)
    .filter(Submission.submission_id == submission_id)
    .first())
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if not os.path.exists(submission.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    return FileResponse(
        path=submission.file_path,
        media_type="application/pdf",
        filename=os.path.basename(submission.file_path)
    )

@app.get("/admin/submission/{submission_id}/attachment/{category}")
def admin_download_attachment(request:Request,submission_id:int,category:str,db:Session=Depends(get_db)):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)

    if admin is None:
        return RedirectResponse(url="/", status_code=303)

    if admin.role.lower()!="admin":
        raise HTTPException(status_code=403, detail="Only administrators can access this page.")
    submission = (
    db.query(Submission)
    .filter(Submission.submission_id == submission_id)
    .first())
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    change_doc = (
    db.query(ChangeDocs)
    .filter(
        ChangeDocs.submission_id == submission_id,
        ChangeDocs.category == category
    )
    .first())
    if change_doc is None:
        raise HTTPException(status_code=404,detail="Attachment not found")
    if not os.path.exists(change_doc.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    return FileResponse(
    path=change_doc.file_path,
    media_type="application/pdf",
    filename=os.path.basename(change_doc.file_path))

@app.get("/admin/export-excel")
def export_excel(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    admin = current_user(session_id, db)
    if admin is None or admin.role.lower() != "admin":
        return RedirectResponse(url="/", status_code=303)
        
    submissions = db.query(Submission).all() 
    wb = Workbook()
    ws = wb.active
    ws.title = "Submissions"
    ws.append([
        "Supplier", "Month", "Year", "Upload Date", 
        "Man Change", "Machine Change", "Method Change", "Material Change", "Status"
    ])
    
    for submission in submissions:
        categories = {
            "Man Change": "No",
            "Machine Change": "No",
            "Method Change": "No",
            "Material Change": "No"
        }
        supplier = submission.supplier
        if supplier is None:
            continue
            
        for doc in submission.change_docs:
            if doc.category in categories:
                categories[doc.category] = "Yes"
                
        ws.append([
            supplier.supplier_name,
            submission.month,
            submission.year,
            submission.upload_date.strftime('%Y-%m-%d') if submission.upload_date else '',
            categories["Man Change"],
            categories["Machine Change"],
            categories["Method Change"],
            categories["Material Change"],
            submission.status
        ])
        
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Submissions.xlsx"'}
    )