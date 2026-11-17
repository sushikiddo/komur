# Kömür — Windows Masaüstü Kedisi ve AI Asistanı

**Onur Can Orhan · Sürüm 1.2.1 · Windows 10/11 x64**

Kömür, masaüstünde yaşayan siyah-beyaz bir kediyle Türkçe yardımcıyı bir araya getiren Python uygulamasıdır. Kediyle etkileşime girebilir, yazı veya isteğe bağlı sesle konuşabilir, not ve hatırlatıcı oluşturabilir ve desteklenen bilgisayar işlemlerini başlatabilirsiniz.

## İndir ve kur

- [Windows x64 kurulumu](https://github.com/sushikiddo/komur/releases/download/v1.2.1/Komur-Setup-1.2.1-x64.exe)
- [SHA-256 dosyası](https://github.com/sushikiddo/komur/releases/download/v1.2.1/Komur-Setup-1.2.1-x64.exe.sha256)
- [Özgün kaynak ZIP](https://github.com/sushikiddo/komur/releases/download/v1.2.1/Komur-Kaynak-v1.2.1.zip)
- [Portfolyo](https://onurcanorhan.pages.dev/index.html)

Kurulum dosyasının boyutu 142.143.321 bayt. Alıcıda Python gerekmez. Kurulum kullanıcı hesabına yapılır, Başlat menüsü kısayolları ve kaldırıcı ekler. Temel yazılı komutlar için AI modeli şart değildir. Yerel sohbet ve ses tanıma modelleri isteğe bağlıdır; ilk indirmeleri internet ve ilave disk alanı gerektirir.

Kurulum kod imzalı değildir; Windows yayımlayıcı/SmartScreen uyarısı gösterebilir. Hash eşleşmesi dosyanın aynı olduğunu gösterir; bağımsız güvenlik denetimi değildir.

~~~powershell
Get-FileHash ./Komur-Setup-1.2.1-x64.exe -Algorithm SHA256
~~~

Beklenen SHA-256:

~~~text
79f51f25fe91d3d95a4e3dc362e717ffccd967b77dc280dbb4493c88a653618f
~~~

## 1.2'de yenilikler

- **Sakin hareket:** Kedi bir yuvada dinlenir, ekranı dolaşmaz; hareket seviyesi Ayarlar'dan seçilir.
- **Ekranı anlama:** Video (mısırla izler), müzik (dans), oyun, kodlama, yazı, okuma, toplantı, boşta ve uzakta durumlarına sakin tepkiler. Başlıklar kaydedilmez, ağa gitmez.
- **AI:** Akıcı (kelime kelime) yanıt, yerel modelde serbest cümleden komut seçimi, tutarlı kişilik, yerel alışkanlık hafızası. Varsayılan Claude modeli claude-sonnet-5-5.
- **Yeni:** Pomodoro/odak modu, isteğe bağlı "Hey Kömür" (varsayılan kapalı), aksesuarlar, gece/akşam tonu, eklentiler (ör. "zar at").
- **Güncellemeler:** Günde en fazla bir kez bu deponun son sürümü denetlenir; indirme ve kurulum yalnız onayla, SHA-256 doğrulamalı.

## Ne işe yarar?

| Özellik | Davranış ve sınırlar |
| --- | --- |
| Masaüstü kedisi | Animasyon, hareket, ihtiyaçlar, sesler ve etkileşimler. |
| Küçük sohbet | Çift tıklayıp yazın, Enter ile gönderin. Geçmiş düğmesi büyük pencereyi açar. |
| Yerel AI | Ollama ile bilgisayarda çalışan model; harici AI API anahtarı gerekmez. |
| Bulut AI | İsteğe bağlı OpenAI ve Anthropic/Claude; ayrı erişim ve ücret koşulları olabilir. |
| Ses | Yerel faster-whisper tanıma ve Windows Türkçe konuşma sesi. Mikrofon elle başlatılır. |
| Hafıza | SQLite ile yerel geçmiş, notlar ve hatırlatıcılar. Uygulama kapalıyken bildirim vermez. |
| Ekran yardımı | Seçili pencerenin metni ve erişilebilir kontrolleri; her arayüz desteklenmez. |
| PC işlemleri | Desteklenen uygulamalar, ses ayarı ve ayrıca onay gerektiren işlemler. |
| Oyun ve medya | Steam/Riot başlatma yolları, desteklenen medya oturumlarına tepkiler. Giriş ve indirme engellerini aşmaz. |

### Örnek kullanım

1. Kediye çift tıklayın veya sağ tık → **Kömür ile konuş** seçin.
2. “Not defterini aç”, “sesi yüzde 30 yap”, “5 dakika sonra mola hatırlat” yazın.
3. “Bunu hatırla: yeşili seviyorum” ile açıkça not kaydedin.
4. “Uyu”, “uyan”, “yerde yuvarlan” ve “dans et” komutlarını deneyin.
5. Ses için **Konuş** ile başlatın, **Bitir** ile durdurun; tanınan metni gönderimden önce kontrol edin.

[Tam kullanıcı kılavuzu](KULLANIM-AI.md).

## Nasıl yazıldı?

Python modülleri, arayüzde Tkinter, çizimde Pillow, seste pygame/Windows ses olanakları ve kalıcı verilerde SQLite kullanılır. AI istekleri ayrı sağlayıcı katmanından geçer. EXE PyInstaller ile, kurulum Inno Setup ile üretilir.

| Dosyalar | Görev |
| --- | --- |
| cat.py | Ana uygulama ve bileşenlerin birleştirilmesi. |
| renderer.py, behavior.py, needs.py | Görünüm, hareket ve ihtiyaç davranışları. |
| bubble.py, chat_bubble.py, assistant_ui.py | Sohbet baloncuğu, geçmiş ve ayarlar. |
| ai.py, local_runtime.py, local_models.py | Sağlayıcılar, bağlam, araç istekleri ve model profilleri. |
| memory_store.py | SQLite geçmişi, notlar ve hatırlatıcılar. |
| voice.py, audio.py | Mikrofon, yerel tanıma ve sesli yanıt. |
| pc_actions.py, steam_actions.py, riot_actions.py | PC/oyun işlemleri ve sonuçları. |
| screen_assist.py, web_actions.py | Pencere yardımı ve web işlemleri. |
| activity_reactions.py | Müzik/video/oyun durumuna tepkiler. |
| bootstrap_setup.py, distribution/ | Model yardımcısı, paketleme, lisans ve kurulum araçları. |
| tests/ | Birim, entegrasyon ve ayrı çalıştırılan görsel inceleme senaryoları. |

Kod yapısında masaüstü karakterine sohbet, ses, hafıza, ekran yardımı ve dağıtım katmanlarının eklenmesi izlenebilir. Bu teknik açıklama eksiksiz tarihsel commit veya sohbet kaydı değildir.

**AI katkısı:** Proje AI araçlarından destek alınarak geliştirildi. Kaynak paketi tüm üretim oturumlarını ve model kullanım kayıtlarını içermiyor. Her dosyanın hangi modelle yazıldığı, toplam geliştirme süresi ve insan/AI katkı oranı doğrulanamıyor; oran veya model adı uydurulmadı.

## Token kullanımı ve maliyet

| Ölçüm | Doğrulanabilen durum |
| --- | --- |
| Toplam geliştirme tokenı | Doğrulanabilir toplam kayıt yok; bilinmiyor. |
| Sohbet başına gerçek token | İstek, model, geçmiş ve araç adımlarına göre değişir; merkezi kullanım raporu yok. |
| Kaynaktaki çıktı sınırları | Bazı isteklerde max_tokens=600, Anthropic araç döngüsünde max_tokens=4000. Bunlar tüketim değil ilgili isteğin çıktı sınırıdır. |
| Ollama yerel kullanım | Bulut AI API token ücreti doğurmaz; donanım ve elektrik tüketimi vardır. |
| Bulut sağlayıcıları | İlgili API hesabının modeli ve gerçek kullanımı üzerinden ücretlenebilir. |

Gerçek ölçüm için her isteğin sağlayıcı/modeli, giriş, çıkış ve önbellek tokenları ile zamanı kaydedilmeli; yeniden denemeler ve araç adımları toplama katılmalıdır. Sağlayıcı kullanım alanları veya Ollama değerlendirme sayaçları esas alınmalıdır. Kelime/karakter sayısı kesin token diye sunulmamalıdır. Geçmiş geliştirme tüketimi yalnız kaynak kodundan hesaplanamaz.

## Sistem ve model gereksinimleri

Windows 10/11 64 bit. Paket kılavuzuna göre standart qwen2.5:7b profili yaklaşık 4,7 GB model indirir ve 16 GB RAM önerir. Hafif qwen3:4b profili yaklaşık 2,6 GB indirir ve 8 GB RAM için sunulur. Ses tanıma modeli ayrıca yaklaşık 486 MB. İndirme değerleri değişebilir. CPU ile çalışabilir; hız donanıma ve modelin bellekte olup olmamasına bağlıdır.

## Kaynaktan çalıştırma

Paket kılavuzu Python 3.13 ile doğrulama bildiriyor. Sanal ortam önerilir:

~~~powershell
py -3.13 -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install pygame Pillow numpy
# İsteğe bağlı sağlayıcı, ses ve geliştirme araçları:
python -m pip install anthropic pyinstaller pytest
python -m pip install -r requirements-voice.txt
python cat.py
~~~

Temel bağımlılıklar için tam kilit dosyası yoktur; bu adımlar her ortamda birebir derleme garantisi değildir. Ollama ve modeller ayrıca kurulur.

~~~powershell
python -m pytest tests
python -m PyInstaller --noconfirm Komur.spec
powershell -File distribution/build_distribution.ps1
~~~

Son betik Inno Setup 6 derleyicisi ve üretilmiş ana EXE gerektirir; lisans toplama ve kurulum/kaldırma denemesi yapar. Çalıştırmadan önce inceleyin.

## Doğrulama ve sınırlar

1.2.1 için 390 otomatik test geçti (1 atlandı); derlenmiş EXE duman testi ile kurulum/kaldırma denemesi geçti. Bunlar tüm özelliklerin her bilgisayarda çalıştığının kanıtı değildir. Gerçek video oynatırken mısır tepkisi ve gerçek mikrofonla "Hey Kömür" bu yayın hazırlığında elle denenmedi.

Temiz bir alıcı bilgisayarda tüm kurulum ve özellikler bu yayın hazırlığında uçtan uca denenmedi. İstemciyi açmak oyuna giriş veya indirmenin tamamlandığı anlamına gelmez. AI yanlış yanıt verebilir; ekran denetimleri tüm uygulamalarda bulunmaz.

## Veriler ve lisans

Geçmiş/notlar yerelde %LOCALAPPDATA%/Komur/memory.sqlite3 içinde tutulur. Geçmiş kaydı kapatılabilir ve kayıtlar uygulamadan silinebilir. Bulut sağlayıcısı seçilirse etkin bağlam bu sağlayıcıya gidebilir. Yerel moddaki web araması da arama sözcüklerini dış hizmete gönderir. Kaldırma hafızayı veya paylaşılan Ollama modellerini otomatik silmez.

Kaynak paketi kişisel sohbet, ayar, API anahtarı ve indirilmiş modelleri içermiyor. Yayın hazırlığında yaygın API anahtarı biçimleri için statik kontrol yapıldı; bu kapsamlı güvenlik denetimi değildir.

[Üçüncü taraf bildirimleri](distribution/THIRD-PARTY-NOTICES.txt). Model ve bağımlılık lisansları ayrıca geçerlidir. Pakette açık ana proje lisansı yok; görünür kaynak sınırsız yeniden kullanım izni demek değildir.
