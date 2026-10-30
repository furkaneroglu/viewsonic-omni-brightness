"""
ViewSonic OMNI DDC/CI Tray - Controller Compatibility Wrapper
Geriye dönük uyumluluk için AsyncWriteQueueWorker sınıfını dışa aktarır.
"""

from .queue_worker import AsyncWriteQueueWorker, MonitorStatus

# Geriye dönük takma ad
HardwareController = AsyncWriteQueueWorker

__all__ = [
    "AsyncWriteQueueWorker",
    "HardwareController",
    "MonitorStatus"
]
