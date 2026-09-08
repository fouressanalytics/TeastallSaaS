import os
import smtplib
import logging
from email.mime.text import MIMEText

logger = logging.getLogger("teastall.email")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "no-reply@teastall.local")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8000")


def send_password_reset_email(to_email: str, token: str) -> None:
    """
    Sends the reset link by email. If SMTP isn't configured (e.g. in local
    dev), logs the link instead of raising, so signup/login flows never
    break because mail isn't set up yet.
    """
    reset_link = f"{FRONTEND_URL}/?reset_token={token}"
    body = (
        "We received a request to reset the password for your Tea Stall "
        "account.\n\n"
        f"Reset your password here (link expires in 1 hour):\n{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )

    if not SMTP_HOST:
        logger.warning("SMTP not configured — password reset link for %s: %s", to_email, reset_link)
        return

    msg = MIMEText(body)
    msg["Subject"] = "Reset your Tea Stall password"
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
    except Exception:
        # Never let a mail-server hiccup surface details to the client;
        # log it so you can investigate on the server.
        logger.exception("Failed to send password reset email to %s", to_email)
