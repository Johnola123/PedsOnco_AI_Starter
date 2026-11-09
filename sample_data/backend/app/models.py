from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200), default="Default Project", index=True)
    original_name: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    object_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["DatasetSource | None"] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", uselist=False
    )
    profile: Mapped["DatasetProfile | None"] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", uselist=False
    )


class DatasetSource(Base):
    __tablename__ = "dataset_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), default="browser")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dataset: Mapped[Dataset] = relationship(back_populates="source")


class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), unique=True, index=True)
    format_name: Mapped[str] = mapped_column(String(50), default="unknown")
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    profile_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dataset: Mapped[Dataset] = relationship(back_populates="profile")


class CohortMerge(Base):
    __tablename__ = "cohort_merges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    source_cohorts_json: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="logical_merge")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CohortWorkspaceRecord(Base):
    __tablename__ = "cohort_workspace_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200), index=True)
    record_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(250))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
