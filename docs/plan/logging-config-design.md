# 日志配置独立成文件（`logger.json`）设计

> **关联**：[`config-panel-taxonomy-design.md`](config-panel-taxonomy-design.md)（面板四域编排与 `[D]` 诊断入口）；图样 `config-panel-mockup/tui.html`、`config-panel-mockup/index.html`。
> **范围**：日志级别、输出目标、轮转参数、日志查看器默认筛选的**配置化**，以及对应的文件、加载顺序、校验、面板入口。
> **不含**：改日志格式（`%(asctime)s [%(levelname)s] %(message)s` 恒定）、改日志读取/解析逻辑、改报告归档清理策略。

---

## 1. 目标

1. **日志配置有归属文件**：`data/config/logger.json`（新增），与 `config.json` / `llm_settings.json` 同级，只放日志相关项。
2. **可配三类旋钮**：写盘级别与路径、控制台级别与颜色、轮转与保留（大小/备份数/查看器默认筛选）。
3. **排障不被配置阻断**：环境变量仍可在**不改文件**的前提下临时覆盖（容器/CI/一次性排障场景）。
4. **校验与面板同源**：非法级别、越界数值一律明确拒绝；TUI 与 Web 走同一份规格。

---

## 2. 文件结构

```jsonc
{
  "version": 1,

  // ── 写盘 ──────────────────────────────────────────────
  "file": {
    "path": "logs/app.log",      // 相对项目根或绝对路径；测试进程仍固定 logs/test.log
    "level": "INFO",             // DEBUG / INFO / WARNING / ERROR / CRITICAL
    "max_bytes": 10485760,       // 单文件上限（字节），默认 10 MB
    "backup_count": 5            // 备份份数（app.log.1 … app.log.N）
  },

  // ── 控制台 ────────────────────────────────────────────
  "console": {
    "level": "INFO",
    "color": true                // 终端不支持颜色时自动降级，本项为"允许使用颜色"
  },

  // ── 日志查看器（TUI [D]→[V]、Web「运行日志」）───────────
  "viewer": {
    "default_level": "INFO",     // 打开时的默认筛选级别；"ALL" = 不过滤
    "tail_lines": 500            // 首屏读取行数上限
  }
}
```

不放进 `config.json` 的理由：日志是**运行诊断域**的配置，与持仓/报告/数据源无关；独立文件便于在故障时只改这一份、也便于 CI 用环境变量或临时文件覆盖。

---

## 3. 键位与默认值

| 键 | 类型 | 默认 | 范围 | 说明 |
|:--|:--|:--|:--|:--|
| `file.path` | str | `logs/app.log` | 非空；不得含 `..` | 写盘目标；测试进程固定 `logs/test.log`（不受本项影响） |
| `file.level` | enum | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL | 写盘级别 |
| `file.max_bytes` | int | `10485760` | 1024 ~ 1073741824 | 单文件上限 |
| `file.backup_count` | int | `5` | 0 ~ 50 | 备份份数；0 = 不轮转 |
| `console.level` | enum | `INFO` | 同上 | 控制台级别 |
| `console.color` | bool | `true` | — | 允许颜色（无颜色终端自动降级） |
| `viewer.default_level` | enum | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL/ALL | 查看器默认筛选 |
| `viewer.tail_lines` | int | `500` | 50 ~ 10000 | 首屏读取行数 |

---

## 4. 生效优先级

```
环境变量（仅级别）> logger.json > 内置默认
```

- `INVEST_LOG_FILE_LEVEL` / `INVEST_LOG_CONSOLE_LEVEL`：保留为**临时覆盖**，用于"不改文件也不进面板"的排障场景；非法值告警一次并回落该层下一优先级。
- 其余键（路径/轮转/查看器）只由 `logger.json` 决定，不设环境变量——避免出现"改了环境变量但没人知道"的隐性状态。
- 演进策略：结构以当前版本为准（**不做旧版兼容**）——其他结构不解析、不转换；重新生成 `logger.json` 并同步更新默认配置生成器。
- 日志文件只按当前行格式解析；更早的行按原文展示，需要干净视图时归档或清空 `logs/`。
- 路径绝对化：`file.path` 在配置层输出绝对路径（相对值仅在读取时解析），与其它路径型配置同口径。
- 加载时机：进程启动时、`logging` 初始化前完成；文件缺失→全默认（不报错）、格式错误→告警并全默认。
- **不引入循环依赖**：`core/logger.py` 不导入 `config` 包，内联读取 JSON（仅标准库 `json` + 路径常量）；面板/校验层再经 `config` 包暴露 `get_logger_config()` 与写入口。

---

## 5. 校验与错误

| 场景 | 行为 |
|:--|:--|
| 级别不在枚举内 | 加载时告警并回落默认；面板保存时**拒绝**并提示合法值 |
| 数值越界/非整数 | 同上（加载回默认、保存拒绝） |
| `path` 含 `..` 或为空 | 加载回默认；保存拒绝 |
| 文件不存在 | 全默认，不告警（首次运行正常态） |
| `version` 缺失、≠1 或高于支持值 | 拒绝加载并提示重新生成（不静默降级、不做其他结构解析） |
| 目录不可写 | 启动时告警并回落控制台输出（不因日志写失败阻断主流程） |

---

## 6. 面板入口

### 6.1 TUI：`[D]` 诊断与排查 → `[L]` 日志设置

```
  ── 诊断与排查 ──
   [V] 运行日志（可按级别筛选）
   [H] 数据源健康历史
   [T] 系统自检（环境 / 配置 / 目录 / 数据源）
   [L] 日志设置（级别 / 轮转 / 查看器）
   [0] 返回主菜单
```

`[L]` 三级（数字编号，`0` 返回诊断与排查）：

```
  ── 日志设置 ──
   1. 写盘级别（当前 INFO）
   2. 控制台级别（当前 INFO）
   3. 单文件上限 MB（当前 10）
   4. 备份份数（当前 5）
   5. 查看器默认级别（当前 INFO）
   6. 查看器首屏行数（当前 500）
   0. 返回诊断与排查
```

- 1/2/5 为枚举选择（输入编号或级别名），3/4/6 为数值（范围校验，越界拒绝）。
- 级别/轮转改动**下次进程启动生效**（handler 在启动时创建）；面板保存后给出明确提示"重启后生效"，查看器两项即时生效。

### 6.2 Web：新增域「运行与诊断」

| 块 | 控件 | 键 |
|:--|:--|:--|
| 日志设置 | 两个下拉（写盘/控制台级别）+ 两个数字（上限 MB / 备份数）+ 查看器默认级别与行数 | `file.level` / `console.level` / `file.max_bytes` / `file.backup_count` / `viewer.default_level` / `viewer.tail_lines` |

- 域说明：「日志写盘与控制台输出；级别与轮转改动在下次启动生效，查看器默认项即时生效」。
- 该域对应 TUI `[D]` → `[L]`，是两渠道共用概念的又一处落点（域 ↔ 菜单）。
- 保存后同样提示生效时机，避免"改了即时级别却看不到变化"。

---

## 7. 影响面

### 7.1 代码

| 文件 | 改动 |
|:--|:--|
| `core/logger.py` | 启动时内联读取 `logger.json`（不导入 config 包）；按配置创建 handler（路径/级别/轮转/颜色）；环境变量作为级别覆盖；写失败回落控制台 |
| `config/_logging.py`（新增） | `get_logger_config()` / 默认值 / 校验 / mtime 缓存 / 写入入口（面板与 CLI 共用） |
| `config/__init__.py` | 导出 `get_logger_config` 等公开面 |
| `config/edit_ops.py` | 白名单新增 6 个日志项（`logger_scalar` 写入原语；枚举与数值校验与面板一致） |
| `core/log_reader.py` / `tui/handlers_log.py` / Web 日志 API | 读取 `viewer.default_level` 与 `tail_lines` 作为初始值（用户仍可在界面内改筛选，不回写） |
| `tui/handlers_config.py` | `[D]` 子菜单新增 `[L]` 日志设置处理器（数字项，0 返回） |
| `web/config_edit.py` | surface 新增 `logging` 块；域编排新增「运行与诊断」 |
| `static/web/main.js` | 渲染日志设置块（下拉 + 数字 + 生效提示） |

### 7.2 文档

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-config.md` | 配置项索引新增 `logger.json` 行；新增「日志设置」小节（键表 + 生效时机 + 环境变量覆盖） |
| `manuals/how-to-use-tui-menu.md` | `[D]` 节补 `[L]` 日志设置；三级面板示例 |
| `manuals/how-to-use-web-mode.md` | 配置面板新增「运行与诊断」域的说明 |
| `manuals/faq.md` | 日志排查条目覆盖三条路径：环境变量（临时）/ `logger.json`（持久）/ 面板（持久） |
| `managements/requirements.md` / `technical.md` | 配置文件清单与 `logger` 配置模块；菜单表 `[D]` 行 |
| `managements/testplan.md` | 日志配置加载/校验/覆盖/生效时机覆盖 |
| `folders.md` | 目录树新增 `config/_logging.py`；数据文件说明补 `logger.json` |

### 7.3 机检与测试

- `data_registry.get_known_*` 不收录日志键（校验由 `config/_logging.py` 自持）；`check-doc-drift` 的默认值表不涉及本文件。
- 单测：默认值、非法级别/越界数值、env 覆盖优先级、mtime 缓存失效、写盘路径与轮转参数生效、日志目录不可写回落、查看器默认值透传。
- 集成：`logger.json` 设为 DEBUG 后重启，`logs/app.log` 出现 DEBUG 行；面板保存非法值被拒且文件不变。

---

## 8. 验证计划

1. 单测：默认值、非法级别/越界数值、env 覆盖优先级、缓存失效、轮转参数生效、目录不可写回落、查看器默认透传（七项逐一断言）。
2. 手动：TUI `[D]→[L]` 改级别 → 重启后日志文件出现对应级别；Web「运行与诊断」保存非法值被拒并提示范围。
3. 回归：日志写失败（目录只读）时主流程仍可跑完，控制台仍有输出。
4. 文档：`how-to-config.md` 键表与文件实际键一致（由 `check-doc-drift` 的默认值表外人工复核一次）。

---

## 9. 约束遵从

| 约束 | 遵从方式 |
|:--|:--|
| 原子写 | 面板/CLI 写入经既有原子写原语，不新增写盘路径 |
| 路径绝对化 | `file.path` 配置层输出绝对路径 |
| 控制台着色 | `console.color` 与 `NO_COLOR`/非 TTY 自动降级一致 |
| 日志统一 | 日志器仍为 `logging.getLogger("invest")`；配置只调 handler 参数 |
| 凭据不入日志 | 本文件不含凭据；日志内容按脱敏规则输出 |
| 中文注释 | 生成器输出带分类与逐项中文注释；读取经统一注释剥离器 |
