"""
app/models.py
──────────────
SQLAlchemy ORM models mirroring the Lakebase schema defined in
infra/02_create_lakebase_schema.sql.

These are used by ui.py for type-safe data access and by the streaming
job for bulk inserts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Double,
    Index, Integer, String, Text, text,
)
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class Well(Base):
    __tablename__ = "wells"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    well_id  = Column(String, unique=True, nullable=False, index=True)
    name     = Column(String)
    field    = Column(String, default="MSEEL")
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self):
        return f"<Well {self.well_id}>"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("predictions_well_ts_idx", "well_id", "ts"),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    well_id     = Column(String, nullable=False)
    ts          = Column(DateTime(timezone=True), nullable=False)
    md          = Column(Double)
    rop_actual  = Column(Double)
    rop_pred    = Column(Double)
    rop_gap     = Column(Double)       # rop_pred - rop_actual
    mse         = Column(Double)
    hazard_flag = Column(String)
    created_at  = Column(DateTime(timezone=True), server_default=text("NOW()"))

    @property
    def rop_efficiency(self) -> Optional[float]:
        """Return rop_actual / rop_pred (clamped 0–1.5), or None."""
        if self.rop_pred and self.rop_pred > 0 and self.rop_actual is not None:
            return min(self.rop_actual / self.rop_pred, 1.5)
        return None

    def __repr__(self):
        return (
            f"<Prediction well={self.well_id} ts={self.ts} "
            f"rop_actual={self.rop_actual:.1f} rop_pred={self.rop_pred:.1f}>"
        )


class Alert(Base):
    __tablename__ = "alerts"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    well_id          = Column(String, nullable=False)
    ts               = Column(DateTime(timezone=True), nullable=False)
    alert_type       = Column(String, nullable=False)
    severity         = Column(String, nullable=False, default="WARNING")
    message          = Column(Text)
    acknowledged     = Column(Boolean, default=False)
    acknowledged_by  = Column(String)
    acknowledged_at  = Column(DateTime(timezone=True))

    @property
    def severity_icon(self) -> str:
        return {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}.get(
            self.severity, "⚪"
        )

    def __repr__(self):
        return f"<Alert {self.severity} well={self.well_id} ts={self.ts} type={self.alert_type}>"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    model_name   = Column(String, nullable=False)
    version      = Column(String, nullable=False)
    stage        = Column(String)
    rmse         = Column(Double)
    r2           = Column(Double)
    feature_list = Column(Text)        # JSON array string
    registered_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
