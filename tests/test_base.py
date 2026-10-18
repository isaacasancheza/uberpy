from unittest.mock import MagicMock

import requests

from uberpy import UberDirect


def _response(
    status_code: int,
    /,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.content = b'{}'
    response.headers = {}
    response.json.return_value = {}
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            response=response,
        )
    return response


def _client(
    *,
    access_token,
    session: MagicMock,
) -> UberDirect:
    return UberDirect(
        version='v1',
        session=session,
        jitter_max=0,
        customer_id='customer',
        access_token=access_token,
    )


def _authorizations(
    session: MagicMock,
    /,
) -> list[str]:
    return [
        call.kwargs['headers']['Authorization']
        for call in session.request.call_args_list
    ]


def test_string_access_token():
    session = MagicMock()
    session.request.return_value = _response(200)

    client = _client(
        session=session,
        access_token='token',
    )
    client.deliveries._get('deliveries')

    assert _authorizations(session) == [
        'Bearer token',
    ]


def test_callable_access_token_is_called_on_every_request(monkeypatch):
    monkeypatch.setattr('uberpy.core.base.sleep', lambda _: None)

    tokens = iter(
        [
            'expired',
            'rotated',
            'rotated',
        ],
    )
    session = MagicMock()
    session.request.side_effect = [
        _response(401),
        _response(200),
        _response(200),
    ]

    client = _client(
        session=session,
        access_token=lambda: next(tokens),
    )
    client.deliveries._get('deliveries')
    client.quotes._get('quotes')

    assert _authorizations(session) == [
        'Bearer expired',
        'Bearer rotated',
        'Bearer rotated',
    ]
