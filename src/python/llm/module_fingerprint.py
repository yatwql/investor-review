"""LLM 模块缓存指纹的唯一事实来源 — 预检侧与写侧同源。

模块缓存键统一为 ``CACHE_PREFIX_LLM + f"{模块}_{指纹}"``，两侧各自拼接：

  - **预检侧**：``generators_orchestrator._compute_module_cache_info()``（判断能否跳过生成）
  - **写侧**：``generators.py`` 各生成函数的 ``_fingerprint`` 闭包（经 ``skeleton.py``
    的 ``_run_standard_mode`` 组装同一形态的键）

风险：两侧靠「注释声明同调」维护时，每逢新增影响提示词或内容的输入
（风险信号摘要、信号预消化后缀、决策教训后缀、辩论增强后缀…），都要在两处手工
各改一遍。任一侧漏改即产生**读写键永不同源**——预检 read 落空、每次报告全量派发，
且不报错、只表现为静默的性能与日志噪声（如 ``history_data`` 与辩论增强后缀两处
历史偏差）。本模块把每个模块的指纹构造收敛为**唯一函数**，两侧都调用它：
新增输入只需改一处，同源由结构保证，而非靠纪律与复查维持。

约定：
  - 四个 LLM 模块（global_macro / expert_review / health_check / penetration_deep）
    的指纹均由 ``MODULE_FINGERPRINT_BUILDERS`` 提供；两侧不得再自行拼接模块指纹。
  - ``ModuleFingerprintInputs`` 是两侧都持有的输入闭包；``history_data`` 的风险
    信号摘要对三模块统一参与哈希（口径一致优先于逐模块精简——多算只带来无害的
    过度失效，漏算则导致内容与键脱钩的陈旧缓存）。
  - **覆盖以「提示词是否真的含该段」为准**：进了提示词的内容必须进指纹
    （``competitive_context`` / ``metrics`` / ``data_quality_text`` /
    ``purchase_block`` / ``pipeline_data`` 派生的【环比变化】【数据质量降级】
    两段），不进提示词的段落不并入（纯成本失效）。
  - **生成参数同样进键**：模块的温度 / 输出上限 / 思考开关、预算与强度由
    ``generation_params_suffix()`` 统一并入；``cache`` 等与生成无关的项不参与，
    避免无谓失效。``get_llm_config()`` 不可用时后缀为空（不使存量缓存整体失效）。
  - **一次渲染、两侧共享同一实例**：``competitive_context`` 与
    ``data_quality_text`` 由调用方（``generate_all_llm``）渲染一次后同时交给预检侧
    与写侧，两边不得各自渲染——两次渲染会让「进键的文本」与「进提示词的文本」
    退化为靠纪律对齐。``purchase_block`` 同理：契约构建期（report 侧）渲染一次，
    两侧只读透传；且**仅在非空时条件并入**——空串不追加 part（无条件拼接会把
    空串与分隔符写进哈希输入，「块空键不变」静默失效、存量缓存无谓全量失效）。
  - 返回值为**指纹本体**（不含 ``CACHE_PREFIX_LLM + 模块名`` 前缀），缓存键由两侧
    按同一形态自行拼装。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.python.config.features import is_feature_enabled
from src.python.llm.fact_checker._constants import FACT_CHECK_RULES_VERSION
from src.python.core import decision_ledger
from src.python.core import signal_ledger
from src.python.llm.fingerprint import (
    build_llm_fingerprint,
    compute_fingerprint,
    extract_stable_categories,
    extract_stable_holdings,
    extract_stable_penetration,
    risk_signals_of,
)
from src.python.llm.prompts_action import scenario_mandate_cache_suffix
from src.python.llm.prompts_signals import _signal_digest_cache_suffix
from src.python.llm.rate_caliber import PROMPT_SCHEMA_VERSION

__all__ = [
    "ModuleFingerprintInputs",
    "market_bucket_cache_suffix",
    "debate_feature_cache_suffix",
    "fingerprint_components",
    "diff_fingerprint_components",
    "debate_procon_fingerprint",
    "debate_synthesis_fingerprint",
    "global_macro_fingerprint",
    "expert_review_fingerprint",
    "health_check_fingerprint",
    "penetration_deep_fingerprint",
    "self_review_fingerprint",
    "self_review_fingerprint_parts",
    "MODULE_FINGERPRINT_BUILDERS",
]


@dataclass(frozen=True)
class ModuleFingerprintInputs:
    """LLM 模块指纹的输入闭包 — 预检侧与写侧共同持有的要素。

    两侧调用点都持有同一组数据（同一次报告生成的参数），故以同一对象喂入同一
    构造器即可保证逐字节相同的哈希输入。

    Attributes:
        total_mv: 持仓总市值
        total_cost: 持仓总成本
        total_profit: 累计盈亏
        total_today_profit: 本日盈亏
        holdings_details: 持仓明细（指纹仅取 name/code/cost 稳定字段）
        penetrated_assets: 穿透 TOP10 资产列表
        categories: 分类汇总
        history_data: 组合历史走势数据（仅取 key 风险信号摘要入哈希）
        pipeline_data: 管线上下文（供信号预消化后缀计算）
        a_indices: A 股指数行情（仅 global_macro 使用）
        us_indices: 美股指数行情（仅 global_macro 使用）
        competitive_context: **已渲染**的竞争语境文本块，由调用方渲染一次后
            与提示词共享**同一实例**（仅提示词含该段的模块使用）
        metrics: 量化指标字典（指标表 / 情景分析 / 风格一致性的共同来源，
            仅 expert_review 使用）
        data_quality_text: **已渲染**的数据质量详细状态文本块，由调用方渲染一次后
            与提示词共享**同一实例**（仅提示词含该段的模块使用——目前仅
            health_check）
        purchase_block: **已渲染**的申购限购约束块（契约字段 ``constraint_block``，
            经统一 prompt 附录进入各分析章提示词）；仅非空时条件并入哈希
            （空串不追加 part，见模块 docstring 纪律）
        holding_change_block: **已渲染**的持仓变动复盘提示词块（契约字段
            ``prompt_block``，同样经统一 prompt 附录进入提示词）；仅非空时条件
            并入哈希（空串不追加 part，键与引入前逐字节一致）
        event_impact_block: **已渲染**的事件窗分歧例块（契约字段 ``prompt_block``，
            同样经统一 prompt 附录进入提示词）；仅非空时条件并入哈希
            （空串不追加 part，键与引入前逐字节一致）
        schedule_replay_block: **已渲染**的调仓纪律回放引用块（契约字段
            ``prompt_block``，同样经统一 prompt 附录进入提示词）；仅非空时条件
            并入哈希（空串不追加 part，键与引入前逐字节一致）
    """

    total_mv: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    total_today_profit: float = 0.0
    holdings_details: list[dict] | None = None
    penetrated_assets: list[dict] | None = None
    categories: dict | None = None
    history_data: dict | None = None
    pipeline_data: dict | None = None
    a_indices: dict | None = None
    us_indices: dict | None = None
    competitive_context: str = ""
    metrics: dict | None = None
    data_quality_text: str = ""
    purchase_block: str = ""
    holding_change_block: str = ""
    event_impact_block: str = ""
    schedule_replay_block: str = ""


def debate_feature_cache_suffix() -> str:
    """辩论增强（条件推理）的缓存指纹后缀。

    取启用模式的代号字母（conditional=c）。集中度问答段已内建于辩论流程
    （阈值触发、不再受开关控制），属常量不进键。后缀保证相同组合产生相同
    后缀、不同组合不串扰。非辩论模式下该增强会改写 expert_review 的提示词
    （追加情景分析段），故后缀必须参与 expert_review 指纹——否则同一持仓在
    开关切换前后会命中同一份缓存。

    Returns:
        空字符串（未启用）或 "_c" 后缀。
    """
    _parts: list[str] = []
    if is_feature_enabled("llm_debate_conditional"):
        _parts.append("c")  # conditional
    return "_" + "".join(sorted(_parts)) if _parts else ""


def _pipeline_block_cache_suffix(pipeline_data: dict | None) -> str:
    """``pipeline_data`` 注入复盘类提示词的正文段（环比差异 / 数据质量降级）指纹后缀。

    复盘与辩论提示词都会带上【环比变化】【数据质量降级】两段（构建器
    ``_build_difpipeline_data_block`` / ``_build_data_degradation_block``），
    但这两段若不参与指纹——持仓未动而降级事件集变化时键不变，预检命中旧键，
    报告继续陈述「某数据源不可用」（或漏报新故障），且不报错。

    与 ``_signal_digest_cache_suffix`` 同法：调用**提示词侧同一构建器**取文本再
    哈希，故「进键的文本」与「进提示词的文本」由同一段代码产出，不靠纪律对齐。
    两段皆空（无环比数据、无降级事件）→ ``""``，键与未注入时一致，不误伤旧缓存。

    Args:
        pipeline_data: 报告管线数据契约。
    """
    # 延迟导入：prompts_core 属提示词层，模块级导入会与 llm 包初始化形成环。
    from src.python.llm.prompts_core import (
        _build_data_degradation_block,
        _build_difpipeline_data_block,
    )

    _blocks = [
        _build_difpipeline_data_block(pipeline_data),
        _build_data_degradation_block(pipeline_data),
    ]
    _block = "\n".join(b for b in _blocks if b)
    if not _block:
        return ""
    return "_" + compute_fingerprint(_block)


def _pipeline_blocks_text(pipeline_data: dict | None) -> str:
    """环比块 + 降级块的渲染文本（与正式指纹同一渲染路径）。"""
    from src.python.llm.prompts_core import (
        _build_data_degradation_block,
        _build_difpipeline_data_block,
    )

    blocks = [_build_difpipeline_data_block(pipeline_data), _build_data_degradation_block(pipeline_data)]
    return "\n".join(block for block in blocks if block)


def fingerprint_components(inputs: "ModuleFingerprintInputs") -> dict[str, str]:
    """指纹**组件级**哈希（只读诊断，不参与缓存键）。

    用途：连续两次同数据报告仍 miss 时，回答「到底哪一块变了」。返回的每项都是
    该组件单独哈希后的短值；把两次结果并排比即可定位变化源，不必再凭猜测改指纹。

    口径与正式指纹一致——同一份输入、同一 ``compute_fingerprint``，只是分组更细。
    调用方应仅在设计/排障路径按需调用（正式路径不计算，避免额外哈希开销）。
    """
    ledger_blocks: dict[str, str] = {}
    if decision_ledger.is_active():
        ledger_blocks["decision_lessons"] = decision_ledger.lessons_cache_suffix()
    ledger_blocks["signal_summary"] = signal_ledger.summary_cache_suffix()
    return {
        "totals": compute_fingerprint(
            inputs.total_mv,
            inputs.total_cost,
            inputs.total_profit,
            inputs.total_today_profit,
        ),
        "holdings": compute_fingerprint(extract_stable_holdings(inputs.holdings_details)),
        "penetration": compute_fingerprint(extract_stable_penetration(inputs.penetrated_assets)),
        "penetration_full": compute_fingerprint(extract_stable_penetration(inputs.penetrated_assets, full=True)),
        "categories": compute_fingerprint(inputs.categories),
        # 与正式指纹同口径：只哈希风险信号子集，不含 bars 等载荷
        "history_risk": compute_fingerprint(risk_signals_of(inputs.history_data)),
        "a_indices": compute_fingerprint(inputs.a_indices),
        "us_indices": compute_fingerprint(inputs.us_indices),
        "competitive_context": compute_fingerprint(inputs.competitive_context),
        "metrics": compute_fingerprint(inputs.metrics),
        "data_quality": compute_fingerprint(inputs.data_quality_text),
        "purchase_block": compute_fingerprint(inputs.purchase_block),
        "holding_change_block": compute_fingerprint(inputs.holding_change_block),
        "event_impact_block": compute_fingerprint(inputs.event_impact_block),
        "schedule_replay_block": compute_fingerprint(inputs.schedule_replay_block),
        # 与生产指纹同口径：哈希的是**渲染后的提示词文本**，不是契约 dict
        # （契约含 snapshot_count 等展示字段，直接哈希会误报「组件变化」）
        "pipeline_blocks": compute_fingerprint(_pipeline_blocks_text(inputs.pipeline_data)),
        "ledger_blocks": compute_fingerprint(ledger_blocks),
        "generation_params": compute_fingerprint(
            *[
                generation_params_suffix(module)
                for module in ("global_macro", "expert_review", "health_check", "penetration_deep")
            ]
        ),
    }


def diff_fingerprint_components(previous: dict[str, str] | None, current: dict[str, str]) -> list[str]:
    """比较两次组件哈希，返回**值发生变化**的组件名（升序）。

    用于连续报告排障：只报告真实变化的组件，避免把「缓存未命中」笼统归因于
    「指纹算法有问题」。无上次记录（``None``/空）时返回空列表。
    """
    if not previous:
        return []
    return sorted(key for key in current if previous.get(key) != current.get(key))


def generation_params_suffix(module: str) -> str:
    """模块级生成参数摘要（温度 / 输出上限 / 思考开关、预算、强度 / 模型 / 精简模式 / 自定义提示词）→ 指纹后缀。

    只并入会改变模型输出的参数：``cache`` 等与生成无关的项不参与，避免无谓失效。
    预检侧与写侧都调用同一个模块指纹构造器，故两侧天然同源。

    **后三项只在非默认值时追加**（模型覆写 / 精简模式 / 自定义提示词）：它们都直接
    改写系统提示词或调用目标，不进键就会在用户改配置后静默复用旧结论；而全为默认时
    不追加任何 part，使存量缓存键逐字节不变（不因本约束整体失效）。

    ``get_llm_config()`` 不可用（无凭据/未初始化）时返回空串——键与引入前一致，
    不因读取失败使存量缓存整体失效。
    """
    from src.python.config import get_llm_config

    config = get_llm_config()
    if not config:
        return ""
    parts = [
        f"t={config.get(f'temperature_{module}')}",
        f"mt={config.get(f'max_tokens_{module}')}",
        f"th={1 if config.get(f'thinking_enabled_{module}') else 0}",
        f"tb={config.get(f'thinking_budget_{module}')}",
        f"te={config.get(f'reasoning_effort_{module}')}",
    ]
    if config.get(f"model_{module}"):
        parts.append(f"m={config.get(f'model_{module}')}")
    if config.get(f"output_brief_{module}"):
        parts.append("ob=1")
    _override = config.get(f"system_prompt_{module}")
    if _override:
        parts.append("sp=" + compute_fingerprint(_override))
    return "_" + compute_fingerprint(*parts)


def market_bucket_cache_suffix() -> str:
    """行情口径桶后缀 —— 进四个基础模块与辩论键的指纹。

    为什么要进键：收盘档（上一交易日收盘 / 上午收盘 / 当日收盘）之间行情快照不同，
    同一份持仓在两档下的输入并不等价；进键让「档变了」显式换键，而不是靠块文本
    逐字节比较去猜。盘中档虽按策略不复用，键里仍带档标识——否则盘中写下的缓存
    会被收盘档读到（键相同、内容却是盘中口径）。
    """
    from src.python.core.market_hours import market_snapshot_bucket

    return "_" + compute_fingerprint(market_snapshot_bucket().key)


def global_macro_fingerprint(inputs: ModuleFingerprintInputs) -> str:
    """全球政经局势：持仓结构 + 分类结构 + 申购限购块 + 版本盐（**不含任何价格**）。

    本模块谈的是全球政经与宏观环境，结论不依赖持仓标的的具体价格，故键里只留
    「我的组合由哪些品种构成」这一层事实：

    **不入键**（仍进提示词，时效由 TTL 兜底）：指数/美股行情、总市值/盈亏、竞争语境块、
    事件窗分歧例块、调仓纪律回放块，以及**持仓变动复盘块**（含跨快照市值差/盈亏差，
    属价格派生）——它一变就换键会让 24h TTL 实际从未生效。
    ``purchase_block`` 只含限购额度/申购状态/下一开放日，与报价无关，属可执行性硬约束，
    故保留在键内。

    同因：**不带行情口径桶后缀**——键里既然没有价格，就没有「按行情快照分档」的必要，
    跨时段复用是安全的（`module_fingerprint.market_bucket_cache_suffix()` 只给含价格的模块）。
    """
    _parts = [
        extract_stable_holdings(inputs.holdings_details),
        extract_stable_categories(inputs.categories),
        # 事实校验规则版本：修正正文会回写模块缓存（键不变），故规则语义变化也须
        # 换键，否则旧缓存里按旧规则改错的正文会继续被复用。本模块不走
        # build_llm_fingerprint，故在此单列（与那边同一常量，口径同源）。
        FACT_CHECK_RULES_VERSION,
    ]
    if inputs.purchase_block:
        _parts.append(inputs.purchase_block)
    return compute_fingerprint(*_parts) + generation_params_suffix("global_macro")


def expert_review_fingerprint(inputs: ModuleFingerprintInputs) -> str:
    """智囊团深度复盘：基础指纹 + 提示词内容（竞争语境块 / 量化指标）+ 五段现算后缀。

    五个后缀（决策教训 / 信号预消化 / 环比与降级块 / 确定性信号摘要 / 结构化
    决策头）各自的开关判定收敛在函数内部，关闭或样本不足时返回空串——键与未
    启用时一致，不误伤既有缓存。

    竞争语境块与 ``metrics`` 都是其提示词的正文段（【今日对比】/【区间对比】/
    【指标对比】/【量化指标】/情景分析），连同 ``pipeline_data`` 派生的【环比
    变化】【数据质量降级】两段（见 ``_pipeline_block_cache_suffix``）一并纳入哈希。
    """
    _parts = [
        build_llm_fingerprint(
            holdings_details=inputs.holdings_details,
            penetrated_assets=inputs.penetrated_assets,
            categories=inputs.categories,
            history_data=inputs.history_data,
        ),
    ]
    if inputs.purchase_block:
        _parts.append(inputs.purchase_block)
    if inputs.holding_change_block:
        _parts.append(inputs.holding_change_block)
    _fp = compute_fingerprint(*_parts)
    _fp += debate_feature_cache_suffix()
    if decision_ledger.is_active():
        _fp += decision_ledger.lessons_cache_suffix()
    _fp += _signal_digest_cache_suffix(inputs.pipeline_data)
    _fp += _pipeline_block_cache_suffix(inputs.pipeline_data)
    _fp += signal_ledger.summary_cache_suffix()
    _fp += scenario_mandate_cache_suffix()
    _fp += market_bucket_cache_suffix()
    _fp += generation_params_suffix("expert_review")
    return _fp


def debate_procon_fingerprint(inputs: ModuleFingerprintInputs) -> str:
    """辩论白脸 / 黑脸两键共用的基础指纹 + 统一附录四块 + 辩论增强后缀 + 环比与降级块后缀。

    **仅写侧使用**：辩论模式绕过标准预检（其缓存键族 ``llm_debate_*`` 与标准
    ``llm_expert_review_*`` 不同），故不进 ``MODULE_FINGERPRINT_BUILDERS``。

    输入口径以其提示词实际包含的段落为准——持仓结构与分类结构 + 辩论增强后缀 +
    ``pipeline_data`` 派生的【环比变化】【数据质量降级】两段（白脸/黑脸复用
    ``_build_expert_review_prompt``，这两段随之进入其提示词）+ 统一 prompt 附录中
    的**口径类**块（申购限购 / 持仓变动复盘；经 skeleton 追加附录，故与四标准模块
    同形**非空才并入**——否则仅附录内容变化（如申购状态更新）时键不动，回放带旧
    附录上下文的旧输出；空串不追加 part，键与引入前逐字节一致）。

    **刻意不并入**：``history_data`` 与决策教训、信号摘要、结构化决策头后缀
    （辩论提示词不含这些段落）；以及纯行情/时效类输入（totals / 竞争语境 /
    量化指标 / 事件窗分歧例块 / 调仓纪律回放块）——它们仍进提示词，但由 TTL 兜底。
    """
    _parts = [
        build_llm_fingerprint(
            holdings_details=inputs.holdings_details,
            penetrated_assets=inputs.penetrated_assets,
            categories=inputs.categories,
        ),
    ]
    # 条件并入：口径类块进提示词即进键；块空不追加 part（逐字节回退，不误伤存量缓存）
    if inputs.purchase_block:
        _parts.append(inputs.purchase_block)
    if inputs.holding_change_block:
        _parts.append(inputs.holding_change_block)
    return (
        compute_fingerprint(*_parts)
        + debate_feature_cache_suffix()
        + _pipeline_block_cache_suffix(inputs.pipeline_data)
        + market_bucket_cache_suffix()
        + generation_params_suffix("expert_review")
    )


def debate_synthesis_fingerprint(inputs: ModuleFingerprintInputs, synthesis_prompt: str) -> str:
    """辩论综合（第三段）：辩论基础指纹 + **综合提示词全文**。

    **仅写侧使用**（同 ``debate_procon_fingerprint``）。

    综合提示词 = 白脸/黑脸**全文** + 条件推理情景段（``debate.conditional.scenarios``
    驱动）+ 集中度问答段（``debate.concentration_qa.threshold`` 驱动，内建段落），由
    ``_build_debate_synthesis_prompt`` 一次性渲染。既然提示词就是这三者的函数，
    键直接取该渲染结果——无需逐项枚举入哈希的来源，也就不会漏项。

    本键不得另起一套摘要：只截取 pro/con **前 200 字符**再拼接会有两处后果——
    正文差异落在 200 字符之后时键不动（命中按旧正文生成的综合结论），仅改
    config（情景名/描述、集中度阈值）而开关位不变时键同样不动。

    Args:
        inputs: 与白脸/黑脸同一份输入闭包（除 ``pipeline_data`` 外，其效果已由
            基础指纹承载）。
        synthesis_prompt: 已渲染的综合阶段 user prompt。
    """
    suffix = generation_params_suffix("expert_review")
    from src.python.config import get_llm_config

    config = get_llm_config() or {}
    procon = (config.get("debate") or {}).get("procon") or {}
    if "synthesis_temperature" in procon:
        suffix += "_" + compute_fingerprint(f"st={procon['synthesis_temperature']}")
    return compute_fingerprint(debate_procon_fingerprint(inputs), synthesis_prompt) + suffix


def health_check_fingerprint(inputs: ModuleFingerprintInputs) -> str:
    """持仓体检报告：基础指纹 + 数据质量详细状态块 + 信号预消化后缀。

    数据质量块（【数据质量详细状态】）由其提示词直接承载，且是**本次运行**的
    数据源画像（属口径类事实，不是行情）：数据源故障期间生成的结论若被复用，
    会陈述与此刻事实相反的故障状态，故进键。该块为**已渲染文本**，与注入
    提示词的实例同一（见模块 docstring）。

    ``pipeline_data`` 派生的【环比变化】【数据质量降级】两段同属口径类事实，同进。
    纯行情/时效类输入（风险信号 / 事件窗分歧例块 / 调仓纪律回放块）
    不入键——它们仍进提示词，由 TTL 兜底。
    """
    _parts = [
        build_llm_fingerprint(
            holdings_details=inputs.holdings_details,
            penetrated_assets=inputs.penetrated_assets,
            categories=inputs.categories,
            history_data=inputs.history_data,
        ),
        inputs.data_quality_text,
    ]
    if inputs.purchase_block:
        _parts.append(inputs.purchase_block)
    if inputs.holding_change_block:
        _parts.append(inputs.holding_change_block)
    _fp = compute_fingerprint(*_parts)
    _fp += _signal_digest_cache_suffix(inputs.pipeline_data)
    _fp += _pipeline_block_cache_suffix(inputs.pipeline_data)
    _fp += market_bucket_cache_suffix()
    _fp += generation_params_suffix("health_check")
    return _fp


def penetration_deep_fingerprint(inputs: ModuleFingerprintInputs) -> str:
    """穿透深度分析：基础指纹（穿透资产含 sector 行业归属）+ 条件并入**口径类**约束块。

    穿透资产的 mv/ratio 是行情派生值（ETF 报价变动即变），不入键；sector 是
    行业归属，属结构性事实，保留。事件窗分歧例块与调仓纪律回放块仍进提示词，
    但不入键（时效类，由 TTL 兜底）。
    """
    _base = build_llm_fingerprint(
        holdings_details=inputs.holdings_details,
        penetrated_assets=inputs.penetrated_assets,
        categories=inputs.categories,
        full_penetration=True,
        history_data=inputs.history_data,
    )
    _extra = [
        part
        for part in (
            inputs.purchase_block,
            inputs.holding_change_block,
        )
        if part
    ]
    if _extra:
        # 条件并入：口径类块进提示词即进键；两块均空时不追加 part（逐字节回退）
        return (
            compute_fingerprint(_base, *_extra)
            + market_bucket_cache_suffix()
            + generation_params_suffix("penetration_deep")
        )
    return _base + market_bucket_cache_suffix() + generation_params_suffix("penetration_deep")


def self_review_fingerprint(
    module_outputs: dict[str, str | None] | None,
    holdings_details: list[dict] | None = None,
    penetrated_assets: list[dict] | None = None,
    purchase_block: str = "",
    holding_change_block: str = "",
) -> str:
    """生成后自检：**内容寻址**指纹——各模块产出文本 + 数据摘要。

    **仅写侧使用**（与辩论三键同形）：自检是生成后一遍，输入是其余模块的产出，
    不存在「预检侧提前算同一键」的需求，故不进 ``MODULE_FINGERPRINT_BUILDERS``
    （该表供预检/写两侧共享同一构造，键形为 ``ModuleFingerprintInputs``）。

    覆盖判据：自检提示词由各模块产出正文 + 持仓/穿透摘要构成，三者都进键；
    产出未变（含全部命中缓存）时键不变 → 自检同样命中缓存。
    提示词文本版本盐（`PROMPT_SCHEMA_VERSION`）并入分段构成——自检清单/禁止项等
    静态文案改动同样须换键，否则旧自检结论会按旧清单继续被复用。

    **口径类附录块进键，时效类附录块不进**：申购限购 / 持仓变动复盘属口径事实
    （进键）；事件窗分歧例 / 调仓纪律回放属行情与新闻派生数据（仍进提示词，
    由 TTL 兜底）——否则自检会跟着新闻刷新每 15 分钟全量重算。

    Args:
        module_outputs: 模块名 → HTML 产出（None/空串按缺失处理）。
        holdings_details: 持仓明细（仅取 name/code/cost 稳定字段）。
        penetrated_assets: 穿透资产列表。
        purchase_block: 申购限购约束块（非空 → 提示词附录含块，故进键；
            块空 → 逐字节沿用不带该段的原形态，键与引入前一致）。
        holding_change_block: 持仓变动复盘提示词块（非空 → 提示词附录含块，
            故进键；块空 → 键与引入前一致）。
    """
    _parts = self_review_fingerprint_parts(
        module_outputs,
        holdings_details,
        penetrated_assets,
        purchase_block=purchase_block,
        holding_change_block=holding_change_block,
    )
    return compute_fingerprint(*_parts.values()) + generation_params_suffix("self_review")


def self_review_fingerprint_parts(
    module_outputs: dict[str, str | None] | None,
    holdings_details: list[dict] | None = None,
    penetrated_assets: list[dict] | None = None,
    purchase_block: str = "",
    holding_change_block: str = "",
) -> dict[str, object]:
    """自检指纹的**分段构成**（有序）：同一事实源供指纹与「哪一段变了」诊断共用。

    键顺序即并入顺序；块为空时不出现该键（与指纹的条件并入逐字节一致）。
    诊断用途：未命中时逐段取摘要比对，可直接定位是哪一段输入变化导致重算
    （自检键并入六类输入，仅看总键无法区分）。
    """
    normalized = {
        key: (text or "")
        for key, text in sorted((module_outputs or {}).items())
        if isinstance(text, str) and text.strip()
    }
    parts: dict[str, object] = {
        # 提示词文本版本盐：自检清单等静态文案改动也须换键（与四主模块同口径）
        "prompt_version": PROMPT_SCHEMA_VERSION,
        "outputs": normalized,
        "holdings": extract_stable_holdings(holdings_details),
        "penetration": extract_stable_penetration(penetrated_assets),
    }
    # 条件并入（口径类）：块空不追加 part（逐字节回退）
    if purchase_block:
        parts["purchase"] = purchase_block
    if holding_change_block:
        parts["holding_change"] = holding_change_block
    return parts


def holding_change_review_fingerprint(
    context_block: str,
    signal_block: str = "",
    holdings_details: list[dict] | None = None,
    purchase_block: str = "",
) -> str:
    """持仓变动复盘归因：**内容寻址**指纹——事实块 + 信号对账块 + 持仓摘要 + 附录约束块。

    **仅写侧使用**（与自检/辩论三键同形）：编排层串行调用，无预检侧提前算键需求。

    覆盖判据仍是「提示词是否真的含该段」：事实块与信号块都直接拼进 user prompt，
    附录约束块经统一 prompt 附录进入——故均进键；块空时不追加 part（键与不带
    该段时逐字节一致）。

    Args:
        context_block: 契约 ``prompt_block`` 事实块（模块存在的理由，恒进键）。
        signal_block: 窗口内历史信号对账块（非空 → 进键）。
        holdings_details: 持仓明细（仅取 name/code/市值稳定字段）。
        purchase_block: 申购限购约束块（非空 → 附录含块，故进键）。
    """
    _parts: list = [context_block or "", extract_stable_holdings(holdings_details)]
    if signal_block:
        _parts.append(signal_block)
    if purchase_block:
        # 条件并入：进提示词必进指纹；块空不追加 part（逐字节回退）
        _parts.append(purchase_block)
    return compute_fingerprint(*_parts) + generation_params_suffix("holding_change")


# 模块标识 → 指纹构造器。预检侧按键取指纹建缓存键，写侧闭包按同一函数现算，
# 新增 LLM 模块时在此登记即可（模块键与 llm 模块注册表一致）。
MODULE_FINGERPRINT_BUILDERS: dict[str, Callable[[ModuleFingerprintInputs], str]] = {
    "global_macro": global_macro_fingerprint,
    "expert_review": expert_review_fingerprint,
    "health_check": health_check_fingerprint,
    "penetration_deep": penetration_deep_fingerprint,
}
