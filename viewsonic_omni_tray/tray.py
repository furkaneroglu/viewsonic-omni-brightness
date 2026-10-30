"""
ViewSonic OMNI DDC/CI Tray - System Tray Icon and Menu Manager (Tray UI)
pystray ve Pillow kullanarak sistem tepsisi simgesi, bildirimler ve sağ tık menüsünü yönetir.
"""

import threading
from typing import Optional, Callable
from PIL import Image, ImageDraw
import pystray
from .config import ConfigManager
from .queue_worker import AsyncWriteQueueWorker, MonitorStatus


def create_tray_image(brightness: int = 50, status: MonitorStatus = MonitorStatus.CONNECTED) -> Image.Image:
    """Sistem tepsisi için yüksek DPI uyumlu, dinamik parlaklık göstergeli simge üretir."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Arka plan yuvarlatılmış kare
    if status == MonitorStatus.CONNECTED:
        bg_color = (24, 24, 27, 255) # Zinc-900 koyu tema
    elif status == MonitorStatus.SLEEPING:
        bg_color = (40, 35, 20, 255) # Amber tonlu uyku
    else:
        bg_color = (45, 20, 20, 255) # Kırmızımsı kopuk

    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=bg_color)

    if status == MonitorStatus.CONNECTED:
        # Parlaklığa göre dinamik güneş rengi (ılık kehribardan parlak altın sarısına)
        ratio = max(0.0, min(1.0, brightness / 100.0))
        r = min(255, int(190 + ratio * 65))
        g = min(255, int(140 + ratio * 115))
        b = min(255, int(20 + ratio * 130))
        sun_color = (r, g, b)

        # Güneş dairesi
        draw.ellipse((20, 14, 44, 38), fill=sun_color)

        # Alt parlaklık barı
        bar_bg = (63, 63, 70, 255)
        draw.rounded_rectangle((10, 46, size - 10, 52), radius=3, fill=bar_bg)

        fill_w = int((size - 20) * ratio)
        if fill_w > 0:
            draw.rounded_rectangle((10, 46, 10 + fill_w, 52), radius=3, fill=sun_color)

    elif status == MonitorStatus.SLEEPING:
        # Uyku sembolü (Hilal)
        draw.ellipse((18, 14, 42, 38), fill=(245, 158, 11))
        draw.ellipse((26, 12, 48, 36), fill=bg_color)
        draw.rounded_rectangle((10, 46, size - 10, 52), radius=3, fill=(100, 80, 20))

    else:
        # Bağlantı yok: Kırmızı çarpı
        draw.line((18, 18, 46, 46), fill=(239, 68, 68), width=5)
        draw.line((18, 46, 46, 18), fill=(239, 68, 68), width=5)

    return img


class TrayApp:
    """Sistem tepsisi ikonunu ve sağ tık menüsünü yöneten sınıf."""

    def __init__(
        self,
        config: ConfigManager,
        worker: AsyncWriteQueueWorker,
        on_open_popup: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_exit: Callable[[], None]
    ):
        self.config = config
        self.worker = worker
        self.on_open_popup = on_open_popup
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit

        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()

    def start(self):
        """Pystray ikonunu detached (arka planda) başlatır."""
        initial_img = create_tray_image(
            self.worker.get_current_brightness(),
            self.worker.status
        )
        self.icon = pystray.Icon(
            name="ViewSonicOmniTray",
            icon=initial_img,
            title="ViewSonic OMNI DDC/CI",
            menu=self._build_menu()
        )
        # Çift tıklama veya varsayılan tıklama eylemi
        self.icon.default_action = lambda icon, item: self.on_open_popup()
        self.icon.run_detached()

    def stop(self):
        """Tepsi ikonunu kapatır."""
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

    def update_icon_and_title(self, brightness: int, status: MonitorStatus):
        """Simge görselini ve fare üzerine gelindiğindeki başlığı (tooltip) günceller."""
        if self.icon is None:
            return

        desc = self.worker.active_device.description if self.worker.active_device else "Monitör"
        status_str = status.value
        title_text = f"ViewSonic OMNI ({desc})\nParlaklık: %{brightness} [{status_str}]"

        try:
            self.icon.title = title_text
            self.icon.icon = create_tray_image(brightness, status)
            self.icon.menu = self._build_menu()
        except Exception as e:
            print(f"[!] Tray update error: {e}")

    def _build_menu(self) -> pystray.Menu:
        """Dinamik sağ tık menüsünü oluşturur."""
        cur_b = self.worker.get_current_brightness()
        status = self.worker.status
        desc = self.worker.active_device.description if self.worker.active_device else "Algılanamadı"

        # Durum ikonu
        if status == MonitorStatus.CONNECTED:
            status_tag = f"🟢 {desc} (%{cur_b})"
        elif status == MonitorStatus.SLEEPING:
            status_tag = f"🟡 {desc} (Uykuda)"
        else:
            status_tag = f"🔴 {desc} (Bağlantı Yok)"

        def make_brightness_action(val: int):
            return lambda icon, item: self.worker.set_brightness(val)

        def make_profile_action(prof_name: str):
            return lambda icon, item: self.worker.apply_profile(prof_name)

        # Hızlı Yüzde Değerleri
        quick_items = [
            pystray.MenuItem("%10", make_brightness_action(10)),
            pystray.MenuItem("%25", make_brightness_action(25)),
            pystray.MenuItem("%50", make_brightness_action(50)),
            pystray.MenuItem("%75", make_brightness_action(75)),
            pystray.MenuItem("%100", make_brightness_action(100)),
        ]

        # Profiller Alt Menüsü
        profile_items = []
        for name, val in self.config.profiles.items():
            profile_items.append(
                pystray.MenuItem(
                    f"{name} (%{val})",
                    make_profile_action(name)
                )
            )

        menu_items = [
            # Başlık (Tıklanamaz bilgi etiketi)
            pystray.MenuItem(status_tag, lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,

            # Hızlı Açılır Panel
            pystray.MenuItem("🎛️  Parlaklık Kontrolü (Aç)", lambda icon, item: self.on_open_popup(), default=True),

            # Alt Menüler
            pystray.MenuItem("🔆 Hızlı Parlaklık", pystray.Menu(*quick_items)),
            pystray.MenuItem("📋 Profiller", pystray.Menu(*profile_items)),
            pystray.Menu.SEPARATOR,

            # Monitör Yeniden Doğrulama
            pystray.MenuItem("🔄 Monitörü Yeniden Tara / Bağlan", lambda icon, item: self._on_rescan_clicked()),

            # Ayarlar
            pystray.MenuItem("⚙️ Ayarlar...", lambda icon, item: self.on_open_settings()),
            pystray.Menu.SEPARATOR,

            # Çıkış
            pystray.MenuItem("❌ Çıkış", lambda icon, item: self.on_exit()),
        ]

        return pystray.Menu(*menu_items)

    def _on_rescan_clicked(self):
        success = self.worker.rescan_monitors()
        cur_b = self.worker.get_current_brightness()
        self.update_icon_and_title(cur_b, self.worker.status)
