"""Load the integration modules without running platform setup.

Run this directory separately from tests/: the legacy tests install dependency
stubs in sys.modules. Runtime checks must use real aiohttp/Home Assistant.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACKAGE = "custom_components.solis_cloud_monitoring"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "solis_cloud_monitoring")]
sys.modules[PACKAGE] = package
