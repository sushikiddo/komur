# Kömür 1.1.0 — geliştirme ve dağıtım doğrulaması

16 Kasım 2026.

- `python distribution/verify_release.py`: 200 test geçti, 1 test Windows sembolik bağ yetkisi olmadığı için atlandı. 46 GUI senaryosu ayrı süreçlerde çalıştı. Ayrıntılar: `release-verification-v4.json`.
- Oyun testleri gerçek oyun açmadan resmi Steam URI'lerini, LoL ürün parametresini, isim eşleşmesini, Steam indirme/güncelleme gözlemini ve onay sınırlarını sınadı. Kullanıcının Riot/Steam hesabına giriş yapılmadı; oyun indirilmedi. Bu nedenle gerçek LoL giriş/oyun menüsü ve Steam indirme kuyruğu uçtan uca doğrulanmış sayılmaz.
- OpenAI uyumlu yerel sağlayıcı, Claude API ve CLI yollarında adımlar hata, bekleyen sonuç ve onay sınırında duruyor. Onay sonrası kalan adımların bir kez çalışması, iptal ve ekran tıklamasının doğrulanmamış sonuç olarak kalması sınandı.
- Gerçek Ollama ile tek istekli Türkçe sohbet denemesi yapıldı; son denemede yaklaşık 1,05 saniyede yanıt geldi. Test eylem yürütücüsü gerçek işlemleri engelledi; hiçbir PC işlemi çalıştırılmadı. Bu ölçüm yüklü/sıcak modele aittir, başka bilgisayarlar için hız garantisi değildir. Sistem istemi ve konuşma örnekleri samimi dil için geliştirildi; modelin dil kalitesi kusursuz değildir.
- Gerçek Windows medya oturumu sorgusu başarıyla çalıştı; oynatma değiştikçe müzik ve boş oturum durumları gözlendi. Müzik/video tepkileri, oyun önceliği ve açık dans/izleme komutları ayrıca belirli girdilerle test edildi. Her oynatıcı medya türü bildirmez.
- Ses durumu gerçek bilgisayarda mikrofon, yerel tanıma modeli ve Türkçe ses için hazır döndü. Ortamdan ses kaydedilmedi. Mikrofon seçimi, ses hızı ve göndermeden önce metin önizlemesi testlerle kontrol edildi.
- Not düzenleme, gizli anahtar maskeleme, SQLite yedek, tekrar eden hatırlatıcıların kapanıp açılınca dönmesi ve tek hatırlatıcı iptali sınandı. Eski hafıza şeması yeni tekrar sütununa yükseltilir.
- 292×224 sohbet ve müzik/video/dinlenme görünümleri gerçek Tk bileşenleriyle incelendi. Görseller: `docs/previews/compact-chat-v4.png`, `docs/previews/activity-v4.png`.
- Paket, kullanıcı sohbetlerini/ayarlarını/anahtarlarını veya indirilen AI modellerini içermez. Kod imzası ve herkese açık yayın eklenmedi.
- PyInstaller EXE derlemesi tamamlandı; dosya ve ürün sürümü 1.1.0. Paketlenmiş EXE ve gerçek `%LOCALAPPDATA%\Programs\Komur\Komur.exe` kurulumu kendi testinden geçti: küçük sohbet, geçmiş, SQLite ve gerçek CPU ses tanıma kitaplığı açıldı.
- Inno Setup paketi temiz geçici klasöre kurulup kaldırıldı; kurulan dosyaların hash değerleri derlemeyle eşleşti. Gerçek kurulum güncellemesinde mevcut ayar/hafıza dosyalarının SHA-256 değerleri değişmedi. Kurulu EXE'nin hash değeri yeni derlemeyle aynı.

Kurulum ve paketlenmiş uygulama kontrollerinin çıktıları ayrıca `exe-smoke-v4.json`, `installed-smoke-v4.json` ve `release-manifest-v4.json` dosyalarında tutulur.
