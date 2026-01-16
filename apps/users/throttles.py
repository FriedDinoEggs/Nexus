import time

from django.core.cache import cache
from rest_framework import throttling


class ResetPasswordThrottle(throttling.BaseThrottle):
    scope = 'reset_password'
    ttl = 10

    def allow_request(self, request, view) -> bool:
        ident = self.get_ident(request)
        path = request.path
        self.cache_key = f'throttle_{self.scope}_{ident}_{path}'

        last_request_time = cache.get(self.cache_key)
        current_time = time.time()

        if last_request_time and (current_time - last_request_time) < self.ttl:
            return False

        cache.set(self.cache_key, current_time, timeout=self.ttl)
        return True

    def wait(self) -> float | None:
        last_request_time = cache.get(self.cache_key)
        return max(0, self.ttl - (time.time() - last_request_time))
