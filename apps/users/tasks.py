from celery import shared_task
from celery.utils.log import get_task_logger

from apps.core.services import MailServices

logger = get_task_logger(__name__)


@shared_task
def send_verification_mail_task(*, verification_url: str, to: str):
    MailServices.send_verify_mail(verification_url=verification_url, to=to)


@shared_task
def send_welcome_mail_task(*, to: str):
    MailServices.send_welcome_mail(to=to)
