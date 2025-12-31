from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from backend.database import SessionLocal, engine
from backend import models, schemas, auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Inventory API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

@app.get("/")
def root():
    return {"status": "API running"}


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

@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(
        username=user.username,
        password=auth.hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    return {"status": "user created"}

@app.post("/product")
def save_product(p: schemas.ProductCreate, db: Session = Depends(get_db)):
    product = models.Product(**p.dict())
    db.add(product)
    db.commit()
    return {"status": "saved"}

@app.get("/product/{barcode}")
def get_product(barcode: str, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter_by(barcode=barcode).first()
    return p
