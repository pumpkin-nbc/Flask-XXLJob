"""Validate the freshly built Flask-XXLJob 0.4.0 wheel and sdist."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import io
import re
import sys
import tarfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from email.message import Message
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIST = ROOT / "dist"
PROJECT_NAME = "flask-xxljob"
NORMALIZED_NAME = "flask_xxljob"
VERSION = "0.4.0"
EXPECTED_WHEEL = f"{NORMALIZED_NAME}-{VERSION}-py3-none-any.whl"
EXPECTED_SDIST = f"{NORMALIZED_NAME}-{VERSION}.tar.gz"
EXPECTED_TOP_LEVEL = f"{NORMALIZED_NAME}-{VERSION}"

FORBIDDEN_COMPONENTS = frozenset(
    {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "venv",
    }
)
FORBIDDEN_FILENAMES = frozenset({".coverage", "coverage.xml"})
SIGNATURE_FILENAMES = frozenset({"RECORD.jws", "RECORD.p7s"})

EXPECTED_REPOSITORY = "https://github.com/pumpkin-nbc/Flask-XXLJob"
EXPECTED_DOCUMENTATION = f"{EXPECTED_REPOSITORY}/tree/master/docs"
EXPECTED_CHANGELOG = f"{EXPECTED_REPOSITORY}/blob/master/CHANGELOG.md"
EXPECTED_METADATA_LINES = (
    "Name: flask-xxljob",
    "Author: Pumpkin",
    "License-Expression: Apache-2.0",
    f"Project-URL: Homepage, {EXPECTED_REPOSITORY}",
    f"Project-URL: Documentation, {EXPECTED_DOCUMENTATION}",
    f"Project-URL: Source, {EXPECTED_REPOSITORY}",
    f"Project-URL: Changelog, {EXPECTED_CHANGELOG}",
)


@dataclass(frozen=True)
class ArtifactInfo:
    """Core metadata and inspected file count for one artifact."""

    name: str = ""
    version: str = ""
    file_count: int = 0


def _canonicalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _normalized_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def _check_forbidden_paths(names: Sequence[str], errors: List[str]) -> None:
    for raw_name in names:
        normalized = _normalized_path(raw_name)
        parts = tuple(part.lower() for part in PurePosixPath(normalized).parts)
        filename = parts[-1] if parts else ""
        if any(part in FORBIDDEN_COMPONENTS for part in parts):
            errors.append(f"Forbidden path in artifact: {raw_name}")
        if filename in FORBIDDEN_FILENAMES:
            errors.append(f"Forbidden path in artifact: {raw_name}")


def _metadata(text: str, label: str, errors: List[str]) -> Message:
    try:
        return Parser().parsestr(text)
    except Exception as exc:  # pragma: no cover - email parser is defensive
        errors.append(f"{label}: metadata parsing failed ({type(exc).__name__})")
        return Message()


def _check_core_metadata(
    metadata: Message, label: str, errors: List[str]
) -> Tuple[str, str]:
    name = metadata.get("Name", "")
    version = metadata.get("Version", "")
    if _canonicalize_name(name) != _canonicalize_name(PROJECT_NAME):
        errors.append(f"{label}: expected Name {PROJECT_NAME!r}, got {name!r}")
    if version != VERSION:
        errors.append(f"{label}: expected Version {VERSION!r}, got {version!r}")
    return name, version


def _duplicate_names(names: Sequence[str]) -> List[str]:
    return sorted(name for name, count in Counter(names).items() if count > 1)


def _validate_record_hash(
    path: str,
    declared: str,
    content: bytes,
    label: str,
    errors: List[str],
) -> None:
    if "=" not in declared:
        errors.append(f"{label}: {path} has an invalid RECORD hash")
        return
    algorithm, encoded = declared.split("=", 1)
    normalized_algorithm = algorithm.lower().replace("-", "")
    if normalized_algorithm in {"md5", "sha1"}:
        errors.append(f"{label}: {path} uses forbidden hash algorithm {algorithm!r}")
        return
    try:
        digest = hashlib.new(algorithm)
    except (TypeError, ValueError):
        errors.append(f"{label}: {path} uses unknown or unavailable hash {algorithm!r}")
        return
    if not isinstance(digest.digest_size, int) or digest.digest_size < 32:
        errors.append(
            f"{label}: {path} hash {algorithm!r} has no fixed 256-bit digest"
        )
        return
    if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        errors.append(f"{label}: {path} has an invalid URL-safe Base64 digest")
        return
    padded = encoded + ("=" * ((4 - len(encoded) % 4) % 4))
    try:
        decoded = base64.b64decode(
            padded.encode("ascii"), altchars=b"-_", validate=True
        )
    except (UnicodeEncodeError, binascii.Error, ValueError):
        errors.append(f"{label}: {path} has an invalid URL-safe Base64 digest")
        return
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if canonical != encoded or len(decoded) != digest.digest_size:
        errors.append(f"{label}: {path} has an invalid URL-safe Base64 digest")
        return
    digest.update(content)
    actual = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")
    if actual != encoded:
        errors.append(f"{label}: {path} RECORD hash does not match its content")


def _validate_wheel_record(
    archive: zipfile.ZipFile,
    record_path: str,
    files: Dict[str, zipfile.ZipInfo],
    errors: List[str],
) -> None:
    label = Path(archive.filename or "wheel").name
    try:
        text = archive.read(files[record_path]).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as exc:
        errors.append(f"{label}: RECORD cannot be read ({type(exc).__name__})")
        return

    rows: Dict[str, Tuple[str, str]] = {}
    duplicate_rows: List[str] = []
    for row_number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if len(row) != 3:
            errors.append(f"{label}: RECORD row {row_number} must have three fields")
            continue
        path, declared_hash, declared_size = row
        if path in rows:
            duplicate_rows.append(path)
            continue
        rows[path] = (declared_hash, declared_size)
    for path in sorted(set(duplicate_rows)):
        errors.append(f"{label}: duplicate RECORD path {path!r}")

    if record_path not in rows:
        errors.append(f"{label}: RECORD must contain its own entry")

    for path in sorted(files):
        if path not in rows:
            errors.append(f"{label}: wheel file {path!r} is missing from RECORD")
            continue
        if path == record_path:
            continue
        declared_hash, declared_size = rows[path]
        if not declared_hash:
            errors.append(f"{label}: {path} is missing a RECORD hash")
        if not declared_size:
            errors.append(f"{label}: {path} is missing a RECORD size")
        content = archive.read(files[path])
        if declared_hash:
            _validate_record_hash(path, declared_hash, content, label, errors)
        if declared_size:
            try:
                size = int(declared_size)
            except ValueError:
                errors.append(f"{label}: {path} has an invalid RECORD size")
            else:
                if size < 0 or size != len(content):
                    errors.append(
                        f"{label}: {path} RECORD size does not match its content"
                    )

    for path in sorted(rows):
        if path not in files:
            errors.append(f"{label}: RECORD references missing file {path!r}")


def _check_wheel(path: Path, errors: List[str]) -> ArtifactInfo:
    label = path.name
    if label != EXPECTED_WHEEL:
        errors.append(f"Expected wheel filename {EXPECTED_WHEEL!r}, got {label!r}")
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"{label}: cannot open wheel ({type(exc).__name__})")
        return ArtifactInfo()

    with archive:
        infos = archive.infolist()
        names = [_normalized_path(info.filename) for info in infos]
        _check_forbidden_paths(names, errors)

        for duplicate in _duplicate_names(
            [name for name, info in zip(names, infos) if not info.is_dir()]
        ):
            errors.append(f"{label}: duplicate wheel file path {duplicate!r}")

        files = {
            name: info for name, info in zip(names, infos) if not info.is_dir()
        }
        for name in files:
            if PurePosixPath(name).name in SIGNATURE_FILENAMES:
                errors.append(f"{label}: forbidden Wheel signature file {name!r}")

        record_paths = [
            name for name in files if name.endswith(".dist-info/RECORD")
        ]
        if len(record_paths) != 1:
            errors.append(f"{label}: expected exactly one .dist-info/RECORD file")
            record_path = ""
        else:
            record_path = record_paths[0]

        metadata_paths = [
            name for name in files if name.endswith(".dist-info/METADATA")
        ]
        name = ""
        version = ""
        if len(metadata_paths) != 1:
            errors.append(f"{label}: expected exactly one .dist-info/METADATA file")
        else:
            metadata_text = archive.read(files[metadata_paths[0]]).decode("utf-8")
            metadata = _metadata(metadata_text, label, errors)
            name, version = _check_core_metadata(metadata, label, errors)
            for expected in EXPECTED_METADATA_LINES:
                if expected not in metadata_text:
                    errors.append(f"{label}: METADATA is missing {expected!r}")
            if "github.com/example/" in metadata_text:
                errors.append(f"{label}: METADATA contains a placeholder URL")
            if "License :: OSI Approved" in metadata_text:
                errors.append(f"{label}: METADATA has a deprecated license classifier")

        required_files = (
            "flask_xxljob/__init__.py",
            "flask_xxljob/_version.py",
            "flask_xxljob/py.typed",
        )
        for required in required_files:
            if required not in files:
                errors.append(f"{label}: wheel is missing {required}")

        license_paths = [
            name for name in files if name.endswith(".dist-info/licenses/LICENSE")
        ]
        notice_paths = [
            name for name in files if name.endswith(".dist-info/licenses/NOTICE")
        ]
        if len(license_paths) != 1:
            errors.append(f"{label}: expected LICENSE in wheel license directory")
        elif "Apache License" not in archive.read(files[license_paths[0]]).decode(
            "utf-8"
        ):
            errors.append(f"{label}: wheel LICENSE is not Apache-2.0")
        if len(notice_paths) != 1:
            errors.append(f"{label}: expected NOTICE in wheel license directory")
        elif "Copyright 2026 Pumpkin" not in archive.read(
            files[notice_paths[0]]
        ).decode("utf-8"):
            errors.append(f"{label}: wheel NOTICE has incorrect attribution")

        if record_path:
            _validate_wheel_record(archive, record_path, files, errors)
        return ArtifactInfo(name=name, version=version, file_count=len(files))


def _extract_tar_text(
    archive: tarfile.TarFile,
    members: Dict[str, tarfile.TarInfo],
    name: str,
    label: str,
    errors: List[str],
) -> str:
    member = members.get(name)
    if member is None or not member.isfile():
        errors.append(f"{label}: sdist is missing {name}")
        return ""
    extracted = archive.extractfile(member)
    if extracted is None:
        errors.append(f"{label}: cannot read {name}")
        return ""
    try:
        return extracted.read().decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{label}: {name} is not UTF-8")
        return ""


def _check_sdist(path: Path, errors: List[str]) -> ArtifactInfo:
    label = path.name
    if label != EXPECTED_SDIST:
        errors.append(f"Expected sdist filename {EXPECTED_SDIST!r}, got {label!r}")
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        errors.append(f"{label}: cannot open sdist ({type(exc).__name__})")
        return ArtifactInfo()

    with archive:
        all_members = archive.getmembers()
        names = [_normalized_path(member.name) for member in all_members]
        _check_forbidden_paths(names, errors)
        top_levels = {PurePosixPath(name).parts[0] for name in names if name}
        if top_levels != {EXPECTED_TOP_LEVEL}:
            errors.append(
                f"{label}: expected single top-level directory {EXPECTED_TOP_LEVEL!r}"
            )

        file_pairs = [
            (name, member)
            for name, member in zip(names, all_members)
            if member.isfile()
        ]
        for duplicate in _duplicate_names([name for name, _ in file_pairs]):
            errors.append(f"{label}: duplicate sdist file path {duplicate!r}")
        files = {name: member for name, member in file_pairs}

        required = (
            f"{EXPECTED_TOP_LEVEL}/PKG-INFO",
            f"{EXPECTED_TOP_LEVEL}/pyproject.toml",
            f"{EXPECTED_TOP_LEVEL}/LICENSE",
            f"{EXPECTED_TOP_LEVEL}/NOTICE",
            f"{EXPECTED_TOP_LEVEL}/README.md",
            f"{EXPECTED_TOP_LEVEL}/README.zh-CN.md",
            f"{EXPECTED_TOP_LEVEL}/CHANGELOG.md",
            f"{EXPECTED_TOP_LEVEL}/CHANGELOG.zh-CN.md",
            f"{EXPECTED_TOP_LEVEL}/flask_xxljob/__init__.py",
            f"{EXPECTED_TOP_LEVEL}/flask_xxljob/_version.py",
            f"{EXPECTED_TOP_LEVEL}/flask_xxljob/py.typed",
            f"{EXPECTED_TOP_LEVEL}/docs/publishing.md",
            f"{EXPECTED_TOP_LEVEL}/docs/publishing.zh-CN.md",
            f"{EXPECTED_TOP_LEVEL}/scripts/check_package.py",
            f"{EXPECTED_TOP_LEVEL}/scripts/smoke_installed_wheel.py",
        )
        for required_path in required:
            if required_path not in files:
                errors.append(f"{label}: sdist is missing {required_path}")

        metadata_path = f"{EXPECTED_TOP_LEVEL}/PKG-INFO"
        metadata_text = _extract_tar_text(
            archive, files, metadata_path, label, errors
        )
        metadata = _metadata(metadata_text, label, errors)
        name, version = _check_core_metadata(metadata, label, errors)

        license_text = _extract_tar_text(
            archive, files, f"{EXPECTED_TOP_LEVEL}/LICENSE", label, errors
        )
        notice_text = _extract_tar_text(
            archive, files, f"{EXPECTED_TOP_LEVEL}/NOTICE", label, errors
        )
        if license_text and "Apache License" not in license_text:
            errors.append(f"{label}: sdist LICENSE is not Apache-2.0")
        if notice_text and "Copyright 2026 Pumpkin" not in notice_text:
            errors.append(f"{label}: sdist NOTICE has incorrect attribution")

        return ArtifactInfo(name=name, version=version, file_count=len(files))


def validate_artifacts(dist_dir: Path) -> Tuple[List[str], int]:
    """Return project-specific validation errors and inspected file count."""
    errors: List[str] = []
    if not dist_dir.is_dir():
        return [f"Artifact directory does not exist: {dist_dir}"], 0

    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1:
        errors.append(f"Expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        errors.append(f"Expected exactly one sdist, found {len(sdists)}")
    if len(wheels) != 1 or len(sdists) != 1:
        return errors, 0

    wheel = _check_wheel(wheels[0], errors)
    sdist = _check_sdist(sdists[0], errors)
    if wheel.name and sdist.name:
        if _canonicalize_name(wheel.name) != _canonicalize_name(sdist.name):
            errors.append("Wheel and sdist metadata names do not match")
    if wheel.version and sdist.version and wheel.version != sdist.version:
        errors.append("Wheel and sdist metadata versions do not match")
    return errors, wheel.file_count + sdist.file_count


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate freshly built Flask-XXLJob 0.4.0 artifacts."
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST,
        help="Clean directory containing exactly one wheel and one sdist.",
    )
    args = parser.parse_args(argv)
    errors, entry_count = validate_artifacts(args.dist_dir.resolve())
    if errors:
        print("Package check FAILED:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1
    print(f"Package check passed ({entry_count} files inspected).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
