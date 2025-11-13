// ========================================
// 全局变量和配置
// ========================================

const API_BASE_URL = 'http://127.0.0.1:8000';
const API_ENDPOINT = `${API_BASE_URL}/api/generate-poc`;
const SCAN_ENDPOINT = `${API_BASE_URL}/api/scan`;

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

    // 扫描功能元素
    targetUrl: document.getElementById('target-url'),
    scanBtn: document.getElementById('scan-btn'),
    scanResultSection: document.getElementById('scan-result-section'),
    scanningState: document.getElementById('scanning-state'),
    scanResultContent: document.getElementById('scan-result-content'),
    vulnStatusCard: document.getElementById('vuln-status-card'),
    vulnStatus: document.getElementById('vuln-status'),
    scannedUrl: document.getElementById('scanned-url'),
    scanReason: document.getElementById('scan-reason'),
    scanDetailsBlock: document.getElementById('scan-details-block'),
    scanDetails: document.getElementById('scan-details'),

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

    // 设置漏洞描述信息
    elements.vulnDescription.textContent = data.original_vulnerability_info || '无漏洞描述信息';

    // 设置漏洞类型
    elements.vulnType.textContent = data.vulnerability_type || '未知类型';

    // 设置POC代码
    elements.pocCode.textContent = data.poc_code || '// 无代码生成';

    // 设置说明
    elements.explanationContent.textContent = data.explanation || '无说明信息';

    // 不自动滚动，让用户自然往下看
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

    // 重置扫描结果显示
    elements.targetUrl.value = '';
    elements.scanResultSection.style.display = 'none';

    elements.vulnerabilityInfo.focus();
    showToast('已重置，可以输入新的漏洞信息', 'success');
}

// ========================================
// 扫描功能
// ========================================

/**
 * 显示扫描中状态
 */
function showScanning() {
    elements.scanResultSection.style.display = 'block';
    elements.scanningState.style.display = 'block';
    elements.scanResultContent.style.display = 'none';
    elements.scanBtn.disabled = true;
    elements.scanBtn.innerHTML = `
        <i class="fas fa-spinner fa-spin"></i>
        <span>扫描中...</span>
    `;
}

/**
 * 隐藏扫描中状态
 */
function hideScanning() {
    elements.scanningState.style.display = 'none';
    elements.scanBtn.disabled = false;
    elements.scanBtn.innerHTML = `
        <i class="fas fa-search"></i>
        <span>开始扫描</span>
    `;
}

/**
 * 显示扫描结果
 */
function showScanResult(result) {
    elements.scanResultContent.style.display = 'block';

    // 设置漏洞状态
    const vulnerable = result.vulnerable;
    const statusCard = elements.vulnStatusCard;
    const statusValue = elements.vulnStatus;

    if (vulnerable) {
        statusCard.classList.add('vulnerable');
        statusCard.classList.remove('safe');
        statusValue.textContent = '存在漏洞';
        statusValue.style.color = '#ef4444';
    } else {
        statusCard.classList.add('safe');
        statusCard.classList.remove('vulnerable');
        statusValue.textContent = '未发现漏洞';
        statusValue.style.color = '#10b981';
    }

    // 设置目标URL
    elements.scannedUrl.textContent = result.target_url || '-';

    // 设置判断依据
    elements.scanReason.textContent = result.reason || '未提供判断原因';

    // 设置详细信息
    if (result.details && result.details.trim()) {
        elements.scanDetailsBlock.style.display = 'block';
        elements.scanDetails.textContent = result.details;
    } else {
        elements.scanDetailsBlock.style.display = 'none';
    }

    // 不自动滚动，让用户自然查看结果
}

/**
 * 执行扫描
 */
async function executeScan() {
    const targetUrl = elements.targetUrl.value.trim();

    // 验证输入
    if (!targetUrl) {
        showToast('请输入目标URL', 'warning');
        elements.targetUrl.focus();
        return;
    }

    // 显示扫描中状态
    showScanning();

    try {
        // 调用扫描API（不再需要scan_id）
        const response = await fetch(SCAN_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                target_url: targetUrl
            })
        });

        // 解析响应
        const data = await response.json();

        // 隐藏扫描中状态
        hideScanning();

        // 处理结果
        if (data.success) {
            showScanResult(data);
            showToast('扫描完成', 'success');
        } else {
            showToast(data.error || '扫描失败', 'error');
            // 仍然显示结果（包含错误信息）
            showScanResult({
                vulnerable: false,
                target_url: targetUrl,
                reason: data.reason || '扫描失败',
                details: data.error || ''
            });
        }

    } catch (error) {
        hideScanning();
        console.error('扫描API调用失败:', error);
        showToast(`网络错误: ${error.message}`, 'error');
    }
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
                                // 标记所有步骤为完成
                                updateProgressStep(3, 'completed', '已完成');
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

    // 扫描按钮点击事件
    elements.scanBtn.addEventListener('click', executeScan);

    // URL输入框回车键触发扫描
    elements.targetUrl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !elements.scanBtn.disabled) {
            executeScan();
        }
    });
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