/**
 * Task Assistant Agent - Core Utilities & Navigation
 * Handles Toasts, HTML Escaping, Navigation Tabs, and Settings Modal.
 */

// Global App State & Event Bus
window.TaskAssistant = window.TaskAssistant || {
  currentTasks: [],
  currentEmails: [],
  isSendingMessage: false
};

// Utility: Toast Notification
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  let icon = 'fa-info-circle';
  if (type === 'success') icon = 'fa-circle-check';
  if (type === 'error') icon = 'fa-circle-exclamation';

  toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
window.showToast = showToast;

// Utility: Glassmorphic In-App Confirm Dialog (Guarantees execution without browser suppression)
function showConfirmDialog({ title = 'Xác Nhận Xóa', message, confirmText = 'Xác Nhận Xóa', onConfirm }) {
  const modal = document.getElementById('confirmDialogModal');
  const titleEl = document.getElementById('confirmDialogTitle');
  const msgEl = document.getElementById('confirmDialogMessage');
  const acceptBtn = document.getElementById('btnConfirmAccept');
  const dismissBtn = document.getElementById('btnConfirmDismiss');
  const closeBtn = document.getElementById('btnCancelConfirmDialog');

  if (!modal) {
    onConfirm?.();
    return;
  }

  if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-danger"></i> <span>${escapeHtml(title)}</span>`;
  if (msgEl) msgEl.textContent = message;
  if (acceptBtn) {
    const span = acceptBtn.querySelector('span');
    if (span) span.textContent = confirmText;
  }

  const cleanup = () => {
    modal.classList.remove('active');
    if (acceptBtn) acceptBtn.onclick = null;
    if (dismissBtn) dismissBtn.onclick = null;
    if (closeBtn) closeBtn.onclick = null;
  };

  if (acceptBtn) {
    acceptBtn.onclick = (e) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      cleanup();
      onConfirm?.();
    };
  }

  if (dismissBtn) {
    dismissBtn.onclick = (e) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      cleanup();
    };
  }

  if (closeBtn) {
    closeBtn.onclick = (e) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      cleanup();
    };
  }
  modal.onclick = (e) => {
    if (e.target === modal) cleanup();
  };

  modal.classList.add('active');
}
window.showConfirmDialog = showConfirmDialog;


// Utility: HTML Escaping
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

// Navigation Tabs Handler
function initNavigation() {
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabContents = document.querySelectorAll('.tab-content');

  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.getAttribute('data-tab');
      navTabs.forEach(t => t.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      document.getElementById(targetTab)?.classList.add('active');

      // Refresh specific tab data
      if (targetTab === 'tab-kanban' && window.loadTasks) window.loadTasks();
      if (targetTab === 'tab-projects' && window.projectsManager) window.projectsManager.loadProjects();
      if (targetTab === 'tab-rag' && window.loadDocs) window.loadDocs();
    });
  });
}
window.initNavigation = initNavigation;
window.appCore = {
  showToast,
  escapeHtml
};


// Settings & System Config
async function loadSettings() {
  const apiKeyStatusBadge = document.getElementById('apiKeyStatusBadge');
  if (!apiKeyStatusBadge) return;

  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();

    if (data.gemini_api_key_set) {
      apiKeyStatusBadge.innerHTML = `
        <span class="status-dot active"></span>
        <span class="indicator-text">${data.gemini_model} (Active)</span>
      `;
      const keyInput = document.getElementById('settingGeminiApiKey');
      if (keyInput) keyInput.placeholder = `Key đang lưu: ${data.gemini_api_key_masked}`;
    } else {
      apiKeyStatusBadge.innerHTML = `
        <span class="status-dot warning"></span>
        <span class="indicator-text">Nhập Gemini API Key</span>
      `;
      const keyInput = document.getElementById('settingGeminiApiKey');
      if (keyInput) keyInput.placeholder = 'Nhập Google Gemini API Key...';
    }

    const modelSelect = document.getElementById('settingGeminiModel');
    if (modelSelect) modelSelect.value = data.gemini_model || 'gemini-flash-latest';
    
    const hostInput = document.getElementById('settingSmtpHost');
    if (hostInput) hostInput.value = data.smtp_host || '';
    
    const portInput = document.getElementById('settingSmtpPort');
    if (portInput) portInput.value = data.smtp_port || 587;
    
    const userInput = document.getElementById('settingSmtpUser');
    if (userInput) userInput.value = data.smtp_user || '';
    
    const devEmailInput = document.getElementById('settingDevEmail');
    if (devEmailInput) devEmailInput.value = data.dev_email || '';
    
    const tlsSelect = document.getElementById('settingSmtpTls');
    if (tlsSelect) tlsSelect.value = data.smtp_tls ? 'true' : 'false';

    if (data.smtp_password_set) {
      const passInput = document.getElementById('settingSmtpPassword');
      if (passInput) passInput.placeholder = '••••••••';
    }
  } catch (e) {
    console.error('Error loading settings:', e);
  }
}
window.loadSettings = loadSettings;

function initSettingsModal() {
  const settingsModal = document.getElementById('settingsModal');
  const apiKeyStatusBadge = document.getElementById('apiKeyStatusBadge');
  const btnOpenSettings = document.getElementById('btnOpenSettings');
  const btnCloseSettingsModal = document.getElementById('btnCloseSettingsModal');
  const btnCancelSettingsModal = document.getElementById('btnCancelSettingsModal');
  const settingsForm = document.getElementById('settingsForm');
  const btnToggleApiKeyVis = document.getElementById('btnToggleApiKeyVis');

  if (apiKeyStatusBadge) {
    apiKeyStatusBadge.addEventListener('click', () => {
      loadSettings();
      settingsModal?.classList.add('active');
    });
  }

  if (btnOpenSettings) {
    btnOpenSettings.addEventListener('click', () => {
      loadSettings();
      settingsModal?.classList.add('active');
    });
  }

  btnCloseSettingsModal?.addEventListener('click', () => settingsModal?.classList.remove('active'));
  btnCancelSettingsModal?.addEventListener('click', () => settingsModal?.classList.remove('active'));

  if (btnToggleApiKeyVis) {
    btnToggleApiKeyVis.addEventListener('click', () => {
      const input = document.getElementById('settingGeminiApiKey');
      if (input) input.type = input.type === 'password' ? 'text' : 'password';
    });
  }

  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const apiKey = document.getElementById('settingGeminiApiKey').value.trim();
      const model = document.getElementById('settingGeminiModel').value;
      const smtpHost = document.getElementById('settingSmtpHost').value.trim();
      const smtpPort = parseInt(document.getElementById('settingSmtpPort').value) || 587;
      const smtpUser = document.getElementById('settingSmtpUser').value.trim();
      const smtpPass = document.getElementById('settingSmtpPassword').value;
      const devEmail = document.getElementById('settingDevEmail').value.trim();
      const smtpTls = document.getElementById('settingSmtpTls').value === 'true';

      const payload = {
        gemini_model: model,
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_user: smtpUser,
        dev_email: devEmail,
        smtp_tls: smtpTls
      };

      if (apiKey) payload.gemini_api_key = apiKey;
      if (smtpPass) payload.smtp_password = smtpPass;

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          showToast('Đã lưu cấu hình hệ thống thành công!', 'success');
          settingsModal?.classList.remove('active');
          loadSettings();
        } else {
          showToast('Lỗi khi lưu cài đặt', 'error');
        }
      } catch (err) {
        showToast('Lỗi mạng khi lưu cài đặt', 'error');
      }
    });
  }
}
window.initSettingsModal = initSettingsModal;
