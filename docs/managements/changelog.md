# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.5]**（2026-10-22）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.6-dev] - 开发中（未发布）

### Fixed

- **`gate → publish` 的 verify 复用按构造永不命中**（v0.14.5 发版实测，等于每次白跑约 27s）：`code_fingerprint` 原用 `git diff HEAD` + `git status` 哈希，而 publish 会先提交 prepare 的改动再算指纹——HEAD 一变，同一份代码就得到两个指纹。改为 `CODE_PATHS`（`src` / `scripts` / `pyproject.toml` / `pytest.ini` / `requirements.txt`）下 **tracked + 未忽略未跟踪文件的内容 sha256**，提交前后一致；回归用例锁「提交前后同指纹 / 内容变化变指纹」。
- **单测改写仓库真实发布戳**（v0.14.5 发版期间发现 `logs/release-gate-stamp.json` 被写成夹具版本 `0.13.12`）：`TestGateArchivePrecondition` 沙箱漏隔离 `GATE_STAMP_FILE`，gate 成功用例走完尾部写入真实路径；现该测试模块统一 autouse 重定向「通过戳 / bench 戳 / 耗时台账」，并加回归断言「跑完 gate 成功用例后仓库真实戳字节不变」。
- **`prepare` 归档后「当前迭代」概述行失准**：归档搬走 ✅ 节后该行仍写「在办 15 项…已实施待归档」（doc-drift 不校验这句，每版都要人工改）。`apply_plan_archive` 现按**现存 `#### plan-N` 节**重算在办项数与 P1~P4 分档编号，残留/幻影编号（如已不存在的 `plan-128`）一并纠正；无分层标题时保守不动。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.5（2026-10-21 ~ 2026-10-22）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
