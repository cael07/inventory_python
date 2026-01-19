from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from io import BytesIO
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, cast, or_, text
from datetime import date, timedelta, datetime
from sqlalchemy.types import Date
from email.message import EmailMessage
from backend.database import SessionLocal, engine
from backend.models import User, Product, ProductMonitoring, Purchase
from backend.schemas import UserCreate, ProductCreate, ProductMonitoringCreate, PurchaseCreate, UserRegister
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

# -------------------------------------------------
# APP
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"status": "API running"}

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
          const r = await fetch(`${{API}}/verify-email?email=${{this.email}}&code=${{this.code}}`, {{
            method:"POST"
          }});
          const d = await r.json();
          this.message = d.status || d.detail;
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
            "storename": user.storename
        }
    }



@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.desc()).all()

    return {
        "total": len(users),
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "firstname": u.firstname,
                "middlename": u.middlename,
                "lastname": u.lastname,
                "storename": u.storename,
                "storelocation": u.storelocation,
                "address": u.address,
                "verified": u.verified,
                "date": u.date.strftime("%Y-%m-%d %H:%M:%S") if u.date else None
            }
            for u in users
        ]
    }

# ---------------- PRODUCTS ----------------
@app.post("/product")
def save_product(p: ProductCreate, db: Session = Depends(get_db)):
    # 1️⃣ Save product (current stock)
    product = Product(
        barcode=p.barcode,
        name=p.name,
        price=p.price,
        quantity=p.quantity
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
        remark="Initial stock"
    )
    db.add(monitoring)
    db.commit()

    return {
        "status": "saved",
        "product_quantity": product.quantity
    }

@app.get("/product/{barcode}")
def get_product(barcode: str, db: Session = Depends(get_db)):
    return db.query(Product).filter_by(barcode=barcode).first()

@app.get("/products")
def get_products(
    page: int = 1,
    limit: int = 25,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    rows = (
        db.query(Product)
        .order_by(Product.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = db.query(Product).count()

    # convert SQLAlchemy objects to plain dicts
    items = [
        {
            "id": r.id,
            "barcode": r.barcode,
            "name": r.name,
            "price": r.price,
            "quantity": r.quantity
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
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S")
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
    # Fetch product
    product = db.query(Product).filter_by(barcode=barcode).first()

    if not product:
        # Create new product
        product = Product(
            barcode=data.barcode,
            name=data.name,
            price=data.price,
            quantity=data.quantity
        )
        db.add(product)
    else:
        # Update quantity
        product.quantity += data.quantity
        product.price = data.price
    # Add monitoring entry
    monitoring = ProductMonitoring(
        barcode=data.barcode,
        name=data.name,
        price=data.price,
        quantity=data.quantity,
        total_price=data.total_price,  # comes from frontend or calculate here
        remark=data.remark
    )
    db.add(monitoring)

    # Commit everything at once
    db.commit()

    return {"message": "Product updated and monitored"}

@app.get("/products_manual_search")
def products_manual_search(search: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Product)
        .filter(
            or_(
                Product.barcode.ilike(f"%{search}%"),
                Product.name.ilike(f"%{search}%")
            )
        )
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
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S")
            }
            for r in rows
        ]
    }


@app.get("/monitoring")
def get_monitoring(
    page: int = 1,
    limit: int = 25,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    rows = (
        db.query(ProductMonitoring)
        .order_by(ProductMonitoring.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = db.query(ProductMonitoring).count()

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
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S")
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
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter_by(barcode=barcode).first()
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
                "date": r.date.strftime("%Y-%m-%d %H:%M:%S")
            }
            for r in rows
        ]
    }



@app.get("/pos/{purchase_number}")
def get_pos_items(purchase_number: str, db: Session = Depends(get_db)):
    items = db.query(Purchase).filter_by(
        purchase_number=purchase_number
    ).all()

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

    for item in items:
        p = Purchase(
            purchase_number=purchase_number,
            barcode=item["barcode"],
            name=item["name"],
            price=item["price"],
            quantity=item["quantity"],
            total_price=item["total_price"]
        )
        db.add(p)
    db.commit()
    return {"status": "success", "message": f"{len(items)} items saved"}

@app.get("/pos/report/export")
def export_pos_report(
    purchase_number: str | None = None,
    barcode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
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

    rows = query.order_by(Purchase.date.desc()).all()

    data = [
        {
            "Date": r.date.strftime("%Y-%m-%d %H:%M:%S"),
            "Purchase Number": r.purchase_number,
            "Barcode": r.barcode,
            "Name": r.name,
            "Price": r.price,
            "Quantity": r.quantity,
            "Total": r.total_price,
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
def purchase_stats_daily(db: Session = Depends(get_db)):
    today = date.today()
    start_date = today - timedelta(days=6)

    rows = (
        db.query(
            cast(Purchase.date, Date).label("date"),
            func.sum(Purchase.total_price).label("total")
        )
        .filter(cast(Purchase.date, Date) >= start_date)
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
def purchase_stats_monthly(db: Session = Depends(get_db)):
    current_year = date.today().year

    rows = (
        db.query(
            func.to_char(Purchase.date, "YYYY-MM").label("month"),
            func.sum(Purchase.total_price).label("total")
        )
        .filter(func.extract("year", Purchase.date) == current_year)
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
def purchase_stats_yearly(db: Session = Depends(get_db)):
    current_year = date.today().year
    start_year = current_year - 6

    rows = (
        db.query(
            func.to_char(Purchase.date, "YYYY").label("year"),
            func.sum(Purchase.total_price).label("total")
        )
        .filter(func.extract("year", Purchase.date) >= start_year)
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
def top_products_daily(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Purchase.name.label("name"),
            func.sum(Purchase.quantity).label("qty")
        )
        .filter(cast(Purchase.date, Date) == cast(func.now(), Date))
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
def top_products_monthly(db: Session = Depends(get_db)):
    current_month = func.to_char(func.now(), "YYYY-MM")

    rows = (
        db.query(
            Purchase.name.label("name"),
            func.sum(Purchase.quantity).label("qty")
        )
        .filter(func.to_char(Purchase.date, "YYYY-MM") == current_month)
        .group_by(Purchase.name)
        .order_by(func.sum(Purchase.quantity).desc())
        .limit(10)
        .all()
    )

    return [
        {"name": r.name, "quantity": int(r.qty or 0)}
        for r in rows
    ]
