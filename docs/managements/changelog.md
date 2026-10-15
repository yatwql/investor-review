# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.2]**（2026-10-15）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.3-dev] - 开发中（未发布）

### Fixed

- **release 编排：prepare/evolution 收尾补 `check-doc-drift --sync`（rf-686）**：v0.13.2 发布复盘发现 `prepare`（版本全链 + changelog 发布段归档，改写多处文档）与 `evolution`（改写 folders.md 演进表/比率/注释）均改动画布却不同步 folders.md 统计表，而 `refresh` 的 sync 又排在 bench 之后——导致 refresh 的 bench（含 doc-drift crosscheck 单测）因统计过期而红，被迫手动 sync 后整套 bench（14 模式，单遍 ~250s）重跑一遍。修复：两步各自改完文档后立即 sync，从源头保持 folders.md 一致，后续 refresh/publish 的测试不再因统计过期而失败（发布提速，消除重复 bench）。

- **LLM provider 故障切换迟滞修复：墙钟总超时 + 安全网判别服务侧故障（rf-687）**：外部服务事故（DeepSeek 过载）暴露两个缺陷——① httpx read 超时度量「块间间隔」，服务端网关排队滴流时配置的 timeout（120s）完全不生效，单请求挂足服务端 900s 上限；② 200+error 信封被「关闭 thinking」安全网误判为偶发空响应，对同一死端点再白打一轮——最坏 15~30 分钟才切到备用 provider。修复：① 新增 `core/http_client.post_with_deadline` 墙钟原语（POST 以独立 daemon 线程执行、主线程 join(timeout) 到点放弃，归一为 httpx.ReadTimeout 走既有超时分类：退避重试→耗尽后切换）；② `_extract_content` 置「服务端错误信封」线程局部标志，安全网仅对服务端正常返回的空响应触发（传输失败/熔断同理跳过）。故障期单模块切换耗时从 ~15 分钟降至 ~4 分钟（503 重试 + 两个墙钟周期）；同步 technical.md 调用流程图/机制容错表、testplan `llm/` 包覆盖清单、llm-technical 失败追踪表超时口径、how-to-config-llm timeout 语义（端到端墙钟上限）。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0（2026-10-13）
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
