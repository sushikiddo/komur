# Kömür 1.2 — oyunlar, küçük sohbet, odak ve etkinlik tepkileri

## Kullanım

Kediye **çift tıklayın** veya sağ tık menüsünden **Kömür ile konuş** seçin. Kedinin yanında 292×224 piksellik mesaj baloncuğu açılır. Mesajınızı yazıp Enter'a basın. Sohbet açıkken kedi hareketini küçük bir alanla sınırlar; yazı alanı uzağa kaçmaz. **Dur** yeni işlem adımlarını ve sesli okumayı durdurur. Başlamış bir uygulama işlemini geri almaz; ağ yanıtının dönmesi zaman alabilir. Sohbeti kapatmak da durdurma isteği gönderir.

**Geçmiş** düğmesi büyük pencereyi açar. Konuşma geçmişi sekmesinde eski konuşmaları görebilir ve arayabilirsiniz. Ayarlar ve kurulum sekmesinde AI, ses, paylaşım, görünüm, güncelleme ve geçmiş seçenekleri vardır. Davranış kontrol paneli sağ tık menüsünden veya Ctrl+Shift+K ile açılır; Ctrl+Shift+H patron tuşudur (kediyi ve panelleri gizler, sesi kısar). Escape küçük sohbeti gizler.

## Sakin hareket

- Kedi bir yuvada dinlenir. Kediyi sürükleyip bıraktığınız yer yeni yuva olur.
- Ayarlar'daki **Hareket** kutusundan **Sakin**, **Normal** veya **Hareketli** seçebilirsiniz; varsayılan Sakin'dir. Sakin modda kedi yuvanın etrafında seyrek ve yavaş gezer; Normal ve Hareketli modlarda tüm ekranda gezinir.
- `beni takip et` komutu kediyi sizin peşinizden getirir. `dolaş` veya `gezintiye çık` komutu tüm ekranda gezinmesini sağlar.

## Sesli konuşma

- **Konuş** mikrofonu yalnız siz başlattığınızda açar. **Bitir** kaydı sonlandırır; tanınan metin önce yazı alanına gelir. Düzelttikten sonra Enter ile gönderin. Ayarlardan bu önizlemeyi kapatıp doğrudan göndermeyi seçebilirsiniz. Kayıt en çok 20 saniye sürer.
- Geçmiş > Ayarlar'dan mikrofon seçebilir ve sesli okuma hızını ayarlayabilirsiniz. **Ses, AI ve bilgisayar durumunu kontrol et**, mikrofon/model/ses durumu, RAM'e göre model önerisi ve boş disk alanını gösterir; model indirmez.
- Küçük sohbeti kayıt sırasında kapatırsanız kayıt iptal edilir ve çıkan metin komut olarak gönderilmez.
- Ses yalnız bilgisayarınızda işlenir; ses dosyası saklanmaz. Tanınan metin normal sohbet mesajıdır.
- **Ses** kutusu yanıtların Türkçe okunmasını açar/kapatır. Windows'ta Türkçe konuşma sesi gerekir; bu bilgisayarda Microsoft Tolga ile doğrulandı.
- Başka bilgisayarda ses tanıma modelini kurulum yardımcısından indirin. Türkçe ses yoksa Windows Ayarlar > Saat ve Dil > Dil ve Bölge > Türkçe > Dil seçenekleri > Konuşma bileşenini kurun. Bu Windows adımı sistem izni gerektirebilir.

## Hey Kömür

- Varsayılan olarak kapalıdır. Ayarlar'dan **"Hey Kömür" ile uyandır** kutusunu açtığınızda etkinleşir.
- Açıkken mikrofon sürekli yerelde dinler ve bu sürekli dinleme CPU kullanır. Ses tanıma modeli gerekir.
- Ses kaydedilmez. Yanlış tetiklemeler olabilir; uyandığında küçük sohbet açılır.

## Ekran yardımı

Önce yardım istediğiniz uygulamayı seçin, sonra Kömür'de **Ekranı oku** düğmesine basın. Yalnız son seçtiğiniz uygulamanın penceresi okunur; başka bir pencere üstünü örtse bile görüntüsü paylaşılmaz. Kömür pencerenin metnini ve erişilebilir denetimlerini yerel modele açıklatır. Algılanan şifre alanları ve yakalamaya karşı korunan pencereler engellenir.

Paylaşım 60 saniye geçerlidir. Bu süre içinde gördüğünüz bir düğmeye basmasını isteyebilirsiniz. Kömür her etkinleştirmeden önce pencereyi ve hedefi göstererek onay ister; eski/karışık hedeflerde işlem yapmaz. Yalnız erişilebilirlik arayüzü sunan düğme ve bağlantılar desteklenir; her oyun veya çizilmiş arayüzde çalışmaz, koordinat tahmini yapmaz.

Onay sırasında hedefin sınırları turuncu çerçeveyle gösterilir. İşlemden sonra erişilebilir denetimler yeniden kontrol edilir. Değişiklik görülmesi, istediğiniz işin kesin tamamlandığı anlamına gelmez; sonuç doğrulanamadığında Kömür bunu belirtir ve bağlı sonraki adımı çalıştırmaz.

Ekrandaki yazılar talimat sayılmaz. Ekran verisi kullanılan model isteklerinde uygulama açma, ağ araması ve kayıt gibi ek işlemler de otomatik çalışmaz; onay gerekir. Ham ekran görüntüsü ve OCR metni diske kaydedilmez. Açıklama normal sohbet geçmişinde kalabilir.

## Kalıcı hafıza ve hatırlatıcılar

- Sohbetler ve açıkça hatırlatılan notlar `%LOCALAPPDATA%\Komur\memory.sqlite3` içinde bu bilgisayarda tutulur.
- `Bunu hatırla: adım Deniz, yeşili seviyorum`, `Neler hatırlıyorsun?`, `Geçmişte proje ara` diyebilirsiniz.
- Uygulamayı kapatıp açınca son konuşmalar ve notlar yeniden kullanılır. Bütün geçmiş modele tek seferde gönderilmez.
- **Sohbet geçmişini bu bilgisayarda sakla** seçeneği yeni sohbetlerin kaydını kapatır. **Geçmişi temizle**, onayınızla konuşmaları, notları ve alışkanlık kayıtlarını siler. Mevcut kayıtları gizlice taşımaz veya yayımlamaz.
- `5 dakika sonra mola hatırlat` gibi hatırlatıcılar kapanıp açılınca korunur. Uygulama kapalıyken süre dolarsa sonraki açılışta bildirilir; bilgisayar kapalıyken bildirim üretilemez.
- Ayarlardaki **Bekleyen hatırlatıcıları iptal et**, onayınızla tüm bekleyen hatırlatıcıları kaldırır.
- `Her 30 dakikada bir mola hatırlat`, `hatırlatıcıları listele`, `hatırlatıcı 2 iptal et` komutları desteklenir. Süresi kaçan tekrarlar açılışta bir kez bildirilir; sonraki tekrar geleceğe alınır.
- **Hafızamı yönet** ekranından notları düzenleyebilir, tek tek unutabilir ve sohbet/not/hatırlatıcı veritabanını seçtiğiniz dosyaya yedekleyebilirsiniz. Yedek kişisel veri içerir; kurulum paketine eklenmez.

## Alışkanlıklar

- Ayarlar'daki **Alışkanlıklarımı öğren** kutusu açıksa Kömür, hangi uygulamayı veya komutu hangi saatte kullandığınızı sayar. Tutulan veri yalnız uygulama/komut adı ve saattir; bilgisayarda yerelde kalır.
- Aynı saatte en az üç farklı günde aynı işlem görülürse Kömür o saat için tek seferlik kısa bir öneri söyler (örneğin "Şimdi açayım mı?"). Öneri yalnız sorar; siz onaylamadan bir işlem yapmaz.
- Kutuyu kapatmak alışkanlık kayıtlarını hemen siler. **Geçmişi temizle** de alışkanlıkları siler.

## Ücretsiz yerel model

**Bilgisayarımda (ücretsiz)** seçeneği Ollama ile çalışır; API anahtarı veya Claude aboneliği gerekmez. Standart profil `qwen2.5:7b` (~4,7 GB, 16 GB RAM önerilir), hafif profil `qwen3:4b` (~2,6 GB, 8 GB RAM için) kullanır. Seçilen iki model de Apache-2.0 lisanslıdır. Ekran kartı yoksa CPU ile çalışabilir fakat daha yavaştır. Ses tanıma için ayrıca yaklaşık 486 MB model gerekir. İlk model yüklemesi ve CPU yanıtları zaman alabilir.

Bu mod sohbeti bulut AI'ya otomatik göndermez. İnternetten araştırma istendiğinde arama sözcükleri arama hizmetine gönderilir, genel web sayfaları indirilir ve yerel model bunları kaynak bağlantılarıyla özetler. Yerel model serbest cümlelerden de komut seçebilir; onay gerektiren işlemler yine onay ister. Yerel model hatalı bilgi veya yorum üretebilir; yapılan işlem doğrulanmadıysa tamamlandı denmez.

OpenAI ve Claude seçenekleri ayrıca ve kullanıcının seçimiyle kullanılabilir; bu ayrı hizmetler ücretli olabilir. Claude seçeneklerinde varsayılan model `claude-sonnet-5-5`tir (eski `claude-sonnet-4-5` ayarı otomatik yükseltilir). Yanıtlar kelime kelime akar. OpenAI anahtarı arayüzde yalnız oturum süresince tutulur, ayar dosyasına yazılmaz. Ekran ve notlar etkin bağlama katıldığında seçtiğiniz sağlayıcıya gidebilir; yerel kullanım için ücretsiz bilgisayar seçeneğinde kalın.

## Diğer işler

`LoL'ü aç`, `Steam'i açıp CS başlat`, `Steam'den Stardew Valley indir` diyebilirsiniz. LoL, Riot'un `league_of_legends` ürün başlatma parametresiyle; Steam oyunları sayısal oyun kimlikli resmi protokollerle açılır. CS/CS2/CS:GO adları güncel Counter-Strike 2'ye yönelir. Diğer oyunlar yerel Steam kitaplığındaki tam adla eşleşir; indirme için gerekirse Steam'in genel mağaza aramasında yalnız tek ve tam ad eşleşmesi kullanılır. Oyun adı belirsizse tahmin edilmez; satın alma yapılmaz.

Steam kurulum isteği bir kurulum/konum/sahiplik penceresi açabilir; gerekiyorsa Steam içindeki seçimi tamamlamanız gerekir. Kömür indirme/güncelleme etkinliğini gözlemediyse indirme başladı demez. Riot giriş, güncelleme ve oyun menüsü ayrı durumlardır; LoL istemcisini açmak maça girmek değildir.

`Hesap makinesini aç; 5 dakika sonra mola hatırlat` gibi açık adımları noktalı virgül, `sonra` veya `ardından` ile sıralayabilirsiniz. En fazla altı adım çalışır. Hata, sonucu belirsiz işlem veya onay noktasında sonraki adımlar durur. Onay reddedilirse kalan işler de çalışmaz.

## Pomodoro / odak

- Örnek komutlar: `pomodoro başlat` (25 dk odak, 5 dk mola), `25 dakika odaklan`, `odak modu 50/10` (50 dk odak, 10 dk mola), `pomodoro bitir`.
- Sağ tık menüsündeki **Pomodoro başlat / bitir** de aynı işi yapar. Odak süresi 1–180 dakika, mola 1–60 dakika arasında olabilir.
- Çalışma süresince kedi uyur ve dikkat dağıtmaz; mola başlayınca gerinir.

## Müzik, film ve oyun tepkileri

Kömür etkinliği bilgisayarda yerelde sınıflandırır ve kedinin tepkisini ona göre seçer. Pencere ve medya başlıkları yalnız bellekte, sınıflandırma sırasında okunur; diske kaydedilmez, loglanmaz ve ağa gönderilmez. Etkinlik paylaşımı açıksa yapay zekâya yalnız etkinlik kategorisi (başlık değil) gider.

Algılanan etkinlikler ve kedinin tepkisi:

- **Video** (YouTube, Netflix, VLC gibi): kedi izler ve "Mısırım hazır, izleyelim." der. Tarayıcıdaki YouTube/Netflix sekmesi oynuyorsa ya da tam ekran tarayıcıda video oynuyorsa video sayılır. Yalnız açık duran bir sekme tepki başlatmaz.
- **Müzik** (Spotify gibi): kedi kısa süre dans eder, sonra mırlar.
- **Oyun**: kedi odaklanır, arkadaş kediler durur, etkinlik yorumu yapılmaz.
- **Kodlama**: kod uygulaması ve son 30 saniyede klavye hareketi. Kedi köşede uyuklar.
- **Yazı** (Word, Not Defteri, Obsidian gibi): "Yazmana engel olmam."
- **Okuma** (PDF okuyucu veya tarayıcı): "Ne okuyorsun öyle?"
- **Toplantı**: mikrofonu tutan arama uygulaması (Discord, Zoom, Teams vb.) ve son 5 dakika içinde girdi. Kedi oturur ve konuşmaz.
- **Boşta**: 60 saniyedir girdi yok. Kedi kendini temizler.
- **Uzakta**: 5 dakikadır girdi yok. Kedi uyur; dönünce "Hoş geldin!" der.

Öncelik sırası: oyun, video, toplantı, uzakta/boşta, müzik, diğer çalışma türleri. Açık bir sesli kanal (Discord gibi) oynayan videoyu engellemez; birlikte izleme sayılır. Kendiliğinden konuşma en fazla 15 dakikada bir gelir ve aynı etkinlik için ayrıca 10–15 dakikalık bekleme vardır.

**Müzik ve videoya yerel tepki ver** ve **Oyunlarda sessiz ve sakin kal** ayrı ayarlardır. Yerel tepkiler AI gerektirmez; pencere başlığını modele paylaşma izninden ayrıdır.

Oyun odağı açıkken hareket yavaşlar, arkadaş kediler durur ve etkinlik yorumları bastırılır. İstediğiniz yanıtlar ve hatırlatıcılar devam eder. `Dans et` ve `benimle izle` komutlarıyla tepkileri elle de başlatabilirsiniz.

`Valorant'ı aç`, `YouTube'dan Gülpembe çal`, `not defterini aç`, `sesi yüzde 30 yap`, `saat kaç`, `ekran görüntüsü al`, `not al: süt al` gibi komutlar vardır. Valorant Riot'un yerel başlatma arayüzünü kullanır; giriş, güncelleme veya Vanguard engellerini aşmaz. YouTube gerçek video bağlantısını açar; tarayıcı otomatik oynatmayı engellerse Oynat'a basmanız gerekir.

Uygulama kapatma, bilgisayarı kapatma/yeniden başlatma, çöp kutusu boşaltma ve PowerShell komutları ayrıca onay gerektirir. Kediye `yerde yuvarlan`, `esne`, `canın sıkılsın`, `uyu`, `uyan` diyebilirsiniz. Adı Kömür ve görünümü siyah-beyaz smokindir.

## Görünüm

- Ayarlar'daki **Aksesuar** kutusundan papyon, atkı, şapka veya gözlük seçebilirsiniz; **Yok** aksesuarı kaldırır.
- **Saate göre gece/akşam tonu** açıksa kedinin görünümü saate göre gece ve akşam tonuna geçer.

## Eklentiler

- Uygulamanın `plugins` klasöründeki eklentiler açılışta yüklenir. Örnek eklenti `zar.py` ile **"zar at"** ve **"yazı tura"** komutlarını ekler.
- Kullanıcı eklentileri `%LOCALAPPDATA%\Komur\plugins` klasöründe bulunur ve yalnız `settings.json` dosyasında `"user_plugins_enabled": true` olduğunda yüklenir. Bu anahtarın arayüzde düğmesi yoktur.
- Eklentiler rastgele kod çalıştırır. Yalnız güvendiğiniz dosyaları bu klasöre koyun.

## Güncellemeler

- Kömür açıldıktan kısa süre sonra günde en fazla bir kez `github.com/sushikiddo/komur` deposunun son sürümüne bakar. Kişisel veri gönderilmez; yalnız sürüm bilgisi istenir.
- **Güncellemeleri denetle** düğmesiyle hemen bakabilirsiniz. Yeni sürüm varsa **Şimdi güncelle** ile indirip kurabilirsiniz. İndirme ve kurulum yalnız onayınızla başlar; indirilen dosya SHA-256 özetiyle doğrulanır.
- Kurulum dosyası henüz kod imzalama sertifikasıyla imzalanmadığı için Windows SmartScreen uyarısı görebilirsiniz.
- Otomatik denetimi Ayarlar'daki **Günde bir kez GitHub'da yeni sürüm denetle** kutusundan kapatabilirsiniz.
- Geliştirici için sürüm yayımlama adımları: `distribution/publish_release.ps1`.

## Başka bilgisayara kurma

Paylaşılacak dosya **Komur-Setup-2.2-x64.exe** kurulum programıdır. Windows 10/11 64 bit desteklenir; alıcıda Python gerekmez. Kurulum kullanıcı hesabına yapılır, Başlat menüsü kısayolları ve kaldırıcı ekler. Kurulum yardımcısı model indirmelerini boyutlarıyla gösterir; indirme yalnız kullanıcının seçimi/onayıyla başlar. AI veya ses kurulmadan temel yazılı komutlar kullanılabilir. Önceki sürümün üzerine kurulum yapılabilir; kişisel veriler ayrı klasörde korunur.

Kurulum paketi sizin sohbetlerinizi, notlarınızı, ayarlarınızı, API anahtarlarınızı veya indirilmiş modellerinizi içermez. Kaldırma kişisel hafızayı ve paylaşılan Ollama/model dosyalarını silmez; bunları ayrıca yönetebilirsiniz. Üçüncü taraf lisansları kurulumdaki `licenses` klasöründedir.

Kurulum dosyası henüz bir kod imzalama sertifikasıyla imzalanmadı; Windows yayımlayıcı/SmartScreen uyarısı gösterebilir. Dosyayı yalnız güvendiğiniz kaynaktan alın ve yanında verilen SHA-256 özetiyle doğrulayın.

## Kaynaktan derleme

Python 3.13 üzerinde doğrulandı. `requirements-voice.txt` ses bağımlılıklarını sabitler; temel uygulama için pygame, Pillow ve isteğe bağlı Anthropic SDK gerekir. `python -m PyInstaller --noconfirm Komur.spec` ana EXE'yi; `distribution/build_distribution.ps1` kurulum yardımcısını ve Inno Setup kurulum paketini üretir. Geliştirme testleri `python -m pytest tests` ile çalıştırılır.
