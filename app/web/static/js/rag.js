/**
 * Task Assistant Agent - RAG Knowledge Base & Semantic Search Tester
 * Handles Document Indexing, File Uploads, Re-indexing and ChromaDB Testing.
 */

let currentDocsList = [];
let currentDocFilter = 'ALL';

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
    if (ragTotalCount) ragTotalCount.textContent = currentDocsList.length;

    renderFilteredDocs();
  } catch (e) {
    console.error('Error loading docs:', e);
  }
}
window.loadDocs = loadDocs;

function renderFilteredDocs() {
  const indexedDocsList = document.getElementById('indexedDocsList');
  if (!indexedDocsList) return;

  let filtered = currentDocsList;
  if (currentDocFilter === 'GENERAL') {
    filtered = currentDocsList.filter(f => f.name.endsWith('.md') || f.name.includes('specs') || f.name.includes('timeline'));
  } else if (currentDocFilter === 'PROJECT') {
    filtered = currentDocsList.filter(f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls') || f.name.includes('report') || f.name.includes('kig') || f.name.includes('sis'));
  }

  if (filtered.length === 0) {
    indexedDocsList.innerHTML = '<div style="color: var(--text-dim); font-size: 0.8rem; text-align: center; padding: 15px;">Chưa có tài liệu nào thuộc danh mục này.</div>';
    return;
  }

  indexedDocsList.innerHTML = filtered.map(f => {
    let icon = 'fa-file-lines';
    let isGeneral = f.name.endsWith('.md') || f.name.includes('specs') || f.name.includes('timeline');
    if (f.name.endsWith('.pdf')) icon = 'fa-file-pdf';
    if (f.name.endsWith('.md')) icon = 'fa-file-code';
    if (f.name.endsWith('.xlsx') || f.name.endsWith('.xls') || f.name.endsWith('.csv')) icon = 'fa-file-excel';

    const catBadge = isGeneral 
      ? '<span class="badge-tag green" style="font-size: 0.65rem;">Kỹ thuật chung</span>'
      : '<span class="badge-tag blue" style="font-size: 0.65rem;">Dự án riêng</span>';

    return `
      <div class="doc-card">
        <div class="doc-card-info">
          <i class="fa-solid ${icon} doc-icon"></i>
          <div>
            <div class="doc-name">${f.name}</div>
            <div class="doc-meta">${f.size_kb} KB • ${catBadge}</div>
          </div>
        </div>
        <div class="doc-actions-row">
          <span class="badge-tag" style="font-size: 0.68rem;">Đã Index</span>
          <button class="btn-card-del btn-delete-doc" data-filename="${encodeURIComponent(f.name)}" title="Xóa tài liệu">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  indexedDocsList.querySelectorAll('.btn-delete-doc').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const fn = btn.getAttribute('data-filename');
      if (fn) deleteDoc(fn);
    });
  });
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
