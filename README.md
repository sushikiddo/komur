# Kömür — Masaüstü Kedisi (macOS & Windows)

**Onur Can Orhan · Sürüm 2.3.0 · macOS (Apple Silicon) & Windows 10/11 (x64)**

Kömür, gerçek siyah-beyaz smokin kedi Kömür'den ilham alınarak Python ve Tkinter ile geliştirilmiş, masaüstünde yaşayan hafif ve gerçekçi bir kedi arkadaştır. Hiçbir harici AI modeli veya ağır bağımlılık gerektirmez; pencerelerinin üstüne tüner, karton kutunun içine girip uyuklar, süt içer, tırmalama tahtasını tırmalar, yaptığın etkinliğe sakin tepkiler verir ve gerçek kedi sesleriyle eşlik eder.

---

## İndir — Platformunu Seç

| Platform | İndirme Paketi | Doğrulama | Gereksinimler |
| --- | --- | --- | --- |
| **🍎 macOS Sürümü (Apple Silicon)** | [Komur-2.3.0-macOS-arm64.zip](https://github.com/sushikiddo/komur/releases/download/v2.3.0/Komur-2.3.0-macOS-arm64.zip) | [SHA-256](https://github.com/sushikiddo/komur/releases/download/v2.3.0/Komur-2.3.0-macOS-arm64.zip.sha256) | macOS (M1–M5), Python gerekmez |
| **🪟 Windows Sürümü (64-bit)** | [Komur-2.3.0-Windows-x64.exe](https://github.com/sushikiddo/komur/releases/download/v2.3.0/Komur-2.3.0-Windows-x64.exe) | [SHA-256](https://github.com/sushikiddo/komur/releases/download/v2.3.0/Komur-2.3.0-Windows-x64.exe.sha256) | Windows 10/11 x64, kurulum ve Python gerekmez |

- **Tüm sürümler:** [GitHub Releases](https://github.com/sushikiddo/komur/releases)
- **Portfolyo sayfası:** [onurcanorhan.pages.dev/komur.html](https://onurcanorhan.pages.dev/komur.html)
- **Eski Windows AI'lı sürüm arşivi (v2.2.2):** [`v2.2.2` Release](https://github.com/sushikiddo/komur/releases/tag/v2.2.2) / `komur-v1.2` dalı

---

## v2.3.0 Yenilikleri (macOS & Windows)

- **Gerçek Kömür'e göre yenilenmiş çizim ve 7 kürk teması:** Siyah pelüş yüz, iri sarı-yeşil parlak gözler, uzun beyaz bıyıklar ve kaş kılları, geniş kar beyazı göğüs önlüğü, beyaz pati uçları ve dolgun kuyruk (`komur`, `zencefil`, `gri`, `pamuk`, `gece`, `kahve`, `altin`).
- **Gerçek kedi yürüyüşü ve doğal hareketler:** 3/4 profil baş, dolgun bacaklar ve 4 zamanlı gerçekçi yürüyüş döngüsü; patiyi yalayıp yanak/kulak yıkayan 3 aşamalı tımarlanma (`groom`); öne uzanıp beli çukurlaştıran gerçek gerinme (`stretch`); kıvrık dilli esneme (`yawn`) ve kuyruğa sarılı uyku (`sleep`).
- **Tam animasyonlu masaüstü aktiviteleri:**
  - **📦 Karton Kutu:** Kedi gerçekten kutunun içine girer, ön patilerini kenara yaslar ve bir süre sonra içine gömülüp uyuklar.
  - **🪟 Pencereye Tüneme:** Aktif pencerenin üst kenarına zıplayıp kuyruğunu kenardan aşağı sarkıtarak tüner; pencere taşınınca birlikte gider.
  - **🥛 Süt Kâsesi:** Eğilip pembe diliyle süt içer, süt halkası ve damlacıklar oluşur.
  - **🪵 Tırmalama Tahtası:** Arka ayakları üzerinde dikilip iki ön patisiyle sırayla tırmalar.
  - **🧶 İplik Yumağı:** Sürüklenip fırlatılabilen yumak, pencerelerden ve ekran kenarlarından seker.
- **Gerçek kedi sesleri & tek tıkla sessize alma:** Sentetik sesler kaldırılıp özgür lisanslı gerçek kedi kayıtları eklendi. Top oynarken veya dolaşırken gürültü yapmaz — sesler yalnızca **sevince (mırlama)**, **esnerken** ve **uyanırken (yumuşak miyavlama)** çalar. Hızlı Menü'de tek tıkla **🔊 Ses Açık / 🔇 Ses Kapalı** ayarı bulunur.
- **Sakin ve gerçekçi etkinlik tepkileri:** Tam ekran video/film izlerken altyazıyı kapatmadan alt köşeye çekilip sakin izler (abartılı çizgi-film efektleri kaldırıldı); müzikte hafif kulak/kuyruk ritmi yapar; boştan/uzaktan dönünce gerinip selamlar; yemek/süt sonrası kendiliğinden tımarlanır.
- **Lazer modu kaldırıldı:** Sağ tık Hızlı Menü ve Kontrol Paneli sadeleştirildi.

---

## 🍎 macOS Sürümü (Apple Silicon)

### Kurulum
1. `Komur-2.3.0-macOS-arm64.zip` dosyasını indirip çift tıklayarak açın.
2. İçinden çıkan **Kömür.app** uygulamasını **Uygulamalar (`/Applications`)** klasörüne sürükleyin.
3. Paket Apple Developer sertifikasıyla imzalanmadığı için ilk açılışta macOS uyarı verirse: **Kömür.app'e sağ tık → Aç** yolunu kullanın veya Terminal'de `xattr -dr com.apple.quarantine /Applications/Kömür.app` çalıştırın.

### macOS'a Özel İyileştirmeler
- **Tam ekran filmlerin ve Spaces'ın üstünde kalır:** `kCGScreenSaverWindowLevel` + `FullScreenAuxiliary` desteği ile YouTube, Netflix, VLC, IINA tam ekranındayken kaybolmaz.
- **Touchpad'de ilk seferde 2 parmak sağ tık:** Başka bir uygulama (Chrome, Safari, VS Code vb.) etkinken bile kedi üstüne tek seferde 2 parmakla tıklayarak (veya `Control+Tık`) Hızlı Menü'yü açabilirsiniz; odak değiştiren ilk sol tık yanlışlıkla "Sev" tetiklemez.
- **Menü çubuğu simgesi:** Üst menü çubuğunda pati/kedi simgesi ile tek tıkla gizle/göster.
- **Şeffaf gölgesiz pencere:** Core Image siyah anahtarlama (`CIColorCubeWithColorSpace`) ile gri kenar ve iz bırakmaz.
- **Veri ve başlangıç:** Ayarlar `~/Library/Application Support/Komur` altında saklanır; "Oturum Açılınca Başlat" `~/Library/LaunchAgents/com.sushikiddo.komur.plist` kullanır.

---

## 🪟 Windows Sürümü (Windows 10/11 x64)

### Kurulum
1. `Komur-2.3.0-Windows-x64.exe` dosyasını indirin ve doğrudan çalıştırın (kurulum veya Python gerekmez).
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
