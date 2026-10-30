"""
ViewSonic OMNI DDC/CI Tray - HotkeyService (Global Kısayol Dinleyicisi)
pynput.keyboard.GlobalHotKeys kullanarak sistem genelinde klavye kısayollarını dinler.
"""

import threading
from typing import Dict, Callable, Optional
from pynput import keyboard
from .config import ConfigManager
from .queue_worker import AsyncWriteQueueWorker


class HotkeyService:
    """Sistem genelinde çalışan kısayol tuşlarını yöneten ve OSD HUD ile bağlayan servis."""

    def __init__(self, config: ConfigManager, worker: AsyncWriteQueueWorker, on_hotkey_triggered: Optional[Callable[[str, int], None]] = None):
        self.config = config
        self.worker = worker
        self.on_hotkey_triggered = on_hotkey_triggered
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def start(self):
        """Kısayol dinleyicisini başlatır."""
        self.reload()

    def stop(self):
        """Kısayol dinleyicisini durdurur."""
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

    def reload(self):
        """Ayar dosyasından güncel kısayol tuşlarını okur ve dinleyiciyi yeniden kurar."""
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

            hotkey_mapping = {}
            hotkeys = self.config.hotkeys
            step = self.config.step_size

            # Parlaklık Artır (örn. Ctrl+Alt+Up)
            if hotkeys.get("brightness_up"):
                hotkey_mapping[hotkeys["brightness_up"]] = lambda: self._on_change_brightness(step, "Parlaklık Artır")

            # Parlaklık Azalt (örn. Ctrl+Alt+Down)
            if hotkeys.get("brightness_down"):
                hotkey_mapping[hotkeys["brightness_down"]] = lambda: self._on_change_brightness(-step, "Parlaklık Azalt")

            # Profil Kısayolları (Ctrl+Alt+1..4)
            if hotkeys.get("profile_day"):
                hotkey_mapping[hotkeys["profile_day"]] = lambda: self._on_apply_profile("Gündüz")

            if hotkeys.get("profile_night"):
                hotkey_mapping[hotkeys["profile_night"]] = lambda: self._on_apply_profile("Gece")

            if hotkeys.get("profile_read"):
                hotkey_mapping[hotkeys["profile_read"]] = lambda: self._on_apply_profile("Okuma")

            if hotkeys.get("profile_game"):
                hotkey_mapping[hotkeys["profile_game"]] = lambda: self._on_apply_profile("Oyun")

            try:
                self._listener = keyboard.GlobalHotKeys(hotkey_mapping)
                self._listener.daemon = True
                self._listener.start()
            except Exception as e:
                print(f"[!] Kısayol dinleyicisi başlatılamadı: {e}")

    def _on_change_brightness(self, delta: int, action_name: str):
        self.worker.change_brightness_by(delta)
        new_val = self.worker.get_current_brightness()
        if self.on_hotkey_triggered:
            self.on_hotkey_triggered(action_name, new_val)

    def _on_apply_profile(self, profile_name: str):
        success = self.worker.apply_profile(profile_name)
        if success:
            val = self.config.profiles.get(profile_name, 50)
            if self.on_hotkey_triggered:
                self.on_hotkey_triggered(f"Profil: {profile_name}", val)


# Geriye dönük takma ad
HotkeyManager = HotkeyService

__all__ = ["HotkeyService", "HotkeyManager"]
