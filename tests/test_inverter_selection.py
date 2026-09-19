"""Focused regression check for inverter selection and persistence."""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch


def _install_dependency_stubs() -> None:
    """Install the small Home Assistant surface used by this regression check."""

    def module(name: str) -> types.ModuleType:
        stub = types.ModuleType(name)
        sys.modules[name] = stub
        return stub

    aiohttp = module("aiohttp")
    aiohttp.ClientError = Exception
    aiohttp.ClientSession = object

    voluptuous = module("voluptuous")

    class Required:
        def __init__(self, schema: str, default: Any = None) -> None:
            self.schema = schema
            self.default = default

    class Schema:
        def __init__(self, schema: dict[Any, Any]) -> None:
            self.schema = schema

    voluptuous.Required = Required
    voluptuous.Schema = Schema

    module("homeassistant")
    config_entries = module("homeassistant.config_entries")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__()

        def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "create_entry", **kwargs}

        async def async_set_unique_id(self, unique_id: str) -> None:
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            return None

        def async_update_reload_and_abort(
            self, entry: Any, *, data: dict[str, Any], reason: str
        ) -> dict[str, Any]:
            entry.data = data
            self.hass.reloads.append(entry.entry_id)
            return {"type": "abort", "reason": reason}

    config_entries.ConfigEntry = object
    config_entries.ConfigFlow = ConfigFlow

    const = module("homeassistant.const")
    const.Platform = type("Platform", (), {"SENSOR": "sensor"})
    core = module("homeassistant.core")
    core.HomeAssistant = object
    flow = module("homeassistant.data_entry_flow")
    flow.FlowResult = dict[str, Any]

    helpers = module("homeassistant.helpers")
    helpers.__path__ = []
    client = module("homeassistant.helpers.aiohttp_client")
    client.async_get_clientsession = lambda hass: hass.session

    selector = module("homeassistant.helpers.selector")

    class SelectOptionDict(dict[str, str]):
        def __init__(self, *, value: str, label: str) -> None:
            super().__init__(value=value, label=label)

    @dataclass(frozen=True)
    class SelectSelectorConfig:
        options: list[SelectOptionDict]
        multiple: bool = False
        mode: str | None = None

    @dataclass(frozen=True)
    class SelectSelector:
        config: SelectSelectorConfig

    selector.SelectOptionDict = SelectOptionDict
    selector.SelectSelector = SelectSelector
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.SelectSelectorMode = type("SelectSelectorMode", (), {"LIST": "list"})

    update = module("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __class_getitem__(cls, item: Any) -> type:
            return cls

    update.DataUpdateCoordinator = DataUpdateCoordinator
    update.UpdateFailed = Exception


_install_dependency_stubs()

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.solis_cloud_monitoring"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "solis_cloud_monitoring")]
sys.modules[PACKAGE] = package

config_flow = importlib.import_module(f"{PACKAGE}.config_flow")
const = importlib.import_module(f"{PACKAGE}.const")


class InverterSelectionRegressionTest(unittest.TestCase):
    def test_six_inverters_can_be_selected_and_selection_survives_reload(self) -> None:
        discovered = [
            {"sn": serial, "stationName": f"Station {serial}"}
            for serial in "ABCDEF"
        ]
        hass = types.SimpleNamespace(session=object(), reloads=[])
        credentials = {
            const.CONF_API_KEY: "key",
            const.CONF_API_SECRET: "secret",
        }

        with patch.object(
            config_flow.SolisCloudAPI,
            "get_inverter_list",
            AsyncMock(return_value=discovered),
        ):
            self.assertEqual(
                len(
                    asyncio.run(
                        config_flow.validate_api_credentials(
                            hass,
                            credentials[const.CONF_API_KEY],
                            credentials[const.CONF_API_SECRET],
                        )
                    )
                ),
                6,
            )
            flow = config_flow.SolisCloudConfigFlow()
            flow.hass = hass
            result = asyncio.run(flow.async_step_user(credentials))

        self.assertEqual(result["step_id"], "inverters")
        result = asyncio.run(
            flow.async_step_inverters({const.CONF_INVERTER_SERIALS: list("ABCDEF")})
        )
        self.assertEqual(
            result["errors"],
            {const.CONF_INVERTER_SERIALS: "too_many_inverters"},
        )
        result = asyncio.run(
            flow.async_step_inverters({const.CONF_INVERTER_SERIALS: ["UNKNOWN"]})
        )
        self.assertEqual(
            result["errors"], {const.CONF_INVERTER_SERIALS: "invalid_inverter_selection"}
        )
        result = asyncio.run(
            flow.async_step_inverters({const.CONF_INVERTER_SERIALS: []})
        )
        self.assertEqual(
            result["errors"], {const.CONF_INVERTER_SERIALS: "no_inverters_selected"}
        )

        result = asyncio.run(
            flow.async_step_inverters({const.CONF_INVERTER_SERIALS: ["B", "D"]})
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"][const.CONF_INVERTER_SERIALS], ["B", "D"])
        self.assertTrue(result["data"][const.CONF_INVERTER_SELECTION_CONFIGURED])

        client = sys.modules["homeassistant.helpers.aiohttp_client"]
        client.async_get_clientsession = lambda hass: hass.session
        spec = importlib.util.spec_from_file_location(
            PACKAGE,
            ROOT / "custom_components" / "solis_cloud_monitoring" / "__init__.py",
        )
        integration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integration)
        entry = types.SimpleNamespace(entry_id="entry", data=result["data"])
        entries = Mock()
        entries.async_forward_entry_setups = AsyncMock()
        runtime_hass = types.SimpleNamespace(
            data={}, config_entries=entries, session=object()
        )
        with patch.object(
            integration.SolisCloudAPI,
            "get_inverter_list",
            AsyncMock(side_effect=AssertionError("explicit selection was rediscovered")),
        ), patch.object(
            integration.SolisCloudDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new_callable=AsyncMock,
            create=True,
        ):
            self.assertTrue(asyncio.run(integration.async_setup_entry(runtime_hass, entry)))
        self.assertEqual(
            runtime_hass.data[const.DOMAIN][entry.entry_id].inverter_serials,
            ["B", "D"],
        )

        existing = types.SimpleNamespace(
            entry_id="existing",
            data={
                const.CONF_API_KEY: "saved-key",
                const.CONF_API_SECRET: "saved-secret",
                const.CONF_INVERTER_SERIALS: ["A", "B", "MISSING"],
            },
        )
        hass.config_entries = types.SimpleNamespace(
            async_get_entry=lambda entry_id: (
                existing if entry_id == existing.entry_id else None
            )
        )
        reconfigure = config_flow.SolisCloudConfigFlow()
        reconfigure.hass = hass
        reconfigure.context = {"entry_id": existing.entry_id}
        with patch.object(
            config_flow,
            "validate_api_credentials",
            AsyncMock(return_value=discovered[:2]),
        ) as validate:
            result = asyncio.run(reconfigure.async_step_reconfigure())
            self.assertNotIn("saved-key", repr(result["data_schema"].schema))
            self.assertNotIn("saved-secret", repr(result["data_schema"].schema))
            result = asyncio.run(
                reconfigure.async_step_reconfigure(
                    {const.CONF_INVERTER_SERIALS: ["B", "MISSING"]}
                )
            )
            validate.assert_awaited_once_with(hass, "saved-key", "saved-secret")

        self.assertEqual(result, {"type": "abort", "reason": "reconfigure_successful"})
        self.assertEqual(existing.data[const.CONF_INVERTER_SERIALS], ["B", "MISSING"])
        self.assertTrue(existing.data[const.CONF_INVERTER_SELECTION_CONFIGURED])
        self.assertEqual(hass.reloads, [existing.entry_id])

        failed_entry = types.SimpleNamespace(
            entry_id="failed",
            data={
                const.CONF_API_KEY: "saved-key",
                const.CONF_API_SECRET: "saved-secret",
                const.CONF_INVERTER_SERIALS: ["A", "B"],
            },
        )
        failed_flow = config_flow.SolisCloudConfigFlow()
        failed_flow.hass = hass
        failed_flow.context = {"entry_id": failed_entry.entry_id}
        hass.config_entries.async_get_entry = lambda entry_id: (
            failed_entry if entry_id == failed_entry.entry_id else None
        )
        original_data = dict(failed_entry.data)
        with patch.object(
            config_flow,
            "validate_api_credentials",
            AsyncMock(side_effect=config_flow.SolisCloudAPIError("unavailable")),
        ):
            result = asyncio.run(
                failed_flow.async_step_reconfigure(
                    {const.CONF_INVERTER_SERIALS: ["A"]}
                )
            )

        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(failed_entry.data, original_data)
        self.assertEqual(hass.reloads, [existing.entry_id])


if __name__ == "__main__":
    unittest.main()
