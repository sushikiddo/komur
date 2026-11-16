# Kömür 1.1 — oyunlar, küçük sohbet ve etkinlik tepkileri

## Kullanım

Kediye **çift tıklayın** veya sağ tık menüsünden **Kömür ile konuş** seçin. Kedinin yanında 292×224 piksellik mesaj baloncuğu açılır. Mesajınızı yazıp Enter'a basın. Sohbet açıkken kedi hareketini küçük bir alanla sınırlar; yazı alanı uzağa kaçmaz. **Dur** yeni işlem adımlarını ve sesli okumayı durdurur. Başlamış bir uygulama işlemini geri almaz; ağ yanıtının dönmesi zaman alabilir. Sohbeti kapatmak da durdurma isteği gönderir.

**Geçmiş** düğmesi büyük pencereyi açar. Konuşma geçmişi sekmesinde eski konuşmaları görebilir ve arayabilirsiniz. Ayarlar ve kurulum sekmesinde AI, ses, paylaşım ve geçmiş seçenekleri vardır. Davranış kontrol paneli sağ tık menüsünden veya Ctrl+Shift+K ile açılır. Escape küçük sohbeti gizler.

## Sesli konuşma

- **Konuş** mikrofonu yalnız siz başlattığınızda açar. **Bitir** kaydı sonlandırır; tanınan metin önce yazı alanına gelir. Düzelttikten sonra Enter ile gönderin. Ayarlardan bu önizlemeyi kapatıp doğrudan göndermeyi seçebilirsiniz. Kayıt en çok 20 saniye sürer.
- Geçmiş > Ayarlar'dan mikrofon seçebilir ve sesli okuma hızını ayarlayabilirsiniz. **Ses, AI ve bilgisayar durumunu kontrol et**, mikrofon/model/ses durumu, RAM'e göre model önerisi ve boş disk alanını gösterir; model indirmez.
- Küçük sohbeti kayıt sırasında kapatırsanız kayıt iptal edilir ve çıkan metin komut olarak gönderilmez.
- Ses yalnız bilgisayarınızda işlenir; ses dosyası saklanmaz. Tanınan metin normal sohbet mesajıdır.
- **Ses** kutusu yanıtların Türkçe okunmasını açar/kapatır. Windows'ta Türkçe konuşma sesi gerekir; bu bilgisayarda Microsoft Tolga ile doğrulandı.
- Başka bilgisayarda ses tanıma modelini kurulum yardımcısından indirin. Türkçe ses yoksa Windows Ayarlar > Saat ve Dil > Dil ve Bölge > Türkçe > Dil seçenekleri > Konuşma bileşenini kurun. Bu Windows adımı sistem izni gerektirebilir.

## Ekran yardımı

Önce yardım istediğiniz uygulamayı seçin, sonra Kömür'de **Ekranı oku** düğmesine basın. Yalnız son seçtiğiniz uygulamanın penceresi okunur; başka bir pencere üstünü örtse bile görüntüsü paylaşılmaz. Kömür pencerenin metnini ve erişilebilir denetimlerini yerel modele açıklatır. Algılanan şifre alanları ve yakalamaya karşı korunan pencereler engellenir.

Paylaşım 60 saniye geçerlidir. Bu süre içinde gördüğünüz bir düğmeye basmasını isteyebilirsiniz. Kömür her etkinleştirmeden önce pencereyi ve hedefi göstererek onay ister; eski/karışık hedeflerde işlem yapmaz. Yalnız erişilebilirlik arayüzü sunan düğme ve bağlantılar desteklenir; her oyun veya çizilmiş arayüzde çalışmaz, koordinat tahmini yapmaz.

Onay sırasında hedefin sınırları turuncu çerçeveyle gösterilir. İşlemden sonra erişilebilir denetimler yeniden kontrol edilir. Değişiklik görülmesi, istediğiniz işin kesin tamamlandığı anlamına gelmez; sonuç doğrulanamadığında Kömür bunu belirtir ve bağlı sonraki adımı çalıştırmaz.

Ekrandaki yazılar talimat sayılmaz. Ekran verisi kullanılan model isteklerinde uygulama açma, ağ araması ve kayıt gibi ek işlemler de otomatik çalışmaz; onay gerekir. Ham ekran görüntüsü ve OCR metni diske kaydedilmez. Açıklama normal sohbet geçmişinde kalabilir.

## Kalıcı hafıza ve hatırlatıcılar

- Sohbetler ve açıkça hatırlatılan notlar `%LOCALAPPDATA%\Komur\memory.sqlite3` içinde bu bilgisayarda tutulur.
- `Bunu hatırla: adım Deniz, yeşili seviyorum`, `Neler hatırlıyorsun?`, `Geçmişte proje ara` diyebilirsiniz.
- Uygulamayı kapatıp açınca son konuşmalar ve notlar yeniden kullanılır. Bütün geçmiş modele tek seferde gönderilmez.
- **Sohbet geçmişini bu bilgisayarda sakla** seçeneği yeni sohbetlerin kaydını kapatır. **Geçmişi temizle**, onayınızla konuşmaları ve notları siler. Mevcut kayıtları gizlice taşımaz veya yayımlamaz.
- `5 dakika sonra mola hatırlat` gibi hatırlatıcılar artık kapanıp açılınca korunur. Uygulama kapalıyken süre dolarsa sonraki açılışta bildirilir; bilgisayar kapalıyken bildirim üretilemez.
- Ayarlardaki **Bekleyen hatırlatıcıları iptal et**, onayınızla tüm bekleyen hatırlatıcıları kaldırır.
- `Her 30 dakikada bir mola hatırlat`, `hatırlatıcıları listele`, `hatırlatıcı 2 iptal et` komutları desteklenir. Süresi kaçan tekrarlar açılışta bir kez bildirilir; sonraki tekrar geleceğe alınır.
- **Hafızamı yönet** ekranından notları düzenleyebilir, tek tek unutabilir ve sohbet/not/hatırlatıcı veritabanını seçtiğiniz dosyaya yedekleyebilirsiniz. Yedek kişisel veri içerir; kurulum paketine eklenmez.

## Ücretsiz yerel model

**Bilgisayarımda (ücretsiz)** seçeneği Ollama ile çalışır; API anahtarı veya Claude aboneliği gerekmez. Standart profil `qwen2.5:7b` (~4,7 GB, 16 GB RAM önerilir), hafif profil `qwen3:4b` (~2,6 GB, 8 GB RAM için) kullanır. Seçilen iki model de Apache-2.0 lisanslıdır. Ekran kartı yoksa CPU ile çalışabilir fakat daha yavaştır. Ses tanıma için ayrıca yaklaşık 486 MB model gerekir. İlk model yüklemesi ve CPU yanıtları zaman alabilir.

Bu mod sohbeti bulut AI'ya otomatik göndermez. İnternetten araştırma istendiğinde arama sözcükleri arama hizmetine gönderilir, genel web sayfaları indirilir ve yerel model bunları kaynak bağlantılarıyla özetler. Yerel model hatalı bilgi veya yorum üretebilir; yapılan işlem doğrulanmadıysa tamamlandı denmez.

OpenAI ve Claude seçenekleri ayrıca ve kullanıcının seçimiyle kullanılabilir; bu ayrı hizmetler ücretli olabilir. OpenAI anahtarı arayüzde yalnız oturum süresince tutulur, ayar dosyasına yazılmaz. Ekran ve notlar etkin bağlama katıldığında seçtiğiniz sağlayıcıya gidebilir; yerel kullanım için ücretsiz bilgisayar seçeneğinde kalın.

## Diğer işler

`LoL'ü aç`, `Steam'i açıp CS başlat`, `Steam'den Stardew Valley indir` diyebilirsiniz. LoL, Riot'un `league_of_legends` ürün başlatma parametresiyle; Steam oyunları sayısal oyun kimlikli resmi protokollerle açılır. CS/CS2/CS:GO adları güncel Counter-Strike 2'ye yönelir. Diğer oyunlar yerel Steam kitaplığındaki tam adla eşleşir; indirme için gerekirse Steam'in genel mağaza aramasında yalnız tek ve tam ad eşleşmesi kullanılır. Oyun adı belirsizse tahmin edilmez; satın alma yapılmaz.

Steam kurulum isteği bir kurulum/konum/sahiplik penceresi açabilir; gerekiyorsa Steam içindeki seçimi tamamlamanız gerekir. Kömür indirme/güncelleme etkinliğini gözlemediyse indirme başladı demez. Riot giriş, güncelleme ve oyun menüsü ayrı durumlardır; LoL istemcisini açmak maça girmek değildir.

`Hesap makinesini aç; 5 dakika sonra mola hatırlat` gibi açık adımları noktalı virgül, `sonra` veya `ardından` ile sıralayabilirsiniz. En fazla altı adım çalışır. Hata, sonucu belirsiz işlem veya onay noktasında sonraki adımlar durur. Onay reddedilirse kalan işler de çalışmaz.

## Müzik, film ve oyun tepkileri

Windows oynayan bir müzik oturumu bildirirse Kömür dans eder; oynayan video bildirirse patlamış mısırıyla izler. Oynatma türü bildirilmezse bilinen uygulama kimliği ve etkin pencere bilgisiyle yerel olarak sınıflandırılır; her tarayıcı/oynatıcı desteklenmeyebilir. Yalnız bir YouTube sekmesinin açık olması tepki başlatmaz. `Dans et` ve `benimle izle` komutlarıyla elle de başlatabilirsiniz.

Oyun odağı açıkken hareket yavaşlar, arkadaş kediler durur ve etkinlik yorumları bastırılır. İstediğiniz yanıtlar ve hatırlatıcılar devam eder. **Müzik ve videoya yerel tepki ver** ve **Oyunlarda sessiz ve sakin kal** ayrı ayarlardır. Yerel tepkiler AI gerektirmez; pencere başlığını modele paylaşma izninden ayrıdır.

`Valorant'ı aç`, `YouTube'dan Gülpembe çal`, `not defterini aç`, `sesi yüzde 30 yap`, `saat kaç`, `ekran görüntüsü al`, `not al: süt al` gibi komutlar vardır. Valorant Riot'un yerel başlatma arayüzünü kullanır; giriş, güncelleme veya Vanguard engellerini aşmaz. YouTube gerçek video bağlantısını açar; tarayıcı otomatik oynatmayı engellerse Oynat'a basmanız gerekir.

Uygulama kapatma, bilgisayarı kapatma/yeniden başlatma, çöp kutusu boşaltma ve PowerShell komutları ayrıca onay gerektirir. Kediye `yerde yuvarlan`, `esne`, `canın sıkılsın`, `uyu`, `uyan`, `beni takip et` diyebilirsiniz. Adı Kömür ve görünümü siyah-beyaz smokindir.

## Başka bilgisayara kurma

Paylaşılacak dosya **Komur-Setup-1.1.0-x64.exe** kurulum programıdır. Windows 10/11 64 bit desteklenir; alıcıda Python gerekmez. Kurulum kullanıcı hesabına yapılır, Başlat menüsü kısayolları ve kaldırıcı ekler. Kurulum yardımcısı model indirmelerini boyutlarıyla gösterir; indirme yalnız kullanıcının seçimi/onayıyla başlar. AI veya ses kurulmadan temel yazılı komutlar kullanılabilir. Önceki sürümün üzerine kurulum yapılabilir; kişisel veriler ayrı klasörde korunur.

Kurulum paketi sizin sohbetlerinizi, notlarınızı, ayarlarınızı, API anahtarlarınızı veya indirilmiş modellerinizi içermez. Kaldırma kişisel hafızayı ve paylaşılan Ollama/model dosyalarını silmez; bunları ayrıca yönetebilirsiniz. Üçüncü taraf lisansları kurulumdaki `licenses` klasöründedir.

Kurulum dosyası henüz bir kod imzalama sertifikasıyla imzalanmadı; Windows yayımlayıcı/SmartScreen uyarısı gösterebilir. Dosyayı yalnız güvendiğiniz kaynaktan alın ve yanında verilen SHA-256 özetiyle doğrulayın.

## Kaynaktan derleme

Python 3.13 üzerinde doğrulandı. `requirements-voice.txt` ses bağımlılıklarını sabitler; temel uygulama için pygame, Pillow ve isteğe bağlı Anthropic SDK gerekir. `python -m PyInstaller --noconfirm Komur.spec` ana EXE'yi; `distribution/build_distribution.ps1` kurulum yardımcısını ve Inno Setup kurulum paketini üretir. Geliştirme testleri `python -m pytest tests` ile çalıştırılır.
