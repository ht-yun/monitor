// ============================================================
// Configuration Management
// ============================================================
var config = {
    aiEndpoint: localStorage.getItem('monitor_aiEndpoint') || '',
    aiKey: localStorage.getItem('monitor_aiKey') || '',
    aiModel: localStorage.getItem('monitor_aiModel') || ''
};

var serverConfig = { hasServerKey: false, defaultModel: 'gpt-4o', defaultEndpoint: 'https://api.openai.com/v1' };

// ============================================================
// State
// ============================================================
var myChart = null;
var conversationHistory = []; // Multi-turn conversation context
var chartHistory = JSON.parse(localStorage.getItem('monitor_chartHistory') || '[]');
var lastUserMessage = "";

// ============================================================
// Initialization
// ============================================================
(async function init() {
    updateClock();
    setInterval(updateClock, 1000);
    renderHistoryList();

    // Check server config
    try {
        const res = await fetch('/api/config');
        if (res.ok) {
            serverConfig = await res.json();
        }
    } catch (e) {
        console.log('Could not reach server config endpoint.');
    }

    updateStatusBadge();
    syncModelDropdown();
    updateModelDisplay();
    checkOnboarding();
})();

// Handle window resize
window.addEventListener('resize', () => {
    if (myChart) myChart.resize();
});

// Clear error state on settings input
document.querySelectorAll('.input-group input').forEach(input => {
    input.addEventListener('input', function () {
        this.classList.remove('error');
    });
});

// ============================================================
// Clock
// ============================================================
function updateClock() {
    const now = new Date();
    document.getElementById('time').innerText = now.toLocaleTimeString();
}

// ============================================================
// Status Badge
// ============================================================
function updateStatusBadge() {
    const badge = document.getElementById('data-status');
    const hasKey = config.aiKey || serverConfig.hasServerKey;
    if (hasKey) {
        badge.innerText = "状态: AI 已连接";
        badge.className = "status-badge live";
    } else {
        badge.innerText = "状态: AI 未配置";
        badge.className = "status-badge demo";
    }
}

// ============================================================
// Onboarding (pulse on settings if not configured)
// ============================================================
function checkOnboarding() {
    const settingsBtn = document.getElementById('settings-btn');
    if (!config.aiKey && !serverConfig.hasServerKey) {
        settingsBtn.classList.add('has-guide');
    } else {
        settingsBtn.classList.remove('has-guide');
    }
}

// ============================================================
// Settings Modal
// ============================================================
function toggleSettings() {
    const modal = document.getElementById('settings-modal');
    modal.classList.toggle('active');

    if (modal.classList.contains('active')) {
        document.getElementById('ai-endpoint').value = config.aiEndpoint;
        document.getElementById('ai-key').value = config.aiKey;
        document.getElementById('ai-model').value = config.aiModel;
        document.querySelectorAll('.input-group input').forEach(el => el.classList.remove('error'));

        // Show server key status
        const banner = document.getElementById('server-key-status');
        if (serverConfig.hasServerKey) {
            banner.style.display = 'block';
        } else {
            banner.style.display = 'none';
        }
    }
}

async function saveSettings() {
    const endpointInput = document.getElementById('ai-endpoint');
    const keyInput = document.getElementById('ai-key');
    const modelInput = document.getElementById('ai-model');
    const saveBtn = document.querySelector('.save-btn');

    [endpointInput, keyInput, modelInput].forEach(el => el.classList.remove('error'));

    let newEndpoint = endpointInput.value.trim();
    const newKey = keyInput.value.trim();
    let newModel = modelInput.value.trim();

    const originalBtnText = saveBtn.innerText;
    saveBtn.innerText = '正在验证配置...';
    saveBtn.style.pointerEvents = 'none';
    saveBtn.style.opacity = '0.7';

    // If user provides a key, validate it
    if (newKey) {
        const testEndpoint = newEndpoint || serverConfig.defaultEndpoint;
        const testModel = newModel || serverConfig.defaultModel;
        try {
            const res = await fetch(`${testEndpoint}/chat/completions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${newKey}` },
                body: JSON.stringify({ model: testModel, messages: [{ role: 'user', content: 'test' }], max_tokens: 1 })
            });

            if (res.status === 401 || res.status === 403) {
                keyInput.classList.add('error');
                saveBtn.innerText = originalBtnText;
                saveBtn.style.pointerEvents = 'auto';
                saveBtn.style.opacity = '1';
                return;
            } else if (res.status === 404) {
                endpointInput.classList.add('error');
                modelInput.classList.add('error');
                saveBtn.innerText = originalBtnText;
                saveBtn.style.pointerEvents = 'auto';
                saveBtn.style.opacity = '1';
                return;
            }
        } catch (e) {
            endpointInput.classList.add('error');
            saveBtn.innerText = originalBtnText;
            saveBtn.style.pointerEvents = 'auto';
            saveBtn.style.opacity = '1';
            return;
        }
    }

    saveBtn.innerText = originalBtnText;
    saveBtn.style.pointerEvents = 'auto';
    saveBtn.style.opacity = '1';

    config.aiEndpoint = newEndpoint;
    config.aiKey = newKey;
    config.aiModel = newModel;

    localStorage.setItem('monitor_aiEndpoint', config.aiEndpoint);
    localStorage.setItem('monitor_aiKey', config.aiKey);
    localStorage.setItem('monitor_aiModel', config.aiModel);

    syncModelDropdown();
    updateStatusBadge();
    updateModelDisplay();
    toggleSettings();
    checkOnboarding();
}

// ============================================================
// Model Display & Sync Logic
// ============================================================
function syncModelDropdown() {
    const modelSelect = document.getElementById('model-select');
    if (!modelSelect) return;

    const activeModel = config.aiModel || serverConfig.defaultModel;
    
    // Clear all existing options
    modelSelect.innerHTML = '';
    
    // Add only the active model as the single option
    const newOption = new Option(activeModel, activeModel);
    modelSelect.add(newOption);
    modelSelect.value = activeModel;
}

function updateModelDisplay() {
    const display = document.getElementById('active-model-display');
    const modelSelect = document.getElementById('model-select');
    if (!display) return;
    
    // When user changes the dropdown, we update config.aiModel to match
    if (modelSelect) {
        config.aiModel = modelSelect.value;
        localStorage.setItem('monitor_aiModel', config.aiModel);
    }
    
    const activeModel = config.aiModel || serverConfig.defaultModel;
    display.innerText = `(${activeModel})`;
}

// Add event listener for model change
document.getElementById('model-select').addEventListener('change', updateModelDisplay);

// ============================================================
// AI Chat — Core Logic
// ============================================================
async function sendMessage(overrideText = null) {
    const input = document.getElementById('chat-input');
    let text;

    if (overrideText) {
        text = overrideText;
    } else {
        text = input.value.trim();
    }

    if (!text) return;
    lastUserMessage = text;

    // Add user message to UI and conversation history
    appendMessage('user', text);
    conversationHistory.push({ role: 'user', content: text });
    input.value = '';

    // Check if we have any API key (server or client)
    const hasKey = config.aiKey || serverConfig.hasServerKey;
    if (!hasKey) {
        const noKeyMsg = "⚠️ 请先在设置中配置 AI API Key，或在服务器 .env 中配置 OPENAI_API_KEY。";
        appendMessage('assistant', noKeyMsg);
        return;
    }

    // Resolve model from dropdown
    const modelSelect = document.getElementById('model-select');
    const activeModel = modelSelect ? modelSelect.value : (config.aiModel || serverConfig.defaultModel);

    // Add loading indicator
    const loadingDiv = appendMessage('assistant', '正在思考并分析数据...', true);

    // Limit conversation history to last 20 messages to avoid token overflow
    const messagesToSend = conversationHistory.slice(-20);

    try {
        // Build request body
        const body = {
            messages: messagesToSend,
            model: activeModel
        };
        // Only send client-side key/endpoint if configured (otherwise server uses .env)
        if (config.aiKey) body.apiKey = config.aiKey;
        if (config.aiEndpoint) body.endpoint = config.aiEndpoint;

        // Use streaming endpoint
        const apiPath = '/api/chat/stream';
        const response = await fetch(apiPath, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errResult = await response.json().catch(() => ({}));
            throw new Error(errResult.error || `HTTP ${response.status}`);
        }

        // Remove loading indicator
        if (loadingDiv && loadingDiv.parentNode) loadingDiv.remove();

        // Create a streaming message bubble
        const streamDiv = appendMessage('assistant', '', true);
        let fullContent = '';

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.type === 'delta') {
                            fullContent += parsed.text;
                            renderMessageContent(streamDiv, fullContent);
                        } else if (parsed.type === 'status') {
                            // Update loading message with status
                            renderMessageContent(streamDiv, `⏳ ${parsed.text}`);
                        } else if (parsed.type === 'error') {
                            throw new Error(parsed.text);
                        }
                    } catch (parseErr) {
                        if (parseErr.message && !parseErr.message.includes('Unexpected')) {
                            throw parseErr;
                        }
                    }
                }
            }
        }

        // Add AI response to conversation history
        conversationHistory.push({ role: 'assistant', content: fullContent });

        // Process for chart/card actions
        processAIResponse(fullContent, streamDiv);

    } catch (error) {
        if (loadingDiv && loadingDiv.parentNode) loadingDiv.remove();
        appendMessage('assistant', formatErrorMessage(error));
    }
}

// ============================================================
// Message Rendering — with Markdown support
// ============================================================
function appendMessage(role, text, isStreaming = false) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'msg-content';

    if (role === 'assistant' && text) {
        renderMessageContent(div, text);
    } else {
        contentDiv.textContent = text;
        div.appendChild(contentDiv);
    }

    if (isStreaming && role === 'assistant') {
        div.classList.add('streaming');
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function renderMessageContent(msgDiv, text) {
    let contentDiv = msgDiv.querySelector('.msg-content');
    if (!contentDiv) {
        contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';
        msgDiv.innerHTML = '';
        msgDiv.appendChild(contentDiv);
    }

    // Render Markdown for assistant messages
    if (msgDiv.classList.contains('assistant') && typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        try {
            const html = marked.parse(text, { breaks: true });
            contentDiv.innerHTML = DOMPurify.sanitize(html);
        } catch (e) {
            contentDiv.textContent = text;
        }
    } else {
        contentDiv.textContent = text;
    }

    // Auto-scroll
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

// ============================================================
// JSON Extraction — Robust bracket-matching algorithm
// ============================================================
function extractJSON(text) {
    // Find the first top-level { ... } using bracket counting
    let depth = 0;
    let start = -1;

    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (ch === '{') {
            if (depth === 0) start = i;
            depth++;
        } else if (ch === '}') {
            depth--;
            if (depth === 0 && start !== -1) {
                const candidate = text.substring(start, i + 1);
                try {
                    return JSON.parse(candidate);
                } catch (e) {
                    // Continue searching for next valid JSON
                    start = -1;
                }
            }
        }
    }
    return null;
}

// ============================================================
// Process AI Response — chart, cards, text
// ============================================================
function processAIResponse(content, existingDiv) {
    if (!content) return;
    if (typeof content !== 'string') content = JSON.stringify(content);

    // Clean markdown JSON fences
    let rawText = content.replace(/```json\s*/g, '').replace(/```\s*/g, '');

    // Extract JSON action using robust method
    const actionObj = extractJSON(rawText);

    if (actionObj) {
        if (actionObj.action === 'render_chart' || actionObj.action === 'create_chart') {
            if (actionObj.chartOption || actionObj.options) {
                renderDynamicChart(actionObj.chartOption || actionObj.options);

                // Save to history with full data
                if (lastUserMessage) {
                    saveToHistory(lastUserMessage, actionObj.chartOption || actionObj.options, actionObj.cards || null);
                    lastUserMessage = "";
                }
            }
        } else if ((actionObj.action === 'update' || actionObj.action === 'updateChart') && myChart) {
            if (Array.isArray(actionObj.chartData || actionObj.data)) {
                myChart.setOption({ series: [{ data: actionObj.chartData || actionObj.data }] });
            }
        }

        if (actionObj.cards) {
            updateCards(actionObj.cards);
        }
    }
}

// ============================================================
// Chart Rendering
// ============================================================
function renderDynamicChart(option) {
    const area = document.getElementById('dynamic-chart-area');
    area.innerHTML = '<div id="dynamic-chart-container"></div>';
    const chartDom = document.getElementById('dynamic-chart-container');

    if (myChart) myChart.dispose();

    myChart = echarts.init(chartDom, 'dark');

    if (option.backgroundColor === undefined) {
        option.backgroundColor = 'transparent';
    }

    myChart.setOption(option);
}

// ============================================================
// Card Updates
// ============================================================
function updateCards(cards) {
    if (cards.sourceName) {
        document.getElementById('card-source-name').innerText = cards.sourceName;
    }
    const sourceLink = document.getElementById('card-source-link');
    if (cards.sourceUrl) {
        sourceLink.href = cards.sourceUrl;
        sourceLink.style.display = 'inline-block';
    } else {
        sourceLink.style.display = 'none';
    }
    if (cards.summary) {
        document.getElementById('card-summary').innerText = cards.summary;
    }
    if (cards.analysis) {
        document.getElementById('card-analysis').innerText = cards.analysis;
    }
}

// ============================================================
// Error Message Formatting
// ============================================================
function formatErrorMessage(error) {
    const msg = error.message || String(error);

    if (msg.includes('401') || msg.includes('Unauthorized') || msg.includes('invalid_api_key')) {
        return '❌ API Key 无效或已过期，请在设置中检查并重新配置。';
    }
    if (msg.includes('403') || msg.includes('Forbidden')) {
        return '❌ API 访问被拒绝，请检查 Key 权限。';
    }
    if (msg.includes('404') || msg.includes('Not Found')) {
        return '❌ API 端点或模型不存在，请检查设置中的 Endpoint 和模型名称。';
    }
    if (msg.includes('429') || msg.includes('rate limit') || msg.includes('请求过于频繁')) {
        return '⏳ 请求过于频繁，请稍后再试。';
    }
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('ERR_CONNECTION')) {
        return '🔌 网络连接失败。请检查：\n1. 服务器是否已启动 (npm start)\n2. 网络连接是否正常';
    }
    if (msg.includes('timeout') || msg.includes('ETIMEDOUT')) {
        return '⏱️ 请求超时，服务器响应过慢，请稍后重试。';
    }

    return `❌ 出错: ${msg}`;
}

// ============================================================
// Chat UI Controls
// ============================================================
function handleKeyPress(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
}

function toggleChat() {
    const container = document.querySelector('.chat-container');
    const icon = document.getElementById('chat-toggle-icon');
    container.classList.toggle('collapsed');

    if (container.classList.contains('collapsed')) {
        icon.innerText = '□';
    } else {
        icon.innerText = '_';
        const msgContainer = document.getElementById('chat-messages');
        msgContainer.scrollTop = msgContainer.scrollHeight;
    }
}

function newConversation() {
    conversationHistory = [];
    const container = document.getElementById('chat-messages');
    container.innerHTML = '<div class="message assistant"><div class="msg-content">🔄 新对话已开始。有什么可以帮你的？</div></div>';
}

// ============================================================
// History — Enhanced with chart + cards data persistence
// ============================================================
function saveToHistory(prompt, chartOption, cards) {
    const id = Date.now().toString();
    const shortTitle = prompt.length > 20 ? prompt.substring(0, 20) + "..." : prompt;

    // Deduplicate
    if (chartHistory.length > 0 && chartHistory[0].prompt === prompt) return;

    chartHistory.unshift({
        id,
        title: shortTitle,
        prompt,
        chartOption: chartOption || null,
        cards: cards || null,
        timestamp: new Date().toLocaleString()
    });

    // Keep last 50
    if (chartHistory.length > 50) chartHistory = chartHistory.slice(0, 50);

    localStorage.setItem('monitor_chartHistory', JSON.stringify(chartHistory));
    renderHistoryList();
}

function renderHistoryList() {
    const listContainer = document.getElementById('history-list');
    if (!listContainer) return;

    listContainer.innerHTML = '';

    if (chartHistory.length === 0) {
        listContainer.innerHTML = '<div class="history-empty">暂无历史记录</div>';
        return;
    }

    chartHistory.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.onclick = () => loadHistoryItem(item, div);

        div.innerHTML = `
            <div class="history-title" title="${item.prompt}">${item.title}</div>
            <div class="history-date">${item.timestamp}</div>
        `;
        listContainer.appendChild(div);
    });
}

function loadHistoryItem(item, elementNode) {
    // Visual active state
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    if (elementNode) elementNode.classList.add('active');

    // If we have saved chart data, restore directly without re-querying AI
    if (item.chartOption) {
        renderDynamicChart(item.chartOption);
        if (item.cards) updateCards(item.cards);
        appendMessage('assistant', `📊 已从历史记录恢复: "${item.prompt}"`);
    } else {
        // Fallback: re-query AI
        const container = document.querySelector('.chat-container');
        if (container.classList.contains('collapsed')) toggleChat();
        appendMessage('assistant', `🔄 正在重新查询: "${item.prompt}"...`);
        sendMessage(item.prompt);
    }
}

function clearHistory() {
    if (confirm("确定要清空所有可视化数据纪要吗？")) {
        chartHistory = [];
        localStorage.removeItem('monitor_chartHistory');
        renderHistoryList();
    }
}
