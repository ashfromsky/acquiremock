from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_payment_otp_key(request: Request) -> str:
    ip = get_remote_address(request)
    payment_id = request.path_params.get("payment_id", "")
    return f"{ip}:{payment_id}"


def get_auth_email_key(request: Request) -> str:
    ip = get_remote_address(request)
    return f"{ip}:{request.url.path}"


limiter = Limiter(key_func=get_remote_address)
