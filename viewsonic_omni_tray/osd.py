"""
ViewSonic OMNI DDC/CI Tray - On-Screen Display (OSD HUD) Overlay
Kısayol tuşları veya harici değişimlerde ekranda beliren şık, modern parlaklık göstergesi.
"""

import tkinter as tk
from typing import Optional
from .config import AppConfig

class OSDOverlay:
    """Ekran üzerinde şık, yarı saydam ve otomatik kaybolan OSD HUD penceresi."""

    def __init__(self, root: tk.Tk, config: AppConfig):
        self.root = root
        self.config = config
        self._window: Optional[tk.Toplevel] = None
        self._hide_timer_id: Optional[str] = None

        self.width = 340
        self.height = 110
        self._create_window()

    def _create_window(self):
        self._window = tk.Toplevel(self.root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.attributes("-alpha", 0.94)
        self._window.configure(bg="#18181b")

        # Kenarlık ve arka plan taşıyıcı frame
        self.frame = tk.Frame(self._window, bg="#18181b", highlightbackground="#3f3f46", highlightthickness=1)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Üst bilgi satırı: Monitör Adı ve Eylem
        self.title_label = tk.Label(
            self.frame,
            text="ViewSonic OMNI",
            font=("Segoe UI", 10, "bold"),
            fg="#a1a1aa",
            bg="#18181b"
        )
        self.title_label.pack(pady=(12, 2))

        # Yüzde ve İkon satırı
        self.value_label = tk.Label(
            self.frame,
            text="☀️ Parlaklık: %50",
            font=("Segoe UI", 13, "bold"),
            fg="#f4f4f5",
            bg="#18181b"
        )
        self.value_label.pack(pady=(0, 8))

        # Modern Parlaklık Barı (Canvas)
        self.canvas = tk.Canvas(
            self.frame,
            width=280,
            height=14,
            bg="#18181b",
            highlightthickness=0
        )
        self.canvas.pack(pady=(0, 12))

    def show(self, monitor_name: str, brightness: int, action_title: Optional[str] = None):
        """OSD HUD penceresini konumlandırır, günceller ve gösterir."""
        if not self.config.show_osd:
            return

        if self._window is None:
            self._create_window()

        # İptal edilmiş eski zamanlayıcı varsa temizle
        if self._hide_timer_id is not None:
            self.root.after_cancel(self._hide_timer_id)
            self._hide_timer_id = None

        # Metinleri güncelle
        header = action_title if action_title else monitor_name
        self.title_label.config(text=header)

        # Parlaklık değerine göre ikon seçimi
        if brightness >= 70:
            sun_icon = "☀️"
        elif brightness >= 35:
            sun_icon = "🌤️"
        else:
            sun_icon = "🌙"

        self.value_label.config(text=f"{sun_icon}  Parlaklık: %{brightness}")

        # Barı çiz
        self.canvas.delete("all")
        bar_w = 280
        bar_h = 14
        radius = 6

        # Arka plan barı (Koyu gri kapsül)
        self._draw_pill(self.canvas, 0, 0, bar_w, bar_h, radius=radius, fill="#27272a")

        # Doluluk barı (Canlı kehribar/altın kapsül)
        fill_w = max(0, min(bar_w, int(bar_w * (brightness / 100.0))))
        if fill_w > radius * 2:
            self._draw_pill(self.canvas, 0, 0, fill_w, bar_h, radius=radius, fill="#f59e0b")
        elif fill_w > 0:
            self.canvas.create_rectangle(0, 0, fill_w, bar_h, fill="#f59e0b", outline="")

        # Ekranın alt-orta kısmına konumlandır
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = screen_h - self.height - 110

        self._window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self._window.deiconify()
        self._window.lift()

        # Süre dolunca gizle
        duration = self.config.data.get("ui", {}).get("osd_duration_ms", 1400)
        self._hide_timer_id = self.root.after(duration, self.hide)

    def hide(self):
        """Pencereyi gizler."""
        if self._window is not None:
            self._window.withdraw()
        self._hide_timer_id = None

    @staticmethod
    def _draw_pill(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int = 6, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)
