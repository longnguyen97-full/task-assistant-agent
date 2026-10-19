/**
 * ============================================================================
 * PROJECTS MODULE: NEW PROJECT PLANNING & SCOPE CHANGE NOTES
 * (STRICT TIMELINE PRESERVATION FOR ONGOING PROJECTS)
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

  let projectsList = [];
  let changeNotesList = [];

  // 1. Load Projects
  async function loadProjects() {
    try {
      const res = await fetch('/api/projects');
      const data = await res.json();
      projectsList = data.projects || [];
      populateProjectSelect(projectsList);
      await loadChangeNotes();
      renderProjectsGrid(projectsList, changeNotesList);
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

  // 3. Populate Project Dropdown
  function populateProjectSelect(projects) {
    if (!projectSelect) return;
    if (projects.length === 0) {
      projectSelect.innerHTML = `<option value="">-- Chưa có dự án nào --</option>`;
      return;
    }

    projectSelect.innerHTML = `
      <option value="">-- Chọn dự án đang chạy --</option>
      ${projects.map(p => `
        <option value="${p.id}" data-name="${escapeHTML(p.name)}">${escapeHTML(p.name)} (${p.status})</option>
      `).join('')}
    `;
  }

  // 4. Render Projects Display Grid
  function renderProjectsGrid(projects, changeNotes) {
    if (!projectsGrid) return;
    const countBadge = document.getElementById('projectsCountBadge');
    if (countBadge) countBadge.textContent = `${projects.length} dự án`;

    if (projects.length === 0) {
      projectsGrid.innerHTML = `<p class="text-muted" style="grid-column: 1 / -1; padding: 2rem 0; text-align: center;">Chưa có dự án nào. Bấm nút <strong>+ Họp Dự Án Mới</strong> ở trên để bắt đầu lập kế hoạch!</p>`;
      return;
    }

    projectsGrid.innerHTML = projects.map(p => {
      // Find change notes for this project
      const notes = changeNotes.filter(n => n.project_id === p.id || (n.project_name && n.project_name.toLowerCase() === p.name.toLowerCase()));
      const notesCount = notes.length;
      let phases = [];
      try {
        phases = p.phases_json ? JSON.parse(p.phases_json) : [];
      } catch (e) {}

      return `
        <div class="project-display-card">
          <div class="project-card-header">
            <h4><i class="fa-solid fa-folder-closed text-purple"></i> ${escapeHTML(p.name)}</h4>
            <span class="badge-tag ${p.status === 'IN_PROGRESS' ? 'blue' : 'purple'}">${escapeHTML(p.status)}</span>
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
            <i class="fa-solid fa-layer-group"></i> <span>Xem Chi Tiết 4 Giai Đoạn & Kế Hoạch</span>
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

    projectsGrid.querySelectorAll('.btn-view-project').forEach(btn => {
      btn.addEventListener('click', () => {
        const pId = parseInt(btn.getAttribute('data-id'), 10);
        const project = projectsList.find(x => x.id === pId);
        if (project) openProjectDetailModal(project);
      });
    });
  }

  // 5. Submit New Project Plan Form
  async function handleNewProjectSubmit(e) {
    e.preventDefault();
    const nameInput = document.getElementById('newProjectName');
    const deadlineInput = document.getElementById('newProjectDeadline');
    const reqInput = document.getElementById('newProjectRequirements');
    const btnSubmit = document.getElementById('btnGeneratePlan');

    const name = nameInput.value.trim();
    const deadline = deadlineInput.value;
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
          target_deadline: deadline
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

  // 6. Submit Change Note Form (Preserve Timeline)
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

    if (modalTitle) {
      modalTitle.innerHTML = `<i class="fa-solid fa-diagram-project text-purple"></i> ${escapeHTML(p.name)}`;
    }

    modalBody.innerHTML = `
      <div class="modal-project-meta-box">
        <div class="meta-item"><strong>Trạng thái:</strong> <span class="badge-tag blue">${escapeHTML(p.status)}</span></div>
        <div class="meta-item"><strong>Bắt đầu:</strong> <span>${p.start_date || 'Gần đây'}</span></div>
        <div class="meta-item"><strong>Hạn chót:</strong> <span class="text-warning">${p.target_deadline || 'Chưa định'}</span></div>
        <div class="meta-item"><strong>Change Requests:</strong> <span class="badge-tag orange">${projectNotes.length} thay đổi</span></div>
      </div>

      <div class="phases-detail-container">
        <h4 class="subheading"><i class="fa-solid fa-calendar-week text-cyan"></i> 📅 Phân Kỳ & Timeline 4 Giai Đoạn (WBS)</h4>
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
    `;

    modal.classList.add('active');
  }

  // Event Listeners
  document.addEventListener('DOMContentLoaded', () => {
    if (newProjectForm) newProjectForm.addEventListener('submit', handleNewProjectSubmit);
    if (changeNoteForm) changeNoteForm.addEventListener('submit', handleChangeNoteSubmit);
    if (btnRefreshProjects) btnRefreshProjects.addEventListener('click', loadProjects);
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
    loadChangeNotes
  };
})();
