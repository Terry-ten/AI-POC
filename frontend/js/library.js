// ========================================
// 全新POC库管理 JavaScript
// ========================================

// API配置 - 使用全局LIB_API_BASE或默认值
const LIB_API_BASE = window.LIB_API_BASE || 'http://127.0.0.1:8000';

// POC库状态管理
const LibraryState = {
    pocs: [],           // 所有POC数据
    currentFilter: 'all', // 当前筛选: all, direct, params, manual
    searchQuery: '',    // 搜索关键词
    vulnTypeFilter: '', // 漏洞类型筛选
    sortBy: 'newest',   // 排序方式
    batchMode: false,
    selectedPocIds: new Set(),
    batchTasks: [],
    batchTaskPoller: null,
    batchTaskStatusMap: new Map(),
    batchTasksInitialized: false,
    recordsFilters: {
        status: '',
        resultFilter: '',
        keyword: '',
        sortBy: 'created_at',
        sortOrder: 'desc'
    }
};

// ========================================
// 初始化POC库
// ========================================
function initLibrary() {
    loadLibraryData();
    loadAssetSourceConfig();
    if (!LibraryState._initialized) {
        setupLibraryEventListeners();
        LibraryState._initialized = true;
    }
    ensureBatchTaskPolling();
}

function initBatchRecords() {
    loadBatchTasks();
    ensureBatchTaskPolling();
    const recordsToast = sessionStorage.getItem('records_toast');
    if (recordsToast) {
        sessionStorage.removeItem('records_toast');
        showToast(recordsToast, 'success');
    }
}

// ========================================
// 加载POC数据
// ========================================
async function loadLibraryData() {
    const loadingEl = document.getElementById('lib-loading');
    const emptyEl = document.getElementById('lib-empty');
    const gridEl = document.getElementById('lib-poc-grid');

    // 显示加载状态
    loadingEl.style.display = 'flex';
    emptyEl.style.display = 'none';
    gridEl.style.display = 'none';

    try {
        // 构建查询参数
        const params = new URLSearchParams();
        params.append('limit', '100');

        // 调用API获取数据
        const response = await fetch(`${LIB_API_BASE}/api/pocs/search?${params}`);
        const data = await response.json();

        if (data.success && data.pocs) {
            LibraryState.pocs = data.pocs;

            // 更新统计信息
            updateLibraryStats();

            // 渲染POC列表
            renderPOCGrid();
        } else {
            LibraryState.pocs = [];
            showLibraryEmpty();
        }

    } catch (error) {
        console.error('加载POC库失败:', error);
        showToast('加载POC库失败', 'error');
        showLibraryEmpty();
    } finally {
        loadingEl.style.display = 'none';
    }
}

// ========================================
// 更新统计信息
// ========================================
function updateLibraryStats() {
    const pocs = LibraryState.pocs;

    // 统计总数
    const total = pocs.length;

    const direct = pocs.filter(p => getPocCategory(p) === 'direct').length;
    const params = pocs.filter(p => getPocCategory(p) === 'params').length;
    const manual = pocs.filter(p => p.verifiable === 0).length;

    // 更新统计卡片
    document.getElementById('stat-total-modern').textContent = total;
    document.getElementById('stat-direct-modern').textContent = direct;
    document.getElementById('stat-params-modern').textContent = params;
    document.getElementById('stat-manual-modern').textContent = manual;

    // 更新筛选标签计数
    document.getElementById('count-all').textContent = total;
    document.getElementById('count-direct').textContent = direct;
    document.getElementById('count-params').textContent = params;
    document.getElementById('count-manual').textContent = manual;

    // 更新漏洞类型筛选器选项
    updateVulnTypeFilter();
}

// ========================================
// 更新漏洞类型筛选器
// ========================================
function updateVulnTypeFilter() {
    const pocs = LibraryState.pocs;
    const vulnTypes = [...new Set(pocs.map(p => p.vuln_type))].sort();

    const filterEl = document.getElementById('lib-filter-type');
    const currentValue = filterEl.value;

    filterEl.innerHTML = '<option value="">所有漏洞类型</option>';

    vulnTypes.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type.toUpperCase();
        filterEl.appendChild(option);
    });

    // 恢复之前的选择
    if (currentValue) {
        filterEl.value = currentValue;
    }
}

// ========================================
// 渲染POC网格
// ========================================
function renderPOCGrid() {
    const gridEl = document.getElementById('lib-poc-grid');
    const emptyEl = document.getElementById('lib-empty');

    // 应用筛选和搜索
    let filteredPOCs = filterPOCs();

    // 应用排序
    filteredPOCs = sortPOCs(filteredPOCs);

    if (filteredPOCs.length === 0) {
        gridEl.style.display = 'none';
        emptyEl.style.display = 'flex';
        return;
    }

    gridEl.style.display = 'grid';
    emptyEl.style.display = 'none';
    gridEl.innerHTML = '';

    filteredPOCs.forEach(poc => {
        const cardEl = createPOCCard(poc);
        gridEl.appendChild(cardEl);
    });

    updateBatchSelectionUI();
}

// ========================================
// 筛选POC
// ========================================
function filterPOCs() {
    let filtered = [...LibraryState.pocs];

    // 按执行分类筛选
    if (LibraryState.currentFilter === 'direct') {
        filtered = filtered.filter(p => getPocCategory(p) === 'direct');
    } else if (LibraryState.currentFilter === 'params') {
        filtered = filtered.filter(p => getPocCategory(p) === 'params');
    } else if (LibraryState.currentFilter === 'manual') {
        filtered = filtered.filter(p => getPocCategory(p) === 'manual');
    }

    // 按搜索关键词筛选
    if (LibraryState.searchQuery) {
        const query = LibraryState.searchQuery.toLowerCase();
        filtered = filtered.filter(p =>
            (p.vuln_name && p.vuln_name.toLowerCase().includes(query)) ||
            (p.vuln_type && p.vuln_type.toLowerCase().includes(query)) ||
            (p.vuln_description && p.vuln_description.toLowerCase().includes(query))
        );
    }

    // 按漏洞类型筛选
    if (LibraryState.vulnTypeFilter) {
        filtered = filtered.filter(p => p.vuln_type === LibraryState.vulnTypeFilter);
    }

    return filtered;
}

// ========================================
// 排序POC
// ========================================
function sortPOCs(pocs) {
    const sorted = [...pocs];

    switch (LibraryState.sortBy) {
        case 'newest':
            sorted.sort((a, b) => new Date(b.create_time) - new Date(a.create_time));
            break;
        case 'oldest':
            sorted.sort((a, b) => new Date(a.create_time) - new Date(b.create_time));
            break;
        case 'name':
            sorted.sort((a, b) => (a.vuln_name || '').localeCompare(b.vuln_name || ''));
            break;
    }

    return sorted;
}

// ========================================
// 创建POC卡片
// ========================================
function createPOCCard(poc) {
    const card = document.createElement('div');
    card.className = 'poc-list-item';

    const isVerifiable = poc.verifiable !== 0;
    const needsRuntimeParams = isVerifiable && poc.execution_mode === 'url_with_params' && Array.isArray(poc.input_schema) && poc.input_schema.length > 0;
    const batchEligible = isBatchEligiblePoc(poc);
    const category = getPocCategory(poc);
    const categoryLabel = getPocCategoryLabel(poc);
    const isSelected = LibraryState.selectedPocIds.has(poc.id);
    const truncatedDesc = poc.vuln_description ?
        (poc.vuln_description.length > 180 ?
            poc.vuln_description.substring(0, 180) + '...' :
            poc.vuln_description) :
        '暂无描述';
    const runtimeParamsHtml = needsRuntimeParams ? createRuntimeParamsForm(poc) : '';

    card.innerHTML = `
        <div class="poc-item-main">
            <div class="poc-item-heading">
            ${LibraryState.batchMode && batchEligible ? `
            <label class="poc-row-select" onclick="event.stopPropagation()">
                <input type="checkbox"
                       ${isSelected ? 'checked' : ''}
                       onchange="toggleBatchPocSelection(${poc.id})">
                <span>加入批量</span>
            </label>
            ` : ''}
                <div class="poc-item-title-group">
                    <h3 class="poc-row-title">${poc.vuln_name || `POC-${poc.id}`}</h3>
                    <div class="poc-row-meta">
                    <span><i class="fas fa-bug"></i> ${escapeHtml(poc.vuln_type || '-')}</span>
                    <span><i class="fas fa-calendar"></i> ${formatDateSmart(poc.create_time)}</span>
                    </div>
                </div>
            </div>
            <p class="poc-row-description">${escapeHtml(truncatedDesc)}</p>
        </div>

        <div class="poc-item-side">
            <div class="poc-row-badges">
                <span class="poc-badge ${poc.poc_type}">${poc.poc_type.toUpperCase()}</span>
                <span class="poc-badge ${category === 'manual' ? 'manual' : 'verifiable'}">
                    <i class="fas fa-${category === 'direct' ? 'check-circle' : category === 'params' ? 'sliders-h' : 'hand-paper'}"></i>
                    ${categoryLabel}
                </span>
                ${isVerifiable && !batchEligible ? `
                <span class="poc-badge manual">
                    <i class="fas fa-layer-group"></i>
                    仅单条执行
                </span>
                ` : ''}
            </div>

            <div class="poc-item-run">
                ${isVerifiable ? `
                <div class="poc-execute-form poc-row-execute-form">
                    <input
                        type="text"
                        class="poc-execute-input"
                        placeholder="输入目标URL..."
                        data-poc-id="${poc.id}"
                    >
                    <button class="btn-poc-execute" onclick="executePOCCard(${poc.id})">
                        <i class="fas fa-play"></i>
                        验证
                    </button>
                </div>
                ${runtimeParamsHtml}
                ` : '<div class="poc-row-manual-tip">该记录需要人工验证，请查看操作指南。</div>'}
            </div>

            <div class="poc-row-actions">
                <button class="btn-poc-action" onclick="viewPOCDetailsV2(${poc.id})" title="查看详情">
                    <i class="fas fa-info-circle"></i>
                    <span>详情</span>
                </button>
                ${isVerifiable ? `
                    <button class="btn-poc-action" onclick="viewPOCCodeV2(${poc.id})" title="查看代码">
                        <i class="fas fa-code"></i>
                        <span>代码</span>
                    </button>
                    <button class="btn-poc-action" onclick="downloadPOCFileV2(${poc.id})" title="下载">
                        <i class="fas fa-download"></i>
                        <span>下载</span>
                    </button>
                ` : `
                    <button class="btn-poc-action" onclick="viewManualGuideV2(${poc.id})" title="查看指南">
                        <i class="fas fa-book"></i>
                        <span>操作指南</span>
                    </button>
                `}
                <button class="btn-poc-action danger" onclick="deletePOCV2(${poc.id})" title="删除">
                    <i class="fas fa-trash"></i>
                    <span>删除</span>
                </button>
            </div>
        </div>
    `;

    return card;
}

function createRuntimeParamsForm(poc) {
    const fields = (poc.input_schema || []).map(field => createRuntimeParamField(poc.id, field)).join('');
    return `
        <div class="poc-runtime-panel">
            <div class="poc-runtime-header">
                <i class="fas fa-sliders-h"></i>
                <span>附加参数（执行前填写）</span>
            </div>
            <div class="poc-runtime-help">该 POC 需要你补充运行时参数，例如 Cookie、Token、Header 或 JSON 数据。</div>
            <div class="poc-runtime-fields">
                ${fields}
            </div>
        </div>
    `;
}

function createRuntimeParamField(pocId, field) {
    const name = escapeHtml(field.name || '');
    const label = escapeHtml(field.label || field.name || '参数');
    const placeholder = escapeHtml(field.placeholder || '');
    const description = field.description ? `<div class="poc-runtime-help">${escapeHtml(field.description)}</div>` : '';
    const requiredMark = field.required ? '<span class="poc-runtime-required">*</span>' : '';
    const dataAttrs = `data-poc-id="${pocId}" data-param-name="${name}" data-param-type="${escapeHtml(field.type || 'text')}"`;
    const defaultValue = field.default ?? '';

    let controlHtml = '';
    if (field.type === 'textarea' || field.type === 'json') {
        controlHtml = `
            <textarea
                class="poc-runtime-input textarea"
                ${dataAttrs}
                placeholder="${placeholder}"
            >${escapeHtml(String(defaultValue))}</textarea>
        `;
    } else if (field.type === 'select') {
        const options = Array.isArray(field.options) ? field.options : [];
        const optionsHtml = options.map(option => {
            const optionValue = typeof option === 'object' ? option.value : option;
            const optionLabel = typeof option === 'object' ? (option.label || option.value) : option;
            const selected = String(optionValue) === String(defaultValue) ? 'selected' : '';
            return `<option value="${escapeHtml(String(optionValue ?? ''))}" ${selected}>${escapeHtml(String(optionLabel ?? ''))}</option>`;
        }).join('');
        controlHtml = `<select class="poc-runtime-input" ${dataAttrs}>${optionsHtml}</select>`;
    } else if (field.type === 'checkbox') {
        const checked = defaultValue ? 'checked' : '';
        controlHtml = `
            <label class="poc-runtime-checkbox">
                <input type="checkbox" class="poc-runtime-input" ${dataAttrs} ${checked}>
                <span>启用</span>
            </label>
        `;
    } else {
        const inputType = field.type === 'password' ? 'password' : 'text';
        controlHtml = `
            <input
                type="${inputType}"
                class="poc-runtime-input"
                ${dataAttrs}
                value="${escapeHtml(String(defaultValue))}"
                placeholder="${placeholder}"
            >
        `;
    }

    return `
        <div class="poc-runtime-field">
            <label class="poc-runtime-label">${label}${requiredMark}</label>
            ${controlHtml}
            ${description}
        </div>
    `;
}

function getBatchEligiblePOCs() {
    return filterPOCs().filter(isBatchEligiblePoc);
}

function isBatchEligiblePoc(poc) {
    return poc && poc.verifiable !== 0 && poc.poc_type !== 'manual' && poc.execution_mode === 'url_only';
}

function getPocCategory(poc) {
    if (!poc || poc.verifiable === 0 || poc.execution_mode === 'manual_guide') {
        return 'manual';
    }
    if (poc.execution_mode === 'url_with_params') {
        return 'params';
    }
    return 'direct';
}

function getPocCategoryLabel(poc) {
    const category = getPocCategory(poc);
    if (category === 'params') {
        return '带参验证';
    }
    if (category === 'manual') {
        return '人工验证';
    }
    return '直接验证';
}

function getBatchUrls() {
    const input = document.getElementById('batch-urls-input');
    if (!input) return [];
    return input.value
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(Boolean);
}

function updateBatchSelectionUI() {
    const selectedCount = document.getElementById('batch-selected-pocs-count');
    const visibleCount = document.getElementById('batch-visible-pocs-count');
    const urlCount = document.getElementById('batch-url-count');
    const preview = document.getElementById('batch-task-preview');

    if (!selectedCount || !visibleCount || !urlCount || !preview) {
        return;
    }

    const visiblePocs = getBatchEligiblePOCs();
    const urls = getBatchUrls();

    selectedCount.textContent = LibraryState.selectedPocIds.size;
    visibleCount.textContent = visiblePocs.length;
    urlCount.textContent = urls.length;
    preview.textContent = `预计创建 ${urls.length * LibraryState.selectedPocIds.size} 个子任务`;
}

function toggleBatchMode(force) {
    LibraryState.batchMode = typeof force === 'boolean' ? force : !LibraryState.batchMode;
    document.getElementById('batch-mode-panel').style.display = LibraryState.batchMode ? 'block' : 'none';
    renderPOCGrid();
    updateBatchSelectionUI();
}

function toggleBatchPocSelection(pocId) {
    if (LibraryState.selectedPocIds.has(pocId)) {
        LibraryState.selectedPocIds.delete(pocId);
    } else {
        LibraryState.selectedPocIds.add(pocId);
    }
    updateBatchSelectionUI();
}

function selectVisibleBatchPocs() {
    getBatchEligiblePOCs().forEach(p => LibraryState.selectedPocIds.add(p.id));
    renderPOCGrid();
}

function clearSelectedBatchPocs() {
    LibraryState.selectedPocIds.clear();
    renderPOCGrid();
}

// ========================================
// 智能日期格式化
// ========================================
function formatDateSmart(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (days < 30) return `${Math.floor(days / 7)}周前`;
    if (days < 365) return `${Math.floor(days / 30)}个月前`;

    return date.toLocaleDateString('zh-CN');
}

// ========================================
// 显示空状态
// ========================================
function showLibraryEmpty() {
    document.getElementById('lib-loading').style.display = 'none';
    document.getElementById('lib-poc-grid').style.display = 'none';
    document.getElementById('lib-empty').style.display = 'flex';
}

// ========================================
// 执行POC验证
// ========================================
async function executePOCCard(pocId) {
    const inputEl = document.querySelector(`.poc-execute-input[data-poc-id="${pocId}"]`);
    const targetUrl = inputEl.value.trim();
    const poc = LibraryState.pocs.find(item => item.id === pocId);

    if (!targetUrl) {
        showToast('请输入目标URL', 'warning');
        inputEl.focus();
        return;
    }

    let runtimeParams = null;
    try {
        runtimeParams = collectRuntimeParams(poc);
    } catch (error) {
        showToast(error.message || '附加参数格式错误', 'error');
        return;
    }

    const btnEl = event.target.closest('.btn-poc-execute');
    const originalHTML = btnEl.innerHTML;
    btnEl.disabled = true;
    btnEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 验证中...';

    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_url: targetUrl,
                runtime_params: runtimeParams
            })
        });

        const data = await response.json();

        // 显示结果对话框
        showExecutionResultModal(data, targetUrl);

    } catch (error) {
        console.error('执行POC失败:', error);
        showToast('执行POC失败', 'error');
    } finally {
        btnEl.disabled = false;
        btnEl.innerHTML = originalHTML;
    }
}

// ========================================
// 显示执行结果模态框
// ========================================
function showExecutionResultModal(data, targetUrl) {
    const modal = document.createElement('div');
    modal.className = 'result-dialog-overlay';
    modal.onclick = (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    };

    let resultHTML = '';
    const classification = data.classification || null;
    const classificationHTML = buildFailureClassificationHTML(classification);
    if (data.success && data.result) {
        const result = data.result;
        const vulnerable = result.vulnerable;

        if (vulnerable) {
            // 发现漏洞
            resultHTML = `
                <div class="result-dialog-icon success">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h3 class="result-dialog-title" style="color: #ef4444;">检测到漏洞！</h3>
                <div class="result-dialog-content">
                    <div class="result-item">
                        <strong>目标URL:</strong>
                        <span>${data.target_url || targetUrl}</span>
                    </div>
                    <div class="result-item">
                        <strong>判断依据:</strong>
                        <span>${result.reason || '未提供判断依据'}</span>
                    </div>
                    ${classificationHTML}
                    ${result.details ? `
                        <div class="result-item">
                            <strong>详细信息:</strong>
                            <pre class="result-details">${typeof result.details === 'object' ? JSON.stringify(result.details, null, 2) : result.details}</pre>
                        </div>
                    ` : ''}
                </div>
            `;
        } else {
            // 未发现漏洞
            resultHTML = `
                <div class="result-dialog-icon info">
                    <i class="fas fa-info-circle"></i>
                </div>
                <h3 class="result-dialog-title">未发现漏洞</h3>
                <div class="result-dialog-content">
                    <div class="result-item">
                        <strong>目标URL:</strong>
                        <span>${data.target_url || targetUrl}</span>
                    </div>
                    <div class="result-item">
                        <strong>判断依据:</strong>
                        <span>${result.reason || '未提供判断依据'}</span>
                    </div>
                    ${classificationHTML}
                    ${result.details ? `
                        <div class="result-item">
                            <strong>详细信息:</strong>
                            <pre class="result-details">${typeof result.details === 'object' ? JSON.stringify(result.details, null, 2) : result.details}</pre>
                        </div>
                    ` : ''}
                </div>
            `;
        }
    } else {
        // 执行失败
        resultHTML = `
            <div class="result-dialog-icon error">
                <i class="fas fa-times-circle"></i>
            </div>
            <h3 class="result-dialog-title" style="color: #ef4444;">执行失败</h3>
            <div class="result-dialog-content">
                <div class="result-item">
                    <strong>错误信息:</strong>
                    <pre class="result-details">${data.error || '未知错误'}</pre>
                </div>
                ${data.result?.reason ? `
                    <div class="result-item">
                        <strong>判断依据:</strong>
                        <span>${data.result.reason}</span>
                    </div>
                ` : ''}
                ${classificationHTML}
                ${data.result?.details ? `
                    <div class="result-item">
                        <strong>详细信息:</strong>
                        <pre class="result-details">${typeof data.result.details === 'object' ? JSON.stringify(data.result.details, null, 2) : data.result.details}</pre>
                    </div>
                ` : ''}
            </div>
        `;
    }

    modal.innerHTML = `
        <div class="result-dialog">
            ${resultHTML}
            <button class="result-dialog-close" onclick="this.closest('.result-dialog-overlay').remove()">
                <i class="fas fa-times"></i> 关闭
            </button>
        </div>
    `;

    document.body.appendChild(modal);
}

// ========================================
// 查看POC代码
// ========================================
async function viewPOCCodeV2(pocId) {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC信息失败', 'error');
            return;
        }

        const poc = data.poc;

        // 获取代码内容
        const codeResponse = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}/code`);
        let pocCode = '';

        if (codeResponse.ok) {
            const codeData = await codeResponse.json();
            pocCode = codeData.code || '无法读取代码';
        } else {
            pocCode = '无法读取代码文件';
        }

        // 显示代码对话框
        const modal = document.createElement('div');
        modal.className = 'result-dialog-overlay';
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };

        modal.innerHTML = `
            <div class="result-dialog code-dialog">
                <div class="result-dialog-header">
                    <h3><i class="fas fa-code"></i> ${poc.vuln_name}</h3>
                    <button class="result-dialog-close-btn" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="code-dialog-content">
                    <pre><code class="language-python">${escapeHtml(pocCode)}</code></pre>
                </div>
                <div class="result-dialog-footer">
                    <button class="btn-secondary" onclick="copyCodeToClipboard(${pocId})">
                        <i class="fas fa-copy"></i> 复制代码
                    </button>
                    <button class="btn-secondary" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i> 关闭
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

    } catch (error) {
        console.error('查看POC代码失败:', error);
        showToast('查看POC代码失败', 'error');
    }
}

// ========================================
// 复制代码到剪贴板
// ========================================
async function copyCodeToClipboard(pocId) {
    try {
        const codeElement = document.querySelector('.code-dialog-content code');
        const code = codeElement.textContent;

        await navigator.clipboard.writeText(code);
        showToast('代码已复制到剪贴板', 'success');
    } catch (error) {
        showToast('复制失败', 'error');
    }
}

// ========================================
// 下载POC文件
// ========================================
async function downloadPOCFileV2(pocId) {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC信息失败', 'error');
            return;
        }

        const poc = data.poc;

        // 获取代码内容
        const codeResponse = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}/code`);

        if (codeResponse.ok) {
            const codeData = await codeResponse.json();
            const pocCode = codeData.code || '';

            // 创建下载
            const blob = new Blob([pocCode], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${poc.vuln_type}_${poc.id}.py`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast('POC文件已下载', 'success');
        } else {
            showToast('下载失败', 'error');
        }

    } catch (error) {
        console.error('下载POC文件失败:', error);
        showToast('下载POC文件失败', 'error');
    }
}

// ========================================
// 查看POC完整详情
// ========================================
async function viewPOCDetailsV2(pocId) {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC信息失败', 'error');
            return;
        }

        const poc = data.poc;

        // 显示详情对话框
        const modal = document.createElement('div');
        modal.className = 'result-dialog-overlay';
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };

        const isVerifiable = poc.verifiable !== 0;

        modal.innerHTML = `
            <div class="result-dialog details-dialog">
                <div class="result-dialog-header">
                    <h3><i class="fas fa-info-circle"></i> POC详情</h3>
                    <button class="result-dialog-close-btn" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="details-dialog-content">
                    <div class="detail-section">
                        <h4><i class="fas fa-tag"></i> 基本信息</h4>
                        <div class="detail-item">
                            <strong>POC名称:</strong>
                            <span>${poc.vuln_name || `POC-${poc.id}`}</span>
                        </div>
                        <div class="detail-item">
                            <strong>漏洞类型:</strong>
                            <span>${poc.vuln_type || '-'}</span>
                        </div>
                        <div class="detail-item">
                            <strong>POC类型:</strong>
                            <span class="poc-badge ${poc.poc_type}">${poc.poc_type.toUpperCase()}</span>
                        </div>
                        <div class="detail-item">
                            <strong>验证方式:</strong>
                            <span class="poc-badge ${isVerifiable ? 'verifiable' : 'manual'}">
                                <i class="fas fa-${isVerifiable ? 'check-circle' : 'hand-paper'}"></i>
                                ${isVerifiable ? '可自动验证' : '需人工操作'}
                            </span>
                        </div>
                        <div class="detail-item">
                            <strong>创建时间:</strong>
                            <span>${poc.create_time || '-'}</span>
                        </div>
                        ${poc.last_used ? `
                        <div class="detail-item">
                            <strong>最后使用:</strong>
                            <span>${poc.last_used}</span>
                        </div>
                        ` : ''}
                    </div>

                    <div class="detail-section">
                        <h4><i class="fas fa-file-alt"></i> 详细描述</h4>
                        <div class="detail-description">
                            <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: inherit;">${poc.vuln_description || '暂无描述'}</pre>
                        </div>
                    </div>
                </div>
                <div class="result-dialog-footer">
                    <button class="btn-secondary" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i> 关闭
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

    } catch (error) {
        console.error('查看POC详情失败:', error);
        showToast('查看POC详情失败', 'error');
    }
}

// ========================================
// 查看人工操作指南
// ========================================
async function viewManualGuideV2(pocId) {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC信息失败', 'error');
            return;
        }

        const poc = data.poc;

        // 解析manual_steps
        let manualSteps = null;
        if (poc.manual_steps) {
            try {
                manualSteps = typeof poc.manual_steps === 'string' ?
                    JSON.parse(poc.manual_steps) : poc.manual_steps;
            } catch (e) {
                console.error('解析manual_steps失败:', e);
            }
        }

        if (!manualSteps) {
            showToast('该POC没有人工操作指南', 'warning');
            return;
        }

        // 显示人工操作指南对话框
        const modal = document.createElement('div');
        modal.className = 'result-dialog-overlay';
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };

        // 构建步骤HTML
        let stepsHTML = '';
        if (manualSteps.steps && Array.isArray(manualSteps.steps)) {
            stepsHTML = manualSteps.steps.map((step, index) => `
                <div class="manual-step">
                    <div class="manual-step-number">${index + 1}</div>
                    <div class="manual-step-content">
                        ${step.title ? `<h6 class="manual-step-title">${escapeHtml(step.title)}</h6>` : ''}
                        <div class="manual-step-section">
                            <strong><i class="fas fa-info-circle"></i> 操作说明:</strong>
                            <p>${escapeHtml(step.description || step.step || step)}</p>
                        </div>
                        ${step.commands && step.commands.length > 0 ? `
                            <div class="manual-step-section">
                                <strong><i class="fas fa-terminal"></i> 执行命令:</strong>
                                ${step.commands.map(cmd => `
                                    <pre class="command-block"><code>${escapeHtml(cmd)}</code></pre>
                                `).join('')}
                            </div>
                        ` : ''}
                        ${step.expected_result ? `
                            <div class="manual-step-section success-indicator">
                                <strong><i class="fas fa-check-circle"></i> 预期结果:</strong>
                                <p>${escapeHtml(step.expected_result)}</p>
                            </div>
                        ` : ''}
                        ${step.notes ? `
                            <div class="manual-step-section warning-note">
                                <strong><i class="fas fa-exclamation-triangle"></i> 注意事项:</strong>
                                <p>${escapeHtml(step.notes)}</p>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `).join('');
        } else if (manualSteps.description) {
            stepsHTML = `<div class="manual-description"><pre style="white-space: pre-wrap;">${escapeHtml(manualSteps.description)}</pre></div>`;
        } else {
            stepsHTML = `<div class="manual-description"><pre style="white-space: pre-wrap;">${escapeHtml(JSON.stringify(manualSteps, null, 2))}</pre></div>`;
        }

        modal.innerHTML = `
            <div class="result-dialog manual-guide-dialog">
                <div class="result-dialog-header">
                    <h3><i class="fas fa-book"></i> 人工操作指南</h3>
                    <button class="result-dialog-close-btn" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="manual-guide-content">
                    <div class="manual-guide-info">
                        <h4>${poc.vuln_name || `POC-${poc.id}`}</h4>
                        <p>${poc.vuln_description || '暂无描述'}</p>
                    </div>

                    ${poc.explanation ? `
                    <div class="manual-reason-box">
                        <h5><i class="fas fa-exclamation-circle"></i> 不可自动化原因</h5>
                        <p>${escapeHtml(poc.explanation)}</p>
                    </div>
                    ` : ''}

                    ${manualSteps.summary ? `
                    <div class="manual-summary">
                        <h5><i class="fas fa-lightbulb"></i> 概述</h5>
                        <p>${escapeHtml(manualSteps.summary)}</p>
                    </div>
                    ` : ''}

                    <div class="manual-steps-container">
                        <h5><i class="fas fa-list-ol"></i> 操作步骤</h5>
                        ${stepsHTML}
                    </div>

                    ${manualSteps.verification ? `
                    <div class="manual-verification">
                        <h5><i class="fas fa-check-circle"></i> 验证方法</h5>
                        ${manualSteps.verification.success_indicators ? `
                            <div class="verification-section">
                                <strong>成功标志:</strong>
                                <ul>
                                    ${manualSteps.verification.success_indicators.map(indicator =>
                                        `<li>${escapeHtml(indicator)}</li>`
                                    ).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${manualSteps.verification.failure_indicators ? `
                            <div class="verification-section">
                                <strong>失败标志:</strong>
                                <ul>
                                    ${manualSteps.verification.failure_indicators.map(indicator =>
                                        `<li>${escapeHtml(indicator)}</li>`
                                    ).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${manualSteps.verification.example_output ? `
                            <div class="verification-section">
                                <strong>示例输出:</strong>
                                <pre style="white-space: pre-wrap; background: #f5f5f5; padding: 10px; border-radius: 4px;">${escapeHtml(manualSteps.verification.example_output)}</pre>
                            </div>
                        ` : ''}
                    </div>
                    ` : ''}

                    ${manualSteps.notes ? `
                    <div class="manual-notes">
                        <h5><i class="fas fa-exclamation-triangle"></i> 注意事项</h5>
                        <pre style="white-space: pre-wrap;">${escapeHtml(manualSteps.notes)}</pre>
                    </div>
                    ` : ''}
                </div>
                <div class="result-dialog-footer">
                    <button class="btn-secondary" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i> 关闭
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

    } catch (error) {
        console.error('查看人工操作指南失败:', error);
        showToast('查看人工操作指南失败', 'error');
    }
}

// ========================================
// 删除POC
// ========================================
async function deletePOCV2(pocId) {
    if (!confirm('确定要删除此POC吗？此操作不可恢复！')) {
        return;
    }

    try {
        const response = await fetch(`${LIB_API_BASE}/api/pocs/${pocId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('POC已删除', 'success');
            // 重新加载数据
            loadLibraryData();
        } else {
            showToast(data.detail || data.error || '删除失败', 'error');
        }

    } catch (error) {
        console.error('删除POC失败:', error);
        showToast('删除POC失败', 'error');
    }
}

function collectRuntimeParams(poc) {
    if (!poc || poc.execution_mode !== 'url_with_params' || !Array.isArray(poc.input_schema) || poc.input_schema.length === 0) {
        return null;
    }

    const params = {};
    for (const field of poc.input_schema) {
        const selector = `.poc-runtime-input[data-poc-id="${poc.id}"][data-param-name="${field.name}"]`;
        const element = document.querySelector(selector);
        if (!element) {
            continue;
        }

        let value;
        if (field.type === 'checkbox') {
            value = element.checked;
        } else {
            value = (element.value || '').trim();
        }

        if ((value === '' || value === null) && field.required) {
            throw new Error(`请填写参数：${field.label || field.name}`);
        }

        if (value === '' || value === null) {
            continue;
        }

        if (field.type === 'json') {
            try {
                value = JSON.parse(value);
            } catch (error) {
                throw new Error(`参数 ${field.label || field.name} 不是合法 JSON`);
            }
        }

        params[field.name] = value;
    }

    return Object.keys(params).length ? params : null;
}

// ========================================
// 批量任务
// ========================================
async function createBatchTask() {
    const targetUrls = getBatchUrls();
    const pocIds = Array.from(LibraryState.selectedPocIds);
    const concurrency = parseInt(document.getElementById('batch-concurrency-select').value, 10) || 3;

    if (targetUrls.length === 0) {
        showToast('请先输入或导入至少一个URL', 'warning');
        return;
    }

    if (pocIds.length === 0) {
        showToast('请至少选择一个可批量执行的 URL-only POC', 'warning');
        return;
    }

    try {
        const response = await fetch(`${LIB_API_BASE}/api/batch-tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_urls: targetUrls,
                poc_ids: pocIds,
                concurrency
            })
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            showToast(data.detail || data.message || '创建批量任务失败', 'error');
            return;
        }

        if (typeof switchTab === 'function') {
            switchTab('records');
        }
        showToast('批量任务已创建，开始检测', 'success');
        await loadBatchTasks();
    } catch (error) {
        console.error('创建批量任务失败:', error);
        showToast('创建批量任务失败', 'error');
    }
}

async function loadAssetSourceConfig() {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/config/asset-sources`);
        const data = await response.json();
        if (!response.ok || !data.success || !data.config) {
            return;
        }
        const provider = document.getElementById('asset-provider-select')?.value || 'fofa';
        applyAssetSourceProviderConfig(provider, data.config);
    } catch (error) {
        console.error('加载空间测绘配置失败:', error);
    }
}

function applyAssetSourceProviderConfig(provider, config) {
    const emailInput = document.getElementById('asset-email-input');
    const tokenInput = document.getElementById('asset-token-input');
    const emailLabel = document.getElementById('asset-email-label');
    const summary = document.getElementById('asset-import-summary');

    const providerConfig = (config || {})[provider] || {};
    if (emailInput) {
        emailInput.disabled = provider !== 'fofa';
        emailInput.placeholder = provider === 'fofa' ? 'FOFA 邮箱，仅 FOFA 需要' : '当前平台无需邮箱';
        emailInput.value = provider === 'fofa' ? (providerConfig.email || '') : '';
    }
    if (emailLabel) {
        emailLabel.textContent = provider === 'fofa' ? 'FOFA 邮箱' : '邮箱（无需填写）';
    }
    if (tokenInput) {
        tokenInput.value = providerConfig.token || '';
    }
    if (summary) {
        const preview = provider === 'fofa'
            ? `邮箱：${providerConfig.email_preview || '未设置'} ｜ Token：${providerConfig.token_preview || '未设置'}`
            : `Token：${providerConfig.token_preview || '未设置'}`;
        summary.textContent = `当前 ${provider.toUpperCase()} 配置：${preview}`;
    }
}

async function saveAssetSourceConfig() {
    const provider = document.getElementById('asset-provider-select').value;
    const email = document.getElementById('asset-email-input').value.trim();
    const token = document.getElementById('asset-token-input').value.trim();

    try {
        const response = await fetch(`${LIB_API_BASE}/api/config/asset-sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider,
                email: provider === 'fofa' ? (email || null) : null,
                token: token || null,
                base_url: null,
            }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            showToast(data.detail || '保存空间测绘配置失败', 'error');
            return;
        }
        applyAssetSourceProviderConfig(provider, data.current_config || {});
        showToast('空间测绘配置已保存', 'success');
    } catch (error) {
        console.error('保存空间测绘配置失败:', error);
        showToast('保存空间测绘配置失败', 'error');
    }
}

async function importTargetsFromAssetSource() {
    const provider = document.getElementById('asset-provider-select').value;
    const query = document.getElementById('asset-query-input').value.trim();
    const pages = parseInt(document.getElementById('asset-pages-select').value, 10) || 1;
    const summary = document.getElementById('asset-import-summary');

    if (!query) {
        showToast('请输入查询语句', 'warning');
        return;
    }

    try {
        if (summary) {
            summary.textContent = `正在从 ${provider.toUpperCase()} 导入目标...`;
        }
        const response = await fetch(`${LIB_API_BASE}/api/asset-sources/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, query, pages }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            showToast(data.detail || '导入目标失败', 'error');
            if (summary) {
                summary.textContent = data.detail || '导入目标失败';
            }
            return;
        }

        const input = document.getElementById('batch-urls-input');
        const current = input.value
            .split('\n')
            .map(item => item.trim())
            .filter(Boolean);
        const merged = [...new Set([...current, ...(data.targets || [])])];
        input.value = merged.join('\n');
        updateBatchSelectionUI();

        if (summary) {
            summary.textContent = `已从 ${provider.toUpperCase()} 导入 ${data.total} 个目标，并追加到 URL 列表。`;
        }
        showToast(`已导入 ${data.total} 个目标`, 'success');
    } catch (error) {
        console.error('导入空间测绘目标失败:', error);
        if (summary) {
            summary.textContent = '导入空间测绘目标失败';
        }
        showToast('导入空间测绘目标失败', 'error');
    }
}

async function loadBatchTasks() {
    const listEl = document.getElementById('batch-tasks-list');
    if (!listEl) return;

    try {
        const params = new URLSearchParams({
            limit: '50',
            sort_by: LibraryState.recordsFilters.sortBy,
            sort_order: LibraryState.recordsFilters.sortOrder,
        });
        if (LibraryState.recordsFilters.status) {
            params.append('status', LibraryState.recordsFilters.status);
        }
        if (LibraryState.recordsFilters.resultFilter) {
            params.append('result_filter', LibraryState.recordsFilters.resultFilter);
        }
        if (LibraryState.recordsFilters.keyword) {
            params.append('keyword', LibraryState.recordsFilters.keyword);
        }

        const response = await fetch(`${LIB_API_BASE}/api/batch-tasks?${params.toString()}`);
        const data = await response.json();

        if (!data.success) {
            listEl.innerHTML = '<div class="empty-folder">任务加载失败</div>';
            return;
        }

        const previousStatusMap = new Map(LibraryState.batchTaskStatusMap);
        LibraryState.batchTasks = data.tasks || [];
        LibraryState.batchTaskStatusMap = new Map(LibraryState.batchTasks.map(task => [task.id, task.status]));
        updateBatchTaskSummary();
        renderActiveBatchTask();
        notifyBatchTaskTransitions(previousStatusMap, LibraryState.batchTasks);
        LibraryState.batchTasksInitialized = true;
        renderBatchTaskList();
    } catch (error) {
        console.error('加载批量任务失败:', error);
        listEl.innerHTML = '<div class="empty-folder">任务加载失败</div>';
    }
}

function renderBatchTaskList() {
    const listEl = document.getElementById('batch-tasks-list');
    if (!listEl) return;

    if (!LibraryState.batchTasks.length) {
        listEl.innerHTML = '<div class="empty-folder"><i class="fas fa-inbox"></i><p>暂无批量任务</p></div>';
        return;
    }

    listEl.innerHTML = LibraryState.batchTasks.map(task => {
        const completed = task.completed_items || 0;
        const total = task.total_items || 0;
        const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
        const config = task.config_json || {};
        const taskType = task.task_type || 'poc_batch';
        const sourceLabel = taskType === 'nuclei_scan' ? 'Nuclei扫描' : 'POC批量检测';
        const sourceIcon = taskType === 'nuclei_scan' ? 'crosshairs' : 'flask';
        const unitLabel = taskType === 'nuclei_scan' ? '模板' : 'POC';
        const unitCount = taskType === 'nuclei_scan' ? (config.template_count || config.poc_count || 0) : (config.poc_count || 0);
        const hitCount = task.vulnerable_items || 0;
        const exceptionCount = task.failed_items || 0;
        const missCount = Math.max((task.success_items || 0) - hitCount, 0);
        const statusLabel = getBatchTaskStatusLabel(task.status);
        const createdAt = formatDateTime(task.created_at);
        const finishedAt = task.finished_at ? formatDateTime(task.finished_at) : '进行中';
        return `
            <div class="batch-task-card ${task.status === 'running' ? 'is-running' : ''}">
                <div class="batch-task-card-header">
                    <div class="batch-task-heading">
                        <div class="batch-task-title-row">
                            <div class="batch-task-title">任务 #${task.id}</div>
                            <span class="batch-task-status ${task.status}">${statusLabel}</span>
                        </div>
                        <div class="batch-task-meta">
                            <span><i class="fas fa-${sourceIcon}"></i> ${sourceLabel}</span>
                            <span><i class="fas fa-layer-group"></i> ${task.mode}</span>
                            <span><i class="fas fa-link"></i> ${config.url_count || 0} 个 URL</span>
                            <span><i class="fas fa-cubes"></i> ${unitCount} 个${unitLabel}</span>
                            <span><i class="fas fa-calendar-plus"></i> ${createdAt}</span>
                            <span><i class="fas fa-flag-checkered"></i> ${finishedAt}</span>
                        </div>
                    </div>
                    <div class="batch-task-highlight ${hitCount > 0 ? 'risk' : exceptionCount > 0 ? 'warn' : 'clean'}">
                        ${hitCount > 0 ? `${hitCount} 个命中` : exceptionCount > 0 ? `${exceptionCount} 个异常` : '全部未命中'}
                    </div>
                </div>

                <div class="batch-task-progress">
                    <div class="batch-task-progress-bar" style="width: ${progress}%"></div>
                </div>

                <div class="batch-task-stats">
                    <span><strong>${completed}</strong> / ${total} 已完成</span>
                    <span><strong>${hitCount}</strong> 命中</span>
                    <span><strong>${missCount}</strong> 未命中</span>
                    <span><strong>${exceptionCount}</strong> 异常</span>
                    <span><strong>${progress}%</strong> 进度</span>
                </div>

                <div class="batch-task-actions">
                    <button class="btn-poc-action" onclick="viewBatchTaskDetails(${task.id})">
                        <i class="fas fa-eye"></i>
                        <span>查看详情</span>
                    </button>
                    <button class="btn-poc-action" onclick="exportBatchTaskReport(${task.id}, 'html')">
                        <i class="fas fa-file-export"></i>
                        <span>导出</span>
                    </button>
                    ${(task.status === 'pending' || task.status === 'running') ? `
                    <button class="btn-poc-action danger" onclick="cancelBatchTask(${task.id})">
                        <i class="fas fa-stop"></i>
                        <span>取消</span>
                    </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function updateBatchTaskSummary() {
    const totalEl = document.getElementById('records-total-tasks');
    const runningEl = document.getElementById('records-running-tasks');
    const completedEl = document.getElementById('records-completed-tasks');
    const failedEl = document.getElementById('records-failed-total');

    if (!totalEl || !runningEl || !completedEl || !failedEl) {
        return;
    }

    const tasks = LibraryState.batchTasks;
    totalEl.textContent = tasks.length;
    runningEl.textContent = tasks.filter(task => task.status === 'running' || task.status === 'pending').length;
    completedEl.textContent = tasks.filter(task => task.status === 'completed').length;
    failedEl.textContent = tasks.reduce((sum, task) => sum + (task.failed_items || 0), 0);
}

function renderActiveBatchTask() {
    const container = document.getElementById('records-active-task');
    if (!container) {
        return;
    }

    const activeTask = LibraryState.batchTasks.find(task => task.status === 'running' || task.status === 'pending');
    if (!activeTask) {
        container.style.display = 'none';
        container.innerHTML = '';
        return;
    }

    const total = activeTask.total_items || 0;
    const completed = activeTask.completed_items || 0;
    const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
    const config = activeTask.config_json || {};
    const taskType = activeTask.task_type || 'poc_batch';
    const sourceLabel = taskType === 'nuclei_scan' ? 'Nuclei扫描' : 'POC批量检测';
    const unitLabel = taskType === 'nuclei_scan' ? '模板' : 'POC';
    const unitCount = taskType === 'nuclei_scan' ? (config.template_count || config.poc_count || 0) : (config.poc_count || 0);
    const statusLabel = getBatchTaskStatusLabel(activeTask.status);
    const hitCount = activeTask.vulnerable_items || 0;
    const exceptionCount = activeTask.failed_items || 0;
    const missCount = Math.max((activeTask.success_items || 0) - hitCount, 0);

    container.style.display = 'block';
    container.innerHTML = `
        <div class="active-task-card">
            <div class="active-task-copy">
                <div class="active-task-kicker">
                    <span class="active-task-dot"></span>
                    ${sourceLabel} · ${statusLabel}
                </div>
                <h3>任务 #${activeTask.id} 正在执行</h3>
                <p>当前模式：${activeTask.mode}，目标 ${config.url_count || 0} 个，${unitLabel} ${unitCount} 个。页面会持续更新，不需要手动刷新。</p>
            </div>
            <div class="active-task-metrics">
                <div><strong>${completed}</strong><span>已完成</span></div>
                <div><strong>${hitCount}</strong><span>命中</span></div>
                <div><strong>${missCount}</strong><span>未命中</span></div>
                <div><strong>${exceptionCount}</strong><span>异常</span></div>
            </div>
            <div class="active-task-progress">
                <div class="active-task-progress-label">
                    <span>进度 ${completed}/${total}</span>
                    <span>${progress}%</span>
                </div>
                <div class="batch-task-progress">
                    <div class="batch-task-progress-bar" style="width: ${progress}%"></div>
                </div>
            </div>
        </div>
    `;
}

function notifyBatchTaskTransitions(previousStatusMap, tasks) {
    if (!LibraryState.batchTasksInitialized) {
        return;
    }

    tasks.forEach(task => {
        const previous = previousStatusMap.get(task.id);
        if (!previous || previous === task.status) {
            return;
        }

        if (task.status === 'completed') {
            showToast(`批量任务 #${task.id} 检测完成`, 'success');
            const activeTab = document.querySelector('.nav-tab.active')?.getAttribute('data-tab');
            if (activeTab === 'records') {
                setTimeout(() => {
                    const firstCard = document.querySelector('.batch-task-card');
                    if (firstCard) {
                        firstCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                }, 120);
            }
        } else if (task.status === 'cancelled') {
            showToast(`批量任务 #${task.id} 已取消`, 'warning');
        }
    });
}

async function cancelBatchTask(taskId) {
    if (!confirm('确定要取消该批量任务吗？')) {
        return;
    }

    try {
        const response = await fetch(`${LIB_API_BASE}/api/batch-tasks/${taskId}/cancel`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            showToast(data.detail || data.message || '取消任务失败', 'error');
            return;
        }

        showToast('批量任务已取消', 'success');
        await loadBatchTasks();
    } catch (error) {
        console.error('取消批量任务失败:', error);
        showToast('取消批量任务失败', 'error');
    }
}

async function viewBatchTaskDetails(taskId) {
    try {
        const [taskRes, itemsRes] = await Promise.all([
            fetch(`${LIB_API_BASE}/api/batch-tasks/${taskId}`),
            fetch(`${LIB_API_BASE}/api/batch-tasks/${taskId}/items?limit=200`)
        ]);

        const taskData = await taskRes.json();
        const itemsData = await itemsRes.json();

        if (!taskData.success || !itemsData.success) {
            showToast('获取任务详情失败', 'error');
            return;
        }

        const task = taskData.task;
        const items = itemsData.items || [];
        const taskType = task.task_type || 'poc_batch';
        const sourceLabel = taskType === 'nuclei_scan' ? 'Nuclei扫描' : 'POC批量检测';
        const unitLabel = taskType === 'nuclei_scan' ? '模板' : 'POC';
        const config = task.config_json || {};
        const unitCount = taskType === 'nuclei_scan' ? (config.template_count || config.poc_count || 0) : (config.poc_count || 0);
        const hitCount = task.vulnerable_items || 0;
        const exceptionCount = task.failed_items || 0;
        const missCount = Math.max((task.success_items || 0) - hitCount, 0);
        const rowsHtml = items.length ? items.map(item => `
            <tr>
                <td class="batch-result-cell-url">${escapeHtml(item.target_url || '-')}</td>
                <td>${escapeHtml(getBatchItemTargetName(item))}</td>
                <td><span class="batch-item-status ${getBatchItemDisplayClass(item)}">${escapeHtml(getBatchItemDisplayStatus(item))}</span></td>
                <td>${item.vulnerable ? '<span class="batch-result-hit">是</span>' : '否'}</td>
                <td>${escapeHtml(item.reason || '-')}</td>
                <td>${escapeHtml(item.error || '-')}</td>
                <td>
                    ${item.has_detail ? `
                    <button class="btn-poc-action batch-detail-btn" onclick="viewBatchTaskItemDetail(${task.id}, ${item.id})">
                        <i class="fas fa-file-alt"></i>
                        <span>详情</span>
                    </button>
                    ` : '<span class="batch-result-no-detail">无详情</span>'}
                </td>
            </tr>
        `).join('') : `
            <tr>
                <td colspan="7" class="batch-result-empty">暂无子任务结果</td>
            </tr>
        `;

        const modal = document.createElement('div');
        modal.className = 'result-dialog-overlay';
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };

        modal.innerHTML = `
            <div class="result-dialog details-dialog" style="max-width: 1100px;">
                <div class="result-dialog-header">
                    <h3><i class="fas fa-stream"></i> 批量任务 #${task.id}</h3>
                    <button class="result-dialog-close-btn" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="details-dialog-content">
                    <div class="detail-section">
                        <h4><i class="fas fa-chart-line"></i> 任务概览</h4>
                        <div class="detail-item"><strong>任务来源:</strong> <span>${sourceLabel}</span></div>
                        <div class="detail-item"><strong>状态:</strong> <span>${escapeHtml(getBatchTaskStatusLabel(task.status))}</span></div>
                        <div class="detail-item"><strong>URL 数量:</strong> <span>${config.url_count || 0}</span></div>
                        <div class="detail-item"><strong>${unitLabel} 数量:</strong> <span>${unitCount}</span></div>
                        <div class="detail-item"><strong>总任务数:</strong> <span>${task.total_items}</span></div>
                        <div class="detail-item"><strong>已完成:</strong> <span>${task.completed_items}</span></div>
                        <div class="detail-item"><strong>命中:</strong> <span>${hitCount}</span></div>
                        <div class="detail-item"><strong>未命中:</strong> <span>${missCount}</span></div>
                        <div class="detail-item"><strong>异常:</strong> <span>${exceptionCount}</span></div>
                        <div class="detail-actions-inline">
                            <button class="btn-poc-action" onclick="exportBatchTaskReport(${task.id}, 'html')">
                                <i class="fas fa-file-code"></i>
                                <span>HTML报告</span>
                            </button>
                            <button class="btn-poc-action" onclick="exportBatchTaskReport(${task.id}, 'json')">
                                <i class="fas fa-brackets-curly"></i>
                                <span>JSON</span>
                            </button>
                            <button class="btn-poc-action" onclick="exportBatchTaskReport(${task.id}, 'txt')">
                                <i class="fas fa-file-lines"></i>
                                <span>TXT</span>
                            </button>
                        </div>
                    </div>
                    <div class="detail-section">
                        <h4><i class="fas fa-list"></i> 子任务结果</h4>
                        <div class="batch-results-table-wrap">
                            <table class="batch-results-table">
                                <thead>
                                    <tr>
                                        <th>URL</th>
                                        <th>${unitLabel}</th>
                                        <th>状态</th>
                                        <th>命中</th>
                                        <th>判断依据</th>
                                        <th>错误信息</th>
                                        <th>详情</th>
                                    </tr>
                                </thead>
                                <tbody>${rowsHtml}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    } catch (error) {
        console.error('查看批量任务详情失败:', error);
        showToast('查看批量任务详情失败', 'error');
    }
}

async function viewBatchTaskItemDetail(taskId, itemId) {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/batch-tasks/${taskId}/items/${itemId}/detail`);
        const data = await response.json();

        if (!response.ok || !data.success) {
            showToast(data.detail || '获取子任务详情失败', 'error');
            return;
        }

        const item = data.item;
        const modal = document.createElement('div');
        modal.className = 'result-dialog-overlay';
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };

        modal.innerHTML = `
            <div class="result-dialog details-dialog" style="max-width: 900px;">
                <div class="result-dialog-header">
                    <h3><i class="fas fa-file-alt"></i> 子任务详情 #${item.id}</h3>
                    <button class="result-dialog-close-btn" onclick="this.closest('.result-dialog-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="details-dialog-content">
                    <div class="detail-section">
                        <h4><i class="fas fa-info-circle"></i> 摘要</h4>
                        <div class="detail-item"><strong>URL:</strong> <span>${escapeHtml(item.target_url || '-')}</span></div>
                        <div class="detail-item"><strong>${item.engine_type === 'nuclei' ? '模板' : 'POC'}:</strong> <span>${escapeHtml(getBatchItemTargetName(item))}</span></div>
                        <div class="detail-item"><strong>状态:</strong> <span>${escapeHtml(getBatchItemDisplayStatus(item))}</span></div>
                        <div class="detail-item"><strong>命中:</strong> <span>${item.vulnerable ? '是' : '否'}</span></div>
                        <div class="detail-item"><strong>判断依据:</strong> <span>${escapeHtml(item.reason || '-')}</span></div>
                        <div class="detail-item"><strong>错误信息:</strong> <span>${escapeHtml(item.error || '-')}</span></div>
                        <div class="detail-item"><strong>分类:</strong> <span>${escapeHtml(getFailureCategoryLabel(item.failure_category))}</span></div>
                        <div class="detail-item"><strong>代码:</strong> <span>${escapeHtml(item.failure_code || '-')}</span></div>
                        <div class="detail-item"><strong>阶段:</strong> <span>${escapeHtml(getFailureStageLabel(item.failure_stage))}</span></div>
                        <div class="detail-item"><strong>建议重试:</strong> <span>${item.retryable ? '是' : '否'}</span></div>
                    </div>
                    <div class="detail-section">
                        <h4><i class="fas fa-code"></i> 详细结果</h4>
                        <pre class="batch-detail-json">${escapeHtml(JSON.stringify(item.detail, null, 2))}</pre>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    } catch (error) {
        console.error('查看子任务详情失败:', error);
        showToast('查看子任务详情失败', 'error');
    }
}

async function exportBatchTaskReport(taskId, format = 'html') {
    try {
        const response = await fetch(`${LIB_API_BASE}/api/batch-tasks/${taskId}/export?format=${encodeURIComponent(format)}`);
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            showToast(data.detail || '导出报告失败', 'error');
            return;
        }

        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition') || '';
        const matched = disposition.match(/filename="([^"]+)"/);
        const fileName = matched ? matched[1] : `batch_task_${taskId}_report.${format}`;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('报告已导出', 'success');
    } catch (error) {
        console.error('导出批量任务报告失败:', error);
        showToast('导出报告失败', 'error');
    }
}

function ensureBatchTaskPolling() {
    if (LibraryState.batchTaskPoller) {
        return;
    }

    LibraryState.batchTaskPoller = setInterval(() => {
        const hasActiveTask = LibraryState.batchTasks.some(task => task.status === 'pending' || task.status === 'running');
        const activeTab = document.querySelector('.nav-tab.active')?.getAttribute('data-tab');
        if (LibraryState.batchMode || hasActiveTask || activeTab === 'records') {
            loadBatchTasks();
        }
    }, 5000);
}

function updateRecordsFilters() {
    const statusEl = document.getElementById('records-status-filter');
    const resultEl = document.getElementById('records-result-filter');
    const sortByEl = document.getElementById('records-sort-by');
    const sortOrderEl = document.getElementById('records-sort-order');

    if (statusEl) LibraryState.recordsFilters.status = statusEl.value;
    if (resultEl) LibraryState.recordsFilters.resultFilter = resultEl.value;
    if (sortByEl) LibraryState.recordsFilters.sortBy = sortByEl.value;
    if (sortOrderEl) LibraryState.recordsFilters.sortOrder = sortOrderEl.value;
}

function getBatchTaskStatusLabel(status) {
    const labels = {
        pending: '待执行',
        running: '检测中',
        completed: '已完成',
        cancelled: '已取消',
        failed: '失败'
    };
    return labels[status] || status || '未知状态';
}

function getBatchItemStatusLabel(status) {
    const labels = {
        pending: '待执行',
        running: '执行中',
        success: '执行完成',
        failed: '失败',
        cancelled: '已取消',
        skipped: '已跳过'
    };
    return labels[status] || status || '未知状态';
}

function getBatchItemDisplayStatus(item) {
    if (item.vulnerable) return '命中';
    if (item.status === 'success') return '未命中';
    if (item.status === 'failed') return '异常';
    return getBatchItemStatusLabel(item.status);
}

function getBatchItemDisplayClass(item) {
    if (item.vulnerable) return 'success';
    if (item.status === 'success') return 'cancelled';
    if (item.status === 'failed') return 'failed';
    return item.status || 'pending';
}

function getBatchItemTargetName(item) {
    if (item.engine_type === 'nuclei') {
        return item.template_path || item.template_id || 'Nuclei模板';
    }
    return item.vuln_name || `POC-${item.poc_id}`;
}

function buildFailureClassificationHTML(classification) {
    if (!classification || (!classification.failure_category && !classification.failure_code && !classification.failure_stage)) {
        return '';
    }

    return `
        <div class="result-item">
            <strong>结构化分类:</strong>
            <span>${escapeHtml(getFailureCategoryLabel(classification.failure_category))}</span>
        </div>
        <div class="result-item">
            <strong>分类代码:</strong>
            <span>${escapeHtml(classification.failure_code || '-')}</span>
        </div>
        <div class="result-item">
            <strong>发生阶段:</strong>
            <span>${escapeHtml(getFailureStageLabel(classification.failure_stage))}</span>
        </div>
        <div class="result-item">
            <strong>建议重试:</strong>
            <span>${classification.retryable ? '是' : '否'}</span>
        </div>
    `;
}

function getFailureCategoryLabel(category) {
    const labels = {
        not_vulnerable: '未命中',
        network_error: '网络异常',
        code_error: '代码异常',
        environment_error: '环境异常',
        oob_error: 'OOB 异常',
        nuclei_error: 'Nuclei 异常',
        unknown: '未分类'
    };
    return labels[category] || category || '-';
}

function getFailureStageLabel(stage) {
    const labels = {
        precheck: '预检查',
        request_send: '请求发送',
        response_parse: '响应解析',
        result_judgement: '结果判定',
        code_execution: '代码执行',
        engine_execution: '引擎执行'
    };
    return labels[stage] || stage || '-';
}

function formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) {
        return dateString;
    }
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ========================================
// HTML转义
// ========================================
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text ?? '').replace(/[&<>"']/g, m => map[m]);
}

// ========================================
// 设置事件监听器
// ========================================
function setupLibraryEventListeners() {
    // 筛选标签切换
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            LibraryState.currentFilter = tab.dataset.filter;
            renderPOCGrid();
        });
    });

    // 搜索输入
    const searchInput = document.getElementById('lib-search-input');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            LibraryState.searchQuery = e.target.value;
            renderPOCGrid();
        }, 300);
    });

    // 漏洞类型筛选
    const vulnTypeFilter = document.getElementById('lib-filter-type');
    vulnTypeFilter.addEventListener('change', (e) => {
        LibraryState.vulnTypeFilter = e.target.value;
        renderPOCGrid();
    });

    // 排序方式
    const sortBy = document.getElementById('lib-sort-by');
    sortBy.addEventListener('change', (e) => {
        LibraryState.sortBy = e.target.value;
        renderPOCGrid();
    });

    const batchUrlsInput = document.getElementById('batch-urls-input');
    batchUrlsInput.addEventListener('input', updateBatchSelectionUI);

    const batchFileInput = document.getElementById('batch-url-file');
    batchFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) {
            return;
        }
        const content = await file.text();
        batchUrlsInput.value = [batchUrlsInput.value.trim(), content.trim()].filter(Boolean).join('\n');
        updateBatchSelectionUI();
        e.target.value = '';
    });

    document.getElementById('toggle-batch-mode-btn').addEventListener('click', () => toggleBatchMode(true));
    document.getElementById('exit-batch-mode-btn').addEventListener('click', () => toggleBatchMode(false));
    document.getElementById('select-visible-pocs-btn').addEventListener('click', selectVisibleBatchPocs);
    document.getElementById('clear-selected-pocs-btn').addEventListener('click', clearSelectedBatchPocs);
    document.getElementById('create-batch-task-btn').addEventListener('click', createBatchTask);
    document.getElementById('save-asset-config-btn').addEventListener('click', saveAssetSourceConfig);
    document.getElementById('import-asset-targets-btn').addEventListener('click', importTargetsFromAssetSource);
    document.getElementById('asset-provider-select').addEventListener('change', async (e) => {
        try {
            const response = await fetch(`${LIB_API_BASE}/api/config/asset-sources`);
            const data = await response.json();
            if (response.ok && data.success && data.config) {
                applyAssetSourceProviderConfig(e.target.value, data.config);
            }
        } catch (error) {
            console.error('切换空间测绘平台失败:', error);
        }
    });
    document.getElementById('refresh-batch-tasks-btn').addEventListener('click', () => {
        loadBatchTasks();
        showToast('批量任务已刷新', 'success');
    });

    const recordsStatusFilter = document.getElementById('records-status-filter');
    const recordsResultFilter = document.getElementById('records-result-filter');
    const recordsSortBy = document.getElementById('records-sort-by');
    const recordsSortOrder = document.getElementById('records-sort-order');
    const recordsSearchInput = document.getElementById('records-search-input');

    [recordsStatusFilter, recordsResultFilter, recordsSortBy, recordsSortOrder].forEach(el => {
        if (!el) return;
        el.addEventListener('change', () => {
            updateRecordsFilters();
            loadBatchTasks();
        });
    });

    let recordsSearchTimeout;
    if (recordsSearchInput) {
        recordsSearchInput.addEventListener('input', () => {
            clearTimeout(recordsSearchTimeout);
            recordsSearchTimeout = setTimeout(() => {
                LibraryState.recordsFilters.keyword = recordsSearchInput.value.trim();
                loadBatchTasks();
            }, 250);
        });
    }

    // 刷新按钮
    const refreshBtn = document.getElementById('refresh-library-btn');
    refreshBtn.addEventListener('click', () => {
        loadLibraryData();
        showToast('已刷新', 'success');
    });
}

// ========================================
// 导出函数供外部使用
// ========================================
window.initLibrary = initLibrary;
window.initBatchRecords = initBatchRecords;
window.executePOCCard = executePOCCard;
window.viewPOCCodeV2 = viewPOCCodeV2;
window.viewPOCDetailsV2 = viewPOCDetailsV2;
window.downloadPOCFileV2 = downloadPOCFileV2;
window.viewManualGuideV2 = viewManualGuideV2;
window.deletePOCV2 = deletePOCV2;
window.copyCodeToClipboard = copyCodeToClipboard;
window.toggleBatchPocSelection = toggleBatchPocSelection;
window.viewBatchTaskDetails = viewBatchTaskDetails;
window.viewBatchTaskItemDetail = viewBatchTaskItemDetail;
window.cancelBatchTask = cancelBatchTask;
window.exportBatchTaskReport = exportBatchTaskReport;
