from pydantic import BaseModel, Field, ConfigDict
import re

def to_camel(snake_str: str) -> str:
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

class CreateInvoiceRequest(BaseModel):
    amount: int = Field(..., description="Сума платежу в копійках/центах.")
    reference: str = Field(..., description="Унікальний референс замовлення.")
    webhook_url: str = Field(..., description="URL для відправки webhook-сповіщення.")
    redirect_url: str = Field(..., description="URL для перенаправлення клієнта після оплати.")

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

class CreateInvoiceResponse(BaseModel):
    pageUrl: str = Field(..., description="URL сторінки оплати.")