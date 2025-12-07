from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

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
    amount: float
    reference: str = Field(index=True)
    webhook_url: str
    redirect_url: str
    status: str = Field(default=PaymentStatus.PENDING)
    otp_email: Optional[str] = Field(default=None)
    otp_code: Optional[str] = Field(default=None)
    card_mask: Optional[str] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, index=True)
    psp_transaction_id: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    webhook_attempts: int = Field(default=0)
    webhook_last_attempt: Optional[datetime] = Field(default=None)
    webhook_status: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))
    paid_at: Optional[datetime] = Field(default=None)

class SuccessfulOperation(SQLModel, table=True):
    __tablename__ = "successful_operations"

    id: Optional[int] = Field(default=None, primary_key=True)
    payment_id: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    amount: float
    reference: str
    card_mask: str
    redirect_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)