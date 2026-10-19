/**
 * Task Assistant Agent - RAG Knowledge Base & Semantic Search Tester
 * Handles Document Indexing, File Uploads, Scope Transfer (General vs Project), and ChromaDB Testing.
 */

let currentDocsList = [];
let currentProjectsList = [];
let currentDocFilter = 'ALL';
let activeMoveTargetFilename = '';

async function loadDocs() {
  const indexedDocsList = document.getElementById('indexedDocsList');
  const ragChunksInfo = document.getElementById('ragChunksInfo');
  const ragTotalCount = document.getElementById('ragTotalCount');
  if (!indexedDocsList) return;

  try {
    const res = await fetch('/api/docs');
    if (!res.ok) return;
    const data = await res.json();

    if (ragChunksInfo) ragChunksInfo.textContent = `${data.total_chunks || 0} chunks vector`;

    currentDocsList = data.files || [];
    currentProjectsList = data.projects || [];

    if (ragTotalCount) ragTotalCount.textContent = currentDocsList.length;

    populateProjectDropdowns(currentProjectsList);
    renderFilteredDocs();
  } catch (e) {
    console.error('Error loading docs:', e);
  }
}
window.loadDocs = loadDocs;

function populateProjectDropdowns(projects) {
  const uploadSelect = document.getElementById('uploadProjectSelect');
  const moveSelect = document.getElementById('moveDocProjectSelect');

  const optionsHTML = projects.length === 0
    ? '<option value="">-- Chưa có dự án nào (tạo tại tab Dự Án) --</option>'
    : `
      <option value="">-- Chọn dự án / website --</option>
      ${projects.map(p => `<option value="${window.escapeHtml ? window.escapeHtml(p) : p}">${window.escapeHtml ? window.escapeHtml(p) : p}</option>`).join('')}
    `;

  if (uploadSelect) uploadSelect.innerHTML = optionsHTML;
  if (moveSelect) moveSelect.innerHTML = optionsHTML;
}

function renderFilteredDocs() {
  const indexedDocsList = document.getElementById('indexedDocsList');
  if (!indexedDocsList) return;

  let filtered = currentDocsList;
  if (currentDocFilter === 'GENERAL') {
    filtered = currentDocsList.filter(f => (f.scope_type || 'GENERAL').toUpperCase() === 'GENERAL');
  } else if (currentDocFilter === 'PROJECT') {
    filtered = currentDocsList.filter(f => (f.scope_type || '').toUpperCase() === 'PROJECT');
  }

  if (filtered.length === 0) {
    indexedDocsList.innerHTML = '<div style="color: var(--text-dim); font-size: 0.8rem; text-align: center; padding: 20px;">Chưa có tài liệu nào thuộc danh mục này.</div>';
    return;
  }

  indexedDocsList.innerHTML = filtered.map(f => {
    const displayName = f.clean_name || f.name;
    let icon = 'fa-file-lines';
    if (displayName.endsWith('.pdf')) icon = 'fa-file-pdf';
    else if (displayName.endsWith('.md')) icon = 'fa-file-code';
    else if (displayName.endsWith('.xlsx') || displayName.endsWith('.xls') || displayName.endsWith('.csv')) icon = 'fa-file-excel';

    const isProject = (f.scope_type || '').toUpperCase() === 'PROJECT';
    const catBadge = isProject
      ? `<span class="badge-tag blue" style="font-size: 0.65rem;" title="Dự án: ${window.escapeHtml ? window.escapeHtml(f.project_name || 'Riêng') : (f.project_name || 'Riêng')}"><i class="fa-solid fa-folder-closed"></i> ${window.escapeHtml ? window.escapeHtml(f.project_name || 'Dự án riêng') : (f.project_name || 'Dự án riêng')}</span>`
      : `<span class="badge-tag green" style="font-size: 0.65rem;"><i class="fa-solid fa-globe"></i> Kỹ thuật chung</span>`;

    return `
      <div class="doc-card">
        <div class="doc-card-info">
          <i class="fa-solid ${icon} doc-icon"></i>
          <div>
            <div class="doc-name">${window.escapeHtml ? window.escapeHtml(displayName) : displayName}</div>
            <div class="doc-meta">${f.size_kb} KB • ${catBadge}</div>
          </div>
        </div>
        <div class="doc-actions-row">
          <button type="button" class="btn-action-outline btn-sm btn-move-doc" 
                  data-filename="${encodeURIComponent(displayName)}" 
                  data-scope="${f.scope_type || 'GENERAL'}" 
                  data-project="${encodeURIComponent(f.project_name || '')}" 
                  title="Chuyển tài liệu vào dự án chung hoặc riêng">
            <i class="fa-solid fa-arrow-right-arrow-left"></i> <span>Chuyển phạm vi</span>
          </button>
          <button type="button" class="btn-card-del btn-delete-doc" data-filename="${encodeURIComponent(displayName)}" title="Xóa tài liệu">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  // Delete listener
  indexedDocsList.querySelectorAll('.btn-delete-doc').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const fn = btn.getAttribute('data-filename');
      if (fn) deleteDoc(fn);
    });
  });

  // Move Scope listener
  indexedDocsList.querySelectorAll('.btn-move-doc').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const fn = decodeURIComponent(btn.getAttribute('data-filename') || '');
      const scope = btn.getAttribute('data-scope') || 'GENERAL';
      const proj = decodeURIComponent(btn.getAttribute('data-project') || '');
      openMoveDocModal(fn, scope, proj);
    });
  });
}

function openMoveDocModal(filename, currentScope, currentProject) {
  activeMoveTargetFilename = filename;
  const modal = document.getElementById('moveDocModal');
  const targetNameEl = document.getElementById('moveDocTargetName');
  const radioGeneral = document.getElementById('scopeRadioGeneral');
  const radioProject = document.getElementById('scopeRadioProject');
  const projectGroup = document.getElementById('moveDocProjectGroup');
  const projectSelect = document.getElementById('moveDocProjectSelect');
  const customProjectInput = document.getElementById('moveDocCustomProject');

  if (!modal) return;

  if (targetNameEl) targetNameEl.textContent = filename;

  if (currentScope === 'PROJECT') {
    if (radioProject) radioProject.checked = true;
    if (projectGroup) projectGroup.style.display = 'block';
  } else {
    if (radioGeneral) radioGeneral.checked = true;
    if (projectGroup) projectGroup.style.display = 'none';
  }

  // Pre-select project in dropdown
  if (projectSelect) {
    let found = false;
    for (let opt of projectSelect.options) {
      if (opt.value && opt.value.toLowerCase() === currentProject.toLowerCase()) {
        opt.selected = true;
        found = true;
        break;
      }
    }
    if (!found) {
      projectSelect.value = '';
      if (customProjectInput) customProjectInput.value = currentProject;
    } else {
      if (customProjectInput) customProjectInput.value = '';
    }
  }

  modal.classList.add('active');
}

async function saveMoveDocScope() {
  if (!activeMoveTargetFilename) return;

  const modal = document.getElementById('moveDocModal');
  const radioProject = document.getElementById('scopeRadioProject');
  const projectSelect = document.getElementById('moveDocProjectSelect');
  const customProjectInput = document.getElementById('moveDocCustomProject');

  const isProject = radioProject ? radioProject.checked : false;
  const scopeType = isProject ? 'PROJECT' : 'GENERAL';

  let finalProjectName = '';
  if (isProject) {
    finalProjectName = (customProjectInput && customProjectInput.value.trim()) || (projectSelect && projectSelect.value.trim()) || '';
    if (!finalProjectName) {
      window.showToast?.('Vui lòng chọn hoặc nhập tên dự án cho tài liệu riêng!', 'warning');
      return;
    }
  }

  window.showToast?.(`Đang chuyển phạm vi cho "${activeMoveTargetFilename}"...`, 'info');

  try {
    const res = await fetch('/api/docs/scope', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: activeMoveTargetFilename,
        scope_type: scopeType,
        project_name: finalProjectName
      })
    });

    if (res.ok) {
      const data = await res.json();
      window.showToast?.(data.message || 'Chuyển phạm vi tài liệu thành công!', 'success');
      if (modal) modal.classList.remove('active');
      await loadDocs();
    } else {
      const err = await res.json();
      window.showToast?.(err.detail || 'Lỗi khi chuyển phạm vi tài liệu', 'error');
    }
  } catch (e) {
    window.showToast?.('Lỗi kết nối server khi chuyển phạm vi', 'error');
  }
}

async function deleteDoc(encodedFilename) {
  const rawName = decodeURIComponent(encodedFilename);
  window.showConfirmDialog({
    title: 'Xác Nhận Xóa Tài Liệu',
    message: `Bạn có chắc muốn xóa vĩnh viễn tài liệu "${rawName}" khỏi kho tài liệu và cập nhật lại chỉ mục RAG không?`,
    confirmText: 'Xóa Tài Liệu',
    onConfirm: async () => {
      window.showToast?.(`Đang xóa ${rawName}...`, 'info');
      try {
        const res = await fetch(`/api/docs/${encodedFilename}`, { method: 'DELETE' });
        if (res.ok) {
          window.showToast?.(`Đã xóa "${rawName}" thành công!`, 'success');
          loadDocs();
        } else {
          const err = await res.json();
          window.showToast?.(err.detail || 'Lỗi khi xóa tài liệu', 'error');
        }
      } catch (e) {
        window.showToast?.('Lỗi kết nối server khi xóa tài liệu', 'error');
      }
    }
  });
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  // Read selected scope & project
  const catRadio = document.querySelector('input[name="docCategory"]:checked');
  const scopeType = catRadio ? catRadio.value : 'GENERAL';
  formData.append('scope_type', scopeType);

  if (scopeType === 'PROJECT') {
    const projectSelect = document.getElementById('uploadProjectSelect');
    const projName = projectSelect ? projectSelect.value : '';
    formData.append('project_name', projName);
  } else {
    formData.append('project_name', '');
  }

  window.showToast?.(`Đang tải lên và index ${file.name}...`, 'info');

  try {
    const res = await fetch('/api/docs/upload', {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      const data = await res.json();
      const successMsg = data.message || `Đã index thành công ${file.name} vào ChromaDB!`;
      window.showToast?.(successMsg, 'success');
      loadDocs();
      if (data.excel_import) {
        if (window.loadTasks) window.loadTasks();
        if (window.updateStatsAndProgress) window.updateStatsAndProgress();
      }
    } else {
      const err = await res.json();
      window.showToast?.(err.detail || 'Lỗi khi upload file', 'error');
    }
  } catch (e) {
    window.showToast?.('Lỗi mạng khi tải lên tài liệu', 'error');
  }
}
window.uploadFile = uploadFile;

async function runRagSearch() {
  const ragTestInput = document.getElementById('ragTestInput');
  const ragSearchResults = document.getElementById('ragSearchResults');
  if (!ragTestInput || !ragSearchResults) return;

  const q = ragTestInput.value.trim();
  if (!q) return;

  ragSearchResults.innerHTML = '<div style="text-align: center; color: var(--text-dim); padding: 30px;"><i class="fa-solid fa-circle-notch fa-spin"></i> Đang tìm kiếm trong Vector Store...</div>';

  try {
    const res = await fetch('/api/docs/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, top_k: 4 })
    });
    if (!res.ok) {
      ragSearchResults.innerHTML = '<div style="color: var(--status-blocked); padding: 20px; text-align: center;"><i class="fa-solid fa-triangle-exclamation"></i> Không thể truy vấn Vector Store. Vui lòng bấm nút <b>"Index Lại Tất Cả"</b> để làm mới chỉ mục.</div>';
      return;
    }
    const data = await res.json();
    const results = data.results || [];

    if (results.length === 0) {
      ragSearchResults.innerHTML = '<div class="empty-state"><i class="fa-solid fa-magnifying-glass"></i><p>Không tìm thấy kết quả phù hợp.</p></div>';
      return;
    }

    ragSearchResults.innerHTML = results.map(r => `
      <div class="rag-result-card">
        <div class="rag-result-meta">
          <span class="source-badge"><i class="fa-regular fa-file"></i> ${r.source} (Chunk ${r.chunk_index})</span>
          <span class="score-badge">Độ khớp: ${(r.relevance_score * 100).toFixed(1)}%</span>
        </div>
        <div class="rag-result-content">${window.escapeHtml?.(r.content) || r.content}</div>
      </div>
    `).join('');
  } catch (e) {
    ragSearchResults.innerHTML = '<div style="color: var(--status-blocked); padding: 20px;">Lỗi khi truy vấn RAG.</div>';
  }
}
window.runRagSearch = runRagSearch;

function initRag() {
  const dropZone = document.getElementById('dropZone');
  const fileUploadInput = document.getElementById('fileUploadInput');
  const btnReindexDocs = document.getElementById('btnReindexDocs');
  const btnRunRagSearch = document.getElementById('btnRunRagSearch');
  const ragTestInput = document.getElementById('ragTestInput');

  // Upload Scope category radio toggle
  const labelCatGeneral = document.getElementById('labelCatGeneral');
  const labelCatProject = document.getElementById('labelCatProject');
  const uploadProjectWrapper = document.getElementById('uploadProjectSelectWrapper');
  const radioInputs = document.querySelectorAll('input[name="docCategory"]');

  radioInputs.forEach(radio => {
    radio.addEventListener('change', () => {
      if (radio.value === 'PROJECT') {
        labelCatGeneral?.classList.remove('active');
        labelCatProject?.classList.add('active');
        if (uploadProjectWrapper) uploadProjectWrapper.style.display = 'block';
      } else {
        labelCatGeneral?.classList.add('active');
        labelCatProject?.classList.remove('active');
        if (uploadProjectWrapper) uploadProjectWrapper.style.display = 'none';
      }
    });
  });

  // Move Modal handlers
  const modalMove = document.getElementById('moveDocModal');
  const btnCloseMove = document.getElementById('btnCloseMoveDocModal');
  const btnCancelMove = document.getElementById('btnCancelMoveDocModal');
  const btnSaveMove = document.getElementById('btnSaveMoveDocScope');
  const scopeRadioGeneral = document.getElementById('scopeRadioGeneral');
  const scopeRadioProject = document.getElementById('scopeRadioProject');
  const moveDocProjectGroup = document.getElementById('moveDocProjectGroup');

  if (scopeRadioGeneral && scopeRadioProject && moveDocProjectGroup) {
    scopeRadioGeneral.addEventListener('change', () => {
      if (scopeRadioGeneral.checked) moveDocProjectGroup.style.display = 'none';
    });
    scopeRadioProject.addEventListener('change', () => {
      if (scopeRadioProject.checked) moveDocProjectGroup.style.display = 'block';
    });
  }

  if (btnCloseMove && modalMove) {
    btnCloseMove.addEventListener('click', () => modalMove.classList.remove('active'));
  }
  if (btnCancelMove && modalMove) {
    btnCancelMove.addEventListener('click', () => modalMove.classList.remove('active'));
  }
  if (modalMove) {
    modalMove.addEventListener('click', (e) => {
      if (e.target === modalMove) modalMove.classList.remove('active');
    });
  }
  if (btnSaveMove) {
    btnSaveMove.addEventListener('click', saveMoveDocScope);
  }

  // Dropzone file upload
  if (dropZone && fileUploadInput) {
    dropZone.addEventListener('click', () => fileUploadInput.click());

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });

    fileUploadInput.addEventListener('change', () => {
      if (fileUploadInput.files && fileUploadInput.files[0]) {
        uploadFile(fileUploadInput.files[0]);
      }
    });
  }

  if (btnReindexDocs) {
    btnReindexDocs.addEventListener('click', async () => {
      window.showToast?.('Đang re-index toàn bộ tài liệu...', 'info');
      try {
        const res = await fetch('/api/docs/reindex', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          window.showToast?.(data.message || 'Re-index thành công!', 'success');
          loadDocs();
        }
      } catch (e) {
        window.showToast?.('Lỗi khi re-index', 'error');
      }
    });
  }

  if (btnRunRagSearch) {
    btnRunRagSearch.addEventListener('click', runRagSearch);
  }

  if (ragTestInput) {
    ragTestInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') runRagSearch();
    });
  }

  // 2-Tier Document Nav Buttons
  const docTabBtns = document.querySelectorAll('.doc-tab-btn');
  docTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      docTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDocFilter = btn.getAttribute('data-doctype') || 'ALL';
      renderFilteredDocs();
    });
  });
}
window.initRag = initRag;
