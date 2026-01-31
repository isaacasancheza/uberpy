import requests

from uberpy.core.base import APIVersion, Base
from uberpy.core.deliveries import Deliveries
from uberpy.core.quotes import Quotes


class UberDirect(Base):
    def __init__(
        self,
        *,
        customer_id: str,
        access_token: str,
        version: APIVersion,
        timeout: float | None = None,
        session: requests.Session | None = None,
        jitter_max: float | None = None,
        max_retries: int | None = None,
        retriable_http_codes: set[int] | None = None,
    ) -> None:
        session = session or requests.Session()
        super().__init__(
            customer_id=customer_id,
            access_token=access_token,
            version=version,
            timeout=timeout,
            session=session,
            jitter_max=jitter_max,
            max_retries=max_retries,
            retriable_http_codes=retriable_http_codes,
        )
        self.quotes = Quotes(
            customer_id=customer_id,
            access_token=access_token,
            version=version,
            timeout=timeout,
            session=session,
            jitter_max=jitter_max,
            max_retries=max_retries,
            retriable_http_codes=retriable_http_codes,
        )
        self.deliveries = Deliveries(
            customer_id=customer_id,
            access_token=access_token,
            version=version,
            timeout=timeout,
            session=session,
            jitter_max=jitter_max,
            max_retries=max_retries,
            retriable_http_codes=retriable_http_codes,
        )
