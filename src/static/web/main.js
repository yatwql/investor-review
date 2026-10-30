/* main.js — Web UI 前端逻辑（原生 ES6，无构建链）。
 *
 * 链路：上传 → 选择报告格式/选项 → 提交 → 轮询进度（编号步骤 + 当前阶段）
 * → 完成后产物按钮；状态区展示数据源健康 + 历史运行记录。
 *
 * XSS 防护（渲染侧）：一律 textContent/DOM API 渲染服务端返回字符串
 * （errors/events/健康/历史，可能含数据源名等不可信内容），禁止 innerHTML。
 * 错误展示：取服务端 error 中文文案直显；error_code 驱动分支动作，
 * 中文文案不前端硬编码映射（避免服务端/前端文案漂移）。
 */
(function () {
  'use strict';

  // AbortSignal.timeout 兼容兜底（Chrome 103+/Safari 16+ 起才提供，缺失时调用
  // 会同步抛 TypeError，fetch 参数构造失败 → 请求从未发出，上传/健康/配置面板
  // 全部静默失效：生成按钮灰色、面板空白、状态卡在"检测中"）。
  // 等价实现：AbortController + setTimeout；连 AbortController 都没有的超旧
  // 环境返回 undefined（fetch 忽略 undefined signal，请求照常发出仅失去超时）。
  if (typeof AbortSignal !== 'undefined' && !AbortSignal.timeout) {
    AbortSignal.timeout = function (ms) {
      var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
      if (ctrl) {
        setTimeout(function () {
          ctrl.abort();
        }, ms);
        return ctrl.signal;
      }
      return undefined;
    };
  }

  var POLL_INTERVAL_MS = 2000;
  // 活动 run 会话标记（sessionStorage）：刷新/误关重开页面据此重建进度视图续轮询
  var RUN_ID_KEY = 'investor_review_active_run_id';

  var state = {
    fileId: null,
    uploadInfo: null,
    runId: null,
    lastSeq: 0,
    pollTimer: null,
    pollBusy: false,
  };

  var els = {};

  function $(id) {
    return document.getElementById(id);
  }

  /* ── 初始化 ── */
  function init() {
    els.fileInput = $('file-input');
    els.uploadStatus = $('upload-status');
    els.generateForm = $('generate-form');
    els.reportType = $('report-type');
    els.historyFetch = $('history-fetch');
    els.forceLlm = $('force-llm');
    els.llmModuleGroup = $('llm-module-group');
    els.llmModuleCbs = document.querySelectorAll('.llm-module-cb');
    els.generateBtn = $('generate-btn');
    els.generateError = $('generate-error');
    els.progressSection = $('progress-section');
    els.progressBar = $('progress-bar');
    els.progressPhase = $('progress-phase');
    els.progressEvents = $('progress-events');
    els.resultSection = $('result-section');
    els.resultActions = $('result-actions');
    els.resultErrors = $('result-errors');
    els.resultFooter = $('result-footer');
    els.healthList = $('health-list');
    els.historyList = $('history-list');
    // 系统自检卡片（doctor_check 关闭时不存在于 DOM）
    els.doctorList = $('doctor-list');
    els.doctorRun = $('doctor-run');
    els.logLevel = $('log-level');
    els.logList = $('log-list');
    els.logStatus = $('log-status');
    // 输入模式（试算 trial / 正式 formal）相关控件
    els.modeRadios = document.querySelectorAll('input[name="input_mode"]');
    els.sourceRadios = document.querySelectorAll('input[name="use_existing"]');
    els.formalOptions = $('formal-options');
    els.formalWarning = $('formal-warning');
    els.formalHint = $('formal-hint');
    els.confirmOverwrite = $('confirm-overwrite');
    els.configPanel = $('config-panel');

    // 定时生成调度面板（配置页签）
    els.schedEnabled = $('sched-enabled');
    els.schedTime = $('sched-time');
    els.schedType = $('sched-type');
    els.schedWeekdayCbs = document.querySelectorAll('.sched-weekday-cb');
    els.schedSave = $('sched-save');
    els.schedStatus = $('sched-status');
    els.schedNext = $('sched-next');

    // 标签页工作台：导航按钮 + 面板切换（点击 / 方向键 / hash 深链）
    els.tabButtons = document.querySelectorAll('.tab-btn');

    // 调仓 What-if：表单与控件
    els.whatifForm = $('whatif-form');
    els.whatifBaseUpload = $('whatif-base-upload');
    els.whatifBaseInput = $('whatif-base-input');
    els.whatifBaseStatus = $('whatif-base-status');
    els.whatifCandInput = $('whatif-cand-input');
    els.whatifCandStatus = $('whatif-cand-status');
    els.whatifEffectiveDate = $('whatif-effective-date');
    els.whatifBtn = $('whatif-btn');
    els.whatifError = $('whatif-error');
    els.whatifResult = $('whatif-result');
    els.whatifLinkHtml = $('whatif-link-html');
    els.whatifLinkExcel = $('whatif-link-excel');
    els.whatifResultMeta = $('whatif-result-meta');

    // 缓存卡：统计展示 + 清理
    els.cacheTotalFiles = $('cache-total-files');
    els.cacheTotalSize = $('cache-total-size');
    els.cacheHitRate = $('cache-hit-rate');
    els.cacheExpired = $('cache-expired');
    els.cachePrefixList = $('cache-prefix-list');
    els.cacheRefresh = $('cache-refresh');
    els.cacheCleanup = $('cache-cleanup');
    els.cacheStatus = $('cache-status');

    els.fileInput.addEventListener('change', onFileSelected);
    els.generateForm.addEventListener('submit', onSubmit);
    if (els.forceLlm) {
      els.forceLlm.addEventListener('change', toggleLlmModuleGroup);
      toggleLlmModuleGroup();
    }
    $('health-refresh').addEventListener('click', function () {
      loadHealth(true);
    });
    if (els.doctorRun) {
      els.doctorRun.addEventListener('click', function () {
        loadDoctor();
      });
    }
    $('config-reload').addEventListener('click', function () {
      loadConfigEdit();
    });
    els.schedSave.addEventListener('click', saveScheduler);
    $('log-load').addEventListener('click', loadLogs);

    // 标签页工作台：五区切换（点击 + 方向键 + hash 深链）
    els.tabButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(btn.getAttribute('data-tab'));
      });
      btn.addEventListener('keydown', onTabKeydown);
    });
    window.addEventListener('hashchange', onLocationHashChange);
    applyLocationHash(true);

    // 调仓 What-if：基准来源切换 + 双文件上传 + 提交
    document.querySelectorAll('input[name="whatif_base"]').forEach(function (r) {
      r.addEventListener('change', onWhatifBaseModeChange);
    });
    els.whatifBaseInput.addEventListener('change', function () {
      uploadWhatifFile(els.whatifBaseInput, els.whatifBaseStatus, function (id) {
        whatifState.baseFileId = id;
      });
    });
    els.whatifCandInput.addEventListener('change', function () {
      uploadWhatifFile(els.whatifCandInput, els.whatifCandStatus, function (id) {
        whatifState.candFileId = id;
      });
    });
    els.whatifForm.addEventListener('submit', onWhatifSubmit);

    // 缓存卡：刷新 / 清理过期
    els.cacheRefresh.addEventListener('click', function () {
      setStatus(els.cacheStatus, '', null);
      loadCacheStats();
    });
    els.cacheCleanup.addEventListener('click', onCacheCleanup);

    // 生成用途/输入来源模式切换：正式模式展开区 + 警示条 + 按钮态联动
    els.modeRadios.forEach(function (r) {
      r.addEventListener('change', onModeChange);
    });
    els.sourceRadios.forEach(function (r) {
      r.addEventListener('change', onModeChange);
    });
    if (els.confirmOverwrite) {
      els.confirmOverwrite.addEventListener('change', updateGenerateBtn);
    }
    // 初始按默认 trial 收敛表单状态（正式展开区收起、按钮态就绪）
    onModeChange();

    // 拖拽上传（拖入上传区高亮）
    var zone = document.querySelector('.upload-zone');
    ['dragenter', 'dragover'].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        zone.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        zone.classList.remove('drag-over');
      });
    });
    zone.addEventListener('drop', function (e) {
      var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) {
        els.fileInput.files = e.dataTransfer.files;
        onFileSelected();
      }
    });

    // 状态区：数据源健康 + 历史运行记录（服务端各有短缓存，非频繁轮询）
    // 三个加载器各自隔离运行：任一初始化阶段抛同步异常（如旧浏览器缺
    // AbortSignal.timeout 导致 fetch 参数构造抛错）不得连带中断后续加载器，
    // 否则配置面板整块空白、生成按钮/健康/历史区全部静默失效。
    safeRun(loadHealth, [false], els.healthList, '健康检测失败，请稍后重试');
    safeRun(loadHistory, [], els.historyList, '历史记录加载失败');

    // 配置编辑面板（与 TUI 菜单一致）
    safeRun(loadConfigEdit, [], els.configPanel, '配置加载失败，请稍后重试');

    // 缓存统计（运行状态区卡片，服务端只读扫描）
    safeRun(loadCacheStats, [], els.cacheStatus, '缓存统计加载失败');

    // 定时生成调度（读取当前调度配置与下次触发预估）
    safeRun(loadScheduler, [], els.schedStatus, '调度配置加载失败，请稍后重试');

    // 断点续轮询：sessionStorage 中有活动 run → 重建进度视图续轮询（run 已随
    // 服务重启消失时，首帧轮询走 404 终态分支收口，不空转重试）
    resumeActiveRun();

    // 轮询节流：页面不可见时暂停轮询，恢复可见立即同步一次（省流量/省请求）
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        stopPolling();
      } else if (state.runId && els.progressSection && !els.progressSection.hidden) {
        startPolling();
      }
    });
  }

  /* ── 响应信封解析 ──
   * 成功：{ok:true, data} ；错误：{ok:false, error_code, error}（HTTP 4xx/5xx）
   * 统一抛 Error，附带 errorCode/httpStatus 供分支。
   */
  function handleResponse(res) {
    return res
      .json()
      .catch(function () {
        return {};
      })
      .then(function (data) {
        if (!res.ok || data.ok === false) {
          var err = new Error(data.error || '请求失败（HTTP ' + res.status + '）');
          err.errorCode = data.error_code || null;
          err.httpStatus = res.status;
          throw err;
        }
        return data.data;
      });
  }

  function setStatus(el, msg, kind) {
    el.textContent = msg;
    el.className = 'status-text' + (kind ? ' status-' + kind : '');
  }

  /* ── 输入模式（试算 trial / 正式 formal）状态机 ──
   * 试算（默认）：读上传临时文件，快照隔离 web/ 域，不碰正式持仓。
   * 正式：覆盖/使用正式持仓文件，快照写共享主目录；分「上传覆盖」与
   *   「直接用存量」两种来源——用存量免上传，但正式模式均须勾选确认。
   */
  function currentMode() {
    var checked = document.querySelector('input[name="input_mode"]:checked');
    return checked ? checked.value : 'trial';
  }

  /* 模块级强刷选择：全选/全不选 → null（后端等价全量），子集 → 键列表 */
  function selectedLlmModules() {
    var all = Array.prototype.slice.call(els.llmModuleCbs || []);
    if (!all.length) return null;
    var picked = all.filter(function (cb) { return cb.checked; }).map(function (cb) { return cb.value; });
    if (picked.length === 0 || picked.length === all.length) return null;
    return picked;
  }

  /* 勾选「强制 LLM」时展开模块多选组（默认全选 = 全量，与旧行为一致） */
  function toggleLlmModuleGroup() {
    if (!els.llmModuleGroup) return;
    els.llmModuleGroup.hidden = !els.forceLlm.checked;
  }

  function currentSource() {
    var checked = document.querySelector('input[name="use_existing"]:checked');
    return checked ? checked.value : 'upload';
  }

  // 正式-用存量：无需上传，直接读正式持仓文件
  function isFormalExisting() {
    return currentMode() === 'formal' && currentSource() === 'existing';
  }

  function onModeChange() {
    var formal = currentMode() === 'formal';
    if (els.formalOptions) {
      els.formalOptions.hidden = !formal;
    }
    if (!formal && els.confirmOverwrite) {
      // 切回试算：清除正式覆盖确认勾选，避免残留状态误导后续提交
      els.confirmOverwrite.checked = false;
    }
    updateWarning();
    updateSourceHint();
    updateGenerateBtn();
  }

  // 警示条文案按输入来源动态（用存量不覆盖文件，措辞区分）
  function updateWarning() {
    if (!els.formalWarning) {
      return;
    }
    var path = els.formalWarning.dataset.holdings || '正式持仓文件';
    if (isFormalExisting()) {
      els.formalWarning.textContent =
        '将读取当前正式持仓文件 ' + path + ' 生成报告，并写入共享快照时间线（不会覆盖文件）';
    } else {
      els.formalWarning.textContent =
        '将覆盖 ' + path + '，旧文件备份为 .bak，并写入共享快照时间线';
    }
  }

  function updateSourceHint() {
    if (!els.formalHint) {
      return;
    }
    if (currentMode() !== 'formal') {
      setStatus(els.formalHint, '', '');
      return;
    }
    if (isFormalExisting()) {
      setStatus(els.formalHint, '无需上传，将直接读取正式持仓文件生成报告', 'ok');
    } else {
      setStatus(els.formalHint, '请先上传新文件，将覆盖正式持仓文件', 'busy');
    }
  }

  // 生成按钮可用性：试算/正式-上传须先上传；正式须勾选确认；正式-用存量免上传
  function updateGenerateBtn() {
    if (currentMode() !== 'formal') {
      els.generateBtn.disabled = !state.fileId;
      return;
    }
    if (els.confirmOverwrite && !els.confirmOverwrite.checked) {
      els.generateBtn.disabled = true;
      return;
    }
    if (isFormalExisting()) {
      els.generateBtn.disabled = false;
      return;
    }
    els.generateBtn.disabled = !state.fileId;
  }

  /* ── 上传 ── */
  function onFileSelected() {
    var file = els.fileInput.files[0];
    if (!file) {
      return;
    }
    var fd = new FormData();
    fd.append('file', file);
    setStatus(els.uploadStatus, '正在上传并校验 ' + file.name + ' ...', 'busy');
    els.generateBtn.disabled = true;

    fetch('/api/upload', {
      method: 'POST',
      body: fd,
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (data) {
        state.fileId = data.file_id;
        state.uploadInfo = data;
        var accountText = data.sheets && data.sheets.length
          ? data.sheets.length + ' 个账户'
          : '1 个账户';
        setStatus(els.uploadStatus, '上传成功：' + accountText + '，共 ' + data.count + ' 条持仓，可生成报告', 'ok');
        updateGenerateBtn();
      })
      .catch(function (err) {
        setStatus(els.uploadStatus, err.message, 'error');
        updateGenerateBtn();
      });
  }

  /* ── 触发生成 ── */
  function onSubmit(e) {
    e.preventDefault();
    var existing = isFormalExisting();
    // 正式-用存量无需上传；其余模式须已上传
    if (!existing && !state.fileId) {
      return;
    }
    els.generateBtn.disabled = true;
    els.generateBtn.setAttribute('aria-busy', 'true');
    els.generateBtn.textContent = '正在提交...';
    els.generateError.textContent = '';

    var body = {
      report_type: els.reportType.value,
      // 历史走势/强制 LLM 开关：表单显式传值（默认值已在页面加载时按配置回填）
      fetch_history: els.historyFetch.checked,
      force_llm: els.forceLlm.checked,
      llm_modules: selectedLlmModules(),
      mode: currentMode(),
      use_existing: existing,
    };
    // 正式-用存量：直接读正式持仓文件，body 不携带 file_id
    // （后端 formal+use_existing 校验禁止携带，携带即 BAD_PARAM）
    if (!existing) {
      body.file_id = state.fileId;
    }

    // full 模式含 LLM 调用：先取事前费用预估做确认弹层（预估失败不阻塞）；
    // 超日预算时须显式确认（budget_ack + 用已有结果）才能提交
    if (body.report_type === 'full') {
      confirmCostForecast(body.llm_modules).then(function (decision) {
        if (!decision.proceed) {
          resetGenerateBtn();
          return;
        }
        if (decision.budgetAck) {
          body.budget_ack = true;
        }
        if (decision.forceDowngraded) {
          body.force_llm = false;
          body.llm_modules = null;
        }
        submitRun(body);
      });
      return;
    }
    submitRun(body);
  }

  function resetGenerateBtn() {
    els.generateBtn.removeAttribute('aria-busy');
    updateGenerateBtn();
    els.generateBtn.textContent = '生成报告';
  }

  /* ── 事前费用预估确认弹层（native confirm；预估失败/无模块/网络失败 → 不阻塞继续）── */
  function confirmCostForecast(modules) {
    // 重新生成范围透传预检：选了模块时预估按所选范围重估（与提交 body 同源）
    var qs = '/api/runs/cost-preflight?report_type=full';
    if (modules && modules.length) {
      qs += '&llm_modules=' + encodeURIComponent(modules.join(','));
    }
    return fetch(qs, {
      signal: AbortSignal.timeout(8000),
    })
      .then(function (res) {
        if (!res.ok) {
          return null;
        }
        return res.json();
      })
      .then(function (j) {
        return j && j.data ? j.data : null;
      })
      .then(function (data) {
        var f = data && data.forecast;
        var b = data && data.budget;
        if (!f || !f.ok || !f.module_count) {
          return { proceed: true };
        }
        // 费用一律用后端格式化好的展示串（分币种并列 `¥0.0123 + $0.0045`）：
        // 前端不再自拼符号与数值，避免各币种各写一遍格式化规则而漂移。
        var lines = '本次生成 LLM 费用预估 ' + (f.cost_display || '—') +
          '（计划 ' + f.module_count + ' 个模块）';
        if (f.forced_count) {
          lines += '\n其中 ' + f.forced_count + ' 个模块重新生成：' +
            (f.forced_cost_display || '—');
        }
        if (b && b.display) {
          lines += '\n' + b.display;
        }
        if (b && b.exceeded) {
          if (!window.confirm('[!] ' + lines + '\n\n今日已超日预算。确定「用已有结果继续」？')) {
            return { proceed: false };
          }
          return { proceed: true, budgetAck: true, forceDowngraded: true };
        }
        if (!window.confirm('[..] ' + lines + '\n\n继续生成？')) {
          return { proceed: false };
        }
        return { proceed: true };
      })
      .catch(function () {
        return { proceed: true };
      });
  }

  function submitRun(body) {
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (data) {
        state.runId = data.run_id;
        state.lastSeq = 0;
        saveRunId(data.run_id);
        els.generateBtn.textContent = '生成中...';
        showProgress();
        startPolling();
      })
      .catch(function (err) {
        els.generateBtn.removeAttribute('aria-busy');
        updateGenerateBtn();
        els.generateBtn.textContent = '生成报告';
        if (err.errorCode === 'FILE_EXPIRED') {
          // 上传文件已过期/服务重启：重置流程引导重新上传
          resetFlow(err.message);
          return;
        }
        // HOLDINGS_MISSING 等运行期错误：文案直显服务端中文，不前端映射
        els.generateError.textContent = err.message;
      });
  }

  /* ── 进度轮询 ── */
  function showProgress() {
    els.progressSection.hidden = false;
    els.resultSection.hidden = true;
    els.progressEvents.textContent = '';
    els.progressPhase.textContent = '准备中...';
    els.progressBar.style.width = '0%';
    els.progressBar.setAttribute('aria-valuenow', '0');
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
    pollOnce();
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  /* 生成按钮与上传态复位（生成完成与流程重置共用单源）：上传文件已随 run 消费
   * 清理 → 试算/正式-上传清 file_id 后由 updateGenerateBtn() 判定并提示重新上传；
   * 正式-用存量免上传，复位后立即可再次生成（换格式再生成同入口） */
  function restoreGenerateBtn(message) {
    els.generateBtn.removeAttribute('aria-busy');
    state.fileId = null;
    state.uploadInfo = null;
    els.fileInput.value = '';
    updateGenerateBtn();
    els.generateBtn.textContent = '生成报告';
    if (isFormalExisting()) {
      setStatus(els.uploadStatus, '可直接重新生成（读取当前正式持仓文件）', 'ok');
    } else {
      setStatus(els.uploadStatus, message || '持仓文件已随本次生成消费，如需再次生成请重新上传', 'busy');
    }
  }

  /* ── 活动 run 会话标记（sessionStorage）：刷新/误关重开页面续轮询 ──
   * 存储不可用（隐私模式等）只放弃恢复，不影响主流程 */
  function saveRunId(runId) {
    try {
      sessionStorage.setItem(RUN_ID_KEY, runId);
    } catch (e) {
      /* 放弃持久化 */
    }
  }

  function loadRunId() {
    try {
      return sessionStorage.getItem(RUN_ID_KEY);
    } catch (e) {
      return null;
    }
  }

  function clearRunId() {
    try {
      sessionStorage.removeItem(RUN_ID_KEY);
    } catch (e) {
      /* 放弃清理 */
    }
  }

  /* 断点续轮询：加载时若 sessionStorage 中有活动 run，重建进度视图并续轮询 */
  function resumeActiveRun() {
    var runId = loadRunId();
    if (!runId) {
      return;
    }
    state.runId = runId;
    state.lastSeq = 0;
    els.generateBtn.setAttribute('aria-busy', 'true');
    els.generateBtn.textContent = '生成中...';
    showProgress();
    startPolling();
  }

  function pollOnce() {
    // 在途互斥：上一轮 fetch 未返回时跳过本 tick（响应超时 10s > 间隔 2s，
    // 并发堆叠会造成同一批事件重复渲染与重复计数）
    if (state.pollBusy) {
      return;
    }
    state.pollBusy = true;
    var req;
    try {
      req = fetch('/api/runs/' + encodeURIComponent(state.runId) + '/events?after=' + state.lastSeq, {
        signal: AbortSignal.timeout(10000),
      });
    } catch (syncErr) {
      state.pollBusy = false;
      return;
    }
    req
      .then(handleResponse)
      .then(function (data) {
        state.pollBusy = false;
        // 缺口判定：first_seq 为服务端仍保留的最小序号，大于已读+1 说明中间事件
        // 已被缓冲上限淘汰——插入省略占位并前移 lastSeq，不静默跳号
        var firstSeq = data.first_seq;
        if (typeof firstSeq === 'number' && firstSeq > state.lastSeq + 1) {
          appendGapNotice(firstSeq - state.lastSeq - 1);
          state.lastSeq = firstSeq - 1;
        }
        // 序号过滤：只回放 seq 大于已读序号的事件（防在途重叠/重复响应重复渲染）
        appendEvents(
          (data.events || []).filter(function (ev) {
            return ev.seq > state.lastSeq;
          })
        );
        if (data.last_seq > state.lastSeq) {
          state.lastSeq = data.last_seq;
        }
        if (data.status === 'done' || data.status === 'failed') {
          stopPolling();
          clearRunId();
          restoreGenerateBtn();
          loadResult();
        }
      })
      .catch(function (err) {
        state.pollBusy = false;
        // 任务不存在（服务重启后内存 run 注册表清空）：终态处理——停止轮询、单源
        // 复位生成按钮并渲染结果区，否则 404 被当瞬时错误无限重试、界面永久卡在进行中
        if (err && (err.httpStatus === 404 || err.errorCode === 'NOT_FOUND')) {
          stopPolling();
          clearRunId();
          restoreGenerateBtn();
          els.progressPhase.textContent = '任务已失效';
          renderResultState(2, ['任务已不存在（服务可能已重启），请刷新页面后重新生成'], []);
          return;
        }
        // 轮询瞬时失败静默，下一周期重试（网络抖动不中断流程）
      });
  }

  function appendEvents(events) {
    events.forEach(function (ev) {
      var li = document.createElement('li');
      li.className = 'event event-' + ev.level;
      var num = document.createElement('span');
      num.className = 'event-seq';
      num.textContent = String(ev.seq);
      var icon = document.createElement('span');
      icon.className = 'event-icon';
      icon.textContent = eventIcon(ev.level);
      var text = document.createElement('span');
      text.textContent = ev.message;
      li.appendChild(num);
      li.appendChild(icon);
      li.appendChild(text);
      els.progressEvents.appendChild(li);
    });
    var last = events[events.length - 1];
    if (last) {
      // 阶段名 + 序号：以事件消息为当前阶段描述，seq 为步序
      els.progressPhase.textContent = '当前阶段（第 ' + last.seq + ' 步）：' + last.message;
    }
    // 无总步数，按已见步骤数估算（封顶 90%，完成时置 100%）
    var pct = Math.min(90, els.progressEvents.children.length);
    els.progressBar.style.width = pct + '%';
    els.progressBar.setAttribute('aria-valuenow', String(pct));
    els.progressEvents.scrollTop = els.progressEvents.scrollHeight;
  }

  /* 事件缺口占位行：说明被缓冲上限淘汰的中间事件条数（不静默跳号） */
  function appendGapNotice(count) {
    var li = document.createElement('li');
    li.className = 'event event-gap';
    var num = document.createElement('span');
    num.className = 'event-seq';
    num.textContent = '…';
    var text = document.createElement('span');
    text.textContent = '中间已省略 ' + count + ' 条进度事件（超出事件缓冲上限）';
    li.appendChild(num);
    li.appendChild(text);
    els.progressEvents.appendChild(li);
  }

  function eventIcon(level) {
    if (level === 'ok') {
      return '✓';
    }
    if (level === 'warn') {
      return '!';
    }
    if (level === 'error') {
      return '✕';
    }
    return '·';
  }

  /* ── 结果 ── */
  function loadResult() {
    fetch('/api/runs/' + encodeURIComponent(state.runId), {
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (data) {
        if (data.status === 'done') {
          els.progressBar.style.width = '100%';
          els.progressBar.setAttribute('aria-valuenow', '100');
          els.progressPhase.textContent = '全部完成';
          renderResultState(data.exit_code, data.errors || [], data.artifacts || []);
        } else {
          renderResultState(
            2,
            data.errors && data.errors.length ? data.errors : ['任务执行失败（详情请查看日志）'],
            []
          );
        }
      })
      .catch(function (err) {
        renderResultState(2, [err.message], []);
      });
  }

  function renderResultState(exitCode, errors, artifacts) {
    els.resultActions.textContent = '';
    els.resultErrors.textContent = '';
    els.resultFooter.textContent = '';

    var badge = document.createElement('p');
    badge.className = 'result-badge result-badge-' + (exitCode === 0 ? 'ok' : exitCode === 1 ? 'warn' : 'error');
    badge.textContent = exitCode === 0 ? '报告生成成功' : exitCode === 1 ? '报告已生成，部分模块遇到问题' : '报告生成失败';
    els.resultErrors.appendChild(badge);

    if (errors.length) {
      var list = document.createElement('ul');
      errors.forEach(function (msg) {
        var li = document.createElement('li');
        li.textContent = msg;
        list.appendChild(li);
      });
      els.resultErrors.appendChild(list);
    }

    if (exitCode === 1) {
      var tip = document.createElement('p');
      tip.className = 'result-tip';
      tip.textContent = '提示：部分数据源暂不可用或模块未完成，已生成的结果可正常预览/下载，可稍后重新生成重试。';
      els.resultErrors.appendChild(tip);
    } else if (exitCode === 2) {
      var tip2 = document.createElement('p');
      tip2.className = 'result-tip';
      tip2.textContent = '提示：请查看日志 logs/app.log 了解详情，稍后重试。';
      els.resultErrors.appendChild(tip2);
      var retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'btn btn-primary';
      retry.textContent = '重新生成';
      retry.addEventListener('click', function () {
        // 上传文件已随 run 消费清理，重新生成需重新上传
        resetFlow('重新生成请重新上传持仓文件');
      });
      els.resultFooter.appendChild(retry);
    }

    renderArtifacts(artifacts);
    els.resultSection.hidden = false;
  }

  function renderArtifacts(artifacts) {
    if (!artifacts.length) {
      return;
    }
    artifacts.forEach(function (a) {
      var url = '/api/reports/' + encodeURIComponent(a.path);
      if (a.kind === 'html') {
        var preview = document.createElement('a');
        preview.className = 'btn btn-primary';
        preview.textContent = '预览 ' + a.name;
        preview.href = url;
        preview.target = '_blank';
        preview.rel = 'noopener';
        els.resultActions.appendChild(preview);
      }
      var download = document.createElement('a');
      download.className = 'btn btn-secondary';
      download.textContent = '下载 ' + a.name;
      download.href = url;
      download.download = a.path;
      els.resultActions.appendChild(download);

      // 服务端绝对路径可复制（Web 与报告不一定同机，「打开目录」无意义；
      // 给路径让用户在本机文件管理器/终端里定位，三渠道信息面一致）
      if (a.path) {
        var pathText = document.createElement('code');
        pathText.className = 'artifact-path';
        pathText.textContent = a.path;
        pathText.title = '点击复制路径';
        pathText.style.cursor = 'pointer';
        pathText.addEventListener('click', function () {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(a.path);
            pathText.textContent = '已复制: ' + a.path;
            setTimeout(function () { pathText.textContent = a.path; }, 1500);
          }
        });
        els.resultActions.appendChild(pathText);
      }
    });
  }

  function resetFlow(message) {
    stopPolling();
    state.runId = null;
    state.lastSeq = 0;
    clearRunId();
    els.progressSection.hidden = true;
    els.resultSection.hidden = true;
    els.generateError.textContent = '';
    // 试算/正式-上传：上传文件已随 run 消费清理，需重新上传；
    // 正式-用存量：无需上传，直接重新生成（提示与焦点均不指向重新上传）
    restoreGenerateBtn(message);
    if (!isFormalExisting()) {
      els.fileInput.focus();
    }
  }

  /* 加载器隔离运行：捕获初始化阶段同步异常，把对应面板渲染成可见错误，
   * 避免一个加载器抛错中断 init 其余加载器（fetch 参数构造同步抛错场景）。 */
  function safeRun(fn, args, errEl, errText) {
    try {
      fn.apply(null, args || []);
    } catch (e) {
      errEl.textContent = '';
      var p = document.createElement('p');
      p.className = 'status-text status-error';
      p.textContent = errText;
      errEl.appendChild(p);
    }
  }

  /* ── 状态区：数据源健康 ── */
  function loadHealth(fresh) {
    els.healthList.textContent = '';
    var busy = document.createElement('p');
    busy.className = 'status-text status-busy';
    busy.textContent = fresh ? '重新检测中...' : '正在检测...';
    els.healthList.appendChild(busy);

    fetch('/api/health' + (fresh ? '?fresh=1' : ''), {
      signal: AbortSignal.timeout(15000),
    })
      .then(handleResponse)
      .then(function (results) {
        renderHealth(results || []);
      })
      .catch(function () {
        els.healthList.textContent = '';
        var p = document.createElement('p');
        p.className = 'status-text status-error';
        p.textContent = '健康检测失败，请稍后重试';
        els.healthList.appendChild(p);
      });
  }

  function renderHealth(results) {
    els.healthList.textContent = '';
    if (!results.length) {
      var p = document.createElement('p');
      p.className = 'status-text status-busy empty-note';
      p.textContent = '暂无数据源检测结果';
      els.healthList.appendChild(p);
      return;
    }
    results.forEach(function (item) {
      if (item.hint) {
        // 代理诊断提示：全灭且多数连接被拒时，服务端追加一条整卡提示
        var note = document.createElement('div');
        note.className = 'health-hint';
        note.textContent = item.message;
        els.healthList.appendChild(note);
        return;
      }
      var row = document.createElement('div');
      row.className = 'health-row ' + (item.ok ? 'health-ok' : 'health-err');
      var name = document.createElement('span');
      name.className = 'health-name';
      name.textContent = item.label || item.name;
      var status = document.createElement('span');
      status.className = 'health-status';
      status.textContent = item.ok ? '正常' : '异常';
      var meta = document.createElement('span');
      meta.className = 'health-meta';
      meta.textContent = item.ok ? item.latency_ms + 'ms' : (item.message || '不可用');
      row.appendChild(name);
      row.appendChild(status);
      row.appendChild(meta);
      els.healthList.appendChild(row);
    });
  }

  /* ── 状态区：系统自检（doctor_check 关闭时卡片不存在，整段跳过） ── */
  function loadDoctor() {
    if (!els.doctorList) return;
    els.doctorList.textContent = '';
    var busy = document.createElement('p');
    busy.className = 'status-text status-busy';
    busy.textContent = '自检中（含数据源联网检查，最多约 12 秒）...';
    els.doctorList.appendChild(busy);
    els.doctorRun.disabled = true;

    fetch('/api/doctor', { signal: AbortSignal.timeout(15000) })
      .then(handleResponse)
      .then(function (data) {
        renderDoctor(data || {});
      })
      .catch(function () {
        els.doctorList.textContent = '';
        var p = document.createElement('p');
        p.className = 'status-text status-error';
        p.textContent = '系统自检失败，请稍后重试';
        els.doctorList.appendChild(p);
      })
      .finally(function () {
        els.doctorRun.disabled = false;
      });
  }

  function renderDoctor(data) {
    els.doctorList.textContent = '';
    var results = data.results || [];
    if (!results.length) {
      var p = document.createElement('p');
      p.className = 'status-text status-busy empty-note';
      p.textContent = '无自检结果';
      els.doctorList.appendChild(p);
      return;
    }
    var currentGroup = null;
    results.forEach(function (item) {
      if (item.group !== currentGroup) {
        currentGroup = item.group;
        var head = document.createElement('div');
        head.className = 'doctor-group';
        head.textContent = currentGroup;
        els.doctorList.appendChild(head);
      }
      var row = document.createElement('div');
      row.className = 'health-row ' + (item.ok ? 'health-ok' : 'health-err');
      var name = document.createElement('span');
      name.className = 'health-name';
      name.textContent = item.label;
      var status = document.createElement('span');
      status.className = 'health-status';
      status.textContent = item.ok ? '正常' : '异常';
      var meta = document.createElement('span');
      meta.className = 'health-meta';
      meta.textContent = item.message;
      row.appendChild(name);
      row.appendChild(status);
      row.appendChild(meta);
      els.doctorList.appendChild(row);
      // 失败项附修复建议——自检的价值一半在「告诉用户下一步做什么」
      if (!item.ok && item.hint) {
        var hint = document.createElement('div');
        hint.className = 'doctor-hint';
        hint.textContent = '→ ' + item.hint;
        els.doctorList.appendChild(hint);
      }
    });
    var summary = document.createElement('p');
    summary.className = 'status-text ' + (data.bad_count ? 'status-error' : 'status-ok');
    summary.textContent = '共 ' + results.length + ' 项 — 通过 ' + data.ok_count + ' / 未通过 ' + data.bad_count;
    els.doctorList.appendChild(summary);
  }

  /* ── ⑦ 日志查看：手动加载 + 级别筛选 + 原生折叠展示 ──
   * 日志可能很大，仅用户点「加载日志」才请求（不自动轮询，对齐设计文档
   * 「自动刷新高 IO → 需手动刷新」）。渲染全 textContent/DOM API，
   * 服务端返回的日志正文（含数据源名等不可信内容）不进 innerHTML。
   */
  function loadLogs() {
    var level = els.logLevel.value;
    var params = new URLSearchParams();
    if (level) {
      params.append('level', level);
    }
    var qs = params.toString();
    setStatus(els.logStatus, '加载中...', 'busy');
    fetch('/api/logs' + (qs ? '?' + qs : ''), {
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (entries) {
        renderLogs(entries || []);
        setStatus(els.logStatus, '共 ' + entries.length + ' 条', 'ok');
      })
      .catch(function (err) {
        setStatus(els.logStatus, err.message, 'error');
        renderLogs([]);
      });
  }

  function renderLogs(entries) {
    els.logList.textContent = '';
    if (!entries.length) {
      var p = document.createElement('p');
      p.className = 'status-text status-busy empty-note';
      p.textContent = '暂无匹配日志';
      els.logList.appendChild(p);
      return;
    }
    entries.forEach(function (entry) {
      var levelCls = entry.level ? entry.level.toLowerCase() : 'info';
      var details = document.createElement('details');
      details.className = 'log-entry log-' + levelCls;
      if (entry.is_decorative) {
        details.classList.add('log-decorative');
      }
      var summary = document.createElement('summary');
      summary.textContent = entry.time + ' [' + entry.level + '] ' + entry.message;
      details.appendChild(summary);
      var body = document.createElement('pre');
      body.className = 'log-body';
      body.textContent = entry.body;
      details.appendChild(body);
      els.logList.appendChild(details);
    });
    els.logList.scrollTop = 0;
  }

  /* ── 状态区：最近运行（单行摘要，聚焦错误痕迹与耗时）── */
  function loadHistory() {
    fetch('/api/runs/history', {
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (records) {
        renderHistory(records || []);
      })
      .catch(function () {
        els.historyList.textContent = '';
        var p = document.createElement('p');
        p.className = 'status-text status-error';
        p.textContent = '历史记录加载失败';
        els.historyList.appendChild(p);
      });
  }

  function renderHistory(records) {
    els.historyList.textContent = '';
    if (!records.length) {
      var p = document.createElement('p');
      p.className = 'status-text status-busy empty-note';
      p.textContent = '暂无运行记录';
      els.historyList.appendChild(p);
      return;
    }
    // 单行摘要：时间 + 状态（成功/有异常）+ 耗时。错误痕迹与耗时是历史记录
    // 的真正价值，类型/条数对单用户自用属装饰字段，已弱化掉。
    var rec = records[0];
    var row = document.createElement('div');
    row.className = 'history-summary';
    var when = document.createElement('span');
    when.className = 'history-time';
    when.textContent = formatTs(rec.timestamp);
    var hasErr = !!(rec.errors && rec.errors.length);
    var status = document.createElement('span');
    status.className = 'history-status ' + (hasErr ? 'history-status-err' : 'history-status-ok');
    status.textContent = hasErr ? '有异常' : '成功';
    var meta = document.createElement('span');
    meta.className = 'history-meta';
    meta.textContent = formatDur(rec.total_seconds);
    row.appendChild(when);
    row.appendChild(status);
    row.appendChild(meta);
    els.historyList.appendChild(row);
  }

  function formatTs(ts) {
    if (!ts) {
      return '-';
    }
    var d = new Date(ts);
    if (isNaN(d.getTime())) {
      return String(ts);
    }
    function pad(n) {
      return n < 10 ? '0' + n : String(n);
    }
    return (
      d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
      ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
    );
  }

  function formatDur(sec) {
    var s = Math.round(Number(sec) || 0);
    if (s < 60) {
      return s + '秒';
    }
    var m = Math.floor(s / 60);
    var r = s % 60;
    if (m < 60) {
      return r ? m + '分' + r + '秒' : m + '分钟';
    }
    return Math.floor(m / 60) + '时' + (m % 60) + '分';
  }

  /* ── 配置编辑（与 TUI 菜单一致，即改即存）──
   * GET /api/config/edit 载入全量可编辑面 → 按服务端分块渲染（路径/报告章节/功能开关四组/匿名化/对比指数/LLM）。
   * 保存语义即改即存（与 TUI「改一项存一项」一致）：checkbox/radio 改动即
   * POST /api/config/edit；自由文本路径经各自「保存」按钮提交；对比指数池经
   * 添加/删除/重置动作提交。提交期间该控件禁用，成功回读该项最新值，失败
   * 恢复为改动前值并显示错误。
   * error_code 驱动分支（中文文案直显服务端，不前端硬编码映射）：
   *   BAD_PARAM(400) → 该分组错误区直显服务端中文；
   *   BAD_PARAM(403) → 面板顶部警示同源失败；
   *   CONFIG_WRITE_FAILED(500) → 分组错误区提示查看日志。
   * XSS 纪律：全部 textContent/DOM API 渲染，禁止 innerHTML。
   */
  var configState = { surface: null };

  // 文案零硬编码：控件标签 / 说明 / 默认值 / 匿名化档位描述全部由服务端
  // /api/config/edit 的 labels / descriptions / defaults / anonymization.labels 下发，
  // 前端不持有任何中文表（与 TUI 同一批条目名，避免两处漂移）。

  function loadConfigEdit() {
    els.configPanel.textContent = '';
    var busy = document.createElement('p');
    busy.className = 'status-text status-busy';
    busy.textContent = '正在加载配置...';
    els.configPanel.appendChild(busy);
    fetch('/api/config/edit', { signal: AbortSignal.timeout(10000) })
      .then(handleResponse)
      .then(renderConfigEdit)
      .catch(function () {
        els.configPanel.textContent = '';
        var p = document.createElement('p');
        p.className = 'status-text status-error';
        p.textContent = '配置加载失败，请稍后重试';
        els.configPanel.appendChild(p);
      });
  }

  // 块 id → 渲染器（`features.<组键>` 由 `renderFeatureBlock` 统一承接）。
  // 契约：`domains[].blocks` 里出现的每个块都必须在此有渲染器（服务端契约测试双向断言）。
  var BLOCK_RENDERERS = {
    paths: function (surface) {
      return renderPathsGroup(surface);
    },
    sections: function (surface) {
      return renderBoolBlock(surface, 'sections', surface.sections);
    },
    llm: function (surface) {
      return renderBoolBlock(surface, 'llm', surface.llm.enabled_llm, { prefix: 'enabled_llm.' });
    },
    standalone_chapters: function (surface) {
      return renderBoolBlock(surface, 'standalone_chapters', surface.standalone_chapters);
    },
    standalone_related: function (surface) {
      return renderBoolBlock(surface, 'standalone_related', surface.standalone_related);
    },
    anonymization: function (surface) {
      return renderAnonGroup(surface);
    },
    indices: function (surface) {
      return renderIndicesGroup(surface);
    },
    providers: function (surface) {
      return renderProvidersGroup(surface);
    },
    tuning: function (surface) {
      return renderTuningGroup(surface);
    },
    logging: function (surface) {
      return renderLoggingBlock(surface);
    },
    reference: function (surface) {
      return renderReferenceBlock(surface);
    }
  };

  function rendererFor(block, surface) {
    if (block.indexOf('features.') === 0) {
      return renderFeatureBlock(surface, block.slice('features.'.length));
    }
    var fn = BLOCK_RENDERERS[block];
    return fn ? fn(surface) : null;
  }

  function renderConfigEdit(surface) {
    configState.surface = surface;
    configState.query = '';
    els.configPanel.textContent = '';
    // 面板顶部警示区（同源失败 403 专用）
    var panelErr = document.createElement('p');
    panelErr.id = 'config-panel-error';
    panelErr.className = 'status-text status-error';
    panelErr.setAttribute('role', 'alert');
    panelErr.hidden = true;
    els.configPanel.appendChild(panelErr);

    var toolbar = renderConfigToolbar();
    els.configPanel.appendChild(toolbar);
    els.configPanel.appendChild(renderDomainChips(surface.domains || []));

    // 域即分区：一级分区与块顺序全部由服务端 domains 决定，前端只做渲染与分派
    (surface.domains || []).forEach(function (domain) {
      var section = renderDomainSection(domain, surface);
      if (section) {
        els.configPanel.appendChild(section);
      }
    });

    refreshConfigStats();
    observeDomains();
    focusDomainFromHash();
  }

  /**
   * 工具条：项数 / 已改数 / 关键词筛选（与 TUI 的「面板内查询 + 状态统计」等价表达）。
   * 计数基准是服务端下发的 `defaults`，前端不自行推算出厂值。
   */
  function renderConfigToolbar() {
    var bar = document.createElement('div');
    bar.className = 'config-toolbar';
    var title = document.createElement('h2');
    title.className = 'config-toolbar-title';
    title.textContent = '配置';
    bar.appendChild(title);

    var stats = document.createElement('span');
    stats.id = 'config-stats';
    stats.className = 'config-toolbar-stats';
    stats.setAttribute('role', 'status');
    stats.textContent = '加载中…';
    bar.appendChild(stats);

    var filter = document.createElement('input');
    filter.type = 'search';
    filter.id = 'config-filter';
    filter.className = 'config-filter';
    filter.placeholder = '筛选：标签 / 说明 / 键名';
    filter.setAttribute('aria-label', '筛选配置项');
    filter.addEventListener('input', function () {
      configState.query = filter.value.trim();
      applyConfigFilter();
    });
    bar.appendChild(filter);
    return bar;
  }

  /** 域导航（chips）：点击直达分区并写 `#domain-<key>`；滚动时高亮当前域。 */
  function renderDomainChips(domains) {
    var nav = document.createElement('nav');
    nav.className = 'chips';
    nav.id = 'config-domain-nav';
    nav.setAttribute('aria-label', '配置域导航');
    domains.forEach(function (domain) {
      var chip = document.createElement('a');
      chip.href = '#domain-' + domain.key;
      chip.className = 'chip';
      chip.dataset.domain = domain.key;
      chip.textContent = domain.title || domain.key;
      chip.addEventListener('click', function (e) {
        e.preventDefault();
        scrollToDomain(domain.key, true);
      });
      nav.appendChild(chip);
    });
    return nav;
  }

  function scrollToDomain(key, updateHash) {
    var section = document.getElementById('domain-' + key);
    if (!section) {
      return;
    }
    if (section.scrollIntoView) {
      section.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
    if (updateHash !== false) {
      window.history.replaceState(null, '', '#domain-' + key);
    }
  }

  /** 深链：`#domain-<key>` → 切到配置页并滚到该域（与标签页 hash 共存）。 */
  function focusDomainFromHash() {
    var hash = (window.location.hash || '').slice(1);
    if (hash.indexOf('domain-') !== 0) {
      return;
    }
    scrollToDomain(hash.slice('domain-'.length), false);
  }

  /** 滚动高亮：可见域中取最靠上的一个置为 active（无 IntersectionObserver 时降级为不亮）。 */
  function observeDomains() {
    if (!('IntersectionObserver' in window)) {
      return;
    }
    if (configState.domainObserver) {
      configState.domainObserver.disconnect();
    }
    configState.domainObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) {
            return;
          }
          var key = entry.target.id.replace('domain-', '');
          document.querySelectorAll('#config-domain-nav .chip').forEach(function (chip) {
            chip.classList.toggle('active', chip.dataset.domain === key);
          });
        });
      },
      { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
    );
    document.querySelectorAll('.config-domain').forEach(function (section) {
      configState.domainObserver.observe(section);
    });
  }

  /** 计数：总项数与「已改 N 项」（当前值 ≠ 服务端 defaults），并同步块计数。 */
  function refreshConfigStats() {
    var surface = configState.surface || {};
    var defaults = surface.defaults || {};
    var total = 0;
    var changed = 0;
    document.querySelectorAll('#config-panel [data-config-key]').forEach(function (control) {
      var key = control.dataset.configKey;
      var current;
      if (control.type === 'checkbox' || control.type === 'radio') {
        current = control.checked;
      } else {
        current = control.type === 'number' ? Number(control.value) : control.value;
      }
      total += 1;
      if (Object.prototype.hasOwnProperty.call(defaults, key) && String(current) !== String(defaults[key])) {
        changed += 1;
      }
    });
    var stats = document.getElementById('config-stats');
    if (stats) {
      stats.textContent = '共 ' + total + ' 项 · 已改 ' + changed + ' 项';
    }
    refreshBlockCounts();
  }

  /** 每块标题旁的 `N 项 · M 开`（枚举/集合类块退化为 `N 项`）。 */
  function refreshBlockCounts() {
    document.querySelectorAll('#config-panel .config-group').forEach(function (group) {
      var meta = group.querySelector('.config-block-meta');
      if (!meta) {
        return;
      }
      var boxes = group.querySelectorAll('input[type="checkbox"]');
      if (boxes.length) {
        var on = 0;
        boxes.forEach(function (cb) {
          if (cb.checked) {
            on += 1;
          }
        });
        meta.textContent = boxes.length + ' 项 · ' + on + ' 开';
        return;
      }
      var others = group.querySelectorAll('.config-row, .field, .config-path-row, .ref-row');
      meta.textContent = others.length + ' 项';
    });
  }

  /** 关键词筛选：匹配标签/说明/键名；空块与空域隐藏，清空即恢复。 */
  function applyConfigFilter() {
    var query = (configState.query || '').toLowerCase();
    document.querySelectorAll('#config-panel .config-domain').forEach(function (section) {
      var visibleBlocks = 0;
      section.querySelectorAll('.config-group').forEach(function (group) {
        var visibleRows = 0;
        group.querySelectorAll('.config-row, .config-path-row, .field, .ref-row').forEach(function (row) {
          var control = row.querySelector('[data-config-key]');
          var text = (row.textContent || '').toLowerCase();
          var key = control ? String(control.dataset.configKey).toLowerCase() : '';
          var hit = !query || text.indexOf(query) !== -1 || key.indexOf(query) !== -1;
          row.classList.toggle('hidden', !hit);
          if (hit) {
            visibleRows += 1;
          }
        });
        var hasBody = group.querySelectorAll('.config-row, .config-path-row, .field, .ref-row').length > 0;
        // 无可筛选行的块（如只读参考块内单行）保持可见，避免筛选时整块消失
        var show = !query || visibleRows > 0 || !hasBody;
        group.classList.toggle('hidden', !show);
        if (show) {
          visibleBlocks += 1;
        }
      });
      section.classList.toggle('hidden', visibleBlocks === 0);
    });
  }

  /** 域分区（标题 + 说明 + TUI 导引 + 块）：域内块全空则该域不出现。 */
  function renderDomainSection(domain, surface) {
    var blocks = (domain.blocks || [])
      .map(function (block) {
        return rendererFor(block, surface);
      })
      .filter(function (el) {
        return !!el;
      });
    if (!blocks.length) {
      return null;
    }
    var section = document.createElement('section');
    section.className = 'config-domain';
    section.id = 'domain-' + domain.key; // 深链锚点 #domain-<key>
    var heading = document.createElement('h2');
    heading.className = 'domain-title';
    heading.textContent = domain.title || domain.key;
    section.appendChild(heading);
    if (domain.hint) {
      var hint = document.createElement('p');
      hint.className = 'domain-hint';
      hint.textContent = domain.hint;
      section.appendChild(hint);
    }
    if (domain.tui) {
      var tui = document.createElement('p');
      tui.className = 'domain-tui';
      tui.textContent = domain.tui;
      section.appendChild(tui);
    }
    blocks.forEach(function (el) {
      section.appendChild(el);
    });
    return section;
  }

  /** 功能开关的章内内容组（`features.<组键>`）：组标题与「影响报告」标记由服务端下发。 */
  function renderFeatureBlock(surface, groupKey) {
    var group = (surface.features.groups || []).find(function (item) {
      return item.key === groupKey;
    });
    if (!group) {
      return null;
    }
    return renderBoolBlock(surface, 'features_' + groupKey, group.switches, {
      title: group.title,
      experimental: surface.features.experimental,
      reportAffecting: surface.features.report_affecting,
      note: groupKey === 'portfolio' ? '关闭「影响报告」的开关会改变报告产物内容；其余开关只影响入口显隐' : null
    });
  }

  /**
   * LLM 调优参数（并发/预算/重试）：清单、范围、说明全部由服务端按共享白名单下发。
   * 保存走同一 POST /api/config/edit（校验在 config.edit_ops，三渠道同一强度）。
   */
  function renderTuningGroup(surface) {
    var items = surface.llm_tuning || [];
    var group = document.createElement('div');
    group.className = 'config-group';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', 'LLM 调优参数');
    var heading = document.createElement('h3');
    heading.className = 'config-group-title';
    heading.textContent = (surface.block_titles || {}).tuning || 'LLM 运行参数';
    group.appendChild(heading);

    items.forEach(function (item) {
      var row = document.createElement('div');
      row.className = 'config-path-row';
      var label = document.createElement('label');
      label.className = 'check-label';
      label.textContent = item.label;
      label.htmlFor = 'config-tuning-' + item.key;
      var input = document.createElement('input');
      input.type = 'number';
      input.id = 'config-tuning-' + item.key;
      input.value = item.value;
      input.min = item.min;
      input.max = item.max;
      input.step = item.step;
      input.dataset.configKey = item.key;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary';
      btn.textContent = '保存';
      btn.addEventListener('click', function () {
        var key = item.key;
        var prev = item.value;
        clearGroupError(group);
        postConfigEdit({ key: key, value: input.value })
          .then(function (data) {
            item.value = data.value;
            input.value = data.value;
          })
          .catch(function (err) {
            input.value = prev;
            showGroupError(group, err);
          });
      });
      row.appendChild(label);
      row.appendChild(input);
      row.appendChild(btn);
      if (item.hint) {
        var hint = document.createElement('p');
        hint.className = 'config-note-sub';
        hint.textContent = item.hint;
        row.appendChild(hint);
      }
      group.appendChild(row);
    });
    return group;
  }

  function renderPathsGroup(surface) {
    var paths = surface.paths || {};
    var group = makeBlockGroup('paths', (surface.block_titles || {}).paths || '目录与文件');
    Object.keys(paths).forEach(function (key) {
      var row = document.createElement('div');
      row.className = 'config-path-row';
      var label = document.createElement('label');
      label.className = 'config-path-label';
      label.textContent = (surface.labels[key] || key) + '：';
      label.htmlFor = 'config-input-' + key;
      var input = document.createElement('input');
      input.type = 'text';
      input.id = 'config-input-' + key;
      input.value = paths[key] || '';
      input.spellcheck = false;
      input.autocomplete = 'off';
      var saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.className = 'btn btn-secondary btn-sm config-save';
      saveBtn.textContent = '保存';
      saveBtn.addEventListener('click', onPathSave);
      var status = document.createElement('span');
      status.className = 'config-row-status';
      status.setAttribute('role', 'status');
      row.appendChild(label);
      row.appendChild(input);
      row.appendChild(saveBtn);
      row.appendChild(status);
      group.appendChild(row);
      var desc = surface.descriptions[key];
      if (desc) {
        group.appendChild(makeConfigDesc(desc));
      }
    });
    group.appendChild(makeGroupErrorEl());
    return group;
  }

  /** 块容器（标题 + role=group）：块标题取结构色（与 TUI 分组标题同色调）。 */
  function makeBlockGroup(blockKey, title) {
    var group = document.createElement('div');
    group.className = 'config-group';
    group.setAttribute('role', 'group');
    group.id = 'config-block-' + blockKey;
    var heading = document.createElement('h3');
    heading.id = 'config-group-' + blockKey;
    heading.className = 'config-group-title';
    heading.textContent = title;
    var meta = document.createElement('span');
    meta.className = 'config-block-meta';
    heading.appendChild(meta);
    group.appendChild(heading);
    group.setAttribute('aria-labelledby', heading.id);
    return group;
  }

  /**
   * 项说明副行（服务端 descriptions 下发）。
   *
   * @param {string} text 说明文本
   * @param {boolean} [flush] 表单类块为 true——说明与字段左缘对齐（不缩进到控件文字列）
   */
  function makeConfigDesc(text, flush) {
    var desc = document.createElement('p');
    desc.className = flush ? 'config-desc config-desc-flush' : 'config-desc';
    desc.textContent = text;
    return desc;
  }

  function renderBoolBlock(surface, blockKey, items, opts) {
    opts = opts || {};
    var titles = surface.block_titles || {};
    var group = makeBlockGroup(blockKey, opts.title || titles[blockKey] || blockKey);
    var labels = surface.labels;
    var descriptions = surface.descriptions || {};
    var defaults = surface.defaults || {};
    var needsHint = surface.needs_hint || [];

    Object.keys(items).forEach(function (key) {
      var fullKey = opts.prefix ? opts.prefix + key : key;
      var label = labels[fullKey] || labels[key] || key;
      if (opts.experimental && opts.experimental.indexOf(fullKey) !== -1) {
        // 实验项逐行 ⚗ 标记：清单由服务端下发，实验身份与作用域分组正交
        label = '⚗ ' + label;
      } else if (opts.reportAffecting && opts.reportAffecting.indexOf(fullKey) !== -1) {
        label = label + '（影响报告）';
      }
      // 「已改」标记：当前值 ≠ 服务端下发的出厂默认（前端不自算基准）
      var currentOn = Boolean(items[key]);
      var defaultOn = Boolean(defaults[fullKey]);
      if (Object.prototype.hasOwnProperty.call(defaults, fullKey) && currentOn !== defaultOn) {
        label = label + ' ✻';
      }
      var row = document.createElement('label');
      row.className = 'check-label config-row';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!items[key];
      cb.dataset.configKey = fullKey;
      cb.addEventListener('change', onConfigToggle);
      row.appendChild(cb);
      var span = document.createElement('span');
      span.textContent = label;
      row.appendChild(span);
      group.appendChild(row);
      // 说明副行：注册表标了「需提示」或本块强制展开时默认显示，其余悬停可见
      var desc = descriptions[fullKey] || descriptions[key];
      if (desc && (needsHint.indexOf(fullKey) !== -1 || opts.showDesc)) {
        group.appendChild(makeConfigDesc(desc));
      } else if (desc) {
        row.title = desc;
      }
    });

    if (opts.note) {
      var note = document.createElement('p');
      note.className = 'config-note-sub';
      note.textContent = opts.note;
      group.appendChild(note);
    }

    group.appendChild(makeGroupErrorEl());
    return group;
  }

  function renderAnonGroup(surface) {
    var anon = surface.anonymization;
    var group = document.createElement('div');
    group.className = 'config-group';
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-label', '持仓匿名化');
    var heading = document.createElement('h3');
    heading.className = 'config-group-title';
    heading.textContent = (surface.block_titles || {}).anonymization || '持仓匿名化';
    heading.id = 'config-group-anonymization';
    group.id = 'config-block-anonymization';
    group.setAttribute('aria-labelledby', heading.id);
    group.appendChild(heading);

    (anon.options || []).forEach(function (mode) {
      var row = document.createElement('label');
      row.className = 'radio-label config-row';
      var radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'config-anonymization';
      radio.value = mode;
      radio.checked = mode === anon.mode;
      radio.dataset.configKey = 'anonymization.mode';
      radio.addEventListener('change', onConfigRadioChange);
      row.appendChild(radio);
      var span = document.createElement('span');
      span.textContent = (anon.labels && anon.labels[mode]) || mode;
      row.appendChild(span);
      group.appendChild(row);
    });

    group.appendChild(makeGroupErrorEl());
    return group;
  }

  function renderIndicesGroup(surface) {
    var group = document.createElement('div');
    group.className = 'config-group';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', '对比指数池');
    var heading = document.createElement('h3');
    heading.className = 'config-group-title';
    heading.textContent = (surface.block_titles || {}).indices || '对比基准指数';
    group.appendChild(heading);

    var listWrap = document.createElement('div');
    listWrap.className = 'config-indices-list';
    renderIndicesList(listWrap, surface.comparison_indices);
    group.appendChild(listWrap);

    var addRow = document.createElement('div');
    addRow.className = 'config-indices-add';
    var codeInput = document.createElement('input');
    codeInput.type = 'text';
    codeInput.id = 'config-index-code';
    codeInput.placeholder = '指数代码（如 sh000905）';
    codeInput.autocomplete = 'off';
    codeInput.spellcheck = false;
    var nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.id = 'config-index-name';
    nameInput.placeholder = '指数名称（如 中证500）';
    nameInput.autocomplete = 'off';
    nameInput.spellcheck = false;
    var addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'btn btn-secondary btn-sm';
    addBtn.textContent = '添加';
    addBtn.addEventListener('click', onIndexAdd);
    addRow.appendChild(codeInput);
    addRow.appendChild(nameInput);
    addRow.appendChild(addBtn);
    group.appendChild(addRow);

    var resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'btn btn-secondary btn-sm config-index-reset';
    resetBtn.textContent = '重置为默认预设';
    resetBtn.addEventListener('click', onIndexReset);
    group.appendChild(resetBtn);

    group.appendChild(makeGroupErrorEl());
    return group;
  }

  /* ── LLM 多链线路优先级：▲▼ 调序 → POST reorder（与 CLI/TUI 同一编辑层） ── */
  function renderProvidersGroup(surface) {
    var prov = surface.llm_providers;
    if (!prov || !(prov.providers || []).length) {
      return null; // 无多链线路（含配置读取失败回退空清单）时不占面板位
    }
    var group = document.createElement('div');
    group.className = 'config-group';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', 'LLM 多链线路优先级');
    var heading = document.createElement('h3');
    heading.className = 'config-group-title';
    heading.textContent = (surface.block_titles || {}).providers || '多链线路优先级';
    heading.id = 'config-group-providers';
    group.id = 'config-block-providers';
    group.setAttribute('aria-labelledby', heading.id);
    group.appendChild(heading);

    var priorityAware = prov.strategy === 'priority' || prov.strategy === 'fallback_only';
    var note = document.createElement('p');
    note.className = 'config-note-sub';
    note.textContent = '按下列顺序作为备用（越靠前越优先）。当前策略 ' + prov.strategy + (priorityAware
      ? '：顺序即实际链序'
      : '：实际链序由权重/成本决定，此顺序仅在 priority / fallback_only 策略下生效');
    group.appendChild(note);

    var listWrap = document.createElement('div');
    listWrap.className = 'config-indices-list';
    renderProvidersList(listWrap, prov);
    group.appendChild(listWrap);
    group.appendChild(makeGroupErrorEl());
    return group;
  }

  function renderProvidersList(wrap, prov) {
    wrap.textContent = '';
    (prov.providers || []).forEach(function (p, i, items) {
      var row = document.createElement('div');
      row.className = 'config-index-row';
      var name = document.createElement('span');
      name.className = 'config-index-name';
      name.textContent = (i + 1) + '. ' + p.name + '（' + p.provider + '）priority ' + p.priority;
      row.appendChild(name);
      [['▲', i > 0, '上移'], ['▼', i < items.length - 1, '下移']].forEach(function (spec) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-secondary btn-sm config-index-del';
        btn.textContent = spec[0];
        btn.disabled = !spec[1];
        btn.setAttribute('aria-label', spec[2] + ' ' + p.name);
        btn.addEventListener('click', onProviderMove);
        row.appendChild(btn);
      });
      wrap.appendChild(row);
    });
  }

  function onProviderMove(e) {
    var btn = e.target;
    var group = btn.closest('.config-group');
    var prov = configState.surface.llm_providers;
    var items = (prov.providers || []).slice();
    var rows = Array.prototype.slice.call(group.querySelectorAll('.config-index-row'));
    var idx = rows.indexOf(btn.closest('.config-index-row'));
    var target = btn.textContent === '\u25b2' ? idx - 1 : idx + 1;
    if (idx < 0 || target < 0 || target >= items.length) {
      return;
    }
    var moved = items.splice(idx, 1)[0];
    items.splice(target, 0, moved);
    var order = items.map(function (p) { return p.name; });
    var listWrap = group.querySelector('.config-indices-list');
    Array.prototype.forEach.call(group.querySelectorAll('button'), function (b) { b.disabled = true; });
    postConfigEdit({ key: 'llm_providers.priority', action: 'reorder', order: order })
      .then(function (data) {
        // 服务端回传生效顺序；priority 已归一化为 10,20,…，本地对齐后整组重渲染
        var names = (data && data.value && data.value.order) || order;
        var byName = {};
        (prov.providers || []).forEach(function (p) { byName[p.name] = p; });
        prov.providers = names.map(function (n, i) {
          var src = byName[n] || {};
          var next = {};
          Object.keys(src).forEach(function (k) { next[k] = src[k]; });
          next.priority = (i + 1) * 10;
          return next;
        });
        renderProvidersList(listWrap, prov);
      })
      .catch(function (err) {
        showGroupError(group, err); // 失败：本地顺序未改，重渲染恢复原状
        renderProvidersList(listWrap, prov);
      });
  }

  function renderIndicesList(wrap, indices) {
    wrap.textContent = '';
    var entries = Object.keys(indices || {});
    if (!entries.length) {
      var empty = document.createElement('p');
      empty.className = 'config-note-sub';
      empty.textContent = '空池（仅显示沪深300）';
      wrap.appendChild(empty);
      return;
    }
    entries.forEach(function (code) {
      var row = document.createElement('div');
      row.className = 'config-index-row';
      var name = document.createElement('span');
      name.className = 'config-index-name';
      name.textContent = code + ' (' + indices[code] + ')';
      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn btn-secondary btn-sm config-index-del';
      delBtn.textContent = '删除';
      delBtn.addEventListener('click', onIndexRemove);
      row.appendChild(name);
      row.appendChild(delBtn);
      wrap.appendChild(row);
    });
  }

  /* ── 即改即存：提交 POST /api/config/edit ── */
  function postConfigEdit(body) {
    return fetch('/api/config/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000)
    })
      .then(handleResponse)
      .then(function (data) {
        // 成功即清除面板顶部同源警示，避免残留误导
        var panelErr = document.getElementById('config-panel-error');
        if (panelErr) {
          panelErr.hidden = true;
          panelErr.textContent = '';
        }
        return data;
      });
  }

  function onConfigToggle(e) {
    var cb = e.target;
    var key = cb.dataset.configKey;
    var prev = !cb.checked; // change 后 checked 已是新值，取反得改动前值
    var group = cb.closest('.config-group');
    cb.disabled = true;
    clearGroupError(group);
    postConfigEdit({ key: key, value: cb.checked })
      .catch(function (err) {
        cb.checked = prev; // 失败恢复为改动前值
        showGroupError(group, err);
      })
      .then(function () {
        cb.disabled = false;
        refreshConfigStats();
      });
  }

  function onConfigRadioChange(e) {
    var radio = e.target;
    if (!radio.checked) {
      return; // 仅处理选中变化
    }
    var prev = configState.surface.anonymization.mode;
    var group = radio.closest('.config-group');
    var radios = group.querySelectorAll('input[type="radio"]');
    radios.forEach(function (r) {
      r.disabled = true;
    });
    clearGroupError(group);
    postConfigEdit({ key: 'anonymization.mode', value: radio.value })
      .then(function () {
        configState.surface.anonymization.mode = radio.value;
      })
      .catch(function (err) {
        var target = group.querySelector('input[value="' + prev + '"]');
        if (target) {
          target.checked = true;
        }
        showGroupError(group, err);
      })
      .then(function () {
        radios.forEach(function (r) {
          r.disabled = false;
        });
        refreshConfigStats();
      });
  }

  /** 显式保存类（下拉 / 数字框）：失败保留输入值并在块内报错。 */
  function onFieldSave(e) {
    var btn = e.target;
    var row = btn.closest('.field');
    var control = row.querySelector('select, input');
    var key = control.dataset.configKey;
    var group = btn.closest('.config-group');
    var status = row.querySelector('.config-row-status');
    btn.disabled = true;
    status.textContent = '';
    status.className = 'config-row-status';
    clearGroupError(group);
    postConfigEdit({ key: key, value: control.type === 'number' ? Number(control.value) : control.value })
      .then(function () {
        status.textContent = '已保存';
        status.className = 'config-row-status status-ok';
        refreshConfigStats();
      })
      .catch(function (err) {
        showGroupError(group, err);
      })
      .then(function () {
        btn.disabled = false;
      });
  }

  function onPathSave(e) {
    var btn = e.target;
    var row = btn.closest('.config-path-row');
    var input = row.querySelector('input[type="text"]');
    var key = input.id.replace('config-input-', '');
    var group = btn.closest('.config-group');
    var status = row.querySelector('.config-row-status');
    btn.disabled = true;
    status.textContent = '';
    status.className = 'config-row-status';
    clearGroupError(group);
    postConfigEdit({ key: key, value: input.value })
      .then(function (data) {
        input.value = data.value;
        status.textContent = data.backup ? '已保存（已备份）' : '已保存';
        status.className = 'config-row-status status-ok';
      })
      .catch(function (err) {
        // 显式保存失败：保留用户输入供直接重试（契约 §4.5「保留输入值 + 错误区提示」），
        // 仅反映状态样式——回滚只用于即时保存类（勾选/单选）
        status.textContent = '保存失败';
        status.className = 'config-row-status status-error';
        showGroupError(group, err);
      })
      .then(function () {
        btn.disabled = false;
      });
  }

  function onIndexAdd(e) {
    var btn = e.target;
    var group = btn.closest('.config-group');
    var codeInput = document.getElementById('config-index-code');
    var nameInput = document.getElementById('config-index-name');
    var code = codeInput.value.trim();
    var name = nameInput.value.trim();
    if (!code || !name) {
      showGroupError(group, { message: '指数代码与名称均不能为空' });
      return;
    }
    btn.disabled = true;
    clearGroupError(group);
    postConfigEdit({ key: 'comparison_indices', action: 'add', code: code, name: name })
      .then(function (data) {
        configState.surface.comparison_indices = data.value;
        codeInput.value = '';
        nameInput.value = '';
        var listWrap = group.querySelector('.config-indices-list');
        renderIndicesList(listWrap, data.value);
      })
      .catch(function (err) {
        showGroupError(group, err);
      })
      .then(function () {
        btn.disabled = false;
      });
  }

  function onIndexRemove(e) {
    var btn = e.target;
    var group = btn.closest('.config-group');
    var row = btn.closest('.config-index-row');
    var code = row.querySelector('.config-index-name').textContent.split(' (')[0];
    btn.disabled = true;
    clearGroupError(group);
    postConfigEdit({ key: 'comparison_indices', action: 'remove', code: code })
      .then(function (data) {
        configState.surface.comparison_indices = data.value;
        var listWrap = group.querySelector('.config-indices-list');
        renderIndicesList(listWrap, data.value);
      })
      .catch(function (err) {
        showGroupError(group, err);
      })
      .then(function () {
        btn.disabled = false;
      });
  }

  function onIndexReset(e) {
    var btn = e.target;
    var group = btn.closest('.config-group');
    var defaults = (configState.surface && configState.surface.comparison_indices_defaults) || {};
    var names = Object.keys(defaults)
      .map(function (c) {
        return c + ' (' + defaults[c] + ')';
      })
      .join('，');
    var confirmMsg = '确定重置对比指数池为默认预设？' + (names ? '（' + names + '）' : '');
    if (!window.confirm(confirmMsg)) {
      return;
    }
    btn.disabled = true;
    clearGroupError(group);
    postConfigEdit({ key: 'comparison_indices', action: 'reset' })
      .then(function (data) {
        configState.surface.comparison_indices = data.value;
        var listWrap = group.querySelector('.config-indices-list');
        renderIndicesList(listWrap, data.value);
      })
      .catch(function (err) {
        showGroupError(group, err);
      })
      .then(function () {
        btn.disabled = false;
      });
  }

  /* ── 分组错误区辅助 ── */
  /**
   * 日志设置块：枚举用下拉、整数用数字框，逐项显式保存（与 TUI `[D]→[L]` 同一批键）。
   * 服务端下发 labels/descriptions/取值范围；「下次启动生效」的键在块尾统一说明。
   */
  function renderLoggingBlock(surface) {
    var data = surface.logging || { items: [], restart_keys: [] };
    if (!data.items || !data.items.length) {
      return null;
    }
    var group = makeBlockGroup('logging', (surface.block_titles || {}).logging || '日志设置');
    var restart = data.restart_keys || [];
    data.items.forEach(function (item) {
      var row = document.createElement('div');
      row.className = 'field';
      var label = document.createElement('label');
      label.textContent = item.label + '：';
      label.htmlFor = 'config-logging-' + item.key.replace(/\./g, '-');
      var control;
      if (item.kind === 'enum') {
        control = document.createElement('select');
        (item.options || []).forEach(function (option) {
          var opt = document.createElement('option');
          opt.value = option;
          opt.textContent = option;
          if (option === item.value) {
            opt.selected = true;
          }
          control.appendChild(opt);
        });
      } else {
        control = document.createElement('input');
        control.type = 'number';
        control.min = item.min;
        control.max = item.max;
        control.step = item.step || 1;
        control.value = item.value;
      }
      control.id = label.htmlFor;
      control.dataset.configKey = item.key;
      var saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.className = 'btn btn-secondary btn-sm config-save';
      saveBtn.textContent = '保存';
      saveBtn.addEventListener('click', onFieldSave);
      var status = document.createElement('span');
      status.className = 'config-row-status';
      status.setAttribute('role', 'status');
      row.appendChild(label);
      row.appendChild(control);
      row.appendChild(saveBtn);
      row.appendChild(status);
      group.appendChild(row);
      if (item.hint) {
        group.appendChild(makeConfigDesc(item.hint, true));
      }
    });
    if (restart.length) {
      var note = document.createElement('p');
      note.className = 'config-note-sub';
      note.textContent = '级别与轮转改动在下次启动生效；查看器两项即时生效。';
      group.appendChild(note);
    }
    group.appendChild(makeGroupErrorEl());
    return group;
  }

  /** 只读参考块：计价参考等不进编辑面的信息行（固定渲染，不随数据为空消失）。 */
  function renderReferenceBlock(surface) {
    var ref = surface.reference;
    if (!ref || !ref.pricing_path) {
      return null;
    }
    var group = makeBlockGroup('reference', (surface.block_titles || {}).reference || '参考信息');
    var row = document.createElement('div');
    row.className = 'ref-row';
    var label = document.createElement('span');
    label.textContent = '计价参考：';
    var path = document.createElement('span');
    path.className = 'mono';
    path.textContent = ref.pricing_path;
    row.appendChild(label);
    row.appendChild(path);
    group.appendChild(row);
    if (ref.note) {
      group.appendChild(makeConfigDesc(ref.note, true));
    }
    return group;
  }

  function makeGroupErrorEl() {
    var el = document.createElement('p');
    el.className = 'status-text config-error';
    el.setAttribute('role', 'alert');
    el.hidden = true;
    return el;
  }

  function clearGroupError(group) {
    var err = group.querySelector('.config-error');
    if (err) {
      err.hidden = true;
      err.textContent = '';
    }
  }

  function showGroupError(group, err) {
    if (err.errorCode === 'BAD_PARAM' && err.httpStatus === 403) {
      // 同源失败 → 面板顶部警示，提示刷新
      var panelErr = document.getElementById('config-panel-error');
      if (panelErr) {
        panelErr.textContent = '同源校验失败，请刷新页面重试';
        panelErr.hidden = false;
      }
      return;
    }
    var msg = err.message || '配置修改失败';
    var errEl = group.querySelector('.config-error');
    if (!errEl) {
      errEl = makeGroupErrorEl();
      group.appendChild(errEl);
    }
    errEl.textContent = msg;
    errEl.hidden = false;
  }

  /* ── 标签页工作台（五区：生成 / 调仓 / 配置 / 状态 / 日志）──
   * 一次只专注一个工作区；支持点击、方向键（WAI-ARIA tabs 模式）与
   * #whatif 等 hash 深链（手册可直接链接到指定工作区）。
   */
  var TAB_NAMES = ['generate', 'whatif', 'holdings', 'config', 'status', 'logs'];

  function activateTab(name, updateHash) {
    if (TAB_NAMES.indexOf(name) === -1) {
      name = 'generate';
    }
    TAB_NAMES.forEach(function (n) {
      var btn = document.getElementById('tab-' + n);
      var panel = document.getElementById('panel-' + n);
      if (!btn || !panel) {
        return;
      }
      var active = n === name;
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
      btn.tabIndex = active ? 0 : -1;
      panel.hidden = !active;
    });
    if (updateHash !== false && window.location.hash.slice(1) !== name) {
      window.history.replaceState(null, '', '#' + name);
    }
  }

  /** 深链路由：`#domain-<key>` 走配置页域锚点，其余按标签页名切换。 */
  function applyLocationHash(initial) {
    var hash = (window.location.hash || '').slice(1);
    if (hash.indexOf('domain-') === 0) {
      activateTab('config', initial ? true : false);
      scrollToDomain(hash.slice('domain-'.length), false);
      return;
    }
    activateTab(hash || 'generate', false);
  }

  function onLocationHashChange() {
    applyLocationHash(false);
  }

  function onTabKeydown(e) {
    var idx = TAB_NAMES.indexOf(this.getAttribute('data-tab'));
    var next = null;
    if (e.key === 'ArrowRight') {
      next = (idx + 1) % TAB_NAMES.length;
    } else if (e.key === 'ArrowLeft') {
      next = (idx - 1 + TAB_NAMES.length) % TAB_NAMES.length;
    } else if (e.key === 'Home') {
      next = 0;
    } else if (e.key === 'End') {
      next = TAB_NAMES.length - 1;
    }
    if (next === null) {
      return;
    }
    e.preventDefault();
    activateTab(TAB_NAMES[next]);
    document.getElementById('tab-' + TAB_NAMES[next]).focus();
  }

  /* ── 调仓 What-if 模拟（同步接口，独立产物）── */
  var whatifState = { baseFileId: null, candFileId: null, running: false };

  function whatifBaseMode() {
    var mode = document.querySelector('input[name="whatif_base"]:checked');
    return mode ? mode.value : 'existing';
  }

  function onWhatifBaseModeChange() {
    els.whatifBaseUpload.hidden = whatifBaseMode() !== 'upload';
    updateWhatifBtn();
  }

  function uploadWhatifFile(input, statusEl, onDone) {
    var file = input.files && input.files[0];
    if (!file) {
      return;
    }
    setStatus(statusEl, '正在上传并校验 ' + file.name + ' ...', 'busy');
    var fd = new FormData();
    fd.append('file', file);
    fetch('/api/upload', {
      method: 'POST',
      body: fd,
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (data) {
        onDone(data.file_id);
        setStatus(statusEl, '已上传：共 ' + data.count + ' 条持仓', 'ok');
        updateWhatifBtn();
      })
      .catch(function (err) {
        onDone(null);
        setStatus(statusEl, err.message, 'error');
        updateWhatifBtn();
      });
  }

  function updateWhatifBtn() {
    var hasCand = !!whatifState.candFileId;
    var hasBase = whatifBaseMode() === 'existing' || !!whatifState.baseFileId;
    els.whatifBtn.disabled = whatifState.running || !hasCand || !hasBase;
  }

  function onWhatifSubmit(e) {
    e.preventDefault();
    if (els.whatifBtn.disabled) {
      return;
    }
    whatifState.running = true;
    updateWhatifBtn();
    els.whatifBtn.textContent = '模拟中...';
    els.whatifError.textContent = '';
    els.whatifResult.hidden = true;

    var mode = whatifBaseMode();
    var body = {
      candidate_file_id: whatifState.candFileId,
      use_existing: mode === 'existing',
    };
    if (mode === 'upload') {
      body.base_file_id = whatifState.baseFileId;
    }
    var eff = (els.whatifEffectiveDate.value || '').trim();
    if (eff) {
      body.effective_date = eff;
    }

    // 生效日回测需联网取历史行情，超时放宽到 3 分钟（本地截面比较通常数秒）
    fetch('/api/whatif', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(180000),
    })
      .then(handleResponse)
      .then(
        function (data) {
          els.whatifLinkHtml.href = '/api/reports/' + encodeURIComponent(data.html);
          els.whatifLinkExcel.href = '/api/reports/' + encodeURIComponent(data.excel);
          els.whatifResultMeta.textContent =
            '基准 ' + data.base_count + ' 条 / 目标 ' + data.candidate_count +
            ' 条 · 独立产物，不并入主报告';
          els.whatifResult.hidden = false;
          whatifDone();
        },
        function (err) {
          if (err.errorCode === 'FILE_EXPIRED') {
            // 上传文件已过期/服务重启：清空两侧文件引导重新上传
            whatifState.baseFileId = null;
            whatifState.candFileId = null;
            setStatus(els.whatifBaseStatus, '', null);
            setStatus(els.whatifCandStatus, '上传文件已过期，请重新选择', 'error');
          }
          els.whatifError.textContent = err.message;
          whatifDone();
        }
      );
  }

  function whatifDone() {
    whatifState.running = false;
    els.whatifBtn.textContent = '开始模拟';
    updateWhatifBtn();
  }

  /* ── 定时生成调度面板：读取/保存 config.json scheduler 块 ── */
  function loadScheduler() {
    fetch('/api/scheduler', { signal: AbortSignal.timeout(10000) })
      .then(handleResponse)
      .then(function (data) {
        els.schedEnabled.checked = !!data.enabled;
        els.schedTime.value = data.time || '07:30';
        els.schedType.value = data.report_type || 'basic';
        els.schedWeekdayCbs.forEach(function (cb) {
          cb.checked = (data.weekdays || []).indexOf(Number(cb.value)) !== -1;
        });
        setStatus(els.schedStatus, '已加载当前调度配置', 'ok');
        renderSchedulerNext(data);
      })
      .catch(function (err) {
        setStatus(els.schedStatus, err.message || '调度配置加载失败', 'error');
      });
  }

  function saveScheduler() {
    var weekdays = [];
    els.schedWeekdayCbs.forEach(function (cb) {
      if (cb.checked) {
        weekdays.push(Number(cb.value));
      }
    });
    setStatus(els.schedStatus, '保存中...', 'busy');
    fetch('/api/scheduler', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        enabled: els.schedEnabled.checked,
        time: els.schedTime.value,
        weekdays: weekdays,
        report_type: els.schedType.value,
      }),
      signal: AbortSignal.timeout(10000),
    })
      .then(handleResponse)
      .then(function (data) {
        setStatus(els.schedStatus, data.enabled ? '调度已启用' : '调度已保存（未启用）', 'ok');
        renderSchedulerNext(data);
      })
      .catch(function (err) {
        setStatus(els.schedStatus, err.message || '调度保存失败', 'error');
      });
  }

  function renderSchedulerNext(data) {
    if (data.next_fire) {
      els.schedNext.textContent = '下次触发：' + data.next_fire + '（宽限 ' + data.grace_minutes + ' 分钟内顺延补触发）';
    } else {
      els.schedNext.textContent = '调度未启用';
    }
  }

  /* ── 缓存卡：统计 + 清理过期（对应 TUI [3][4]）── */
  function formatSize(bytes) {
    if (bytes >= 1048576) {
      return (bytes / 1048576).toFixed(1) + ' MB';
    }
    if (bytes >= 1024) {
      return (bytes / 1024).toFixed(1) + ' KB';
    }
    return bytes + ' B';
  }

  function loadCacheStats() {
    return fetch('/api/cache', { signal: AbortSignal.timeout(15000) })
      .then(handleResponse)
      .then(function (data) {
        els.cacheTotalFiles.textContent = data.total_files + ' 个';
        els.cacheTotalSize.textContent = formatSize(data.total_size_bytes || 0);
        var hit = data.hit_rate || {};
        els.cacheHitRate.textContent = hit.total > 0
          ? Math.round((hit.rate || 0) * 100) + '%（' + hit.hits + '/' + hit.total + '）'
          : '暂无观测';
        els.cacheExpired.textContent = data.expired_count > 0
          ? data.expired_count + ' 个（可清理）'
          : '无';

        // 前缀分布（服务端已按文件数降序，取前 6 行避免卡片过长）
        els.cachePrefixList.textContent = '';
        var pairs = Array.isArray(data.by_prefix) ? data.by_prefix : [];
        var top = pairs.slice(0, 6);
        if (!top.length) {
          var empty = document.createElement('p');
          empty.className = 'status-text';
          empty.textContent = '暂无缓存文件';
          els.cachePrefixList.appendChild(empty);
          return;
        }
        top.forEach(function (pair) {
          var row = document.createElement('div');
          row.className = 'health-row';
          var name = document.createElement('span');
          name.className = 'health-name';
          name.textContent = pair[0];
          var meta = document.createElement('span');
          meta.className = 'health-meta';
          meta.textContent = pair[1] + ' 个';
          row.appendChild(name);
          row.appendChild(meta);
          els.cachePrefixList.appendChild(row);
        });
      })
      .catch(function (err) {
        setStatus(els.cacheStatus, err.message, 'error');
      });
  }

  function onCacheCleanup() {
    els.cacheCleanup.disabled = true;
    setStatus(els.cacheStatus, '正在清理过期缓存...', 'busy');
    fetch('/api/cache/cleanup', {
      method: 'POST',
      signal: AbortSignal.timeout(30000),
    })
      .then(handleResponse)
      .then(function (data) {
        setStatus(
          els.cacheStatus,
          data.removed > 0 ? '已清理 ' + data.removed + ' 个过期文件' : '没有需要清理的过期文件',
          data.removed > 0 ? 'ok' : ''
        );
        return loadCacheStats();
      })
      .catch(function (err) {
        setStatus(els.cacheStatus, err.message, 'error');
      })
      .then(function () {
        els.cacheCleanup.disabled = false;
      });
  }

  // ── 深浅色主题（与 HTML 报告 theme.js 同款存储键 investor-theme-dark，偏好跨页共享）──
  // 亮色 = 移除 data-theme 属性；暗色 = data-theme="dark"（style.css 变量块切换）。
  (function () {
    var KEY = 'investor-theme-dark';
    var btn = document.getElementById('theme-toggle');
    var dark = false;
    try {
      dark = localStorage.getItem(KEY) === '1';
    } catch (e) {
      /* 隐私模式/存储不可用：仅本次会话生效（同报告 theme.js 降级） */
    }
    function apply() {
      if (dark) {
        document.documentElement.setAttribute('data-theme', 'dark');
      } else {
        document.documentElement.removeAttribute('data-theme');
      }
      if (btn) {
        btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
        btn.textContent = dark ? '浅色' : '深色';
        btn.title = dark ? '切换为浅色模式' : '切换为深色模式';
      }
    }
    apply();
    if (btn) {
      btn.addEventListener('click', function () {
        dark = !dark;
        apply();
        try {
          localStorage.setItem(KEY, dark ? '1' : '0');
        } catch (e) {
          /* ignore */
        }
      });
    }
  })();


  /* ── 持仓录入（在线改持仓文件；与 TUI [U] 同一套编解码与校验）─────────
     变更清单只存在浏览器内存里，服务端每次 preview/save 重放；
     保存前有 mtime 闸门与 .bak 备份（与 TUI 一致），不覆盖他人的手改。 */
  (function () {
    var state = { overview: null, baseMtime: null, draft: [] };
    var box = document.getElementById('panel-holdings');
    if (!box) {
      return;
    }
    var $ = function (id) { return document.getElementById(id); };
    var els = {
      note: $('holdings-file-note'),
      account: $('holdings-account'),
      accountNew: $('holdings-account-new'),
      asset: $('holdings-asset'),
      code: $('holdings-code'),
      name: $('holdings-name'),
      kind: $('holdings-kind'),
      side: $('holdings-side'),
      shares: $('holdings-shares'),
      amount: $('holdings-amount'),
      price: $('holdings-price'),
      date: $('holdings-date'),
      add: $('holdings-add'),
      error: $('holdings-error'),
      wrap: $('holdings-draft-wrap'),
      list: $('holdings-draft'),
      flows: $('holdings-flows'),
      clear: $('holdings-clear'),
      preview: $('holdings-preview'),
      save: $('holdings-save'),
      previewBox: $('holdings-preview-box'),
    };

    function setMsg(el, text, kind) {
      el.textContent = text || '';
      el.className = 'status-text' + (kind ? ' status-' + kind : '');
    }

    function postJson(url, body) {
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
        signal: AbortSignal.timeout(120000),
      }).then(function (res) {
        return res.json().then(function (payload) {
          if (!payload || payload.ok !== true) {
            var err = new Error((payload && payload.error) || '请求失败');
            err.errorCode = payload && payload.error_code;
            throw err;
          }
          return payload.data;
        });
      });
    }

    function accountNames() {
      return (state.overview ? state.overview.accounts : []).map(function (a) { return a.account; });
    }

    function rowsOf(account) {
      var found = (state.overview ? state.overview.accounts : []).filter(function (a) {
        return a.account === account;
      })[0];
      return found ? found.rows : [];
    }

    function fillAccounts() {
      var names = accountNames();
      els.account.replaceChildren();
      names.forEach(function (name) {
        var opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        els.account.appendChild(opt);
      });
      fillAssets();
    }

    function fillAssets() {
      var rows = rowsOf(els.account.value);
      els.asset.replaceChildren();
      var blank = document.createElement('option');
      blank.value = '';
      blank.textContent = rows.length ? '（选择已有持仓）' : '（该账户暂无持仓）';
      els.asset.appendChild(blank);
      rows.forEach(function (row, index) {
        var opt = document.createElement('option');
        opt.value = String(index);
        opt.textContent = row.name + '（' + row.code + '）份额 ' + row.shares;
        els.asset.appendChild(opt);
      });
    }

    function loadOverview() {
      setMsg(els.error, '', null);
      return fetch('/api/holdings', { signal: AbortSignal.timeout(30000) })
        .then(function (res) { return res.json(); })
        .then(function (payload) {
          if (!payload || payload.ok !== true) {
            throw new Error((payload && payload.error) || '读取持仓文件失败');
          }
          state.overview = payload.data;
          state.baseMtime = payload.data.mtime;
          els.note.textContent =
            '文件：' + payload.data.file + ' · ' + payload.data.rows_total + ' 条持仓 · 未保存的变更不会写入文件';
          fillAccounts();
        })
        .catch(function (err) {
          state.overview = null;
          els.note.textContent = '持仓文件不可用';
          setMsg(els.error, err.message, 'error');
        });
    }

    function currentTarget() {
      var code = (els.code.value || '').trim();
      if (code) {
        return { code: code, name: (els.name.value || '').trim() };
      }
      var rows = rowsOf(els.account.value);
      var picked = els.asset.value === '' ? null : rows[Number(els.asset.value)];
      return picked ? { code: picked.code, name: picked.name } : null;
    }

    function currentAccount() {
      var typed = (els.accountNew.value || '').trim();
      return typed || (els.account.value || '').trim();
    }

    function buildIntent() {
      var account = currentAccount();
      if (!account) {
        throw new Error('请先选择账户，或输入新账户名');
      }
      var target = currentTarget();
      if (!target) {
        throw new Error('请选择已有持仓，或输入证券代码');
      }
      var shares = (els.shares.value || '').trim();
      var amount = (els.amount.value || '').trim();
      if (!shares && !amount) {
        throw new Error('请填写份额；场外买入可只填申购金额');
      }
      return {
        account: account,
        code: target.code,
        name: target.name,
        side: els.side.value,
        shares: shares || null,
        amount: amount || null,
        price: (els.price.value || '').trim() || null,
        trade_date: (els.date.value || '').trim() || null,
        asset_kind: els.kind.value || null,
      };
    }

    function intentLabel(intent) {
      var side = intent.side === 'buy' ? '买入' : '卖出';
      var qty = intent.shares ? intent.shares + ' 份' : intent.amount + ' 元';
      return intent.account + ' · ' + side + ' ' + (intent.name || intent.code) + '（' + intent.code + '）' + qty;
    }

    function renderDraft() {
      els.list.replaceChildren();
      state.draft.forEach(function (intent, index) {
        var item = document.createElement('li');
        var text = document.createElement('span');
        text.textContent = intentLabel(intent);
        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-ghost holdings-remove';
        remove.textContent = '移除';
        remove.addEventListener('click', function () {
          state.draft.splice(index, 1);
          renderDraft();
        });
        item.appendChild(text);
        item.appendChild(remove);
        els.list.appendChild(item);
      });
      var empty = state.draft.length === 0;
      els.wrap.hidden = empty;
      els.save.disabled = empty;
      els.preview.disabled = empty;
      els.clear.disabled = empty;
      if (empty) {
        els.previewBox.hidden = true;
      }
    }

    function renderPreview(data) {
      var diff = data.diff || { added: 0, updated: 0, removed: 0 };
      var lines = [
        '写回后共 ' + data.rows_total + ' 条持仓 · 新增 ' + diff.added +
          ' / 更新 ' + diff.updated + ' / 移除 ' + diff.removed,
      ];
      (data.accounts || []).forEach(function (account) {
        lines.push('── ' + account.account + '（' + account.rows.length + ' 条）' + (account.dirty ? ' *' : ''));
        account.rows.forEach(function (row) {
          lines.push('  ' + (row.dirty ? '* ' : '  ') + row.name + '（' + row.code + '）份额 ' + row.shares + ' · 成本 ' + row.cost);
        });
      });
      els.previewBox.textContent = lines.join('\n');
      els.previewBox.hidden = false;
    }

    els.add.addEventListener('click', function () {
      try {
        var intent = buildIntent();
        state.draft.push(intent);
        setMsg(els.error, '', null);
        els.shares.value = '';
        els.amount.value = '';
        // 保留账户/标的：分批卖出、加仓时可直接改份额继续录（对齐 TUI 的「继续录上一笔」）
        renderDraft();
      } catch (err) {
        setMsg(els.error, err.message, 'error');
      }
    });

    els.account.addEventListener('change', fillAssets);
    els.accountNew.addEventListener('input', fillAssets);

    els.preview.addEventListener('click', function () {
      setMsg(els.error, '', null);
      postJson('/api/holdings/preview', { intents: state.draft }).then(renderPreview, function (err) {
        setMsg(els.error, err.message, 'error');
      });
    });

    els.save.addEventListener('click', function () {
      if (state.draft.length === 0) {
        return;
      }
      var summary = state.draft.map(intentLabel).join('\n');
      setMsg(els.error, '', null);
      postJson('/api/holdings/preview', { intents: state.draft }).then(function (preview) {
        var diff = preview.diff || {};
        var head =
          '写回后共 ' + preview.rows_total + ' 条持仓（新增 ' + (diff.added || 0) +
          ' / 更新 ' + (diff.updated || 0) + ' / 移除 ' + (diff.removed || 0) + '）';
        if (!window.confirm('确认写入持仓文件？\n\n' + head + '\n\n' + summary + '\n\n写前会自动备份为 .bak。')) {
          return;
        }
        return doSave();
      }, function (err) {
        setMsg(els.error, err.message, 'error');
      });
    });

    function doSave() {
      return postJson('/api/holdings/save', {
        intents: state.draft,
        base_mtime: state.baseMtime,
        append_flows: els.flows.checked,
      }).then(
        function (data) {
          state.draft = [];
          renderDraft();
          setMsg(
            els.error,
            '已写入 ' + data.file + '：' + data.saved + ' 笔变更' +
              (data.append_flows ? '（含交易流水）' : '') +
              (data.backup ? '，备份 ' + data.backup : ''),
            'ok'
          );
          loadOverview();
        },
        function (err) {
          setMsg(els.error, err.message, 'error');
          if (err.errorCode === 'HOLDINGS_STALE') {
            loadOverview();
          }
        }
      );
    }

    // 清空本次变更清单（不写文件）；与 TUI 的「2=丢弃草稿」同义
    els.clear.addEventListener('click', function () {
      if (state.draft.length === 0) {
        return;
      }
      if (!window.confirm('清空本次 ' + state.draft.length + ' 笔变更？持仓文件不会被改动。')) {
        return;
      }
      state.draft = [];
      renderDraft();
      setMsg(els.error, '已清空变更清单（持仓文件未改动）', 'ok');
    });

    // 记住「同时记入交易流水」的选择，省去每次重勾
    try {
      els.flows.checked = localStorage.getItem('holdings:flows') === '1';
    } catch (e) {
      /* 隐私模式下 localStorage 不可用，保持默认未勾选 */
    }
    els.flows.addEventListener('change', function () {
      try {
        localStorage.setItem('holdings:flows', els.flows.checked ? '1' : '0');
      } catch (e) {
        /* ignore */
      }
    });

    // 切到本页签时懒加载总览（首次与每次进入都刷新，避免看到旧文件状态）；
    // 深链 (#holdings) 直接进入时也要加载，否则面板停在「正在读取…」
    function loadIfVisible() {
      if ((window.location.hash || '').slice(1) === 'holdings') {
        loadOverview();
      }
    }
    var tabBtn = document.getElementById('tab-holdings');
    if (tabBtn) {
      tabBtn.addEventListener('click', loadOverview);
      tabBtn.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          loadOverview();
        }
      });
    }
    window.addEventListener('hashchange', loadIfVisible);
    loadIfVisible();
  })();

  document.addEventListener('DOMContentLoaded', init);
})();
