# 计划归档 — v0.14.x

> 归档时间：2026-10-21（v0.14.0 发布，0.14 系列首份）；2026-10-21 v0.14.0 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.14.x 开发期完成项（含 v0.14.0）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-170` 提交期 dev-verify 墙钟治理（离线桩接管等待型 sleep）✅

**完成（2026-10-21，v0.13.13-dev）**：P0 `dev-verify` 中位 37.3s 里，跨 worker `time.sleep` 累计 104.9s 全属「离线桩已声明、却仍在白等注定取不到的源」——`core/throttle.py:102` 间隔节流 31.9s、`core/retry.py:182/191` 多策略退避 26.2s、`providers/{cninfo,datasink}` 429 限速窗口 3s。动作：`_network_guard` 新增 `_NoWaitClock`（`time` 模块代理，只接管 `sleep`，`monotonic`/`perf_counter` 原样透传），`apply_offline_stubs` 用它替换 `core.throttle` / `core.retry` / `providers.cninfo` / `providers.datasink` 的**模块级 `time`**——作用域限于声明 `offline_external_sources` 的文件，测试自身 `time.sleep` 与验证等待语义的用例（`test_throttle` / `test_phase_timeout` / `test_batch::TestRateLimiter` / `test_handlers::test_queue_full_429`）不受影响，未声明离线的文件等待语义逐字节不变。效果（16 核/load 3~5 交替 3 轮）：**37.3s → 24.0s（−13.3s / −36%）**，用例数与断言强度不变（7481 passed）；并行度复核 `-n 12` 反而更慢（墙钟 27.4~29.4s、user CPU 235s vs 145s）→ 维持 `medium=50% 核数`、不加并发。剩余睡眠 57.8s 中 30s 在 daemon 线程、22.2s 属未声明离线的 provider/fetcher 用例；全局禁睡上限实测中位 22.2s，即剩余可压缩空间 ≤2s，无性价比。测试：`unit/core/test_network_guard.py` 新增 4 例（节流零等待且算式返回值不变 / 退避零等待且重试次数不变 / 代理保留真实 monotonic·perf_counter / 未声明离线时等待语义原样）+ 桩目标存在性补四个模块的 `time.sleep` 断言。
