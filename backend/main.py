from fastapi.responses import StreamingResponse
from io import BytesIO
import pandas as pd
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, cast
from datetime import date, timedelta
from sqlalchemy.types import Date

from backend.database import SessionLocal, engine
from backend.models import User, Product, ProductMonitoring, Purchase
from backend.schemas import UserCreate, ProductCreate, ProductMonitoringCreate, PurchaseCreate
from backend import auth

import uuid

# Create tables (safe: won't drop existing data)
Product.__table__.create(bind=engine, checkfirst=True)
ProductMonitoring.__table__.create(bind=engine, checkfirst=True)
User.__table__.create(bind=engine, checkfirst=True)
Purchase.__table__.create(bind=engine, checkfirst=True)

app = FastAPI(
    title="Inventory API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for testing
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

# ---------------- AUTH ----------------
@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter_by(username=user.username).first()
    if db_user:
        return {"status": "User already exists"}
    new_user = User(username=user.username, password=auth.hash_password(user.password))
    db.add(new_user)
    db.commit()
    return {"status": "user created"}

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
