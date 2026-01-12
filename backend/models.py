from sqlalchemy import Column, Integer, String, Float, DateTime, func
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    useremail = Column(String, unique=True, index=True)

    password = Column(String)

    firstname = Column(String)
    middlename = Column(String, nullable=True)
    lastname = Column(String)

    address = Column(String)
    storename = Column(String)
    storelocation = Column(String)

    verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    barcode = Column(String, unique=True)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer, default=0)  # NEW

class ProductMonitoring(Base):
    __tablename__ = "product_monitoring"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    total_price = Column(Float)
    remark = Column(String, default="")
    date = Column(DateTime(timezone=True), server_default=func.now())

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    purchase_number = Column(String)  # e.g., "POS-0001"
    barcode = Column(String)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    total_price = Column(Float)
    remark = Column(String, default="")
    date = Column(DateTime(timezone=True), server_default=func.now())