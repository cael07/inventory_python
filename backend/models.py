from sqlalchemy import Column, Integer, String, Float
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    barcode = Column(String, unique=True)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer, default=0)  # NEW