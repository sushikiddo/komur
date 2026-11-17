# GitHub'a surum yayinlar (gh CLI gerekir: gh auth login). Yayinlamak kullanici kararidir; elle calistirin.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$ver = (Select-String -Path (Join-Path $root 'version.py') -Pattern 'APP_VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$setup = Join-Path $root "dist-installer\Komur-Setup-$ver-x64.exe"
$sha = "$setup.sha256"
$notes = Join-Path $root "distribution\release-notes-$ver.md"
foreach ($f in @($setup, $sha, $notes)) { if (-not (Test-Path $f)) { throw "Eksik dosya: $f" } }
gh release create "v$ver" $setup $sha --repo sushikiddo/komur --title "Komur $ver" --notes-file $notes
