import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import config
from ..auth import Role, current_role
from ..db import connect
from ..catalog import terms
from ..priority import machine_compatibility_for, priority_for

router = APIRouter(prefix="/api")


class StatusUpdate(BaseModel):
    status: Literal["pending_review", "approved", "rejected", "completed"]


class UrgencyVerification(BaseModel):
    reviewer: str = Field(min_length=1, max_length=80)

    @field_validator("reviewer")
    @classmethod
    def clean_reviewer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reviewer must not be empty")
        return value.strip()


def _mutations_enabled() -> None:
    if not config.MUTATIONS_ENABLED:
        raise HTTPException(status_code=503, detail="Mutations are disabled")


@router.get("/requests")
def list_requests(
    _: Role = Depends(current_role),
    status: str | None = Query(default=None),
    phone: str | None = Query(default=None),
):
    if status and status not in {"draft", "pending_review", "approved", "rejected", "completed"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    clauses: list[str] = []
    values: list[str] = []
    if status:
        clauses.append("status=?")
        values.append(status)
    if phone:
        clauses.append("farmer_phone=?")
        values.append(phone)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as db:
        rows = db.execute(
            f"SELECT * FROM requests{where} ORDER BY id DESC", values
        ).fetchall()
        machines = [dict(row) for row in db.execute("SELECT * FROM machines")]
        entries = terms(db)
    items = []
    for row in rows:
        item = {**dict(row), "payload": json.loads(row["payload"])}
        fit, reason, matches = machine_compatibility_for(item["payload"], machines, entries)
        item["machine_fit"] = fit
        item["machine_fit_reason"] = reason
        item["matching_machines"] = matches
        item["priority_score"], item["priority_reason"] = priority_for(
            item["payload"], item["created_at"], machine_fit=fit
        )
        items.append(item)
    return sorted(items, key=lambda item: (-item["priority_score"], -item["id"]))


@router.patch("/requests/{request_id}/urgency-verification")
def verify_urgency(
    request_id: int,
    payload: UrgencyVerification,
    _: Role = Depends(current_role),
):
    _mutations_enabled()
    with connect() as db:
        row = db.execute(
            "SELECT payload, status FROM requests WHERE id=?", (request_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["status"] != "pending_review":
            raise HTTPException(
                status_code=409,
                detail="Only requests pending review can have urgency verified",
            )
        request_payload = json.loads(row["payload"])
        if request_payload.get("urgency_level") not in {"urgent", "critical"}:
            raise HTTPException(
                status_code=409,
                detail="Only declared urgent requests need urgency verification",
            )
        request_payload["verified_by"] = payload.reviewer
        db.execute(
            "UPDATE requests SET payload=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(request_payload, ensure_ascii=False), request_id),
        )
    return {"id": request_id, "verified_by": payload.reviewer}


@router.patch("/requests/{request_id}/status")
def change_status(
    request_id: int,
    payload: StatusUpdate | None = None,
    status: str | None = Query(default=None),
    _: Role = Depends(current_role),
):
    _mutations_enabled()
    if payload is None:
        if status not in {'pending_review','approved','rejected','completed'}:
            raise HTTPException(422, 'Provide a valid JSON status or status query parameter')
        payload = StatusUpdate(status=status)
    allowed = {
        "pending_review": {"approved", "rejected"},
        "approved": {"completed", "rejected"},
        "rejected": set(),
        "completed": set(),
    }
    with connect() as db:
        row = db.execute("SELECT status FROM requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        current = row["status"]
        if current == "draft":
            raise HTTPException(status_code=409, detail="Draft must be confirmed first")
        if payload.status not in allowed.get(current, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Invalid status transition from {current} to {payload.status}",
            )
        db.execute(
            "UPDATE requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (payload.status, request_id),
        )
    return {"id": request_id, "status": payload.status}
