# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.6]**（2026-11-08）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.7-dev] - 开发中（未发布）

### 新增

- **TUI 首页最下方显示本机 IP** —— 主菜单帧末新增一行弱化展示（`本机 IP 192.168.1.5`），
  数据取自 `core/logger.get_machine_ip` 单源（优先非回环网卡），与页头状态行共用 45 秒
  TTL 记忆化（首页逐帧重绘，不重复探测）；探测不到时整行降级为 `本机 IP —`，按列宽折行
  且计入原地重绘行数。用途：在手机/另一台机器上访问本机时不必再去系统里查地址。
  契约行见 `DESIGN-TUI.md` 反馈表，手册见 `how-to-use-tui-menu.md`。

### 修复

- **计价节假日判定只读缓存交易日历（rf-1089）** —— `llm/pricing.py::_is_holiday` 原经
  `trading_calendar._is_trading_day` 判定，日历缓存缺失时会真实取数（akshare）；计价发生在
  每次 LLM 调用收尾，为此拉一次远端日历既慢又与本次调用无关，且无日历缓存的机器 / CI 上
  会把整批 LLM 缓存用例拦成网络守卫硬失败。改为只读 `cached_trading_days()`（不触网），
  无缓存时按「非周末即交易日」降级；补 4 例回归（不触网 / 无缓存降级 / 周末不查日历 / 异常降级）。

- **`cost_first` 策略单价键纠错（rf-1090）** —— `llm/strategy.py::_apply_cost_first` 原读
  `input_price`/`output_price`，而计价表实际键为 `input`/`output`：所有模型得分恒 `inf`，
  `cost_first` 静默退化为「保持原序」（旧用例用同款假键名把错哄住）。改读真实键 + 模型名小写
  归一，缺价/币种子表按未知排末尾；用例改用真实键名，并新增以**真实定价表**为真值的顺序断言。

- **一行静态检查清出的真实隐患（rf-1091）** —— `api_base._attempt` 的 `result` 可能未绑定
  （`PacingGate.__exit__` 声明 `-> bool` 即可被推断为吞异常，现已改 `-> None`）、
  `analysis/scenario.py` 的 CI 区间值可能为 None 仍参与乘法、`analysis/rebalance.py` /
  `trade_discipline.py` 配置段可能为 None 却直接 `dict()` / 下标、`tui_keys` 的 msvcrt 平台桩
  与 `fd` 可空、`holding_change_review` 方向值 `get` 重载不匹配。均为「值判空 + 显式收窄」修复，
  无行为变更。

- **代码类型判定回归中心化（rf-1088）** —— `core/holdings_editor.py::ambiguous_price_kind`
  原内联 `len(raw) == 6 and raw.startswith("00")` 自行判代码形态与 00 重叠区，属架构约束
  「代码类型判定中心化」违规；改用 `code_utils.is_six_digit_code` +
  `is_otc_code_overlap`，与 `price_kind`/`analysis/rebalance.py` 等处口径同一源（消除「代码类型判定中心化」约束下的分散判定）。
  行为不变，补「非 6 位码恒 False」形态用例锁住门槛。

- **主机 IP 展示不再恒为回环** —— 三端（TUI 首页摘要 / CLI 启动日志 / Web 系统信息）
  共用的 `core/logger.py::get_machine_ip` 原为 `gethostbyname(gethostname())`，在
  `/etc/hosts` 把主机名映射到 `127.0.0.1`/`127.0.1.1` 的机器上恒显示回环，对「在哪台
  机器的哪个地址访问」没有信息量。改为按可靠性降序取首个非回环地址：默认出口网卡
  （UDP `connect` 只建路由不发包）→ 主机名解析出的全部 IPv4 → 仅回环可用时仍返回
  回环（离线单机场景它仍是正确地址）→ 全失败 `unknown`。测试网络守卫以
  `BaseException` 子类阻断外部建连，该兜底路径不得让其冒成启动失败。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.6（2026-11-04 ~ 2026-11-08）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
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
