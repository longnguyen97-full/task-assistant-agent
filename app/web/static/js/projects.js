/**
 * ============================================================================
 * PROJECTS MODULE: NEW PROJECT PLANNING, TIMELINE & HOT/COLD STORAGE TIERS
 * (STRICT TIMELINE PRESERVATION & AI STORAGE TIER ADVISOR)
 * ============================================================================
 */

(function () {
  const newProjectForm = document.getElementById('newProjectForm');
  const changeNoteForm = document.getElementById('changeNoteForm');
  const projectSelect = document.getElementById('changeProjectSelect');
  const projectsGrid = document.getElementById('projectsDisplayGrid');
  const planPreviewBox = document.getElementById('planPreviewBox');
  const planPreviewContent = document.getElementById('planPreviewContent');
  const btnClosePlanPreview = document.getElementById('btnClosePlanPreview');
  const btnRefreshProjects = document.getElementById('btnRefreshProjects');
  const btnRunAiAdvisor = document.getElementById('btnRunAiAdvisor');
  const btnCloseAiProposals = document.getElementById('btnCloseAiProposals');
  const aiAdvisorProposalsBox = document.getElementById('aiAdvisorProposalsBox');
  const aiProposalsList = document.getElementById('aiProposalsList');

  let projectsList = [];
  let changeNotesList = [];
  let currentTierFilter = 'ALL'; // 'ALL', 'HOT', 'COLD'

  // 1. Load Projects
  async function loadProjects() {
    try {
      const res = await fetch('/api/projects');
      const data = await res.json();
      projectsList = data.projects || [];
      populateProjectSelect(projectsList);
      updateTierFilterCounts();
      await loadChangeNotes();
      renderProjectsGrid();
    } catch (err) {
      console.error('Failed to load projects:', err);
      if (projectsGrid) {
        projectsGrid.innerHTML = `
          <div class="ops-loading-state">
            <i class="fa-solid fa-triangle-exclamation text-warning"></i>
            <p>Không thể tải danh sách dự án.</p>
          </div>
        `;
      }
    }
  }

  // 2. Load Change Notes
  async function loadChangeNotes() {
    try {
      const res = await fetch('/api/projects/change-notes');
      const data = await res.json();
      changeNotesList = data.change_notes || [];
    } catch (err) {
      console.error('Failed to load change notes:', err);
    }
  }

  // 3. Update Filter Counts
  function updateTierFilterCounts() {
    const countAll = document.getElementById('countAllProjects');
    const countHot = document.getElementById('countHotProjects');
    const countCold = document.getElementById('countColdProjects');
    const countBadge = document.getElementById('projectsCountBadge');

    const total = projectsList.length;
    const hotCount = projectsList.filter(p => (p.storage_tier || 'HOT').toUpperCase() === 'HOT').length;
    const coldCount = projectsList.filter(p => (p.storage_tier || 'HOT').toUpperCase() === 'COLD').length;

    if (countAll) countAll.textContent = total;
    if (countHot) countHot.textContent = hotCount;
    if (countCold) countCold.textContent = coldCount;
    if (countBadge) countBadge.textContent = `${total} dự án (${hotCount} Hot, ${coldCount} Cold)`;
  }

  // 4. Populate Project Dropdown
  function populateProjectSelect(projects) {
    if (!projectSelect) return;
    if (projects.length === 0) {
      projectSelect.innerHTML = `<option value="">-- Chưa có dự án nào --</option>`;
      return;
    }

    projectSelect.innerHTML = `
      <option value="">-- Chọn dự án đang chạy --</option>
      ${projects.map(p => `
        <option value="${p.id}" data-name="${escapeHTML(p.name)}">${escapeHTML(p.name)} [${(p.storage_tier || 'HOT').toUpperCase()}] (${p.status})</option>
      `).join('')}
    `;
  }

  // 5. Render Projects Display Grid with Filter & Tier Badges
  function renderProjectsGrid() {
    if (!projectsGrid) return;

    // Filter projects based on current tier filter
    let displayedProjects = projectsList;
    if (currentTierFilter === 'HOT') {
      displayedProjects = projectsList.filter(p => (p.storage_tier || 'HOT').toUpperCase() === 'HOT');
    } else if (currentTierFilter === 'COLD') {
      displayedProjects = projectsList.filter(p => (p.storage_tier || 'HOT').toUpperCase() === 'COLD');
    }

    if (displayedProjects.length === 0) {
      const filterLabel = currentTierFilter === 'HOT' ? 'Hot Storage' : currentTierFilter === 'COLD' ? 'Cold Storage' : 'hệ thống';
      projectsGrid.innerHTML = `
        <div class="empty-tier-placeholder" style="grid-column: 1 / -1; padding: 3rem 1rem; text-align: center; color: var(--text-dim);">
          <i class="fa-solid fa-box-open" style="font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.6;"></i>
          <p>Không có dự án nào trong vùng <strong>${filterLabel}</strong>.</p>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Bạn có thể tạo dự án mới hoặc chuyển dự án từ vùng khác sang.</span>
        </div>
      `;
      return;
    }

    projectsGrid.innerHTML = displayedProjects.map(p => {
      const tier = (p.storage_tier || 'HOT').toUpperCase();
      const isHot = tier === 'HOT';
      const notes = changeNotesList.filter(n => n.project_id === p.id || (n.project_name && n.project_name.toLowerCase() === p.name.toLowerCase()));
      const notesCount = notes.length;
      let phases = [];
      try {
        phases = p.phases_json ? JSON.parse(p.phases_json) : [];
      } catch (e) {}

      return `
        <div class="project-display-card tier-${tier.toLowerCase()}">
          <div class="project-card-header">
            <div>
              <div class="project-tier-pill-row">
                <span class="badge-tag tier-badge ${isHot ? 'hot' : 'cold'}">
                  <i class="fa-solid ${isHot ? 'fa-fire' : 'fa-snowflake'}"></i> ${isHot ? 'Hot Storage' : 'Cold Storage'}
                </span>
                <span class="badge-tag ${p.status === 'IN_PROGRESS' ? 'blue' : 'purple'}">${escapeHTML(p.status)}</span>
              </div>
              <h4 class="project-card-title"><i class="fa-solid fa-folder-closed text-purple"></i> ${escapeHTML(p.name)}</h4>
            </div>

            <div class="project-header-actions-col">
              <button type="button" class="btn-tier-toggle ${isHot ? 'to-cold' : 'to-hot'} btn-switch-tier" data-id="${p.id}" data-target="${isHot ? 'COLD' : 'HOT'}" data-name="${escapeHTML(p.name)}" title="${isHot ? 'Chuyển dự án sang Cold Storage' : 'Đưa dự án lên Hot Storage'}">
                <i class="fa-solid ${isHot ? 'fa-snowflake' : 'fa-fire'}"></i>
                <span>${isHot ? 'Chuyển Cold' : 'Đưa lên Hot'}</span>
              </button>
              <button type="button" class="btn-card-del btn-delete-project" data-id="${p.id}" data-name="${escapeHTML(p.name)}" title="Xóa dự án này">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </div>

          <div class="project-meta-row">
            <span><i class="fa-solid fa-calendar-day"></i> Bắt đầu: ${p.start_date || 'Gần đây'}</span>
            <span><i class="fa-solid fa-flag-checkered text-cyan"></i> Hạn: ${p.target_deadline || 'Chưa định'}</span>
            <span><i class="fa-solid fa-arrows-rotate text-amber"></i> ${notesCount} thay đổi</span>
          </div>

          ${p.plan_summary ? `<p class="text-dim text-sm">${escapeHTML(p.plan_summary)}</p>` : ''}

          <!-- Phase mini timeline badges -->
          ${phases.length > 0 ? `
            <div class="phase-mini-badges">
              ${phases.map(ph => `
                <div class="phase-badge-chip">
                  <span class="ph-name">GĐ ${ph.phase_num}</span>
                  <span class="ph-dates">${ph.start_date.slice(5)} -> ${ph.end_date.slice(5)}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}

          <button class="btn-action-outline btn-sm w-100 btn-view-project" data-id="${p.id}">
            <i class="fa-solid fa-layer-group"></i> <span>Xem Chi Tiết ${phases.length > 0 ? `${phases.length} Giai Đoạn` : ''} & Kế Hoạch</span>
          </button>

          <!-- Change Notes Accordion / List -->
          <div class="project-change-notes-list">
            <span class="diag-lbl"><i class="fa-solid fa-shield-halved"></i> Nhật Ký Thay Đổi (Timeline Gốc Bảo Toàn):</span>
            ${notes.length === 0
              ? '<span class="text-dim text-xs">Chưa có Change Request nào phát sinh.</span>'
              : notes.slice(0, 2).map(n => `
                <div class="change-note-item">
                  <span class="change-note-title"><i class="fa-solid fa-arrow-right"></i> ${escapeHTML(n.title)}</span>
                  <span class="change-note-body">${escapeHTML(n.content.substring(0, 90))}${n.content.length > 90 ? '...' : ''}</span>
                  <span class="text-dim text-xs">Yêu cầu bởi: <em>${escapeHTML(n.author || 'Khách hàng')}</em> (${formatDateTime(n.created_at)})</span>
                </div>
              `).join('')}
          </div>
        </div>
      `;
    }).join('');

    // Attach View Detail listeners
    projectsGrid.querySelectorAll('.btn-view-project').forEach(btn => {
      btn.addEventListener('click', () => {
        const pId = parseInt(btn.getAttribute('data-id'), 10);
        const project = projectsList.find(x => x.id === pId);
        if (project) openProjectDetailModal(project);
      });
    });

    // Attach Switch Tier listeners
    projectsGrid.querySelectorAll('.btn-switch-tier').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const pId = parseInt(btn.getAttribute('data-id'), 10);
        const targetTier = btn.getAttribute('data-target');
        const pName = btn.getAttribute('data-name');
        if (pId && targetTier) {
          updateProjectStorageTier(pId, targetTier, pName);
        }
      });
    });

    // Attach Delete listeners
    projectsGrid.querySelectorAll('.btn-delete-project').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const pId = parseInt(btn.getAttribute('data-id'), 10);
        const pName = btn.getAttribute('data-name');
        if (pId) deleteProject(pId, pName);
      });
    });
  }

  // 6. Update Project Storage Tier (Dev có thể chuyển tùy ý)
  async function updateProjectStorageTier(projectId, targetTier, projectName = '') {
    try {
      const tierLabel = targetTier === 'HOT' ? 'Hot Storage 🔥' : 'Cold Storage ❄️';
      window.showToast?.(`Đang chuyển dự án sang ${tierLabel}...`, 'info');

      const res = await fetch(`/api/projects/${projectId}/storage-tier`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ storage_tier: targetTier })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        window.showToast?.(data.message, 'success');
        await loadProjects();

        // If detail modal is open for this project, update it
        const detailModal = document.getElementById('projectDetailModal');
        if (detailModal && detailModal.classList.contains('active')) {
          const updatedProj = projectsList.find(x => x.id === projectId);
          if (updatedProj) openProjectDetailModal(updatedProj);
        }

        // If AI advisor proposals box is visible, refresh it
        if (aiAdvisorProposalsBox && aiAdvisorProposalsBox.style.display !== 'none') {
          runAiAdvisor();
        }
      } else {
        window.showToast?.(data.detail || 'Lỗi khi cập nhật vùng lưu trữ', 'error');
      }
    } catch (err) {
      console.error('Failed to update project storage tier:', err);
      window.showToast?.('Lỗi kết nối khi chuyển vùng lưu trữ', 'error');
    }
  }
  window.switchProjectTier = updateProjectStorageTier;

  // 7. AI Storage Advisor (Đánh Giá & Đề Xuất Phân Vùng Lưu Trữ)
  async function runAiAdvisor() {
    if (!btnRunAiAdvisor || !aiAdvisorProposalsBox || !aiProposalsList) return;

    try {
      btnRunAiAdvisor.disabled = true;
      btnRunAiAdvisor.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang Phân Tích Tasks & Chat...</span>`;

      const res = await fetch('/api/projects/tier-analysis');
      const data = await res.json();

      aiAdvisorProposalsBox.style.display = 'block';

      if (!data || data.status !== 'success') {
        aiProposalsList.innerHTML = `<div class="ai-proposal-empty error"><i class="fa-solid fa-triangle-exclamation"></i> Không thể phân tích dự án lúc này.</div>`;
        return;
      }

      const proposals = data.proposals || [];

      if (proposals.length === 0) {
        aiProposalsList.innerHTML = `
          <div class="ai-proposal-empty-state">
            <div class="empty-icon"><i class="fa-solid fa-circle-check text-success"></i></div>
            <div class="empty-content">
              <strong>Tất cả các dự án đều đang ở phân vùng tối ưu!</strong>
              <p>AI Agent đã kiểm tra toàn bộ ${data.total_projects} dự án qua số task đang chạy và lịch sử chat: Không có dự án nào bị bỏ quên ở Cold hoặc gây nhiễu ở Hot.</p>
            </div>
          </div>
        `;
        return;
      }

      aiProposalsList.innerHTML = proposals.map(p => {
        const curTier = p.current_tier;
        const sugTier = p.suggested_tier;
        const isSugHot = sugTier === 'HOT';
        const m = p.metrics || {};

        return `
          <div class="ai-proposal-card urgency-${(p.urgency || 'low').toLowerCase()}">
            <div class="ai-proposal-header">
              <div class="ai-proposal-title-box">
                <span class="ai-proposal-proj-name"><i class="fa-solid fa-folder text-purple"></i> ${escapeHTML(p.project_name)}</span>
                <div class="ai-proposal-tier-transition">
                  <span class="tier-pill ${curTier.toLowerCase()}">${curTier === 'HOT' ? '🔥 Hot' : '❄️ Cold'}</span>
                  <i class="fa-solid fa-arrow-right text-dim"></i>
                  <span class="tier-pill ${sugTier.toLowerCase()} highlight">${isSugHot ? '🔥 Hot Storage' : '❄️ Cold Storage'}</span>
                </div>
              </div>
              <span class="badge-tag urgency-tag ${(p.urgency || '').toLowerCase()}">Mức độ: ${escapeHTML(p.urgency || 'LOW')}</span>
            </div>

            <p class="ai-proposal-reason"><i class="fa-solid fa-circle-info text-cyan"></i> ${escapeHTML(p.reason)}</p>

            <div class="ai-proposal-metrics-row">
              <span class="metric-pill"><i class="fa-solid fa-list-check"></i> ${m.active_tasks_count || 0} active tasks</span>
              <span class="metric-pill ${m.urgent_tasks_count > 0 ? 'highlight-orange' : ''}"><i class="fa-solid fa-bolt"></i> ${m.urgent_tasks_count || 0} urgent</span>
              <span class="metric-pill"><i class="fa-solid fa-check-double"></i> ${m.done_tasks_count || 0} done</span>
              <span class="metric-pill"><i class="fa-solid fa-comments"></i> ${m.chat_mentions || 0} chat mentions</span>
            </div>

            <div class="ai-proposal-footer-actions">
              <button type="button" class="btn-action-primary btn-sm btn-accept-tier-proposal" data-id="${p.project_id}" data-target="${sugTier}" data-name="${escapeHTML(p.project_name)}">
                <i class="fa-solid ${isSugHot ? 'fa-fire' : 'fa-snowflake'}"></i>
                <span>Chấp Nhận Chuyển Sang ${isSugHot ? 'Hot Storage' : 'Cold Storage'}</span>
              </button>
              <button type="button" class="btn-action-outline btn-sm btn-dismiss-proposal">
                Bỏ Qua
              </button>
            </div>
          </div>
        `;
      }).join('');

      // Attach accept proposal handlers
      aiProposalsList.querySelectorAll('.btn-accept-tier-proposal').forEach(btn => {
        btn.addEventListener('click', async () => {
          const pId = parseInt(btn.getAttribute('data-id'), 10);
          const targetTier = btn.getAttribute('data-target');
          const pName = btn.getAttribute('data-name');
          if (pId && targetTier) {
            await updateProjectStorageTier(pId, targetTier, pName);
          }
        });
      });

      // Attach dismiss handler
      aiProposalsList.querySelectorAll('.btn-dismiss-proposal').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const card = e.target.closest('.ai-proposal-card');
          if (card) {
            card.style.opacity = '0';
            card.style.transform = 'translateY(-6px)';
            setTimeout(() => {
              card.remove();
              if (aiProposalsList.children.length === 0) {
                aiAdvisorProposalsBox.style.display = 'none';
              }
            }, 200);
          }
        });
      });

    } catch (err) {
      console.error('Error running AI Advisor:', err);
      window.showToast?.('Lỗi kết nối khi chạy AI Storage Advisor', 'error');
    } finally {
      btnRunAiAdvisor.disabled = false;
      btnRunAiAdvisor.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> <span>AI Đánh Giá Dự Án</span>`;
    }
  }
  window.runAiTierAdvisor = runAiAdvisor;

  // 8. Submit New Project Plan Form
  async function handleNewProjectSubmit(e) {
    e.preventDefault();
    const nameInput = document.getElementById('newProjectName');
    const deadlineInput = document.getElementById('newProjectDeadline');
    const tierInput = document.getElementById('newProjectStorageTier');
    const reqInput = document.getElementById('newProjectRequirements');
    const btnSubmit = document.getElementById('btnGeneratePlan');

    const name = nameInput.value.trim();
    const deadline = deadlineInput.value;
    const storageTier = tierInput ? tierInput.value : 'HOT';
    const requirements = reqInput.value.trim();

    if (!name || !requirements) {
      window.appCore.showToast('Vui lòng nhập tên dự án và nội dung yêu cầu!', 'warning');
      return;
    }

    try {
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang Lập Kế Hoạch 4 Pha...</span>`;

      const res = await fetch('/api/projects/new-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: name,
          requirements: requirements,
          target_deadline: deadline,
          storage_tier: storageTier
        })
      });

      const data = await res.json();
      if (data.success) {
        window.appCore.showToast(`Đã sinh Kế Hoạch WBS & ${data.total_created_tasks} tasks thành công!`, 'success');

        // Show Preview
        if (planPreviewBox && planPreviewContent) {
          planPreviewContent.innerHTML = window.marked ? window.marked.parse(data.plan_markdown) : data.plan_markdown;
          planPreviewBox.style.display = 'block';
        }

        nameInput.value = '';
        deadlineInput.value = '';
        reqInput.value = '';

        await loadProjects();
        if (window.kanbanManager && window.kanbanManager.loadTasks) {
          window.kanbanManager.loadTasks();
        }
      } else {
        window.appCore.showToast('Lỗi khi lập kế hoạch: ' + (data.detail || 'Lỗi server'), 'error');
      }
    } catch (err) {
      window.appCore.showToast('Lỗi kết nối khi gửi yêu cầu lập kế hoạch', 'error');
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> <span>Tạo Kế Hoạch & Timeline (4 Pha)</span>`;
    }
  }

  // 9. Submit Change Note Form (Preserve Timeline)
  async function handleChangeNoteSubmit(e) {
    e.preventDefault();
    const selectedOption = projectSelect.options[projectSelect.selectedIndex];
    const projectName = selectedOption ? selectedOption.getAttribute('data-name') : '';
    const titleInput = document.getElementById('changeNoteTitle');
    const authorInput = document.getElementById('changeNoteAuthor');
    const contentInput = document.getElementById('changeNoteContent');
    const btnSubmit = document.getElementById('btnRecordChangeNote');

    const title = titleInput.value.trim();
    const author = authorInput.value.trim() || 'Khách hàng';
    const content = contentInput.value.trim();

    if (!projectName || !title || !content) {
      window.appCore.showToast('Vui lòng chọn dự án và nhập đầy đủ thông tin thay đổi!', 'warning');
      return;
    }

    try {
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang Ghi Nhận...</span>`;

      const res = await fetch('/api/projects/change-notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: projectName,
          title: title,
          content: content,
          author: author
        })
      });

      const data = await res.json();
      if (data.success) {
        window.appCore.showToast(`Đã ghi nhận Change Request! Timeline gốc được bảo toàn 100%.`, 'success');
        titleInput.value = '';
        contentInput.value = '';

        await loadProjects();
        document.getElementById('changeNoteModal')?.classList.remove('active');
        if (window.kanbanManager && window.kanbanManager.loadTasks) {
          window.kanbanManager.loadTasks();
        }
      } else {
        window.appCore.showToast('Lỗi khi ghi nhận thay đổi: ' + (data.detail || 'Lỗi server'), 'error');
      }
    } catch (err) {
      window.appCore.showToast('Lỗi kết nối khi ghi nhận thay đổi', 'error');
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `<i class="fa-solid fa-clipboard-check"></i> <span>Ghi Nhận Thay Đổi (Bảo Toàn Timeline)</span>`;
    }
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return `${d.getDate()}/${d.getMonth() + 1} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
    } catch (e) {
      return isoStr;
    }
  }

  function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
  }

  // 10. Open Project Detail Modal
  function openProjectDetailModal(p) {
    const modal = document.getElementById('projectDetailModal');
    const modalTitle = document.getElementById('projectDetailModalTitle');
    const modalBody = document.getElementById('projectDetailBody');
    if (!modal || !modalBody) return;

    let phases = [];
    try {
      phases = p.phases_json ? JSON.parse(p.phases_json) : [];
    } catch (e) {}

    const projectNotes = changeNotesList.filter(n => n.project_id === p.id || (n.project_name && n.project_name.toLowerCase() === p.name.toLowerCase()));
    const tier = (p.storage_tier || 'HOT').toUpperCase();
    const isHot = tier === 'HOT';

    if (modalTitle) {
      modalTitle.innerHTML = `<i class="fa-solid fa-diagram-project text-purple"></i> ${escapeHTML(p.name)}`;
    }

    modalBody.innerHTML = `
      <div class="modal-project-meta-box">
        <div class="meta-item">
          <strong>Phân Vùng:</strong> 
          <span class="badge-tag tier-badge ${isHot ? 'hot' : 'cold'}" style="margin-right: 8px;">
            <i class="fa-solid ${isHot ? 'fa-fire' : 'fa-snowflake'}"></i> ${isHot ? 'Hot Storage' : 'Cold Storage'}
          </span>
          <button type="button" class="btn-tier-toggle ${isHot ? 'to-cold' : 'to-hot'} btn-sm" id="btnModalToggleTier" style="display: inline-flex; padding: 2px 8px; font-size: 0.75rem;">
            <i class="fa-solid ${isHot ? 'fa-snowflake' : 'fa-fire'}"></i>
            <span>${isHot ? 'Chuyển sang Cold' : 'Đưa lên Hot'}</span>
          </button>
        </div>
        <div class="meta-item"><strong>Trạng thái:</strong> <span class="badge-tag blue">${escapeHTML(p.status)}</span></div>
        <div class="meta-item"><strong>Bắt đầu:</strong> <span>${p.start_date || 'Gần đây'}</span></div>
        <div class="meta-item"><strong>Hạn chót:</strong> <span class="text-warning">${p.target_deadline || 'Chưa định'}</span></div>
        <div class="meta-item"><strong>Change Requests:</strong> <span class="badge-tag orange">${projectNotes.length} thay đổi</span></div>
      </div>

      <div class="phases-detail-container">
        <h4 class="subheading"><i class="fa-solid fa-calendar-week text-cyan"></i> 📅 Phân Kỳ & Timeline ${phases.length > 0 ? `${phases.length} Giai Đoạn` : ''} (WBS)</h4>
        ${phases.length === 0 ? '<p class="text-dim">Chưa có dữ liệu giai đoạn chi tiết.</p>' : `
          <div class="phases-list">
            ${phases.map(ph => `
              <div class="phase-detail-card">
                <div class="phase-card-header">
                  <h5><i class="fa-solid fa-circle-check text-purple"></i> ${escapeHTML(ph.name)}</h5>
                  <span class="badge-date"><i class="fa-regular fa-calendar"></i> Từ ${ph.start_date} đến ${ph.end_date} (${ph.duration_days || ''} ngày)</span>
                </div>
                <div class="phase-card-row">
                  <span class="phase-label"><i class="fa-solid fa-users"></i> Thành viên:</span>
                  <span class="phase-val">${escapeHTML(ph.assignees || 'Developer')}</span>
                </div>
                <div class="phase-card-row">
                  <span class="phase-label"><i class="fa-solid fa-bullseye text-cyan"></i> Mục tiêu:</span>
                  <span class="phase-val highlight">${escapeHTML(ph.objective || '')}</span>
                </div>
                <div class="phase-card-row">
                  <span class="phase-label"><i class="fa-solid fa-list-check"></i> Nội dung thực hiện:</span>
                  <ul class="phase-task-bullets">
                    ${(ph.tasks || []).map(t => `<li>${escapeHTML(t)}</li>`).join('')}
                  </ul>
                </div>
              </div>
            `).join('')}
          </div>
        `}
      </div>

      ${p.timeline_doc ? `
        <div class="wbs-markdown-box">
          <h4 class="subheading"><i class="fa-solid fa-file-contract text-purple"></i> 📋 Kế Hoạch Đầy Đủ & WBS</h4>
          <div class="markdown-body p-3 border-subtle rounded">
            ${window.marked ? window.marked.parse(p.timeline_doc) : escapeHTML(p.timeline_doc)}
          </div>
        </div>
      ` : ''}

      <div class="project-change-notes-modal-section">
        <h4 class="subheading"><i class="fa-solid fa-shield-halved text-amber"></i> 🔄 Nhật Ký Thay Đổi Đã Lưu (Timeline Gốc Bảo Toàn 100%)</h4>
        ${projectNotes.length === 0 ? '<p class="text-dim text-xs">Chưa có Change Request nào phát sinh cho dự án này.</p>' : `
          <div class="change-notes-timeline">
            ${projectNotes.map(n => `
              <div class="change-note-modal-item">
                <div class="change-note-header">
                  <strong>${escapeHTML(n.title)}</strong>
                  <span class="text-dim text-xs">Bởi: <em>${escapeHTML(n.author || 'Khách hàng')}</em> (${formatDateTime(n.created_at)})</span>
                </div>
                <p class="change-note-content">${escapeHTML(n.content)}</p>
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 15px; border-top: 1px solid var(--border-subtle); margin-top: 10px;">
        <button type="button" class="btn-action-danger btn-sm" id="btnDeleteProjectFromDetail">
          <i class="fa-solid fa-trash-can"></i> <span>Xóa Dự Án Này</span>
        </button>
        <button type="button" class="btn-action-outline btn-sm" id="btnCloseProjectDetailModalBottom">
          Đóng
        </button>
      </div>
    `;

    document.getElementById('btnModalToggleTier')?.addEventListener('click', () => {
      const nextTier = isHot ? 'COLD' : 'HOT';
      updateProjectStorageTier(p.id, nextTier, p.name);
    });

    document.getElementById('btnDeleteProjectFromDetail')?.addEventListener('click', () => {
      deleteProject(p.id, p.name);
    });

    document.getElementById('btnCloseProjectDetailModalBottom')?.addEventListener('click', () => {
      modal.classList.remove('active');
    });

    modal.classList.add('active');
  }

  // 11. Delete Project Action
  function deleteProject(pId, pName) {
    window.showConfirmDialog({
      title: 'Xác Nhận Xóa Dự Án',
      message: `Bạn có chắc muốn xóa vĩnh viễn dự án "${pName}" không? Toàn bộ Change Requests liên quan sẽ bị xóa bỏ khỏi hệ thống.`,
      confirmText: 'Xóa Dự Án',
      onConfirm: async () => {
        window.showToast?.(`Đang xóa dự án "${pName}"...`, 'info');
        try {
          const res = await fetch(`/api/projects/${pId}`, { method: 'DELETE' });
          if (res.ok) {
            window.showToast?.(`Đã xóa dự án "${pName}" thành công!`, 'success');
            const modalDetail = document.getElementById('projectDetailModal');
            if (modalDetail) modalDetail.classList.remove('active');
            await loadProjects();
            if (window.loadTasks) window.loadTasks();
            if (window.loadDocs) window.loadDocs();
          } else {
            const err = await res.json();
            window.showToast?.(err.detail || 'Lỗi khi xóa dự án', 'error');
          }
        } catch (e) {
          window.showToast?.('Lỗi kết nối khi xóa dự án', 'error');
        }
      }
    });
  }

  // 12. Init Event Listeners
  document.addEventListener('DOMContentLoaded', () => {
    if (newProjectForm) newProjectForm.addEventListener('submit', handleNewProjectSubmit);
    if (changeNoteForm) changeNoteForm.addEventListener('submit', handleChangeNoteSubmit);
    if (btnRefreshProjects) btnRefreshProjects.addEventListener('click', loadProjects);
    if (btnRunAiAdvisor) btnRunAiAdvisor.addEventListener('click', runAiAdvisor);
    if (btnCloseAiProposals) {
      btnCloseAiProposals.addEventListener('click', () => {
        if (aiAdvisorProposalsBox) aiAdvisorProposalsBox.style.display = 'none';
      });
    }

    // Filter Buttons Listener
    const tierFilterGroup = document.getElementById('tierFilterGroup');
    if (tierFilterGroup) {
      tierFilterGroup.querySelectorAll('.tier-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          tierFilterGroup.querySelectorAll('.tier-filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentTierFilter = btn.getAttribute('data-tier') || 'ALL';
          renderProjectsGrid();
        });
      });
    }

    if (btnClosePlanPreview) {
      btnClosePlanPreview.addEventListener('click', () => {
        if (planPreviewBox) planPreviewBox.style.display = 'none';
      });
    }

    // Modal: Project Detail
    const modalDetail = document.getElementById('projectDetailModal');
    const btnCloseDetail = document.getElementById('btnCloseProjectDetailModal');
    if (btnCloseDetail && modalDetail) {
      btnCloseDetail.addEventListener('click', () => modalDetail.classList.remove('active'));
      modalDetail.addEventListener('click', (e) => {
        if (e.target === modalDetail) modalDetail.classList.remove('active');
      });
    }

    // Modal: New Project Plan
    const modalNew = document.getElementById('newProjectModal');
    const btnOpenNew = document.getElementById('btnOpenNewProjectModal');
    const btnCloseNew = document.getElementById('btnCloseNewProjectModal');
    const btnCancelNew = document.getElementById('btnCancelNewProjectModal');
    if (btnOpenNew && modalNew) {
      btnOpenNew.addEventListener('click', () => {
        if (planPreviewBox) planPreviewBox.style.display = 'none';
        modalNew.classList.add('active');
        document.getElementById('newProjectName')?.focus();
      });
    }
    btnCloseNew?.addEventListener('click', () => modalNew?.classList.remove('active'));
    btnCancelNew?.addEventListener('click', () => modalNew?.classList.remove('active'));
    modalNew?.addEventListener('click', (e) => {
      if (e.target === modalNew) modalNew.classList.remove('active');
    });

    // Modal: Change Note
    const modalChange = document.getElementById('changeNoteModal');
    const btnOpenChange = document.getElementById('btnOpenChangeNoteModal');
    const btnCloseChange = document.getElementById('btnCloseChangeNoteModal');
    const btnCancelChange = document.getElementById('btnCancelChangeNoteModal');
    if (btnOpenChange && modalChange) {
      btnOpenChange.addEventListener('click', () => {
        modalChange.classList.add('active');
      });
    }
    btnCloseChange?.addEventListener('click', () => modalChange?.classList.remove('active'));
    btnCancelChange?.addEventListener('click', () => modalChange?.classList.remove('active'));
    modalChange?.addEventListener('click', (e) => {
      if (e.target === modalChange) modalChange.classList.remove('active');
    });

    loadProjects();
  });

  window.projectsManager = {
    loadProjects,
    loadChangeNotes,
    runAiAdvisor,
    updateProjectStorageTier
  };
})();
