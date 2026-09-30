"""Regression checks using Home Assistant's real ConfigFlow and AbortFlow.

Only the registry and cloud calls are replaced. In particular, neither
async_set_unique_id nor _abort_if_unique_id_configured is stubbed out. Run in a
separate pytest process from the legacy tests that replace homeassistant itself.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import AbortFlow

from custom_components.solis_cloud_monitoring import config_flow
from custom_components.solis_cloud_monitoring.api import SolisCloudAPIError
from custom_components.solis_cloud_monitoring.const import (
    CONF_API_KEY, CONF_API_SECRET, CONF_INVERTER_SERIALS,
    CONF_INVERTER_SELECTION_CONFIGURED, DOMAIN,
)

CREDENTIALS = {CONF_API_KEY: "test-key", CONF_API_SECRET: "test-secret"}
INVERTERS = [{"sn": "A"}, {"sn": "B"}]


class Registry:
    def __init__(self):
        self.entries = {}
        self.progress = []
        self.flow = SimpleNamespace(async_progress_by_handler=self.progress_by_handler)

    def async_entry_for_domain_unique_id(self, domain, unique_id):
        return self.entries.get(unique_id)

    def async_entries(self, domain, include_ignore=False):
        return list(self.entries.values())

    def async_get_entry(self, entry_id):
        return next((e for e in self.entries.values() if e.entry_id == entry_id), None)

    def progress_by_handler(self, handler, include_uninitialized=False, match_context=None):
        return [
            flow for flow in self.progress
            if all(flow["context"].get(k) == v for k, v in (match_context or {}).items())
        ]

    def add_entry(self):
        entry = SimpleNamespace(
            entry_id="existing-entry", unique_id="test-key",
            source=config_entries.SOURCE_USER,
            state=config_entries.ConfigEntryState.LOADED,
            data={**CREDENTIALS, CONF_INVERTER_SERIALS: ["A"]},
            update_listeners=[],
        )
        self.entries["test-key"] = entry
        return entry


def new_flow(registry=None):
    registry = registry or Registry()
    flow = config_flow.SolisCloudConfigFlow()
    flow.hass = SimpleNamespace(config_entries=registry)
    flow.handler = DOMAIN
    flow.context = {"source": config_entries.SOURCE_USER}
    return flow, registry


def test_existing_entry_aborts_before_network_even_during_cloud_outage():
    flow, registry = new_flow()
    registry.add_entry()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=AssertionError("Network must not be contacted"))) as api:
        with pytest.raises(AbortFlow) as caught:
            asyncio.run(flow.async_step_user(CREDENTIALS))
    assert caught.value.reason == "already_configured"
    api.assert_not_awaited()


def test_parallel_flow_aborts_before_network():
    flow, registry = new_flow()
    registry.progress.append({"flow_id": "other-flow", "context": {
        "source": config_entries.SOURCE_USER, "unique_id": "test-key",
    }})
    with patch.object(config_flow, "validate_api_credentials", AsyncMock()) as api:
        with pytest.raises(AbortFlow) as caught:
            asyncio.run(flow.async_step_user(CREDENTIALS))
    assert caught.value.reason == "already_in_progress"
    api.assert_not_awaited()


def test_entry_created_during_validation_aborts_normally():
    flow, registry = new_flow()
    async def discover(*args):
        registry.add_entry()
        return INVERTERS
    with patch.object(config_flow, "validate_api_credentials", side_effect=discover):
        with pytest.raises(AbortFlow) as caught:
            asyncio.run(flow.async_step_user(CREDENTIALS))
    assert caught.value.reason == "already_configured"


def test_entry_created_while_selection_is_open_aborts_normally():
    flow, registry = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(return_value=INVERTERS)):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["step_id"] == "inverters"
    registry.add_entry()
    with pytest.raises(AbortFlow) as caught:
        asyncio.run(flow.async_step_inverters({CONF_INVERTER_SERIALS: ["A"]}))
    assert caught.value.reason == "already_configured"


def test_successful_setup_preserves_credentials_and_selection():
    flow, _ = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(return_value=INVERTERS)):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["step_id"] == "inverters"
    result = asyncio.run(flow.async_step_inverters({CONF_INVERTER_SERIALS: ["B"]}))
    assert result["type"] == "create_entry"
    assert result["data"] == {**CREDENTIALS, CONF_INVERTER_SERIALS: ["B"], CONF_INVERTER_SELECTION_CONFIGURED: True}


ERROR_KEYS = ["invalid_auth", "timeout", "server_error", "rate_limited", "invalid_response", "no_inverters", "api_error", "cannot_connect"]


@pytest.mark.parametrize("key", ERROR_KEYS)
def test_setup_uses_structured_error_key(key):
    flow, _ = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=SolisCloudAPIError("Safe error", error_key=key))):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["errors"] == {"base": key}
    assert result["step_id"] == "user"


@pytest.mark.parametrize("key", ERROR_KEYS)
def test_failed_reconfigure_reports_error_and_preserves_entry(key):
    flow, registry = new_flow()
    entry = registry.add_entry()
    before = dict(entry.data)
    flow.context = {"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=SolisCloudAPIError("Safe error", error_key=key))):
        result = asyncio.run(flow.async_step_reconfigure({CONF_INVERTER_SERIALS: ["B"]}))
    assert result["errors"] == {"base": key}
    assert entry.data == before


def test_unexpected_exception_still_reports_unknown():
    flow, _ = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=RuntimeError("Unexpected failure"))):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["errors"] == {"base": "unknown"}


def test_message_text_does_not_override_error_category():
    flow, _ = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=SolisCloudAPIError("Z0001 is not the actual code", error_key="server_error"))):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["errors"] == {"base": "server_error"}


def test_retry_after_transient_failure_can_complete_same_flow():
    flow, _ = new_flow()
    with patch.object(config_flow, "validate_api_credentials", AsyncMock(side_effect=[SolisCloudAPIError("Timeout", error_key="timeout"), INVERTERS])):
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
        assert result["errors"] == {"base": "timeout"}
        result = asyncio.run(flow.async_step_user(CREDENTIALS))
    assert result["step_id"] == "inverters"
