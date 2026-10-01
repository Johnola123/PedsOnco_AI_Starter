from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200), default="Default Project")
    original_name: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    object_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
