# Web Vulnerability to POC Generator

基于大模型API的Web漏洞信息到POC代码生成系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-Educational-red.svg)](LICENSE)

## ⚠️ 重要声明

**本工具仅用于授权的安全测试和研究目的**

- ✅ 仅在获得明确授权的系统上使用
- ❌ 未经授权的测试可能违反法律
- 📋 使用者需对其行为负责
- 🎓 建议用于安全教育和CTF竞赛

---

## 目录

- [功能特性](#功能特性)
- [项目架构](#项目架构)
- [实现方法](#实现方法)
- [快速开始](#快速开始)
- [API文档](#api文档)
- [配置说明](#配置说明)
- [支持的漏洞类型](#支持的漏洞类型)
- [使用示例](#使用示例)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

---

## 功能特性

### 核心功能
- 🤖 **智能POC生成** - 基于大模型API自动分析漏洞并生成验证代码
- 🔍 **漏洞类型识别** - 自动识别SQL注入、XSS、CSRF、文件上传等Web漏洞
- 📦 **多格式输入** - 支持文字描述、CVE编号、HTTP数据包等多种输入
- 📝 **完整输出** - 返回POC代码、使用说明、风险提示和原始漏洞信息

### 技术特性
- ⚡ **高性能异步** - 基于FastAPI异步框架，支持高并发
- 🌐 **CORS支持** - 内置跨域支持，便于前端集成
- 📚 **自动文档** - Swagger UI + ReDoc双文档系统
- 🔧 **灵活配置** - 支持多种大模型API（OpenAI兼容接口）
- 📊 **详细日志** - 完整的请求日志和错误追踪

---

## 项目架构

### 目录结构

```
yanwutang_test1/
├── main.py                 # FastAPI应用入口，服务器启动
├── config.py               # 全局配置（API、大模型设置）
├── requirements.txt        # Python依赖包列表
├── README.md              # 项目文档
├── api_server.log         # 运行日志文件
│
├── api/                   # API层 - 路由和端点定义
│   ├── __init__.py
│   └── routes.py          # API路由（/generate-poc, /health）
│
├── models/                # 数据层 - Pydantic模型定义
│   ├── __init__.py
│   └── schemas.py         # 请求/响应数据模型
│
├── services/              # 业务层 - 核心业务逻辑
│   ├── __init__.py
│   └── llm_service.py     # 大模型API调用服务
│
└── frontend/              # 前端层 - Web用户界面
    ├── index.html         # 主页面（单页应用）
    ├── css/
    │   └── style.css      # 完整样式表（970行）
    └── js/
        └── app.js         # 交互逻辑（480行）
```

### 技术栈

#### 后端技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web框架 | FastAPI | 高性能异步框架 |
| HTTP服务器 | Uvicorn | ASGI服务器 |
| 数据验证 | Pydantic | 数据模型和验证 |
| LLM集成 | OpenAI SDK | 支持OpenAI兼容API |
| 日志记录 | Logging | Python标准日志库 |
| 静态文件 | StaticFiles | FastAPI静态文件服务 |

#### 前端技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 页面结构 | HTML5 | 语义化标签、现代Web标准 |
| 样式设计 | CSS3 | CSS变量、Grid、Flexbox、动画 |
| 交互逻辑 | Vanilla JavaScript | 原生ES6+，无框架依赖 |
| HTTP请求 | Fetch API | 现代异步请求接口 |
| 图标库 | Font Awesome 6.4 | 矢量图标（CDN） |
| 设计风格 | 暗色主题 | 现代化深色UI设计 |

---

## 实现方法

### 后端实现

后端采用FastAPI框架构建RESTful API，主要实现步骤：

1. **项目架构设计**：采用分层架构，将API路由、数据模型、业务逻辑分离
2. **API端点开发**：实现POC生成接口(`/api/generate-poc`)和健康检查接口(`/api/health`)
3. **大模型集成**：通过OpenAI SDK调用兼容的大模型API，使用精心设计的提示词引导模型生成安全的POC代码
4. **请求处理流程**：
   - 接收用户输入的漏洞信息和目标信息
   - 构造结构化的提示词发送给大模型
   - 解析大模型返回的JSON响应
   - 提取POC代码、漏洞类型、使用说明等信息
   - 返回格式化的响应给前端

### 前端实现

前端采用纯原生技术栈，无框架依赖，实现步骤：

1. **页面结构（HTML5）**：
   - 使用语义化标签构建清晰的文档结构
   - 分为导航栏、警告横幅、Hero区域、生成器主体、功能特性、页脚等模块
   - 输入输出分栏布局，左侧输入漏洞信息，右侧显示生成结果

2. **样式设计（CSS3）**：
   - 采用CSS自定义属性（CSS Variables）实现主题化
   - 暗色主题设计，使用渐变色和发光效果
   - Grid和Flexbox布局实现响应式设计
   - CSS动画实现加载状态、背景粒子效果、按钮交互等
   - 完全自适应移动端和桌面端

3. **交互逻辑（JavaScript）**：
   - 使用Fetch API调用后端RESTful接口
   - 实现状态管理：空状态、加载状态、结果展示状态
   - 快速示例按钮：预设SQL注入、XSS、文件上传、SSRF等示例
   - 代码操作：复制到剪贴板、下载为.py文件
   - Toast通知系统提供操作反馈
   - 平滑滚动和导航栏激活状态跟踪

4. **前后端集成**：
   - FastAPI通过`StaticFiles`中间件挂载前端静态资源
   - `/`根路径返回`index.html`
   - `/css`, `/js`, `/assets`分别挂载对应的静态文件目录
   - CORS中间件配置允许跨域访问

---

## 快速开始

### 环境要求

- Python 3.8 或更高版本
- pip 包管理器
- 有效的大模型API密钥（OpenAI或兼容服务）

### 1. 克隆项目（如适用）

```bash
cd yanwutang_test1
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

**依赖包说明：**
- `fastapi>=0.110.0` - Web框架
- `uvicorn[standard]>=0.27.0` - ASGI服务器
- `pydantic>=2.6.0` - 数据验证
- `openai>=1.0.0` - OpenAI SDK
- `python-dotenv>=1.0.0` - 环境变量管理

### 3. 配置API密钥

#### 方法1：修改 config.py（适用于开发环境）

编辑 `config.py` 文件，修改以下配置：

```python
LLM_API_KEY: str = "your-api-key-here"
LLM_API_BASE: str = "https://api.siliconflow.cn/v1"  # 或其他兼容服务
LLM_MODEL: str = "moonshotai/Kimi-K2-Instruct-0905"  # 或其他模型
```

#### 方法2：使用环境变量（推荐用于生产环境）

创建 `.env` 文件：

```bash
LLM_API_KEY=your-api-key-here
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

### 4. 启动服务

```bash
python main.py
```

**启动成功后，您将看到：**

```
⚠️  警告：本工具仅用于授权的安全测试和研究目的
    - 仅在获得明确授权的系统上使用
    - 未经授权的测试可能违反法律
    - 使用者需对其行为负责

🚀 启动服务器: http://127.0.0.1:8000
📚 API文档: http://127.0.0.1:8000/docs
```

### 5. 访问Web界面

在浏览器中打开：

- **Web界面（推荐）**: http://127.0.0.1:8000/
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### 6. 使用Web界面生成POC

#### 方式一：直接输入漏洞信息

1. 在"漏洞信息输入"文本框中输入漏洞描述，支持：
   - **漏洞描述**：例如"目标网站 http://example.com/login 存在SQL注入漏洞，位于username参数"
   - **CVE编号**：例如"CVE-2017-5638: Apache Struts2远程代码执行漏洞"
   - **HTTP数据包**：完整的请求包和响应信息

2. （可选）在"目标信息"输入框填写目标系统信息：例如"MySQL 5.7 - PHP 7.4"

3. 点击"生成POC代码"按钮，等待AI分析

4. 查看生成结果：
   - **漏洞类型标签**：自动识别的漏洞类型
   - **POC验证代码**：完整的Python验证代码
   - **使用说明**：代码说明和使用方法

5. 代码操作：
   - **复制代码**：点击"复制"按钮将代码复制到剪贴板
   - **下载POC**：点击"下载POC"按钮保存为.py文件
   - **新建POC**：点击"新建POC"清空表单开始新的生成

#### 方式二：使用快速示例

Web界面提供了4个预设示例，点击即可快速加载：

- **SQL注入**：MySQL时间盲注示例
- **XSS跨站**：反射型XSS示例
- **文件上传**：PHP后门上传示例
- **SSRF**：服务端请求伪造示例

#### Web界面特性

- ✅ **响应式设计**：支持桌面端和移动端访问
- ✅ **暗色主题**：护眼的现代化深色UI
- ✅ **实时反馈**：Toast通知提示操作结果
- ✅ **加载动画**：分步骤显示AI处理进度
- ✅ **代码高亮**：专业的代码显示格式
- ✅ **快捷键支持**：Ctrl+Enter提交表单

---

## API文档

### 1. 生成POC代码

**端点**: `POST /api/generate-poc`

**功能**: 根据漏洞信息生成POC验证代码

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vulnerability_info` | string | ✅ | 漏洞信息（描述/CVE/数据包） |
| `target_info` | string | ❌ | 目标系统信息 |

#### 请求示例1 - 漏洞描述

```json
{
  "vulnerability_info": "目标网站 http://example.com/login 存在SQL注入漏洞，位于登录页面的username参数，使用单引号可以触发数据库错误",
  "target_info": "Web应用 - MySQL数据库 - PHP后端"
}
```

#### 请求示例2 - HTTP数据包

```json
{
  "vulnerability_info": "POST /login HTTP/1.1\nHost: example.com\nContent-Type: application/x-www-form-urlencoded\n\nusername=admin'&password=123456\n\n响应：You have an error in your SQL syntax",
  "target_info": "MySQL 5.7"
}
```

#### 请求示例3 - CVE信息

```json
{
  "vulnerability_info": "CVE-2017-5638: Apache Struts2远程代码执行漏洞，版本2.3.5-2.3.31，可通过Content-Type头注入OGNL表达式",
  "target_info": "Apache Struts 2.3.28"
}
```

#### 响应参数

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功生成 |
| `vulnerability_type` | string | 识别的漏洞类型 |
| `original_vulnerability_info` | string | 原始漏洞信息 |
| `poc_code` | string | 生成的Python POC代码 |
| `explanation` | string | 代码说明和使用方法 |
| `error` | string | 错误信息（失败时） |
| `warning` | string | 安全警告 |

#### 响应示例

```json
{
  "success": true,
  "vulnerability_type": "SQL注入",
  "original_vulnerability_info": "目标网站 http://example.com/login 存在SQL注入漏洞...",
  "poc_code": "import requests\nimport time\n\n# POC验证代码 - SQL注入（时间盲注）\nurl = 'http://example.com/login'\n\n# 安全的验证payload\npayload = \"admin' AND SLEEP(3)--\"\ndata = {'username': payload, 'password': '123456'}\n\nstart_time = time.time()\nresponse = requests.post(url, data=data)\nend_time = time.time()\n\nif (end_time - start_time) >= 3:\n    print('[+] 漏洞存在：检测到SQL注入漏洞')\nelse:\n    print('[-] 漏洞不存在')",
  "explanation": "该POC用于验证SQL注入漏洞...",
  "error": null,
  "warning": "⚠️ 警告：本工具仅用于授权的安全测试和研究目的"
}
```

### 2. 健康检查

**端点**: `GET /api/health`

**功能**: 检查服务状态

#### 响应示例

```json
{
  "status": "healthy",
  "service": "Vulnerability to POC Generator",
  "version": "1.0.0"
}
```

---

## 配置说明

### config.py 配置项

在 `config.py` 中可以调整以下参数：

#### API服务配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `API_HOST` | `127.0.0.1` | 服务监听地址 |
| `API_PORT` | `8000` | 服务端口 |

#### 大模型配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | 环境变量或默认值 | API密钥 |
| `LLM_API_BASE` | `https://api.siliconflow.cn/v1` | API基础URL |
| `LLM_MODEL` | `moonshotai/Kimi-K2-Instruct-0905` | 使用的模型 |
| `LLM_TEMPERATURE` | `0.7` | 生成随机性（0-1） |
| `LLM_MAX_TOKENS` | `2000` | 最大生成长度 |

### 支持的大模型服务

本系统支持所有兼容OpenAI API格式的服务：

#### 国际服务
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude（需使用兼容层）
- **Google**: Gemini（需使用兼容层）

#### 国内服务
- **硅基流动**: Kimi, Qwen, DeepSeek等
- **通义千问**: qwen-turbo, qwen-plus
- **百度文心**: ERNIE系列
- **智谱AI**: GLM系列

#### 本地部署
- **Ollama**: 本地运行开源模型
- **LM Studio**: 本地模型服务
- **vLLM**: 高性能推理服务

---

## 支持的漏洞类型

### 注入类漏洞
- ✅ **SQL注入** - 数据库查询注入（Union注入、盲注、报错注入）
- ✅ **命令注入** - 系统命令执行（OS Command Injection）
- ✅ **LDAP注入** - LDAP查询注入
- ✅ **XPath注入** - XML路径语言注入
- ✅ **模板注入** (SSTI) - 服务端模板注入
- ✅ **NoSQL注入** - MongoDB等NoSQL数据库注入

### 跨站类漏洞
- ✅ **XSS** - 跨站脚本攻击
  - 反射型XSS
  - 存储型XSS
  - DOM型XSS
- ✅ **CSRF** - 跨站请求伪造

### 文件类漏洞
- ✅ **文件上传** - 任意文件上传漏洞
- ✅ **文件包含** - 本地/远程文件包含（LFI/RFI）
- ✅ **路径遍历** - 目录穿越（Path Traversal）
- ✅ **文件下载** - 任意文件读取

### 逻辑类漏洞
- ✅ **越权访问** - 水平/垂直越权（IDOR）
- ✅ **业务逻辑漏洞** - 支付绕过、优惠券滥用等
- ✅ **认证绕过** - 登录认证缺陷
- ✅ **会话管理** - Session固定、劫持

### 其他Web漏洞
- ✅ **SSRF** - 服务端请求伪造
- ✅ **XXE** - XML外部实体注入
- ✅ **反序列化** - 不安全的反序列化
- ✅ **JWT漏洞** - Token伪造/篡改
- ✅ **API漏洞** - REST/GraphQL API安全问题
- ✅ **CORS错误配置** - 跨域资源共享漏洞

---

## 使用示例

### Python调用示例

```python
import requests
import json

# API端点
url = "http://127.0.0.1:8000/api/generate-poc"

# 构建请求数据
payload = {
    "vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
    "target_info": "MySQL 5.7 - PHP 7.4"
}

# 发送POST请求
response = requests.post(url, json=payload)
result = response.json()

# 处理响应
if result["success"]:
    print("=" * 60)
    print(f"漏洞类型: {result['vulnerability_type']}")
    print("=" * 60)
    print("\nPOC代码:")
    print(result['poc_code'])
    print("\n" + "=" * 60)
    print("使用说明:")
    print(result['explanation'])
    print("=" * 60)
else:
    print(f"生成失败: {result['error']}")
```

### JavaScript/TypeScript 示例

```javascript
// Fetch API
async function generatePoc(vulnerabilityInfo, targetInfo = null) {
  const response = await fetch('http://127.0.0.1:8000/api/generate-poc', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      vulnerability_info: vulnerabilityInfo,
      target_info: targetInfo
    })
  });

  const result = await response.json();

  if (result.success) {
    console.log('漏洞类型:', result.vulnerability_type);
    console.log('POC代码:\n', result.poc_code);
    console.log('使用说明:', result.explanation);
  } else {
    console.error('生成失败:', result.error);
  }

  return result;
}

// 使用示例
generatePoc(
  "目标网站存在XSS漏洞，位于搜索框参数q",
  "http://example.com/search?q="
);
```

### cURL 示例

```bash
curl -X POST "http://127.0.0.1:8000/api/generate-poc" \
  -H "Content-Type: application/json" \
  -d '{
    "vulnerability_info": "目标网站存在SQL注入漏洞，位于登录页面的username参数",
    "target_info": "MySQL数据库"
  }'
```

---

## 开发指南

### 添加新功能

#### 1. 添加新的数据模型

编辑 `models/schemas.py`:

```python
class NewRequest(BaseModel):
    """新请求模型"""
    field1: str
    field2: Optional[int] = None
```

#### 2. 创建新服务

在 `services/` 目录创建新文件:

```python
class NewService:
    async def process(self, data):
        # 业务逻辑
        pass
```

#### 3. 添加新路由

编辑 `api/routes.py`:

```python
@router.post("/new-endpoint")
async def new_endpoint(request: NewRequest):
    # 调用服务
    result = await new_service.process(request)
    return result
```

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 创建测试文件 tests/test_api.py
# 运行测试
pytest tests/ -v
```

### 代码规范

- 使用 **Black** 格式化代码
- 使用 **flake8** 检查代码质量
- 使用 **mypy** 进行类型检查

```bash
pip install black flake8 mypy
black .
flake8 .
mypy .
```

---

## 常见问题

### Q1: API调用失败，提示认证错误

**A**: 检查以下几点：
1. API密钥是否正确配置在 `config.py`
2. API服务商是否支持所选模型
3. 检查网络连接和代理设置
4. 查看 `api_server.log` 了解详细错误

### Q2: 生成的POC代码不完整

**A**: 可能的原因：
1. `LLM_MAX_TOKENS` 设置过小，建议设置为 `2000` 或更高
2. 模型能力限制，建议使用更强大的模型（如GPT-4）
3. 漏洞信息描述不够清晰，请提供更详细的信息

### Q3: 如何修改服务器地址和端口？

**A**: 编辑 `config.py`:

```python
API_HOST: str = "0.0.0.0"  # 监听所有接口
API_PORT: int = 9000       # 修改为其他端口
```

### Q4: 支持哪些大模型？

**A**: 支持所有兼容 OpenAI API 格式的服务：
- OpenAI: GPT-4, GPT-3.5
- 硅基流动、通义千问、文心一言等国内服务
- Ollama、LM Studio等本地部署服务

只需修改 `LLM_API_BASE` 和 `LLM_MODEL` 即可。

### Q5: 如何保护API安全？

**A**: 建议添加以下安全措施：
1. **添加身份验证**: 使用JWT或API Key
2. **速率限制**: 使用 `slowapi` 限制请求频率
3. **CORS配置**: 在 `main.py` 中设置具体允许的域名
4. **HTTPS**: 使用反向代理（Nginx）配置SSL证书

---

## 安全建议

### 开发环境
- ✅ 使用测试数据和虚拟环境
- ✅ 不要在公网暴露开发服务器
- ✅ 定期更新依赖包

### 生产环境
- ✅ 配置防火墙和访问控制
- ✅ 使用HTTPS加密传输
- ✅ 实施用户认证和授权
- ✅ 添加请求频率限制
- ✅ 记录详细的审计日志
- ✅ 定期备份和安全审计

### API密钥管理
- ✅ 使用环境变量或密钥管理服务
- ❌ 不要将密钥硬编码在代码中
- ❌ 不要将 `.env` 文件提交到版本控制
- ✅ 定期轮换API密钥

---

## 贡献指南

欢迎提交Issue和Pull Request！

### 提交Issue
- 详细描述问题或建议
- 提供复现步骤和环境信息
- 附上相关日志和截图

### 提交PR
1. Fork本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 许可证

本项目仅供安全研究和教育用途。使用者需遵守相关法律法规。

**禁止用于：**
- 未经授权的安全测试
- 恶意攻击和破坏
- 其他非法用途

---

## 联系方式

如有问题或建议，请提交Issue或联系项目维护者。

---

## 更新日志

### v1.0.0 (2025-01-01)
- 🎉 首次发布
- ✨ 支持基于大模型的POC生成
- ✨ 支持多种Web漏洞类型
- ✨ 完整的API文档
- ✨ 详细的日志记录

---

**⚠️ 最后提醒：本工具仅用于授权的安全测试和研究目的，使用者需对其行为负责！**