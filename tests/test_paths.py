from pathlib import Path

from app import paths


def test_uses_exe_dir_when_writable(tmp_path):
    exe_dir = tmp_path / "exe"
    fallback = tmp_path / "fallback"

    chosen = paths.choose_base_dir(exe_dir, fallback, writable_check=lambda p: True)

    assert chosen == exe_dir


def test_falls_back_when_exe_dir_is_not_writable(tmp_path):
    # Program Files にインストールされた場合のように、exeの隣に書き込めないケース
    exe_dir = tmp_path / "program_files"
    fallback = tmp_path / "appdata"

    chosen = paths.choose_base_dir(exe_dir, fallback, writable_check=lambda p: False)

    assert chosen == fallback


def test_is_writable_dir_true_for_normal_directory(tmp_path):
    assert paths.is_writable_dir(tmp_path) is True


def test_is_writable_dir_false_when_path_is_a_file(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_text("x", encoding="utf-8")

    assert paths.is_writable_dir(a_file / "sub") is False


def test_user_data_dir_prefers_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.get_user_data_dir() == Path(tmp_path) / "Bikkurapon"


def test_user_data_dir_falls_back_to_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert paths.get_user_data_dir() == Path(tmp_path) / "bikkurapon"
