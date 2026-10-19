/**
 * Task Assistant Agent - Kanban Task Board & Monthly Report Export
 * Handles Board Rendering, Task CRUD, Blocker management, Search & Excel Export.
 */

let currentTasks = [];

async function loadTasks() {
  try {
    const res = await fetch('/api/tasks');
    if (!res.ok) return;
    const data = await res.json();
    currentTasks = data.tasks || [];
    window.TaskAssistant.currentTasks = currentTasks;
    renderKanbanCards(currentTasks);
    
    const kanbanTotalBadge = document.getElementById('kanbanTotalBadge');
    if (kanbanTotalBadge) kanbanTotalBadge.textContent = currentTasks.length;
    
    if (window.updateStatsAndProgress) window.updateStatsAndProgress();
  } catch (e) {
    console.error('Error loading tasks:', e);
  }
}
window.loadTasks = loadTasks;

function renderKanbanCards(tasks) {
  const cardsTodo = document.getElementById('cardsTodo');
  const cardsInProgress = document.getElementById('cardsInProgress');
  const cardsBlocked = document.getElementById('cardsBlocked');
  const cardsDone = document.getElementById('cardsDone');

  if (!cardsTodo || !cardsInProgress || !cardsBlocked || !cardsDone) return;

  cardsTodo.innerHTML = '';
  cardsInProgress.innerHTML = '';
  cardsBlocked.innerHTML = '';
  cardsDone.innerHTML = '';

  let cTodo = 0, cProg = 0, cBlock = 0, cDone = 0;

  tasks.forEach(task => {
    const card = createKanbanCardElement(task);
    switch (task.status) {
      case 'TODO':
        cardsTodo.appendChild(card);
        cTodo++;
        break;
      case 'IN_PROGRESS':
        cardsInProgress.appendChild(card);
        cProg++;
        break;
      case 'BLOCKED':
        cardsBlocked.appendChild(card);
        cBlock++;
        break;
      case 'DONE':
        cardsDone.appendChild(card);
        cDone++;
        break;
    }
  });

  const countColTodo = document.getElementById('countColTodo');
  const countColInProgress = document.getElementById('countColInProgress');
  const countColBlocked = document.getElementById('countColBlocked');
  const countColDone = document.getElementById('countColDone');

  if (countColTodo) countColTodo.textContent = cTodo;
  if (countColInProgress) countColInProgress.textContent = cProg;
  if (countColBlocked) countColBlocked.textContent = cBlock;
  if (countColDone) countColDone.textContent = cDone;
}
window.renderKanbanCards = renderKanbanCards;

function createKanbanCardElement(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.setAttribute('data-id', task.id);

  let blockerHtml = '';
  if (task.status === 'BLOCKED' && task.blocker_reason) {
    blockerHtml = `
      <div class="card-blocker-box">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>${window.escapeHtml?.(task.blocker_reason) || task.blocker_reason}</span>
      </div>
    `;
  }

  let deadlineHtml = '';
  if (task.deadline) {
    const isOverdue = new Date(task.deadline) < new Date() && task.status !== 'DONE';
    deadlineHtml = `
      <div class="card-deadline ${isOverdue ? 'overdue' : ''}">
        <i class="fa-regular fa-calendar"></i>
        <span>${task.deadline} ${isOverdue ? '(Quá hạn)' : ''}</span>
      </div>
    `;
  }

    let sourceBadge = '';
    if (task.source_type === 'TEAMS_EMAIL') {
      sourceBadge = '<span class="badge-tag warning"><i class="fa-solid fa-bolt"></i> Teams/Email</span>';
    } else if (task.source_type === 'PROJECT_NEW') {
      sourceBadge = '<span class="badge-tag purple"><i class="fa-solid fa-rocket"></i> Dự Án Mới</span>';
    } else if (task.source_type === 'CHANGE_REQUEST') {
      sourceBadge = '<span class="badge-tag red"><i class="fa-solid fa-arrows-rotate"></i> Change Request</span>';
    } else if (task.source_type === 'MANUAL') {
      sourceBadge = '<span class="badge-tag blue"><i class="fa-solid fa-pen-to-square"></i> Thủ Công</span>';
    }

    let webBadge = '';
    if (task.website_name) {
      webBadge = `<span class="badge-tag"><i class="fa-solid fa-globe"></i> ${window.escapeHtml?.(task.website_name) || task.website_name}</span>`;
    }

  card.innerHTML = `
    <div class="card-top">
      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span class="card-id">#${task.id}</span>
        ${webBadge}
        ${sourceBadge}
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="priority-pill ${task.priority}">${task.priority}</span>
        <button type="button" class="btn-card-del" title="Xóa task này" onclick="deleteTask(${task.id}, event)">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </div>
    </div>
    <div class="card-title">${window.escapeHtml?.(task.title) || task.title}</div>
    ${task.description ? `<div class="card-desc">${window.escapeHtml?.(task.description) || task.description}</div>` : ''}
    ${blockerHtml}
    <div class="card-footer">
      <div class="card-assignee">
        <i class="fa-solid fa-user-circle"></i>
        <span>${task.assignee || 'Dev'}</span>
      </div>
      ${deadlineHtml}
      <select class="card-status-select" onclick="event.stopPropagation()">
        <option value="TODO" ${task.status === 'TODO' ? 'selected' : ''}>TODO</option>
        <option value="IN_PROGRESS" ${task.status === 'IN_PROGRESS' ? 'selected' : ''}>IN PROGRESS</option>
        <option value="BLOCKED" ${task.status === 'BLOCKED' ? 'selected' : ''}>BLOCKED</option>
        <option value="DONE" ${task.status === 'DONE' ? 'selected' : ''}>DONE</option>
      </select>
    </div>
  `;

  // Handle Quick Status Change
  const statusSelect = card.querySelector('.card-status-select');
  statusSelect.addEventListener('change', async (e) => {
    e.stopPropagation();
    const newStatus = statusSelect.value;
    try {
      const res = await fetch('/api/tasks/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.id, status: newStatus })
      });
      if (res.ok) {
        window.showToast?.(`Đã chuyển task #${task.id} sang ${newStatus}`, 'success');
        loadTasks();
      }
    } catch (err) {
      window.showToast?.('Lỗi khi đổi trạng thái task', 'error');
    }
  });

  // Handle Click to Edit
  card.addEventListener('click', () => {
    openEditTaskModal(task);
  });

  return card;
}

// Global Single Task Deletion (Reliable, Direct, No Modal Blockers)
async function deleteTask(taskId, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  try {
    const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    if (res.ok) {
      window.showToast?.(`Đã xóa task #${taskId} thành công!`, 'info');
      const taskModal = document.getElementById('taskModal');
      if (taskModal) taskModal.classList.remove('active');
      await loadTasks();
      if (window.updateStatsAndProgress) window.updateStatsAndProgress();
    } else {
      const err = await res.json().catch(() => ({}));
      window.showToast?.(err.detail || 'Lỗi khi xóa task', 'error');
    }
  } catch (err) {
    console.error('Error deleting task:', err);
    window.showToast?.('Lỗi kết nối khi xóa task', 'error');
  }
}
window.deleteTask = deleteTask;

function deleteCurrentModalTask(event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const idInput = document.getElementById('taskFormId');
  const taskId = idInput ? idInput.value : null;
  if (!taskId) return;
  deleteTask(taskId, event);
}
window.deleteCurrentModalTask = deleteCurrentModalTask;

function openEditTaskModal(task) {
  const taskModal = document.getElementById('taskModal');
  const taskModalTitle = document.getElementById('taskModalTitle');
  const btnDeleteCurrentTask = document.getElementById('btnDeleteCurrentTask');

  document.getElementById('taskFormId').value = task.id;
  document.getElementById('taskFormTitle').value = task.title;
  document.getElementById('taskFormStatus').value = task.status;
  document.getElementById('taskFormPriority').value = task.priority;
  document.getElementById('taskFormAssignee').value = task.assignee || 'Developer';
  document.getElementById('taskFormDeadline').value = task.deadline || '';
  document.getElementById('taskFormBlocker').value = task.blocker_reason || '';
  document.getElementById('taskFormDescription').value = task.description || '';
  document.getElementById('taskFormTags').value = task.tags || '';

  if (btnDeleteCurrentTask) {
    btnDeleteCurrentTask.style.display = 'inline-flex';
  }

  if (taskModalTitle) {
    taskModalTitle.innerHTML = `<i class="fa-solid fa-pen-to-square"></i> Cập Nhật Task #${task.id}`;
  }
  taskModal?.classList.add('active');
}
window.openEditTaskModal = openEditTaskModal;

// Global Clear All Tasks Action
async function clearAllTasks(event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  window.showConfirmDialog({
    title: 'Xóa Toàn Bộ Tasks',
    message: '⚠️ Bạn có chắc chắn muốn XÓA TOÀN BỘ TASKS trên bảng không? Thao tác này sẽ xóa sạch dữ liệu công việc hiện có!',
    confirmText: 'Xóa Toàn Bộ',
    onConfirm: async () => {
      try {
        const res = await fetch('/api/tasks/clear-all', { method: 'DELETE' });
        if (res.ok) {
          const data = await res.json();
          window.showToast?.(data.message || 'Đã xóa toàn bộ tasks!', 'info');
          await loadTasks();
          if (window.updateStatsAndProgress) window.updateStatsAndProgress();
        } else {
          window.showToast?.('Lỗi khi xóa tasks', 'error');
        }
      } catch (e) {
        console.error('Error clearing tasks:', e);
        window.showToast?.('Lỗi kết nối khi xóa tasks', 'error');
      }
    }
  });
}
window.clearAllTasks = clearAllTasks;

function initKanban() {
  const taskSearchInput = document.getElementById('taskSearchInput');
  const btnClearAllTasks = document.getElementById('btnClearAllTasks');
  const btnOpenNewTaskModal = document.getElementById('btnOpenNewTaskModal');
  const btnCloseTaskModal = document.getElementById('btnCloseTaskModal');
  const btnCancelTaskModal = document.getElementById('btnCancelTaskModal');
  const taskForm = document.getElementById('taskForm');
  const taskModal = document.getElementById('taskModal');
  const taskModalTitle = document.getElementById('taskModalTitle');
  const btnDeleteCurrentTask = document.getElementById('btnDeleteCurrentTask');
  const btnExportMonthlyReport = document.getElementById('btnExportMonthlyReport');

  // Filter System
  let currentSourceFilter = 'ALL';
  let currentWebsiteFilter = 'ALL';

  function applyFilters() {
    const val = taskSearchInput ? taskSearchInput.value.toLowerCase().trim() : '';
    const filtered = currentTasks.filter(t => {
      const matchSource = (currentSourceFilter === 'ALL') || (t.source_type === currentSourceFilter);
      const matchWebsite = (currentWebsiteFilter === 'ALL') || 
        (t.website_name && t.website_name.toLowerCase() === currentWebsiteFilter.toLowerCase()) ||
        (t.tags && t.tags.toLowerCase().includes(currentWebsiteFilter.toLowerCase()));
      const matchSearch = !val || 
        t.title.toLowerCase().includes(val) ||
        (t.description && t.description.toLowerCase().includes(val)) ||
        (t.tags && t.tags.toLowerCase().includes(val));
      return matchSource && matchWebsite && matchSearch;
    });
    renderKanbanCards(filtered);
  }

  // Search Filter
  if (taskSearchInput) {
    taskSearchInput.addEventListener('input', applyFilters);
  }

  // Source Filter Pills
  const sourceFilterBtns = document.querySelectorAll('#kanbanSourceFilters .filter-pill');
  sourceFilterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      sourceFilterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentSourceFilter = btn.getAttribute('data-source') || 'ALL';
      applyFilters();
    });
  });

  // Website Select Filter
  const websiteSelectFilter = document.getElementById('kanbanWebsiteFilter');
  if (websiteSelectFilter) {
    websiteSelectFilter.addEventListener('change', (e) => {
      currentWebsiteFilter = e.target.value || 'ALL';
      applyFilters();
    });
  }

  // Clear All Tasks
  if (btnClearAllTasks) {
    btnClearAllTasks.addEventListener('click', clearAllTasks);
  }

  // Open New Task Modal
  if (btnOpenNewTaskModal) {
    btnOpenNewTaskModal.addEventListener('click', () => {
      taskForm?.reset();
      const idInput = document.getElementById('taskFormId');
      if (idInput) idInput.value = '';
      if (taskModalTitle) taskModalTitle.innerHTML = '<i class="fa-solid fa-plus-circle"></i> Tạo Task Mới';
      if (btnDeleteCurrentTask) btnDeleteCurrentTask.style.display = 'none';
      taskModal?.classList.add('active');
    });
  }

  btnCloseTaskModal?.addEventListener('click', () => taskModal?.classList.remove('active'));
  btnCancelTaskModal?.addEventListener('click', () => taskModal?.classList.remove('active'));

  // Task Form Submit
  if (taskForm) {
    taskForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('taskFormId').value;
      const taskData = {
        title: document.getElementById('taskFormTitle').value.trim(),
        status: document.getElementById('taskFormStatus').value,
        priority: document.getElementById('taskFormPriority').value,
        assignee: document.getElementById('taskFormAssignee').value.trim(),
        deadline: document.getElementById('taskFormDeadline').value,
        blocker_reason: document.getElementById('taskFormBlocker').value.trim(),
        description: document.getElementById('taskFormDescription').value.trim(),
        tags: document.getElementById('taskFormTags').value.trim()
      };

      try {
        let res;
        if (id) {
          res = await fetch(`/api/tasks/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
          });
        } else {
          res = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
          });
        }

        if (res.ok) {
          window.showToast?.(id ? 'Cập nhật task thành công!' : 'Tạo task mới thành công!', 'success');
          taskModal?.classList.remove('active');
          loadTasks();
        } else {
          window.showToast?.('Có lỗi xảy ra khi lưu task', 'error');
        }
      } catch (err) {
        window.showToast?.('Lỗi kết nối server', 'error');
      }
    });
  }

  // Monthly Report Excel Export Button
  if (btnExportMonthlyReport) {
    btnExportMonthlyReport.addEventListener('click', async () => {
      window.showToast?.('Đang kết xuất file Báo Cáo Tháng (.xlsx)...', 'info');
      try {
        const response = await fetch('/api/tasks/export-monthly-report');
        if (!response.ok) {
          const err = await response.json();
          window.showToast?.(err.detail || 'Lỗi khi xuất file báo cáo', 'error');
          return;
        }

        // Trigger file download in browser
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const now = new Date();
        const monthStr = String(now.getMonth() + 1).padStart(2, '0');
        const yearStr = now.getFullYear();
        a.download = `Monthly_Report_${monthStr}_${yearStr}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        window.showToast?.('Đã tải xuống file Báo Cáo Tháng (.xlsx) thành công!', 'success');
      } catch (e) {
        console.error(e);
        window.showToast?.('Lỗi kết nối khi xuất file Excel', 'error');
      }
    });
  }
}
window.initKanban = initKanban;
window.kanbanManager = {
  loadTasks,
  renderKanbanCards
};
