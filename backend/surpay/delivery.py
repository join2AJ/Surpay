"""Sending one-time codes by email (SMTP) and text message (Twilio). Returns False if not set up."""

import logging
import smtplib
from email.message import EmailMessage

import httpx

from . import config

log = logging.getLogger(__name__)


def email_ready() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def sms_ready() -> bool:
    return bool(config.TWILIO_SID and config.TWILIO_TOKEN and config.TWILIO_FROM)


def send_email(to: str, subject: str, body: str) -> bool:
    if not email_ready():
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - report as not sent; the caller tells the user
        log.exception("email to %s failed", to)
        return False


def send_sms(to: str, body: str) -> bool:
    if not sms_ready():
        return False
    try:
        r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_SID}/Messages.json",
                       auth=(config.TWILIO_SID, config.TWILIO_TOKEN),
                       data={"From": config.TWILIO_FROM, "To": to, "Body": body}, timeout=20)
        return r.status_code < 300
    except Exception:  # noqa: BLE001
        log.exception("sms to %s failed", to)
        return False
