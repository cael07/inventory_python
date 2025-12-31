from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from backend.database import SessionLocal, engine
from backend.models import User, Product, ProductMonitoring
from backend.schemas import UserCreate, ProductCreate, ProductMonitoringCreate
from backend import auth

# Create tables (safe: won't drop existing data)
Product.__table__.create(bind=engine, checkfirst=True)
ProductMonitoring.__table__.create(bind=engine, checkfirst=True)
User.__table__.create(bind=engine, checkfirst=True)

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

    # 2️⃣ Save monitoring record (movement log)
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
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id.desc()).all()

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
def get_monitoring(db: Session = Depends(get_db)):
    return db.query(ProductMonitoring).order_by(ProductMonitoring.date.desc()).all()
