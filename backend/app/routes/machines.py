from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from ..auth import Role, require_admin
from ..db import connect
from .. import config

router = APIRouter(prefix="/api")


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    machine_type: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    hourly_rate: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    available: bool = True
    owner_type: Literal["company", "partner"] = "company"
    reserved_for_own_use: bool = False
    available_from: date | None = None
    available_to: date | None = None
    compatibility_notes: str | None = Field(default=None, max_length=500)

    @field_validator("name", "machine_type")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be empty")
        return value.strip()

    @field_validator("location", "compatibility_notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_window(self):
        if self.available_from and self.available_to and self.available_from > self.available_to:
            raise ValueError("available_from must be on or before available_to")
        return self


class MachineUpdate(MachineCreate):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    machine_type: str | None = Field(default=None, min_length=1, max_length=120)
    available: bool | None = None
    owner_type: Literal["company", "partner"] | None = None
    reserved_for_own_use: bool | None = None

    @model_validator(mode="after")
    def validate_window(self):
        for name in ('name', 'machine_type', 'available', 'owner_type', 'reserved_for_own_use'):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        return self


def _mutations_enabled() -> None:
    if not config.MUTATIONS_ENABLED:
        raise HTTPException(status_code=503, detail="Mutations are disabled")


@router.get("/machines")
def list_machines():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM machines ORDER BY id DESC")]


@router.post("/machines", status_code=201)
def create_machine(payload: MachineCreate, _: Role = Depends(require_admin)):
    _mutations_enabled()
    data = payload.model_dump(mode="json")
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO machines(
                name, machine_type, location, hourly_rate, available, owner_type,
                reserved_for_own_use, available_from, available_to, compatibility_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"], data["machine_type"], data["location"], data["hourly_rate"],
                int(data["available"]), data["owner_type"], int(data["reserved_for_own_use"]),
                data["available_from"], data["available_to"], data["compatibility_notes"],
            ),
        )
        row = db.execute("SELECT * FROM machines WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@router.patch("/machines/{machine_id}")
def update_machine(
    machine_id: int,
    payload: MachineUpdate,
    _: Role = Depends(require_admin),
):
    _mutations_enabled()
    updates = payload.model_dump(mode="json", exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="At least one field is required")
    with connect() as db:
        row = db.execute("SELECT * FROM machines WHERE id=?", (machine_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Machine listing not found")
        start = updates.get("available_from", row["available_from"])
        end = updates.get("available_to", row["available_to"])
        if start and end and start > end:
            raise HTTPException(
                status_code=422,
                detail="available_from must be on or before available_to",
            )
        for field in ("available", "reserved_for_own_use"):
            if field in updates and updates[field] is not None:
                updates[field] = int(updates[field])
        assignments = ", ".join(f"{field}=?" for field in updates)
        db.execute(
            f"UPDATE machines SET {assignments} WHERE id=?",
            (*updates.values(), machine_id),
        )
        updated = db.execute("SELECT * FROM machines WHERE id=?", (machine_id,)).fetchone()
    return dict(updated)
