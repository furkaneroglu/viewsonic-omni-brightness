"""
ViewSonic OMNI DDC/CI Tray - MonitorManager (Donanım Katmanı)
Windows High-Level Monitor Configuration API (Dxva2) ve Low-Level VCP DDC/CI arayüzü.
"""

import sys
import ctypes
from ctypes import wintypes
from typing import List, Dict, Optional, Tuple

# Win32 / DXVA2 DDC/CI Hata Kodları ve Anlaşılır Açıklamaları
DDCCI_ERROR_MESSAGES = {
    0xC0262582: "Monitörden geçersiz veya bozuk DDC/CI verisi alındı (ERROR_GRAPHICS_DDCCI_INVALID_DATA).",
    0xC0262584: "Monitör bu VCP özelliğini (Luminance/Parlaklık) desteklemiyor (ERROR_GRAPHICS_DDCCI_VCP_NOT_SUPPORTED).",
    0xC0262585: "I2C veri aktarım hatası (ERROR_GRAPHICS_I2C_ERROR_TRANSMITTING_DATA). Monitör I2C sinyallerine yanıt vermedi.",
    0xC0262586: "I2C veri alma hatası (ERROR_GRAPHICS_I2C_ERROR_RECEIVING_DATA).",
    0xC0262587: "Monitör geçersiz zamanlama durumu döndürdü (ERROR_GRAPHICS_DDCCI_MONITOR_RETURNED_INVALID_TIMING_STATUS_BYTE).",
    0xC0262588: "DDC/CI yetenekler dizgisi okunamadı (ERROR_GRAPHICS_DDCCI_INVALID_CAPABILITIES_STRING).",
    31: "Cihaz yanıt vermiyor (ERROR_GEN_FAILURE). Monitör uyku modunda olabilir veya OSD menüsünde DDC/CI kapalı.",
    6: "Geçersiz tanıtıcı (ERROR_INVALID_HANDLE). Monitör uyku/uyanma sonrası tanıtıcı sıfırlanmış olabilir.",
    1460: "I2C/DDC iletişim zaman aşımına uğradı (ERROR_TIMEOUT).",
}

class DDCCIError(Exception):
    """DDC/CI genel donanım hatası."""
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code

class DDCCIDisconnectedError(DDCCIError):
    """Monitör uyku moduna geçtiğinde, DPMS kapandığında veya kablo koptuğunda fırlatılır."""
    pass

class DDCCIUnsupportedError(DDCCIError):
    """Monitör VCP parlaklık özelliğini desteklemediğinde fırlatılır."""
    pass


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)
    ]


class MonitorDevice:
    """Tek bir fiziksel monitörün özelliklerini ve durumunu temsil eden veri modeli."""
    def __init__(
        self,
        index: int,
        hmonitor: wintypes.HMONITOR,
        description: str,
        current_brightness: int,
        min_brightness: int = 0,
        max_brightness: int = 100,
        capabilities_string: str = ""
    ):
        self.index = index
        self.hmonitor = hmonitor
        self.description = description
        self.current_brightness = current_brightness
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.capabilities_string = capabilities_string
        desc_lower = description.lower()
        self.is_viewsonic = "viewsonic" in desc_lower or "vx2718" in desc_lower or "omni" in desc_lower

    @property
    def supports_luminance(self) -> bool:
        """Monitörün yetenek dizgisinde VCP 0x10 (Luminance) desteğini kontrol eder."""
        if not self.capabilities_string:
            return True # String alınamadıysa ama GetMonitorBrightness çalıştıysa destekleniyor kabul edilir
        caps = self.capabilities_string.lower()
        return "10" in caps or "luminance" in caps

    def __repr__(self):
        return f"<MonitorDevice #{self.index}: '{self.description}' (%{self.current_brightness})>"


class MonitorManager:
    """
    Windows Dxva2 ve User32 API'lerini doğrudan sarmalayan,
    monitör algılama, VCP yetenek denetimi (capabilities) ve get/set brightness
    işlemlerini yöneten donanım soyutlama katmanı.
    """

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("MonitorManager yalnızca Windows işletim sisteminde (Dxva2 API) çalışır.")

        self.user32 = ctypes.windll.user32
        self.dxva2 = ctypes.windll.dxva2
        self._init_api_signatures()

    def _init_api_signatures(self):
        # Dxva2 Win32 Fonksiyon İmzaları
        self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
            wintypes.HMONITOR,
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL

        self.dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [
            wintypes.HMONITOR,
            wintypes.DWORD,
            ctypes.POINTER(PHYSICAL_MONITOR)
        ]
        self.dxva2.GetPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL

        self.dxva2.GetMonitorBrightness.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.dxva2.GetMonitorBrightness.restype = wintypes.BOOL

        self.dxva2.SetMonitorBrightness.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD
        ]
        self.dxva2.SetMonitorBrightness.restype = wintypes.BOOL

        self.dxva2.GetCapabilitiesStringLength.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.dxva2.GetCapabilitiesStringLength.restype = wintypes.BOOL

        self.dxva2.CapabilitiesRequestAndCapabilitiesReply.argtypes = [
            wintypes.HANDLE,
            ctypes.c_char_p,
            wintypes.DWORD
        ]
        self.dxva2.CapabilitiesRequestAndCapabilitiesReply.restype = wintypes.BOOL

        self.dxva2.DestroyPhysicalMonitors.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(PHYSICAL_MONITOR)
        ]
        self.dxva2.DestroyPhysicalMonitors.restype = wintypes.BOOL

        self.MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM
        )
        self.user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC,
            ctypes.c_void_p,
            self.MONITORENUMPROC,
            wintypes.LPARAM
        ]
        self.user32.EnumDisplayMonitors.restype = wintypes.BOOL

    def _format_win32_error(self, err_code: int) -> str:
        unsigned = err_code & 0xFFFFFFFF
        msg = DDCCI_ERROR_MESSAGES.get(unsigned) or DDCCI_ERROR_MESSAGES.get(err_code)
        if msg:
            return f"0x{unsigned:08X} - {msg}"
        return f"0x{unsigned:08X} (Kod: {err_code})"

    def _read_capabilities(self, handle: wintypes.HANDLE) -> str:
        """Monitörün VESA MCCS DDC/CI yetenekler dizgisini (capabilities) okur."""
        try:
            str_len = wintypes.DWORD()
            if self.dxva2.GetCapabilitiesStringLength(handle, ctypes.byref(str_len)):
                if str_len.value > 0:
                    buf = (ctypes.c_char * str_len.value)()
                    if self.dxva2.CapabilitiesRequestAndCapabilitiesReply(handle, buf, str_len.value):
                        return buf.value.decode("ascii", errors="ignore")
        except Exception:
            pass
        return ""

    def enumerate_monitors(self) -> List[MonitorDevice]:
        """
        Sisteme bağlı tüm ekranları tarar, DDC/CI destekleyen fiziksel monitörleri,
        mevcut parlaklık seviyelerini ve yetenek dizgilerini listeler.
        """
        hmonitors: List[wintypes.HMONITOR] = []

        def _enum_cb(hmon, hdc, lprect, lparam):
            hmonitors.append(hmon)
            return True

        if not self.user32.EnumDisplayMonitors(None, None, self.MONITORENUMPROC(_enum_cb), 0):
            return []

        devices: List[MonitorDevice] = []
        global_idx = 0

        for hmon in hmonitors:
            count = wintypes.DWORD()
            if not self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)):
                continue

            if count.value == 0:
                continue

            phys_array = (PHYSICAL_MONITOR * count.value)()
            if not self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, phys_array):
                continue

            try:
                for i in range(count.value):
                    handle = phys_array[i].hPhysicalMonitor
                    desc = str(phys_array[i].szPhysicalMonitorDescription)

                    min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                    success = self.dxva2.GetMonitorBrightness(
                        handle,
                        ctypes.byref(min_b),
                        ctypes.byref(cur_b),
                        ctypes.byref(max_b)
                    )

                    if success:
                        caps = self._read_capabilities(handle)
                        dev = MonitorDevice(
                            index=global_idx,
                            hmonitor=hmon,
                            description=desc,
                            current_brightness=cur_b.value,
                            min_brightness=min_b.value,
                            max_brightness=max_b.value,
                            capabilities_string=caps
                        )
                        devices.append(dev)
                        global_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        return devices

    def set_brightness(self, target_index: int, value: int) -> int:
        """
        Belirtilen monitörün parlaklığını DDC/CI ile ayarlar.
        Değişikliği doğrulamak için monitörden okunan son değeri döner.
        """
        value = max(0, min(100, int(value)))
        hmonitors: List[wintypes.HMONITOR] = []

        def _enum_cb(hmon, hdc, lprect, lparam):
            hmonitors.append(hmon)
            return True

        self.user32.EnumDisplayMonitors(None, None, self.MONITORENUMPROC(_enum_cb), 0)

        current_idx = 0
        for hmon in hmonitors:
            count = wintypes.DWORD()
            if not self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)):
                continue

            phys_array = (PHYSICAL_MONITOR * count.value)()
            if not self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, phys_array):
                continue

            try:
                for i in range(count.value):
                    if current_idx == target_index:
                        handle = phys_array[i].hPhysicalMonitor
                        desc = str(phys_array[i].szPhysicalMonitorDescription)

                        success = self.dxva2.SetMonitorBrightness(handle, wintypes.DWORD(value))
                        if not success:
                            err = ctypes.GetLastError()
                            details = self._format_win32_error(err)
                            if err in (31, 6, 0xC0262585, 0xC0262586):
                                raise DDCCIDisconnectedError(
                                    f"'{desc}' monitörüyle bağlantı koptu veya uyku modunda: {details}",
                                    code=err
                                )
                            elif err == 0xC0262584:
                                raise DDCCIUnsupportedError(
                                    f"'{desc}' monitörü parlaklık (Luminance) komutunu desteklemiyor: {details}",
                                    code=err
                                )
                            raise DDCCIError(f"Parlaklık ayarlanamadı: {details}", code=err)

                        # Doğrulama amaçlı tekrar oku
                        min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                        self.dxva2.GetMonitorBrightness(
                            handle,
                            ctypes.byref(min_b),
                            ctypes.byref(cur_b),
                            ctypes.byref(max_b)
                        )
                        return cur_b.value

                    current_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        raise DDCCIDisconnectedError(f"Monitör #{target_index} bulunamadı.")

    def get_brightness(self, target_index: int) -> int:
        """Belirtilen monitörün mevcut donanım parlaklık değerini okur."""
        hmonitors: List[wintypes.HMONITOR] = []

        def _enum_cb(hmon, hdc, lprect, lparam):
            hmonitors.append(hmon)
            return True

        self.user32.EnumDisplayMonitors(None, None, self.MONITORENUMPROC(_enum_cb), 0)

        current_idx = 0
        for hmon in hmonitors:
            count = wintypes.DWORD()
            if not self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)):
                continue

            phys_array = (PHYSICAL_MONITOR * count.value)()
            if not self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, phys_array):
                continue

            try:
                for i in range(count.value):
                    if current_idx == target_index:
                        handle = phys_array[i].hPhysicalMonitor
                        min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                        success = self.dxva2.GetMonitorBrightness(
                            handle,
                            ctypes.byref(min_b),
                            ctypes.byref(cur_b),
                            ctypes.byref(max_b)
                        )
                        if not success:
                            err = ctypes.GetLastError()
                            details = self._format_win32_error(err)
                            raise DDCCIDisconnectedError(f"Parlaklık okunamadı: {details}", code=err)
                        return cur_b.value
                    current_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        raise DDCCIDisconnectedError(f"Monitör #{target_index} bulunamadı.")
