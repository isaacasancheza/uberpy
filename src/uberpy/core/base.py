import random
from abc import ABC
from time import sleep
from typing import Any, Literal, NotRequired, TypedDict, Unpack
from urllib.parse import quote

import requests
from pydantic import BaseModel

type URL = str | int
type Body = dict | BaseModel
type Params = dict
type Method = Literal['GET', 'PUT', 'POST', 'PATCH', 'DELETE']
type Headers = dict
type APIVersion = Literal['v1']
type OAuthVersion = Literal['v2']

BASE_URL = 'https://api.uber.com/{version}/customers/{customer_id}'
OAUTH_URL = 'https://auth.uber.com/oauth'
DEFAULT_TIMEOUT = 10
DEFAULT_JITTER_MAX = 0.5
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRIABLE_HTTP_CODES = {
    401,
    429,
    500,
    502,
    503,
    504,
}


class OptionalArguments(TypedDict):
    params: NotRequired[Params | None]
    headers: NotRequired[Headers | None]


class Base(ABC):
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
        self._session = session or requests.Session()
        self._timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        self._api_root = BASE_URL.format(version=version, customer_id=customer_id)
        self._jitter_max = DEFAULT_JITTER_MAX if jitter_max is None else jitter_max
        self._max_retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries
        self._customer_id = customer_id
        self._access_token = access_token
        self._retriable_http_codes = (
            DEFAULT_RETRIABLE_HTTP_CODES
            if retriable_http_codes is None
            else retriable_http_codes
        )

    def _get(
        self,
        /,
        *args: URL,
        **kwargs: Unpack[OptionalArguments],
    ):
        return self._wrapper(
            *args,
            **kwargs,
            method='GET',
        )

    def _put(
        self,
        body: Body,
        /,
        *args: URL,
        **kwargs: Unpack[OptionalArguments],
    ):
        return self._wrapper(
            *args,
            **kwargs,
            body=body,
            method='PUT',
        )

    def _post(
        self,
        body: Body,
        /,
        *args: URL,
        **kwargs: Unpack[OptionalArguments],
    ):
        return self._wrapper(
            *args,
            **kwargs,
            body=body,
            method='POST',
        )

    def _patch(
        self,
        body: Body,
        /,
        *args: URL,
        **kwargs: Unpack[OptionalArguments],
    ):
        return self._wrapper(
            *args,
            **kwargs,
            body=body,
            method='PATCH',
        )

    def _delete(
        self,
        /,
        data: Body | None = None,
        *args: URL,
        **kwargs: Unpack[OptionalArguments],
    ):
        return self._wrapper(
            *args,
            **kwargs,
            body=data,
            method='DELETE',
        )

    def _wrapper(
        self,
        *args: URL,
        body: Body | None = None,
        params: Params | None = None,
        method: Method,
        headers: Headers | None = None,
    ) -> Any:
        retries = 0
        exception: Exception | None = None
        while retries <= self._max_retries:
            try:
                return self._request(
                    *args,
                    body=body,
                    params=params,
                    method=method,
                    headers=headers,
                )
            except requests.HTTPError as e:
                exception = e
                if e.response.status_code in self._retriable_http_codes:
                    backoff = min(2**retries, 20) + random.uniform(0, self._jitter_max)
                    # honor Retry-After if present (seconds), else exponential backoff with jitter
                    if retry_after := e.response.headers.get('Retry-After'):
                        try:
                            backoff = float(retry_after)
                        except (TypeError, ValueError):
                            pass
                    sleep(backoff)
                    retries += 1
                    continue
                raise
            except (requests.ConnectionError, requests.Timeout) as e:
                exception = e
                backoff = min(2**retries, 20) + random.uniform(0, self._jitter_max)
                sleep(backoff)
                retries += 1
                continue

        # linter
        assert exception

        raise exception

    def _request(
        self,
        *args: URL,
        body: Body | None = None,
        params: Params | None = None,
        method: Method,
        headers: Headers | None = None,
    ) -> Any:
        # copy headers to avoid mutating caller dict
        headers = {**(headers or {})}

        headers['Authorization'] = f'Bearer {self._access_token}'
        headers.setdefault('Accept', 'application/json')

        # safe URL join without double slashes and with path segment quoting
        path_segments = [self._api_root.rstrip('/')]
        path_segments.extend(quote(str(arg).strip('/'), safe='') for arg in args)
        url = '/'.join(path_segments)

        # serialize pydantic models
        if isinstance(body, BaseModel):
            body = body.model_dump(
                mode='json',
                exclude_none=True,
            )

        response = self._session.request(
            url=url,
            json=body,
            method=method,
            params=params,
            headers=headers,
            timeout=self._timeout,
        )

        response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return {}

        return response.json()

    @staticmethod
    def get_access_token(
        *,
        version: OAuthVersion = 'v2',
        client_id: str,
        client_secret: str,
    ) -> str:
        # oauth endpoint
        url = '/'.join([OAUTH_URL, version, 'token'])

        # data
        data = {
            'scope': 'eats.deliveries',
            'client_id': client_id,
            'grant_type': 'client_credentials',
            'client_secret': client_secret,
        }

        # request
        response = requests.post(
            url=url,
            data=data,
            timeout=DEFAULT_TIMEOUT,
        )

        # assert response
        response.raise_for_status()

        # decode jwt
        jwt = response.json()

        return jwt['access_token']
