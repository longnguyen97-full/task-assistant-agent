/**
 * Task Assistant Agent - Monitoring & System Observability
 * Manages Telemetry Metrics, Waterfall Traces, and Automated Evals Runner.
 */

let isRunningBenchmark = false;

async function loadMonitoring() {
  const container = document.getElementById('tab-monitoring');
  if (!container) return;

  try {
    const res = await fetch('/api/monitoring/stats');
    if (!res.ok) return;
    const data = await res.json();

    const telem = data.telemetry || {};
    const db = data.database || {};
    const rag = data.vector_store || {};
    const sched = data.scheduler || {};
    const llm = data.llm_config || {};

    // 1. Populate KPI Cards
    const totalReq = telem.total_requests || 0;
    const totalTok = telem.total_tokens || 0;
    const costUsd = telem.total_cost_usd || 0.0;
    const avgLat = telem.avg_latency_ms || 0.0;

    const elTotalReq = document.getElementById('monTotalRequests');
    if (elTotalReq) elTotalReq.textContent = totalReq.toLocaleString();

    const elGuardrailRate = document.getElementById('monGuardrailRate');
    if (elGuardrailRate) {
      elGuardrailRate.textContent = `Tỷ lệ qua Guardrail: ${telem.guardrail_pass_rate || 100}% (${telem.out_of_scope_count || 0} bị chặn)`;
    }

    const elAvgLat = document.getElementById('monAvgLatency');
    if (elAvgLat) {
      elAvgLat.textContent = avgLat > 1000 ? `${(avgLat / 1000).toFixed(2)}s` : `${avgLat.toFixed(1)} ms`;
    }

    const elLatBreak = document.getElementById('monLatencyBreakdown');
    if (elLatBreak) {
      elLatBreak.textContent = `LLM: ${telem.avg_llm_latency_ms || 0}ms | Tools: ${telem.avg_tool_latency_ms || 0}ms`;
    }

    const elTotalTok = document.getElementById('monTotalTokens');
    if (elTotalTok) elTotalTok.textContent = `${totalTok.toLocaleString()} tok`;

    const elTotalCost = document.getElementById('monTotalCost');
    if (elTotalCost) {
      elTotalCost.textContent = costUsd > 0 ? `$${costUsd.toFixed(5)} USD` : '$0.00 (Local Free)';
    }

    const elActiveProvider = document.getElementById('monActiveProvider');
    if (elActiveProvider) {
      const p = (llm.provider || 'ollama').toUpperCase();
      const m = p === 'GEMINI' ? (llm.gemini_model || 'Gemini Flash') : (llm.ollama_model || 'Qwen 2.5');
      elActiveProvider.textContent = `${p} (${m})`;
    }

    // 2. Populate Subsystem Status
    const elLlmDesc = document.getElementById('monLlmDesc');
    if (elLlmDesc) {
      elLlmDesc.textContent = `Provider: ${llm.provider || 'ollama'} | Model: ${llm.provider === 'gemini' ? llm.gemini_model : llm.ollama_model}`;
    }

    const elDbDesc = document.getElementById('monDbDesc');
    if (elDbDesc) {
      elDbDesc.textContent = `Dung lượng: ${db.size_kb || 0} KB | Chế độ: ${db.journal_mode || 'WAL'}`;
    }

    const elRagDesc = document.getElementById('monRagDesc');
    if (elRagDesc) {
      elRagDesc.textContent = `${rag.total_files || 0} tài liệu | ${rag.total_chunks || 0} chunks vector`;
    }

    const elSchedDesc = document.getElementById('monSchedulerDesc');
    if (elSchedDesc) {
      elSchedDesc.textContent = `Trạng thái: ${sched.is_running ? 'Running' : 'Idle'} | Scan kế tiếp: 9:00 AM`;
    }

    // 3. Populate Task & Tier Distribution
    const tasksByStatus = telem.tasks_by_status || {};
    const projectsByTier = telem.projects_by_tier || {};
    const totalTasks = Object.values(tasksByStatus).reduce((a, b) => a + b, 0);

    const elTaskDistSummary = document.getElementById('monTaskDistSummary');
    if (elTaskDistSummary) elTaskDistSummary.textContent = `${totalTasks} Tasks`;

    const elDistPills = document.getElementById('monDistPills');
    if (elDistPills) {
      elDistPills.innerHTML = `
        <span class="dist-pill todo">TODO: ${tasksByStatus['TODO'] || 0}</span>
        <span class="dist-pill in-prog">IN PROGRESS: ${tasksByStatus['IN_PROGRESS'] || 0}</span>
        <span class="dist-pill blocked">BLOCKED: ${tasksByStatus['BLOCKED'] || 0}</span>
        <span class="dist-pill done">DONE: ${tasksByStatus['DONE'] || 0}</span>
        <span class="dist-pill hot">🔥 Hot Projects: ${projectsByTier['HOT'] || 0}</span>
        <span class="dist-pill" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3);">❄️ Cold: ${projectsByTier['COLD'] || 0}</span>
      `;
    }

    // 4. Render Benchmark Card
    renderBenchmarkReport(data.latest_eval);

    // 5. Render Recent Waterfall Traces
    renderTracesTable(data.recent_traces || []);

  } catch (err) {
    console.error('Error loading monitoring stats:', err);
  }
}
window.loadMonitoring = loadMonitoring;

function renderBenchmarkReport(evalReport) {
  const summary = evalReport?.summary;
  const results = evalReport?.results || [];

  const elBadge = document.getElementById('monBenchmarkBadge');
  const elPassRate = document.getElementById('monBmPassRate');
  const elGuardrail = document.getElementById('monBmGuardrailAcc');
  const elTool = document.getElementById('monBmToolAcc');
  const elAvgLat = document.getElementById('monBmAvgLat');
  const elTime = document.getElementById('monBenchmarkTimestamp');
  const tbody = document.getElementById('monBenchmarkTableBody');

  if (!summary || results.length === 0) {
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Chưa có kết quả benchmark. Bấm nút <strong>"Chạy Benchmark Đánh Giá"</strong> ở trên để bắt đầu kiểm thử tự động!</td></tr>';
    }
    return;
  }

  const passPct = summary.pass_rate_percent ?? 100;
  if (elBadge) {
    elBadge.textContent = `${passPct}% PASS`;
    elBadge.className = passPct >= 90 ? 'badge-pass-pill' : 'badge-pass-pill' ;
  }
  if (elPassRate) elPassRate.textContent = `${passPct}%`;
  if (elGuardrail) elGuardrail.textContent = `${summary.guardrail_accuracy_percent ?? 100}%`;
  if (elTool) elTool.textContent = `${summary.tool_calling_accuracy_percent ?? 100}%`;
  if (elAvgLat) {
    const lat = summary.avg_latency_ms || 0;
    elAvgLat.textContent = lat > 1000 ? `${(lat / 1000).toFixed(1)}s` : `${lat.toFixed(0)}ms`;
  }
  if (elTime && evalReport.timestamp) {
    const d = new Date(evalReport.timestamp);
    elTime.textContent = `Lần chạy gần nhất: ${d.toLocaleString('vi-VN')} (${summary.passed}/${summary.total_tests} pass)`;
  }

  if (tbody) {
    tbody.innerHTML = results.map(r => `
      <tr>
        <td><code>${r.id}</code></td>
        <td><span class="trace-tag">${r.category}</span></td>
        <td>${escapeHtml(r.description || r.input)}</td>
        <td>
          <span class="${r.passed ? 'status-badge-pass' : 'status-badge-fail'}">
            ${r.passed ? 'PASS' : 'FAIL'}
          </span>
        </td>
        <td><span class="trace-lat-pill ${r.latency_ms < 1000 ? 'fast' : (r.latency_ms < 4500 ? 'medium' : 'slow')}">${(r.latency_ms / 1000).toFixed(2)}s</span></td>
      </tr>
    `).join('');
  }
}

function renderTracesTable(traces) {
  const tbody = document.getElementById('monTracesTableBody');
  const badge = document.getElementById('monTracesCountBadge');
  if (badge) badge.textContent = `${traces.length} traces`;

  if (!tbody) return;

  if (!traces || traces.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Chưa có lượt thực thi nào được ghi nhận. Hãy gửi tin nhắn qua tab Chat để tạo trace đầu tiên!</td></tr>';
    return;
  }

  tbody.innerHTML = traces.map((t, idx) => {
    const timeStr = t.created_at ? new Date(t.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-';
    const latS = (t.latency_ms / 1000).toFixed(2) + 's';
    const latClass = t.latency_ms < 1000 ? 'fast' : (t.latency_ms < 3500 ? 'medium' : 'slow');
    const costStr = t.cost_usd > 0 ? `$${t.cost_usd.toFixed(5)}` : '$0.00';

    let toolsHtml = '<span style="color: var(--text-dim);">-</span>';
    try {
      const toolNames = typeof t.executed_tools === 'string' ? JSON.parse(t.executed_tools) : t.executed_tools;
      if (Array.isArray(toolNames) && toolNames.length > 0) {
        toolsHtml = toolNames.map(tn => `<span class="trace-tag">${tn}</span>`).join(' ');
      }
    } catch (e) {}

    let statusBadge = '<span class="status-badge-pass">SUCCESS</span>';
    if (t.out_of_scope) {
      statusBadge = '<span class="status-badge-blocked">OUT SCOPE</span>';
    } else if (t.fallback_triggered) {
      statusBadge = '<span class="status-badge-blocked">FALLBACK</span>';
    }

    return `
      <tr>
        <td><code>#${t.id}</code></td>
        <td style="color: var(--text-muted); font-size: 0.76rem;">${timeStr}</td>
        <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(t.user_prompt)}">
          ${escapeHtml(t.user_prompt)}
        </td>
        <td><code>${t.model_name || 'agent'}</code></td>
        <td><span class="trace-lat-pill ${latClass}">${latS}</span></td>
        <td><span style="font-family: var(--font-mono);">${(t.total_tokens || 0).toLocaleString()}</span></td>
        <td style="color: #34d399; font-family: var(--font-mono);">${costStr}</td>
        <td>${toolsHtml}</td>
        <td>${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

async function triggerEvalBenchmark() {
  if (isRunningBenchmark) return;
  isRunningBenchmark = true;

  const btn = document.getElementById('btnTriggerEvalBenchmark');
  const originalHtml = btn ? btn.innerHTML : '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Đang chạy 10 kịch bản test...</span>';
  }

  window.showToast?.('Đang chạy toàn bộ bộ kiểm thử Golden Dataset, vui lòng chờ trong giây lát...', 'info');

  try {
    const res = await fetch('/api/monitoring/benchmark/run', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      window.showToast?.(err.detail || 'Lỗi khi chạy benchmark', 'error');
    } else {
      const report = await res.json();
      const passRate = report.summary?.pass_rate_percent ?? 100;
      window.showToast?.(`Benchmark hoàn tất! Tỷ lệ đạt: ${passRate}% (${report.summary?.passed}/${report.summary?.total_tests})`, 'success');
      renderBenchmarkReport(report);
      loadMonitoring();
    }
  } catch (e) {
    console.error('Benchmark execution error:', e);
    window.showToast?.('Không thể chạy benchmark', 'error');
  } finally {
    isRunningBenchmark = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}
window.triggerEvalBenchmark = triggerEvalBenchmark;

function initMonitoring() {
  const btnRefresh = document.getElementById('btnRefreshMonitoring');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      btnRefresh.querySelector('i')?.classList.add('fa-spin');
      loadMonitoring().finally(() => {
        setTimeout(() => btnRefresh.querySelector('i')?.classList.remove('fa-spin'), 600);
      });
    });
  }

  const btnBenchmark = document.getElementById('btnTriggerEvalBenchmark');
  if (btnBenchmark) {
    btnBenchmark.addEventListener('click', triggerEvalBenchmark);
  }
}
window.initMonitoring = initMonitoring;
