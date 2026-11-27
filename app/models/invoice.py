from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.sanitizer import (
    validate_redirect_url,
    validate_reference,
    validate_webhook_url,
)


def to_camel(snake_str: str) -> str:
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class CreateInvoiceRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Payment amount in minor currency units.")
    reference: str = Field(..., min_length=1, max_length=120, description="Merchant order reference.")
    webhook_url: str = Field(..., max_length=2048, description="URL for outgoing webhook notifications.")
    redirect_url: str = Field(..., max_length=2048, description="URL to redirect the customer after payment.")

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @field_validator("reference")
    @classmethod
    def check_reference(cls, value: str) -> str:
        return validate_reference(value)

    @field_validator("webhook_url")
    @classmethod
    def check_webhook_url(cls, value: str) -> str:
        return validate_webhook_url(value)

    @field_validator("redirect_url")
    @classmethod
    def check_redirect_url(cls, value: str) -> str:
        return validate_redirect_url(value)


class CreateInvoiceResponse(BaseModel):
    pageUrl: str = Field(..., description="Hosted checkout page URL.")
