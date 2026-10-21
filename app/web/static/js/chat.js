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

function appendChatMessage(role, content, toolCalls = [], timestamp = null, metrics = null) {
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
    const badges = toolCalls.map(tc => `
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

    toolBadgesHtml = `
      <div class="agent-thinking-box">
        <div class="thinking-pill completed" onclick="const d = this.nextElementSibling; const isHidden = d.style.display === 'none'; d.style.display = isHidden ? 'block' : 'none'; const ch = this.querySelector('i.fa-chevron-down, i.fa-chevron-up'); if(ch){ ch.className = isHidden ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'; }">
          <div class="thinking-pill-left">
            <span class="thinking-pill-dot"></span>
            <span><i class="fa-solid fa-brain"></i> Quá trình suy nghĩ & thực thi (${toolCalls.length} công cụ)</span>
          </div>
          <button type="button" class="btn-toggle-thought-details">
            <span>Chi tiết</span> <i class="fa-solid fa-chevron-down"></i>
          </button>
        </div>
        <div class="thought-steps-drawer" style="display: none;">
          ${badges}
        </div>
      </div>
    `;
  }

  let telemetryHtml = '';
  if (!isUser && metrics && (metrics.latency_ms || metrics.total_tokens || metrics.model)) {
    const latSec = (metrics.latency_ms ? (metrics.latency_ms / 1000).toFixed(2) : '0.00') + 's';
    const tokCount = (metrics.total_tokens || 0).toLocaleString();
    const costUsd = metrics.cost_usd ? `$${metrics.cost_usd.toFixed(5)}` : '$0.00';
    const modelLabel = metrics.model || 'Agent';

    telemetryHtml = `
      <div class="msg-telemetry-badge">
        <span class="telemetry-pill lat" title="Tổng độ trễ xử lý (Latency)"><i class="fa-solid fa-bolt"></i> ${latSec}</span>
        <span class="telemetry-pill tok" title="Tổng Tokens (Input + Output)"><i class="fa-solid fa-coins"></i> ${tokCount} tok</span>
        <span class="telemetry-pill cost" title="Ước tính chi phí API"><i class="fa-solid fa-dollar-sign"></i> ${costUsd}</span>
        <span class="telemetry-pill model" title="Mô hình LLM"><i class="fa-solid fa-microchip"></i> ${modelLabel}</span>
      </div>
    `;
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
      ${telemetryHtml}
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
    const isImage = selectedAttachment.type.startsWith('image/') || /\.(png|jpe?g|webp|bmp|gif)$/i.test(attachedName);
    const formData = new FormData();
    formData.append('file', selectedAttachment);

    if (isImage) {
      window.showToast?.(`Đang tải lên hình ảnh thiết kế: ${attachedName}...`, 'info');
      try {
        const upRes = await fetch('/api/chat/upload-image', {
          method: 'POST',
          body: formData
        });
        if (upRes.ok) {
          const upData = await upRes.json();
          outgoingText = outgoingText
            ? `[Đính kèm hình ảnh: ${upData.file_path}]\n${outgoingText}`
            : `[Đính kèm hình ảnh: ${upData.file_path}]\nHãy phân tích hình ảnh này và tìm kiếm file thiết kế tương ứng.`;
        } else {
          window.showToast?.('Lỗi khi tải ảnh lên máy chủ', 'error');
        }
      } catch (e) {
        console.error('Image upload failed:', e);
      }
    } else {
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

function createStreamingAssistantBubble() {
  const chatMessages = document.getElementById('chatMessages');
  if (!chatMessages) return null;

  const wrapper = document.createElement('div');
  wrapper.className = 'message-wrapper assistant';

  wrapper.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="msg-bubble">
      <div class="msg-header">
        <span class="sender-name">Task Assistant</span>
        <span class="msg-time">Đang trả lời...</span>
      </div>
      <div class="agent-thinking-box" id="currentThinkingBox">
        <div class="thinking-pill active" id="currentThinkingPill">
          <div class="thinking-pill-left">
            <span class="thinking-pill-dot"></span>
            <span id="currentThinkingStatusText"><i class="fa-solid fa-brain"></i> Đang khởi tạo...</span>
          </div>
          <button type="button" class="btn-toggle-thought-details" id="currentBtnToggleDetails">
            <span>Chi tiết</span> <i class="fa-solid fa-chevron-down"></i>
          </button>
        </div>
        <div class="thought-steps-drawer" id="currentThoughtDrawer" style="display: none;">
          <!-- Chi tiết suy nghĩ và công cụ được giấu ở đây, bấm Chi Tiết mới mở -->
        </div>
      </div>
      <div class="msg-content markdown-body" id="currentStreamingContent">
        <span class="streaming-cursor" style="color: var(--accent-purple); font-size: 0.85rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Đang chuẩn bị phản hồi...</span>
      </div>
      <div class="msg-telemetry-badge" id="currentTelemetryBadge" style="display: none;"></div>
    </div>
  `;

  // Thiết lập sự kiện toggle cho drawer suy nghĩ
  const pill = wrapper.querySelector('#currentThinkingPill');
  const drawer = wrapper.querySelector('#currentThoughtDrawer');
  const toggleBtn = wrapper.querySelector('#currentBtnToggleDetails');

  const toggleHandler = (e) => {
    e.stopPropagation();
    const isHidden = drawer.style.display === 'none';
    drawer.style.display = isHidden ? 'block' : 'none';
    const chevron = toggleBtn.querySelector('i');
    if (chevron) {
      chevron.className = isHidden ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down';
    }
  };

  if (pill) pill.onclick = toggleHandler;
  if (toggleBtn) toggleBtn.onclick = toggleHandler;

  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return {
    wrapper,
    statusText: wrapper.querySelector('#currentThinkingStatusText'),
    pill,
    drawer,
    contentEl: wrapper.querySelector('#currentStreamingContent'),
    telemetryEl: wrapper.querySelector('#currentTelemetryBadge')
  };
}

async function handleSendMessage(messageText) {
  const chatInput = document.getElementById('chatInput');
  const btnSendMessage = document.getElementById('btnSendMessage');
  const previewBox = document.getElementById('chatAttachmentPreview');
  const fileInput = document.getElementById('chatFileInput');
  const chatMessages = document.getElementById('chatMessages');

  if ((!messageText && !selectedAttachment) || isSendingMessage) return;

  isSendingMessage = true;
  lastSubmittedMessageText = messageText || '';

  // Đổi nút Gửi sang nút Dừng khi đang xử lý
  if (btnSendMessage) {
    btnSendMessage.disabled = false;
    btnSendMessage.classList.add('btn-send-stop');
    btnSendMessage.innerHTML = '<i class="fa-solid fa-stop"></i>';
    btnSendMessage.title = 'Dừng suy nghĩ & Sửa lại tin nhắn (Esc)';
  }

  let outgoingText = messageText || '';
  let attachedName = '';

  // Xử lý đính kèm nếu có
  if (selectedAttachment) {
    attachedName = selectedAttachment.name;
    const isImage = selectedAttachment.type.startsWith('image/') || /\.(png|jpe?g|webp|bmp|gif)$/i.test(attachedName);
    const formData = new FormData();
    formData.append('file', selectedAttachment);

    if (isImage) {
      window.showToast?.(`Đang tải lên hình ảnh thiết kế: ${attachedName}...`, 'info');
      try {
        const upRes = await fetch('/api/chat/upload-image', {
          method: 'POST',
          body: formData
        });
        if (upRes.ok) {
          const upData = await upRes.json();
          outgoingText = outgoingText
            ? `[Đính kèm hình ảnh: ${upData.file_path}]\n${outgoingText}`
            : `[Đính kèm hình ảnh: ${upData.file_path}]\nHãy phân tích hình ảnh này và tìm kiếm file thiết kế tương ứng.`;
        } else {
          window.showToast?.('Lỗi khi tải ảnh lên máy chủ', 'error');
        }
      } catch (e) {
        console.error('Image upload failed:', e);
      }
    } else {
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

  currentChatAbortController = new AbortController();
  const streamUi = createStreamingAssistantBubble();

  let accumulatedMarkdown = '';
  let toolCallsList = [];

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: outgoingText, author: 'Developer' }),
      signal: currentChatAbortController.signal
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      window.showToast?.(err.detail || 'Lỗi khi gửi tin nhắn', 'error');
      if (streamUi && streamUi.contentEl) {
        streamUi.contentEl.innerHTML = '<p>⚠️ Đã xảy ra lỗi khi kết nối với AI Agent. Vui lòng thử lại.</p>';
        streamUi.pill.classList.remove('active');
        streamUi.pill.classList.add('completed');
        streamUi.statusText.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-danger"></i> Đã xảy ra lỗi';
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Giữ lại phần chưa hoàn thành dòng

      let currentEvent = 'message';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.slice(6).trim();
        } else if (trimmed.startsWith('data:')) {
          const rawData = trimmed.slice(5).trim();
          try {
            const data = JSON.parse(rawData);

            // 1. Cập nhật Status
            if (currentEvent === 'status') {
              if (streamUi && streamUi.statusText) {
                streamUi.statusText.innerHTML = escapeHtml(data.message);
              }
              if (streamUi && streamUi.drawer) {
                const item = document.createElement('div');
                item.className = 'thought-step-item active';
                item.innerHTML = `<i class="fa-solid fa-circle-check step-icon text-cyan"></i> <span>${escapeHtml(data.message)}</span>`;
                streamUi.drawer.appendChild(item);
                streamUi.drawer.scrollTop = streamUi.drawer.scrollHeight;
              }
            } 
            // 2. Cập nhật Tool Start
            else if (currentEvent === 'tool_start') {
              if (streamUi && streamUi.statusText) {
                streamUi.statusText.innerHTML = `⚡ Đang chạy công cụ: <strong>${escapeHtml(data.name)}</strong>...`;
              }
              if (streamUi && streamUi.drawer) {
                const item = document.createElement('div');
                item.className = 'thought-step-item active';
                item.innerHTML = `<i class="fa-solid fa-gear fa-spin step-icon text-purple"></i> <span>Gọi công cụ <code>${escapeHtml(data.name)}</code>: <small>${escapeHtml(JSON.stringify(data.args))}</small></span>`;
                streamUi.drawer.appendChild(item);
                streamUi.drawer.scrollTop = streamUi.drawer.scrollHeight;
              }
            } 
            // 3. Cập nhật Tool End
            else if (currentEvent === 'tool_end') {
              toolCallsList.push({ name: data.name, result: data.result });
              if (streamUi && streamUi.statusText) {
                streamUi.statusText.innerHTML = `✅ Hoàn thành công cụ: <strong>${escapeHtml(data.name)}</strong>`;
              }
              if (streamUi && streamUi.drawer) {
                const item = document.createElement('div');
                item.className = 'thought-step-item success';
                item.innerHTML = `<i class="fa-solid fa-check step-icon text-green"></i> <span>Hoàn tất <code>${escapeHtml(data.name)}</code></span>`;
                streamUi.drawer.appendChild(item);
                streamUi.drawer.scrollTop = streamUi.drawer.scrollHeight;
              }
            } 
            // 4. Stream từng Token (Nội dung chính hiển thị ở dưới, drawer suy nghĩ ẩn giấu)
            else if (currentEvent === 'token') {
              accumulatedMarkdown += data.token;
              if (streamUi && streamUi.contentEl) {
                streamUi.contentEl.innerHTML = marked.parse(accumulatedMarkdown);
                if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
              }
              // Chuyển status pill sang completed (giấu nhẹm vào accordion)
              if (streamUi && streamUi.pill && streamUi.pill.classList.contains('active')) {
                streamUi.pill.classList.remove('active');
                streamUi.pill.classList.add('completed');
                const tcCount = toolCallsList.length;
                const tcText = tcCount > 0 ? ` (${tcCount} công cụ)` : '';
                streamUi.statusText.innerHTML = `<i class="fa-solid fa-brain"></i> Quá trình suy nghĩ & thực thi${tcText} (Bấm xem chi tiết)`;
              }
            } 
            // 5. Done event
            else if (currentEvent === 'done') {
              if (data.content && !accumulatedMarkdown) {
                accumulatedMarkdown = data.content;
              }
              if (streamUi && streamUi.contentEl) {
                streamUi.contentEl.innerHTML = marked.parse(accumulatedMarkdown);
              }
              if (streamUi && streamUi.pill) {
                streamUi.pill.classList.remove('active');
                streamUi.pill.classList.add('completed');
                const tcCount = (data.tool_calls || toolCallsList).length;
                const tcText = tcCount > 0 ? ` • Đã dùng ${tcCount} công cụ` : '';
                const latStr = data.metrics?.latency_ms ? ` • ${(data.metrics.latency_ms/1000).toFixed(1)}s` : '';
                streamUi.statusText.innerHTML = `<i class="fa-solid fa-check text-green"></i> Đã hoàn tất${latStr}${tcText} (Bấm xem chi tiết)`;
              }
              // Telemetry badges
              if (streamUi && streamUi.telemetryEl && data.metrics) {
                const m = data.metrics;
                const latSec = (m.latency_ms ? (m.latency_ms / 1000).toFixed(2) : '0.00') + 's';
                const tokCount = (m.total_tokens || 0).toLocaleString();
                const costUsd = m.cost_usd ? `$${m.cost_usd.toFixed(5)}` : '$0.00';
                const modelLabel = m.model || 'Agent';
                streamUi.telemetryEl.style.display = 'flex';
                streamUi.telemetryEl.innerHTML = `
                  <span class="telemetry-pill lat"><i class="fa-solid fa-bolt"></i> ${latSec}</span>
                  <span class="telemetry-pill tok"><i class="fa-solid fa-coins"></i> ${tokCount} tok</span>
                  <span class="telemetry-pill cost"><i class="fa-solid fa-dollar-sign"></i> ${costUsd}</span>
                  <span class="telemetry-pill model"><i class="fa-solid fa-microchip"></i> ${modelLabel}</span>
                `;
              }
              // Cập nhật ngầm Bảng Tasks và Notes
              if (window.loadTasks) window.loadTasks();
              if (window.loadDailyNotes) window.loadDailyNotes();
              if (window.updateStatsAndProgress) window.updateStatsAndProgress();
            }
          } catch (e) {
            console.error('Error parsing SSE event data:', e);
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Chat fetch aborted by user.');
      return;
    }
    console.error(err);
    window.showToast?.('Lỗi mạng khi kết nối server streaming', 'error');
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

    // Support Clipboard Paste (Ctrl+V) for screenshots directly in chat
    if (chatInput) {
      chatInput.addEventListener('paste', (e) => {
        const items = (e.clipboardData || window.clipboardData)?.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.indexOf('image') !== -1) {
            const blob = items[i].getAsFile();
            if (blob) {
              const fileName = `screenshot_${Date.now()}.png`;
              selectedAttachment = new File([blob], fileName, { type: blob.type });
              if (previewName) previewName.textContent = fileName;
              if (previewIcon) previewIcon.className = 'fa-solid fa-file-image text-purple';
              previewBox.style.display = 'block';
              window.showToast?.('Đã nhận ảnh chụp màn hình từ Clipboard! Hãy nhập đường dẫn cần quét (ví dụ: \\\\172.16.44.103\\design$).', 'info');
              break;
            }
          }
        }
      });
    }
  }
}
window.initChat = initChat;

