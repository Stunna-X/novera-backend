from sqlalchemy import Column, Integer, String, Date
from backend.app.db.base import Base


class Usage(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    api_key = Column(String, index=True, nullable=False)
    date = Column(Date, nullable=False)
    count = Column(Integer, default=0, nullable=False)
