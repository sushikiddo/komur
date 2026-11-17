"""Best-effort, local activity reactions. No titles or metadata are retained."""
import json
import os
import queue
import subprocess
import threading
import time

from awareness import (ReactionPlanner, Stabilizer, active_game, browser_hint, classify_activity,
                       media_kind)
from context import _is_fullscreen, get_foreground_info, idle_seconds, mic_in_use_apps

# Eski tek seferlik GSMTC sorgusu (geriye uyum); yeni yol MediaSessionClient.
_SCRIPT = r'''$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1)
$op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
$t = $asTask.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]).Invoke($null, @($op)); $t.Wait()
$s = $t.Result.GetCurrentSession()
if ($null -eq $s) { 'none'; exit }
$p = $s.GetPlaybackInfo()
if ($p.PlaybackStatus.ToString() -ne 'Playing') { 'none'; exit }
$type = if ($null -ne $p.PlaybackType) { $p.PlaybackType.ToString() } else { '' }
if ($type -eq 'Video') { 'video' } elseif ($type -eq 'Music') { 'music' } else { 'playing|' + $s.SourceAppUserModelId }
'''

_LAUNCHERS = ('steam', 'epicgameslauncher', 'riotclient', 'leagueclient', 'battle.net', 'gamingservices', 'goggalaxy', 'eaapp', 'eadesktop', 'ubisoftconnect')

def media_playback(info=None):
    if os.name != 'nt':
        return 'none'
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', _SCRIPT],
                                capture_output=True, text=True, timeout=5,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        value = result.stdout.strip().lower()
        if result.returncode != 0:
            return 'none'
        if value in ('music', 'video'):
            return value
        if not value.startswith('playing|'):
            return 'none'
        source = value.partition('|')[2]
        if any(app in source for app in ('spotify', 'musicbee', 'foobar2000', 'aimp', 'itunes', 'applemusic', 'music.ui')):
            return 'music'
        if any(app in source for app in ('netflix', 'vlc', 'video.ui', 'kodi', 'disneyplus')):
            return 'video'
        info = info or {}
        # Only infer from a foreground hint if the playing session belongs to
        # the foreground process; an unrelated browser tab is not evidence.
        process = (info.get('process_name') or '').lower().removesuffix('.exe')
        hint = (info.get('hint') or '').lower()
        if process and process in source and info.get('category') == 'media':
            if hint in ('youtube', 'netflix', 'twitch', 'disney+', 'prime video'):
                return 'video'
            if hint in ('spotify', 'youtube music'):
                return 'music'
        return 'none' 
    except (OSError, subprocess.SubprocessError):
        return 'none'

# Tek uzun ömürlü PowerShell: stdin'e bir satır -> stdout'a tek satır JSON (çalan oturumlar).
# Başlıklar yalnız bellekte okunur; diske/loga yazılmaz.
_SESSION_SCRIPT = r'''$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1)
function Await($op, $rt) { $t = $asTask.MakeGenericMethod($rt).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
$mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
[Console]::Out.WriteLine('ready')
while ($null -ne ($line = [Console]::In.ReadLine())) {
  $out = @()
  try {
    foreach ($s in $mgr.GetSessions()) {
      $p = $s.GetPlaybackInfo()
      if ($p.PlaybackStatus.ToString() -ne 'Playing') { continue }
      $ty = if ($null -ne $p.PlaybackType) { $p.PlaybackType.ToString() } else { '' }
      $ti = ''; $ar = ''
      try { $m = Await ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties]); $ti = $m.Title; $ar = $m.Artist } catch {}
      $out += [pscustomobject]@{ app = $s.SourceAppUserModelId; type = $ty; title = $ti; artist = $ar }
    }
  } catch { $out = @() }
  [Console]::Out.WriteLine((ConvertTo-Json -InputObject @($out) -Compress))
}
'''


class MediaSessionClient:
    """Uzun ömürlü PowerShell sürecinden çalan medya oturumlarını ister. Ölürse sessizce yeniden başlar."""

    def __init__(self, popen=None, timeout=6.0, retry_after=30.0):
        self._popen = popen or self._default_popen
        self.timeout = timeout
        self.retry_after = retry_after
        self._proc = None
        self._lines = queue.Queue()
        self._retry_at = 0.0

    @staticmethod
    def _default_popen():
        return subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', _SESSION_SCRIPT],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding='utf-8', errors='replace',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def _reader(self, proc):
        try:
            for line in proc.stdout:
                self._lines.put(line.strip())
        except (OSError, ValueError):
            pass

    def _start(self):
        self._lines = queue.Queue()
        self._proc = self._popen()
        threading.Thread(target=self._reader, args=(self._proc,), daemon=True).start()

    def close(self):
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass

    def _fail(self):
        self.close()
        self._retry_at = time.monotonic() + self.retry_after
        return []

    def query(self):
        """Çalan oturumlar: [{'app','type','title','artist'}]; sorun olursa []."""
        if os.name != 'nt' and self._popen == self._default_popen:
            return []
        try:
            if self._proc is not None and self._proc.poll() is not None:
                self._proc = None
            if self._proc is None:
                if time.monotonic() < self._retry_at:
                    return []
                self._start()
                cold = True          # ilk sorgu PowerShell + WinRT yüklemesini de bekler
            else:
                cold = False
            self._proc.stdin.write('q\n')
            self._proc.stdin.flush()
            deadline = time.monotonic() + (max(self.timeout, 20.0) if cold else self.timeout)
            while True:
                try:
                    line = self._lines.get(timeout=max(0.05, deadline - time.monotonic()))
                except queue.Empty:
                    return self._fail()
                if line.startswith('['):
                    data = json.loads(line)
                    return [s for s in data if isinstance(s, dict)]
                if time.monotonic() >= deadline:
                    return self._fail()
        except Exception:
            return self._fail()


class ActivityReactions:
    """poll() -> 'none'|'music'|'video'|'gaming'|'coding'|'writing'|'reading'|'meeting'|'idle'|'away'.

    Değer histerezisle kararlıdır. Sınıf değişince ``take_reaction()`` bir kez
    {'class','state','message','still'} döner (aksi halde None).
    """

    def __init__(self, interval=5, media_client=None, stable_samples=2):
        self.current = 'none'
        self.interval = interval
        self._last = float('-inf')
        self._worker = None
        self._enabled = True
        self._media = media_client or MediaSessionClient()
        self._stab = Stabilizer(stable_samples)
        self._planner = ReactionPlanner()
        self._reaction = None
        self._browser_memory = None

    def poll(self, now=None, enabled=True):
        self._enabled = enabled
        if not enabled:
            self.current = 'none'
            return self.current
        now = time.monotonic() if now is None else now
        if now - self._last >= self.interval and (self._worker is None or not self._worker.is_alive()):
            self._last = now
            self._worker = threading.Thread(target=self._sample, daemon=True)
            self._worker.start()
        return self.current

    def take_reaction(self):
        reaction, self._reaction = self._reaction, None
        return reaction

    def close(self):
        self._media.close()

    def _sample(self):
        try:
            info = get_foreground_info()
            idle = idle_seconds()
            fullscreen = _is_fullscreen()
            media, playing = None, False
            if not active_game(info):      # oyunda medya sorgusuna gerek yok
                sessions = self._media.query()
                playing = bool(sessions)
                hint = browser_hint(info)
                if not sessions:
                    self._browser_memory = None
                elif hint:
                    self._browser_memory = hint
                media = media_kind(sessions, info, fullscreen, self._browser_memory)
            raw = classify_activity(info, media, idle, fullscreen, mic_in_use_apps(), playing)
            if not self._enabled:
                return
            old = self.current
            self.current = self._stab.feed(raw)
            if self.current != old:
                self._reaction = self._planner.plan(old, self.current, time.monotonic())
        except Exception:
            self.current = 'none'
