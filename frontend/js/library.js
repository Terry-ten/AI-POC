// ========================================
// 全新POC库管理 JavaScript
// ========================================

// API配置 - 使用全局LIB_API_BASE或默认值
const LIB_API_BASE = window.LIB_API_BASE || 'http://127.0.0.1:8000';

// POC库状态管理
const LibraryState = {
    pocs: [],           // 所有POC数据
    currentFilter: 'all', // 当前筛选: all, verifiable, manual
    searchQuery: '',    // 搜索关键词
    vulnTypeFilter: '', // 漏洞类型筛选
    sortBy: 'newest'    // 排序方式
};

// ========================================
// 初始化POC库
// ========================================
function initLibrary() {
    loadLibraryData();
    setupLibraryEventListeners();
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

    // 统计可验证和需人工的
    const verifiable = pocs.filter(p => p.verifiable !== 0).length;
    const manual = pocs.filter(p => p.verifiable === 0).length;

    // 统计漏洞类型数量
    const vulnTypes = new Set(pocs.map(p => p.vuln_type)).size;

    // 更新统计卡片
    document.getElementById('stat-total-modern').textContent = total;
    document.getElementById('stat-verifiable-modern').textContent = verifiable;
    document.getElementById('stat-manual-modern').textContent = manual;
    document.getElementById('stat-types-modern').textContent = vulnTypes;

    // 更新筛选标签计数
    document.getElementById('count-all').textContent = total;
    document.getElementById('count-verifiable').textContent = verifiable;
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
}

// ========================================
// 筛选POC
// ========================================
function filterPOCs() {
    let filtered = [...LibraryState.pocs];

    // 按可验证性筛选
    if (LibraryState.currentFilter === 'verifiable') {
        filtered = filtered.filter(p => p.verifiable !== 0);
    } else if (LibraryState.currentFilter === 'manual') {
        filtered = filtered.filter(p => p.verifiable === 0);
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
    card.className = 'poc-card-v2';

    const isVerifiable = poc.verifiable !== 0;
    const truncatedDesc = poc.vuln_description ?
        (poc.vuln_description.length > 120 ?
            poc.vuln_description.substring(0, 120) + '...' :
            poc.vuln_description) :
        '暂无描述';

    card.innerHTML = `
        <div class="poc-card-header-v2">
            <h3 class="poc-card-title">${poc.vuln_name || `POC-${poc.id}`}</h3>
            <div class="poc-card-badges-v2">
                <span class="poc-badge ${poc.poc_type}">${poc.poc_type.toUpperCase()}</span>
                <span class="poc-badge ${isVerifiable ? 'verifiable' : 'manual'}">
                    <i class="fas fa-${isVerifiable ? 'check-circle' : 'hand-paper'}"></i>
                    ${isVerifiable ? '可验证' : '需人工'}
                </span>
            </div>
        </div>

        <div class="poc-card-body-v2">
            <p class="poc-card-description">${truncatedDesc}</p>
            <div class="poc-card-meta-v2">
                <div class="poc-meta-item">
                    <i class="fas fa-bug"></i>
                    <span>${poc.vuln_type}</span>
                </div>
                <div class="poc-meta-item">
                    <i class="fas fa-calendar"></i>
                    <span>${formatDateSmart(poc.create_time)}</span>
                </div>
            </div>
        </div>

        ${isVerifiable ? `
        <div class="poc-card-execute-v2">
            <div class="poc-execute-form">
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
        </div>
        ` : ''}

        <div class="poc-card-actions-v2">
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
    `;

    return card;
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

    if (!targetUrl) {
        showToast('请输入目标URL', 'warning');
        inputEl.focus();
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
            body: JSON.stringify({ target_url: targetUrl })
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

        if (data.success) {
            showToast('POC已删除', 'success');
            // 重新加载数据
            loadLibraryData();
        } else {
            showToast(data.error || '删除失败', 'error');
        }

    } catch (error) {
        console.error('删除POC失败:', error);
        showToast('删除POC失败', 'error');
    }
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
    return text.replace(/[&<>"']/g, m => map[m]);
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
window.executePOCCard = executePOCCard;
window.viewPOCCodeV2 = viewPOCCodeV2;
window.viewPOCDetailsV2 = viewPOCDetailsV2;
window.downloadPOCFileV2 = downloadPOCFileV2;
window.viewManualGuideV2 = viewManualGuideV2;
window.deletePOCV2 = deletePOCV2;
window.copyCodeToClipboard = copyCodeToClipboard;
