# 数据、备份与升级

这篇回答四件事：**我的数据都在哪**、**要备份什么**、**换电脑/升级要怎么做**、**怎么清空重来**。首次使用建议只读第 1、2 节（5 分钟），能省掉以后很多麻烦。

## 目录

- [1. 数据都在哪](#1-数据都在哪) · [2. 备份](#2-备份)（[2.1 最小备份（推荐）](#21-最小备份推荐) · [2.2 完整备份](#22-完整备份) · [2.3 密钥文件（重点）](#23-密钥文件重点)）
- [3. 换电脑 / 迁移](#3-换电脑--迁移) · [4. 版本升级](#4-版本升级)
- [5. 重置与卸载](#5-重置与卸载)（[5.1 分级重置](#51-分级重置) · [5.2 卸载](#52-卸载) · [5.3 关于 `.bak`](#53-关于-bak)） · [6. 隐私提醒](#6-隐私提醒)

## 1. 数据都在哪

项目根目录下这些位置和你的数据有关（`reports/`、`logs/`、`data/cache/`、`.venv/` 均为 git 忽略目录，不进版本库）：

```
investor-review/
├── data/
│   ├── holdings/      ← 你的持仓 Excel（每张工作表 = 一个账户）
│   ├── config/        ← 配置文件（含密钥，见 §2.3）
│   ├── history/       ← 组合历史快照（snapshots/，报告环比与演进用）
│   ├── state/         ← 运行时状态（熔断、健康历史、实验计数、决策账本…）
│   ├── cache/         ← 行情/新闻/LLM 等缓存（可随时删）
│   ├── knowledge/     ← 内置知识库（基准对照表、行业关键词）
│   └── calibration/   ← 新闻去重锚点等校准数据（可删）
├── reports/           ← 报告产物：最新版 + 按日期存档（YYYYMMDD/）
└── logs/              ← 运行日志 app.log（按大小轮转）
```

| 目录 | 谁在写 | 删掉会怎样 | 需要备份 |
|---|---|---|---|
| `data/holdings/` | 你（手工放 / Web 上传） | 没数据可算——**这是唯一无法重建的东西** | ✅ 必须 |
| `data/config/` | 程序首次启动生成；你在 TUI/Web 改 | 会重新生成默认配置，你的路径/开关/密钥全丢 | ✅ 必须 |
| `data/history/` | 程序（每次生成报告后写快照） | 环比、组合演进、快照对比会从「没有上期」重新开始 | ✅ 建议 |
| `data/state/` | 程序（熔断恢复、健康历史、实验计数、决策账本） | 自愈类状态自己会重建；**决策账本与实验计数丢了不可恢复** | ⬜ 可选 |
| `data/cache/` | 程序 | 下次运行自动重新拉取（只是慢一次） | ❌ 不必 |
| `data/knowledge/` | 随代码分发 | 会缺内置对照表（基准/关键词） | ❌ 随代码恢复 |
| `reports/` | 程序 | 历史报告归档会丢（如需留存请单独备份） | ⬜ 按需 |
| `logs/` | 程序 | 排查线索丢失 | ❌ 不必 |

## 2. 备份

### 2.1 最小备份（推荐）

只需要三样：**持仓 Excel + `data/config/` 整个目录 + `data/history/`**。

```bash
# Linux / macOS：打包成一个带日期的压缩包
tar -czf ~/investor-backup-$(date +%Y%m%d).tar.gz \
    data/holdings data/config data/history
```

```powershell
# Windows PowerShell
$d = Get-Date -Format yyyyMMdd
Compress-Archive -Path data\holdings,data\config,data\history -DestinationPath "$env:USERPROFILE\investor-backup-$d.zip"
```

### 2.2 完整备份

想连报告归档一起留档，就把 `reports/` 也带上；缓存与日志没有备份价值（体积还不小）。

### 2.3 密钥文件（重点）

`data/config/` 里**两个文件含密钥，备份件也要当密码对待**；其余配置文件不含明文凭据：

| 文件 | 内容 | 注意 |
|---|---|---|
| `llm_key.json` | LLM API Key | 不要提交到 git、不要贴到公开 issue、不要放进公共网盘 |
| `data_key.json` | 数据源密钥（DataSinking / 同花顺等） | 同上 |
| `config.json` / `features.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` | 路径与开关、LLM 参数、线路路由、日志级别、计价参考 | **不含明文密钥**（`llm_providers.json` 用 `credentials_ref` 引用密钥文件），可安全共享 |

程序启动时会检查密钥文件权限，过宽会提示（Linux/macOS 建议 `chmod 600 data/config/llm_key.json data/config/data_key.json`）。另外所有配置写入都会先留 `.bak`（见 §5.3）。

## 3. 换电脑 / 迁移

1. **先备份**（§2.1），把压缩包拷到新机器；
2. **在新机器重新克隆代码**并跑一次启动脚本（`launch.sh` / `launch.ps1`）——`.venv/` 与本机绑死，**不要直接复制**；
3. 把备份解压回项目根目录，覆盖 `data/holdings`、`data/config`、`data/history`；
4. 跑一次自检确认环境与配置都能读懂：

```bash
.venv/bin/python -m src.python.cli doctor
```

5. 生成一次报告验证：路径、密钥、数据源都通就完成了迁移。

> 只迁移持仓、不迁移配置也可以：删掉 `data/config/` 让程序重新生成默认配置，再按 [配置指引](how-to-config.md) 填密钥——适合「旧配置已经很乱、想重新来过」的情况。

## 4. 版本升级

拉新版本后按这个顺序核对，基本不会踩坑：

| 步骤 | 命令 / 动作 | 为什么 |
|---|---|---|
| 1 | `git pull` → 重跑启动脚本（重建/更新依赖） | 依赖清单可能变了 |
| 2 | `.venv/bin/python -m src.python.cli doctor` | 环境、配置、目录、数据源一次性体检 |
| 3 | 打开 TUI 按 `[R]`（刷新配置）或重启程序 | 新增配置项由默认值补齐 |
| 4 | 看 [变更日志](../managements/changelog.md) 对应版本段 | 新增开关的默认值、行为变化都在里面 |
| 5 | 需要时清 `data/cache/` | 缓存格式变了或想强制取新数据（只是慢一次） |

几个常见疑问：

- **旧 `config.json` 缺新键怎么办？** 不用手补：程序按「配置文件不必须存在」的惯例处理，缺失键回落出厂默认；`features.json` 里新增的开关同理。
- **结构版本不符怎么办？** `llm_settings.json` / `logger.json` / `llm_pricing_ref.json` 带 `version`，且程序**只认当前结构**：版本不符会拒绝加载并提示重新生成——删掉该文件重启即按当前模板重建（个人设置需按手册重设；`.bak` 可回退）。`config.json` / `features.json` 无版本门槛，逐键回落默认。
- **升级后报告多/少了几章？** 先看变更日志里「新增开关默认值」；再确认 `[C]`/`[S]` 里的章节与开关状态（新开关默认值可能是「关」）。
- **升级后想回退？** `git checkout <旧 tag>` + 重跑启动脚本；`data/` 一般不需要回退（程序对旧数据向后兼容），但**持仓与配置先备份**更稳妥。

## 5. 重置与卸载

### 5.1 分级重置

| 想达到的效果 | 做法 | 影响 |
|---|---|---|
| 只清缓存（数据可能陈旧时） | 删 `data/cache/`，或 TUI `[3]` / Web「运行状态 → 缓存管理」清理过期项 | 下次运行重新拉取，仅慢一次 |
| 让报告从「没有上期」重新开始 | 删 `data/history/snapshots/` | 环比、组合演进、快照对比重新积累 |
| 恢复出厂配置（保留持仓） | 删 `data/config/` 后重启 | 密钥、路径、开关全部要重新填 |
| 彻底重来 | 删 `data/`、`reports/`、`logs/`（保留 `data/holdings/` 里的持仓 Excel） | 缓存、历史、状态全清 |

> 每次删除前建议先按 §2.1 备份——尤其是 `data/config/`。

### 5.2 卸载

程序本身不写注册表、不装系统服务：**删掉项目目录即卸载**。定时任务（Windows 任务计划程序 / Linux crontab）与 Web 内置调度属于你额外配置的东西，需要单独删除——见 [CLI 手册](how-to-use-cli-mode.md) §13 与 [Web 手册](how-to-use-web-mode.md) §调度。

### 5.3 关于 `.bak`

配置与持仓的**覆盖写**都会先留备份：`config.json.bak`、`个人投资持仓信息.xlsx.bak` 等。它们只保留**上一次**的版本，作用是「改错了能立刻找回」；正确姿势仍是按 §2.1 做带日期的外部备份。

## 6. 隐私提醒

- 报告默认**不做匿名化**，文件名、代码、金额都在里面；对外发送前请开启匿名化（TUI `[A]` / Web 配置面），或只发脱敏样例。
- 程序不向任何自建服务器上报数据：外部请求只发生在你配置的数据源与 LLM 端点。
- 排查问题时贴日志：`logs/app.log` 不含明文密钥（日志对密钥做了掩码），但**含你的持仓代码与金额**，贴之前请自行脱敏。

---

**相关手册**：[← 快速开始](how-to-start.md) · [TUI 菜单操作手册 →](how-to-use-tui-menu.md) · [手册总索引](README.md)
同主题：[常规配置指引](how-to-config.md) · [常见问题解答](faq.md)
