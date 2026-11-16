"""Best-effort, local activity reactions. No titles or metadata are retained."""
import os
import subprocess
import threading
import time

from context import get_foreground_info

# GSMTC reports a playback state, avoiding guesses from browser window titles.
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

def active_game(info):
    name = (info.get('process_name') or '').lower().replace('.exe', '')
    return bool(name and info.get('category') == 'gaming' and not any(x in name for x in _LAUNCHERS))

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

class ActivityReactions:
    def __init__(self, interval=8):
        self.current = 'none'
        self.interval = interval
        self._last = float('-inf')
        self._worker = None
        self._enabled = True

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

    def _sample(self):
        try:
            info = get_foreground_info()
            result = 'gaming' if active_game(info) else media_playback(info)
            if self._enabled:
                self.current = result
        except Exception:
            self.current = 'none'
