import json
from pathlib import Path

import pytest

from bootstrap_setup import (meets_ram_recommendation, recommended_model_for_ram,
                             save_local_model_choice, stage_files, validate_manifest)


def test_manifest_rejects_paths_outside_roots():
    with pytest.raises(ValueError):
        validate_manifest([{"source": "../secret", "target": "app.exe"}])
    with pytest.raises(ValueError):
        validate_manifest([{"source": "app.exe", "target": "../../outside.exe"}])


def test_manifest_rejects_duplicate_targets_case_insensitively():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_manifest([{"source": "a", "target": "App.exe"},
                           {"source": "b", "target": "app.EXE"}])


def test_stages_declared_files_into_fresh_install_directory(tmp_path):
    source = tmp_path / "bundle"
    install = tmp_path / "LOCALAPPDATA" / "Programs" / "Komur"
    (source / "assets").mkdir(parents=True)
    (source / "Komur.exe").write_bytes(b"app")
    (source / "assets" / "cat.dat").write_bytes(b"asset")

    copied = stage_files(source, install, [
        {"source": "Komur.exe", "target": "Komur.exe"},
        {"source": "assets/cat.dat", "target": "assets/cat.dat"},
    ])

    assert (install / "Komur.exe").read_bytes() == b"app"
    assert (install / "assets" / "cat.dat").read_bytes() == b"asset"
    assert set(copied) == {install / "Komur.exe", install / "assets" / "cat.dat"}


def test_staging_refuses_existing_files_and_leaves_them_unchanged(tmp_path):
    source, install = tmp_path / "bundle", tmp_path / "install"
    source.mkdir()
    install.mkdir()
    (source / "Komur.exe").write_bytes(b"new app")
    existing = install / "Komur.exe"
    existing.write_bytes(b"user file")

    with pytest.raises(FileExistsError):
        stage_files(source, install, [{"source": "Komur.exe", "target": "Komur.exe"}])
    assert existing.read_bytes() == b"user file"


def test_staging_rejects_symlink_escape(tmp_path):
    source, install, outside = tmp_path / "bundle", tmp_path / "install", tmp_path / "outside"
    source.mkdir()
    install.mkdir()
    outside.mkdir()
    (source / "app.exe").write_bytes(b"app")
    try:
        (install / "escape").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Windows symlink creation unavailable: {exc}")

    with pytest.raises(ValueError, match="escaped"):
        stage_files(source, install, [{"source": "app.exe", "target": "escape/app.exe"}])


def test_inno_uninstall_does_not_delete_user_data_or_shared_models():
    installer = Path(__file__).parents[1] / "distribution" / "Komur.iss"
    source = installer.read_text(encoding="utf-8")
    assert "[UninstallDelete]" not in source
    assert "%LOCALAPPDATA%\\Komur" not in source
    assert "{userappdata}" not in source


def test_inno_uninstall_only_removes_its_exact_autostart_command():
    installer = Path(__file__).parents[1] / "distribution" / "Komur.iss"
    source = installer.read_text(encoding="utf-8")
    assert "InstalledCommand := '\"' + ExpandConstant('{app}\\Komur.exe') + '\"';" in source
    assert "if CompareText(RunValue, InstalledCommand) = 0 then" in source


def test_model_recommendations_cover_8gb_reports_and_low_ram_warning():
    assert recommended_model_for_ram(7.8) == "qwen3:4b"
    assert recommended_model_for_ram(12.0) == "qwen2.5:7b"
    assert meets_ram_recommendation(7.8, 8)
    assert not meets_ram_recommendation(4.0, 8)


def test_saving_model_choice_preserves_existing_user_settings(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"ai_api_key":"keep-this","name":"Misket","ai_backend":"offline"}', encoding="utf-8")
    save_local_model_choice("qwen3:4b", settings)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data == {"ai_api_key": "keep-this", "name": "Misket",
                    "ai_backend": "local", "ai_local_model": "qwen3:4b"}


def test_invalid_settings_are_left_untouched_when_saving_model_choice(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("broken-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="left unchanged"):
        save_local_model_choice("qwen3:4b", settings)
    assert settings.read_text(encoding="utf-8") == "broken-json"
