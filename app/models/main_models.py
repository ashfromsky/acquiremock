from datetime import timedelta, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, SQLModel

import app.core.config as config
from app.core.time import utcnow

class PaymentStatus(str, Enum):
    PENDING = "pending"
    WAITING_FOR_OTP = "waiting_for_otp"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"

class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: str = Field(primary_key=True)
    amount: int = Field(sa_column=Column(BigInteger, nullable=False))
    reference: str = Field(index=True)
    webhook_url: str
    redirect_url: str
    status: str = Field(default=PaymentStatus.PENDING)
    otp_email: Optional[str] = Field(default=None)
    otp_code: Optional[str] = Field(default=None)
    otp_attempts: int = Field(default=0)
    otp_expires_at: Optional[datetime] = Field(default=None)
    otp_resend_count: int = Field(default=0)
    card_mask: Optional[str] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, index=True, unique=True)
    psp_transaction_id: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    webhook_attempts: int = Field(default=0)
    webhook_last_attempt: Optional[datetime] = Field(default=None)
    webhook_status: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: utcnow() + timedelta(minutes=config.PAYMENT_TTL_MINUTES)
    )
    paid_at: Optional[datetime] = Field(default=None)

class SuccessfulOperation(SQLModel, table=True):
    __tablename__ = "successful_operations"

    id: Optional[int] = Field(default=None, primary_key=True)
    payment_id: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    amount: int = Field(sa_column=Column(BigInteger, nullable=False))
    reference: str
    card_mask: str
    redirect_url: str
    created_at: datetime = Field(default_factory=utcnow)

class SavedCard(SQLModel, table=True):
    __tablename__ = "saved_cards"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    card_token: str
    card_hash: str
    cvv_hash: str
    expiry: str
    card_mask: str
    psp_provider: str = Field(default="mock")
    created_at: datetime = Field(default_factory=utcnow)

class WebhookLog(SQLModel, table=True):
    __tablename__ = "webhook_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    payment_id: str = Field(index=True)
    webhook_url: str
    payload: str
    response_status: Optional[int] = Field(default=None)
    response_body: Optional[str] = Field(default=None)
    signature: str
    attempt_number: int
    trigger: str = Field(default="auto")
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class AdminSession(SQLModel, table=True):
    __tablename__ = "admin_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, unique=True)
    username: str = Field(index=True)
    csrf_token: str
    expires_at: datetime = Field(index=True)
    revoked_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class IdempotencyRecord(SQLModel, table=True):
    __tablename__ = "idempotency_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    idempotency_key: str = Field(index=True, unique=True)
    payment_id: str = Field(index=True)
    request_fingerprint: str
    status: str = Field(default="in_progress")
    response_status: Optional[int] = Field(default=None)
    response_location: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuthChallenge(SQLModel, table=True):
    __tablename__ = "auth_challenges"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    code_hash: str
    attempts: int = Field(default=0)
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)