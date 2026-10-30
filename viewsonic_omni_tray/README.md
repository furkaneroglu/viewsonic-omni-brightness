# 🖥️ ViewSonic OMNI - DDC/CI Sistem Tepsisi (Tray) ve Kısayol Yöneticisi

ViewSonic OMNI serisi masaüstü monitörlerin (HDMI / DisplayPort) parlaklık seviyesini doğrudan **DDC/CI (VESA MCCS)** donanım protokolü üzerinden yöneten, sistem tepsisinde (system tray) arka planda çalışan, donanım korumalı (debounce/throttling) ve küresel klavye kısayolları ile kontrol edilebilen hafif bir Windows masaüstü uygulamasıdır.

---

## 🚀 Temel Özellikler

1. **Sistem Tepsisi (Tray App):**
   - Windows bildirim alanında (sağ altta) sessizce çalışır.
   - Pillow ile dinamik üretilen, anlık parlaklık seviyesini ve bağlantı durumunu (Bağlı/Uykuda/Hata) yansıtan akıllı simge.
   - Simgeye sol tıklandığında modern koyu temalı hızlı kontrol paneli (Slider Popup) açılır.
   - Sağ tık menüsünden hızlı yüzdelere (%10, %25, %50, %75, %100) ve ön tanımlı profillere tek tıkla erişim.

2. **Donanım Koruması (Debounce & Throttling):**
   - Monitörün I2C mikrodenetleyici veri yolunun kilitlenmemesi için **hızlı slider ve kısayol hareketlerine 80ms debounce** ve ardışık donanım yazımları arasına **en az 100ms throttling** uygulanır.
   - Kullanıcı arayüzünde (slider / OSD) 0 gecikme hissi korunurken, donanıma sadece filtrelenmiş son hedef değer gönderilir (coalescing).

3. **Hata Yönetimi ve Otomatik Yeniden Bağlantı (Watchdog):**
   - Monitör DPMS uyku moduna geçtiğinde (`0xC0262585`, `ERROR_GEN_FAILURE`, `ERROR_INVALID_HANDLE`) uygulama asla kilitlenmez veya çökmez.
   - Arka plandaki **Watchdog** servisi monitörün uyanmasını periyodik olarak (varsayılan 15 saniyede bir) kontrol eder ve uyanır uyanmaz son istenen parlaklığı otomatik olarak uygular.

4. **Klavye Kısayolları (Global Hotkeys) & Ekran HUD'ı (OSD):**
   - Hangi oyunda veya uygulamada olursanız olun klavyeden parlaklığı anında değiştirin.
   - Kısayol kullanıldığında ekranın altında yarı saydam, modern bir **OSD HUD (On-Screen Display)** belirir ve 1.4 saniye sonra zarifçe kaybolur.

5. **Ön Tanımlı Profiller:**
   - ☀️ **Gündüz:** %80
   - 🌙 **Gece:** %20
   - 📖 **Okuma:** %40
   - 🎮 **Oyun:** %90
   - 🎬 **Sinema:** %30

---

## ⌨️ Varsayılan Kısayol Tuşları (Hotkeys)

| Kısayol | Eylem | Açıklama |
| :--- | :--- | :--- |
| `Ctrl + Alt + ↑` (Yukarı) | **Parlaklık Artır** | Parlaklığı %5 (veya ayarlanan adım kadar) artırır |
| `Ctrl + Alt + ↓` (Aşağı) | **Parlaklık Azalt** | Parlaklığı %5 (veya ayarlanan adım kadar) azaltır |
| `Ctrl + Alt + 1` | **Gündüz Profili** | Parlaklığı doğrudan %80 seviyesine getirir |
| `Ctrl + Alt + 2` | **Gece Profili** | Parlaklığı doğrudan %20 seviyesine getirir |
| `Ctrl + Alt + 3` | **Okuma Profili** | Parlaklığı doğrudan %40 seviyesine getirir |
| `Ctrl + Alt + 4` | **Oyun Profili** | Parlaklığı doğrudan %90 seviyesine getirir |

*Not: Tüm kısayollar, adım boyutları ve yüzdeler Ayarlar penceresinden veya `config.json` dosyasından dilediğiniz gibi özelleştirilebilir.*

---

## 📂 Proje Mimarisi

```
viewsonic_omni_tray/
├── config.py       # JSON ayar yönetimi & Windows Startup (Run) Registry
├── ddcci.py        # Windows Dxva2 High-Level Monitor API (ctypes) sarmalayıcısı
├── controller.py   # Debounce & Throttling motoru, durum makinesi, Watchdog
├── hotkeys.py      # pynput GlobalHotKeys yöneticisi
├── osd.py          # Ekran üzeri On-Screen Display HUD parlaklık göstergesi
├── popup.py        # Görev çubuğunda açılan Slider ve Hızlı Profil paneli
├── settings.py     # Detaylı ayarlar ve yapılandırma penceresi
├── tray.py         # pystray & Pillow sistem tepsisi ikonu ve sağ tık menüsü
├── app.py          # Ana uygulama koordinatörü & Win32 Mutex tekil örnek denetimi
├── main.py         # Giriş noktası (Konsollu başlatıcı)
└── tests/          # Birim ve entegrasyon testleri
```

---

## 🛠️ Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.8+ (Windows 10 veya 11)
- ViewSonic OMNI monitörünün HDMI veya DisplayPort kablosu ile doğrudan ekran kartına bağlı olması.
- Monitörün fiziksel OSD menüsünde DDC/CI ayarının **Açık (On / Enabled)** olması (`Setup Menu -> DDC/CI -> On`).

### Bağımlılıkların Kurulumu
Uygulama `pystray`, `Pillow` ve `pynput` kullanır:
```bash
pip install pystray pillow pynput
```

### Çalıştırma Yöntemleri
1. **Sessiz Arka Plan (Önerilen):**
   ```bash
   pythonw run_viewsonic_tray.pyw
   ```
   veya doğrudan `start_tray_silently.vbs` ya da `run_tray.bat` dosyasına çift tıklayın.

2. **Konsol Günlükleriyle Çalıştırma (Hata ayıklama):**
   ```bash
   python -m viewsonic_omni_tray.main
   ```

3. **Windows Açılışında Otomatik Başlatma:**
   - Sistem tepsisinde simgeye sağ tıklayıp **Ayarlar**'ı açın.
   - *"Windows açılışında otomatik başlat"* seçeneğini işaretleyip **Kaydet**'e tıklayın.

---

## 🧪 Testlerin Çalıştırılması

Tüm donanım iletişimini, debounce/throttling kuyruğunu ve Win32 Mutex mekanizmasını doğrulamak için:
```bash
python viewsonic_omni_tray/tests/test_tray_app.py
```
