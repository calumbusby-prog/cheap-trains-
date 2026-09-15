from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from . import Notifier


class EmailNotifier(Notifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    def send(self, subject: str, message: str, html: Optional[str] = None) -> None:
        email_msg = EmailMessage()
        email_msg["Subject"] = subject
        email_msg["From"] = self.from_addr
        email_msg["To"] = ", ".join(self.to_addrs)
        email_msg.set_content(message)
        if html:
            email_msg.add_alternative(html, subtype="html")

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
            if self.use_tls:
                smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(email_msg)
