// ========================================
// 全局变量和配置
// ========================================

const API_BASE_URL = 'http://127.0.0.1:8000';
const API_ENDPOINT = `${API_BASE_URL}/api/generate-poc`;
const POC_LIBRARY_ENDPOINT = `${API_BASE_URL}/api/pocs`;

// 示例数据
const EXAMPLES = {
    sql: {
        vulnerability_info: `目标网站 http://example.com/login 存在SQL注入漏洞

漏洞位置: 登录页面的username参数
触发方式: 使用单引号(')可以触发数据库错误
数据库类型: MySQL

HTTP请求示例:
POST /login HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded

username=admin'&password=123456

响应: You have an error in your SQL syntax`,
        target_info: 'MySQL 5.7 - PHP 7.4 - Apache 2.4'
    },
    xss: {
        vulnerability_info: `目标网站存在反射型XSS漏洞

URL: http://example.com/search
参数: q (搜索关键词)
触发: 输入<script>alert(1)</script>会直接执行

测试payload:
http://example.com/search?q=<script>alert(document.cookie)</script>

响应: 搜索结果页面直接渲染了脚本代码`,
        target_info: 'Web应用 - 无输入过滤'
    },
    upload: {
        vulnerability_info: `文件上传漏洞 - 可上传PHP后门

URL: http://example.com/upload
方式: POST multipart/form-data
限制: 仅检查文件扩展名，未检查文件内容

绕过方式:
1. 修改扩展名为 .php5, .phtml
2. 双写扩展名 .php.jpg
3. 大小写绕过 .PhP

上传成功后文件路径: /uploads/filename.php`,
        target_info: 'PHP 7.x - Apache - Linux'
    },
    ssrf: {
        vulnerability_info: `服务端请求伪造(SSRF)漏洞

URL: http://example.com/api/fetch
参数: url
功能: 服务器会请求用户提供的URL并返回内容

漏洞验证:
GET /api/fetch?url=http://127.0.0.1:8080/admin

可以访问内网服务，读取本地文件等`,
        target_info: 'Python Flask - 内网IP段: 192.168.1.0/24'
    }
};

// ========================================
// DOM元素引用
// ========================================

const elements = {
    // 输入元素
    vulnerabilityInfo: document.getElementById('vulnerability-info'),
    targetInfo: document.getElementById('target-info'),
    generateBtn: document.getElementById('generate-btn'),
    exampleButtons: document.querySelectorAll('.btn-example'),

    // 输出元素
    loadingState: document.getElementById('loading-state'),
    emptyState: document.getElementById('empty-state'),
    resultContent: document.getElementById('result-content'),
    vulnDescription: document.getElementById('vuln-description'),
    vulnType: document.getElementById('vuln-type'),
    pocCode: document.getElementById('poc-code'),
    explanationContent: document.getElementById('explanation-content'),
    copyBtn: document.getElementById('copy-btn'),
    downloadBtn: document.getElementById('download-btn'),
    newBtn: document.getElementById('new-btn'),

    // Toast
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toast-message')
};

// ========================================
// 工具函数
// ========================================

/**
 * 显示Toast通知
 */
function showToast(message, type = 'success') {
    elements.toastMessage.textContent = message;
    elements.toast.classList.add('show');

    // 根据类型更改颜色
    if (type === 'error') {
        elements.toast.style.background = '#ef4444';
    } else if (type === 'warning') {
        elements.toast.style.background = '#f59e0b';
    } else {
        elements.toast.style.background = '#10b981';
    }

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

/**
 * 显示加载状态
 */
function showLoading() {
    elements.emptyState.style.display = 'none';
    elements.resultContent.style.display = 'none';
    elements.loadingState.style.display = 'block';
    elements.generateBtn.disabled = true;
    elements.generateBtn.innerHTML = `
        <i class="fas fa-spinner fa-spin"></i>
        <span>生成中...</span>
    `;

    // 重置进度步骤状态
    resetProgressSteps();
}

/**
 * 重置进度步骤
 */
function resetProgressSteps() {
    const steps = document.querySelectorAll('.progress-step');
    steps.forEach(step => {
        step.classList.remove('active', 'completed');
        const icon = step.querySelector('.step-icon i');
        icon.className = 'fas fa-circle';
        const status = step.querySelector('.step-status');
        status.textContent = '等待中...';
    });
}

/**
 * 更新进度步骤
 */
function updateProgressStep(step, status, message) {
    const stepElement = document.querySelector(`.progress-step[data-step="${step}"]`);
    if (!stepElement) return;

    const icon = stepElement.querySelector('.step-icon i');
    const statusText = stepElement.querySelector('.step-status');

    // 清除之前的所有步骤的active状态
    document.querySelectorAll('.progress-step').forEach(s => {
        if (parseInt(s.getAttribute('data-step')) < step) {
            s.classList.remove('active');
            s.classList.add('completed');
            s.querySelector('.step-icon i').className = 'fas fa-check-circle';
        } else if (parseInt(s.getAttribute('data-step')) === step) {
            s.classList.add('active');
            s.classList.remove('completed');
        } else {
            s.classList.remove('active', 'completed');
        }
    });

    if (status === 'active') {
        stepElement.classList.add('active');
        stepElement.classList.remove('completed');
        icon.className = 'fas fa-circle-notch fa-spin';
        statusText.textContent = message || '进行中...';
    } else if (status === 'completed') {
        stepElement.classList.remove('active');
        stepElement.classList.add('completed');
        icon.className = 'fas fa-check-circle';
        statusText.textContent = '已完成';
    }
}

/**
 * 隐藏加载状态
 */
function hideLoading() {
    elements.loadingState.style.display = 'none';
    elements.generateBtn.disabled = false;
    elements.generateBtn.innerHTML = `
        <i class="fas fa-magic"></i>
        <span>生成POC代码</span>
        <div class="btn-glow"></div>
    `;
}

/**
 * 显示结果
 */
function showResult(data) {
    elements.emptyState.style.display = 'none';
    elements.resultContent.style.display = 'block';

    // 隐藏原有的详细内容区域
    elements.vulnDescription.parentElement.style.display = 'none';
    elements.pocCode.parentElement.parentElement.style.display = 'none';
    elements.explanationContent.parentElement.style.display = 'none';
    document.querySelector('.action-buttons').style.display = 'none';

    // 显示简化的结果信息
    const resultContainer = document.getElementById('result-content');

    // 判断是否可验证
    const isVerifiable = data.verifiable !== false;
    const vulnType = data.vulnerability_type || '未知类型';

    resultContainer.innerHTML = `
        <div style="text-align: center; padding: 3rem 2rem;">
            <div style="margin-bottom: 2rem;">
                <i class="fas fa-${isVerifiable ? 'check-circle' : 'hand-paper'}"
                   style="font-size: 4rem; color: ${isVerifiable ? '#10b981' : '#f59e0b'};"></i>
            </div>

            <h2 style="font-size: 1.75rem; font-weight: 700; margin-bottom: 1rem; color: var(--text-primary);">
                ${isVerifiable ? '✅ 该漏洞可直接验证' : '⚠️ 该漏洞需人工操作'}
            </h2>

            <p style="font-size: 1.125rem; color: var(--text-secondary); margin-bottom: 2rem;">
                漏洞类型：<span style="color: var(--primary-color); font-weight: 600;">${vulnType}</span>
            </p>

            <div style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
                        border: 2px solid var(--primary-color); border-radius: 1rem; padding: 1.5rem; margin-bottom: 2rem;">
                <i class="fas fa-info-circle" style="color: var(--primary-color); margin-right: 0.5rem;"></i>
                <span style="color: var(--text-primary); font-weight: 600;">已成功保存到POC脚本库</span>
            </div>

            <p style="color: var(--text-muted); font-size: 0.9375rem; margin-bottom: 2rem;">
                ${isVerifiable
                    ? '您可以前往"POC库"标签页查看并执行此POC脚本'
                    : '您可以前往"POC库"标签页查看详细的人工操作指南'}
            </p>

            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button onclick="switchTab('library')" class="btn-primary" style="width: auto;">
                    <i class="fas fa-database"></i>
                    <span>前往POC库</span>
                    <div class="btn-glow"></div>
                </button>
                <button onclick="newPOC()" class="btn-secondary" style="width: auto;">
                    <i class="fas fa-plus"></i>
                    <span>继续生成</span>
                </button>
            </div>
        </div>
    `;
}

/**
 * 显示错误
 */
function showError(message) {
    elements.emptyState.style.display = 'block';
    elements.resultContent.style.display = 'none';
    showToast(message, 'error');
}

/**
 * 格式化代码（简单的语法高亮）
 */
function formatCode(code) {
    // 这里可以集成代码高亮库，如Prism.js或highlight.js
    // 暂时直接返回原始代码
    return code;
}

/**
 * 下载POC代码为文件
 */
function downloadPOC() {
    const code = elements.pocCode.textContent;
    const vulnType = elements.vulnType.textContent;

    if (!code || code === '// 无代码生成') {
        showToast('没有可下载的代码', 'warning');
        return;
    }

    // 创建文件名
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `poc_${vulnType.replace(/\s+/g, '_')}_${timestamp}.py`;

    // 创建Blob并下载
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('POC代码已下载', 'success');
}

/**
 * 复制代码到剪贴板
 */
async function copyToClipboard() {
    const code = elements.pocCode.textContent;

    if (!code || code === '// 无代码生成') {
        showToast('没有可复制的代码', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(code);
        showToast('代码已复制到剪贴板', 'success');

        // 临时改变按钮文本
        const originalHTML = elements.copyBtn.innerHTML;
        elements.copyBtn.innerHTML = '<i class="fas fa-check"></i><span>已复制</span>';

        setTimeout(() => {
            elements.copyBtn.innerHTML = originalHTML;
        }, 2000);
    } catch (err) {
        showToast('复制失败，请手动复制', 'error');
    }
}

/**
 * 重置表单，开始新的POC生成
 */
function newPOC() {
    elements.vulnerabilityInfo.value = '';
    elements.targetInfo.value = '';
    elements.resultContent.style.display = 'none';
    elements.emptyState.style.display = 'block';

    elements.vulnerabilityInfo.focus();
    showToast('已重置，可以输入新的漏洞信息', 'success');
}

// ========================================
// API调用
// ========================================

/**
 * 调用后端API生成POC（使用SSE流式响应）
 */
async function generatePOC() {
    const vulnerabilityInfo = elements.vulnerabilityInfo.value.trim();
    const targetInfo = elements.targetInfo.value.trim();

    // 验证输入
    if (!vulnerabilityInfo) {
        showToast('请输入漏洞信息', 'warning');
        elements.vulnerabilityInfo.focus();
        return;
    }

    // 显示加载状态
    showLoading();

    try {
        // 先发送POST请求启动生成流程
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                vulnerability_info: vulnerabilityInfo,
                target_info: targetInfo || null
            })
        });

        // 检查响应是否为流式响应
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // 读取流数据
        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');

            // 保留最后一个不完整的行
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);

                    if (data === '[DONE]') {
                        console.log('✅ 流式响应结束');
                        continue;
                    }

                    try {
                        const json = JSON.parse(data);

                        if (json.type === 'status') {
                            // 更新进度显示
                            console.log(`进度更新: 第${json.step}步 - ${json.message}`);
                            if (json.step > 0) {
                                updateProgressStep(json.step, 'active', json.message);
                            }
                        } else if (json.type === 'result') {
                            // 接收到最终结果
                            console.log('✅ 收到最终结果');
                            hideLoading();

                            if (json.data.success) {
                                // 标记步骤为完成
                                updateProgressStep(1, 'completed', '已完成');
                                showResult(json.data);
                                showToast('POC代码生成成功', 'success');
                            } else {
                                showError(json.data.error || 'POC生成失败');
                            }
                        } else if (json.type === 'error') {
                            // 接收到错误
                            console.error('❌ 生成失败:', json.data.error);
                            hideLoading();
                            showError(json.data.error || 'POC生成失败');
                        }
                    } catch (e) {
                        console.error('JSON解析错误:', e, data);
                    }
                }
            }
        }

    } catch (error) {
        hideLoading();
        console.error('API调用失败:', error);
        showError(`网络错误: ${error.message}`);
    }
}

// ========================================
// POC库管理功能
// ========================================

// 全局变量 - 当前查看的POC
let currentPOC = null;

/**
 * 标签页切换
 */
function switchTab(tabName) {
    const tabs = document.querySelectorAll('.nav-tab');
    const generatorSection = document.querySelector('.generator-section');
    const librarySection = document.querySelector('.library-section');

    // 更新标签状态
    tabs.forEach(tab => {
        if (tab.getAttribute('data-tab') === tabName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // 切换显示区域
    if (tabName === 'generator') {
        generatorSection.style.display = 'block';
        librarySection.style.display = 'none';
    } else if (tabName === 'library') {
        generatorSection.style.display = 'none';
        librarySection.style.display = 'block';

        // 加载POC库数据
        loadPOCLibrary();
        loadStatistics();
    }
}

/**
 * 加载POC库列表
 */
async function loadPOCLibrary() {
    const listContainer = document.getElementById('poc-list');
    const loadingState = document.getElementById('poc-list-loading');
    const emptyState = document.getElementById('poc-list-empty');

    // 显示加载状态
    loadingState.style.display = 'flex';
    emptyState.style.display = 'none';
    listContainer.innerHTML = '';

    try {
        // 获取筛选条件
        const keyword = document.getElementById('search-keyword').value.trim();
        const vulnType = document.getElementById('filter-vuln-type').value;
        const pocType = document.getElementById('filter-poc-type').value;

        // 获取当前选中的verifiable值
        const activeTab = document.querySelector('.verifiable-tabs .tab-btn.active');
        const verifiable = activeTab ? activeTab.dataset.verifiable : 'all';

        // 构建查询参数
        const params = new URLSearchParams();
        if (keyword) params.append('keyword', keyword);
        if (vulnType) params.append('vuln_type', vulnType);
        if (pocType) params.append('poc_type', pocType);

        // 添加verifiable参数
        if (verifiable !== 'all') {
            params.append('verifiable', verifiable === 'true' ? 'true' : 'false');
        }

        params.append('limit', '50');

        // 调用API
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/search?${params}`);
        const data = await response.json();

        // 隐藏加载状态
        loadingState.style.display = 'none';

        // 显示结果
        if (data.success && data.pocs && data.pocs.length > 0) {
            renderPOCList(data.pocs);
        } else {
            emptyState.style.display = 'flex';
        }

    } catch (error) {
        console.error('加载POC库失败:', error);
        loadingState.style.display = 'none';
        showToast('加载POC库失败', 'error');
    }
}

/**
 * 渲染POC列表
 */
function renderPOCList(pocs) {
    const listContainer = document.getElementById('poc-list');
    listContainer.innerHTML = '';

    pocs.forEach(poc => {
        const pocItem = document.createElement('div');
        pocItem.className = 'poc-card-new';

        const isVerifiable = poc.verifiable !== 0;

        // 截断描述到100个字符
        const shortDesc = poc.vuln_description ?
            (poc.vuln_description.length > 100 ? poc.vuln_description.substring(0, 100) + '...' : poc.vuln_description) :
            '暂无描述';

        pocItem.innerHTML = `
            <div class="poc-card-left">
                <!-- 漏洞信息 -->
                <div class="poc-card-info" onclick="showPOCDetail(${poc.id})">
                    <div class="poc-header-new">
                        <div class="poc-name">${poc.vuln_name || `POC-${poc.id}`}</div>
                        <div class="poc-badges">
                            <span class="poc-type-badge ${poc.poc_type}">${poc.poc_type.toUpperCase()}</span>
                            ${isVerifiable ?
                                '<span class="poc-type-badge verifiable"><i class="fas fa-check-circle"></i> 可验证</span>' :
                                '<span class="poc-type-badge manual"><i class="fas fa-hand-paper"></i> 需人工</span>'
                            }
                        </div>
                    </div>
                    <div class="poc-description">${shortDesc}</div>
                    <div class="poc-meta">
                        <span><i class="fas fa-bug"></i> ${poc.vuln_type}</span>
                        <span><i class="fas fa-calendar"></i> ${formatDate(poc.create_time)}</span>
                    </div>
                </div>

                ${isVerifiable ? `
                <!-- URL输入和验证区域 -->
                <div class="poc-execute-area">
                    <input type="text"
                           class="poc-url-input"
                           id="url-input-${poc.id}"
                           placeholder="输入目标URL (如: http://192.168.1.100:8080)"
                           onclick="event.stopPropagation()">
                    <button class="btn-execute" onclick="event.stopPropagation(); executeInlinePOC(${poc.id})">
                        <i class="fas fa-play"></i> 验证
                    </button>
                </div>
                ` : ''}
            </div>

            <!-- 右侧操作按钮 -->
            <div class="poc-card-actions">
                ${isVerifiable ? `
                    <button class="btn-action" onclick="event.stopPropagation(); viewPOCCode(${poc.id})" title="查看脚本">
                        <i class="fas fa-code"></i>
                        <span>查看脚本</span>
                    </button>
                    <button class="btn-action" onclick="event.stopPropagation(); downloadPOCFile(${poc.id})" title="下载脚本">
                        <i class="fas fa-download"></i>
                        <span>下载</span>
                    </button>
                ` : ''}
                <button class="btn-action btn-action-danger" onclick="event.stopPropagation(); deletePOCFromCard(${poc.id})" title="删除POC">
                    <i class="fas fa-trash"></i>
                    <span>删除</span>
                </button>
            </div>
        `;

        listContainer.appendChild(pocItem);
    });
}

/**
 * 格式化日期
 */
function formatDate(dateString) {
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
    return `${Math.floor(days / 365)}年前`;
}

/**
 * 显示POC详情模态框（只查看详情，不执行）
 */
async function showPOCDetail(pocId) {
    const modal = document.getElementById('poc-detail-modal');

    try {
        // 调用API获取详情
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC详情失败', 'error');
            return;
        }

        const poc = data.poc;
        currentPOC = poc;

        // 获取模态框的body元素
        const modalBody = document.querySelector('#poc-detail-modal .modal-body');

        // 根据verifiable字段显示不同内容
        if (poc.verifiable === 0 && poc.manual_steps) {
            // 不可验证：显示人工操作指南
            try {
                const manualSteps = typeof poc.manual_steps === 'string' ?
                    JSON.parse(poc.manual_steps) : poc.manual_steps;

                const manualGuideHTML = renderManualGuide(manualSteps);

                modalBody.innerHTML = `
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">漏洞类型:</span>
                            <span class="detail-value">${poc.vuln_type || '-'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">POC类型:</span>
                            <span class="detail-value">${poc.poc_type.toUpperCase()}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">创建时间:</span>
                            <span class="detail-value">${new Date(poc.create_time).toLocaleString()}</span>
                        </div>
                    </div>

                    <div class="detail-description">
                        <div class="detail-section-title">
                            <i class="fas fa-info-circle"></i>
                            漏洞描述
                        </div>
                        <div class="detail-section-content">
                            ${poc.vuln_description || '暂无描述'}
                        </div>
                    </div>

                    ${manualGuideHTML}
                `;
            } catch (e) {
                console.error('解析manual_steps失败:', e);
                modalBody.innerHTML = `
                    <div style="color: var(--error-color); padding: 1rem;">
                        <i class="fas fa-exclamation-triangle"></i>
                        无法解析人工操作指南数据
                    </div>
                `;
            }
        } else {
            // 可验证：只显示漏洞描述，不显示执行区域
            modalBody.innerHTML = `
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">漏洞类型:</span>
                        <span class="detail-value">${poc.vuln_type || '-'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">POC类型:</span>
                        <span class="detail-value">${poc.poc_type.toUpperCase()}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">创建时间:</span>
                        <span class="detail-value">${new Date(poc.create_time).toLocaleString()}</span>
                    </div>
                </div>

                <div class="detail-description">
                    <div class="detail-section-title">
                        <i class="fas fa-info-circle"></i>
                        漏洞描述
                    </div>
                    <div class="detail-section-content">
                        ${poc.vuln_description || '暂无描述'}
                    </div>
                </div>

                <div style="margin-top: 2rem; padding: 1rem; background: rgba(99, 102, 241, 0.1); border-radius: 0.5rem; text-align: center;">
                    <i class="fas fa-info-circle" style="color: var(--primary-color); margin-right: 0.5rem;"></i>
                    <span style="color: var(--text-secondary);">提示：POC脚本已在列表中，可直接在卡片上输入URL进行验证</span>
                </div>
            `;
        }

        // 显示模态框
        modal.style.display = 'flex';

    } catch (error) {
        console.error('获取POC详情失败:', error);
        showToast('获取POC详情失败', 'error');
    }
}

/**
 * 关闭POC详情模态框
 */
function closePOCDetailModal() {
    const modal = document.getElementById('poc-detail-modal');
    modal.style.display = 'none';
    currentPOC = null;
}

/**
 * 渲染人工操作指南
 */
function renderManualGuide(manualSteps) {
    let html = `
        <div class="manual-guide-section">
            <div class="manual-guide-header">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>该漏洞无法通过单个POC脚本自动化验证</h3>
            </div>

            <div class="manual-guide-notice">
                <strong>注意:</strong> 此漏洞需要人工操作和判断,请按照以下步骤进行验证。
            </div>
    `;

    // 渲染所需工具
    if (manualSteps.required_tools && manualSteps.required_tools.length > 0) {
        html += `
            <div class="manual-tools-section">
                <h4><i class="fas fa-tools"></i> 所需工具</h4>
        `;
        manualSteps.required_tools.forEach(tool => {
            html += `
                <div class="tool-item">
                    <div class="tool-item-header">
                        <span class="tool-name">${tool.name}</span>
                        ${tool.version ? `<span class="tool-version">版本: ${tool.version}</span>` : ''}
                    </div>
                    <div class="tool-purpose">${tool.purpose}</div>
                    ${tool.install_command ? `
                        <div class="tool-install">
                            <strong>安装命令:</strong><br>
                            <code>${tool.install_command}</code>
                        </div>
                    ` : ''}
                    ${tool.download_url ? `
                        <div style="margin-top: 0.5rem;">
                            <a href="${tool.download_url}" target="_blank" class="btn-link">
                                <i class="fas fa-download"></i> 下载链接
                            </a>
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += `</div>`;
    }

    // 渲染操作步骤
    if (manualSteps.steps && manualSteps.steps.length > 0) {
        html += `
            <div class="manual-steps-section">
                <h4><i class="fas fa-list-ol"></i> 操作步骤</h4>
        `;
        manualSteps.steps.forEach(step => {
            html += `
                <div class="step-item">
                    <div class="step-header">
                        <span class="step-number">${step.step_number}</span>
                        <span class="step-title">${step.title}</span>
                    </div>
                    <div class="step-description">${step.description}</div>

                    ${step.commands && step.commands.length > 0 ? `
                        <div class="step-commands">
                            ${step.commands.map(cmd => `<div class="step-command">$ ${cmd}</div>`).join('')}
                        </div>
                    ` : ''}

                    ${step.expected_result ? `
                        <div class="step-expected">
                            <div class="step-expected-label">预期结果:</div>
                            <div class="step-expected-text">${step.expected_result}</div>
                        </div>
                    ` : ''}

                    ${step.notes ? `
                        <div class="step-notes">
                            <div class="step-notes-label">注意事项:</div>
                            <div class="step-notes-text">${step.notes}</div>
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += `</div>`;
    }

    // 渲染验证结果说明
    if (manualSteps.verification) {
        html += `
            <div class="manual-verification-section">
                <h4><i class="fas fa-clipboard-check"></i> 如何判断漏洞存在</h4>

                ${manualSteps.verification.success_indicators ? `
                    <div class="verification-indicators">
                        <div class="indicator-label success">
                            <i class="fas fa-check-circle"></i> 成功标志:
                        </div>
                        <ul class="indicator-list success">
                            ${manualSteps.verification.success_indicators.map(indicator =>
                                `<li>${indicator}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${manualSteps.verification.failure_indicators ? `
                    <div class="verification-indicators">
                        <div class="indicator-label failure">
                            <i class="fas fa-times-circle"></i> 失败标志:
                        </div>
                        <ul class="indicator-list failure">
                            ${manualSteps.verification.failure_indicators.map(indicator =>
                                `<li>${indicator}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${manualSteps.verification.example_output ? `
                    <div style="margin-top: 1rem;">
                        <strong>示例输出:</strong>
                        <div class="example-output">${manualSteps.verification.example_output}</div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    html += `</div>`;
    return html;
}

/**
 * 执行POC
 */
async function executePOC() {
    if (!currentPOC) {
        showToast('请先选择POC', 'warning');
        return;
    }

    const targetUrl = document.getElementById('execute-target-url').value.trim();
    if (!targetUrl) {
        showToast('请输入目标URL', 'warning');
        return;
    }

    const executeBtn = document.getElementById('execute-poc-btn');
    const resultContainer = document.getElementById('execute-result');

    // 禁用按钮
    executeBtn.disabled = true;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 执行中...';

    try {
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${currentPOC.id}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                target_url: targetUrl
            })
        });

        const data = await response.json();

        // 显示结果
        resultContainer.style.display = 'block';

        if (data.success && data.result) {
            // 获取POC脚本返回的验证结果
            const pocResult = data.result;
            const vulnerable = pocResult.vulnerable;

            if (vulnerable) {
                // 漏洞存在
                resultContainer.className = 'execute-result success';
                let resultHtml = `
                    <h4 style="color: #10b981; margin-bottom: 0.5rem;">
                        <i class="fas fa-check-circle"></i> 检测到漏洞
                    </h4>
                    <div style="margin-top: 0.5rem;">
                        <p><strong>目标URL:</strong> ${data.target_url || targetUrl}</p>
                        <p><strong>判断依据:</strong> ${pocResult.reason || '未提供判断依据'}</p>
                `;

                if (pocResult.details) {
                    resultHtml += `
                        <div style="margin-top: 0.5rem;">
                            <strong>详细信息:</strong>
                            <pre style="white-space: pre-wrap; background: rgba(0,0,0,0.05); padding: 0.5rem; border-radius: 4px; margin-top: 0.25rem; max-height: 400px; overflow-y: auto;">${typeof pocResult.details === 'object' ? JSON.stringify(pocResult.details, null, 2) : pocResult.details}</pre>
                        </div>
                    `;
                }

                resultHtml += '</div>';
                resultContainer.innerHTML = resultHtml;
                showToast('检测到漏洞！', 'warning');
            } else {
                // 未发现漏洞
                resultContainer.className = 'execute-result';
                let resultHtml = `
                    <h4 style="color: #6b7280; margin-bottom: 0.5rem;">
                        <i class="fas fa-info-circle"></i> 未发现漏洞
                    </h4>
                    <div style="margin-top: 0.5rem;">
                        <p><strong>目标URL:</strong> ${data.target_url || targetUrl}</p>
                        <p><strong>判断依据:</strong> ${pocResult.reason || '未提供判断依据'}</p>
                `;

                if (pocResult.details) {
                    resultHtml += `
                        <div style="margin-top: 0.5rem;">
                            <strong>详细信息:</strong>
                            <pre style="white-space: pre-wrap; background: rgba(0,0,0,0.05); padding: 0.5rem; border-radius: 4px; margin-top: 0.25rem; max-height: 400px; overflow-y: auto;">${typeof pocResult.details === 'object' ? JSON.stringify(pocResult.details, null, 2) : pocResult.details}</pre>
                        </div>
                    `;
                }

                resultHtml += '</div>';
                resultContainer.innerHTML = resultHtml;
                showToast('POC执行完成', 'success');
            }
        } else {
            // 执行失败
            resultContainer.className = 'execute-result error';
            resultContainer.innerHTML = `
                <h4 style="color: #ef4444; margin-bottom: 0.5rem;">
                    <i class="fas fa-times-circle"></i> 执行失败
                </h4>
                <pre style="white-space: pre-wrap; margin: 0;">${data.error || '执行失败'}</pre>
            `;
            showToast('POC执行失败', 'error');
        }

    } catch (error) {
        console.error('执行POC失败:', error);
        resultContainer.style.display = 'block';
        resultContainer.className = 'execute-result error';
        resultContainer.innerHTML = `
            <h4 style="color: #ef4444; margin-bottom: 0.5rem;">
                <i class="fas fa-times-circle"></i> 网络错误
            </h4>
            <p>${error.message}</p>
        `;
        showToast('执行POC失败', 'error');
    } finally {
        // 恢复按钮
        executeBtn.disabled = false;
        executeBtn.innerHTML = '<i class="fas fa-rocket"></i> 执行';
    }
}

/**
 * 从卡片删除POC
 */
async function deletePOCFromCard(pocId) {
    if (!confirm(`确定要删除此POC吗？此操作不可恢复！`)) {
        return;
    }

    try {
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${pocId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('POC已删除', 'success');
            loadPOCLibrary();
            loadStatistics();
        } else {
            showToast(data.error || '删除失败', 'error');
        }

    } catch (error) {
        console.error('删除POC失败:', error);
        showToast('删除POC失败', 'error');
    }
}

/**
 * 在POC卡片上直接执行验证
 */
async function executeInlinePOC(pocId) {
    const urlInput = document.getElementById(`url-input-${pocId}`);
    const targetUrl = urlInput.value.trim();

    if (!targetUrl) {
        showToast('请输入目标URL', 'warning');
        urlInput.focus();
        return;
    }

    // 显示加载状态
    const executeBtn = event.target.closest('.btn-execute');
    const originalHTML = executeBtn.innerHTML;
    executeBtn.disabled = true;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 验证中...';

    try {
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${pocId}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                target_url: targetUrl
            })
        });

        const data = await response.json();

        // 恢复按钮
        executeBtn.disabled = false;
        executeBtn.innerHTML = originalHTML;

        // 显示结果对话框
        showExecutionResultDialog(data, targetUrl);

    } catch (error) {
        console.error('执行POC失败:', error);
        executeBtn.disabled = false;
        executeBtn.innerHTML = originalHTML;
        showToast('执行POC失败', 'error');
    }
}

/**
 * 显示执行结果对话框
 */
function showExecutionResultDialog(data, targetUrl) {
    const modal = document.createElement('div');
    modal.className = 'result-dialog-overlay';
    modal.onclick = (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    };

    let resultHTML = '';
    if (data.success && data.result) {
        const pocResult = data.result;
        const vulnerable = pocResult.vulnerable;

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
                        <span>${pocResult.reason || '未提供判断依据'}</span>
                    </div>
                    ${pocResult.details ? `
                        <div class="result-item">
                            <strong>详细信息:</strong>
                            <pre class="result-details">${typeof pocResult.details === 'object' ? JSON.stringify(pocResult.details, null, 2) : pocResult.details}</pre>
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
                        <span>${pocResult.reason || '未提供判断依据'}</span>
                    </div>
                    ${pocResult.details ? `
                        <div class="result-item">
                            <strong>详细信息:</strong>
                            <pre class="result-details">${typeof pocResult.details === 'object' ? JSON.stringify(pocResult.details, null, 2) : pocResult.details}</pre>
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

/**
 * 查看POC代码
 */
async function viewPOCCode(pocId) {
    try {
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC代码失败', 'error');
            return;
        }

        const poc = data.poc;

        // 读取POC文件内容
        const fileResponse = await fetch(`/api/pocs/${pocId}/code`);
        let pocCode = '';

        if (fileResponse.ok) {
            const fileData = await fileResponse.json();
            pocCode = fileData.code || '无法读取代码';
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
                    <pre><code class="language-python">${pocCode}</code></pre>
                </div>
                <div class="result-dialog-footer">
                    <button class="btn-secondary" onclick="copyPOCCode(${pocId})">
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

/**
 * 复制POC代码
 */
async function copyPOCCode(pocId) {
    try {
        const codeElement = document.querySelector('.code-dialog-content code');
        const code = codeElement.textContent;

        await navigator.clipboard.writeText(code);
        showToast('代码已复制到剪贴板', 'success');
    } catch (error) {
        showToast('复制失败', 'error');
    }
}

/**
 * 下载POC文件
 */
async function downloadPOCFile(pocId) {
    try {
        const response = await fetch(`${POC_LIBRARY_ENDPOINT}/${pocId}`);
        const data = await response.json();

        if (!data.success || !data.poc) {
            showToast('获取POC信息失败', 'error');
            return;
        }

        const poc = data.poc;

        // 读取POC文件内容
        const fileResponse = await fetch(`/api/pocs/${pocId}/code`);

        if (fileResponse.ok) {
            const fileData = await fileResponse.json();
            const pocCode = fileData.code || '';

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

/**
 * 加载统计信息
 */
async function loadStatistics() {
    try {
        // 加载统计数据
        const statsResponse = await fetch(`${POC_LIBRARY_ENDPOINT}/statistics`);
        const statsData = await statsResponse.json();

        if (statsData.success) {
            const stats = statsData.statistics;
            document.getElementById('stat-total').textContent = stats.total_pocs || 0;
            document.getElementById('stat-python').textContent = stats.python_pocs || 0;
            document.getElementById('stat-nuclei').textContent = stats.nuclei_pocs || 0;
        }

        // 加载漏洞类型列表
        const typesResponse = await fetch(`${POC_LIBRARY_ENDPOINT}/vuln-types`);
        const typesData = await typesResponse.json();

        if (typesData.success && typesData.vuln_types) {
            const filterSelect = document.getElementById('filter-vuln-type');

            // 清空现有选项（保留"所有类型"）
            filterSelect.innerHTML = '<option value="">所有漏洞类型</option>';

            // 添加漏洞类型选项
            typesData.vuln_types.forEach(type => {
                const option = document.createElement('option');
                option.value = type;
                option.textContent = type.toUpperCase();
                filterSelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

/**
 * 刷新POC库
 */
function refreshPOCLibrary() {
    // 清空搜索条件
    document.getElementById('search-keyword').value = '';
    document.getElementById('filter-vuln-type').value = '';
    document.getElementById('filter-poc-type').value = '';

    // 重新加载
    loadPOCLibrary();
    loadStatistics();

    showToast('已刷新', 'success');
}

// ========================================
// 事件监听器
// ========================================

/**
 * 初始化事件监听
 */
function initializeEventListeners() {
    // 生成按钮点击事件
    elements.generateBtn.addEventListener('click', generatePOC);

    // Enter键提交（在textarea中使用Ctrl+Enter）
    elements.vulnerabilityInfo.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            generatePOC();
        }
    });

    // 示例按钮点击事件
    elements.exampleButtons.forEach(button => {
        button.addEventListener('click', () => {
            const exampleType = button.getAttribute('data-example');
            const example = EXAMPLES[exampleType];

            if (example) {
                elements.vulnerabilityInfo.value = example.vulnerability_info;
                elements.targetInfo.value = example.target_info;
                showToast(`已加载${button.textContent.trim()}示例`, 'success');

                // 添加视觉反馈
                button.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    button.style.transform = '';
                }, 150);
            }
        });
    });

    // 复制按钮
    elements.copyBtn.addEventListener('click', copyToClipboard);

    // 下载按钮
    elements.downloadBtn.addEventListener('click', downloadPOC);

    // 新建按钮
    elements.newBtn.addEventListener('click', newPOC);

    // POC库管理相关事件
    // 可验证性选项卡切换
    const verifiableTabs = document.querySelectorAll('.verifiable-tabs .tab-btn');
    verifiableTabs.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有active类
            verifiableTabs.forEach(b => b.classList.remove('active'));
            // 添加active类到当前按钮
            this.classList.add('active');

            // 刷新POC列表
            loadPOCLibrary();
        });
    });

    // 标签页切换
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    // 搜索框输入事件（延迟搜索）
    let searchTimeout;
    const searchKeywordInput = document.getElementById('search-keyword');
    if (searchKeywordInput) {
        searchKeywordInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadPOCLibrary();
            }, 500);
        });
    }

    // 筛选条件变化
    const filterVulnType = document.getElementById('filter-vuln-type');
    const filterPocType = document.getElementById('filter-poc-type');
    if (filterVulnType) {
        filterVulnType.addEventListener('change', loadPOCLibrary);
    }
    if (filterPocType) {
        filterPocType.addEventListener('change', loadPOCLibrary);
    }

    // 刷新按钮
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshPOCLibrary);
    }

    // 模态框关闭按钮
    const modalCloseButtons = document.querySelectorAll('.modal-close');
    modalCloseButtons.forEach(btn => {
        btn.addEventListener('click', closePOCDetailModal);
    });

    // 点击模态框背景关闭
    const pocDetailModal = document.getElementById('poc-detail-modal');
    if (pocDetailModal) {
        pocDetailModal.addEventListener('click', (e) => {
            if (e.target === pocDetailModal) {
                closePOCDetailModal();
            }
        });
    }

    // 执行POC按钮
    const executePocBtn = document.getElementById('execute-poc-btn');
    if (executePocBtn) {
        executePocBtn.addEventListener('click', executePOC);
    }

    // 执行目标URL回车键触发执行
    const executeTargetUrl = document.getElementById('execute-target-url');
    if (executeTargetUrl) {
        executeTargetUrl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                executePOC();
            }
        });
    }
}

// ========================================
// 页面加载完成后初始化
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Web漏洞POC生成器已加载');
    console.log('📡 API端点:', API_ENDPOINT);

    // 初始化事件监听
    initializeEventListeners();

    // 检查API健康状态
    fetch(`${API_BASE_URL}/api/health`)
        .then(response => response.json())
        .then(data => {
            console.log('✅ API状态:', data);
        })
        .catch(error => {
            console.error('❌ API连接失败:', error);
            showToast('无法连接到后端API，请确保服务已启动', 'error');
        });
});

// ========================================
// 页面可见性变化检测
// ========================================

document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // 页面重新可见时，可以执行一些刷新操作
        console.log('页面重新激活');
    }
});

// ========================================
// 错误处理
// ========================================

window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的Promise拒绝:', event.reason);
});

// ========================================
// 导出给控制台使用的调试函数
// ========================================

window.pocGenerator = {
    generatePOC,
    showToast,
    downloadPOC,
    copyToClipboard,
    newPOC,
    EXAMPLES
};

console.log('💡 提示: 可以通过 window.pocGenerator 访问API函数');