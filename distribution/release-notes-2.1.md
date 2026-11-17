# Kömür 2.1 — Güncelleme notları

17 Kasım 2026 · Windows 10/11 x64

## 1.2.1’den bu yana

- Masaüstü fiziği: pencere üzerine tüneme, görev çubuğunda yürüme, kutu ve lazer etkileşimleri ile pati izleri.
- Yeni animasyonlar: yay tabanlı kuyruk/kulak hareketleri, bakış takibi, büyüme aşamaları, katmanlı kostümler ve retro piksel görünümü.
- Ses motoru: konuma göre stereo ses, sevme hızına bağlı mırıldanma, değişken miyav tonları ve lo-fi odak ambiyansı.
- Kişilik ve hafıza: kişilik şablonları, rüya kaydı, dostluk puanı ve seviye sistemi.
- Günlük yardımcılar: dosya sürükleme sepeti, yapılacak işler için balık görevleri, gizleme tuşu ve sağlık/su hatırlatmaları.
- Arayüz: yenilenen sağ tık hızlı işlem paneli ve sohbet baloncuğu düzenlemeleri.

## İndir ve kullan

- **Komur.exe**: doğrudan uygulama dosyası, 129.633.060 bayt (yaklaşık 129,6 MB). Eski Kömür çalışıyorsa kapatıp bu dosyayı çalıştırın. Bu yayında Inno Setup kurulum paketi yoktur; eski sürümlerin uygulama içi kurulum güncelleyicisi bu EXE'yi otomatik kurmaz.
- **Komur-Kaynak-v2.1.zip**: gönderilen özgün kaynak arşivi, değiştirilmeden yayımlandı. Arşiv içindeki eski README sürüm bilgileri yerine bu sürüm notlarını ve depodaki güncel README'yi esas alın.
- Her iki dosya için **SHA-256** doğrulama dosyası eklidir.

Yerel AI ve ses modelleri ayrıca kurulur. Çevrimiçi TTS ve bulut AI seçenekleri ağ erişimi gerektirebilir.

## Doğrulama

Yeni modüllere ait 71 mevcut otomatik test geçti; 114 Python dosyası sözdizimi kontrolünden geçti. EXE yeniden derlenmedi; gönderilen ikili dosyanın tüm özellikleri temiz bir bilgisayarda uçtan uca denenmedi.

```text
da46e24cab4a9d1476ccc60074b55f9ccce8007677b3009cab3324ec52b2d6fc  Komur.exe
125bd5800c1aed62a54aa65d1712c3de886fbe39a3e44a551884a7a35b83918e  Komur-Kaynak-v2.1.zip
```
