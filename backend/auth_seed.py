from database import SessionLocal
from models import Users
from auth import hash_password

db = SessionLocal()

# Check if an admin already exists
existing_admin = db.query(Users).filter(Users.role == "admin").first()

if existing_admin:
    print("Admin already exists.")
else:
    admin = Users(
        email="admin@example.com",
        password_hash=hash_password("admin123"),
        role="admin",
        supplier_id=None,
    )

    db.add(admin)
    db.commit()

    print("Admin created successfully!")

db.close()