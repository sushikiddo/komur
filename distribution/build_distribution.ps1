$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dist = Join-Path $root 'dist'
$iscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'

if (-not (Test-Path (Join-Path $dist 'Komur.exe'))) {
    throw 'Build Komur.exe first with Komur.spec; no recipient data is included by this script.'
}
if (-not (Test-Path $iscc)) { throw "Inno Setup compiler not found: $iscc" }

Push-Location $root
try {
    python (Join-Path $PSScriptRoot 'write_licenses.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage third-party license files.' }
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name bootstrap_setup bootstrap_setup.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed while building the optional setup wizard.' }
} finally { Pop-Location }

& $iscc (Join-Path $PSScriptRoot 'Komur.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

$smokeRoot = Join-Path $env:TEMP ("KomurInstallerSmoke-" + [guid]::NewGuid().ToString('N'))
$installRoot = Join-Path $smokeRoot 'Installed'
$dataRoot = Join-Path $smokeRoot 'UserData'
$setup = Join-Path $root 'dist-installer\Komur-Setup-1.2.0-x64.exe'
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$sentinel = Join-Path $dataRoot 'settings.json'
[IO.File]::WriteAllText($sentinel, '{"keep":true}', [Text.Encoding]::UTF8)
try {
    $installed = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $installRoot + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($installed.ExitCode -ne 0) { throw "Smoke install failed with exit code $($installed.ExitCode)." }
    foreach ($file in @('Komur.exe', 'bootstrap_setup.exe', 'KULLANIM-AI.md')) {
        $installedFile = Join-Path $installRoot $file
        if (-not (Test-Path -LiteralPath $installedFile)) { throw "Installer did not install $file." }
        $sourceFile = if ($file -eq 'KULLANIM-AI.md') { Join-Path $root $file } else { Join-Path $dist $file }
        if ((Get-FileHash -LiteralPath $installedFile -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash) {
            throw "Installed file hash does not match the current build: $file"
        }
    }
    if (-not (Get-ChildItem -LiteralPath (Join-Path $installRoot 'licenses') -Recurse -File -ErrorAction SilentlyContinue)) {
        throw 'Installer did not install third-party license files.'
    }
    $uninstaller = Start-Process -FilePath (Join-Path $installRoot 'unins000.exe') -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -WindowStyle Hidden -Wait -PassThru
    if ($uninstaller.ExitCode -ne 0) { throw "Smoke uninstall failed with exit code $($uninstaller.ExitCode)." }
    if ((Get-Content -LiteralPath $sentinel -Raw) -notmatch 'keep') { throw 'Uninstall modified the independent user-data sentinel.' }
    if (Test-Path -LiteralPath $installRoot) { throw 'Uninstall did not remove its installation folder.' }
    Write-Host 'Fresh-directory install/uninstall smoke passed; independent user data was retained.'
} finally {
    $tempPrefix = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    $smokeFullPath = [IO.Path]::GetFullPath($smokeRoot)
    if (-not $smokeFullPath.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean smoke path outside TEMP: $smokeFullPath"
    }
    if (Test-Path -LiteralPath $smokeFullPath) { Remove-Item -LiteralPath $smokeFullPath -Recurse -Force }
}
Write-Host "Installer created under $(Join-Path $root 'dist-installer')."
