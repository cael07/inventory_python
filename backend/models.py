from sqlalchemy import Column, Integer, String, Float, DateTime, func, Boolean, UniqueConstraint
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
    rank = Column(String, default="owner") # owner, cashier, bagger

    created_at = Column(DateTime, server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, index=True)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    store_name = Column(String, nullable=True)
    created_by = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint('barcode', 'store_name', name='uix_barcode_store'), )

class ProductMonitoring(Base):
    __tablename__ = "product_monitoring"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    total_price = Column(Float)
    remark = Column(String)
    date = Column(DateTime, default=func.now())
    store_name = Column(String, nullable=True)
    created_by = Column(String, nullable=True)

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    purchase_number = Column(String)
    barcode = Column(String)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    total_price = Column(Float)
    date = Column(DateTime, default=func.now())
    remark = Column(String, nullable=True)
    store_name = Column(String, nullable=True)
    created_by = Column(String, nullable=True)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, index=True)
    receiver_id = Column(Integer, index=True)
    content = Column(String)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Suki(Base):
    __tablename__ = "suki"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True)
    suki_id = Column(Integer, index=True)
    status = Column(String, default="pending") # pending, accepted
    created_at = Column(DateTime, server_default=func.now())

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True)
    employee_id = Column(Integer, index=True)
    rank = Column(String) # cashier, bagger
    status = Column(String, default="pending") # pending, accepted
    created_at = Column(DateTime, server_default=func.now())

class EmployeeHistory(Base):
    __tablename__ = "employee_history"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True)
    employee_id = Column(Integer, index=True)
    employee_name = Column(String)
    employee_store = Column(String)
    report = Column(String, nullable=True)
    achievement = Column(String, nullable=True)
    rank = Column(String)
    purpose = Column(String, nullable=True) # for removal reason etc
    date = Column(DateTime(timezone=True), server_default=func.now())