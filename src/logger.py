
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any, List

import requests
import colorlog


def setup_logging() -> None:
    """Configure the centralised logging settings."""
    log_level = os.getenv('M3U_LOG_LEVEL', 'INFO').upper()
    log_file = os.getenv('M3U_LOG_FILE')
    max_bytes = int(os.getenv('LOG_FILE_MAX_BYTES', '10485760'))  # 10 MB
    backup_count = int(os.getenv('LOG_FILE_BACKUP_COUNT', '5'))
    postmark_api_token = os.getenv('POSTMARK_API_TOKEN')
    postmark_sender_email = os.getenv('POSTMARK_SENDER_EMAIL')
    postmark_receiver_emails = os.getenv('POSTMARK_RECEIVER_EMAILS')
    postmark_alert_subject = os.getenv('POSTMARK_ALERT_SUBJECT', 'Application Error Alert')

    # Create a custom logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    if not logger.hasHandlers():
        # Create handlers
        console_handler = logging.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)s:%(name)s:%(message)s",
            log_colors={
                'DEBUG': 'bold_blue',
                'INFO': 'bold_green',
                'WARNING': 'bold_yellow',
                'ERROR': 'bold_red',
                'CRITICAL': 'bold_purple'
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # Add file handler if LOG_FILE is specified
        if log_file:
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s - (%(filename)s:%(lineno)d)'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        # Add Postmark handler if credentials are available
        if postmark_api_token and postmark_sender_email and postmark_receiver_emails:
            postmark_handler = PostmarkHandler(
                api_token=postmark_api_token,
                sender_email=postmark_sender_email,
                receiver_emails=postmark_receiver_emails.split(','),
                subject=postmark_alert_subject
            )
            postmark_handler.setLevel(logging.ERROR)
            logger.addHandler(postmark_handler)


class PostmarkHandler(logging.Handler):
    """Custom logging handler to send error logs via PostmarkApp."""

    def __init__(self, api_token: str, sender_email: str, receiver_emails: List[str], subject: str) -> None:
        """
        Initialize the handler.

        Args:
            api_token: Postmark API token.
            sender_email: Sender email address.
            receiver_emails: List of receiver email addresses.
            subject: Subject line for the alert emails.
        """
        super().__init__()
        self.api_token = api_token
        self.sender_email = sender_email
        self.receiver_emails = receiver_emails
        self.subject = subject

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.

        Args:
            record: LogRecord to be sent as an email alert.
        """
        log_entry = self.format(record)
        payload = {
            'From': self.sender_email,
            'To': ','.join(self.receiver_emails),
            'Subject': self.subject,
            'TextBody': log_entry
        }
        headers = {
            'X-Postmark-Server-Token': self.api_token,
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post('https://api.postmarkapp.com/email', json=payload, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to send email alert: {e}")


# Ensure handlers and formatters are set up correctly
setup_logging()