"""Durable idempotency handling for financial write requests.

Claims are committed before the business operation starts.  This is
intentional: an unexpected process exit or an indeterminate provider response
must leave a durable ``processing`` record that blocks a second money movement.
Operations that complete (or fail in a known way) persist their exact response,
which is replayed for the same key and request digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import logging
import re
from typing import Any, Mapping, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.idempotency import IdempotencyRequest


logger = logging.getLogger(__name__)
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{7,127}$")


@dataclass(frozen=True)
class IdempotencyClaim:
    record_id: int
    key: str
    replay_response: Optional[dict] = None

    @property
    def is_replay(self) -> bool:
        return self.replay_response is not None


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        # Financial endpoints should normally pass integer cents.  Keeping a
        # stable decimal string here prevents platform-specific JSON floats.
        return format(Decimal(str(value)), "f")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def request_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _canonical_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_key(
    raw_key: Optional[str],
    *,
    owner_type: str,
    owner_id: int,
    operation: str,
    digest: str,
) -> str:
    if raw_key is None or not raw_key.strip():
        if settings.is_deployed:
            raise HTTPException(
                status_code=428,
                detail="该资金操作必须提供 Idempotency-Key 请求头",
            )
        # Development/testing compatibility for legacy clients.  Deployed
        # environments never take this path.  Identical legacy requests are
        # intentionally deduplicated rather than risking duplicate charges.
        seed = f"{owner_type}:{owner_id}:{operation}:{digest}".encode("utf-8")
        return "legacy-" + hashlib.sha256(seed).hexdigest()

    key = raw_key.strip()
    if not _KEY_RE.fullmatch(key):
        raise HTTPException(
            status_code=400,
            detail=(
                "Idempotency-Key 必须为 8-128 位，"
                "且仅包含字母、数字、点、下划线、冒号或连字符"
            ),
        )
    return key


def _decode_json(raw: Optional[str]) -> dict:
    if not raw:
        raise HTTPException(status_code=409, detail="幂等记录缺少可重放结果，请人工核对")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="幂等记录损坏，请人工核对")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=409, detail="幂等记录格式错误，请人工核对")
    return payload


def _resolve_existing(
    record: IdempotencyRequest,
    *,
    operation: str,
    digest: str,
) -> IdempotencyClaim:
    if record.operation != operation or record.request_hash != digest:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key 已绑定其他操作或请求参数",
        )
    if record.status == "completed":
        return IdempotencyClaim(
            record_id=record.id,
            key=record.idempotency_key,
            replay_response=_decode_json(record.response_json),
        )
    if record.status == "failed":
        error = _decode_json(record.response_json)
        raise HTTPException(
            status_code=int(record.response_status or 500),
            detail=error.get("detail", "此前相同请求已失败"),
        )
    raise HTTPException(
        status_code=409,
        detail="相同幂等请求正在处理或结果未知，请勿重复发起资金操作",
    )


def claim_financial_request(
    db: Session,
    *,
    raw_key: Optional[str],
    owner_type: str,
    owner_id: int,
    operation: str,
    payload: Mapping[str, Any],
) -> IdempotencyClaim:
    """Claim a client key, or replay/reject the already persisted claim."""
    digest = request_digest(payload)
    key = _resolve_key(
        raw_key,
        owner_type=owner_type,
        owner_id=owner_id,
        operation=operation,
        digest=digest,
    )

    existing = (
        db.query(IdempotencyRequest)
        .filter(
            IdempotencyRequest.owner_type == owner_type,
            IdempotencyRequest.owner_id == owner_id,
            IdempotencyRequest.idempotency_key == key,
        )
        .with_for_update()
        .first()
    )
    if existing:
        return _resolve_existing(existing, operation=operation, digest=digest)

    record = IdempotencyRequest(
        owner_type=owner_type,
        owner_id=owner_id,
        idempotency_key=key,
        operation=operation,
        request_hash=digest,
        status="processing",
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        return IdempotencyClaim(record_id=record.id, key=key)
    except IntegrityError:
        # A concurrent request won the unique-key race.  Resolve its durable
        # state with exactly the same operation/digest checks.
        db.rollback()
        existing = (
            db.query(IdempotencyRequest)
            .filter(
                IdempotencyRequest.owner_type == owner_type,
                IdempotencyRequest.owner_id == owner_id,
                IdempotencyRequest.idempotency_key == key,
            )
            .first()
        )
        if not existing:
            raise HTTPException(status_code=409, detail="幂等请求并发冲突，请稍后查询结果")
        return _resolve_existing(existing, operation=operation, digest=digest)


def complete_financial_request(
    db: Session,
    claim: IdempotencyClaim,
    response: dict,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> dict:
    """Persist the exact successful response and commit outstanding work."""
    record = (
        db.query(IdempotencyRequest)
        .filter(IdempotencyRequest.id == claim.record_id)
        .with_for_update()
        .first()
    )
    if not record or record.status != "processing":
        db.rollback()
        raise HTTPException(status_code=409, detail="幂等请求状态异常，请人工核对")
    record.status = "completed"
    record.response_status = 200
    record.response_json = json.dumps(
        jsonable_encoder(response),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    record.resource_type = resource_type
    record.resource_id = str(resource_id)[:64] if resource_id is not None else None
    record.completed_at = datetime.utcnow()
    db.commit()
    return response


def fail_financial_request(
    db: Session,
    claim: IdempotencyClaim,
    exc: Exception,
) -> None:
    """Rollback current work and durably remember a known failure response."""
    db.rollback()
    try:
        record = (
            db.query(IdempotencyRequest)
            .filter(IdempotencyRequest.id == claim.record_id)
            .with_for_update()
            .first()
        )
        if not record or record.status != "processing":
            db.rollback()
            return
        if isinstance(exc, HTTPException):
            status_code = int(exc.status_code)
            detail = exc.detail
        else:
            status_code = 500
            detail = "资金请求处理失败，请使用原幂等键查询或联系运营核对"
        record.status = "failed"
        record.response_status = status_code
        record.response_json = json.dumps(
            jsonable_encoder({"detail": detail}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        record.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to persist financial idempotency failure")
