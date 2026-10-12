"""report_qa 单元测试共享夹具：构造最小报告 HTML（锚点/表格/噪声全含）。

样本覆盖解析契约的全部锚点：``div.section[id^=sec-]`` 分章、
``div.section-title`` 章标题、``sec-holdings_detail`` 表头名映射明细表
（含可选列「资金加权成本/申购状态」与合计行）、script/style/nav 噪声、
超长数据章（触发摘要截断）。
"""

from __future__ import annotations

import pytest

SAMPLE_REPORT_NAME = "个人投资分析报告.html"
SAMPLE_REPORT_NAME_2 = "组合复盘报告.html"

# 超过数据章摘要上限（_QA_DATA_SECTION_CAP=2500）的填充正文
_LONG_DATA = "仓位结构数据填充句，用于触发数据章摘要截断。" * 120

_SAMPLE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>个人投资分析报告</title>
<style>.sec-noise{display:none}</style>
<script>var alert_x = 'script-noise';</script>
</head>
<body>
<nav><a href="#sec-summary">导航目录链接</a></nav>
<div class="page">
<div class="section" id="sec-summary">
  <div class="section-title">1、投资分析汇总</div>
  <div class="kv-table">
    <div class="kv-row"><span>统计时间</span><span>2026-10-11 17:00</span></div>
    <div class="kv-row"><span>所属交易日</span><span>2026-10-11</span></div>
  </div>
  <div class="section-block">
    <div class="block-title">持仓概况</div>
    <div class="metric-grid"><div class="metric-cell"><span>持仓总市值</span><span>1,234,567.89 元</span></div></div>
  </div>
</div>
<div class="section" id="sec-holdings_detail">
  <div class="section-title">2、持仓明细</div>
  <table class="tbl">
    <thead><tr><th>名称</th><th>代码</th><th>份额</th><th>市值</th><th>收益率</th><th>资金加权成本</th><th>申购状态</th></tr></thead>
    <tbody>
      <tr><td>沪深300ETF</td><td>510300</td><td>1,000.00</td><td>3,900.00</td><td>5.20%</td><td>3.71</td><td>可申购</td></tr>
      <tr><td>某债券基金</td><td>000001</td><td>2,000.00</td><td>2,000.00</td><td>-1.10%</td><td>1.01</td><td>—</td></tr>
      <tr><td>合计</td><td></td><td>—</td><td>5,900.00</td><td>2.30%</td><td>—</td><td>—</td></tr>
    </tbody>
  </table>
</div>
<div class="section" id="sec-position_structure">
  <div class="section-title">5、仓位结构</div>
  <p>__LONG_DATA__</p>
</div>
<div class="section" id="sec-global_macro">
  <div class="section-title">10、全球政经局势</div>
  <p>全球宏观判断第一段，关注美元利率路径。</p>
  <p>全球宏观判断第二段，地缘风险溢价仍在。</p>
</div>
<div class="section" id="sec-expert_review">
  <div class="section-title">12、专家复盘</div>
  <p>专家复盘正文：组合波动主要来自权益仓位。</p>
</div>
</div>
</body>
</html>
"""

SAMPLE_REPORT_HTML = _SAMPLE_TEMPLATE.replace("__LONG_DATA__", _LONG_DATA)


@pytest.fixture
def qa_report(tmp_path):
    """写入两份样本报告，返回 (report, report2, output_dir)。"""
    (tmp_path / SAMPLE_REPORT_NAME).write_text(SAMPLE_REPORT_HTML, encoding="utf-8")
    (tmp_path / SAMPLE_REPORT_NAME_2).write_text(SAMPLE_REPORT_HTML, encoding="utf-8")
    return SAMPLE_REPORT_NAME, SAMPLE_REPORT_NAME_2, str(tmp_path)
