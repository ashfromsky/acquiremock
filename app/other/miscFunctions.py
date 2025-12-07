def validate_otp(payment, input_code: str) -> bool:
    stored_code = getattr(payment, 'otp_code', None)

    if not stored_code:
        return False

    if input_code != stored_code:
        return False

    return True