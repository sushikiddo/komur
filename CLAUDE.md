# Kömür — proje notları

Masaüstü kedisi. Python + tkinter, macOS (Apple Silicon, Homebrew Python 3.15 + Tk 9.1) ve Windows. Sürüm `version.py` içinde (2.4.0).

## Dallar
- `main`: yayın dalı. `mac-port`: macOS işi, `main`'e birleştirilir.
- `komur-v1.2`: eski 2.2.x hattı, artık geliştirilmiyor.

## Kurallar
- Yapay zekâ yok (Ollama/OpenAI/Claude, ses, mikrofon, ekran okuma kaldırıldı). Yalnız yazılı komut balonu (`commands.py` CommandEngine → `intents.py` + `pc_actions.py`) ve kısa hazır durum lafları. Geri ekleme.
- `behavior.py` ve `renderer.py` orijinal kalmalı (bytecode'dan geri çıkarıldı, golden görüntülerle doğrulandı).
- macOS platform katmanı `window_utils.py` (ctypes ile AppKit/ObjC). Tk penceresine dokunan her ObjC çağrısı `_is_tk_nswindow` korumasından geçmeli: kapatılmış pencereye `setStyleMask:` çökme yapıyordu.
- AppKit çağrıları yalnız Tk ana iş parçacığında.

## Komutlar
- Testler: `.venv/bin/python -m pytest -q -p no:cacheprovider tests`
- Mac paketi: `.venv/bin/pyinstaller --noconfirm Komur-mac.spec` → `dist/Kömür.app`
- Açılış testi: `"dist/Kömür.app/Contents/MacOS/Kömür" --smoke-test out.json`
- Log: `~/Library/Application Support/Komur/komur.log`

## Son durum (2026-11-28)
- 22 hata düzeltildi: komut ayrıştırma (kapat/yeniden başlat), pencere kapanırken çökme, ayar dosyasının atomik yazılması, ses süreçleri, aksesuar yuvaları, arkadaş kedi, Steam (Mac), Intel `objc_msgSend_stret`. Testler `tests/test_fixes_*.py`.
- Kullanıcının ekranda denemesi gereken: genel görünüm; Steam oyunu başlatma gerçek oyunla denenmedi.
