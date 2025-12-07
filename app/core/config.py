import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')
CURRENCY_CODE = os.getenv('CURRENCY_CODE', 'USD')
CURRENCY_SYMBOL = os.getenv('CURRENCY_SYMBOL', '$')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'default_secret_key_change_in_production')