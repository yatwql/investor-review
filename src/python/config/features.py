"""功能开关注册表 — Feature Flag 体系。

提供集中管理功能开关的能力，替代分散在各模块中的条件判断。
所有开关在注册表中统一声明默认值，支持运行时启用/禁用。

用法：
  >>> from src.python.config.features import is_feature_enabled, FEATURE_FLAGS
  >>> if is_feature_enabled("metrics_enabled"):
  ...     render_metric_cards()

配置持久化：功能开关可通过 features.json 覆写默认值。
全部开关在 :data:`feature_switch_registry` 一处登记（显示名/说明/作用域分组/
默认值/产物影响/实验身份），TUI 面板、Web 配置面板、CLI 取值域与文档清单一律
由它派生——渠道层不得另写开关清单。分组（呈现与体验 / 分析增强 / 独立章节与
回放 / 机制与诊断）表达**作用域**——「开了长出什么」，是面板主分类轴；
**生命周期**是独立字段 ``experimental``：``--experiment`` 取值域与页脚实验自述
只看该字段，不看分组。「转正」= 把 ``experimental`` 置 False 摘除实验身份；
若作用域同时变化则再改 ``group``。
模块级 LLM 分析章节、新闻源、报告章节等**不在此登记**——它们各有归属文件，
见 ``feature_switch_registry`` 上方说明。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any

from src.python.core.atomic_write import write_json_atomic
from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

# ── 路径常量 ────────────────────────────────────────────────

FEATURES_FILE = os.path.join(PROJECT_ROOT, "data/config/features.json")

# ── 分组常量（作用域轴）───────────────────────────────────────
# 分组表达**作用域**——用户决策心智是「开了长出什么」：
#   GROUP_PRESENTATION —— 呈现与体验：只改呈现不改内容（2 项全默认开）
#   GROUP_ANALYSIS     —— 分析增强：在既有章节内追加分析块/列/子表
#   GROUP_STANDALONE   —— 独立章节与回放：新增整页签或多期回放（全默认关）
#   GROUP_MECHANISM    —— 机制与诊断：内部机制 / 诊断接缝 / 待验证实验
# **生命周期是另一根轴**：``FeatureSwitchDef.experimental``（末位默认 False 字段）。
# 此前「默认值」「是否实验项」「分组」三者纠缠在一个 group 字段上：转正会连带
# 摘掉面板入口（doctor_check 转正后只剩手改 features.json 一条关闭途径）、
# 组内默认态混合时标签写不准。解耦后：作用域由 group 定、生命周期由
# experimental 定、取值由 default 定——``--experiment`` 取值域与页脚实验自述
# 只看 experimental，「转正」= experimental 置 False（作用域也变时再改 group）。

GROUP_PRESENTATION = "presentation"
GROUP_ANALYSIS = "analysis"
GROUP_STANDALONE = "standalone"
GROUP_MECHANISM = "mechanism"

# 分组标题（TUI 菜单 [S] 与 Web 配置面板共用同一措辞，渠道层不另写文字）
GROUP_LABELS: dict[str, str] = {
    GROUP_PRESENTATION: "📊 呈现与体验（默认开启 · 只改呈现不改内容）",
    GROUP_ANALYSIS: "🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表）",
    GROUP_STANDALONE: "📑 独立章节与回放（默认关闭 · 新增整页签或多期回放）",
    GROUP_MECHANISM: "⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验）",
}
# 面板分块顺序（顺序即渲染顺序；默认开在前、默认关在后、机制收尾）
GROUP_ORDER: tuple[str, ...] = (GROUP_PRESENTATION, GROUP_ANALYSIS, GROUP_STANDALONE, GROUP_MECHANISM)


@dataclass(frozen=True)
class FeatureSwitchDef:
    """单条功能开关声明。

    Attributes:
        label: 显示名（TUI 面板行名 / Web 配置面板标签，服务端同源下发）
        desc: 一句话说明（CLI 报错提示、控制台横幅、文档）
        group: 作用域分组（``GROUP_PRESENTATION`` / ``GROUP_ANALYSIS`` /
            ``GROUP_STANDALONE`` / ``GROUP_MECHANISM``）
        default: 出厂默认值（``features.json`` 未覆写时的取值）
        affects_report: 开启后报告产物内容是否可能不同——决定它是否进入产物自述
        experimental: 生命周期为实验项（``--experiment`` 取值域即此字段为真者；
            末位默认 False，仅实验项显式标注）
    """

    label: str
    desc: str
    group: str
    default: bool
    affects_report: bool
    experimental: bool = False


# ── 功能开关注册表（唯一登记点） ────────────────────────────
# 渠道层（TUI 面板、Web 配置面板、CLI 取值域与提示）与各文档清单一律由此派生，
# **不得另写清单**——一处登记即三面上屏，改一处即三面同步。声明顺序即面板顺序。
#
# 本注册表只登记**有消费者的开关**（全仓必有一处 is_feature_enabled 读取其取值）。
# 其余开关各有归属文件，不在此登记、也不要再往这里搬：
#   - LLM 模块启停 / 基金深度分析模块 → llm_settings.json 的 enabled_llm（TUI 菜单 S
#     标准模块区、Web 配置面板「LLM 分析章节」组）
#   - 新闻源启停 → config.json 的 news_sources
#   - 历史走势与回撤 → config.json 的 enable_history
#   - 基础报告章节（基金深度分析/市场新闻/组合演进/行动建议）→ config.json 的 enable_*
#   - 匿名化模式 → config.json 的 anonymization.mode
# 注：报告增强子模块（数据质量/行业Beta/候选比较/成本流水/估值分位/市场温度/财报摘要/
# 财务指标）登记于本注册表 GROUP_ANALYSIS / GROUP_STANDALONE 分组，取值落 features.json。
# 声明了却无人读取的开关会让用户照文档配置后毫无效果（本注册表曾含 16 项此类
# 陈旧开关，已全部移除）。新增开关必须同时接线到消费点，回归测试见
# test_features.py::TestRegistryLiveness。
#
# ``affects_report`` 是**产物自述的准入口径**：开启该开关后报告产物的内容是否可能
# 不同。``experimental`` 与 ``affects_report`` 双真者进入报告自述（HTML 页脚 /
# Excel 落点）与控制台横幅，读者据此判断手上这份产物是否非默认开关下的结果；
# ``affects_report`` 为 True 的非实验项在 Web 配置面板的项标签上带「（影响报告）」。
# 只改入口可见性的开关答 False，不得凭惯性落进自述——
# 列出一个不改报告任何字节的开关，读者会推断内容受其影响。
feature_switch_registry: dict[str, FeatureSwitchDef] = {
    # ── 机制与诊断：LLM 输出增强实验项（写盘积累账本，experimental=True 需真实数据验证） ──
    "decision_reflection": FeatureSwitchDef(
        "决策跨期反思闭环",
        "登记决策 → 真实行情结算命中率 → 教训回灌专家复盘提示词",
        GROUP_MECHANISM,
        False,
        True,
        experimental=True,
    ),
    # ── 机制与诊断：报告对话式追问实验项（报告页同源问答、experimental=True；
    #    消费点：web/handlers._handle_report_qa_ask（403 门）+ 报告模板追问区块 ──
    "report_qa": FeatureSwitchDef(
        "报告对话式追问",
        "报告页内针对本期报告的会话式追问（零新增取数、轮数上限、用量独立记账）",
        GROUP_MECHANISM,
        False,
        True,
        experimental=True,
    ),
    # ── 机制与诊断：确定性信号（实时注入 + 跨期沉淀双面，账本已有真实积累故转正合并） ──
    "deterministic_signal": FeatureSwitchDef(
        "确定性信号模块",
        "市场温度/估值分位/尾部风险等确定性评级的实时预消化信号行注入复盘与体检提示词，"
        "并跨期沉淀为带实时-非实时标签的账本（统计默认只算实时），教训与命中率随摘要回灌提示词",
        GROUP_MECHANISM,
        True,
        True,
    ),
    # ── 分析增强与独立章节的转正项（实验身份已摘除，default 保持原值） ──
    # 面板编号 = 组序 + 注册表内声明顺序派生；四分组后不再有「转正项追加块首、
    # 既有项编号不位移」的跨块承诺（块边界由作用域决定，见手册面板编号表）
    # 辩论-正反辩论（已转正，2026-10-11；三段式换调用次数，默认关）。
    # 集中度问答段为本流程内建段落（见 prompts_action._build_concentration_qa_block），
    # 其触发阈值配置在 llm_settings.json 的 debate.concentration_qa.threshold。
    "llm_debate_procon": FeatureSwitchDef("辩论-正反辩论", "三段式(白脸→黑脸→综合)", GROUP_ANALYSIS, False, True),
    # 辩论增强：条件推理（与正反辩论相邻；默认开不变，情景段仍在既有调用内产出）
    "llm_debate_conditional": FeatureSwitchDef("辩论-条件推理", "情景化分析(涨/跌/震荡)", GROUP_ANALYSIS, True, True),
    # 因子目录（已转正，2026-10-11；门槛评测三指标过审）
    "factor_catalog": FeatureSwitchDef(
        "因子目录",
        "25 因子五来源族横截面信号入账与风格与因子分析区「因子目录」区块",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    # 调仓纪律回放（已转正，2026-10-11；先决门槛三项过审）
    "rebalance_schedule_replay": FeatureSwitchDef(
        "调仓纪律回放",
        "月度定期/阈值偏离纪律多期回放 vs 买入持有（含成本），回放章双线与逐期成本表",
        GROUP_STANDALONE,
        False,
        True,
    ),
    "holding_change_review": FeatureSwitchDef(
        "持仓变动复盘",
        "快照差分出新增/加仓/减仓/清仓事件清单与频率/结构演变/意图对账（区间净额推断，结构级）+ LLM 归因块",
        GROUP_STANDALONE,
        False,
        True,
    ),
    # ── 独立章节与回放：What-if 交易成本与基准对比（页签/区块类转正项：实验身份已摘除、default 保持 False）──
    "whatif_trade_cost": FeatureSwitchDef(
        "What-if 交易成本对比",
        "调仓回放计入申赎成本（FIFO 持有期阶梯）+ 成本前后收益差与业绩基准三线参照",
        GROUP_STANDALONE,
        False,
        True,
    ),
    # ── 分析增强：事件窗量化对照（区块类转正项：实验身份已摘除、default 保持 False）──
    "event_window_impact": FeatureSwitchDef(
        "事件窗量化对照",
        "新闻事件映射交易日后 ±5 交易日窗口：品种收益/超额收益与文本极性同表对照，分歧例进 LLM 分析章",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    # ── 机制与诊断：LLM 输出增强（只读侧注入，不增调用次数、不写盘） ──
    "module_quality_gate": FeatureSwitchDef(
        "模块级质量分级",
        "按完整性/一致性给各 LLM 模块输出评 A~F 级，低评级随内容头部标注质量提示（不阻断不重试）",
        GROUP_MECHANISM,
        True,
        True,
    ),
    "decision_header_parse": FeatureSwitchDef(
        "决策头结构化",
        "提示词追加受控 JSON 决策头，抽取优先读结构化、失败回落确定性表格解析（决策词归一，防写反方向）",
        GROUP_MECHANISM,
        True,
        True,
    ),
    # ── 机制与诊断：数据层（就绪态上体检与健康检查） ──
    "datasource_credential_ready": FeatureSwitchDef(
        "数据源凭据就绪",
        "声明数据源所需凭据，缺失时链路跳过并给出可读指引；体检与健康检查报告就绪状态（需凭据的源如 DataSinking 财报）",
        GROUP_MECHANISM,
        True,
        True,
    ),
    # ── 呈现与体验：量化指标（原 metrics_* 七项逐项开关，已合并为单一总开关）──
    # 七项指标始终全量计算，开关只表达「量化指标画像是否输出」：关闭即雷达图
    # 各轴转 "N/A"（含降级 3 轴路径）+ 熔断器暂停指标失败计数，指标之间无差异化
    # 生效面，逐项开关未换来逐项控制价值，故收敛为一项（面板 7 行 → 1 行）。
    "metrics_enabled": FeatureSwitchDef(
        "量化指标显示",
        "报告量化指标是否输出（雷达图各轴）；关闭即各轴显示 N/A、熔断器暂停指标失败计数（指标始终全量计算）",
        GROUP_PRESENTATION,
        True,
        True,
    ),
    # ── 机制与诊断：只读诊断（不改产物、不写文件，默认关的代价是环境出故障者看不到它） ──
    "doctor_check": FeatureSwitchDef(
        "系统自检上屏",
        "TUI 菜单 [T] 与 Web「系统自检」卡片可见性；CLI doctor 子命令不受本开关约束",
        GROUP_MECHANISM,
        True,
        False,
    ),
    # ── 机制与诊断：内部接缝（开关两态下报告产物逐源等价，保留为回退杠杆） ──
    "datasource_adapter": FeatureSwitchDef(
        "数据源适配契约",
        "行情域三源走三段式适配器（参数转译→抓取→映射到标准字段）；置 false 回退既有转换函数",
        GROUP_MECHANISM,
        True,
        False,
    ),
    # ── 分析增强与独立章节与回放（以下声明顺序即各组组内面板顺序）──
    "data_quality": FeatureSwitchDef(
        "数据质量仪表盘",
        "「数据源可用性矩阵」章渲染数据覆盖/时效/降级状态区块",
        GROUP_ANALYSIS,
        True,
        True,
    ),
    "industry_beta": FeatureSwitchDef(
        "行业Beta子表",
        "「风格与因子分析」章渲染行业 Beta 子表（行业暴露 + 回归敏感性）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "candidate_compare": FeatureSwitchDef(
        "候选基金比较子表",
        "「基金业绩分析」章渲染候选基金横向比较表（候选来自 comparison_candidates）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "cost_lots": FeatureSwitchDef(
        "成本流水",
        "汇总/市值/分类页签渲染成本分档 + XIRR + 分红累计（需持仓 Excel 含交易/分红流水）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "valuation_percentile": FeatureSwitchDef(
        "估值分位",
        "「资产穿透TOP10」章渲染估值分位列（真实历史 PE/PB 分位，无覆盖时回落价格分位代理）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "market_temperature": FeatureSwitchDef(
        "市场温度",
        "「投资分析汇总」章渲染市场温度刻度行（三因子合成；数据不足时该行静默省略）",
        GROUP_ANALYSIS,
        True,
        True,
    ),
    "financial_report_digest": FeatureSwitchDef(
        "持仓个股财报摘要",
        "新增独立章：A 股标的财报章节摘要（需 DataSinking key）",
        GROUP_STANDALONE,
        False,
        True,
    ),
    "market_sentiment": FeatureSwitchDef(
        "市场情绪与资金热点",
        "行动建议章内嵌块「市场情绪与持仓热点」：持仓/穿透标的当日上榜龙虎榜与进入连板梯队的事件行（需同花顺 key；零命中时写市场概览与说明行）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "financial_indicator": FeatureSwitchDef(
        "财务指标",
        "新增独立章：持仓 A 股基本面（指标 + 质量档 + 趋势 + 当前 PE/PB；需数据底座就绪）",
        GROUP_STANDALONE,
        False,
        True,
    ),
    "fund_purchase_limit": FeatureSwitchDef(
        "基金申购限购",
        "「持仓明细与分类」市值明细追加「申购状态」列（天天基金渠道口径，含日限/下一开放日；数据不可用时静默隐列）",
        GROUP_ANALYSIS,
        True,
        True,
    ),
    "cost_position": FeatureSwitchDef(
        "持仓成本区间位置",
        "「持仓明细与分类」市值明细追加「成本区间位置」列（每份成本相对近 20/260 交易日价格区间百分位，≈1 追涨嫌疑；行情缺失时静默隐列）",
        GROUP_ANALYSIS,
        True,
        True,
    ),
    "risk_adjusted_excess": FeatureSwitchDef(
        "风险调整超额",
        "走势章新增「风险调整超额」子块：滚动 1Y 超额曲线 + 年化 IR/跟踪误差 + 近 12/24 月跑赢基准胜率（需配置业绩基准，独立拉长取数窗口）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    "crisis_replay": FeatureSwitchDef(
        "危机回放",
        "危机区间标注升级为双层回放：组合侧窗口内危机穿越表现（区间收益） + 指数侧历史危机区间表现（收益/最大回撤，长窗指数日线）",
        GROUP_STANDALONE,
        False,
        True,
    ),
    "summary_highlights": FeatureSwitchDef(
        "本期要点与环比对照",
        "摘要区首屏执行摘要卡：关键指标环比行（总市值/总收益率/持仓数/集中度） + 本期关键变化 Top N（快照 diff 单源派生，无上期快照时整块隐藏）",
        GROUP_ANALYSIS,
        False,
        True,
    ),
    # ── 分析增强：投资方法框架（转正项：评分口径验证达成，已摘除实验身份、默认开；
    # 行动章内嵌评分卡区块，作用域属既有章内追加） ──
    "prosperity_framework": FeatureSwitchDef(
        "景气度框架诊断",
        "六维评分卡（景气方向/ROE 低位弹性/全球比较优势/流动性/集中度与周期拼接/业绩回撤印证）评估组合契合度，缺数据维度标记需核实",
        GROUP_ANALYSIS,
        True,
        True,
    ),
}

# ── 出厂默认值投影 ──────────────────────────────────────────
# 出厂默认值投影：``get_feature_defaults()`` 与兼容既有引用的取值表
_FEATURE_FLAGS_DEFAULT: dict[str, bool] = {flag: d.default for flag, d in feature_switch_registry.items()}

# ── 注册表查询 ──────────────────────────────────────────────


def switches_in_group(group: str) -> list[tuple[str, FeatureSwitchDef]]:
    """返回某分组下的开关声明 ``[(开关名, 声明), ...]``（顺序 = 注册表顺序）。

    面板渲染的唯一取数入口——渠道层据此分块，不自行筛选；实验清单取
    :func:`experimental_flags`（生命周期看字段、不看分组）。
    """
    return [(flag, d) for flag, d in feature_switch_registry.items() if d.group == group]


def experimental_flags() -> list[tuple[str, FeatureSwitchDef]]:
    """实验项清单 ``[(开关名, 声明), ...]``（顺序 = 注册表顺序）= ``experimental`` 为真者。

    生命周期判定的唯一来源——``--experiment`` 取值域、CLI 帮助清单与页脚实验
    自述均由此派生，与作用域分组无关。
    """
    return [(flag, d) for flag, d in feature_switch_registry.items() if d.experimental]


def is_experimental_switch(flag: str) -> bool:
    """判定开关是否为实验项（``experimental`` 字段；``--experiment`` 的取值域即此集合）。"""
    d = feature_switch_registry.get(flag)
    return d is not None and d.experimental


# ── 开关名解析（``--experiment`` / ``--feature``） ──────────

EXPERIMENT_ALL = "all"

# ``--feature NAME=VALUE`` 的取值词表（大小写不敏感）
_SWITCH_TRUE_TOKENS = frozenset({"on", "true", "1", "yes", "enable", "enabled"})
_SWITCH_FALSE_TOKENS = frozenset({"off", "false", "0", "no", "disable", "disabled"})


def _match_experiment(token: str) -> str | None:
    """按开关名（大小写不敏感）或显示名（精确）匹配单个实验功能。

    Returns:
        命中的开关名，未匹配到返回 None
    """
    lowered = token.lower()
    for flag, d in experimental_flags():
        if flag.lower() == lowered or d.label == token:
            return flag
    return None


def resolve_experiment_flags(names: list[str]) -> tuple[set[str], list[str]]:
    """将用户输入的实验功能名解析为开关名集合（注册表驱动）。

    接受三种写法（忽略首尾空白；开关名大小写不敏感）：
      - 开关名：``decision_reflection``
      - 显示名：``决策跨期反思闭环``
      - ``all``：全部实验功能

    Args:
        names: 用户输入的名称列表（空白项自动跳过）

    Returns:
        ``(命中的开关名集合, 未识别的原始名称列表)``；调用方据此决定
        是全部启用还是报错提示可用清单。
    """
    resolved: set[str] = set()
    unknown: list[str] = []
    for raw in names:
        token = (raw or "").strip()
        if not token:
            continue
        if token.lower() == EXPERIMENT_ALL:
            resolved.update(flag for flag, _d in experimental_flags())
            continue
        hit = _match_experiment(token)
        if hit is None:
            unknown.append(raw)
        else:
            resolved.add(hit)
    return resolved, unknown


def describe_experiment_flags() -> str:
    """返回实验功能清单的人类可读串（供 CLI 帮助与报错提示复用）。"""
    return "、".join(f"{flag}（{d.label}）" for flag, d in experimental_flags())


def describe_switches() -> str:
    """返回全部功能开关清单的人类可读串（``--feature`` 报错提示复用）。"""
    return "、".join(f"{flag}（{d.label}）" for flag, d in feature_switch_registry.items())


def resolve_switch_values(pairs: list[tuple[str, bool]] | None) -> list[tuple[str, bool]]:
    """把 ``--feature NAME=VALUE`` 解析结果收敛为待应用的覆写列表。

    Args:
        pairs: argparse 收集的 ``(开关名, 取值)`` 列表（可为 None）

    Returns:
        去重后的 ``(开关名, 取值)`` 列表，后者覆盖前者（同名重复时以最后一次为准）；
        输入为空时返回空列表。
    """
    merged: dict[str, bool] = {}
    for flag, value in pairs or []:
        merged[flag] = value
    return list(merged.items())


def parse_switch_override(token: str) -> tuple[str, bool]:
    """解析 ``--feature`` 的单个取值 ``NAME=VALUE``。

    取值在 argparse ``type`` 回调中即时校验——错误的开关名或取值当场报错并列出
    可选项，而不是等到运行中途静默无效。

    Args:
        token: 形如 ``module_quality_gate=on`` / ``doctor_check=off`` 的字符串

    Returns:
        ``(开关名, 取值)``

    Raises:
        ValueError: 缺少 ``=``、开关名未知、或取值不在词表内
    """
    name, sep, raw_value = token.partition("=")
    name = name.strip()
    if not sep or not name:
        raise ValueError("应为 NAME=VALUE 形式（如 module_quality_gate=on）")
    if name not in feature_switch_registry:
        raise ValueError(f"未知功能开关 '{name}'；可选: {describe_switches()}")

    value = raw_value.strip().lower()
    if value in _SWITCH_TRUE_TOKENS:
        return name, True
    if value in _SWITCH_FALSE_TOKENS:
        return name, False
    raise ValueError(f"开关 '{name}' 的取值 '{raw_value}' 不可识别；可选: on / off")


def enabled_experimental_features() -> list[tuple[str, str]]:
    """返回当前已启用、且**可能改变报告产物**的实验功能 ``[(开关名, 显示名), ...]``。

    报告层用它在**产物自身上**标注生成条件（HTML 页脚 / Excel 落点）——报告是
    可脱离本机流转的文件，读者须能判断内容是否为非默认开关下的产物。

    只列注册表中 ``affects_report`` 为真者：只改交互入口可见性的开关不改报告
    任何字节，列进自述会让读者推断内容受其影响。清单取自 :func:`experimental_flags`
    （生命周期看 ``experimental`` 字段），注册表仍是唯一来源；TUI 菜单 [S] 与
    Web 配置面板渲染的是**全部开关**（含不影响产物者与非实验项），两者用途不同。

    Returns:
        已启用项的 ``(开关名, 显示名)`` 列表，按注册表顺序；无启用项时返回空列表。
    """
    return [(flag, d.label) for flag, d in experimental_flags() if d.affects_report and is_feature_enabled(flag)]


def log_experimental_features() -> None:
    """如果已启用实验性功能，在日志中输出醒目标记，说明具体开启了什么功能。

    唯一调用点为报告入口 ``report/orchestrator.generate_report``（在配置初始化
    之后），故 TUI / CLI / Web 三条入口在生成报告时均会提示——「本次报告受哪些
    实验功能影响」正是需要看到这条信息的时刻。
    级别取 ``INFO``：横幅是生成条件提示而非错误，用 ``ERROR`` 会污染错误统计
    （实测一次运行 68 条 ERROR 中 65 条为本横幅，真错误被淹没）；醒目由
    ``log_reader`` 的装饰横幅标记与报告产物自身的实验标注承担。
    """
    enabled = enabled_experimental_features()
    if not enabled:
        return

    import logging

    logger = logging.getLogger("invest")
    sep = "=" * 48

    logger.info(sep)
    logger.info("  ⚗ 实验性功能已开启！")
    logger.info(sep)
    for flag, name in enabled:
        logger.info("  ⚗ %s — %s", name, feature_switch_registry[flag].desc)
    logger.info(sep)

    # 使用统计（尽力而为，绝不影响报告主链路）：每次生成报告时记录各实验开关
    # 的累计启用次数与最近启用日期，供「转正 / 撤销」决策用客观数据支撑。
    try:
        from src.python.core.experiment_stats import record_experiment_usage

        record_experiment_usage([flag for flag, _name in enabled])
    except Exception:  # noqa: BLE001
        logger.warning("[features] 实验功能使用统计记录失败（不影响报告生成）", exc_info=True)


__all__ = [
    "EXPERIMENT_ALL",
    "FEATURE_FLAGS",
    "GROUP_ANALYSIS",
    "GROUP_LABELS",
    "GROUP_MECHANISM",
    "GROUP_ORDER",
    "GROUP_PRESENTATION",
    "GROUP_STANDALONE",
    "FeatureSwitchDef",
    "describe_experiment_flags",
    "describe_switches",
    "enabled_experimental_features",
    "experimental_flags",
    "feature_switch_registry",
    "get_feature_defaults",
    "is_experimental_switch",
    "is_feature_enabled",
    "log_experimental_features",
    "parse_switch_override",
    "resolve_experiment_flags",
    "resolve_switch_values",
    "set_feature_enabled",
    "switches_in_group",
    "load_feature_overrides",
    "save_feature_overrides",
    "reset_feature_flags",
]

# ── 运行时状态 ──────────────────────────────────────────────
# 合并默认值 + 外部覆写后的最终生效值

FEATURE_FLAGS: dict[str, bool] = dict(_FEATURE_FLAGS_DEFAULT)
_FEATURES_LOCK = threading.Lock()


def get_feature_defaults() -> dict[str, bool]:
    """返回功能开关的出厂默认值（不受运行时覆写影响）。"""
    return dict(_FEATURE_FLAGS_DEFAULT)


def is_feature_enabled(flag_name: str) -> bool:
    """检查指定功能开关是否启用。

    Args:
        flag_name: 功能开关名称（如 "llm_global_macro"）

    Returns:
        True 表示功能启用，False 表示功能禁用
    """
    if flag_name not in FEATURE_FLAGS:
        logger.debug("[features] 未知功能开关 '%s'，视为关闭", flag_name)
        return False
    return FEATURE_FLAGS[flag_name]


def set_feature_enabled(flag_name: str, enabled: bool) -> None:
    """运行时切换功能开关状态（不持久化）。

    持久化覆写请调用 save_feature_overrides()。

    Args:
        flag_name: 功能开关名称
        enabled: True 启用 / False 禁用
    """
    if flag_name not in FEATURE_FLAGS:
        logger.warning("[features] 试图设置未知功能开关 '%s'，忽略", flag_name)
        return
    old = FEATURE_FLAGS[flag_name]
    FEATURE_FLAGS[flag_name] = enabled
    if old != enabled:
        logger.info("[features] 功能开关 '%s': %s → %s", flag_name, old, enabled)


def load_feature_overrides() -> None:
    """从 features.json 加载覆写配置，合并到 FEATURE_FLAGS。

    文件中仅需列出需要覆写的开关键值对，未列出的保持默认值。

    JSON 格式：
      {
        "metrics_enabled": true,
        "data_quality": false
      }
    """
    if not os.path.exists(FEATURES_FILE):
        return
    try:
        with open(FEATURES_FILE, encoding="utf-8") as f:
            overrides = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[features] 加载覆写文件失败: %s", e)
        return

    if not isinstance(overrides, dict):
        logger.warning("[features] 覆写文件格式异常（应为 JSON object），忽略")
        return

    valid_count = 0
    changed = 0
    unknown: list[str] = []
    with _FEATURES_LOCK:
        for flag_name, value in overrides.items():
            if isinstance(value, bool) and flag_name in FEATURE_FLAGS:
                changed += FEATURE_FLAGS[flag_name] != value
                FEATURE_FLAGS[flag_name] = value
                valid_count += 1
            elif isinstance(value, bool):
                unknown.append(flag_name)
                FEATURE_FLAGS[flag_name] = value
                valid_count += 1
                changed += 1
            else:
                logger.warning("[features] 覆写 '%s' 值应为 bool，忽略", flag_name)

    # 无消费者开关一次告警（多为陈旧开关或拼写错误）：这类键在本版本不驱动任何
    # 行为，用户照文档配置后会毫无效果，必须让其可见。收集后合并成一条——逐键
    # 打印会在每次启动刷屏，而 features.json 在模块导入时就会加载一次。
    if unknown:
        logger.warning(
            "[features] features.json 含 %d 项无消费者的开关，配置后不产生任何效果"
            "（请核对拼写，或查阅 how-to-config 的功能开关键表）: %s",
            len(unknown),
            "、".join(sorted(unknown)),
        )

    if not valid_count:
        return
    # 只有确实改变了取值才报 INFO：本模块在导入时自动加载一次，调用方（如 CLI
    # 早返回命令的应用开关入口）可能再显式加载一次，重复打印同一条日志是噪声。
    if changed:
        logger.info("[features] 已加载 %d 项功能开关覆写", valid_count)
    else:
        logger.debug("[features] 覆写已生效（%d 项，取值无变化）", valid_count)


def save_feature_overrides(overrides: dict[str, bool], merge: bool = True) -> None:
    """保存功能开关覆写到 features.json。

    Args:
        overrides: {flag_name: enabled} 字典
        merge: True = 合并到现有覆写（覆盖同名键），False = 完全替换
    """
    existing: dict[str, Any] = {}
    if merge and os.path.exists(FEATURES_FILE):
        try:
            with open(FEATURES_FILE, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing.update(overrides)

    # 只保留值为 bool 的条目
    cleaned = {k: v for k, v in existing.items() if isinstance(v, bool)}

    # 落盘委托 core/atomic_write（唯一原语，mkstemp + os.replace）。失败由原语记日志
    # 并返回 False——开关覆写属尽力持久化：写不进盘不影响本次运行（内存态随后同步），
    # 也不应因此中断调用链。
    if write_json_atomic(
        FEATURES_FILE,
        cleaned,
        prefix=".features_",
        log_tag="features",
        noun="功能开关覆写",
    ):
        logger.info("[features] 已保存 %d 项功能开关覆写", len(cleaned))

    # 同步运行时状态
    for flag_name, enabled in cleaned.items():
        FEATURE_FLAGS[flag_name] = enabled


def reset_feature_flags() -> None:
    """重置所有功能开关为默认值（运行时状态，不影响持久化文件）。"""
    with _FEATURES_LOCK:
        FEATURE_FLAGS.clear()
        FEATURE_FLAGS.update(_FEATURE_FLAGS_DEFAULT)
    logger.debug("[features] 功能开关已重置为默认值")


# 模块导入时自动加载覆写
load_feature_overrides()
