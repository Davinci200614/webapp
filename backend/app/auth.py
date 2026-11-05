import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from .db import connect

from . import config

Role = Literal["operator", "admin"]
_ITERATIONS = 240_000


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Invalid email")
        return value


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        ).hex()
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def provision_bootstrap() -> None:
    from . import config
    if not config.AUTH_BOOTSTRAP_EMAIL or not config.AUTH_BOOTSTRAP_PASSWORD:
        return
    try:
        credentials = LoginRequest(email=config.AUTH_BOOTSTRAP_EMAIL, password=config.AUTH_BOOTSTRAP_PASSWORD)
    except ValidationError:
        logging.getLogger(__name__).warning(
            'Administrator bootstrap skipped: check AUTH_BOOTSTRAP_EMAIL and '
            'AUTH_BOOTSTRAP_PASSWORD (12–256 characters). Public pages and the bot remain available.'
        )
        return
    with connect() as db:
        exists = db.execute(
            "SELECT 1 FROM operators WHERE email=?", (credentials.email,)
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO operators(email,password_hash,role) VALUES (?,?,?)",
                (credentials.email, _password_hash(credentials.password), "admin"),
            )


def login(credentials: LoginRequest) -> tuple[str, dict[str, str]]:
    with connect() as db:
        operator = db.execute(
            "SELECT id,email,role,password_hash FROM operators WHERE email=? AND active=1",
            (str(credentials.email).lower(),),
        ).fetchone()
        if not operator or not _verify_password(credentials.password, operator["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=config.AUTH_SESSION_TTL_HOURS)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db.execute(
            "INSERT INTO operator_sessions(token_hash,operator_id,expires_at) VALUES (?,?,?)",
            (token_hash, operator["id"], expires.isoformat()),
        )
    return token, {"email": operator["email"], "role": operator["role"]}


def logout(token: str) -> None:
    with connect() as db:
        db.execute(
            "DELETE FROM operator_sessions WHERE token_hash=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )


def _session_role(token: str) -> tuple[Role, str] | None:
    with connect() as db:
        row = db.execute(
            """SELECT o.role, o.email FROM operator_sessions s
               JOIN operators o ON o.id=s.operator_id
               WHERE s.token_hash=? AND o.active=1 AND datetime(s.expires_at) > CURRENT_TIMESTAMP""",
            (hashlib.sha256(token.encode()).hexdigest(),),
        ).fetchone()
    return (row["role"], row["email"]) if row else None


def current_role(authorization: Annotated[str | None, Header()] = None) -> Role:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    session = _session_role(token)
    if session:
        return session[0]
    if config.ADMIN_API_KEY and secrets.compare_digest(token, config.ADMIN_API_KEY):
        return "admin"
    if config.OPERATOR_API_KEY and secrets.compare_digest(token, config.OPERATOR_API_KEY):
        return "operator"
    raise HTTPException(status_code=401, detail="Invalid credentials")


def require_admin(role: Role = Depends(current_role)) -> Role:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return role
