"""Resolve Steam games from local manifests and dispatch official Steam URIs."""
import os
import re
from pathlib import Path

ALIASES = {'cs': (730, 'Counter-Strike 2'), 'cs2': (730, 'Counter-Strike 2'),
           'counter strike 2': (730, 'Counter-Strike 2'), 'counter-strike 2': (730, 'Counter-Strike 2'),
           'csgo': (730, 'Counter-Strike 2'), 'cs go': (730, 'Counter-Strike 2'),
           'counter strike': (730, 'Counter-Strike 2'), 'counter-strike': (730, 'Counter-Strike 2'),
           'dota 2': (570, 'Dota 2'), 'dota2': (570, 'Dota 2'),
           'pubg': (578080, 'PUBG: BATTLEGROUNDS'), 'pubg battlegrounds': (578080, 'PUBG: BATTLEGROUNDS')}

PROCESS_NAMES = {730: 'cs2.exe', 570: 'dota2.exe', 578080: 'TslGame.exe'}


def steam_roots():
    roots = []
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                roots.append(Path(winreg.QueryValueEx(key, 'SteamPath')[0]))
        except OSError:
            pass
    for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES'):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]) / 'Steam')
    return roots


def library_roots(roots=None):
    libraries = list(steam_roots() if roots is None else roots)
    for root in list(libraries):
        try:
            data = (root / 'steamapps' / 'libraryfolders.vdf').read_text(encoding='utf-8')
            libraries.extend(Path(p.replace('\\\\', '\\')) for p in re.findall(r'"path"\s*"([^"]+)"', data))
        except OSError:
            pass
    return libraries


def installed_games(roots=None):
    libraries = library_roots(roots)
    games = {}
    for root in libraries:
        for manifest in (root / 'steamapps').glob('appmanifest_*.acf'):
            try:
                data = manifest.read_text(encoding='utf-8')
                appid = re.search(r'"appid"\s*"(\d+)"', data)
                name = re.search(r'"name"\s*"([^"]+)"', data)
                if appid and name:
                    games[int(appid.group(1))] = name.group(1)
            except OSError:
                continue
    return games


def download_state(appid, roots=None):
    """Return observed Steam update state; absence and ambiguous flags are unknown."""
    if not isinstance(appid, int) or appid <= 0:
        return 'unknown'
    for root in library_roots(roots):
        try:
            data = (root / 'steamapps' / f'appmanifest_{appid}.acf').read_text(encoding='utf-8')
            match = re.search(r'"StateFlags"\s*"(\d+)"', data, re.I)
            if match and int(match.group(1)) & 256:
                return 'updating'
        except OSError:
            continue
    return 'unknown'


def process_running(appid, runner):
    """Check a known game executable; unknown games cannot be verified this way."""
    name = PROCESS_NAMES.get(appid)
    if not name:
        return False
    try:
        result = runner(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV', '/NH'], 5)
        return result.returncode == 0 and f'"{name.lower()}"' in result.stdout.lower()
    except Exception:
        return False


def resolve_game(name, games=None):
    query = ' '.join(name.casefold().split())
    if not query:
        return None
    if query in ALIASES:
        return ALIASES[query]
    matches = [(appid, title) for appid, title in (installed_games() if games is None else games).items()
               if ' '.join(title.casefold().split()) == query]
    return matches[0] if len(matches) == 1 else None


def search_store(name):
    """Find only an exact title match in Steam's public search results."""
    import json
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    query = ' '.join(name.casefold().split())
    if not query or len(query) > 200:
        return None
    try:
        url = 'https://store.steampowered.com/api/storesearch/?' + urlencode({'term': name, 'l': 'english', 'cc': 'US'})
        with urlopen(Request(url, headers={'User-Agent': 'Komur/1.0'}), timeout=5) as response:
            data = json.loads(response.read(262144))
        matches = [(item['id'], item['name']) for item in data.get('items', [])
                   if isinstance(item.get('id'), int) and item['id'] > 0
                   and isinstance(item.get('name'), str)
                   and ' '.join(item['name'].casefold().split()) == query]
        return matches[0] if len(matches) == 1 else None
    except (OSError, ValueError, TypeError, KeyError):
        return None
