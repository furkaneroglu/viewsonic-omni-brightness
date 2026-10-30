# 🖥️ ViewSonic OMNI DDC/CI Brightness Control

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-blue.svg)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://python.org)
[![Build](https://img.shields.io/badge/Build-PyInstaller%20Standalone%20EXE-orange.svg)]()

A lightweight, hardware-protected, system tray application for controlling the brightness of **ViewSonic OMNI** (and other DDC/CI-compliant) monitors over HDMI / DisplayPort using the VESA DDC/CI (MCCS VCP `0x10`) protocol.

No physical monitor buttons needed — adjust brightness with a slick taskbar slider, predefined profiles, or global keyboard hotkeys with a floating on-screen display (OSD HUD)!

---

## ⚡ Quick Start (For End-Users)

You don't need Python or any developer tools!

1. Download **`ViewSonic_OMNI_Brightness.exe`** from the [**Releases**](../../releases) page.
2. Double-click the `.exe` file.
3. The app will immediately appear in your Windows system tray (near the clock) as a ☀️ icon.
4. *(Optional)* Right-click the tray icon ➔ **Settings...** ➔ Check **"Run on Windows Startup"** so it starts automatically with Windows!

---

## 🌟 Key Features

* **🎛️ System Tray & Quick Slider:** Click the golden sun icon in the notification area to open a sleek dark-themed popup with a live brightness slider, stepper buttons (`-10%`, `-5%`, `+5%`, `+10%`), and one-click profile buttons.
* **⌨️ Global Hotkeys:** Control brightness anytime, anywhere (even while gaming full-screen):
  * `Ctrl + Alt + Up`: Brightness **+5%**
  * `Ctrl + Alt + Down`: Brightness **-5%**
  * `Ctrl + Alt + 1`: **Day Profile (80%)**
  * `Ctrl + Alt + 2`: **Night Profile (20%)**
  * `Ctrl + Alt + 3`: **Reading Profile (40%)**
  * `Ctrl + Alt + 4`: **Gaming Profile (90%)**
* **🖥️ On-Screen Display (OSD HUD):** Changing brightness via hotkeys displays a semi-transparent, modern floating HUD bar that smoothly auto-dismisses after 1.4 seconds.
* **🛡️ Hardware Protection (Debounce & Throttling):** DDC/CI communicates over an I2C bus at 100 kHz. Flooding it with commands can freeze the monitor microcontroller. This app applies **80ms debounce coalescing** and **100ms hardware throttling** — your UI stays 100% responsive while your monitor's I2C bus stays safe.
* **🔄 Fault-Tolerant Watchdog:** When your monitor enters DPMS sleep mode or powers off, the app won't crash or freeze. The background watchdog service silently polls and re-syncs brightness as soon as the monitor wakes up.
* **🔔 Windows Toast Notifications:** Alerts you if DDC/CI communication drops or when the monitor reconnects, complete with spam suppression.
* **🔒 Single Instance Protection:** Win32 Mutex prevents accidental duplicate background processes.

---

## ⌨️ Default Keyboard Shortcuts

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Ctrl + Alt + ↑` | **Brightness Up** | Increases brightness by 5% (configurable) |
| `Ctrl + Alt + ↓` | **Brightness Down** | Decreases brightness by 5% (configurable) |
| `Ctrl + Alt + 1` | **Day Profile** | Sets brightness directly to **80%** |
| `Ctrl + Alt + 2` | **Night Profile** | Sets brightness directly to **20%** |
| `Ctrl + Alt + 3` | **Reading Profile** | Sets brightness directly to **40%** |
| `Ctrl + Alt + 4` | **Gaming Profile** | Sets brightness directly to **90%** |

*All shortcuts and percentages can be fully customized in the Settings window or via `%APPDATA%\ViewSonicOmniTray\config.json`.*

---

## 🛠️ Architecture & Technologies

```
viewsonic-omni-brightness/
├── .github/workflows/       # CI/CD: Automated EXE builds on release
├── viewsonic_omni_tray/     # Core application package
│   ├── monitor_manager.py   # Windows Dxva2 & User32 DDC/CI hardware abstraction
│   ├── queue_worker.py      # Async rate-limiting queue & Watchdog reconnection
│   ├── config.py            # JSON configuration & Windows startup registry
│   ├── tray.py              # Pystray dynamic icon & context menu
│   ├── popup.py             # Sleek taskbar slider & preset buttons
│   ├── hotkeys.py           # pynput global hotkey listener
│   ├── osd.py               # Tkinter floating On-Screen Display HUD
│   ├── notifications.py     # Windows tray notifications & spam filter
│   ├── app.py               # Coordinator & Win32 single instance mutex
│   └── main.py              # Application entry point
├── tests/                   # Unit & timing test suite
├── build.py                 # One-click PyInstaller build script
├── requirements.txt
└── LICENSE                  # MIT License
```

* **Windows High-Level Monitor API:** Uses Windows `dxva2.dll` and `user32.dll` via Python's standard `ctypes` library.
* **Zero Bloatware:** Built with native Tkinter and lightweight libraries (`pystray`, `Pillow`, `pynput`). Consumes **< 25 MB RAM** and starts in under 100 ms.

---

## 💻 Developer Setup & Building from Source

### Prerequisites
* Windows 10 or 11
* Python 3.8+
* HDMI or DisplayPort connection directly to your GPU.
* DDC/CI enabled in your monitor's OSD menu: `Setup Menu -> DDC/CI -> On`.

### 1. Clone the repository
```bash
git clone https://github.com/furkaneroglu/viewsonic-omni-brightness.git
cd viewsonic-omni-brightness
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run directly from Python
```bash
python -m viewsonic_omni_tray.main
```

### 4. Run automated tests
```bash
python -m unittest discover -s tests -v
```

### 5. Build standalone `.exe`
```bash
python build.py
```
This generates `ViewSonic_OMNI_Brightness.exe` in the root folder.

---

## ❓ Troubleshooting

* **Monitör bulunamadı / DDC/CI Hatası:**
  1. Monitörünüzün fiziksel joystick/tuşları ile OSD Menüsüne girin: `[Setup Menu / Ayarlar] -> [DDC/CI]` seçeneğinin **Açık (On / Enabled)** olduğunu doğrulayın.
  2. HDMI veya DisplayPort kablosunun doğrudan ekran kartınıza bağlı olduğundan emin olun (bazı pasif dönüştürücüler veya ucuz USB-C hub'lar I2C/DDC sinyal hattını kesebilir).
  3. Ekran kartı sürücülerinizin güncel olduğunu kontrol edin.

---

## 🇹🇷 Türkçe Özet

ViewSonic OMNI serisi monitörlerin parlaklığını DDC/CI protokolü üzerinden yöneten, sistem tepsisinde (saat yanında) arka planda sessizce çalışan ve klavye kısayolları ile kontrol edilebilen hafif masaüstü uygulamasıdır.

* **Hazır EXE Kullanımı:** [Releases](../../releases) sayfasından `ViewSonic_OMNI_Brightness.exe` dosyasını indirip çift tıklamanız yeterlidir (Python kurulumu gerektirmez).
* **Kısayollar:** `Ctrl+Alt+Yukarı/Aşağı` ile parlaklığı 5'er 5'er değiştirin, `Ctrl+Alt+1..4` ile profiller arasında geçiş yapın. Ekranda şık bir OSD göstergesi belirir.
* **Donanım Koruması:** Hızlı slider hareketlerinde I2C yolu kilitlenmez (80ms debounce & 100ms throttle).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
