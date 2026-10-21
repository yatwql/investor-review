# 检查脚本共享历史叙述词表：单一来源设计

> 文档版本：0.13.11-dev
> 状态：已实施（`scripts/_traces_common.py` + `scripts/_traces_doc/patterns.py`）

## 1. 背景

`check-code-traces.py`（代码注释域）与 `check-doc-traces.py`（文档域）是两个独立脚本，但「历史变更叙述」的判定词汇高度重合——实测两模式表中有 **31 条正则逐字节相同**（分类 CODE/CIPHER/HIGH/CHAPTER/ROUND/LOW 各有重合），例如 `已迁移`、`重构前`、`替代旧`、`第X章`、`第N轮`、`系列代号`、`架构约束代号`。

语义命名纪律要求同一规则只有一处定义。重复 31 条正则的直接后果：

- 新增同义词（如 `改名` 再补 `更名`）时**必须**记得在两侧同时改；只改一侧 → 另一域静默漏检，且两侧描述文案天然漂移；
- 两侧模式的**顺序**决定「每行首个命中」的报告分类，顺序不一致时同一行在两域报不同类别，排查成本高；
- 词表条目本身就是历史痕迹字面量的集合（如注释里的「旧逻辑/曾考虑」），放进任一脚本正文都会让另一脚本的自查报错。

## 2. 决策

新增 `scripts/_traces_common.py` 作为**词表单一来源**：只登记正则字面量（命名常量 + `SHARED_REGEXES` 元组），不含分类与描述。两侧模式表改为常量引用，分类/描述仍按各自域定义。

```
scripts/_traces_common.py      # 31 条共享正则字面量（本模块不含判定逻辑）
        ↑                      ↑
_traces_code/patterns.py   _traces_doc/patterns.py
（代码域分类/描述）         （文档域分类/描述）
```

补充决策：

1. **文档域模式表整体迁出 CLI** → `scripts/_traces_doc/patterns.py`（`DOC_PATTERNS` / `TREE_ONLY_PATTERNS` / `EXCLUDE_PATTERNS` / `is_excluded`）。CLI 已逼近千行红线，共享词表接入必须先把模式表搬走，否则只能删注释凑行数。
2. **多域登记辅助** `_multi_domain()`：同一正则（如 `不再`）需在 STATUS 与 NARRATIVE 各登记一条，正则字面量只写一份。
3. **树行专属模式并入 bundle**：`_pattern_bundle(categories, include_cipher, include_tree_only)`——原树行分支需「单独拼表 + 跳过并集预筛」（`prefilter=None`），现在预筛面与精确面同源，少一处特例分支。
4. **规则载体豁免扩面**：`_traces_code/config.py` 的 `RULE_CARRIER_DIRS` 增加 `_traces_doc`，并新增 `RULE_CARRIER_FILES = {"_traces_common.py"}`——词表与模式表属「尺子本身」，与 `check-*traces.py` 同等待遇，否则新文件里的示例字面量会被 code-traces 自己扫出来。
5. **结论缓存指纹扩面**：`check-doc-traces.py` 的 `_LOGIC_FILES` 加入 `_traces_doc/patterns.py` 与 `_traces_common.py`——判定面搬家后，缓存键必须跟着走，否则改模式仍回放旧结论（假绿）。

## 3. 契约

- 公开面不变：`check-doc-traces.py` 仍可按脚本名访问 `_DOC_PATTERNS`（`(pattern, category, description)` 字符串元组）、`_is_excluded`；测试与 `check-doc-drift` 等调用方无需改动。
- `_traces_common` 只导出常量，不导出函数：判定的入口、分类矩阵、豁免语义仍归各域模块，避免「共享模块长成第二个 CLI」。
- 新增同源模式的落地顺序：字面量加进 `_traces_common` → 两域模式表引用常量 → 两侧各补一条正向用例。若只在一域需要，就不进共享词表。

## 4. 验证

`src/test/unit/scripts/test_trace_shared_vocabulary.py` 锁四件事：

| 断言 | 防的回归 |
|------|----------|
| `SHARED_REGEXES` 内无重复 | 两个语义名指向同一正则（隐形重复） |
| 两域模式表都包含每一条共享正则 | 常量加了但某侧忘了引用（静默漏检） |
| 两表交集恰等于共享词表 | 新增同源模式未收编，就地复制第二份 |
| 两模式源码内不出现共享字面量 | 「图省事」重新写死，漂移面回归 |
| `不再` 在 STATUS/NARRATIVE 各一条 | 多域登记的语义不被「去重」掉 |

另：`TestDocTracesCacheLogicSurface` 断言 `_LOGIC_FILES` 覆盖 `patterns.py` / `_traces_common.py` 且文件真实存在。

## 5. 取舍

- **不抽出跨脚本模式表的公共结构**（只共享字面量）：分类集合与域矩阵两侧不同（代码域有 ORIGIN/DEPR/IDENT/MAGIC，文档域有 ARCHIVE/STATUS/NARRATIVE），强行统一会把域语义塞进共享模块。
- **不合并两脚本**：扫描对象、退出码分级、豁免策略均不同（代码域 HIGH=1/LOW=3，文档域 HIGH=1/LOW=2），合并后 CLI 分支比现在更多。
- 模式顺序仍是「每行首个命中」的隐式契约：往共享词表加词不影响顺序，但调整某侧表内顺序仍会改变报告分类——该风险与本次改动无关，保持原顺序即零漂移（已用全仓 `--ci` 对拍确认 findings 集合一致）。
