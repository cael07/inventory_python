from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from io import BytesIO
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, cast, or_, and_, text
from datetime import date, timedelta, datetime
from sqlalchemy.types import Date
from email.message import EmailMessage
from backend.database import SessionLocal, engine
from backend.models import User, Product, ProductMonitoring, Purchase, Message, Suki
from backend.schemas import UserCreate, ProductCreate, ProductMonitoringCreate, PurchaseCreate, UserRegister, UserUpdate, MessageCreate, SukiCreate
from backend import auth

import uuid
import secrets
import smtplib
import os
import traceback
import requests
# -------------------------------------------------
# CREATE TABLES
# -------------------------------------------------

Product.__table__.create(bind=engine, checkfirst=True)
ProductMonitoring.__table__.create(bind=engine, checkfirst=True)

# DEV ONLY: reset users
# User.__table__.drop(bind=engine, checkfirst=True)
User.__table__.create(bind=engine, checkfirst=True)

Purchase.__table__.create(bind=engine, checkfirst=True)
Message.__table__.create(bind=engine, checkfirst=True)

# -------------------------------------------------
# DB MIGRATION: Switch from global barcode unique to
# composite unique (barcode + store_name)
# -------------------------------------------------
try:
    with engine.connect() as conn:
        # Drop old single-column unique constraint if it exists
        conn.execute(text("""
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'products_barcode_key'
                ) THEN
                    ALTER TABLE products DROP CONSTRAINT products_barcode_key;
                END IF;
            END $$;
        """))
        # Add composite unique constraint if it doesn't exist
        conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uix_barcode_store'
                ) THEN
                    ALTER TABLE products
                    ADD CONSTRAINT uix_barcode_store
                    UNIQUE (barcode, store_name);
                END IF;
            END $$;
        """))
        conn.commit()
except Exception as e:
    print(f"[MIGRATION WARNING] {e}")

Suki.__table__.create(bind=engine, checkfirst=True)

# -------------------------------------------------
# APP STARTUP
# -------------------------------------------------

app = FastAPI(
    title="Inventory API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GLOBAL_ERRORS = []

def sync_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT last_activity FROM users LIMIT 1"))
    except Exception as e:
        GLOBAL_ERRORS.append(f"Initial check failed: {str(e)}")
        try:
            with engine.connect() as conn:
                # Detect dialect and use appropriate syntax
                dialect = engine.dialect.name
                col_type = "TIMESTAMPTZ" if dialect == "postgresql" else "TIMESTAMP"
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_activity {col_type}"))
                conn.commit()
                GLOBAL_ERRORS.append("✅ Successfully added last_activity column")
        except Exception as e2:
            GLOBAL_ERRORS.append(f"Migration failed (last_activity): {str(e2)}")
    
    # NEW MIGRATION: suki status
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT status FROM suki LIMIT 1"))
    except Exception as e:
        GLOBAL_ERRORS.append(f"Initial suki check failed: {str(e)}")
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE suki ADD COLUMN status VARCHAR DEFAULT 'pending'"))
                conn.commit()
                GLOBAL_ERRORS.append("✅ Successfully added suki status column")
        except Exception as e2:
            GLOBAL_ERRORS.append(f"Migration failed (suki status): {str(e2)}")

    # NEW MIGRATION: Tracking columns
    for table_name in ["products", "product_monitoring", "purchases"]:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"SELECT store_name FROM {table_name} LIMIT 1"))
        except Exception:
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN store_name VARCHAR"))
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN created_by VARCHAR"))
                    conn.commit()
                    GLOBAL_ERRORS.append(f"✅ Added tracking columns to {table_name}")
            except Exception as e2:
                GLOBAL_ERRORS.append(f"Migration failed ({table_name} tracking): {str(e2)}")

# Run sync after app definition
@app.on_event("startup")
def on_startup():
    sync_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        return {
            "status": "API running",
            "user_count": len(users),
            "errors": GLOBAL_ERRORS
        }
    except Exception as e:
        return {"status": "API running", "error": str(e), "errors": GLOBAL_ERRORS}

@app.get("/debug/errors")
def get_debug_errors():
    return {"errors": GLOBAL_ERRORS}

# -------------------------------------------------
# SUKI (FRIEND LIST)
# -------------------------------------------------

# -------------------------------------------------
# DEBUG
# -------------------------------------------------

@app.get("/debug/users")
def debug_users(db: Session = Depends(get_db)):
    try:
        # --- DATABASE CHECK ---
        rows = db.execute(text("SELECT * FROM users")).fetchall()
        users = [dict(r._mapping) for r in rows]

        # --- ENV CHECK (RAW, UNMASKED) ---
        env_dump = {
            # STATUS
            "API_STATUS": "RUNNING",

            # DATABASE
            "DATABASE_URL": os.getenv("DATABASE_URL"),

            # BREVO API
            "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
            "BREVO_SENDER_EMAIL": os.getenv("BREVO_SENDER_EMAIL"),
            "BREVO_SENDER_NAME": os.getenv("BREVO_SENDER_NAME"),

            # SMTP (even if unused)
            "SMTP_HOST": os.getenv("SMTP_HOST"),
            "SMTP_PORT": os.getenv("SMTP_PORT"),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
            "SMTP_FROM_EMAIL": os.getenv("SMTP_FROM_EMAIL"),
            "SMTP_FROM_NAME": os.getenv("SMTP_FROM_NAME"),
        }

        return {
            "status": "OK",
            "env": env_dump,
            "user_count": len(users),
            "users": users
        }

    except Exception as e:
        print("❌ DEBUG ERROR")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------
# REGISTER
# -------------------------------------------------
@app.post("/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    try:
        hashed_password = auth.hash_password(user.password)
        verification_code = secrets.token_hex(3)

        new_user = User(
            username=user.username,
            useremail=user.useremail,
            password=hashed_password,
            firstname=user.firstname,
            middlename=user.middlename or None,
            lastname=user.lastname,
            address=user.address,
            storename=user.storename,
            storelocation=user.storelocation,
            verified=False,
            verification_code=verification_code
        )

        db.add(new_user)
        db.commit()

        send_verification_email(new_user.useremail, verification_code)

        return {
            "status": "ok",
            "message": "Verification email sent",
            "email": new_user.useremail
        }

    except Exception as e:
        raise HTTPException(500, detail=str(e))


# -------------------------------------------------
# EMAIL VERIFICATION
# -------------------------------------------------
def send_verification_email(to_email: str, code: str):
    print("📧 Sending verification email via Brevo API")

    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    sender_name = os.getenv("BREVO_SENDER_NAME")

    print("🔎 BREVO ENV CHECK")
    print("BREVO_API_KEY:", api_key)
    print("BREVO_SENDER_EMAIL:", sender_email)
    print("BREVO_SENDER_NAME:", sender_name)

    if not api_key or not sender_email:
        raise Exception("Brevo environment variables missing")

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "email": sender_email,
            "name": sender_name or "Verification"
        },
        "to": [
            {"email": to_email}
        ],
        "subject": "Verify your account",
        "htmlContent": f"""
            <h2>Verify your account</h2>
            <p>Your verification code is:</p>
            <h1>{code}</h1>
            <p>This code expires in 10 minutes.</p>
        """
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    print("📨 BREVO STATUS:", response.status_code)
    print("📨 BREVO RESPONSE:", response.text)

    if response.status_code not in (200, 201):
        raise Exception("Brevo email sending failed")

@app.get("/verify.html", response_class=HTMLResponse)
def serve_verify_page(request: Request, email: str = ""):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <script src="https://unpkg.com/vue@3"></script>
      <style>
        body {{ font-family: Arial; background:#f4f4f4; }}
        .box {{ max-width:360px; margin:40px auto; background:white; padding:20px; border-radius:6px; }}
        input, button {{ width:100%; padding:8px; margin:6px 0; }}
        button {{ background:#27ae60; color:white; border:none; }}
      </style>
    </head>
    <body>
    <div id="app" class="box">
      <h2>✅ Verify Email</h2>
      <input v-model="email" placeholder="Email" :value="{email}">
      <input v-model="code" placeholder="Verification Code">
      <button @click="verify">Verify</button>
      <p>{{ message }}</p>
      <a href="/login.html">Go to Login</a>
    </div>
    <script>
    const API = "https://inventory-python.onrender.com";

    Vue.createApp({{
      data() {{
        return {{ email: "{email}", code:"", message:"" }}
      }},
      methods:{{
        async verify() {{
          if (!this.email || !this.code) {{
            this.message = "Please enter both email and code.";
            return;
          }}
          this.message = "Verifying...";
          try {{
            const r = await fetch(`${{API}}/verify-email?email=${{encodeURIComponent(this.email.trim())}}&code=${{encodeURIComponent(this.code.trim())}}`, {{
              method:"POST"
            }});
            const d = await r.json();
            this.message = d.status || d.detail || "Verification processed";
            if (d.status === "Email verified successfully" || d.status === "Account already verified") {{
               setTimeout(() => {{ window.location.href = "login.html"; }}, 1500);
            }}
          }} catch(e) {{
            this.message = "Connection error. Please try again.";
            console.error(e);
          }}
        }}
      }}
    }}).mount("#app");
    </script>
    </body>
    </html>
    """

@app.post("/verify-email")
def verify_email(
    email: str,
    code: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.useremail == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.verified:
        return {"status": "Account already verified"}

    if user.verification_code != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.verified = True
    user.verification_code = None
    db.commit()

    return {"status": "Email verified successfully"}


@app.get("/check-availability")
def check_availability(
    username: str | None = None,
    email: str | None = None,
    db: Session = Depends(get_db)
):
    if username:
        exists = db.query(User).filter(User.username == username).first()
        return {"field": "username", "available": not bool(exists)}

    if email:
        exists = db.query(User).filter(User.useremail == email).first()
        return {"field": "email", "available": not bool(exists)}

    raise HTTPException(400, "Missing username or email")

# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@app.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=username).first()

    if not user or not auth.verify(password, user.password):
        raise HTTPException(401, "Invalid credentials")

    if not user.verified:
        raise HTTPException(403, "Email not verified")

    token = auth.create_access_token({
        "sub": str(user.id),
        "username": user.username
    })

    return {
        "status": "ok",
        "access_token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "storename": user.storename,
            "firstname": user.firstname,
            "middlename": user.middlename,
            "lastname": user.lastname
        }
    }



@app.get("/user/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.useremail,
        "firstname": user.firstname,
        "middlename": user.middlename,
        "lastname": user.lastname,
        "address": user.address,
        "storename": user.storename,
        "storelocation": user.storelocation,
        "verified": user.verified,
        "date": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
    }

@app.put("/user/{user_id}")
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.address:
        user.address = user_data.address
    if user_data.storename:
        user.storename = user_data.storename
    if user_data.storelocation:
        user.storelocation = user_data.storelocation
    if user_data.password:
        user.password = auth.hash_password(user_data.password)
        
    db.commit()
    return {"status": "success", "message": "User updated successfully"}

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    try:
        users = db.query(User).order_by(User.id.desc()).all()

        return {
            "total": len(users),
            "items": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.useremail,
                    "firstname": u.firstname,
                    "middlename": u.middlename,
                    "lastname": u.lastname,
                    "storename": u.storename,
                    "storelocation": u.storelocation,
                    "address": u.address,
                    "verified": u.verified,
                    "date": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if (u.created_at and hasattr(u.created_at, "strftime")) else None
                }
                for u in users
            ]
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/user/{user_id}/ping")
def ping_user_status(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.last_activity = func.now()
        db.commit()
    return {"status": "ok"}

# ---------------- MESSAGES ----------------
@app.get("/messages/contacts/{user_id}")
def get_message_contacts(user_id: int, db: Session = Depends(get_db)):
    # 🚨 RESTRICTION: Only show users who are mutual Sukis (accepted)
    # Get all sukis related to this user where status = accepted
    accepted_sukis = db.query(Suki).filter(
        or_(
            and_(Suki.owner_id == user_id, Suki.status == "accepted"),
            and_(Suki.suki_id == user_id, Suki.status == "accepted")
        )
    ).all()
    
    friend_ids = set()
    for s in accepted_sukis:
        if s.owner_id == user_id: friend_ids.add(s.suki_id)
        else: friend_ids.add(s.owner_id)
    
    # Now get user objects for these IDs
    contacts = []
    if friend_ids:
        users = db.query(User).filter(User.id.in_(friend_ids)).all()
        for u in users:
            # Existing message history logic...
            last_msg = db.query(Message).filter(
                or_(
                    and_(Message.sender_id == user_id, Message.receiver_id == u.id),
                    and_(Message.sender_id == u.id, Message.receiver_id == user_id)
                )
            ).order_by(Message.id.desc()).first()
            
            unread = db.query(Message).filter(
                Message.sender_id == u.id,
                Message.receiver_id == user_id,
                Message.is_read == False
            ).count()
            
            now = datetime.now()
            is_online = False
            if (u.last_activity and hasattr(u.last_activity, "replace")):
                 ua = u.last_activity.replace(tzinfo=None)
                 is_online = (now - ua).total_seconds() < 300

            contacts.append({
                "user_id": u.id,
                "username": u.username,
                "firstname": u.firstname,
                "lastname": u.lastname,
                "storename": u.storename,
                "storelocation": u.storelocation,
                "last_message": last_msg.content if last_msg else None,
                "last_message_time": last_msg.timestamp if last_msg else None,
                "unread_count": unread,
                "is_online": is_online
            })
    
    # Sort: Online first, then unread first, then by last message time
    contacts.sort(key=lambda x: (not x["is_online"], not (x["unread_count"] > 0), str(x["last_message_time"] or "0000")), reverse=False)
    return contacts

@app.get("/messages/{user_id}/{other_id}")
def get_message_history(user_id: int, other_id: int, db: Session = Depends(get_db)):
    history = db.query(Message).filter(
        or_(
            (Message.sender_id == user_id) & (Message.receiver_id == other_id),
            (Message.sender_id == other_id) & (Message.receiver_id == user_id)
        )
    ).order_by(Message.timestamp.asc()).all()
    
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "timestamp": m.timestamp.strftime("%H:%M") if m.timestamp else "",
            "is_read": m.is_read
        } for m in history
    ]

@app.post("/messages/{user_id}")
def send_message(user_id: int, data: MessageCreate, db: Session = Depends(get_db)):
    msg = Message(
        sender_id=user_id,
        receiver_id=data.receiver_id,
        content=data.content
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"status": "success", "message": "Sent", "id": msg.id}

@app.post("/messages/{user_id}/read/{other_id}")
def mark_messages_read(user_id: int, other_id: int, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.sender_id == other_id,
        Message.receiver_id == user_id,
        Message.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "success"}


    # -------------------------------------------------
    # PERSISTENCE LOGIC (V3 - Audited)
    # -------------------------------------------------
    return f"Product {product.name} saved successfully by {product.created_by}"

@app.post("/product")
def save_product(p: ProductCreate, db: Session = Depends(get_db)):
    # 1️⃣ Save product (current stock)
    product = Product(
        barcode=p.barcode,
        name=p.name,
        price=p.price,
        quantity=p.quantity,
        store_name=p.store_name,
        created_by=p.created_by
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # 2️⃣ Save monitoring record (initial stock)
    monitoring = ProductMonitoring(
        barcode=p.barcode,
        name=p.name,
        price=p.price,
        quantity=p.quantity,
        total_price=p.price * p.quantity,
        remark="Initial stock",
        store_name=p.store_name,
        created_by=p.created_by
    )
    db.add(monitoring)
    db.commit()

    return {
        "status": "saved",
        "product_quantity": product.quantity
    }

@app.get("/product/{barcode}")
def get_product(
    barcode: str, 
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter_by(barcode=barcode)
    if store_name:
        query = query.filter(Product.store_name == store_name)
    return query.first()

@app.get("/products")
def get_products(
    page: int = 1,
    limit: int = 25,
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    query = db.query(Product)
    if store_name:
        query = query.filter(Product.store_name == store_name)

    rows = (
        query
        .order_by(Product.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = query.count()

    # convert SQLAlchemy objects to plain dicts
    items = [
        {
            "id": r.id,
            "barcode": r.barcode,
            "name": r.name,
            "price": r.price,
            "quantity": r.quantity,
            "store_name": r.store_name,
            "created_by": r.created_by
        }
        for r in rows
    ]

    return {
        "page": page,
        "limit": limit,
        "total_records": total,
        "items": items
    }

@app.get("/monitoring_manual_search")
def monitoring_manual_search(
    search: str | None = None,
    date_from: str | None = None,   # YYYY-MM-DD
    date_to: str | None = None,     # YYYY-MM-DD
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    filters = []

    # 🔍 Text search
    if search:
        filters.append(
            or_(
                ProductMonitoring.barcode.ilike(f"%{search}%"),
                ProductMonitoring.name.ilike(f"%{search}%")
            )
        )

    # 📅 Date range
    if date_from:
        from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        filters.append(ProductMonitoring.date >= from_dt)

    if date_to:
        to_dt = datetime.strptime(date_to, "%Y-%m-%d")
        filters.append(ProductMonitoring.date <= to_dt)

    if store_name:
        filters.append(ProductMonitoring.store_name == store_name)

    rows = (
        db.query(ProductMonitoring)
        .filter(and_(*filters)) if filters else db.query(ProductMonitoring)
    )

    rows = (
        rows
        .order_by(ProductMonitoring.date.desc())
        .limit(50)
        .all()
    )

    return {
        "items": [
            {
                "id": r.id,
                "barcode": r.barcode,
                "name": r.name,
                "price": r.price,
                "quantity": r.quantity,
                "total_price": r.total_price,
                "remark": r.remark,
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S"), "store_name": r.store_name, "created_by": r.created_by,
                "store_name": r.store_name,
                "created_by": r.created_by
            }
            for r in rows
        ]
    }


# ---------------- MONITORING ----------------
@app.put("/update_product/{barcode}")
def update_product_item(
    barcode: str,
    data: ProductMonitoringCreate,
    db: Session = Depends(get_db)
):
    # --- AUTO-DETECTION FALLBACK ---
    s_name = data.store_name
    c_by = data.created_by
    
    # If the frontend failed to send the name/store, try to find it via username
    if not s_name or not c_by:
        user = db.query(User).filter(User.username == c_by).first()
        if user:
            s_name = s_name or user.storename
            c_by = c_by or user.username

    # Fetch product
    product = db.query(Product).filter_by(barcode=barcode, store_name=s_name).first()

    if not product:
        # Create new product
        product = Product(
            barcode=data.barcode,
            name=data.name,
            price=data.price,
            quantity=data.quantity,
            store_name=s_name,
            created_by=c_by
        )
        db.add(product)
    else:
        # Update quantity
        product.quantity += data.quantity
        product.price = data.price
        product.store_name = s_name
        product.created_by = c_by
        
    # Add monitoring entry
    monitoring = ProductMonitoring(
        barcode=data.barcode,
        name=data.name,
        price=data.price,
        quantity=data.quantity,
        total_price=data.total_price,
        remark=data.remark,
        store_name=s_name,
        created_by=c_by
    )
    db.add(monitoring)
    db.commit()

    return {"message": "Success", "saved_as": c_by, "store": s_name}

@app.get("/products_manual_search")
def products_manual_search(
    search: str, 
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(
        or_(
            Product.barcode.ilike(f"%{search}%"),
            Product.name.ilike(f"%{search}%")
        )
    )
    
    if store_name:
        query = query.filter(Product.store_name == store_name)

    rows = (
        query
        .limit(20)
        .all()
    )

    return {
        "items": [
            {
                "id": r.id,
                "barcode": r.barcode,
                "name": r.name,
                "price": r.price,
                "quantity": r.quantity
            }
            for r in rows
        ]
    }


@app.get("/monitoring_manual_search")
def monitoring_manual_search(
    search: str,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(ProductMonitoring)
        .filter(
            or_(
                ProductMonitoring.barcode.ilike(f"%{search}%"),
                ProductMonitoring.name.ilike(f"%{search}%")
            )
        )
        .order_by(ProductMonitoring.date.desc())
        .limit(50)
        .all()
    )

    return {
        "items": [
            {
                "id": r.id,
                "barcode": r.barcode,
                "name": r.name,
                "price": r.price,
                "quantity": r.quantity,
                "total_price": r.total_price,
                "remark": r.remark,
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S"), "store_name": r.store_name, "created_by": r.created_by
            }
            for r in rows
        ]
    }


@app.get("/monitoring")
def get_monitoring(
    page: int = 1,
    limit: int = 25,
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    query = db.query(ProductMonitoring)
    if store_name:
        query = query.filter(ProductMonitoring.store_name == store_name)

    rows = (
        query
        .order_by(ProductMonitoring.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = query.count()

    return {
        "page": page,
        "limit": limit,
        "total_records": total,
        "items": [
            {
                "id": r.id,
                "barcode": r.barcode,
                "name": r.name,
                "price": r.price,
                "quantity": r.quantity,
                "total_price": r.total_price,
                "remark": r.remark,
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S"), "store_name": r.store_name, "created_by": r.created_by
            }
            for r in rows
        ]
    }


@app.post("/pos/start")
def start_pos():
    purchase_number = uuid.uuid4().hex[:10].upper()
    return {"purchase_number": purchase_number}

@app.post("/pos/scan")
def pos_scan(
    purchase_number: str,
    barcode: str,
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter_by(barcode=barcode, store_name=store_name).first()
    if not product:
        raise HTTPException(404, "Product not found")

    if product.quantity <= 0:
        raise HTTPException(400, "Out of stock")

    qty = 1
    total = product.price * qty

    # deduct stock
    product.quantity -= qty

    purchase = Purchase(
        purchase_number=purchase_number,
        barcode=product.barcode,
        name=product.name,
        price=product.price,
        quantity=qty,
        total_price=total
    )

    db.add(purchase)
    db.commit()

    return {
        "barcode": product.barcode,
        "name": product.name,
        "price": product.price,
        "quantity": qty,
        "total_price": total
    }

@app.get("/pos/report")
def pos_report(
    page: int = 1,
    limit: int = 10,
    purchase_number: str | None = None,
    barcode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    query = db.query(Purchase)

    if purchase_number:
        query = query.filter(Purchase.purchase_number.ilike(f"%{purchase_number}%"))

    if barcode:
        query = query.filter(Purchase.barcode.ilike(f"%{barcode}%"))

    if date_from:
        query = query.filter(Purchase.date >= date_from)

    if date_to:
        query = query.filter(Purchase.date <= date_to)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    total = query.count()

    rows = (
        query.order_by(Purchase.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "page": page,
        "limit": limit,
        "total_records": total,
        "items": [
            {
                "id": r.id,
                "purchase_number": r.purchase_number,
                "barcode": r.barcode,
                "name": r.name,
                "price": r.price,
                "quantity": r.quantity,
                "total_price": r.total_price,
                "remark": r.remark,
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S"), "store_name": r.store_name, "created_by": r.created_by
            }
            for r in rows
        ]
    }



@app.get("/pos/{purchase_number}")
def get_pos_items(
    purchase_number: str, 
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    items = db.query(Purchase).filter(
        Purchase.purchase_number == purchase_number
    )
    if store_name:
        items = items.filter(Purchase.store_name == store_name)
    
    items = items.all()

    total = sum(i.total_price for i in items)

    return {
        "items": items,
        "grand_total": total
    }

@app.post("/pos/save")
def save_purchase(data: dict, db: Session = Depends(get_db)):
    purchase_number = data["purchase_number"]
    items = data["items"]
    paid_amount = data.get("paid_amount", 0)

    store_name = data.get("store_name")
    created_by = data.get("created_by")

    for item in items:
        p = Purchase(
            purchase_number=purchase_number,
            barcode=item["barcode"],
            name=item["name"],
            price=item["price"],
            quantity=item["quantity"],
            total_price=item["total_price"],
            store_name=store_name,
            created_by=created_by
        )
        db.add(p)
        
        # Deduct from inventory
        product = db.query(Product).filter_by(barcode=item["barcode"], store_name=store_name).first()
        if product:
            product.quantity -= item["quantity"]
            
            # Record in monitoring
            mon = ProductMonitoring(
                barcode=item["barcode"],
                name=item["name"],
                price=item["price"],
                quantity=-item["quantity"],  # negative for deduction
                total_price=-item["total_price"],
                remark=f"Sold (POS: {purchase_number})",
                store_name=store_name,
                created_by=created_by
            )
            db.add(mon)
            
    db.commit()
    return {"status": "success", "message": f"{len(items)} items saved"}

@app.get("/pos/report/export")
def export_pos_report(
    purchase_number: str | None = None,
    barcode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Purchase)

    if purchase_number:
        query = query.filter(Purchase.purchase_number.ilike(f"%{purchase_number}%"))

    if barcode:
        query = query.filter(Purchase.barcode.ilike(f"%{barcode}%"))

    if date_from:
        query = query.filter(Purchase.date >= date_from)

    if date_to:
        query = query.filter(Purchase.date <= date_to)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = query.order_by(Purchase.date.desc()).all()

    data = [
        {
            "date": r.date.strftime("%Y-%m-%d %H:%M:%S"), "store_name": r.store_name, "created_by": r.created_by,
            "Purchase Number": r.purchase_number,
            "Barcode": r.barcode,
            "Name": r.name,
            "Price": r.price,
            "Quantity": r.quantity,
            "Total": r.total_price,
            "Store": r.store_name,
            "Created By": r.created_by
        }
        for r in rows
    ]

    df = pd.DataFrame(data)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pos_report.xlsx"}
    )


# ---------------- 📊 PURCHASE STATS (DAILY - LAST 7 DAYS) ----------------
@app.get("/stats/purchases/daily")
def purchase_stats_daily(
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    start_date = today - timedelta(days=6)

    query = db.query(
        cast(Purchase.date, Date).label("date"),
        func.sum(Purchase.total_price).label("total")
    ).filter(cast(Purchase.date, Date) >= start_date)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = (
        query
        .group_by(cast(Purchase.date, Date))
        .order_by(cast(Purchase.date, Date))
        .all()
    )

    return [
        {"date": r.date.strftime("%Y-%m-%d"), "total": float(r.total or 0)}
        for r in rows
    ]

# ---------------- 📊 PURCHASE STATS (MONTHLY - CURRENT YEAR) ----------------
@app.get("/stats/purchases/monthly")
def purchase_stats_monthly(
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    current_year = date.today().year

    query = db.query(
        func.to_char(Purchase.date, "YYYY-MM").label("month"),
        func.sum(Purchase.total_price).label("total")
    ).filter(func.extract("year", Purchase.date) == current_year)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = (
        query
        .group_by(func.to_char(Purchase.date, "YYYY-MM"))
        .order_by(func.to_char(Purchase.date, "YYYY-MM"))
        .all()
    )

    return [
        {"month": r.month, "total": float(r.total or 0)}
        for r in rows
    ]

# ---------------- 📊 PURCHASE STATS (YEARLY - LAST 7 YEARS) ----------------
@app.get("/stats/purchases/yearly")
def purchase_stats_yearly(
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    current_year = date.today().year
    start_year = current_year - 6

    query = db.query(
        func.to_char(Purchase.date, "YYYY").label("year"),
        func.sum(Purchase.total_price).label("total")
    ).filter(func.extract("year", Purchase.date) >= start_year)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = (
        query
        .group_by(func.to_char(Purchase.date, "YYYY"))
        .order_by(func.to_char(Purchase.date, "YYYY"))
        .all()
    )

    return [
        {"year": r.year, "total": float(r.total or 0)}
        for r in rows
    ]


# ---------------- 🏆 TOP PRODUCT SALES ----------------
@app.get("/stats/products/top/daily")
def top_products_daily(
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        Purchase.name.label("name"),
        func.sum(Purchase.quantity).label("qty")
    ).filter(cast(Purchase.date, Date) == cast(func.now(), Date))

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = (
        query
        .group_by(Purchase.name)
        .order_by(func.sum(Purchase.quantity).desc())
        .limit(10)
        .all()
    )

    return [
        {"name": r.name, "quantity": int(r.qty or 0)}
        for r in rows
    ]


@app.get("/stats/products/top/monthly")
def top_products_monthly(
    store_name: str | None = None,
    db: Session = Depends(get_db)
):
    current_month = func.to_char(func.now(), "YYYY-MM")

    query = db.query(
        Purchase.name.label("name"),
        func.sum(Purchase.quantity).label("qty")
    ).filter(func.to_char(Purchase.date, "YYYY-MM") == current_month)

    if store_name:
        query = query.filter(Purchase.store_name == store_name)

    rows = (
        query
        .group_by(Purchase.name)
        .order_by(func.sum(Purchase.quantity).desc())
        .limit(10)
        .all()
    )

    return [
        {"name": r.name, "quantity": int(r.qty or 0)}
        for r in rows
    ]

# -------------------------------------------------
# SUKI (FRIEND LIST)
# -------------------------------------------------

@app.post("/suki")
def add_suki(suki_in: SukiCreate, owner_id: int, db: Session = Depends(get_db)):
    # 1. Check if user already requested
    existing = db.query(Suki).filter(Suki.owner_id == owner_id, Suki.suki_id == suki_in.suki_id).first()
    if existing:
        if existing.status == "accepted":
            return {"message": "Already mutual Sukis"}
        return {"message": "Request already sent"}
    
    # 2. Check if the OTHER user already sent a request to ME (auto-accept)
    reverse_req = db.query(Suki).filter(Suki.owner_id == suki_in.suki_id, Suki.suki_id == owner_id).first()
    if reverse_req:
        reverse_req.status = "accepted"
        # Also create my direction as accepted
        new_suki = Suki(owner_id=owner_id, suki_id=suki_in.suki_id, status="accepted")
        db.add(new_suki)
        db.commit()
        return {"message": "Mutual Suki connection established!"}
    
    # 3. Create a new pending request
    new_suki = Suki(owner_id=owner_id, suki_id=suki_in.suki_id, status="pending")
    db.add(new_suki)
    db.commit()
    return {"message": "Suki request sent"}

@app.get("/suki/pending/{user_id}")
def get_pending_requests(user_id: int, db: Session = Depends(get_db)):
    # Get requests sent TO me (suki_id = me) where status is pending
    requests = db.query(Suki).filter(Suki.suki_id == user_id, Suki.status == "pending").all()
    results = []
    for r in requests:
        u = db.query(User).filter(User.id == r.owner_id).first()
        if u:
            results.append({
                "id": u.id,
                "username": u.username,
                "firstname": u.firstname,
                "lastname": u.lastname,
                "storename": u.storename
            })
    return results

@app.get("/suki/sent/{user_id}")
def get_sent_requests(user_id: int, db: Session = Depends(get_db)):
    """Requests I sent that are still pending."""
    reqs = db.query(Suki).filter(Suki.owner_id == user_id, Suki.status == "pending").all()
    results = []
    for r in reqs:
        u = db.query(User).filter(User.id == r.suki_id).first()
        if u:
            results.append({"id": u.id, "username": u.username, "firstname": u.firstname, "lastname": u.lastname, "storename": u.storename})
    return results


@app.put("/suki/accept/{owner_id}/{suki_id}")
def accept_suki(owner_id: int, suki_id: int, db: Session = Depends(get_db)):
    # owner_id is the requester, suki_id is the receiver (me)
    req = db.query(Suki).filter(Suki.owner_id == owner_id, Suki.suki_id == suki_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    req.status = "accepted"
    # Create the mutual connection in the other direction too
    existing_other = db.query(Suki).filter(Suki.owner_id == suki_id, Suki.suki_id == owner_id).first()
    if not existing_other:
        new_other = Suki(owner_id=suki_id, suki_id=owner_id, status="accepted")
        db.add(new_other)
    else:
        existing_other.status = "accepted"
    
    db.commit()
    return {"message": "Suki request accepted"}

@app.get("/suki/{owner_id}")
def get_sukis(owner_id: int, db: Session = Depends(get_db)):
    # Only return accepted sukis
    sukis = db.query(Suki).filter(Suki.owner_id == owner_id, Suki.status == "accepted").all()
    results = []
    for s in sukis:
        user = db.query(User).filter(User.id == s.suki_id).first()
        if user:
            results.append({
                "id": user.id,
                "username": user.username,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "storename": user.storename,
                "storelocation": user.storelocation
            })
    return results

@app.delete("/suki/{owner_id}/{suki_id}")
def remove_suki(owner_id: int, suki_id: int, db: Session = Depends(get_db)):
    # Remove BOTH directions
    rel1 = db.query(Suki).filter(Suki.owner_id == owner_id, Suki.suki_id == suki_id).first()
    rel2 = db.query(Suki).filter(Suki.owner_id == suki_id, Suki.suki_id == owner_id).first()
    
    if rel1: db.delete(rel1)
    if rel2: db.delete(rel2)
    
    db.commit()
    return {"message": "Suki removed successfully"}


# -------------------------------------------------
# MESSAGING ENDPOINTS
# -------------------------------------------------

@app.get("/messages/contacts/{user_id}")
def get_contacts(user_id: int, db: Session = Depends(get_db)):
    """Return accepted sukis enriched with last message + unread count."""
    sukis = db.query(Suki).filter(
        Suki.owner_id == user_id, Suki.status == "accepted"
    ).all()

    results = []
    for s in sukis:
        u = db.query(User).filter(User.id == s.suki_id).first()
        if not u:
            continue

        # Last message between the two users
        last_msg = (
            db.query(Message)
            .filter(
                or_(
                    and_(Message.sender_id == user_id, Message.receiver_id == s.suki_id),
                    and_(Message.sender_id == s.suki_id, Message.receiver_id == user_id),
                )
            )
            .order_by(Message.timestamp.desc())
            .first()
        )

        # Unread count
        unread = db.query(Message).filter(
            Message.sender_id == s.suki_id,
            Message.receiver_id == user_id,
            Message.is_read == False,
        ).count()

        results.append({
            "user_id": u.id,
            "username": u.username,
            "firstname": u.firstname,
            "lastname": u.lastname,
            "storename": u.storename,
            "is_online": False,
            "last_message": last_msg.content if last_msg else None,
            "last_message_time": last_msg.timestamp.isoformat() if last_msg else None,
            "unread_count": unread,
        })

    results.sort(key=lambda x: x["last_message_time"] or "", reverse=True)
    return results


@app.get("/messages/{sender_id}/{receiver_id}")
def get_messages(sender_id: int, receiver_id: int, db: Session = Depends(get_db)):
    msgs = (
        db.query(Message)
        .filter(
            or_(
                and_(Message.sender_id == sender_id, Message.receiver_id == receiver_id),
                and_(Message.sender_id == receiver_id, Message.receiver_id == sender_id),
            )
        )
        .order_by(Message.timestamp.asc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "is_read": m.is_read,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in msgs
    ]


@app.post("/messages/{sender_id}")
def send_message(sender_id: int, data: MessageCreate, db: Session = Depends(get_db)):
    msg = Message(
        sender_id=sender_id,
        receiver_id=data.receiver_id,
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "sender_id": msg.sender_id, "content": msg.content}


@app.post("/messages/{user_id}/read/{other_id}")
def mark_read(user_id: int, other_id: int, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.sender_id == other_id,
        Message.receiver_id == user_id,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"status": "ok"}


@app.post("/user/{user_id}/ping")
def ping_user(user_id: int, db: Session = Depends(get_db)):
    """Keep-alive ping — no-op for now, returns ok."""
    return {"status": "ok"}


@app.get("/users/search")
def search_users(q: str, user_id: int, db: Session = Depends(get_db)):
    """Search registered users by name/username/store, excluding self."""
    users = (
        db.query(User)
        .filter(
            User.id != user_id,
            or_(
                User.username.ilike(f"%{q}%"),
                User.firstname.ilike(f"%{q}%"),
                User.lastname.ilike(f"%{q}%"),
                User.storename.ilike(f"%{q}%"),
            ),
        )
        .limit(20)
        .all()
    )

    # For each result check suki status
    results = []
    for u in users:
        rel = db.query(Suki).filter(
            Suki.owner_id == user_id, Suki.suki_id == u.id
        ).first()
        results.append({
            "id": u.id,
            "username": u.username,
            "firstname": u.firstname,
            "lastname": u.lastname,
            "storename": u.storename,
            "storelocation": u.storelocation,
            "suki_status": rel.status if rel else None,  # None / "pending" / "accepted"
        })
    return results

