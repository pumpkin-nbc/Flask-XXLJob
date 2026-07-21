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
from typing import List

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# 不允许出现在产物中的路径片段 / Path fragments not allowed in artifacts.
FORBIDDEN_PATH_FRAGMENTS = [
    ".venv",
    ".idea",
    ".git/",
    "__pycache__",
]


def _artifact_names() -> List[str]:
    names: List[str] = []
    for whl in DIST.glob("*.whl"):
        with zipfile.ZipFile(whl) as archive:
            names.extend(archive.namelist())
    for sdist in DIST.glob("*.tar.gz"):
        with tarfile.open(sdist) as archive:
            names.extend(archive.getnames())
    return names


def main() -> int:
    if not DIST.exists():
        print("No dist/ directory found. Build the package first.")
        return 1

    names = _artifact_names()
    if not names:
        print("No build artifacts found in dist/.")
        return 1

    errors: List[str] = []
    for name in names:
        for fragment in FORBIDDEN_PATH_FRAGMENTS:
            if fragment in name:
                errors.append(f"Forbidden path in artifact: {name}")

    if errors:
        print("Package check FAILED:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1

    print(f"Package check passed ({len(names)} entries inspected).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
