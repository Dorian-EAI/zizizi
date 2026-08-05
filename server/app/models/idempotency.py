"""Persistent idempotency records for externally initiated write commands."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


class IdempotencyRequest(Base):
    """Bind one opaque client key to one principal, operation and request digest.

    The unique constraint deliberately omits ``operation``.  Reusing the same
    key for a different financial command by the same principal is a conflict,
    rather than silently creating a second side effect.
    """

    __tablename__ = "idempotency_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_type = Column(String(16), nullable=False)
    owner_id = Column(Integer, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)

    # processing/completed/failed.  A process crash leaves ``processing`` and
    # therefore fails closed instead of retrying an ambiguous money movement.
    status = Column(String(16), default="processing", nullable=False)
    response_json = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=True)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "idempotency_key",
            name="uq_idempotency_owner_key",
        ),
        Index("ix_idempotency_operation_created", "operation", "created_at"),
        Index("ix_idempotency_resource", "resource_type", "resource_id"),
    )
