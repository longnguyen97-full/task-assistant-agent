/**
 * Task Assistant Agent - Chat Interface & Daily Notes
 * Handles Chat Streaming, Messages, Tool Badges, Markdown, and Sidebar Stats.
 */

let isSendingMessage = false;

async function loadChatHistory() {
  const chatMessages = document.getElementById('chatMessages');
  if (!chatMessages) return;

  try {
    const res = await fetch('/api/chat/history');
    if (!res.ok) return;
    const history = await res.json();
    
    if (history && history.length > 0) {
      chatMessages.innerHTML = '';
      history.forEach(msg => {
        let toolCalls = [];
        if (msg.tool_calls) {
          try {
            toolCalls = JSON.parse(msg.tool_calls);
          } catch (e) {}
        }
        appendChatMessage(msg.role, msg.content, toolCalls, msg.created_at);
      });
    }
  } catch (e) {
    console.error('Error loading history:', e);
  }
}
window.loadChatHistory = loadChatHistory;

let currentChatAbortController = null;
let lastSubmittedMessageText = '';
let lastSubmittedUserWrapper = null;

function appendChatMessage(role, content, toolCalls = [], timestamp = null) {
  const chatMessages = document.getElementById('chatMessages');
  if (!chatMessages) return;

  const isUser = role === 'user';
  const wrapper = document.createElement('div');
  wrapper.className = `message-wrapper ${isUser ? 'user' : 'assistant'}`;

  if (isUser) {
    lastSubmittedUserWrapper = wrapper;
  }

  const avatarHtml = isUser 
    ? '<div class="msg-avatar"><i class="fa-solid fa-user"></i></div>'
    : '<div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>';

  const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : 'Vừa xong';
  const senderName = isUser ? 'Developer' : 'Task Assistant';

  let toolBadgesHtml = '';
  if (toolCalls && toolCalls.length > 0) {
    toolBadgesHtml = toolCalls.map(tc => `
      <div class="tool-execution-badge">
        <div class="tool-badge-header" onclick="this.nextElementSibling.classList.toggle('open')">
          <span><i class="fa-solid fa-gear"></i> Executed Tool: <strong>${tc.name}</strong></span>
          <i class="fa-solid fa-chevron-down"></i>
        </div>
        <div class="tool-badge-details">
          <div><strong>Input:</strong> <code>${JSON.stringify(tc.args)}</code></div>
          <div style="margin-top: 4px;"><strong>Result:</strong> <code>${typeof tc.result === 'object' ? JSON.stringify(tc.result) : tc.result}</code></div>
        </div>
      </div>
    `).join('');
  }

  const parsedContent = (typeof marked !== 'undefined') ? marked.parse(content || '') : content;

  wrapper.innerHTML = `
    ${avatarHtml}
    <div class="msg-bubble">
      <div class="msg-header">
        <span class="sender-name">${senderName}</span>
        <span class="msg-time">${timeStr}</span>
      </div>
      ${toolBadgesHtml}
      <div class="msg-content markdown-body">
        ${parsedContent}
      </div>
    </div>
  `;

  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
window.appendChatMessage = appendChatMessage;

function appendTypingIndicator() {
  const chatMessages = document.getElementById('chatMessages');
  if (!chatMessages) return;
  const wrapper = document.createElement('div');
  wrapper.id = 'typingIndicator';
  wrapper.className = 'message-wrapper assistant';
  wrapper.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="msg-bubble" style="padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
      <span style="color: var(--text-dim); font-size: 0.85rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Task Assistant đang suy luận và xử lý...</span>
      <button type="button" class="btn-stop-thinking" onclick="abortChatThinking(event)" title="Ngắt luồng & Sửa lại tin nhắn (Esc)">
        <i class="fa-solid fa-stop"></i> <span>Dừng & Sửa lại</span>
      </button>
    </div>
  `;
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) indicator.remove();
}

async function abortChatThinking(event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  if (currentChatAbortController) {
    try {
      currentChatAbortController.abort();
    } catch (e) {}
    currentChatAbortController = null;
  }

  // Notify backend to cancel and delete mistakenly saved user message
  fetch('/api/chat/cancel', { method: 'POST' }).catch(() => {});

  removeTypingIndicator();

  // Remove the uncompleted user message element from the DOM
  if (lastSubmittedUserWrapper && lastSubmittedUserWrapper.parentNode) {
    lastSubmittedUserWrapper.remove();
    lastSubmittedUserWrapper = null;
  }

  // Restore input text so developer can edit and correct it
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.value = lastSubmittedMessageText || '';
    chatInput.style.height = 'auto';
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
    chatInput.focus();
    chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
  }

  isSendingMessage = false;
  const btnSendMessage = document.getElementById('btnSendMessage');
  if (btnSendMessage) {
    btnSendMessage.disabled = false;
    btnSendMessage.classList.remove('btn-send-stop');
    btnSendMessage.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
    btnSendMessage.title = 'Gửi tin nhắn';
  }

  window.showToast?.('Đã dừng suy nghĩ! Nội dung tin nhắn đã được phục hồi để bạn chỉnh sửa.', 'info');
}
window.abortChatThinking = abortChatThinking;

let selectedAttachment = null;

async function handleSendMessage(messageText) {
  const chatInput = document.getElementById('chatInput');
  const btnSendMessage = document.getElementById('btnSendMessage');
  const previewBox = document.getElementById('chatAttachmentPreview');
  const fileInput = document.getElementById('chatFileInput');

  if ((!messageText && !selectedAttachment) || isSendingMessage) return;

  isSendingMessage = true;
  lastSubmittedMessageText = messageText || '';

  // Switch Send button to Stop button while thinking
  if (btnSendMessage) {
    btnSendMessage.disabled = false;
    btnSendMessage.classList.add('btn-send-stop');
    btnSendMessage.innerHTML = '<i class="fa-solid fa-stop"></i>';
    btnSendMessage.title = 'Dừng suy nghĩ & Sửa lại tin nhắn (Esc)';
  }

  let outgoingText = messageText || '';
  let attachedName = '';

  // If file attached, upload first
  if (selectedAttachment) {
    attachedName = selectedAttachment.name;
    const formData = new FormData();
    formData.append('file', selectedAttachment);

    window.showToast?.(`Đang tải lên & index tài liệu: ${attachedName}...`, 'info');
    try {
      const upRes = await fetch('/api/docs/upload', {
        method: 'POST',
        body: formData
      });
      if (upRes.ok) {
        const upData = await upRes.json();
        if (upData.excel_import && window.loadTasks) {
          window.loadTasks();
        }
        if (window.loadDocs) window.loadDocs();
        outgoingText = outgoingText 
          ? `[Đính kèm: ${attachedName}]\n${outgoingText}`
          : `Tôi vừa gửi tài liệu: "${attachedName}". Hãy kiểm tra, trích xuất thông tin và ghi nhận công việc cần làm giúp tôi.`;
      }
    } catch (e) {
      console.error('File upload failed:', e);
    }

    selectedAttachment = null;
    if (fileInput) fileInput.value = '';
    if (previewBox) previewBox.style.display = 'none';
  }

  appendChatMessage('user', outgoingText);
  if (chatInput) {
    chatInput.value = '';
    chatInput.style.height = 'auto';
  }

  appendTypingIndicator();

  currentChatAbortController = new AbortController();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: outgoingText, author: 'Developer' }),
      signal: currentChatAbortController.signal
    });

    removeTypingIndicator();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      window.showToast?.(err.detail || 'Lỗi khi gửi tin nhắn', 'error');
      appendChatMessage('assistant', '⚠️ Đã xảy ra lỗi khi kết nối với AI Agent. Vui lòng thử lại.');
    } else {
      const data = await res.json();
      if (!data.cancelled) {
        appendChatMessage('assistant', data.content, data.tool_calls);
        if (window.loadTasks) window.loadTasks();
        if (window.loadDailyNotes) window.loadDailyNotes();
        if (window.updateStatsAndProgress) window.updateStatsAndProgress();
      }
    }
  } catch (err) {
    removeTypingIndicator();
    if (err.name === 'AbortError') {
      console.log('Chat fetch aborted by user.');
      return;
    }
    console.error(err);
    window.showToast?.('Lỗi mạng khi kết nối server', 'error');
  } finally {
    isSendingMessage = false;
    currentChatAbortController = null;
    if (btnSendMessage) {
      btnSendMessage.disabled = false;
      btnSendMessage.classList.remove('btn-send-stop');
      btnSendMessage.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
      btnSendMessage.title = 'Gửi tin nhắn';
    }
  }
}
window.handleSendMessage = handleSendMessage;

// Daily Notes & Sidebar Planning Stats
async function loadDailyNotes() {
  const dailyNotesList = document.getElementById('dailyNotesList');
  const notesCountPill = document.getElementById('notesCountPill');
  if (!dailyNotesList) return;

  try {
    const res = await fetch('/api/notes?limit=15');
    if (!res.ok) return;
    const data = await res.json();
    const notes = data.notes || [];

    if (notesCountPill) notesCountPill.textContent = notes.length;

    if (notes.length === 0) {
      dailyNotesList.innerHTML = '<div style="text-align: center; color: var(--text-dim); padding: 20px; font-size: 0.8rem;">Chưa có nhật ký nào được ghi nhận.</div>';
      return;
    }

    dailyNotesList.innerHTML = notes.map(n => {
      const timeStr = new Date(n.created_at).toLocaleString('vi-VN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      return `
        <div class="note-item">
          <div class="note-meta">
            <span><i class="fa-solid fa-user-circle"></i> ${n.author}</span>
            <span>${timeStr}</span>
          </div>
          <div class="note-content">${window.escapeHtml?.(n.content) || n.content}</div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Error loading notes:', e);
  }
}
window.loadDailyNotes = loadDailyNotes;

async function updateStatsAndProgress() {
  const statTodo = document.getElementById('statTodo');
  const statInProgress = document.getElementById('statInProgress');
  const statBlocked = document.getElementById('statBlocked');
  const statDone = document.getElementById('statDone');
  const sprintProgressBar = document.getElementById('sprintProgressBar');
  const sprintPercentText = document.getElementById('sprintPercentText');
  const sprintRiskBadge = document.getElementById('sprintRiskBadge');

  if (!statTodo) return;

  try {
    const res = await fetch('/api/planning/analyze');
    if (!res.ok) return;
    const data = await res.json();

    const summary = data.summary || {};
    const risk = data.risk_assessment || {};

    statTodo.textContent = summary.todo || 0;
    statInProgress.textContent = summary.in_progress || 0;
    statBlocked.textContent = summary.blocked || 0;
    statDone.textContent = summary.done || 0;

    const completionRate = data.completion_rate_percent || 0;
    if (sprintProgressBar) sprintProgressBar.style.width = `${completionRate}%`;
    if (sprintPercentText) sprintPercentText.textContent = `${completionRate}% Hoàn thành`;

    const riskLevel = risk.overall_risk || 'LOW';
    if (sprintRiskBadge) {
      sprintRiskBadge.textContent = `Rủi ro: ${riskLevel}`;
      sprintRiskBadge.className = `risk-badge ${riskLevel.toLowerCase()}`;
    }
  } catch (e) {
    console.error('Error updating stats:', e);
  }
}
window.updateStatsAndProgress = updateStatsAndProgress;

function initChat() {
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');
  const btnRefreshStats = document.getElementById('btnRefreshStats');

  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      if (isSendingMessage) {
        abortChatThinking(e);
        return;
      }
      const text = chatInput?.value.trim();
      if (text) handleSendMessage(text);
    });
  }

  // Keyboard shortcut: Press Escape to stop agent thinking & edit message
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isSendingMessage) {
      e.preventDefault();
      abortChatThinking(e);
    }
  });

  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (isSendingMessage) {
          abortChatThinking(e);
          return;
        }
        const text = chatInput.value.trim();
        if (text) handleSendMessage(text);
      }
    });

    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
    });
  }

  document.querySelectorAll('.prompt-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt) handleSendMessage(prompt);
    });
  });

  if (btnRefreshStats) {
    btnRefreshStats.addEventListener('click', () => {
      updateStatsAndProgress();
      loadDailyNotes();
      window.showToast?.('Đã làm mới dữ liệu tiến độ', 'info');
    });
  }

  // File Attachment Listener
  const fileInput = document.getElementById('chatFileInput');
  const previewBox = document.getElementById('chatAttachmentPreview');
  const previewIcon = document.getElementById('previewFileIcon');
  const previewName = document.getElementById('previewFileName');
  const btnRemove = document.getElementById('btnRemoveAttachment');

  if (fileInput && previewBox) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files[0]) {
        selectedAttachment = fileInput.files[0];
        if (previewName) previewName.textContent = selectedAttachment.name;
        if (previewIcon) {
          if (selectedAttachment.type.startsWith('image/')) {
            previewIcon.className = 'fa-solid fa-file-image text-purple';
          } else if (selectedAttachment.name.endsWith('.xlsx') || selectedAttachment.name.endsWith('.xls') || selectedAttachment.name.endsWith('.csv')) {
            previewIcon.className = 'fa-solid fa-file-excel text-green';
          } else {
            previewIcon.className = 'fa-solid fa-file-lines text-cyan';
          }
        }
        previewBox.style.display = 'block';
      }
    });

    if (btnRemove) {
      btnRemove.addEventListener('click', () => {
        selectedAttachment = null;
        fileInput.value = '';
        previewBox.style.display = 'none';
      });
    }
  }
}
window.initChat = initChat;

