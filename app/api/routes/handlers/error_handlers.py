from fastapi import Request
from fastapi.responses import JSONResponse
from app.models.errors import PaymentError

async def payment_error_handler(request: Request, exc: PaymentError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "payment_id": exc.payment_id
        }
    )