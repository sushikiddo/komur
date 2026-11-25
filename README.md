# Kömür — Masaüstü Kedisi (macOS & Windows)

**Onur Can Orhan · Sürüm 2.4.0 · macOS (Apple Silicon) & Windows 10/11 (x64)**

Kömür, gerçek siyah-beyaz smokin kedi Kömür'den ilham alınarak Python ve Tkinter ile geliştirilmiş, masaüstünde yaşayan hafif ve gerçekçi bir kedi arkadaştır. Hiçbir harici AI modeli veya ağır bağımlılık gerektirmez; pencerelerinin veya MacBook çentiğinin üstüne tüner, karton kutunun içine girip uyuklar, tam ekran video izlerken üst katmanda kalıp köşede sessizce uyur, diğer uygulamaların odağını çalmadan etkileşim kurar ve pil dostu çalışır.

---

## İndir — Platformunu Seç

| Platform | İndirme Paketi | Doğrulama | Gereksinimler |
| --- | --- | --- | --- |
| **🍎 macOS Sürümü (Apple Silicon · DMG)** | [Komur-2.4.0-macOS-arm64.dmg](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-macOS-arm64.dmg) | [SHA-256](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-macOS-arm64.dmg.sha256) | macOS 13+ (M1–M5), Python gerekmez |
| **🍎 macOS Sürümü (Apple Silicon · ZIP)** | [Komur-2.4.0-macOS-arm64.zip](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-macOS-arm64.zip) | [SHA-256](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-macOS-arm64.zip.sha256) | macOS 13+ (M1–M5), Python gerekmez |
| **🪟 Windows Sürümü (64-bit)** | [Komur-2.4.0-Windows-x64.exe](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-Windows-x64.exe) | [SHA-256](https://github.com/sushikiddo/komur/releases/download/v2.4.0/Komur-2.4.0-Windows-x64.exe.sha256) | Windows 10/11 x64, kurulum ve Python gerekmez |

- **Tüm sürümler:** [GitHub Releases](https://github.com/sushikiddo/komur/releases)
- **Portfolyo sayfası:** [onurcanorhan.pages.dev/komur.html](https://onurcanorhan.pages.dev/komur.html)
- **Eski Windows AI'lı sürüm arşivi (v2.2.2):** [`v2.2.2` Release](https://github.com/sushikiddo/komur/releases/tag/v2.2.2) / `komur-v1.2` dalı

---

## v2.4.0 Yenilikleri (macOS & Windows)

- **Fotoğraf sadakatinde gerçek Kömür & çevik kedi yürüyüşü:** İri badem sarı-yeşil gözler, kadife siyah yüz, bembeyaz bıyık/kaşlar, kar beyazı göğüs önlüğü, beyaz patiler ve hafif-çevik 4 zamanlı ev kedisi yürüyüşü (`feline_locomotion.py`, `cat_poses.py`, `renderer.py`).
- **Odak çalmayan yüzen pencereler (`NonactivatingPanel` / `WS_EX_NOACTIVATE`):** Kömür'e tek tıkla sevmek, sürüklemek veya Hızlı Menü'yü açmak Chrome, VS Code ya da diğer açık uygulamaları arka plana atmaz.
- **Tam ekran videoda üstte kal + köşede uyu:** Tam ekran YouTube/Netflix/VLC izlerken arka plana düşmez; en yakın alt köşeye süzülüp video bitene kadar sessizce uyur.
- **MacBook Çentik (`Notch Peek`) & Dock etkileşimi:** Çentikli MacBook'larda üst çentikten aşağı bakan özel poz; çentik yakınına sürükleyip bırakınca tutunur. Menü çubuğunda **Çentikten Bak**, **Dock Üstünde Gez** ve canlı **🍅 Odak (Pomodoro)** sayacı yer alır.
- **4 slotlu görsel Gardırop & 19 kıyafet/takı:** Baş, Göz, Boyun ve Gövde slotları aynı anda kombinlenebilir (ör. gözlük + atkı + şapka + kazak) ve Kontrol Paneli'nde görsel kartlarla seçilir (`wardrobe_ui.py`, `costumes.py`).
- **Pil dostu uyarlanabilir FPS & güç yönetimi:** Pil modunda, uykuda veya boşta kare hızı ve çizim otomatik kısılır (`power.py`); düşük güç modunu ve batarya durumunu otomatik algılar.
- **Özel uygulama simgesi & sürükle-bırak macOS DMG:** Özel tasarlanmış Kömür ikonu (`komur.icns` / `komur.ico`), sadeleştirilmiş paket boyutu (~34 MB) ve tek sürüklemeyle kurulan `.dmg` paketi.

---

## 🍎 macOS Sürümü (Apple Silicon)

### Kurulum
1. `Komur-2.4.0-macOS-arm64.dmg` (veya `.zip`) dosyasını indirip açın.
2. **Kömür.app** uygulamasını **Uygulamalar (`/Applications`)** klasörüne sürükleyin.
3. Paket Apple Developer sertifikasıyla imzalanmadığı için ilk açılışta macOS uyarı verirse: **Kömür.app'e sağ tık → Aç** yolunu kullanın veya Terminal'de `xattr -dr com.apple.quarantine /Applications/Kömür.app` çalıştırın.

### macOS'a Özel İyileştirmeler
- **Tam ekran filmlerin ve Spaces'ın üstünde kalır:** `kCGScreenSaverWindowLevel` + `FullScreenAuxiliary` desteği ile YouTube, Netflix, VLC, IINA tam ekranındayken kaybolmaz, en yakın alt köşeye çekilip uyur.
- **Odak çalmayan tek tık & 2 parmak Hızlı Menü:** Yerel `NSPanel` (`NonactivatingPanel`) sayesinde Chrome veya başka bir uygulama etkinken Kömür'ü sevmek, sürüklemek ya da 2 parmakla Hızlı Menü'yü kullanmak aktif uygulamayı arka plana atmaz.
- **MacBook Çentiği & Menü çubuğu:** Çentikten bakan özel poz (`notch_peek`), üst menü çubuğunda canlı Pomodoro geri sayımı ve tek tıkla gizle/göster.
- **Şeffaf gölgesiz pencere & pil dostu motor:** Core Image siyah anahtarlama (`CIColorCubeWithColorSpace`) ve pilde uyarlanabilir FPS.
- **Veri ve başlangıç:** Ayarlar `~/Library/Application Support/Komur` altında saklanır; "Oturum Açılınca Başlat" `~/Library/LaunchAgents/com.sushikiddo.komur.plist` kullanır.

---

## 🪟 Windows Sürümü (Windows 10/11 x64)

### Kurulum
1. `Komur-2.4.0-Windows-x64.exe` dosyasını indirin ve doğrudan çalıştırın (kurulum veya Python gerekmez).
2. EXE kod imzalı olmadığı için Windows SmartScreen uyarısı çıkarsa **Ek bilgi → Yine de çalıştır** seçeneğini kullanın.
3. İsteğe bağlı SHA-256 doğrulaması:
   ```powershell
   Get-FileHash .\Komur-2.3.0-Windows-x64.exe -Algorithm SHA256
   ```

### Windows'a Özel Özellikler
- **Tek dosya taşınabilir EXE:** PyInstaller ile paketlenir; tüm yeni gerçekçi Kömür çizimleri, `cat_poses` animasyonları, oyuncaklar ve gerçek kedi WAV sesleri paket içinde gelir.
- **Yerel Windows entegrasyonu:** Sistem tepsisi (`tray.py`), global kısayollar (`Ctrl+Shift+K` Kontrol Paneli, `Ctrl+Shift+H` Patron Tuşu), görev çubuğu üstünde yürüme, `winsound` / `pygame.mixer` gerçek kedi sesleri ve `HKCU\...\Run` başlangıç desteği.
- **Veri konumu:** `%LOCALAPPDATA%\Komur`

---

## Kontroller ve Komutlar

- **Sağ tık (macOS: 2 parmak tık veya `Control+Tık`):** Koyu cam Hızlı Menü (Mama, Sev, Kutu, Süt, Tırmalama, Yumak, Pencereye Tüne, Hava Durumu, Ses Aç/Kapat, Kontrol Paneli, Sohbet).
- **Sol tık + sürükle:** Kediyi masaüstünde istediğin yere taşı.
- **Orta tık veya Hızlı Menü → 💬 Sohbet:** Hızlı komut kutusu (`uyu`, `uyan`, `gerin`, `yuvarlan`, `not defterini aç`, `sesi %30 yap`, `5 dakika sonra mola hatırlat`, `hava nasıl`, `zar at` vb.).
- **F1:** Kontrol Panelini açar · **Esc:** Gezinme moduna döner.

---

## Kaynaktan Çalıştırma ve Derleme

### macOS
```bash
brew install python-tk@3.15   # Homebrew Python'a Tk desteği (bir kez)
python3 -m venv .venv
.venv/bin/pip install pytest pyinstaller
.venv/bin/python cat.py

# Kömür.app paketi derleme:
.venv/bin/pyinstaller --noconfirm Komur-mac.spec
```

### Windows (PowerShell)
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pytest pyinstaller pygame Pillow
python cat.py

# Komur.exe paketi derleme:
pyinstaller --noconfirm Komur.spec
```

### Testler
```bash
.venv/bin/pytest -q --tb=short
```

---

## Mimari & Gizlilik

| Modül | Görev |
| --- | --- |
| `cat.py` | Ana uygulama döngüsü, menüler, etkinlik tepkileri ve alt sistem bağlantıları |
| `renderer.py`, `cat_poses.py`, `feline_locomotion.py` | Gerçekçi Kömür çizimi, 7 tema, 4 zamanlı yürüyüş ve tüm aktivite pozları |
| `desktop_toys.py`, `desktop_physics.py`, `needs.py`, `behavior.py` | Oyuncak pencereleri, pencere tüneme fiziği, ihtiyaçlar ve yaşam döngüsü |
| `window_utils.py`, `tray.py`, `autostart.py` | Windows (`user32`) ve macOS (`AppKit` / `CoreGraphics` / `CoreImage`) pencere katmanı |
| `sounds.py`, `audio.py`, `effects.py`, `acoustic_engine.py` | Gerçek kedi WAV sesleri, stereo pan, perde varyasyonu ve görsel parçacıklar |
| `context.py`, `awareness.py`, `activity_reactions.py`, `weather.py` | Yerel etkinlik farkındalığı ve isteğe bağlı Open-Meteo hava durumu |
| `context_hud.py`, `panel.py`, `chat_bubble.py`, `bubble.py`, `companion.py` | Sağ tık HUD, Kontrol Paneli, komut balonu ve arkadaş kediler |

- **Gizlilik:** Pencere ve medya başlıkları yalnızca bellekte sınıflandırılır; diske yazılmaz, ağa gönderilmez. Hava durumu varsayılan olarak kapalıdır; açılırsa yalnızca şehir adı Open-Meteo'ya sorgulanır.
- **AI katkısı:** Proje AI araçlarından destek alınarak geliştirildi.
