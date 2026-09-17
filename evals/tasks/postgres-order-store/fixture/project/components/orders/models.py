"""Order persistence model."""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="NEW")
    payload = Column(String, nullable=False, default="{}")
