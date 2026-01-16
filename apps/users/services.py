import logging
import random
from datetime import datetime
from datetime import timezone as dt_timezone

import uuid6
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import CacheKeyWarning, InvalidCacheKey, cache
from django.db import DatabaseError, InterfaceError, OperationalError, transaction
from django.urls.base import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import BlackListToken
from .tasks import (
    send_reset_password_mail_task,
    send_verification_mail_task,
    send_welcome_mail_task,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class UserVerificationServices:
    cache_verify_header: str = 'mail_verify:'
    cache_reset_pwd_header: str = 'mail_reset_pwd'

    @classmethod
    def send_verification_mail(cls, *, user, base_url: str) -> None:
        if not isinstance(user, User):
            logger.warning('send_verification_mail: user is not django User isinstance')
            raise TypeError(f'user must be django user istance, got {type(user)}')

        token: str = ''
        max_attempts: int = 3
        for _attempt_count in range(max_attempts):
            token = uuid6.uuid7().hex

            if cache.add(f'{cls.cache_verify_header}{token}', user.id, timeout=60 * 60):
                break
        else:
            raise RuntimeError('Generate token error')

        if not base_url:
            base_url = settings.SITE_BASEURL

        base_url.rstrip('/')
        path = reverse('v1:users:verification-detail', kwargs={'id': token})
        url = f'{base_url}{path}'
        send_verification_mail_task.delay(verification_url=url, to=user.email)

    @classmethod
    @transaction.atomic
    def verify_mail(cls, *, token: str) -> int:
        key = f'{cls.cache_verify_header}{token}'
        user_id = cache.get(key=key)
        cache.delete(key=key)

        update_count = User.objects.filter(pk=user_id).update(is_verified=True)

        if update_count != 0:
            email = User.objects.filter(pk=user_id).values_list('email', flat=True).first()
            send_welcome_mail_task.delay(to=email)
        else:
            logger.error(f'verify_mail: User {user_id} not found')
        return update_count

    @classmethod
    def send_reset_pwd_mail(cls, *, account: str):
        code: str | None = None
        max_attempts: int = 3
        for _attempt_count in range(max_attempts):
            code = f'{random.randint(0, 999999):06d}'

            if cache.set(account, f'{cls.cache_reset_pwd_header}{code}', timeout=60 * 15):
                break
        else:
            raise RuntimeError('Generate token error')

        send_reset_password_mail_task.delay(code=code, to=account)

    @classmethod
    def verify_reset_pwd(cls, *, code: str, account: str) -> bool:
        verification_code: str | None = None

        try:
            verification_code = cache.get(account)
            cache.delete(account)
        except Exception:
            raise

        if verification_code != f'{cls.cache_reset_pwd_header}{code}':
            return False

        return True


class BlackListService:
    blacklist_prefix: str = 'blacklisted_access'

    @classmethod
    def is_token_blacklisted(cls, token):
        if not token:
            return False

        token_jti = token.get('jti')
        if not token_jti:
            logger.warning('token missing jit claim')
            return False

        black_name = f'{cls.blacklist_prefix}:{token_jti}'

        try:
            is_blacklisted = cache.get(black_name)

            if is_blacklisted is not None:
                return True

            return False
        except Exception as e:
            logger.error(f'Redis connection failed when checking blacklist: {e}')
            logger.warning('Falling back to DB check for reliability.')

            try:
                return BlackListToken.objects.filter(token=black_name).exists()

            except Exception as db_e:
                logger.critical(f'Both Redis and DB are down= =: {db_e}')

                return False

    @classmethod
    def set_blacklisted(cls, *, user, token):
        if isinstance(token, AccessToken):
            token_jti = token['jti']
            token_exp_timestamp = float(token['exp'])
            current_timestamp = timezone.now().timestamp()
            utc_aware_dt = datetime.fromtimestamp(token_exp_timestamp, tz=dt_timezone.utc)

            ttl = int(token_exp_timestamp - current_timestamp)

            black_name = f'{cls.blacklist_prefix}:{token_jti}'

            if ttl <= 0:
                logger.debug('token JTI already expired, skipping cache')
            else:
                try:
                    cache.get_or_set(black_name, True, timeout=ttl)
                except (
                    CacheKeyWarning,
                    InvalidCacheKey,
                    ConnectionRefusedError,
                    TimeoutError,
                ) as e:
                    logger.error(f'Cache operation failed for token JTI {token_jti}!: {e}')
                except Exception as e:
                    logger.error(f'An unexpected cache error occurred!: {e}')

                try:
                    BlackListToken.objects.get_or_create(
                        token=black_name, defaults={'expires_at': utc_aware_dt, 'user': user}
                    )
                except (OperationalError, InterfaceError, DatabaseError):
                    logger.exception(
                        f'Database operation failed for token JTI {token_jti}.'
                        ' Token might remain valid temporarily= ='
                    )

        elif isinstance(token, RefreshToken):
            try:
                token.blacklist()
            except Exception as e:
                logger.exception(f'Failed to blacklist refresh token: {e}')
