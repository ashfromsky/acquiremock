import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import aiosmtplib

load_dotenv()

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = os.getenv('SMTP_PORT')
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')

EMAIL_ENABLED = all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS])

if not EMAIL_ENABLED:
    logger.warning(
        "📧 Email service is DISABLED. SMTP credentials not configured. "
        "OTP codes will be logged to console instead. "
        "To enable emails, set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in .env"
    )


async def send_email(to_email: str, subject: str, html_content: str, text_content: str):
    if not EMAIL_ENABLED:
        logger.info(
            f"📧 Email SKIPPED (SMTP not configured)\n"
            f"   To: {to_email}\n"
            f"   Subject: {subject}\n"
            f"   Content: {text_content}"
        )
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")

    msg.attach(part1)
    msg.attach(part2)

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=int(SMTP_PORT),
            username=SMTP_USER,
            password=SMTP_PASS,
            use_tls=False,
            start_tls=True
        )
        logger.info(f"✅ Email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {e}", exc_info=True)


async def send_otp_email(to_email: str, otp_code: str):
    subject = "AcquireMock: Your Verification Code"
    template_path = Path("templates/misc/email-letter.html")

    if not EMAIL_ENABLED:
        logger.info(f"🔐 OTP Code for {to_email}: {otp_code}")
    else:
        logger.info(f"🔐 OTP Code sent to {to_email}")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        logger.warning(f"Email template not found at {template_path}")
        html_content = f"<h1>Code: {otp_code}</h1>"

    html_body = html_content.replace("{{ code }}", str(otp_code))
    text_body = f"Your verification code: {otp_code}"

    await send_email(to_email, subject, html_body, text_body)


async def send_receipt_email(to_email: str, payment_data: dict):
    subject = f"Payment Receipt for Order #{payment_data.get('reference')}"
    template_path = Path("templates/misc/receipt.html")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        logger.warning(f"Receipt template not found at {template_path}")
        html_content = "<h1>Payment Successful</h1>"

    replacements = {
        "{{ amount }}": str(payment_data.get('amount')),
        "{{ reference }}": str(payment_data.get('reference')),
        "{{ date }}": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "{{ card_mask }}": payment_data.get('card_mask', '****'),
        "{{ payment_id }}": payment_data.get('payment_id', '')
    }

    for key, value in replacements.items():
        html_content = html_content.replace(key, value)

    text_body = (
        f"Payment successful. "
        f"Amount: {payment_data.get('amount')} UAH. "
        f"Order: {payment_data.get('reference')}"
    )

    await send_email(to_email, subject, html_content, text_body)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(send_otp_email("test@example.com", "1234"))