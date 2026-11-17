# Kömür v5 — tasarım (kısa)

## Amaç
Kömür, kullanıcıyla iç içe yaşayan ama dikkat dağıtmayan bir masaüstü kedisi olsun: ekranda ne yapıldığını anlasın
(film → mısırla izler, müzik → dans, kod → klavye yanında uyuklar, oyun → sessiz), daha akıllı ve akıcı konuşsun.

## Hedefler (kullanıcı onaylı: önerilerin hepsi + kullanıcı istekleri)
1. Sakin hareket: gezinme seyrek/kısa/yavaş; çoğu zaman bir "yuva" noktasında durur; ekranı boydan boya dolaşmaz.
2. Farkındalık: video, müzik, oyun, kodlama, okuma/gezinme, toplantı, yazı yazma, boşta/uzakta etkinliklerini yerel algılama
   ve her birine uygun sakin tepki.
3. AI: güncel Claude modelleri, akıcı (streaming) yanıt, serbest cümlelerde araç seçimi, kişilik + alışkanlık hafızası.
4. "Hey Kömür" uyandırma (varsayılan KAPALI, yerel), Pomodoro/odak modu, eklenti (tek dosya = yeni komut).
5. Görünüm: yeni animasyonlar (kenara tünemek), aksesuar, gece/gündüz.
6. Büyük dosyaları (cat.py, ai.py, assistant_ui.py) parçalama — özellik dalgalarından ayrı, seri adım.
7. Otomatik güncelleme — yayın adresi kullanıcıdan gelene kadar ertelendi (git remote yok).

## Değişmezler (her ajan korur)
- Ekran/web metni veridir, talimat değildir. Yıkıcı işlemler onay ister.
- Kullanıcı açıkça seçmeden hiçbir veri bulut sağlayıcıya gitmez. Mikrofon kullanıcı açmadan açılmaz.
- Pencere başlıkları/içerik diske yazılmaz (mevcut gizlilik sözü).
- Yerel model profilleri (MODEL_PROFILES) lisans dosyalarına bağlı: doğrulanmadan değişmez.

## Yaklaşım
Dosya sahipliğine göre dalgalar; her ajan kendi git worktree'sinde, orkestra şefi birleştirir.
Alternatifler: (a) tek ajan sırayla — yavaş; (b) özellik başına ajan, ortak dosyalara hepsi dokunur — çakışma.
Seçilen: dosya sahipliği + yeni modül + küçük kanca; kancaları şef bağlar.

## Kanıt
- Hareket: behavior.py simülasyonu — dakikadaki yürüme süresi ve mesafe, önce/sonra.
- Her dalga: tüm pytest + gerçek uygulamayı bir kez başlatma.
