"""
文档一致性检查脚本。

Documentation consistency check script.

检查项对应需求文档第 29 节。

The checks correspond to section 29 of the requirements document.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent

# 需要成对存在的英文文档基名（相对仓库根目录，不含 .md）。
# English doc base names (relative to repo root, without .md) that must be
# paired with a .zh-CN.md counterpart.
PAIRED_DOCS = [
    "README",
    "CHANGELOG",
    "CONTRIBUTING",
    "SECURITY",
    "docs/getting-started",
    "docs/configuration",
    "docs/application-factory",
    "docs/request-callbacks",
    "docs/callback",
    "docs/deployment",
    "docs/logging",
    "docs/migration",
    "docs/development",
    "docs/publishing",
    "docs/api-reference",
    "docs/integration-testing",
    "examples/basic/README",
    "examples/application_factory/README",
    "examples/batch_callback/README",
    "examples/complete_integration/README",
    "examples/multiple_apps/README",
    "examples/registry_status/README",
]

# 禁止出现的旧文档命名 / Forbidden legacy doc names.
LEGACY_PATHS = [
    "README_EN.md",
    "CHANGELOG_EN.md",
    "docs/en",
    "docs/zh-CN",
]


def _count_code_fences(text: str) -> int:
    return len(re.findall(r"^```", text, flags=re.MULTILINE))


def _config_keys(text: str) -> set:
    return set(re.findall(r"XXL_JOB_[A-Z_]+", text))


def _changelog_version(text: str) -> str:
    match = re.search(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)\]", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _package_version() -> str:
    text = (ROOT / "flask_xxljob" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _pyproject_name() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def main() -> int:
    errors: List[str] = []

    # 1 & 2: 成对存在 / paired existence.
    for base in PAIRED_DOCS:
        en = ROOT / f"{base}.md"
        zh = ROOT / f"{base}.zh-CN.md"
        if not en.exists():
            errors.append(f"Missing English document: {base}.md")
        if not zh.exists():
            errors.append(f"Missing Chinese document: {base}.zh-CN.md")

    # 9: 无旧命名 / no legacy naming.
    for legacy in LEGACY_PATHS:
        if (ROOT / legacy).exists():
            errors.append(f"Legacy documentation path present: {legacy}")

    # 3: README 语言切换链接 / README language switch links.
    for name in ("README.md", "README.zh-CN.md"):
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if "[English](README.md)" not in text or "[简体中文](README.zh-CN.md)" not in text:
                errors.append(f"{name} is missing the language switch links")

    # 6: 代码块数量一致 / code fence count parity.
    for base in PAIRED_DOCS:
        en = ROOT / f"{base}.md"
        zh = ROOT / f"{base}.zh-CN.md"
        if en.exists() and zh.exists():
            en_count = _count_code_fences(en.read_text(encoding="utf-8"))
            zh_count = _count_code_fences(zh.read_text(encoding="utf-8"))
            if en_count != zh_count:
                errors.append(
                    f"Code fence count mismatch in {base}: "
                    f"EN={en_count} ZH={zh_count}"
                )

    # 5: 配置项名称一致 / config key parity.
    for base in ("README", "docs/configuration"):
        en = ROOT / f"{base}.md"
        zh = ROOT / f"{base}.zh-CN.md"
        if en.exists() and zh.exists():
            en_keys = _config_keys(en.read_text(encoding="utf-8"))
            zh_keys = _config_keys(zh.read_text(encoding="utf-8"))
            if en_keys != zh_keys:
                diff = en_keys.symmetric_difference(zh_keys)
                errors.append(f"Config key mismatch in {base}: {sorted(diff)}")

    # 4 & 10: CHANGELOG 版本一致且与单一版本源匹配 / changelog + version source.
    package_version = _package_version()
    en_changelog = _changelog_version((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    zh_changelog = _changelog_version(
        (ROOT / "CHANGELOG.zh-CN.md").read_text(encoding="utf-8")
    )
    if en_changelog != zh_changelog:
        errors.append(
            f"CHANGELOG version mismatch: EN={en_changelog} ZH={zh_changelog}"
        )
    if en_changelog != package_version:
        errors.append(
            f"CHANGELOG version {en_changelog} does not match package "
            f"version {package_version}"
        )

    # 7 & 8: 包名与导入名统一 / package and import name consistency.
    if _pyproject_name() != "flask-xxljob":
        errors.append("pyproject name must be 'flask-xxljob'")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "flask_xxljob" not in readme:
        errors.append("README.md must reference the import package 'flask_xxljob'")

    if errors:
        print("Documentation check FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Documentation check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
