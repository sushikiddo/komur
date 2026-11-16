"""Stage license texts for the frozen app's direct and transitive Python deps."""
from __future__ import annotations

import re
import shutil
import hashlib
import io
import json
import tarfile
from importlib import metadata
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "build" / "distribution-licenses"
MARKER = ".owned-by-komur-license-generator"
ROOT_PACKAGES = (
    "pygame", "anthropic", "Pillow", "numpy", "faster-whisper",
    "sounddevice", "av", "huggingface-hub",
)
LICENSE_NAME = re.compile(r"^(license|licence|copying|notice|copyright)(\.|$)", re.I)
SPDX_HASHES = {
    "MIT": "6d7c9e9d7d12c8d3753bdb24417b84819ba4d6c2f025c37948113d86dc81eef9",
    "Apache-2.0": "074e6e32c86a4c0ef8b3ed25b721ca23aca83df277cd88106ef7177c354615ff",
}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def license_packages() -> list[metadata.Distribution]:
    available = {normalized(d.metadata.get("Name", "")): d for d in metadata.distributions()}
    selected: dict[str, metadata.Distribution] = {}
    pending = list(ROOT_PACKAGES)
    while pending:
        name = pending.pop()
        key = normalized(name)
        if key in selected:
            continue
        dist = available.get(key)
        if dist is None:
            raise RuntimeError(f"Required packaged dependency metadata is missing: {name}")
        selected[key] = dist
        for requirement in dist.requires or ():
            parsed = Requirement(requirement)
            if parsed.marker is None or parsed.marker.evaluate(default_environment()):
                pending.append(parsed.name)
    return sorted(selected.values(), key=lambda d: normalized(d.metadata.get("Name", "")))


def safe_output_dir() -> None:
    root = (ROOT / "build").resolve()
    target = DEST.resolve()
    if not target.is_relative_to(root):
        raise RuntimeError("License staging path escaped the build directory")
    if DEST.exists():
        marker = DEST / MARKER
        if not marker.is_file() or marker.read_text(encoding="ascii") != "Komur license files only\n":
            raise RuntimeError(f"Refusing to replace an unowned license staging directory: {DEST}")
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST / MARKER).write_text("Komur license files only\n", encoding="ascii")


def fetch_sdist_licenses(dist: metadata.Distribution, folder: Path) -> int:
    """Fetch an sdist only when the installed wheel omitted its license text.

    PyPI's published SHA-256 is checked before reading any archive entries.
    Only small, named license files are copied; nothing is extracted to disk.
    """
    name = dist.metadata.get("Name", "")
    version = dist.version
    request = Request(f"https://pypi.org/pypi/{name}/{version}/json",
                      headers={"User-Agent": "Komur-License-Stager/1"})
    with urlopen(request, timeout=30) as response:
        if not response.geturl().startswith("https://pypi.org/"):
            raise RuntimeError(f"Unexpected PyPI metadata redirect for {name}")
        metadata_json = json.loads(response.read(8 * 1024 * 1024))
    sdist = next((entry for entry in metadata_json.get("urls", []) if entry.get("packagetype") == "sdist"), None)
    if not sdist:
        return 0
    url = sdist["url"]
    if not url.startswith("https://files.pythonhosted.org/"):
        raise RuntimeError(f"Unexpected source archive URL for {name}")
    with urlopen(Request(url, headers={"User-Agent": "Komur-License-Stager/1"}), timeout=60) as response:
        if not response.geturl().startswith("https://files.pythonhosted.org/"):
            raise RuntimeError(f"Unexpected source archive redirect for {name}")
        archive_bytes = response.read(200 * 1024 * 1024 + 1)
    if len(archive_bytes) > 200 * 1024 * 1024:
        raise RuntimeError(f"Source archive too large to inspect: {name}")
    expected_hash = sdist.get("digests", {}).get("sha256", "")
    if not expected_hash or hashlib.sha256(archive_bytes).hexdigest() != expected_hash:
        raise RuntimeError(f"PyPI source archive hash check failed for {name}")
    copied = 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as archive:
        for member in archive.getmembers():
            member_path = PurePosixPath(member.name)
            leaf = member_path.name
            if not member.isfile() or not LICENSE_NAME.match(leaf) or member.size > 2 * 1024 * 1024:
                continue
            if member_path.is_absolute() or ".." in member_path.parts or len(member_path.parts) < 2:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            destination = folder / "source-dist" / Path(*member_path.parts[1:])
            if not destination.resolve().is_relative_to(folder.resolve()):
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(stream.read(2 * 1024 * 1024 + 1))
            copied += 1
    return copied


def fetch_spdx_texts(license_value: str, folder: Path) -> int:
    aliases = {"MIT License": "MIT", "Apache 2.0": "Apache-2.0", "Apache License 2.0": "Apache-2.0"}
    identifiers = []
    for token in re.split(r"\s+(?:OR|AND)\s+", license_value):
        token = aliases.get(token.strip(), token.strip())
        if token in SPDX_HASHES and token not in identifiers:
            identifiers.append(token)
    copied = 0
    for identifier in identifiers:
        url = f"https://raw.githubusercontent.com/spdx/license-list-data/v3.26.0/text/{identifier}.txt"
        with urlopen(Request(url, headers={"User-Agent": "Komur-License-Stager/1"}), timeout=30) as response:
            if not response.geturl().startswith("https://raw.githubusercontent.com/spdx/license-list-data/"):
                raise RuntimeError(f"Unexpected SPDX text redirect for {identifier}")
            content = response.read(100 * 1024 + 1)
        if len(content) > 100 * 1024 or hashlib.sha256(content).hexdigest() != SPDX_HASHES[identifier]:
            raise RuntimeError(f"Pinned SPDX license text verification failed for {identifier}")
        (folder / f"LICENSE-{identifier}.txt").write_bytes(content)
        copied += 1
    return copied


def main() -> None:
    packages = license_packages()
    safe_output_dir()
    for dist in packages:
        name = dist.metadata.get("Name", "unknown")
        version = dist.version
        folder = DEST / f"{normalized(name)}-{version}"
        folder.mkdir()
        license_value = dist.metadata.get("License-Expression") or dist.metadata.get("License") or "See included license files"
        urls = [value for key, value in dist.metadata.items() if key == "Project-URL"]
        notice = [f"{name} {version}", f"License metadata: {license_value}"]
        if urls:
            notice.extend(urls)
        (folder / "PACKAGE-NOTICE.txt").write_text("\n".join(notice) + "\n", encoding="utf-8")
        copied = 0
        for entry in dist.files or ():
            rel = Path(str(entry))
            if not LICENSE_NAME.match(rel.name):
                continue
            source = Path(dist.locate_file(entry))
            try:
                resolved = source.resolve()
                dist_root = Path(dist.locate_file("")).resolve()
                if not resolved.is_relative_to(dist_root) or not resolved.is_file():
                    continue
                target = folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolved, target)
                copied += 1
            except OSError:
                continue
        if not copied:
            license_text = dist.metadata.get("License", "")
            if len(license_text.strip()) > 500:
                (folder / "LICENSE-METADATA.txt").write_text(license_text.strip() + "\n", encoding="utf-8")
                copied += 1
        if not copied:
            copied += fetch_sdist_licenses(dist, folder)
        if not copied:
            license_value = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
            copied += fetch_spdx_texts(license_value, folder)
        if not copied:
            (folder / "LICENSE-FILE-NOT-IN-WHEEL.txt").write_text(
                "The installed wheel metadata did not include a license text file. "
                "Use the project URL and license metadata in PACKAGE-NOTICE.txt to obtain the full text.\n",
                encoding="utf-8",
            )
    print(f"Staged license notices for {len(packages)} dependency packages in {DEST}")


if __name__ == "__main__":
    main()
