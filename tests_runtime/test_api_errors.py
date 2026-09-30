"""API boundary tests using real aiohttp exceptions and no network access."""
import asyncio
import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from custom_components.solis_cloud_monitoring.api import SolisCloudAPI, SolisCloudAPIError
from custom_components.solis_cloud_monitoring.const import API_BASE_URL, API_INVERTER_LIST

SECRET = "PRIVATE_RESPONSE_MUST_NOT_BE_LOGGED"


def client_for(*, status=200, payload=None, text=None, failure=None):
    response = Mock(status=status)
    response.text = AsyncMock(return_value=text if text is not None else json.dumps(payload))
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=response, side_effect=failure)
    context.__aexit__ = AsyncMock(return_value=False)
    session = Mock()
    session.post.return_value = context
    return SolisCloudAPI("test-key", "test-secret", session), session, response


def request(client):
    return asyncio.run(client._request(API_INVERTER_LIST, {"pageSize": "100"}))


@pytest.mark.parametrize("status,key", [
    (401, "invalid_auth"), (403, "invalid_auth"), (404, "cannot_connect"),
    (429, "rate_limited"), (500, "server_error"), (502, "server_error"),
    (503, "server_error"), (504, "server_error"),
])
def test_http_errors_are_structured_without_reading_response_body(status, key):
    client, session, response = client_for(status=status, text=SECRET)
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    error = caught.value
    assert error.error_key == key
    assert error.http_status == status
    assert SECRET not in str(error)
    response.text.assert_not_awaited()
    session.post.assert_called_once()  # No hidden immediate retries.


@pytest.mark.parametrize("code,key", [("Z0001", "invalid_auth"), ("B0115", "api_error"), ("Z9999", "api_error")])
def test_api_codes_not_remote_messages_determine_error(code, key):
    client, _, _ = client_for(payload={"code": code, "msg": SECRET, "data": None})
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == key
    assert caught.value.api_code == code
    assert SECRET not in str(caught.value)


def test_auth_like_text_does_not_misclassify_other_api_error():
    client, _, _ = client_for(payload={"code": "B0115", "msg": "Z0001 " + SECRET})
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == "api_error"
    assert "Z0001" not in str(caught.value)


def test_arbitrary_api_code_is_not_logged():
    client, _, _ = client_for(payload={"code": SECRET, "msg": SECRET})
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.api_code is None
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("payload", [None, [], "string", {}, {"code": None}, {"code": False}, {"code": []}])
def test_malformed_envelope(payload):
    client, _, _ = client_for(payload=payload)
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == "invalid_response"


def test_invalid_json_is_not_logged():
    client, _, _ = client_for(text="<html>" + SECRET + "</html>")
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == "invalid_response"
    assert SECRET not in str(caught.value)


def test_request_timeout_not_mislabeled_as_connect_timeout():
    client, _, _ = client_for(failure=TimeoutError(SECRET))
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == "timeout"
    assert "request timed out" in str(caught.value)
    assert SECRET not in str(caught.value)


def test_network_error_does_not_echo_connection_details():
    client, _, _ = client_for(failure=aiohttp.ClientConnectionError(SECRET))
    with pytest.raises(SolisCloudAPIError) as caught:
        request(client)
    assert caught.value.error_key == "cannot_connect"
    assert SECRET not in str(caught.value)


def test_cancellation_propagates():
    client, _, _ = client_for(failure=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        request(client)


@pytest.mark.parametrize("code", ["0", 0])
def test_success_preserves_data_and_signed_post(code):
    data = {"page": {"records": [{"sn": "A"}]}}
    client, session, _ = client_for(payload={"code": code, "data": data})
    assert request(client) == data
    args, kwargs = session.post.call_args
    assert args == (API_BASE_URL + API_INVERTER_LIST,)
    headers = kwargs["headers"]
    body = kwargs["data"]
    md5 = base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
    assert headers["Content-MD5"] == md5
    to_sign = f"POST\n{md5}\napplication/json\n{headers['Date']}\n{API_INVERTER_LIST}"
    signature = base64.b64encode(hmac.new(b"test-secret", to_sign.encode(), hashlib.sha1).digest()).decode()
    assert headers["Authorization"] == "API test-key:" + signature


@pytest.mark.parametrize("data,key", [
    (None, "invalid_response"), ({}, "invalid_response"),
    ({"page": []}, "invalid_response"), ({"page": {}}, "invalid_response"),
    ({"page": {"records": None}}, "invalid_response"),
    ({"page": {"records": []}}, "no_inverters"),
    ({"page": {"records": [None]}}, "invalid_response"),
    ({"page": {"records": [{"sn": "  "}]}}, "invalid_response"),
    ({"page": {"records": [{"sn": 123}]}}, "invalid_response"),
])
def test_inverter_list_validation(data, key):
    client, _, _ = client_for()
    with patch.object(client, "_request", AsyncMock(return_value=data)):
        with pytest.raises(SolisCloudAPIError) as caught:
            asyncio.run(client.get_inverter_list())
    assert caught.value.error_key == key


def test_inverter_serials_still_normalized_and_deduplicated():
    data = {"page": {"records": [{"sn": " A ", "model": "first"}, {"sn": "A"}, {"sn": "B"}]}}
    client, _, _ = client_for()
    with patch.object(client, "_request", AsyncMock(return_value=data)):
        assert asyncio.run(client.get_inverter_list()) == [{"sn": "A", "model": "first"}, {"sn": "B"}]


@pytest.mark.parametrize("method", ["get_inverter_details", "get_station_details"])
@pytest.mark.parametrize("data", [None, {}, [], "not a mapping", [1]])
def test_invalid_detail_payloads_become_handled_api_errors(method, data):
    client, _, _ = client_for()
    with patch.object(client, "_request", AsyncMock(return_value=data)):
        with pytest.raises(SolisCloudAPIError) as caught:
            asyncio.run(getattr(client, method)("test-id"))
    assert caught.value.error_key == "invalid_response"


@pytest.mark.parametrize("method", ["get_inverter_details", "get_station_details"])
def test_valid_detail_payload_unchanged(method):
    data = {"pac": 1.5, "stationId": "example"}
    client, _, _ = client_for()
    with patch.object(client, "_request", AsyncMock(return_value=data)):
        assert asyncio.run(getattr(client, method)("test-id")) == data
