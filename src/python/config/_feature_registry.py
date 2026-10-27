"""功能开关注册表与定义（唯一事实来源）：分组常量、``FeatureSwitchDef``、注册表条目、
纯注册表视图（分组过滤 / 实验项清单 / 默认值派生）。

从 :mod:`config.features` 拆出——注册表逐开关增长（每项约十行）是文件膨胀的主因，
而运行时状态（features.json 覆写、读写、迁移、日志）仍留在原模块；单向依赖：
运行时 → 注册表。原模块 re-export 本模块符号，既有导入面不变。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("invest")


GROUP_PORTFOLIO = "portfolio"
GROUP_MARKET = "market"
GROUP_FUND_STYLE = "fund_style"
GROUP_EVENT_SUMMARY = "event_summary"
GROUP_MECHANISM = "mechanism"
GROUP_STANDALONE = "standalone"
GROUP_CHAPTER_OPTIONS = "chapter_options"


GROUP_LABELS: dict[str, str] = {
    GROUP_PORTFOLIO: "💼 持仓与交易（成本、申赎状态、成本收益、风险调整）",
    GROUP_MARKET: "📈 市场与估值（温度、估值分位、景气度、危机回放）",
    GROUP_FUND_STYLE: "🧩 基金与风格（候选比较、行业 Beta、因子目录）",
    GROUP_EVENT_SUMMARY: "📰 事件与摘要（事件窗、情绪热点、本期要点）",
    GROUP_MECHANISM: "⚙ 机制与质量（提示词注入 / 报告追问 / 输出评级）",
    GROUP_STANDALONE: "📑 独立章节与回放（新增整页签或多期回放）",
    GROUP_CHAPTER_OPTIONS: "🧩 章节内选项（由 [C] 作为章节子项渲染）",
}

GROUP_ORDER: tuple[str, ...] = (
    GROUP_PORTFOLIO,
    GROUP_MARKET,
    GROUP_FUND_STYLE,
    GROUP_EVENT_SUMMARY,
    GROUP_MECHANISM,
    GROUP_STANDALONE,
    GROUP_CHAPTER_OPTIONS,
)

DOMAIN_REPORT_CONTENT = "report_content"
DOMAIN_PRESENTATION_MECHANISM = "presentation_mechanism"
DOMAIN_DATA_AND_ROUTES = "data_and_routes"
DOMAIN_LLM_RUN = "llm_run"
DOMAIN_OPS_DIAGNOSTICS = "ops_diagnostics"

DOMAIN_LABELS: dict[str, str] = {
    DOMAIN_REPORT_CONTENT: "报告内容",
    DOMAIN_PRESENTATION_MECHANISM: "呈现与机制",
    DOMAIN_DATA_AND_ROUTES: "数据与线路",
    DOMAIN_LLM_RUN: "LLM 运行",
    DOMAIN_OPS_DIAGNOSTICS: "运行与诊断",
}

DOMAIN_HINTS: dict[str, str] = {
    DOMAIN_REPORT_CONTENT: "改这里会改变报告里出现什么：哪些章节出现、章节内多出什么",
    DOMAIN_PRESENTATION_MECHANISM: "只改呈现口径、匿名化与机制接缝：内容主体不变或仅影响入口显隐",
    DOMAIN_DATA_AND_ROUTES: "数据从哪读、跟什么基准比、LLM 走哪条线路",
    DOMAIN_LLM_RUN: "LLM 调用的运行约束（并发 / 重试 / 预算）",
    DOMAIN_OPS_DIAGNOSTICS: "日志写盘与控制台输出、查看器默认筛选",
}

DOMAIN_ORDER: tuple[str, ...] = (
    DOMAIN_REPORT_CONTENT,
    DOMAIN_PRESENTATION_MECHANISM,
    DOMAIN_DATA_AND_ROUTES,
    DOMAIN_LLM_RUN,
    DOMAIN_OPS_DIAGNOSTICS,
)

GROUP_DOMAIN: dict[str, str] = {
    GROUP_PORTFOLIO: DOMAIN_REPORT_CONTENT,
    GROUP_MARKET: DOMAIN_REPORT_CONTENT,
    GROUP_FUND_STYLE: DOMAIN_REPORT_CONTENT,
    GROUP_EVENT_SUMMARY: DOMAIN_REPORT_CONTENT,
    GROUP_MECHANISM: DOMAIN_PRESENTATION_MECHANISM,
    GROUP_STANDALONE: DOMAIN_REPORT_CONTENT,
    GROUP_CHAPTER_OPTIONS: DOMAIN_REPORT_CONTENT,
}

PANEL_GROUPS: dict[str, tuple[str, ...]] = {
    "[S]": (
        GROUP_PORTFOLIO,
        GROUP_MARKET,
        GROUP_FUND_STYLE,
        GROUP_EVENT_SUMMARY,
        GROUP_MECHANISM,
    ),
    "[C]": (GROUP_STANDALONE, GROUP_CHAPTER_OPTIONS),
}


@dataclass(frozen=True)
class FeatureSwitchDef:
    """单条功能开关声明。

    Attributes:
        label: 显示名（TUI 面板行名 / Web 配置面板标签，服务端同源下发）
        desc: 一句话说明（CLI 报错提示、控制台横幅、文档）
        group: 作用域分组（``GROUP_PRESENTATION`` / ``GROUP_FUND_STYLE`` /
            ``GROUP_STANDALONE`` / ``GROUP_MECHANISM``）
        default: 出厂默认值（``features.json`` 未覆写时的取值）
        affects_report: 开启后报告产物内容是否可能不同——决定它是否进入产物自述
        experimental: 生命周期为实验项（``--experiment`` 取值域即此字段为真者；
            末位默认 False，仅实验项显式标注）
        needs_hint: 说明是否默认以副行展示（默认 False = 常识项，悬停读取）
    """

    label: str
    desc: str
    group: str
    default: bool
    affects_report: bool
    experimental: bool = False
    needs_hint: bool = False


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
        "报告页内针对本期报告的会话式追问（零新增取数、轮数上限；回答由 LLM 生成、按量计费，用量独立记账）",
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
    "llm_debate_procon": FeatureSwitchDef(
        "辩论-正反辩论", "三段式(白脸→黑脸→综合)", GROUP_CHAPTER_OPTIONS, False, True
    ),
    # 辩论增强：条件推理（与正反辩论相邻；默认开不变，情景段仍在既有调用内产出）
    "llm_debate_conditional": FeatureSwitchDef(
        "辩论-条件推理", "情景化分析(涨/跌/震荡)", GROUP_CHAPTER_OPTIONS, True, True
    ),
    # 因子目录（已转正，2026-10-11；门槛评测三指标过审）
    "factor_catalog": FeatureSwitchDef(
        "因子目录",
        "25 因子五来源族横截面信号入账与风格与因子分析区「因子目录」区块",
        GROUP_FUND_STYLE,
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
    # ── 分析增强：事件窗对照（区块类转正项：实验身份已摘除、default 保持 False）──
    "event_window_impact": FeatureSwitchDef(
        "事件窗对照",
        "新闻事件发生后 ±5 个交易日的品种表现：收益/超额收益与文本极性同表对照，分歧例进 LLM 分析章",
        GROUP_EVENT_SUMMARY,
        False,
        True,
    ),
    # ── 机制与诊断：LLM 输出增强（只读侧注入，不增调用次数、不写盘） ──
    "module_quality_gate": FeatureSwitchDef(
        "LLM 输出评级",
        "按完整性/一致性给各 LLM 模块输出评 A~F 级，低评级随内容头部标注质量提示（不阻断不重试）",
        GROUP_MECHANISM,
        True,
        True,
    ),
    # ── 机制与诊断：只读诊断（不改产物、不写文件，默认关的代价是环境出故障者看不到它） ──
    # ── 分析增强与独立章节与回放（以下声明顺序即各组组内面板顺序）──
    "industry_beta": FeatureSwitchDef(
        "行业Beta子表",
        "「风格与因子分析」章渲染行业 Beta 子表（行业暴露 + 回归敏感性）",
        GROUP_FUND_STYLE,
        False,
        True,
    ),
    "candidate_compare": FeatureSwitchDef(
        "候选基金比较子表",
        "「基金业绩分析」章渲染候选基金横向比较表（候选来自 comparison_candidates）",
        GROUP_FUND_STYLE,
        False,
        True,
    ),
    "cost_lots": FeatureSwitchDef(
        "成本流水",
        "汇总/市值/分类页签渲染成本分档 + XIRR + 分红累计（需持仓 Excel 含交易/分红流水）",
        GROUP_PORTFOLIO,
        False,
        True,
    ),
    "valuation_percentile": FeatureSwitchDef(
        "估值分位",
        "「资产穿透TOP10」章渲染估值分位列（有历史 PE/PB 数据时用真实分位，没有时用价格分位近似）",
        GROUP_MARKET,
        False,
        True,
    ),
    "market_temperature": FeatureSwitchDef(
        "市场温度",
        "「投资分析汇总」章渲染市场温度刻度行（三因子合成；数据不足时该行静默省略）",
        GROUP_MARKET,
        True,
        True,
    ),
    "stock_fundamentals": FeatureSwitchDef(
        "个股基本面",
        "新增独立章：持仓个股基本面（财务指标 + 质量档/趋势/当前 PE-PB 与 A 股财报章节摘要两块；需数据底座与 DataSinking key）",
        GROUP_STANDALONE,
        False,
        True,
    ),
    "market_sentiment": FeatureSwitchDef(
        "市场情绪与资金热点",
        "行动建议章内嵌块「市场情绪与持仓热点」：持仓/穿透标的当日上榜龙虎榜与进入连板梯队的事件行（需同花顺 key；零命中时写市场概览与说明行）",
        GROUP_EVENT_SUMMARY,
        False,
        True,
    ),
    "fund_purchase_limit": FeatureSwitchDef(
        "基金申购限购",
        "「持仓明细与分类」市值明细追加「申购状态」列（天天基金渠道口径，含日限/下一开放日；数据不可用时静默隐列）",
        GROUP_PORTFOLIO,
        True,
        True,
    ),
    "cost_position": FeatureSwitchDef(
        "持仓成本区间位置",
        "「持仓明细与分类」市值明细追加「成本区间位置」列（每份成本相对近 20/260 交易日价格区间百分位，≈1 追涨嫌疑；行情缺失时静默隐列）",
        GROUP_PORTFOLIO,
        True,
        True,
    ),
    "risk_adjusted_excess": FeatureSwitchDef(
        "风险调整超额",
        "走势章新增「风险调整超额」子块：滚动 1Y 超额曲线 + 年化 IR/跟踪误差 + 近 12/24 月跑赢基准胜率（需配置业绩基准，独立拉长取数窗口）",
        GROUP_PORTFOLIO,
        False,
        True,
    ),
    "crisis_replay": FeatureSwitchDef(
        "危机回放",
        "危机区间标注升级为双层回放：组合侧窗口内危机穿越表现（区间收益） + 指数侧历史危机区间表现（收益/最大回撤，长窗指数日线）",
        GROUP_MARKET,
        False,
        True,
    ),
    "summary_highlights": FeatureSwitchDef(
        "首页执行摘要卡",
        "摘要区首屏执行摘要卡：关键指标环比行（总市值/总收益率/持仓数/集中度） + 本期关键变化 Top N（快照 diff 单源派生，无上期快照时整块隐藏）",
        GROUP_EVENT_SUMMARY,
        False,
        True,
    ),
    # ── 分析增强：投资方法框架（转正项：评分口径验证达成，已摘除实验身份、默认开；
    # 行动章内嵌评分卡区块，作用域属既有章内追加） ──
    "prosperity_framework": FeatureSwitchDef(
        "景气度框架诊断",
        "评估持仓组合与当前景气的匹配度：六维评分卡（景气方向/ROE 低位弹性/全球比较优势/流动性/集中度与周期拼接/业绩回撤印证），缺数据维度标记需核实",
        GROUP_MARKET,
        True,
        True,
    ),
}


_FEATURE_FLAGS_DEFAULT: dict[str, bool] = {flag: d.default for flag, d in feature_switch_registry.items()}


def switches_in_group(group: str) -> list[tuple[str, FeatureSwitchDef]]:
    """返回某分组下的开关声明 ``[(开关名, 声明), ...]``（顺序 = 注册表顺序）。

    面板渲染的唯一取数入口——渠道层据此分块，不自行筛选；实验清单取
    :func:`experimental_flags`（生命周期看字段、不看分组）。
    """
    return [(flag, d) for flag, d in feature_switch_registry.items() if d.group == group]


def panel_option_numbers(panel: str) -> tuple[tuple[int, str, FeatureSwitchDef], ...]:
    """按面板的组序派生编号：``((1, 开关名, 声明), (2, ...), ...)``（1 起连续）。

    面板编号的唯一派生入口——``[S]`` 只呈现 ``PANEL_GROUPS["[S]"]`` 的五组
    （LLM 章节与独立章节在 ``[C]``）；增删开关后编号自动重排，渠道层与测试都
    不得写死数字。
    """
    numbered: list[tuple[int, str, FeatureSwitchDef]] = []
    for group in PANEL_GROUPS.get(panel, ()):
        for flag, definition in switches_in_group(group):
            numbered.append((len(numbered) + 1, flag, definition))
    return tuple(numbered)


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


EXPERIMENT_ALL = "all"
