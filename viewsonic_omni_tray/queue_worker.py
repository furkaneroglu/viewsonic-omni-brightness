"""
ViewSonic OMNI DDC/CI Tray - AsyncWriteQueueWorker (Rate-Limiting & Asenkron Kuyruk)
Donanım I2C yolunu tıkamamak için kuyruğa alma, debounce, throttling ve periyodik watchdog mimarisi.
"""

import time
import threading
from enum import Enum
from typing import List, Optional, Callable, Dict, Any
from .monitor_manager import MonitorManager, MonitorDevice, DDCCIError, DDCCIDisconnectedError
from .config import ConfigManager

class MonitorStatus(Enum):
    CONNECTED = "Bağlı"
    SLEEPING = "Uykuda / Beklemede"
    DISCONNECTED = "Bağlantı Yok"
    ERROR = "İletişim Hatası"


class AsyncWriteQueueWorker:
    """
    DDC/CI I2C donanım isteklerini UI iş parçacığından bağımsız yürüten,
    debounce (80ms) ve throttling (100ms) ile donanım koruması sağlayan asenkron kuyruk işçisi.
    """

    def __init__(self, config: ConfigManager, monitor_manager: Optional[MonitorManager] = None):
        self.config = config
        self.manager = monitor_manager or MonitorManager()

        self.devices: List[MonitorDevice] = []
        self.active_device: Optional[MonitorDevice] = None
        self.active_index: int = 0

        self.status: MonitorStatus = MonitorStatus.DISCONNECTED
        self.status_message: str = "Başlatılıyor..."

        self._current_brightness: int = 50
        self._target_brightness: int = 50
        self._last_write_timestamp: float = 0.0

        # Donanım Koruması Zamanlama Parametreleri (ms -> sn)
        self.throttle_sec: float = max(0.05, self.config.throttle_ms / 1000.0)
        self.debounce_sec: float = max(0.04, self.config.debounce_ms / 1000.0)
        self.watchdog_interval: float = max(5.0, float(self.config.watchdog_interval_s))

        # Thread senkronizasyonu
        self._lock = threading.Lock()
        self._request_event = threading.Event()
        self._stop_event = threading.Event()

        # UI ve Bildirim dinleyicileri
        self._brightness_listeners: List[Callable[[int, bool], None]] = []
        self._status_listeners: List[Callable[[MonitorStatus, str], None]] = []
        self._device_listeners: List[Callable[[List[MonitorDevice], Optional[MonitorDevice]], None]] = []
        self._notification_listeners: List[Callable[[str, str, str], None]] = [] # (title, message, type)

        # Arka plan iş parçacıkları
        self._worker_thread = threading.Thread(target=self._hardware_worker_loop, name="DDC-WriteWorker", daemon=True)
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="DDC-Watchdog", daemon=True)

    def start(self):
        """Monitörleri ilk defa tarar ve arka plan iş parçacıklarını başlatır."""
        self.rescan_monitors()
        self._worker_thread.start()
        self._watchdog_thread.start()

    def stop(self):
        """Arka plan iş parçacıklarını temiz şekilde durdurur."""
        self._stop_event.set()
        self._request_event.set()

    # --- Dinleyici Kayıt Metotları ---
    def add_brightness_listener(self, cb: Callable[[int, bool], None]):
        self._brightness_listeners.append(cb)

    def add_status_listener(self, cb: Callable[[MonitorStatus, str], None]):
        self._status_listeners.append(cb)

    def add_device_listener(self, cb: Callable[[List[MonitorDevice], Optional[MonitorDevice]], None]):
        self._device_listeners.append(cb)

    def add_notification_listener(self, cb: Callable[[str, str, str], None]):
        self._notification_listeners.append(cb)

    def _notify_brightness(self, value: int, from_hardware: bool = False):
        for cb in list(self._brightness_listeners):
            try:
                cb(value, from_hardware)
            except Exception as e:
                print(f"[!] Brightness listener hatası: {e}")

    def _notify_status(self, status: MonitorStatus, message: str):
        for cb in list(self._status_listeners):
            try:
                cb(status, message)
            except Exception as e:
                print(f"[!] Status listener hatası: {e}")

    def _notify_devices(self):
        for cb in list(self._device_listeners):
            try:
                cb(self.devices, self.active_device)
            except Exception as e:
                print(f"[!] Device listener hatası: {e}")

    def _notify_user(self, title: str, message: str, level: str = "info"):
        for cb in list(self._notification_listeners):
            try:
                cb(title, message, level)
            except Exception as e:
                print(f"[!] Notification listener hatası: {e}")

    # --- Monitör Tarama & Seçim ---
    def rescan_monitors(self) -> bool:
        """Sisteme bağlı monitörleri tarar, ViewSonic veya hedef monitörü aktif seçer."""
        with self._lock:
            try:
                devs = self.manager.enumerate_monitors()
                self.devices = devs

                if not devs:
                    old_status = self.status
                    self.active_device = None
                    self.status = MonitorStatus.DISCONNECTED
                    self.status_message = "Hiçbir DDC/CI monitör algılanamadı."
                    self._notify_status(self.status, self.status_message)
                    self._notify_devices()
                    if old_status == MonitorStatus.CONNECTED:
                        self._notify_user(
                            "Monitör Bağlantısı Kesildi",
                            "DDC/CI uyumlu monitör bulunamadı. Kabloyu veya OSD menüsünü kontrol edin.",
                            level="warning"
                        )
                    return False

                # ViewSonic öncelikli hedef bulma
                target = None
                match_keyword = self.config.monitor_match.lower()
                for d in devs:
                    if match_keyword in d.description.lower():
                        target = d
                        break

                if not target:
                    target = devs[0]

                prev_status = self.status
                self.active_device = target
                self.active_index = target.index
                self._current_brightness = target.current_brightness
                self._target_brightness = target.current_brightness
                self.status = MonitorStatus.CONNECTED
                self.status_message = f"{target.description} bağlandı."

                self._notify_brightness(self._current_brightness, from_hardware=True)
                self._notify_status(self.status, self.status_message)
                self._notify_devices()

                # Uykudan veya kopmadan geri geldiyse kullanıcıya bildir
                if prev_status in (MonitorStatus.SLEEPING, MonitorStatus.DISCONNECTED, MonitorStatus.ERROR):
                    self._notify_user(
                        "Monitör Bağlandı",
                        f"'{target.description}' DDC/CI üzerinden aktif. Parlaklık: %{self._current_brightness}",
                        level="info"
                    )

                return True

            except Exception as e:
                self.status = MonitorStatus.ERROR
                self.status_message = f"Tarama hatası: {e}"
                self._notify_status(self.status, self.status_message)
                return False

    def select_device(self, index: int):
        """Aktif monitörü kullanıcı seçimine göre ayarlar."""
        with self._lock:
            for d in self.devices:
                if d.index == index:
                    self.active_device = d
                    self.active_index = index
                    self._current_brightness = d.current_brightness
                    self._target_brightness = d.current_brightness
                    self.status = MonitorStatus.CONNECTED
                    self.status_message = f"{d.description} seçildi."
                    self._notify_brightness(self._current_brightness, from_hardware=True)
                    self._notify_status(self.status, self.status_message)
                    self._notify_devices()
                    return

    # --- Parlaklık İstekleri ---
    def get_current_brightness(self) -> int:
        with self._lock:
            return self._target_brightness

    def set_brightness(self, value: int, immediate_ui: bool = True):
        """
        Kullanıcıdan gelen yeni parlaklık isteğini kuyruğa ekler.
        Ana UI iş parçacığını ASLA bloklamaz.
        """
        clamped = max(0, min(100, int(value)))
        with self._lock:
            self._target_brightness = clamped
            if immediate_ui:
                self._notify_brightness(clamped, from_hardware=False)
            self._request_event.set()

    def change_brightness_by(self, delta: int):
        """Mevcut parlaklığı adım kadar (örn. +5 veya -5) artırır/azaltır."""
        with self._lock:
            new_val = self._target_brightness + delta
        self.set_brightness(new_val, immediate_ui=True)

    def apply_profile(self, profile_name: str) -> bool:
        """Kayıtlı profillerden birini uygular."""
        profiles = self.config.profiles
        if profile_name in profiles:
            val = profiles[profile_name]
            self.set_brightness(val, immediate_ui=True)
            return True
        return False

    # --- Asenkron Donanım Kuyruk Döngüsü (Coalescing + Debounce + Throttle) ---
    def _hardware_worker_loop(self):
        while not self._stop_event.is_set():
            self._request_event.wait(timeout=0.2)
            if self._stop_event.is_set():
                break

            with self._lock:
                target = self._target_brightness
                cur_hw = self._current_brightness
                target_dev_idx = self.active_index
                has_dev = self.active_device is not None

            if not has_dev or target == cur_hw:
                self._request_event.clear()
                continue

            # 1. Debounce gecikmesi (80ms bekleyerek hızlı slider hareketlerinin ara değerlerini süz)
            time.sleep(self.debounce_sec)
            with self._lock:
                target = self._target_brightness
                cur_hw = self._current_brightness

            if target == cur_hw:
                self._request_event.clear()
                continue

            # 2. Throttling kontrolü (İki fiziksel donanım yazımı arası en az throttle_sec bekle)
            elapsed = time.time() - self._last_write_timestamp
            if elapsed < self.throttle_sec:
                time.sleep(self.throttle_sec - elapsed)

            # 3. Donanıma yazma
            try:
                verified = self.manager.set_brightness(target_dev_idx, target)
                self._last_write_timestamp = time.time()

                with self._lock:
                    self._current_brightness = verified
                    if self.status != MonitorStatus.CONNECTED:
                        self.status = MonitorStatus.CONNECTED
                        self.status_message = "Bağlantı aktif."
                        self._notify_status(self.status, self.status_message)

                self._notify_brightness(verified, from_hardware=True)

            except DDCCIDisconnectedError as e:
                prev_status = self.status
                with self._lock:
                    self.status = MonitorStatus.SLEEPING
                    self.status_message = "Monitör uyku modunda veya bağlantı kesildi."
                self._notify_status(self.status, self.status_message)
                if prev_status == MonitorStatus.CONNECTED:
                    self._notify_user(
                        "DDC/CI İletişim Uyarısı",
                        "Monitör uyku moduna geçti veya I2C yanıt vermedi.",
                        level="warning"
                    )
                time.sleep(0.5)

            except DDCCIError as e:
                with self._lock:
                    self.status = MonitorStatus.ERROR
                    self.status_message = f"DDC/CI Hatası: {e}"
                self._notify_status(self.status, self.status_message)
                time.sleep(0.5)

            except Exception as e:
                with self._lock:
                    self.status = MonitorStatus.ERROR
                    self.status_message = f"Bilinmeyen hata: {e}"
                self._notify_status(self.status, self.status_message)
                time.sleep(0.5)

            finally:
                with self._lock:
                    if self._target_brightness == self._current_brightness:
                        self._request_event.clear()

    # --- Watchdog & Yeniden Bağlantı Döngüsü ---
    def _watchdog_loop(self):
        while not self._stop_event.is_set():
            time.sleep(self.watchdog_interval)
            if self._stop_event.is_set():
                break

            if self.status in (MonitorStatus.SLEEPING, MonitorStatus.DISCONNECTED, MonitorStatus.ERROR):
                success = self.rescan_monitors()
                if success:
                    self._request_event.set()
            elif self.status == MonitorStatus.CONNECTED and self.active_device is not None:
                idle_time = time.time() - self._last_write_timestamp
                if idle_time > self.watchdog_interval:
                    try:
                        hw_val = self.manager.get_brightness(self.active_index)
                        with self._lock:
                            if hw_val != self._current_brightness and not self._request_event.is_set():
                                self._current_brightness = hw_val
                                self._target_brightness = hw_val
                                self._notify_brightness(hw_val, from_hardware=True)
                    except DDCCIDisconnectedError:
                        with self._lock:
                            self.status = MonitorStatus.SLEEPING
                            self.status_message = "Monitör uykuya geçti."
                        self._notify_status(self.status, self.status_message)
                    except Exception:
                        pass
