"""Basit eklenti yükleyici: plugins/<ad>.py dosyalarındaki ACTIONS listesini okur.

Yerleşik klasör her zaman yüklenir; kullanıcı klasörü (settings.config_dir()/plugins)
yalnızca ayar dosyasında "user_plugins_enabled" true ise (rastgele kod çalıştırır!).
Hatalı eklenti loglanır ve atlanır; var olan ad ezilmez.
"""
import importlib.util
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).resolve().parent / "plugins"


def user_plugins_enabled() -> bool:
    # Settings.load() DEFAULTS dışındaki anahtarları attığı için ham dosyadan okunur.
    try:
        import settings
        data = json.loads(settings.config_path().read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("user_plugins_enabled", False) is True
    except Exception:  # noqa: BLE001
        return False


def user_dir() -> Path:
    import settings
    return settings.config_dir() / "plugins"


def _load_file(path: Path, tag: str) -> list:
    spec = importlib.util.spec_from_file_location(f"komur_plugin_{tag}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.ACTIONS)


def _load_dir(directory: Path, tag: str, taken: set, out: list):
    from pc_actions import ActionSpec
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            specs = _load_file(path, tag)
        except Exception as error:  # noqa: BLE001 - eklenti hatası uygulamayı düşürmez
            log.warning("Eklenti yüklenemedi %s: %s", path.name, error)
            continue
        for spec in specs:
            if not isinstance(spec, ActionSpec) or not callable(spec.func) or not spec.name:
                log.warning("Eklenti %s: geçersiz eylem atlandı", path.name)
            elif spec.name in taken:
                log.warning("Eklenti %s: '%s' zaten var, atlandı", path.name, spec.name)
            else:
                taken.add(spec.name)
                out.append(spec)


def load_plugins(existing_names, builtin_dir: Path | None = None, user_directory: Path | None = None,
                 allow_user: bool | None = None) -> list:
    """Kaydedilecek yeni ActionSpec listesini döndürür."""
    taken, out = set(existing_names), []
    _load_dir(builtin_dir or BUILTIN_DIR, "builtin", taken, out)
    if user_plugins_enabled() if allow_user is None else allow_user:
        try:
            _load_dir(user_directory or user_dir(), "user", taken, out)
        except Exception as error:  # noqa: BLE001
            log.warning("Kullanıcı eklentileri okunamadı: %s", error)
    return out
