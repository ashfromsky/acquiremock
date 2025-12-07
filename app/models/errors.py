from fastapi import HTTPException
from typing import Optional

class PaymentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, payment_id: Optional[str] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.payment_id = payment_id
        super().__init__(self.message)

class PaymentNotFoundError(PaymentError):
    def __init__(self, payment_id: str):
        super().__init__(
            code="PAYMENT_NOT_FOUND",
            message=f"Payment {payment_id} not found",
            status_code=404,
            payment_id=payment_id
        )

class PaymentAlreadyProcessedError(PaymentError):
    def __init__(self, payment_id: str):
        super().__init__(
            code="PAYMENT_ALREADY_PROCESSED",
            message="Payment has already been processed",
            status_code=409,
            payment_id=payment_id
        )

class PaymentExpiredError(PaymentError):
    def __init__(self, payment_id: str):
        super().__init__(
            code="PAYMENT_EXPIRED",
            message="Payment session has expired",
            status_code=410,
            payment_id=payment_id
        )

class InsufficientFundsError(PaymentError):
    def __init__(self, payment_id: Optional[str] = None):
        super().__init__(
            code="INSUFFICIENT_FUNDS",
            message="Insufficient funds or invalid card",
            status_code=402,
            payment_id=payment_id
        )

class InvalidOTPError(PaymentError):
    def __init__(self, payment_id: str):
        super().__init__(
            code="INVALID_OTP",
            message="Invalid or expired OTP code",
            status_code=401,
            payment_id=payment_id
        )

class CSRFTokenMismatchError(PaymentError):
    def __init__(self, payment_id: Optional[str] = None):
        super().__init__(
            code="CSRF_TOKEN_MISMATCH",
            message="CSRF token validation failed",
            status_code=403,
            payment_id=payment_id
        )

class InvalidCardError(PaymentError):
    def __init__(self, payment_id: Optional[str] = None):
        super().__init__(
            code="INVALID_CARD",
            message="Invalid card details",
            status_code=400,
            payment_id=payment_id
        )

class SavedCardNotFoundError(PaymentError):
    def __init__(self, card_id: int):
        super().__init__(
            code="SAVED_CARD_NOT_FOUND",
            message=f"Saved card {card_id} not found",
            status_code=404
        )