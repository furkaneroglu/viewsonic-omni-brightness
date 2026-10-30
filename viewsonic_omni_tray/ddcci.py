"""
ViewSonic OMNI DDC/CI Tray - Win32 DXVA2 Compatibility Wrapper
Geriye dönük uyumluluk için MonitorManager sınıfını dışa aktarır.
"""

from .monitor_manager import (
    MonitorManager,
    MonitorDevice,
    DDCCIError,
    DDCCIDisconnectedError,
    DDCCIUnsupportedError,
    PHYSICAL_MONITOR,
    DDCCI_ERROR_MESSAGES
)

# Geriye dönük takma ad
DDCCIBackend = MonitorManager

__all__ = [
    "MonitorManager",
    "MonitorDevice",
    "DDCCIError",
    "DDCCIDisconnectedError",
    "DDCCIUnsupportedError",
    "PHYSICAL_MONITOR",
    "DDCCI_ERROR_MESSAGES",
    "DDCCIBackend"
]
