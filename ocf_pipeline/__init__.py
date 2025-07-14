import importlib
import sys
from types import ModuleType

_module_names = [
    "config",
    "elexon_api",
    "elexon_data",
    "storage",
    "plotting",
    "streamlit_plotting",
]

for _name in _module_names:
    try:
        _mod: ModuleType = importlib.import_module(f".{_name}", package=__name__)
        sys.modules[f"{__name__}.{_name}"] = _mod
    except ModuleNotFoundError:
        pass

__all__ = _module_names 