import logging
import os
import string
import textwrap

import httpx
from dotenv import load_dotenv

from web.constants import DONT_SEND_EMAILS, MAILGUN_API_KEY

load_dotenv()
logger = logging.getLogger(__name__)

FROM_EMAIL_ADDRESS = "no-reply@skelmis.co.nz"
MAILGUN_API_URL = "https://api.mailgun.net/v3/skelmis.co.nz/messages"


async def send_email(
    to_address: str,
    subject: str,
    *,
    text: str = None,
    html: str = None,
    cc: list[str] = None,
    bcc: list[str] = None,
):
    if "PYTEST_CURRENT_TEST" in os.environ or DONT_SEND_EMAILS:
        print(
            f"Email to '{to_address}' with content: {repr(html) if html else repr(text)}"
            f"\n\tcc: {repr(cc)}\n\tbcc: {repr(bcc)}"
        )
        return

    # html takes preference over text when specified
    resp = httpx.post(
        MAILGUN_API_URL,
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": FROM_EMAIL_ADDRESS,
            "to": to_address,
            "subject": subject,
            "text": text,
            "html": html,
            "cc": cc,
            "bcc": bcc,
        },
    )
    if resp.status_code == 200:  # success
        logger.debug(
            f"Successfully sent an email to '{to_address}' via Mailgun API.",
            extra={"related_function": "Mailgun Integration"},
        )
    else:  # error
        logger.error(
            f"Could not send the email, reason: {resp.text}",
            extra={"related_function": "Mailgun Integration"},
        )
