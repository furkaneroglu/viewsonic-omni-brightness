"""
ViewSonic OMNI DDC/CI Tray - Taskbar Slider & Presets Popup (Tray UI)
Sistem tepsisi simgesine tıklandığında açılan modern, karanlık temalı hızlı kontrol paneli.
"""

import tkinter as tk
from typing import Optional, Callable
from .config import ConfigManager
from .queue_worker import AsyncWriteQueueWorker, MonitorStatus

class SliderPopup:
    """Görev çubuğu üzerinde açılan hızlı parlaklık ve profil kontrol penceresi."""

    def __init__(self, root: tk.Tk, config: ConfigManager, worker: AsyncWriteQueueWorker, on_open_settings: Optional[Callable[[], None]] = None):
        self.root = root
        self.config = config
        self.worker = worker
        self.on_open_settings = on_open_settings

        self.width = 360
        self.height = 370
        self._window: Optional[tk.Toplevel] = None
        self._is_dragging = False

        self._create_window()

    def _create_window(self):
        self._window = tk.Toplevel(self.root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(bg="#18181b")

        # Odak kaybedildiğinde otomatik gizleme
        self._window.bind("<FocusOut>", self._on_focus_out)
        self._window.bind("<Escape>", lambda e: self.hide())

        # Ana çerçeve (Kenarlıklı)
        main_frame = tk.Frame(
            self._window,
            bg="#18181b",
            highlightbackground="#3f3f46",
            highlightthickness=1,
            padx=16,
            pady=14
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Başlık ve Durum Satırı
        header_frame = tk.Frame(main_frame, bg="#18181b")
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_sub_frame = tk.Frame(header_frame, bg="#18181b")
        title_sub_frame.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(
            title_sub_frame,
            text="ViewSonic OMNI",
            font=("Segoe UI", 11, "bold"),
            fg="#f4f4f5",
            bg="#18181b"
        )
        self.title_lbl.pack(anchor="w")

        self.desc_lbl = tk.Label(
            title_sub_frame,
            text="VX2718-2KPC",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#18181b"
        )
        self.desc_lbl.pack(anchor="w")

        # Durum rozeti (Pill)
        self.status_badge = tk.Label(
            header_frame,
            text="● Bağlı",
            font=("Segoe UI", 9, "bold"),
            fg="#10b981", # Emerald yeşil
            bg="#27272a",
            padx=8,
            pady=3
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Ayırıcı çizgi
        sep1 = tk.Frame(main_frame, height=1, bg="#27272a")
        sep1.pack(fill=tk.X, pady=(4, 12))

        # 2. Parlaklık Değeri ve Slider
        val_frame = tk.Frame(main_frame, bg="#18181b")
        val_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            val_frame,
            text="Parlaklık",
            font=("Segoe UI", 10, "bold"),
            fg="#e4e4e7",
            bg="#18181b"
        ).pack(side=tk.LEFT)

        self.brightness_text_lbl = tk.Label(
            val_frame,
            text="%50",
            font=("Segoe UI", 12, "bold"),
            fg="#f59e0b", # Amber
            bg="#18181b"
        )
        self.brightness_text_lbl.pack(side=tk.RIGHT)

        # Tkinter Scale Slider
        self.scale_var = tk.IntVar(value=50)
        self.scale = tk.Scale(
            main_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.scale_var,
            showvalue=False,
            bg="#27272a",
            troughcolor="#18181b",
            activebackground="#f59e0b",
            highlightthickness=0,
            relief=tk.FLAT,
            sliderrelief=tk.FLAT,
            length=320,
            command=self._on_slider_moved
        )
        self.scale.pack(fill=tk.X, pady=(4, 8))

        # 3. Kademeli Değişim Butonları (-10%, -5%, +5%, +10%)
        stepper_frame = tk.Frame(main_frame, bg="#18181b")
        stepper_frame.pack(fill=tk.X, pady=(0, 12))

        for text, delta in [("-10%", -10), ("-5%", -5), ("+5%", +5), ("+10%", +10)]:
            btn = tk.Button(
                stepper_frame,
                text=text,
                font=("Segoe UI", 8, "bold"),
                fg="#d4d4d8",
                bg="#27272a",
                activebackground="#3f3f46",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=4,
                command=lambda d=delta: self._on_step(d)
            )
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Ayırıcı çizgi
        sep2 = tk.Frame(main_frame, height=1, bg="#27272a")
        sep2.pack(fill=tk.X, pady=(0, 10))

        # 4. Hızlı Profiller Bölümü
        tk.Label(
            main_frame,
            text="Ön Tanımlı Profiller",
            font=("Segoe UI", 9, "bold"),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 6))

        presets_frame = tk.Frame(main_frame, bg="#18181b")
        presets_frame.pack(fill=tk.X, pady=(0, 14))

        profiles = [
            ("☀️ Gündüz (%80)", "Gündüz"),
            ("🌙 Gece (%20)", "Gece"),
            ("📖 Okuma (%40)", "Okuma"),
            ("🎮 Oyun (%90)", "Oyun"),
        ]

        row1 = tk.Frame(presets_frame, bg="#18181b")
        row1.pack(fill=tk.X, pady=2)
        row2 = tk.Frame(presets_frame, bg="#18181b")
        row2.pack(fill=tk.X, pady=2)

        for i, (label_txt, prof_name) in enumerate(profiles):
            target_row = row1 if i < 2 else row2
            btn = tk.Button(
                target_row,
                text=label_txt,
                font=("Segoe UI", 8),
                fg="#f4f4f5",
                bg="#27272a",
                activebackground="#f59e0b",
                activeforeground="#18181b",
                relief=tk.FLAT,
                bd=0,
                pady=6,
                command=lambda p=prof_name: self._on_profile_click(p)
            )
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 5. Alt Bar: Ayarlar ve Kapat
        bottom_frame = tk.Frame(main_frame, bg="#18181b")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        settings_btn = tk.Button(
            bottom_frame,
            text="⚙️ Ayarlar",
            font=("Segoe UI", 8),
            fg="#a1a1aa",
            bg="#18181b",
            activebackground="#27272a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            command=self._on_settings_click
        )
        settings_btn.pack(side=tk.LEFT)

        close_btn = tk.Button(
            bottom_frame,
            text="Kapat",
            font=("Segoe UI", 8),
            fg="#a1a1aa",
            bg="#18181b",
            activebackground="#27272a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            command=self.hide
        )
        close_btn.pack(side=tk.RIGHT)

    def _on_slider_moved(self, val_str: str):
        val = int(val_str)
        self.brightness_text_lbl.config(text=f"%{val}")
        self.worker.set_brightness(val, immediate_ui=False)

    def _on_step(self, delta: int):
        cur = self.scale_var.get()
        new_val = max(0, min(100, cur + delta))
        self.scale_var.set(new_val)
        self.brightness_text_lbl.config(text=f"%{new_val}")
        self.worker.set_brightness(new_val, immediate_ui=True)

    def _on_profile_click(self, profile_name: str):
        self.worker.apply_profile(profile_name)
        new_val = self.worker.get_current_brightness()
        self.scale_var.set(new_val)
        self.brightness_text_lbl.config(text=f"%{new_val}")

    def _on_settings_click(self):
        self.hide()
        if self.on_open_settings:
            self.on_open_settings()

    def update_values(self, brightness: int, status: MonitorStatus, active_desc: Optional[str] = None):
        """Dışarıdan gelen güncellemelerle popup arayüzünü tazeler."""
        self.scale_var.set(brightness)
        self.brightness_text_lbl.config(text=f"%{brightness}")

        if active_desc:
            self.desc_lbl.config(text=active_desc)

        if status == MonitorStatus.CONNECTED:
            self.status_badge.config(text="● Bağlı", fg="#10b981")
        elif status == MonitorStatus.SLEEPING:
            self.status_badge.config(text="● Uykuda", fg="#f59e0b")
        else:
            self.status_badge.config(text="● Bağlantı Yok", fg="#ef4444")

    def toggle(self):
        if self._window is not None and self._window.winfo_viewable():
            self.hide()
        else:
            self.show()

    def show(self):
        if self._window is None:
            self._create_window()

        cur_b = self.worker.get_current_brightness()
        desc = self.worker.active_device.description if self.worker.active_device else "Bilinmeyen Monitör"
        self.update_values(cur_b, self.worker.status, desc)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - self.width - 16
        y = sh - self.height - 54

        self._window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()

    def hide(self):
        if self._window is not None:
            self._window.withdraw()

    def _on_focus_out(self, event):
        if self._window is not None and self._window.winfo_viewable():
            focused = self._window.focus_get()
            if focused is None:
                self.hide()
