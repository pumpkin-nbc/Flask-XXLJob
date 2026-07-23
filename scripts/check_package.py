"""
构建产物敏感信息检查脚本。

Built-artifact sensitive-content check script.

检查 ``dist/`` 中的 wheel 与 sdist 是否意外包含敏感文件或内容。

Checks whether the wheel and sdist under ``dist/`` accidentally include
sensitive files or content.
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# 不允许出现在产物中的路径片段 / Path fragments not allowed in artifacts.
FORBIDDEN_PATH_FRAGMENTS = [
    ".venv",
    ".idea",
    ".git/",
    "__pycache__",
    "ai.md",
]

EXPECTED_REPOSITORY = "https://github.com/pumpkin-nbc/Flask-XXLJob"
EXPECTED_DOCUMENTATION = f"{EXPECTED_REPOSITORY}/tree/master/docs"
EXPECTED_CHANGELOG = f"{EXPECTED_REPOSITORY}/blob/master/CHANGELOG.md"
EXPECTED_METADATA_LINES = [
    "Name: flask-xxljob",
    "Author: Pumpkin",
    "License-Expression: Apache-2.0",
    f"Project-URL: Homepage, {EXPECTED_REPOSITORY}",
    f"Project-URL: Documentation, {EXPECTED_DOCUMENTATION}",
    f"Project-URL: Source, {EXPECTED_REPOSITORY}",
    f"Project-URL: Changelog, {EXPECTED_CHANGELOG}",
]


def _check_forbidden_paths(names: Sequence[str], errors: List[str]) -> None:
    for name in names:
        for fragment in FORBIDDEN_PATH_FRAGMENTS:
            if fragment in name:
                errors.append(f"Forbidden path in artifact: {name}")


def _find_suffix(names: Sequence[str], suffix: str) -> List[str]:
    normalized_suffix = suffix.replace("\\", "/")
    return [name for name in names if name.replace("\\", "/").endswith(normalized_suffix)]


def _check_wheel(path: Path, errors: List[str]) -> int:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        _check_forbidden_paths(names, errors)

        metadata_files = _find_suffix(names, ".dist-info/METADATA")
        if len(metadata_files) != 1:
            errors.append(f"{path.name}: expected exactly one METADATA file")
        else:
            metadata = archive.read(metadata_files[0]).decode("utf-8")
            for line in EXPECTED_METADATA_LINES:
                if line not in metadata:
                    errors.append(f"{path.name}: METADATA is missing {line!r}")
            if "github.com/example/" in metadata:
                errors.append(f"{path.name}: METADATA contains a placeholder project URL")
            if "License :: OSI Approved" in metadata:
                errors.append(f"{path.name}: METADATA contains a deprecated license classifier")

        license_files = _find_suffix(names, ".dist-info/licenses/LICENSE")
        notice_files = _find_suffix(names, ".dist-info/licenses/NOTICE")
        if len(license_files) != 1:
            errors.append(f"{path.name}: expected LICENSE in wheel license directory")
        elif "Apache License" not in archive.read(license_files[0]).decode("utf-8"):
            errors.append(f"{path.name}: wheel LICENSE is not Apache-2.0")
        if len(notice_files) != 1:
            errors.append(f"{path.name}: expected NOTICE in wheel license directory")
        elif "Copyright 2026 Pumpkin" not in archive.read(notice_files[0]).decode("utf-8"):
            errors.append(f"{path.name}: wheel NOTICE has incorrect attribution")
        return len(names)


def _check_sdist(path: Path, errors: List[str]) -> int:
    with tarfile.open(path) as archive:
        names = archive.getnames()
        _check_forbidden_paths(names, errors)

        required_suffixes = ["/LICENSE", "/NOTICE", "/pyproject.toml"]
        for suffix in required_suffixes:
            if len(_find_suffix(names, suffix)) != 1:
                errors.append(f"{path.name}: expected exactly one {suffix[1:]} file")

        license_files = _find_suffix(names, "/LICENSE")
        notice_files = _find_suffix(names, "/NOTICE")
        if license_files:
            member = archive.extractfile(license_files[0])
            content = member.read().decode("utf-8") if member is not None else ""
            if "Apache License" not in content:
                errors.append(f"{path.name}: sdist LICENSE is not Apache-2.0")
        if notice_files:
            member = archive.extractfile(notice_files[0])
            content = member.read().decode("utf-8") if member is not None else ""
            if "Copyright 2026 Pumpkin" not in content:
                errors.append(f"{path.name}: sdist NOTICE has incorrect attribution")
        return len(names)


def main() -> int:
    if not DIST.exists():
        print("No dist/ directory found. Build the package first.")
        return 1

    wheels = list(DIST.glob("*.whl"))
    sdists = list(DIST.glob("*.tar.gz"))
    if not wheels or not sdists:
        print("No build artifacts found in dist/.")
        return 1

    errors: List[str] = []
    entry_count = 0
    for wheel in wheels:
        entry_count += _check_wheel(wheel, errors)
    for sdist in sdists:
        entry_count += _check_sdist(sdist, errors)

    if errors:
        print("Package check FAILED:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1

    print(f"Package check passed ({entry_count} entries inspected).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
