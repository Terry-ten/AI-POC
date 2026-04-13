/**
 * Nuclei 漏洞扫描器前端逻辑 v2.0
 * 支持文件夹分类、分页加载、多选扫描
 */

const API_BASE = '/api';

// 状态
let state = {
    folders: [],
    currentFolder: null,
    templates: [],
    selectedTemplates: new Set(),
    currentPage: 1,
    totalPages: 1,
    totalTemplates: 0,
    pageSize: 100,
    keyword: '',
    isScanning: false,
    nucleiAvailable: false
};

// DOM 元素缓存
const $ = (id) => document.getElementById(id);

const dom = {
    nucleiStatus: $('nuclei-status'),
    targetUrl: $('target-url'),
    scanBtn: $('scan-btn'),
    createTaskBtn: $('create-task-btn'),
    foldersList: $('folders-list'),
    refreshFoldersBtn: $('refresh-folders-btn'),
    templatesList: $('templates-list'),
    templatesCount: $('templates-count'),
    templateSearch: $('template-search'),
    selectAllBtn: $('select-all-btn'),
    deselectAllBtn: $('deselect-all-btn'),
    selectedCount: $('selected-count'),
    prevPage: $('prev-page'),
    nextPage: $('next-page'),
    currentPage: $('current-page'),
    totalPages: $('total-pages'),
    resultsEmpty: $('results-empty'),
    resultsList: $('results-list'),
    findingsCount: $('findings-count'),
    scanStatus: $('scan-status'),
    statusMessage: $('status-message'),
    scanSummary: $('scan-summary'),
    summaryTarget: $('summary-target'),
    summaryFindings: $('summary-findings'),
    summaryStatus: $('summary-status'),
    clearResultsBtn: $('clear-results-btn'),
    templateModal: $('template-modal'),
    modalTitle: $('modal-title'),
    modalCode: $('modal-code'),
    toast: $('toast'),
    toastMessage: $('toast-message')
};

// 初始化
document.addEventListener('DOMContentLoaded', init);

async function init() {
    bindEvents();
    await checkNucleiStatus();
    await loadFolders();
}

// 绑定事件
function bindEvents() {
    // 刷新文件夹
    dom.refreshFoldersBtn.addEventListener('click', async () => {
        await fetch(`${API_BASE}/nuclei/cache/clear`, { method: 'POST' });
        await loadFolders();
    });

    // 搜索（防抖）
    let searchTimeout;
    dom.templateSearch.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.keyword = dom.templateSearch.value.trim();
            state.currentPage = 1;
            loadTemplates();
        }, 300);
    });

    // 全选/取消
    dom.selectAllBtn.addEventListener('click', selectAllCurrentPage);
    dom.deselectAllBtn.addEventListener('click', deselectAll);

    // 分页
    dom.prevPage.addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            loadTemplates();
        }
    });

    dom.nextPage.addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            loadTemplates();
        }
    });

    // 扫描
    dom.scanBtn.addEventListener('click', startScan);
    dom.createTaskBtn.addEventListener('click', createScanTask);

    // 清空结果
    dom.clearResultsBtn.addEventListener('click', clearResults);

    // 模态框
    dom.templateModal.addEventListener('click', (e) => {
        if (e.target === dom.templateModal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}

// 检查 Nuclei 状态
async function checkNucleiStatus() {
    try {
        const res = await fetch(`${API_BASE}/nuclei/status`);
        const data = await res.json();

        state.nucleiAvailable = data.available;

        if (data.available) {
            dom.nucleiStatus.className = 'nuclei-status available';
            dom.nucleiStatus.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <span>Nuclei 就绪 | ${data.templates_count} 模板</span>
            `;
            dom.scanBtn.disabled = false;
            dom.createTaskBtn.disabled = false;
        } else {
            dom.nucleiStatus.className = 'nuclei-status unavailable';
            dom.nucleiStatus.innerHTML = `
                <i class="fas fa-times-circle"></i>
                <span>${data.error || 'Nuclei 不可用'}</span>
            `;
            dom.scanBtn.disabled = true;
            dom.createTaskBtn.disabled = true;
        }
    } catch (e) {
        dom.nucleiStatus.className = 'nuclei-status unavailable';
        dom.nucleiStatus.innerHTML = `
            <i class="fas fa-times-circle"></i>
            <span>检查失败</span>
        `;
        dom.scanBtn.disabled = true;
        dom.createTaskBtn.disabled = true;
    }
}

// 加载文件夹列表
async function loadFolders() {
    dom.foldersList.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div>';

    try {
        const res = await fetch(`${API_BASE}/nuclei/folders`);
        const data = await res.json();

        if (data.success && data.folders.length > 0) {
            state.folders = data.folders;
            renderFolders();

            // 默认选中第一个
            if (state.folders.length > 0) {
                selectFolder(state.folders[0].path);
            }
        } else {
            dom.foldersList.innerHTML = '<div class="empty-folder"><i class="fas fa-folder-open"></i><p>暂无模板</p></div>';
        }
    } catch (e) {
        dom.foldersList.innerHTML = '<div class="empty-folder">加载失败</div>';
    }
}

// 渲染文件夹列表
function renderFolders() {
    dom.foldersList.innerHTML = state.folders.map(folder => `
        <div class="folder-item ${state.currentFolder === folder.path ? 'active' : ''}"
             data-path="${folder.path}" onclick="selectFolder('${folder.path}')">
            <span class="folder-name">
                <i class="fas fa-folder"></i>
                ${escapeHtml(folder.name)}
            </span>
            <span class="folder-count">${folder.count}</span>
        </div>
    `).join('');
}

// 选择文件夹
function selectFolder(path) {
    state.currentFolder = path;
    state.currentPage = 1;
    state.keyword = '';
    dom.templateSearch.value = '';

    // 更新 UI
    document.querySelectorAll('.folder-item').forEach(el => {
        el.classList.toggle('active', el.dataset.path === path);
    });

    loadTemplates();
}

// 加载模板列表
async function loadTemplates() {
    dom.templatesList.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div>';

    try {
        const params = new URLSearchParams({
            folder: state.currentFolder || '',
            page: state.currentPage,
            page_size: state.pageSize,
            keyword: state.keyword
        });

        const res = await fetch(`${API_BASE}/nuclei/templates?${params}`);
        const data = await res.json();

        if (data.success) {
            state.templates = data.templates;
            state.totalTemplates = data.total;
            state.totalPages = data.total_pages || 1;

            renderTemplates();
            updatePagination();
        } else {
            dom.templatesList.innerHTML = '<div class="empty-folder">加载失败</div>';
        }
    } catch (e) {
        dom.templatesList.innerHTML = '<div class="empty-folder">加载失败</div>';
    }
}

// 渲染模板列表
function renderTemplates() {
    if (state.templates.length === 0) {
        dom.templatesList.innerHTML = '<div class="empty-folder"><i class="fas fa-file"></i><p>无模板</p></div>';
        dom.templatesCount.textContent = '0';
        return;
    }

    dom.templatesCount.textContent = state.totalTemplates;

    dom.templatesList.innerHTML = state.templates.map(t => `
        <div class="template-row ${state.selectedTemplates.has(t.relative_path) ? 'selected' : ''}"
             data-path="${escapeHtml(t.relative_path)}">
            <input type="checkbox" ${state.selectedTemplates.has(t.relative_path) ? 'checked' : ''}
                   onclick="event.stopPropagation(); toggleTemplate('${escapeHtml(t.relative_path)}')">
            <div class="template-info" onclick="toggleTemplate('${escapeHtml(t.relative_path)}')">
                <span class="template-name" title="${escapeHtml(t.name)}">${escapeHtml(t.name)}</span>
                <span class="template-id">${escapeHtml(t.id)}</span>
            </div>
            <span class="severity-badge severity-${t.severity}">${t.severity}</span>
            <div class="template-actions">
                <button class="btn-icon btn-run" onclick="event.stopPropagation(); runSingleTemplate('${escapeHtml(t.relative_path)}')" title="单独运行">
                    <i class="fas fa-play"></i>
                </button>
                <button class="btn-icon" onclick="event.stopPropagation(); viewTemplate('${escapeHtml(t.relative_path)}')" title="查看内容">
                    <i class="fas fa-eye"></i>
                </button>
            </div>
        </div>
    `).join('');

    updateSelectedCount();
}

// 切换模板选择
function toggleTemplate(path) {
    if (state.selectedTemplates.has(path)) {
        state.selectedTemplates.delete(path);
    } else {
        state.selectedTemplates.add(path);
    }

    // 更新行样式
    const row = document.querySelector(`.template-row[data-path="${CSS.escape(path)}"]`);
    if (row) {
        row.classList.toggle('selected', state.selectedTemplates.has(path));
        row.querySelector('input[type="checkbox"]').checked = state.selectedTemplates.has(path);
    }

    updateSelectedCount();
}

// 全选当前页
function selectAllCurrentPage() {
    state.templates.forEach(t => {
        state.selectedTemplates.add(t.relative_path);
    });
    renderTemplates();
}

// 取消所有选择
function deselectAll() {
    state.selectedTemplates.clear();
    renderTemplates();
}

// 更新已选计数
function updateSelectedCount() {
    dom.selectedCount.textContent = state.selectedTemplates.size;
}

// 更新分页
function updatePagination() {
    dom.currentPage.textContent = state.currentPage;
    dom.totalPages.textContent = state.totalPages;
    dom.prevPage.disabled = state.currentPage <= 1;
    dom.nextPage.disabled = state.currentPage >= state.totalPages;
}

// 查看模板内容
async function viewTemplate(path) {
    try {
        const res = await fetch(`${API_BASE}/nuclei/template/content?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.success) {
            dom.modalTitle.textContent = path;
            dom.modalCode.textContent = data.content;
            dom.templateModal.classList.add('show');
        } else {
            showToast('加载失败', 'error');
        }
    } catch (e) {
        showToast('加载失败', 'error');
    }
}

// 关闭模态框
function closeModal() {
    dom.templateModal.classList.remove('show');
}

// 开始扫描
async function startScan() {
    const targetUrl = getValidatedTargetUrl();
    if (!targetUrl || !validateSelectedTemplates()) return;

    // 开始扫描
    state.isScanning = true;
    updateScanUI(true);

    const requestBody = {
        target_url: targetUrl,
        template_paths: Array.from(state.selectedTemplates),
        timeout: 300
    };

    try {
        const response = await fetch(`${API_BASE}/nuclei/scan/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let findings = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const event = JSON.parse(data);
                        handleScanEvent(event, findings);
                    } catch (e) {}
                }
            }
        }

        finishScan(targetUrl, findings);

    } catch (e) {
        showToast(`扫描失败: ${e.message}`, 'error');
    } finally {
        state.isScanning = false;
        updateScanUI(false);
    }
}

function getValidatedTargetUrl() {
    const targetUrl = dom.targetUrl.value.trim();

    if (!targetUrl) {
        showToast('请输入目标 URL', 'warning');
        dom.targetUrl.focus();
        return null;
    }

    try {
        new URL(targetUrl);
    } catch {
        showToast('请输入有效的 URL', 'warning');
        return null;
    }

    return targetUrl;
}

function validateSelectedTemplates() {
    if (state.selectedTemplates.size === 0) {
        showToast('请至少选择一个模板', 'warning');
        return false;
    }
    return true;
}

async function createScanTask() {
    const targetUrl = getValidatedTargetUrl();
    if (!targetUrl || !validateSelectedTemplates()) return;

    const originalHtml = dom.createTaskBtn.innerHTML;
    dom.createTaskBtn.disabled = true;
    dom.createTaskBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>创建中...</span>';

    try {
        const response = await fetch(`${API_BASE}/nuclei/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_urls: [targetUrl],
                template_paths: Array.from(state.selectedTemplates),
                concurrency: 3
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.detail || data.message || '创建任务失败');
        }

        sessionStorage.setItem('records_toast', `Nuclei 扫描任务 #${data.task.id} 已创建`);
        window.location.href = '/?tab=records';
    } catch (e) {
        showToast(`创建任务失败: ${e.message}`, 'error');
    } finally {
        dom.createTaskBtn.disabled = !state.nucleiAvailable || state.isScanning;
        dom.createTaskBtn.innerHTML = originalHtml;
    }
}

// 处理扫描事件
function handleScanEvent(event, findings) {
    switch (event.type) {
        case 'status':
            dom.statusMessage.textContent = event.message;
            break;

        case 'finding':
            findings.push(event.data);
            addResultItem(event.data);
            dom.findingsCount.textContent = findings.length;
            dom.findingsCount.style.display = 'inline-flex';
            break;

        case 'complete':
            dom.statusMessage.textContent = `扫描完成，发现 ${event.total_findings} 个漏洞`;
            break;

        case 'error':
            showToast(event.message, 'error');
            break;
    }
}

// 添加结果项
function addResultItem(finding) {
    dom.resultsEmpty.style.display = 'none';
    dom.resultsList.style.display = 'block';

    const html = `
        <div class="result-item severity-${finding.severity}">
            <div class="result-header">
                <span class="result-title">${escapeHtml(finding.template_name)}</span>
                <span class="severity-badge severity-${finding.severity}">${finding.severity}</span>
            </div>
            <div class="result-details">
                <div class="result-detail">
                    <span class="result-detail-label">模板:</span>
                    <span class="result-detail-value">${escapeHtml(finding.template_id)}</span>
                </div>
                ${finding.matched_at ? `
                <div class="result-detail">
                    <span class="result-detail-label">位置:</span>
                    <span class="result-detail-value">${escapeHtml(finding.matched_at)}</span>
                </div>` : ''}
                ${finding.host ? `
                <div class="result-detail">
                    <span class="result-detail-label">目标:</span>
                    <span class="result-detail-value">${escapeHtml(finding.host)}</span>
                </div>` : ''}
            </div>
        </div>
    `;

    dom.resultsList.insertAdjacentHTML('beforeend', html);
    dom.resultsList.scrollTop = dom.resultsList.scrollHeight;
}

// 完成扫描
function finishScan(targetUrl, findings) {
    dom.scanStatus.style.display = 'none';
    dom.scanSummary.style.display = 'block';

    dom.summaryTarget.textContent = targetUrl;
    dom.summaryFindings.textContent = findings.length;
    dom.summaryStatus.textContent = findings.length > 0 ? '存在风险' : '未发现漏洞';
    dom.summaryStatus.className = `value ${findings.length > 0 ? 'highlight' : ''}`;
}

// 更新扫描 UI
function updateScanUI(scanning) {
    dom.scanBtn.disabled = scanning;
    dom.createTaskBtn.disabled = scanning || !state.nucleiAvailable;

    if (scanning) {
        dom.scanBtn.innerHTML = '<i class="fas fa-stop"></i><span>扫描中...</span>';
        dom.scanBtn.classList.add('scanning');
        dom.resultsEmpty.style.display = 'none';
        dom.resultsList.style.display = 'block';
        dom.resultsList.innerHTML = '';
        dom.scanStatus.style.display = 'flex';
        dom.scanSummary.style.display = 'none';
        dom.findingsCount.textContent = '0';
        dom.findingsCount.style.display = 'none';
    } else {
        dom.scanBtn.innerHTML = '<i class="fas fa-play"></i><span>立即扫描</span>';
        dom.scanBtn.classList.remove('scanning');
        dom.scanStatus.style.display = 'none';
    }
}

// 清空结果
function clearResults() {
    dom.resultsList.innerHTML = '';
    dom.resultsList.style.display = 'none';
    dom.resultsEmpty.style.display = 'flex';
    dom.scanSummary.style.display = 'none';
    dom.findingsCount.style.display = 'none';
}

// HTML 转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 转义 JavaScript 字符串（用于 onclick 等属性）
function escapeJs(text) {
    if (!text) return '';
    return text
        .replace(/\\/g, '\\\\')  // 先转义反斜杠
        .replace(/'/g, "\\'")     // 转义单引号
        .replace(/"/g, '\\"');    // 转义双引号
}

// 显示 Toast
function showToast(message, type = 'success') {
    const toast = dom.toast;
    const icon = toast.querySelector('i');

    toast.className = `toast ${type}`;
    dom.toastMessage.textContent = message;

    icon.className = type === 'success' ? 'fas fa-check-circle' :
                     type === 'error' ? 'fas fa-times-circle' :
                     'fas fa-exclamation-circle';

    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// 全局函数
window.selectFolder = selectFolder;
window.toggleTemplate = toggleTemplate;
window.viewTemplate = viewTemplate;
window.closeModal = closeModal;
window.runSingleTemplate = runSingleTemplate;

// 单个模板运行
async function runSingleTemplate(path) {
    const targetUrl = dom.targetUrl.value.trim();

    if (!targetUrl) {
        showToast('请先输入目标 URL', 'warning');
        dom.targetUrl.focus();
        return;
    }

    try {
        new URL(targetUrl);
    } catch {
        showToast('请输入有效的 URL', 'warning');
        return;
    }

    // 检查是否是 headless 模板
    if (path.toLowerCase().includes('headless')) {
        showToast('Headless 模板需要浏览器支持，可能很慢', 'warning');
    }

    // 开始扫描
    state.isScanning = true;
    updateScanUI(true);

    const requestBody = {
        target_url: targetUrl,
        template_paths: [path],
        timeout: 120
    };

    try {
        const response = await fetch(`${API_BASE}/nuclei/scan/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let findings = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const event = JSON.parse(data);
                        handleScanEvent(event, findings);
                    } catch (e) {}
                }
            }
        }

        finishScan(targetUrl, findings);

    } catch (e) {
        showToast(`扫描失败: ${e.message}`, 'error');
    } finally {
        state.isScanning = false;
        updateScanUI(false);
    }
}
