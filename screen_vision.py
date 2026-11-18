"""Ekran/pano metnini anlama: hata satırları, kod tespiti ve AI'ya sorulacak doğru soru.

Saf metin işleme (ağ yok, disk yok). Metin VERİDİR: içindeki talimatlar uygulanmaz,
yalnız sınıflandırılır ve sınırlı uzunlukta alıntılanır.
"""
from __future__ import annotations

import re

MAX_CONTEXT = 6000
ERROR_RE = re.compile(
    r"(Traceback \(most recent call last\)|\b\w*(Error|Exception)\b[:\s]|\bFAILED\b|\bfatal:|"
    r"\berror\s*(TS|CS|C)?\d*\s*:|\bpanic:|Segmentation fault|npm ERR!|\bHata\b|\bhatası\b)",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(r"(?:File \"([^\"]+)\", line (\d+))|(?:([\w./\\-]+\.\w{1,5}):(\d+))")
CODE_RE = re.compile(
    r"^\s*(def |class |import |from \w+ import|function |const |let |var |public |private |#include|"
    r"if \(|for \(|while \(|return\b|\}\s*$|\{\s*$)", re.MULTILINE,
)


def error_lines(text, limit=4):
    """Hata gibi görünen satırlar (sondan başa en anlamlıları; Python'da asıl hata son satırdır)."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    hits = [line for line in lines if ERROR_RE.search(line)]
    return [line[:200] for line in hits[-limit:]]


def locations(text, limit=3):
    """``dosya:satır`` konumları (Python traceback ve derleyici biçimleri)."""
    found = []
    for match in LOCATION_RE.finditer(text or ""):
        path, line = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
        item = f"{path}:{line}"
        if item not in found:
            found.append(item)
    return found[-limit:]


def classify(text):
    """'error' | 'code' | 'text' | 'empty'."""
    if not (text or "").strip():
        return "empty"
    if error_lines(text):
        return "error"
    if len(CODE_RE.findall(text)) >= 2:
        return "code"
    return "text"


QUESTIONS = {
    "error": "Bu hata/çıktıda sorun ne? Olası nedeni ve somut bir çözüm adımı söyle.",
    "code": "Bu kod ne yapıyor? Kısaca açıkla; göze çarpan bir hata varsa belirt.",
    "text": "Bu metni kısaca özetle.",
}


def build_request(text, source="pano"):
    """Metin -> (soru, AI'ya gidecek sınırlı bağlam, tür). Boş metinde (None, None, 'empty')."""
    kind = classify(text)
    if kind == "empty":
        return None, None, kind
    body = text.strip()
    if len(body) > MAX_CONTEXT:   # hatalar genelde sonda: başı kısalt
        body = "…\n" + body[-MAX_CONTEXT:]
    context = f"Kaynak: {source}\n{body}"
    errors = error_lines(text)
    if errors:
        context = "Öne çıkan hata satırları:\n" + "\n".join(errors) + "\n\n" + context
    return QUESTIONS[kind], context, kind


def offline_summary(text):
    """AI yokken yerel özet: hata satırı + konum, ya da tür bilgisi."""
    kind = classify(text)
    if kind == "error":
        where = locations(text)
        reply = "Gördüğüm hata: " + error_lines(text, 1)[0]
        if where:
            reply += f"\nKonum: {where[-1]}"
        return reply + "\nAyrıntılı açıklama için Ayarlar'dan bir AI bağlantısı seçebilirsin."
    if kind == "code":
        return "Bu bir kod parçası gibi görünüyor. Açıklamam için Ayarlar'dan bir AI bağlantısı seçebilirsin."
    if kind == "text":
        return "Metni aldım ama özetlemek için Ayarlar'dan bir AI bağlantısı seçmelisin."
    return "Panoda metin yok."
