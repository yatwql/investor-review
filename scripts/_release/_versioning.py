"""版本号解析/渲染纯函数（X.Y.Z-dev 开发版 ↔ X.Y.Z 发布版）。

全部为纯文本变换，不读文件系统、不读入口模块路径常量。
"""

from __future__ import annotations

import re

from _release._common import ReleaseError

DEV_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-dev$")
RELEASE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
APP_VERSION_LINE_RE = re.compile(r'^APP_VERSION = "([^"]+)"', re.M)


def read_app_version(text: str) -> str:
    m = APP_VERSION_LINE_RE.search(text)
    if not m:
        raise ReleaseError("constants.py 中未找到 APP_VERSION 行")
    return m.group(1)


def render_app_version(text: str, version: str) -> str:
    new_text, n = APP_VERSION_LINE_RE.subn(f'APP_VERSION = "{version}"', text, count=1)
    if n != 1:
        raise ReleaseError("constants.py 中未找到 APP_VERSION 行")
    return new_text


def release_version_of(dev_version: str) -> str:
    m = DEV_VERSION_RE.match(dev_version)
    if not m:
        raise ReleaseError(f"当前版本 {dev_version} 不是 X.Y.Z-dev 形态（发布前应处于开发版）")
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"


def next_dev_version_of(release_version: str) -> str:
    m = RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    return f"{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}-dev"


def render_readme_version(text: str, version: str) -> str:
    new_text, n = re.subn(r"^(> 当前版本：)[^\s（]+", lambda m: m.group(1) + version, text, count=1, flags=re.M)
    if n != 1:
        raise ReleaseError("README.md 中未找到「> 当前版本：」行")
    return new_text


def normalize_release_title(title: str) -> str:
    """剥离 `--title` 中多余的 `release: v… —— ` 或裸版本 `v… —— ` 前缀。

    commit subject 由 publish 统一加前缀（`release: v{ver} —— {title}`）；title 自带
    前缀时会拼出双前缀（发布提交实测）。两类自写前缀都剥：

    - `release: vX.Y.Z —— 主题`（带 release: 标签）
    - `vX.Y.Z —— 主题` / `vX.Y.Z-dev —— 主题`（裸版本+破折号，人工写标题时最
      自然的写法；此前只剥第一类，会拼出重复两遍版本号的提交标题）

    剥离后为空（title 本身就是前缀）则按原样使用。
    """
    stripped = title.strip()
    for pattern in (
        r"^release:\s*v\S+\s*—+\s*",
        r"^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?\s*—+\s*",
    ):
        stripped = re.sub(pattern, "", stripped, count=1)
    return stripped or title.strip()


def archive_name_for(release_version: str) -> str:
    """按小版本推导 changelog 归档文件名（纯字符串，无路径拼接）。"""
    m = RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    return f"archived_changelog.{minor}.x.md"
