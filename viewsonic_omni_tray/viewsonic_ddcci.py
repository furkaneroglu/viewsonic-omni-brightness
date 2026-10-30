#!/usr/bin/env python3
"""
ViewSonic OMNI - DDC/CI Parlaklık Denetleyici (PoC)
Windows High-Level Monitor Configuration API (Dxva2) Wrapper

Gereksinimler:
- Python 3.7+
- Windows (ekstra pip kütüphanesi gerektirmez, standart ctypes kullanır)
- Monitörün HDMI / DisplayPort ile bağlı olması
- Monitör OSD Menüsünde DDC/CI seçeneğinin açık olması
"""

import sys
import os
import argparse
import ctypes
from ctypes import wintypes
from typing import List, Dict, Optional, Tuple

# Windows konsolunda Türkçe karakter veya emoji kodlama hatası yaşanmaması için UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Win32 / DXVA2 DDC/CI Hata Kodları ve Anlaşılır Açıklamaları
DDCCI_ERROR_MESSAGES = {
    0xC0262582: "Monitörden geçersiz veya bozuk DDC/CI verisi alındı (ERROR_GRAPHICS_DDCCI_INVALID_DATA).",
    0xC0262584: "Monitör bu VCP özelliğini (Luminance/Parlaklık) desteklemiyor (ERROR_GRAPHICS_DDCCI_VCP_NOT_SUPPORTED).",
    0xC0262585: "I2C veri aktarım hatası (ERROR_GRAPHICS_I2C_ERROR_TRANSMITTING_DATA). Monitör I2C sinyallerine yanıt vermedi.",
    0xC0262586: "I2C veri alma hatası (ERROR_GRAPHICS_I2C_ERROR_RECEIVING_DATA).",
    0xC0262587: "Monitör geçersiz zamanlama baytı döndürdü (ERROR_GRAPHICS_DDCCI_MONITOR_RETURNED_INVALID_TIMING_STATUS_BYTE).",
    0xC0262588: "DDC/CI yetenekler dizgisi okunamadı (ERROR_GRAPHICS_DDCCI_INVALID_CAPABILITIES_STRING).",
    31: "Cihaz yanıt vermiyor (ERROR_GEN_FAILURE / 0x1F). Monitörün OSD menüsünde DDC/CI kapalı olabilir.",
    1460: "I2C/DDC iletişim zaman aşımına uğradı (ERROR_TIMEOUT).",
}

class DDCCIException(Exception):
    """DDC/CI genel hata sınıfı."""
    pass

class DDCCIDisabledOrI2CError(DDCCIException):
    """Monitör OSD'sinde DDC/CI kapalı veya I2C iletişim hatası alındığında fırlatılır."""
    pass


# Windows API Yapıları ve Tanımlamaları
class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)
    ]

class MonitorManager:
    """Windows Dxva2 ve User32 API'leri ile DDC/CI işlemlerini yöneten sınıf."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Bu PoC scripti Windows Dxva2 API'si üzerine kurulmuştur. Linux için ddcutil / monitorcontrol kullanabilirsiniz.")

        self.user32 = ctypes.windll.user32
        self.dxva2 = ctypes.windll.dxva2
        self._setup_api_signatures()

    def _setup_api_signatures(self):
        # dxva2 fonksiyon argüman ve dönüş tipleri
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

        self.dxva2.DestroyPhysicalMonitors.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(PHYSICAL_MONITOR)
        ]
        self.dxva2.DestroyPhysicalMonitors.restype = wintypes.BOOL

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM
        )
        self.user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC,
            ctypes.c_void_p,
            MONITORENUMPROC,
            wintypes.LPARAM
        ]
        self.user32.EnumDisplayMonitors.restype = wintypes.BOOL
        self.MONITORENUMPROC = MONITORENUMPROC

    def _format_error(self, err_code: int) -> str:
        unsigned_code = err_code & 0xFFFFFFFF
        friendly = DDCCI_ERROR_MESSAGES.get(unsigned_code) or DDCCI_ERROR_MESSAGES.get(err_code)
        
        detail = f"Hata Kodu: 0x{unsigned_code:08X} ({err_code})"
        if friendly:
            detail += f"\nAçıklama: {friendly}"
        
        detail += (
            "\n\n[!] Çözüm Önerileri:"
            "\n 1. ViewSonic OMNI monitörünüzün joystick/tuşları ile OSD Menüsüne girin:"
            "\n    [Setup Menu / Ayarlar] -> [DDC/CI] ayarının 'On' / 'Açık' (Enabled) olduğunu doğrulayın."
            "\n 2. HDMI veya DisplayPort kablosunun doğrudan ekran kartına bağlı olduğundan emin olun."
            "\n    (Pasif adaptörler, dönüştürücüler veya bazı KVM switch'ler DDC/CI I2C sinyal hattını engelleyebilir)."
            "\n 3. Ekran kartı sürücünüzün (NVIDIA / AMD / Intel) güncel olduğundan emin olun."
        )
        return detail

    def get_all_monitors(self) -> List[Dict]:
        """Tüm bağlı monitörleri ve DDC/CI parlaklık değerlerini listeler."""
        hmonitors = []

        def _enum_callback(hmon, hdc, lprect, lparam):
            hmonitors.append(hmon)
            return True

        self.user32.EnumDisplayMonitors(None, None, self.MONITORENUMPROC(_enum_callback), 0)

        results = []
        global_idx = 0

        for hmon in hmonitors:
            count = wintypes.DWORD()
            if not self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)):
                continue

            if count.value == 0:
                continue

            phys_array = (PHYSICAL_MONITOR * count.value)()
            if not self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, phys_array):
                err = ctypes.GetLastError()
                raise DDCCIDisabledOrI2CError(
                    f"Fiziksel monitör bilgileri alınamadı!\n{self._format_error(err)}"
                )

            try:
                for i in range(count.value):
                    handle = phys_array[i].hPhysicalMonitor
                    desc = phys_array[i].szPhysicalMonitorDescription

                    min_b = wintypes.DWORD()
                    cur_b = wintypes.DWORD()
                    max_b = wintypes.DWORD()

                    success = self.dxva2.GetMonitorBrightness(
                        handle,
                        ctypes.byref(min_b),
                        ctypes.byref(cur_b),
                        ctypes.byref(max_b)
                    )

                    if not success:
                        err = ctypes.GetLastError()
                        raise DDCCIDisabledOrI2CError(
                            f"'{desc}' monitöründen DDC/CI parlaklık verisi okunamadı!\n{self._format_error(err)}"
                        )

                    results.append({
                        "index": global_idx,
                        "hmonitor": hmon,
                        "description": desc,
                        "current_brightness": cur_b.value,
                        "min_brightness": min_b.value,
                        "max_brightness": max_b.value,
                    })
                    global_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        return results

    def set_monitor_brightness(self, target_index: int, new_brightness: int) -> Tuple[str, int]:
        """Hedeflenen monitörün parlaklık değerini DDC/CI ile günceller."""
        if not (0 <= new_brightness <= 100):
            raise ValueError(f"Parlaklık değeri 0 ile 100 arasında olmalıdır! Girilen: {new_brightness}")

        hmonitors = []

        def _enum_callback(hmon, hdc, lprect, lparam):
            hmonitors.append(hmon)
            return True

        self.user32.EnumDisplayMonitors(None, None, self.MONITORENUMPROC(_enum_callback), 0)

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
                        desc = phys_array[i].szPhysicalMonitorDescription

                        success = self.dxva2.SetMonitorBrightness(handle, wintypes.DWORD(new_brightness))
                        if not success:
                            err = ctypes.GetLastError()
                            raise DDCCIDisabledOrI2CError(
                                f"'{desc}' monitörüne parlaklık komutu gönderilemedi!\n{self._format_error(err)}"
                            )

                        # Değişikliğin uygulandığını doğrulamak için tekrar oku
                        min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                        self.dxva2.GetMonitorBrightness(
                            handle,
                            ctypes.byref(min_b),
                            ctypes.byref(cur_b),
                            ctypes.byref(max_b)
                        )
                        return desc, cur_b.value

                    current_idx += 1
            finally:
                self.dxva2.DestroyPhysicalMonitors(count.value, phys_array)

        raise IndexError(f"Monitör dizini #{target_index} bulunamadı! Toplam tespit edilen monitör sayısı: {current_idx}")


def main():
    parser = argparse.ArgumentParser(
        description="ViewSonic OMNI / DDC-CI Parlaklık Denetleyici (PoC)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Örnek Kullanımlar:
  python viewsonic_ddcci.py                # Bağlı monitörleri ve mevcut parlaklığı listeler
  python viewsonic_ddcci.py --set 75       # 0 numaralı monitörün parlaklığını %75 yapar
  python viewsonic_ddcci.py --id 0 --set 50 # 0 numaralı monitörün parlaklığını %50 yapar
        """
    )
    parser.add_argument(
        "--set", "-s",
        type=int,
        metavar="0-100",
        help="Monitöre atanacak yeni parlaklık değeri (0 - 100)"
    )
    parser.add_argument(
        "--id", "-i",
        type=int,
        default=0,
        metavar="INDEX",
        help="Hedef monitör indeksi (Varsayılan: 0)"
    )
    parser.add_argument(
        "--match", "-m",
        type=str,
        default=None,
        metavar="NAME",
        help="Model adında eşleşen monitörü filtreler (örn. 'ViewSonic')"
    )

    args = parser.parse_args()

    print("=" * 65)
    print(" ViewSonic OMNI - DDC/CI Parlaklık Kontrol CLI (PoC)")
    print("=" * 65)

    try:
        manager = MonitorManager()
        monitors = manager.get_all_monitors()

        if not monitors:
            print("[!] Hiçbir DDC/CI uyumlu monitör tespit edilemedi.")
            print("    Monitör OSD menüsünden DDC/CI özelliğini etkinleştirdiğinizden emin olun.")
            sys.exit(1)

        print(f"\n[+] Tespit Edilen Monitör Sayısı: {len(monitors)}")
        print("-" * 65)
        target_idx = args.id

        for m in monitors:
            is_target = ""
            if args.match and args.match.lower() in m["description"].lower():
                target_idx = m["index"]
                is_target = " [HEDEF SEÇİLDİ]"
            elif m["index"] == target_idx:
                is_target = " [VARSAYILAN HEDEF]"

            print(f" Monitör #{m['index']}{is_target}:")
            print(f"   Model / Tanım    : {m['description']}")
            print(f"   Mevcut Parlaklık : %{m['current_brightness']} (Min: {m['min_brightness']}, Max: {m['max_brightness']})")
            print("-" * 65)

        # Parlaklık atama işlemi istendiyse
        if args.set is not None:
            new_val = args.set
            if not (0 <= new_val <= 100):
                print(f"\n[-] Hata: Parlaklık 0-100 arasında olmalıdır. Girilen: {new_val}")
                sys.exit(1)

            print(f"\n[*] Hedef Monitör #{target_idx} için parlaklık %{new_val} olarak ayarlanıyor...")
            model, verified_val = manager.set_monitor_brightness(target_idx, new_val)
            print(f"[+] Başarılı! '{model}' monitörünün yeni parlaklık değeri: %{verified_val}")

    except DDCCIDisabledOrI2CError as e:
        print(f"\n[-] DDC/CI İletişim Hatası:\n{e}")
        sys.exit(2)
    except Exception as e:
        print(f"\n[-] Beklenmeyen bir hata oluştu: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
