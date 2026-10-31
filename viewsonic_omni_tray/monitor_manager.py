"""
ViewSonic OMNI DDC/CI Tray - MonitorManager (Donanım Katmanı)
Windows High-Level Monitor Configuration API (Dxva2) ve Low-Level VCP DDC/CI arayüzü.
Parlaklık, Ses, Giriş Kaynağı ve Güç/Uyku kontrolünü yönetir.
"""

import sys
import ctypes
from ctypes import wintypes
from typing import List, Dict, Optional, Tuple

# Win32 / DXVA2 DDC/CI Hata Kodları ve Anlaşılır Açıklamaları
DDCCI_ERROR_MESSAGES = {
    0xC0262582: "Monitörden geçersiz veya bozuk DDC/CI verisi alındı (ERROR_GRAPHICS_DDCCI_INVALID_DATA).",
    0xC0262584: "Monitör bu VCP özelliğini desteklemiyor (ERROR_GRAPHICS_DDCCI_VCP_NOT_SUPPORTED).",
    0xC0262585: "I2C veri aktarım hatası (ERROR_GRAPHICS_I2C_ERROR_TRANSMITTING_DATA). Monitör I2C sinyallerine yanıt vermedi.",
    0xC0262586: "I2C veri alma hatası (ERROR_GRAPHICS_I2C_ERROR_RECEIVING_DATA).",
    0xC0262587: "Monitör geçersiz zamanlama durumu döndürdü (ERROR_GRAPHICS_DDCCI_MONITOR_RETURNED_INVALID_TIMING_STATUS_BYTE).",
    0xC0262588: "DDC/CI yetenekler dizgisi okunamadı (ERROR_GRAPHICS_DDCCI_INVALID_CAPABILITIES_STRING).",
    31: "Cihaz yanıt vermiyor (ERROR_GEN_FAILURE). Monitör uyku modunda olabilir veya OSD menüsünde DDC/CI kapalı.",
    6: "Geçersiz tanıtıcı (ERROR_INVALID_HANDLE). Monitör uyku/uyanma sonrası tanıtıcı sıfırlanmış olabilir.",
    1460: "I2C/DDC iletişim zaman aşımına uğradı (ERROR_TIMEOUT).",
}

# Giriş Kaynakları ve Kodları (ViewSonic OMNI VESA Standartları)
INPUT_SOURCES = {
    0x0F: "DisplayPort",
    0x11: "HDMI 1",
    0x12: "HDMI 2"
}

# Güç Modları (VCP 0xD6)
POWER_MODES = {
    0x01: "Açık (On)",
    0x04: "Bekleme (Standby)",
    0x05: "Kapalı / Askıya Al (Suspend)"
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
    """Monitör VCP özelliğini desteklemediğinde fırlatılır."""
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
        current_volume: int = 50,
        current_input: int = 0x12,
        capabilities_string: str = ""
    ):
        self.index = index
        self.hmonitor = hmonitor
        self.description = description
        self.current_brightness = current_brightness
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.current_volume = current_volume
        self.current_input = current_input
        self.capabilities_string = capabilities_string
        desc_lower = description.lower()
        self.is_viewsonic = "viewsonic" in desc_lower or "vx2718" in desc_lower or "omni" in desc_lower

    @property
    def input_name(self) -> str:
        return INPUT_SOURCES.get(self.current_input, f"Giriş (0x{self.current_input:02X})")

    @property
    def supports_luminance(self) -> bool:
        if not self.capabilities_string:
            return True
        caps = self.capabilities_string.lower()
        return "10" in caps or "luminance" in caps

    def __repr__(self):
        return f"<MonitorDevice #{self.index}: '{self.description}' (%{self.current_brightness}, Ses: %{self.current_volume}, Giriş: {self.input_name})>"


class MonitorManager:
    """
    Windows Dxva2 ve User32 API'lerini sarmalayan,
    parlaklık, ses, giriş kaynağı ve güç kontrolünü yöneten donanım soyutlama katmanı.
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

        # Low-level VCP (Ses 0x62, Giriş 0x60, Güç 0xD6)
        self.dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
            wintypes.HANDLE,
            ctypes.c_byte,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.dxva2.GetVCPFeatureAndVCPFeatureReply.restype = wintypes.BOOL

        self.dxva2.SetVCPFeature.argtypes = [
            wintypes.HANDLE,
            ctypes.c_byte,
            wintypes.DWORD
        ]
        self.dxva2.SetVCPFeature.restype = wintypes.BOOL

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

    def _execute_on_handle(self, target_index: int, func):
        """Belirtilen hedef indeks için fiziksel handle alır, func(handle) çağırır ve handle'ı serbest bırakır."""
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
                        return func(handle, desc)
                    current_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        raise DDCCIDisconnectedError(f"Monitör #{target_index} bulunamadı.")

    def enumerate_monitors(self) -> List[MonitorDevice]:
        """Sisteme bağlı tüm DDC/CI monitörleri tarar; parlaklık, ses ve giriş kaynağını okur."""
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

                        # Ses okuma (0x62)
                        pvct, cur_vol, mx_vol = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                        vol_val = 50
                        if self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, 0x62, ctypes.byref(pvct), ctypes.byref(cur_vol), ctypes.byref(mx_vol)):
                            vol_val = cur_vol.value

                        # Giriş kaynağı okuma (0x60)
                        cur_inp, mx_inp = wintypes.DWORD(), wintypes.DWORD()
                        inp_val = 0x12
                        if self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, 0x60, ctypes.byref(pvct), ctypes.byref(cur_inp), ctypes.byref(mx_inp)):
                            inp_val = cur_inp.value

                        dev = MonitorDevice(
                            index=global_idx,
                            hmonitor=hmon,
                            description=desc,
                            current_brightness=cur_b.value,
                            min_brightness=min_b.value,
                            max_brightness=max_b.value,
                            current_volume=vol_val,
                            current_input=inp_val,
                            capabilities_string=caps
                        )
                        devices.append(dev)
                        global_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        return devices

    # --- Parlaklık (Luminance VCP 0x10) ---
    def set_brightness(self, target_index: int, value: int) -> int:
        value = max(0, min(100, int(value)))

        def _action(handle, desc):
            if not self.dxva2.SetMonitorBrightness(handle, wintypes.DWORD(value)):
                err = ctypes.GetLastError()
                raise DDCCIError(f"Parlaklık ayarlanamadı: {self._format_win32_error(err)}", code=err)
            min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            self.dxva2.GetMonitorBrightness(handle, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b))
            return cur_b.value

        return self._execute_on_handle(target_index, _action)

    def get_brightness(self, target_index: int) -> int:
        def _action(handle, desc):
            min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if not self.dxva2.GetMonitorBrightness(handle, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b)):
                err = ctypes.GetLastError()
                raise DDCCIDisconnectedError(f"Parlaklık okunamadı: {self._format_win32_error(err)}", code=err)
            return cur_b.value

        return self._execute_on_handle(target_index, _action)

    # --- Ses Seviyesi (Volume VCP 0x62) & Mute (0x8D) ---
    def set_volume(self, target_index: int, value: int) -> int:
        value = max(0, min(100, int(value)))

        def _action(handle, desc):
            if not self.dxva2.SetVCPFeature(handle, 0x62, wintypes.DWORD(value)):
                err = ctypes.GetLastError()
                raise DDCCIError(f"Ses ayarlanamadı: {self._format_win32_error(err)}", code=err)
            pvct, cur_vol, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, 0x62, ctypes.byref(pvct), ctypes.byref(cur_vol), ctypes.byref(mx))
            return cur_vol.value

        return self._execute_on_handle(target_index, _action)

    def get_volume(self, target_index: int) -> int:
        def _action(handle, desc):
            pvct, cur_vol, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if not self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, 0x62, ctypes.byref(pvct), ctypes.byref(cur_vol), ctypes.byref(mx)):
                err = ctypes.GetLastError()
                raise DDCCIDisconnectedError(f"Ses okunamadı: {self._format_win32_error(err)}", code=err)
            return cur_vol.value

        return self._execute_on_handle(target_index, _action)

    def set_mute(self, target_index: int, mute: bool) -> bool:
        # VESA MCCS 0x8D: 1 = Mute, 2 = Unmute
        val = 1 if mute else 2

        def _action(handle, desc):
            if not self.dxva2.SetVCPFeature(handle, 0x8D, wintypes.DWORD(val)):
                err = ctypes.GetLastError()
                raise DDCCIError(f"Sessize alma başarısız: {self._format_win32_error(err)}", code=err)
            return mute

        return self._execute_on_handle(target_index, _action)

    # --- Giriş Kaynağı (Input Source VCP 0x60) ---
    def set_input_source(self, target_index: int, source_code: int) -> int:
        def _action(handle, desc):
            if not self.dxva2.SetVCPFeature(handle, 0x60, wintypes.DWORD(source_code)):
                err = ctypes.GetLastError()
                raise DDCCIError(f"Giriş kaynağı değiştirilemedi: {self._format_win32_error(err)}", code=err)
            return source_code

        return self._execute_on_handle(target_index, _action)

    def get_input_source(self, target_index: int) -> int:
        def _action(handle, desc):
            pvct, cur_inp, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if not self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, 0x60, ctypes.byref(pvct), ctypes.byref(cur_inp), ctypes.byref(mx)):
                err = ctypes.GetLastError()
                raise DDCCIDisconnectedError(f"Giriş kaynağı okunamadı: {self._format_win32_error(err)}", code=err)
            return cur_inp.value

        return self._execute_on_handle(target_index, _action)

    # --- Güç ve Uyku Yönetimi (Power Mode VCP 0xD6) ---
    def set_power_mode(self, target_index: int, mode: int = 0x04) -> bool:
        """Monitörü uyku/bekleme moduna (0x04 Standby) veya açılışa (0x01 On) alır."""
        def _action(handle, desc):
            if not self.dxva2.SetVCPFeature(handle, 0xD6, wintypes.DWORD(mode)):
                err = ctypes.GetLastError()
                raise DDCCIError(f"Güç modu ayarlanamadı: {self._format_win32_error(err)}", code=err)
            return True

        return self._execute_on_handle(target_index, _action)
