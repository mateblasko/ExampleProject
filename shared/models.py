from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

db = SQLAlchemy()

class Coin(db.Model):
    __tablename__ = 'coins'

    symbol: Mapped[str] = mapped_column(primary_key=True)
    
    price = db.relationship('Price', back_populates='coin')
    open_interest = db.relationship('OpenInterest', back_populates='coin')
    base_volume = db.relationship('BaseVolume', back_populates='coin')

class Price(db.Model):
    __tablename__ = 'price'

    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    coin_symbol: Mapped[str] = mapped_column(db.ForeignKey('coins.symbol'), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[float]

    coin = db.relationship('Coin', back_populates='price')

class OpenInterest(db.Model): 
    __tablename__ = 'open_interest'

    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    coin_symbol: Mapped[str] = mapped_column(db.ForeignKey('coins.symbol'), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open_interest: Mapped[float]
    percentage_change: Mapped[float]

    coin = db.relationship('Coin', back_populates='open_interest')

class BaseVolume(db.Model):
    __tablename__ = 'base_volume'

    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    coin_symbol: Mapped[str] = mapped_column(db.ForeignKey('coins.symbol'), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    volume: Mapped[float]
    percentage_change: Mapped[float]

    coin = db.relationship('Coin', back_populates='base_volume')