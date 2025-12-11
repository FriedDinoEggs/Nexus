import logging
from datetime import datetime
from datetime import timezone as dt_timezone

from django.core.cache import CacheKeyWarning, InvalidCacheKey, cache
from django.db import DatabaseError, InterfaceError, OperationalError
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import BlackListToken

logger = logging.getLogger(__name__)


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
                        f'Database operation failed for token JTI {token_jti}. Token might remain valid temporarily= ='
                    )

        elif isinstance(token, RefreshToken):
            try:
                token.blacklist()
            except Exception as e:
                logger.exception(f'Failed to blacklist refresh token: {e}')
