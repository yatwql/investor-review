"""项目共享常量模块。

此模块不含对本项目其他任何模块的 import，保持零依赖。
供 cache.py、registry.py、tui.py 等模块引用。
"""

import os
from datetime import timedelta, timezone


def _find_project_root() -> str:
    """从当前文件向上查找标记文件，确定项目根目录。

    查找顺序：pyproject.toml → .git（目录）。两种标记均可，找到即停。
    不依赖目录树深度，文件移动不会导致路径偏移。
    """
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(20):  # 安全上限，防止意外死循环
        if os.path.isfile(os.path.join(current, "pyproject.toml")):
            return current
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # 回退：按当前 src/python/ 深度计算
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── 项目根路径（单一来源，所有模块从此导入） ─────────────
# 使用标记文件查找法（pyproject.toml / .git），不依赖目录树深度。
PROJECT_ROOT = _find_project_root()

# ── 项目名称与版本 ─────────────────────────────────────────

# 应用名称（单一来源，TUI 首页 / 启动日志 / Web 首页 / HTML 报告首页 / Excel 首页统一引用）
APP_NAME = "投资复盘助手"

APP_VERSION = "0.16.5"

# ── 报告产物文件名（单一来源：Excel/HTML 写入器与 Web 预览下载统一引用） ──
# 报告产物文件基名（归档名 = 基名 + 时间戳后缀）
REPORT_FILE_BASE = "个人投资分析报告"
LATEST_XLSX_NAME = f"{REPORT_FILE_BASE}.xlsx"
LATEST_HTML_NAME = f"{REPORT_FILE_BASE}.html"
# 调仓模拟（少数派产物：与主报告并列于输出目录顶层，产物清扫与 TUI/Web 列举按名识别）
WHATIF_FILE_BASE = "调仓模拟"
LATEST_WHATIF_XLSX_NAME = f"{WHATIF_FILE_BASE}.xlsx"
LATEST_WHATIF_HTML_NAME = f"{WHATIF_FILE_BASE}.html"

# ── 缓存频率常量（秒，用作代码内默认值） ──────────────────

CACHE_DAILY = 86400  # 每日（24h）
CACHE_WEEKLY = 604800  # 每周（7d）
CACHE_TWO_WEEKS = 1209600  # 两周（14d）
CACHE_MONTHLY = 2592000  # 每月（30d）

# ── 组合历史走势 ─────────────────────────────────

# 快照目录（相对于 PROJECT_ROOT）
HISTORY_SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, "data", "history", "snapshots")
# 快照保留天数（超过此天数的旧快照自动清理）
# 180 天：为持仓变动复盘（holding_change_events）保证长复盘窗口——周报告节奏下
# 仍约 26 期（先决门槛 12 期的 2 倍余量）；60 天时周节奏仅约 9 期会跌破门槛。
HISTORY_SNAPSHOT_RETENTION_DAYS = 180
# 快照最大保留数量（安全上限，远超 retention 正常生成量，仅在异常堆积时触发）
# 180天×每日约1.5份 ≈ 270 以内，设为 365 防止误伤正常快照
HISTORY_SNAPSHOT_MAX_COUNT = 365


# ── LLM 模型定价表（每百万 token，CNY）══ 唯一默认源 ══

# 币种口径：每条按**厂商官方标价币种原样记录**，不做任何汇率折算，且**每条都显式
# 写 `currency`**（Anthropic / OpenAI / Google = USD，DeepSeek / Kimi = CNY）——
# 不让条目靠全局缺省兜底，避免「改本地币种配置把人民币数字贴成 `$`」。报告按条目
# 币种显示原生金额，跨币种金额分组并列（如 `¥0.012 + $0.003`），从不相加。


# 缺省币种（本地主币种，默认 CNY）。**语义只有一个**：模型同时提供多币种价时，选哪一套
# 计价与显示（条目 `alt` 子表提供该币种价即命中），以及日预算以哪个币种判定。
# 它**不是**「条目缺省币种」——`MODEL_PRICING` 每条都必须显式声明 `currency`
# （CNY 厂商也要写），条目币种与配置币种各自独立，互不串味。
PRICING_DEFAULT_CURRENCY: str = "CNY"

MODEL_PRICING: dict[str, dict[str, float | str | dict[str, float]]] = {
    # 单一来源：此表为唯一默认定价。pricing.py 以此为基，从 llm_settings.json
    # 的 llm_pricing_ref.json 逐模型覆盖，运行时合并到 _PRICING_MERGED。
    # 新增模型请在此处添加，不要仅修改 llm_settings.json。
    # Per 1M token:
    #   input: 标准输入（缓存未命中）——含 "peak" 子段的模型即闲时价（默认价）
    #   output: 输出
    #   input_cache_hit: 缓存命中输入（可选，默认等于 input 即无折扣）
    #   peak: 高峰价子段（可选，仅 DeepSeek 峰谷定价模型有）——高峰日（工作日且非法
    #         定节假日）高峰时段按此计费，其余时段按 base 价（input/output/input_cache_hit）。
    #         时段见下方 PRICING_PEAK_PERIODS / PRICING_IDLE_PERIODS；周末与法定节假日
    #         全天按闲时价（2026-08-23 起周末统一低谷价、2026-09-10 起含法定节假日），
    #         见 PRICING_WEEKEND_ALWAYS_IDLE / PRICING_HOLIDAY_ALWAYS_IDLE。
    #         均可经 llm_settings.json → pricing 段覆盖。
    # 通用前缀（如 "claude-sonnet-5-"）用作 startswith() 回退匹配，
    # 覆盖所有日期戳变体（如 claude-sonnet-5-5-20260928），避免费用显示 "-"。
    # 官方价目核验：Anthropic / OpenAI / Google / DeepSeek / Kimi 官方定价页（2026-10-25）。
    #
    # ── Claude 5.5 家族（现役，官方 USD 标价） ──
    # Fable 5.1 $10/$50，缓存命中 $0.25
    "claude-fable-5-1": {"currency": "USD", "input": 10.0, "output": 50.0, "input_cache_hit": 0.25},
    "claude-fable-5-": {"currency": "USD", "input": 10.0, "output": 50.0, "input_cache_hit": 0.25},
    # Opus 5.5 $4/$20，缓存命中 $0.20
    "claude-opus-5-5": {"currency": "USD", "input": 4.0, "output": 20.0, "input_cache_hit": 0.2},
    "claude-opus-5-": {"currency": "USD", "input": 4.0, "output": 20.0, "input_cache_hit": 0.2},
    # Sonnet 5.5 $2/$10，缓存命中 $0.10
    "claude-sonnet-5-5": {"currency": "USD", "input": 2.0, "output": 10.0, "input_cache_hit": 0.1},
    # Sonnet 5（legacy，仍在售）$2/$10，缓存命中 $0.20
    "claude-sonnet-5-": {"currency": "USD", "input": 2.0, "output": 10.0, "input_cache_hit": 0.2},
    # Haiku 5.5 $0.10/$0.50（prompt ≤100K），缓存命中 $0.01；>100K 档
    # （$0.50/$2.50，命中 $0.05）不单列——本表一条记录对应一个模型名，
    # 分档计费需按输入长度切换，超出「单模型单价」表达能力。
    "claude-haiku-5-5": {"currency": "USD", "input": 0.1, "output": 0.5, "input_cache_hit": 0.01},
    "claude-haiku-5-": {"currency": "USD", "input": 0.1, "output": 0.5, "input_cache_hit": 0.01},
    #
    # ── Claude 旧代（legacy，仍可调用） ──
    # Sonnet 4.6 $3/$15，缓存命中 $0.30
    "claude-sonnet-4-6": {"currency": "USD", "input": 3.0, "output": 15.0, "input_cache_hit": 0.3},
    "claude-sonnet-4-": {"currency": "USD", "input": 3.0, "output": 15.0, "input_cache_hit": 0.3},
    # Opus 4.x $5/$25，缓存命中 $0.50
    "claude-opus-4-6": {"currency": "USD", "input": 5.0, "output": 25.0, "input_cache_hit": 0.5},
    "claude-opus-4-8": {"currency": "USD", "input": 5.0, "output": 25.0, "input_cache_hit": 0.5},
    "claude-opus-4-": {"currency": "USD", "input": 5.0, "output": 25.0, "input_cache_hit": 0.5},
    # Haiku 4.5 $1/$5，缓存命中 $0.10
    "claude-haiku-4-5": {"currency": "USD", "input": 1.0, "output": 5.0, "input_cache_hit": 0.1},
    "claude-haiku-4-": {"currency": "USD", "input": 1.0, "output": 5.0, "input_cache_hit": 0.1},
    # Fable 5 $10/$50，缓存命中 $1.00
    "claude-fable-5": {"currency": "USD", "input": 10.0, "output": 50.0, "input_cache_hit": 1.0},
    #
    # ── OpenAI（官方 USD） ──
    # GPT-6 Astra $10/$50，缓存命中 $1.00
    "gpt-6-astra": {"currency": "USD", "input": 10.0, "output": 50.0, "input_cache_hit": 1.0},
    # GPT-6.1 Sol $2/$10，缓存命中 $0.10
    "gpt-6.1-sol": {"currency": "USD", "input": 2.0, "output": 10.0, "input_cache_hit": 0.1},
    "gpt-6.1-": {"currency": "USD", "input": 2.0, "output": 10.0, "input_cache_hit": 0.1},
    # GPT-6 Luna $0.10/$0.50，缓存命中 $0.01（不入 gpt-6- 族前缀，避免与 Sol 价混淆）
    "gpt-6-luna": {"currency": "USD", "input": 0.1, "output": 0.5, "input_cache_hit": 0.01},
    # GPT-5.6 Sol $4/$20，缓存命中 $0.40
    "gpt-5.6-sol": {"currency": "USD", "input": 4.0, "output": 20.0, "input_cache_hit": 0.4},
    "gpt-5.6-": {"currency": "USD", "input": 4.0, "output": 20.0, "input_cache_hit": 0.4},
    # GPT-4o 系列（legacy）$2.50/$10 与 $0.15/$0.60，缓存命中各 50%
    "gpt-4o": {"currency": "USD", "input": 2.5, "output": 10.0, "input_cache_hit": 1.25},
    "gpt-4o-mini": {"currency": "USD", "input": 0.15, "output": 0.6, "input_cache_hit": 0.075},
    #
    # ── Gemini（官方 USD） ──
    # Gemini 3.8 Flash $0.75/$3.75（2026-12-31 前优惠价），缓存命中 $0.075
    "gemini-3.8-flash": {"currency": "USD", "input": 0.75, "output": 3.75, "input_cache_hit": 0.075},
    "gemini-3.8-": {"currency": "USD", "input": 0.75, "output": 3.75, "input_cache_hit": 0.075},
    # Gemini 3.1 Pro (preview) $2/$12，缓存命中 $0.20
    "gemini-3.1-pro": {"currency": "USD", "input": 2.0, "output": 12.0, "input_cache_hit": 0.2},
    "gemini-3.1-": {"currency": "USD", "input": 2.0, "output": 12.0, "input_cache_hit": 0.2},
    # Gemini 2.5 Flash / Pro（legacy）$0.30/$2.50 与 $1.25/$10
    "gemini-2.5-flash": {"currency": "USD", "input": 0.3, "output": 2.5, "input_cache_hit": 0.03},
    "gemini-2.5-pro": {"currency": "USD", "input": 1.25, "output": 10.0, "input_cache_hit": 0.125},
    "gemini-2.5-": {"currency": "USD", "input": 1.25, "output": 10.0, "input_cache_hit": 0.125},
    #
    # ── DeepSeek 峰谷定价（元/百万 token，官方直接以 CNY 标价） ──
    # base 为闲时价；peak 为高峰价（高峰时段为闲时的 2 倍）。峰谷时段、周末与法定
    # 节假日规则见下方 PRICING_PEAK_PERIODS / PRICING_WEEKEND_ALWAYS_IDLE /
    # PRICING_HOLIDAY_ALWAYS_IDLE。
    #
    # deepseek-flash（DeepSeek 新一代 Flash 正式模型名，2026-09-10 发布）沿用
    # flash 系列定价：闲时 输入 1.0/输出 4.0/缓存命中 0.02，高峰翻倍
    # 2.0/8.0/0.04（2026-09-10 12:00 北京时间起 flash 系列官方降价，最高 60%）。
    "deepseek-flash": {
        "currency": "CNY",
        "input": 1.0,
        "output": 4.0,
        "input_cache_hit": 0.02,
        "peak": {"input": 2.0, "output": 8.0, "input_cache_hit": 0.04},
    },
    # 别名 deepseek-v4-flash / deepseek-v4-flash-vision-exp 端点仍接受，底层模型
    # 已由新一代 Flash 接管并按同一单价计费，故数值与 deepseek-flash 一致。
    "deepseek-v4-flash": {
        "currency": "CNY",
        "input": 1.0,
        "output": 4.0,
        "input_cache_hit": 0.02,
        "peak": {"input": 2.0, "output": 8.0, "input_cache_hit": 0.04},
    },
    # deepseek-v4-pro 单价未随 flash 调价变动（官方 2026-09-10 公告：2026-09-14 之后
    # 继续提供 API 服务，计费方式保持不变）。
    "deepseek-v4-pro": {
        "currency": "CNY",
        "input": 4.5,
        "output": 13.5,
        "input_cache_hit": 0.15,
        "peak": {"input": 9.0, "output": 27.0, "input_cache_hit": 0.30},
    },
    #
    # ── Kimi（月之暗面开放平台，官方直接以 CNY 标价） ──
    # kimi-k3.1-pro：旗舰升级版（1M 上下文），输入 13 / 输出 68 / 缓存命中 1.30
    "kimi-k3.1-pro": {"currency": "CNY", "input": 13.0, "output": 68.0, "input_cache_hit": 1.30},
    # kimi-k3.1-pro-highspeed：同模型高速档，输入 26 / 输出 136 / 缓存命中 1.30
    "kimi-k3.1-pro-highspeed": {"currency": "CNY", "input": 26.0, "output": 136.0, "input_cache_hit": 1.30},
    # kimi-k3：旗舰模型（1M 上下文），输入 20 / 输出 100 / 缓存命中 2.00
    "kimi-k3": {"currency": "CNY", "input": 20.0, "output": 100.0, "input_cache_hit": 2.00},
    # kimi-k2.6：通用模型（256k 上下文，支持思考/非思考模式）
    "kimi-k2.6": {"currency": "CNY", "input": 6.5, "output": 27.0, "input_cache_hit": 1.10},
}

# ── LLM 峰谷定价时段（DeepSeek 官方方案，北京时间）══ 唯一默认源 ══
# 高峰时段为北京时间周一至周五（不含中国法定节假日）9:00–12:00、14:00–18:00；
# 闲时为其余时间（闲时价 = MODEL_PRICING 中含 "peak" 子段模型的 base 价）。周末
# （周六/周日）全天与法定节假日全天按闲时价计费，不区分峰谷（官方 2026-09-10
# 定价页口径：周末及中国法定节假日全天均为空闲时段）。pricing.py 以此为基，可从
# llm_settings.json → pricing 段（peak_periods / idle_periods / timezone /
# weekend_always_idle / holiday_always_idle）覆盖。
# 单位：当日 00:00 起算的分钟数（闭区间 [start, end]）。

# 高峰时段（分钟）——9:00–12:00、14:00–18:00（仅工作日生效）
PRICING_PEAK_PERIODS: list[tuple[int, int]] = [(9 * 60, 12 * 60), (14 * 60, 18 * 60)]

# 闲时时段（分钟）——空列表 = 高峰之外的其余时间均为闲时
PRICING_IDLE_PERIODS: list[tuple[int, int]] = []

# 周末全天按闲时价计费（周六/周日不再区分峰谷，2026-08-23 起 DeepSeek 官方方案）
PRICING_WEEKEND_ALWAYS_IDLE: bool = True

# 法定节假日全天按闲时价计费（工作日但非 A 股交易日；复用 core.trading_calendar
# 判定，2026-09-10 起 DeepSeek 官方定价页口径）
PRICING_HOLIDAY_ALWAYS_IDLE: bool = True

# 峰谷时段判定所用 IANA 时区（默认北京时间）
PRICING_TIMEZONE: str = "Asia/Shanghai"

#: 报告深度档位（顺序即由省到全）：config.json 默认值与 llm 档位解析共用这一份，
#: 新增档位只改这里（默认值单源纪律由 check-code-traces 的 DEFAULTDUP 守卫）
REPORT_DEPTH_LEVELS: tuple[str, ...] = ("brief", "standard", "deep")

#: 报告深度出厂默认档位
REPORT_DEPTH_DEFAULT: str = "standard"

#: 项目统一北京时间口径（UTC+8 固定偏移，无夏令时）。**所有「自然日」判定都用它**：
#: 毫秒戳 → 日期的展示/契约转换、交易日边界、峰谷时段判定——用本机时区会随运行环境漂移
#: （CI 跑 UTC 时，CST 午夜附近的毫秒戳会算成前一天，测试与报告日期随之不一致）。
BEIJING_TZ = timezone(timedelta(hours=8))
