"""Narrow Riot localhost launch bridge. Never exposes its ephemeral credential."""
import base64
import http.client
import json
import os
from pathlib import Path
import ssl
import subprocess


VALORANT_ENDPOINT = '/product-launcher/v1/products/valorant/patchlines/live'


def verify_listener(pid, port, executable):
    # Only validated integers enter this fixed read-only command. No credential does.
    script = (
        f"$p = Get-Process -Id {int(pid)} -ErrorAction Stop; "
        f"$c = Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction Stop | "
        f"Where-Object {{ $_.LocalAddress -eq '127.0.0.1' -and $_.OwningProcess -eq {int(pid)} }}; "
        "if ($c) { @{ path=$p.Path; valid=$true } | ConvertTo-Json -Compress }"
    )
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=8,
                            creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode or not result.stdout.strip():
        return False
    data = json.loads(result.stdout)
    return bool(data.get('valid') and os.path.normcase(os.path.realpath(data.get('path', ''))) ==
                os.path.normcase(os.path.realpath(executable)))


def launch_valorant(executable, lockfile=None, verifier=verify_listener, connection_factory=None):
    """Return accepted/unavailable/rejected. No arbitrary endpoint, redirects or credentials in errors."""
    submitted = False
    try:
        path = lockfile or Path(os.environ.get('LOCALAPPDATA', '')) / 'Riot Games/Riot Client/Config/lockfile'
        name, pid, port, password, scheme = Path(path).read_text(encoding='utf-8').strip().split(':')
        pid, port = int(pid), int(port)
        if name != 'Riot Client' or scheme != 'https' or pid <= 0 or not 1 <= port <= 65535 or not password:
            return 'unavailable'
        if not verifier(pid, port, executable):
            return 'unavailable'
        # Riot uses a self-signed localhost certificate. Owner/path validation above
        # is mandatory before sending the ephemeral token to this fixed loopback IP.
        factory = connection_factory or http.client.HTTPSConnection
        conn = factory('127.0.0.1', port, timeout=5, context=ssl._create_unverified_context())
        headers = {'Authorization': 'Basic ' + base64.b64encode(('riot:' + password).encode()).decode(),
                   'Content-Type': 'application/json'}
        try:
            conn.request('OPTIONS', VALORANT_ENDPOINT, headers=headers)
            response = conn.getresponse()
            allowed = response.getheader('Allow', '')
            response.read(4096)
            if response.status != 204 or 'POST' not in allowed.split(', '):
                return 'unavailable'
            submitted = True
            conn.request('POST', VALORANT_ENDPOINT, body='{}', headers=headers)
            response = conn.getresponse()
            response.read(4096)
            return 'accepted' if response.status in (200, 201, 202, 204) else 'rejected'
        finally:
            conn.close()
    except Exception:
        # Never log underlying requests, lockfile contents or auth exception detail.
        return 'pending' if submitted else 'unavailable'
