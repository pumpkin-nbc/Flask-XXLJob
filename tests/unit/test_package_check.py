"""Project-specific wheel and sdist artifact validation tests."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import check_package

DIST_INFO = "flask_xxljob-0.4.0.dist-info"
RECORD = f"{DIST_INFO}/RECORD"
METADATA = "\n".join(
    (
        "Metadata-Version: 2.4",
        "Name: flask-xxljob",
        "Version: 0.4.0",
        "Author: Pumpkin",
        "License-Expression: Apache-2.0",
        "Project-URL: Homepage, https://github.com/pumpkin-nbc/Flask-XXLJob",
        "Project-URL: Documentation, "
        "https://github.com/pumpkin-nbc/Flask-XXLJob/tree/master/docs",
        "Project-URL: Source, https://github.com/pumpkin-nbc/Flask-XXLJob",
        "Project-URL: Changelog, "
        "https://github.com/pumpkin-nbc/Flask-XXLJob/blob/master/CHANGELOG.md",
        "",
    )
)


def _hash(content: bytes, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm, content).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{algorithm}={encoded}"


def _wheel_files() -> dict:
    return {
        "flask_xxljob/__init__.py": b"from ._version import __version__\n",
        "flask_xxljob/_version.py": b'__version__ = "0.4.0"\n',
        "flask_xxljob/py.typed": b"",
        f"{DIST_INFO}/METADATA": METADATA.encode("utf-8"),
        f"{DIST_INFO}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
        f"{DIST_INFO}/licenses/LICENSE": b"Apache License\n",
        f"{DIST_INFO}/licenses/NOTICE": b"Copyright 2026 Pumpkin\n",
    }


def _record_rows(files: dict) -> list:
    rows = [[name, _hash(content), str(len(content))] for name, content in files.items()]
    rows.append([RECORD, "", ""])
    return rows


def _write_wheel(
    tmp_path: Path,
    *,
    files: dict = None,
    rows: list = None,
    directories: tuple = (),
    duplicate_file: str = "",
) -> Path:
    wheel_files = dict(files or _wheel_files())
    record_rows = list(rows or _record_rows(wheel_files))
    record_buffer = io.StringIO(newline="")
    csv.writer(record_buffer, lineterminator="\n").writerows(record_rows)
    path = tmp_path / check_package.EXPECTED_WHEEL
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in directories:
            archive.writestr(directory.rstrip("/") + "/", b"")
        for name, content in wheel_files.items():
            archive.writestr(name, content)
        if duplicate_file:
            with pytest.warns(UserWarning):
                archive.writestr(duplicate_file, wheel_files[duplicate_file])
        archive.writestr(RECORD, record_buffer.getvalue().encode("utf-8"))
    return path


def _wheel_errors(path: Path) -> list:
    errors = []
    check_package._check_wheel(path, errors)  # noqa: SLF001 - validator unit test
    return errors


def test_valid_wheel_record_and_directory_entry(tmp_path):
    path = _write_wheel(tmp_path, directories=("flask_xxljob/data",))

    assert _wheel_errors(path) == []


def test_record_self_entry_may_have_empty_hash_and_size(tmp_path):
    rows = _record_rows(_wheel_files())
    assert rows[-1] == [RECORD, "", ""]

    assert _wheel_errors(_write_wheel(tmp_path, rows=rows)) == []


@pytest.mark.parametrize("signature", ["RECORD.jws", "RECORD.p7s"])
def test_new_project_wheel_rejects_signature_files(tmp_path, signature):
    files = _wheel_files()
    files[f"{DIST_INFO}/{signature}"] = b"legacy-signature"

    errors = _wheel_errors(_write_wheel(tmp_path, files=files))

    assert any("forbidden Wheel signature" in error for error in errors)


def test_duplicate_zip_file_path_is_rejected(tmp_path):
    path = _write_wheel(
        tmp_path, duplicate_file="flask_xxljob/__init__.py"
    )

    assert any("duplicate wheel file path" in error for error in _wheel_errors(path))


def test_duplicate_record_path_is_rejected(tmp_path):
    rows = _record_rows(_wheel_files())
    rows.append(list(rows[0]))

    assert any(
        "duplicate RECORD path" in error
        for error in _wheel_errors(_write_wheel(tmp_path, rows=rows))
    )


def test_unrecorded_file_and_missing_file_record_are_rejected(tmp_path):
    files = _wheel_files()
    files["flask_xxljob/extra.py"] = b"extra\n"
    rows = _record_rows(_wheel_files())
    rows.insert(-1, ["flask_xxljob/missing.py", _hash(b"missing"), "7"])

    errors = _wheel_errors(_write_wheel(tmp_path, files=files, rows=rows))

    assert any("extra.py' is missing from RECORD" in error for error in errors)
    assert any("RECORD references missing file" in error for error in errors)


@pytest.mark.parametrize(
    ("hash_value", "expected"),
    [
        ("", "missing a RECORD hash"),
        ("sha256=***", "invalid URL-safe Base64"),
        ("md5=X03MO1qnZdYdgyfeuILPmQ", "forbidden hash algorithm"),
        ("sha1=qvTGHdzF6KLavt4PO0gs2a6pQ00", "forbidden hash algorithm"),
        ("unknown=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "unknown or unavailable"),
        ("shake_128=AAAAAAAAAAAAAAAAAAAAAA", "no fixed 256-bit digest"),
        ("sha256=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "does not match"),
    ],
)
def test_record_hash_failures_are_rejected(tmp_path, hash_value, expected):
    files = _wheel_files()
    rows = _record_rows(files)
    rows[0][1] = hash_value

    errors = _wheel_errors(_write_wheel(tmp_path, files=files, rows=rows))

    assert any(expected in error for error in errors)


def test_unavailable_hash_algorithm_is_rejected(tmp_path, monkeypatch):
    path = _write_wheel(tmp_path)
    original_new = check_package.hashlib.new

    def unavailable(name, *args, **kwargs):
        if name == "sha256":
            raise ValueError("provider unavailable")
        return original_new(name, *args, **kwargs)

    monkeypatch.setattr(check_package.hashlib, "new", unavailable)

    assert any("unknown or unavailable" in error for error in _wheel_errors(path))


@pytest.mark.parametrize(
    ("size_value", "expected"),
    [("", "missing a RECORD size"), ("invalid", "invalid RECORD size"), ("999", "does not match")],
)
def test_record_size_failures_are_rejected(tmp_path, size_value, expected):
    files = _wheel_files()
    rows = _record_rows(files)
    rows[0][2] = size_value

    errors = _wheel_errors(_write_wheel(tmp_path, files=files, rows=rows))

    assert any(expected in error for error in errors)


def _tar_files() -> dict:
    top = check_package.EXPECTED_TOP_LEVEL
    metadata = b"Metadata-Version: 2.4\nName: flask-xxljob\nVersion: 0.4.0\n"
    return {
        f"{top}/PKG-INFO": metadata,
        f"{top}/pyproject.toml": b"[project]\nname='flask-xxljob'\n",
        f"{top}/LICENSE": b"Apache License\n",
        f"{top}/NOTICE": b"Copyright 2026 Pumpkin\n",
        f"{top}/README.md": b"README\n",
        f"{top}/README.zh-CN.md": b"README\n",
        f"{top}/CHANGELOG.md": b"CHANGELOG\n",
        f"{top}/CHANGELOG.zh-CN.md": b"CHANGELOG\n",
        f"{top}/flask_xxljob/__init__.py": b"",
        f"{top}/flask_xxljob/_version.py": b'__version__ = "0.4.0"\n',
        f"{top}/flask_xxljob/py.typed": b"",
        f"{top}/docs/publishing.md": b"publish\n",
        f"{top}/docs/publishing.zh-CN.md": b"publish\n",
        f"{top}/scripts/check_package.py": b"check\n",
        f"{top}/scripts/smoke_installed_wheel.py": b"smoke\n",
        f"{top}/nested/PKG-INFO": b"nested metadata is allowed\n",
    }


def _write_sdist(tmp_path: Path, files: dict) -> Path:
    path = tmp_path / check_package.EXPECTED_SDIST
    with tarfile.open(path, "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return path


def test_sdist_uses_top_level_pkg_info_and_allows_nested_metadata(tmp_path):
    errors = []

    check_package._check_sdist(  # noqa: SLF001 - validator unit test
        _write_sdist(tmp_path, _tar_files()), errors
    )

    assert errors == []


def test_sdist_requires_authoritative_top_level_pkg_info(tmp_path):
    files = _tar_files()
    del files[f"{check_package.EXPECTED_TOP_LEVEL}/PKG-INFO"]
    errors = []

    check_package._check_sdist(  # noqa: SLF001 - validator unit test
        _write_sdist(tmp_path, files), errors
    )

    assert any("/PKG-INFO" in error for error in errors)


def test_forbidden_project_files_are_rejected(tmp_path):
    files = _wheel_files()
    files["flask_xxljob/__pycache__/module.pyc"] = b"cache"

    errors = _wheel_errors(_write_wheel(tmp_path, files=files))

    assert any(
        "Forbidden path" in error and "__pycache__" in error
        for error in errors
    )
