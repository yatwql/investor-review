/* chart-export.js — 单图导出 PNG / CSV 按钮。
 *
 * 职责：
 *   - 提供 window.ChartExport.register(chart, key)：为每个 Chart.js 图表
 *     注入「导出PNG」「导出CSV」两枚按钮（容器 .chart-export-actions）
 *   - PNG：chart.toBase64Image()（2x 分辨率）→ <a download> 下载
 *   - CSV：读取 chart.data（与屏显同源的图表数据，Python 数据层已按匿名化
 *     口径脱敏，导出值与图表悬停值一致）→ UTF-8 BOM + CRLF 的 CSV 文本
 *     → Blob 本地下载（纯本地零后端），供读者做透视/二次分析
 *   - 必须在 chart-init.js 之前加载（chart-init.js 创建图表后立即 register）
 * - ES5 保守语法：var / function / 无箭头函数
 *
 * 按钮位置：存在 .chart-title 时容器追加到标题栏右侧；否则以绝对定位浮于
 * .chart-box 右上角（图表区固定高度，普通流式追加会溢出）。
 */
(function () {
  'use strict';

  /* ── CSV 组装 ──────────────────────────────────────── */

  /* 单元格转义（RFC 4180）：含引号/逗号/换行时整体加引号，内部引号翻倍 */
  function csvCell(value) {
    var s = (value === null || value === undefined) ? '' : String(value);
    if (s.indexOf('"') !== -1 || s.indexOf(',') !== -1 ||
        s.indexOf('\n') !== -1 || s.indexOf('\r') !== -1) {
      s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  /* 数据列取值：图表数据恒为标量数组；对象点取 y，空洞（null/undefined）留空 */
  function cellValue(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'object') {
      if (typeof v.y !== 'undefined') return v.y;
      return JSON.stringify(v);
    }
    return v;
  }

  /* 首列表头：优先 x/r 轴标题（模板配置里有才取），否则通用「标签」 */
  function firstHeader(chart) {
    var scales = chart && chart.options && chart.options.scales;
    if (scales) {
      if (scales.x && scales.x.title && scales.x.title.text) return scales.x.title.text;
      if (scales.r && scales.r.title && scales.r.title.text) return scales.r.title.text;
    }
    return '标签';
  }

  /* 由 chart.data（与屏显同源）组装 CSV 文本：
   * 行 = 标签 + 各数据系列；\ufeff（BOM）+ CRLF，Excel 直接双击可开 */
  function buildCsvText(chart) {
    var data = (chart && chart.data) || {};
    var labels = data.labels || [];
    var datasets = data.datasets || [];
    if (!datasets.length) return '';

    var header = [firstHeader(chart)];
    datasets.forEach(function (ds, i) {
      var lb = ds && ds.label;
      header.push(lb || (datasets.length === 1 ? '数值' : '系列 ' + (i + 1)));
    });
    var rows = [header];

    var n = labels.length;
    datasets.forEach(function (ds) {
      var arr = (ds && ds.data) || [];
      if (arr.length > n) n = arr.length;
    });
    for (var i = 0; i < n; i++) {
      var row = [i < labels.length ? labels[i] : ''];
      datasets.forEach(function (ds) {
        var arr = (ds && ds.data) || [];
        row.push(i < arr.length ? cellValue(arr[i]) : '');
      });
      rows.push(row);
    }

    var lines = rows.map(function (r) {
      return r.map(csvCell).join(',');
    });
    return '\ufeff' + lines.join('\r\n') + '\r\n';
  }

  /* ── 下载 ───────────────────────────────────────────── */

  function downloadBlob(filename, blob) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  function downloadPng(chart, key) {
    var a = document.createElement('a');
    a.href = chart.toBase64Image({ width: Math.round(chart.canvas.width * 2) });
    a.download = (key || 'chart') + '.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  /* ── 注入导出按钮 ───────────────────────────────────── */

  function makeButton(label, ariaLabel, handler) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chart-export-btn';
    btn.textContent = label;
    btn.setAttribute('aria-label', ariaLabel);
    btn.onclick = handler;
    return btn;
  }

  function addExportButtons(chart, key) {
    if (!chart || !chart.canvas) return;
    var box = chart.canvas.parentNode;
    while (box && (!box.className || String(box.className).indexOf('chart-box') === -1)) {
      box = box.parentNode;
    }
    if (!box || box.querySelector('.chart-export-actions')) return;

    var group = document.createElement('div');
    group.className = 'chart-export-actions';

    group.appendChild(makeButton('导出PNG', '导出图表为 PNG 图片', function () {
      try {
        downloadPng(chart, key);
      } catch (e) {
        console.warn('[chart] 导出 PNG 失败（' + key + '）: ', e);
      }
    }));

    group.appendChild(makeButton('导出CSV', '导出图表数据为 CSV 文件', function () {
      try {
        var csv = buildCsvText(chart);
        if (!csv) return;
        downloadBlob((key || 'chart') + '.csv',
          new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      } catch (e) {
        console.warn('[chart] 导出 CSV 失败（' + key + '）: ', e);
      }
    }));

    var titleEl = box.querySelector('.chart-title');
    if (titleEl) {
      titleEl.appendChild(group);
    } else {
      box.appendChild(group);
    }
  }

  window.ChartExport = {
    register: function (chart, key) {
      addExportButtons(chart, key);
      return chart;
    }
  };
})();
