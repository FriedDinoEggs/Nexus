from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import cache

from apps.core.services import MailServices

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=30 / 5 * 5, default_retries_delay=5, rate_limit='2/m')
def send_unified_mail_task(
    self, mail_type: str, to: str, verification_url: str = '', code: str = ''
):
    MAIL_LOCK_KEY = 'mail_services_lock'

    if not cache.add(MAIL_LOCK_KEY, 'locked', timeout=30):
        raise self.retry(countdown=5)

    try:
        match mail_type:
            case 'verify':
                assert verification_url != ''
                MailServices.send_verify_mail(verification_url=verification_url, to=to)
            case 'welcome':
                MailServices.send_welcome_mail(to=to)
            case 'reset_pwd':
                assert code != ''
                MailServices.send_reset_password_mail(code=code, to=to)
            case _:
                pass
    except Exception as e:
        raise self.retry(exc=e, countdown=60) from None
