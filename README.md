# AI-POC：智能Web漏洞POC生成与管理平台

基于大模型API的Web漏洞POC自动生成、管理和执行系统

补充文档索引见 [docs/README.md](./docs/README.md)

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

## 📑 目录

- [系统概述](#系统概述)
- [核心功能](#核心功能)
- [模块架构](#模块架构)
- [快速开始](#快速开始)
- [前端使用手册](#前端使用手册)
- [后端API文档](#后端api文档)
- [技术实现详解](#技术实现详解)
- [配置说明](#配置说明)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

---

## 🌟 系统概述

AI-POC是一个完整的Web漏洞POC管理平台，集成了**AI生成**、**库管理**、**多引擎执行**三大核心能力：

```
┌─────────────────────────────────────────────────────────┐
│                    AI-POC 平台                          │
├─────────────────────────────────────────────────────────┤
│  📝 POC生成器    │  📚 POC库管理    │  🔍 漏洞扫描    │
│  AI自动生成      │  搜索/执行/删除  │  目标验证       │
└─────────────────────────────────────────────────────────┘
           ↓                 ↓                 ↓
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ LLM API  │      │ SQLite DB│      │ Python   │
    │ 调用服务 │      │ + 文件存储│      │ Nuclei   │
    └──────────┘      └──────────┘      └──────────┘
```

### 解决的核心问题

1. **POC覆盖问题** ✅
   之前每次生成POC都会覆盖 `scan.py`，现在所有POC自动保存到数据库，每个POC有唯一ID，可随时调用

2. **工具兼容问题** ✅
   支持Python和Nuclei两种POC类型，采用混合执行引擎架构，可轻松扩展其他工具

3. **POC管理问题** ✅
   提供完整的POC库管理功能，支持搜索、筛选、执行、删除，可追踪POC使用历史

---

## 🎯 核心功能

### 1️⃣ 智能POC生成器

**功能**：输入漏洞信息，AI自动生成可执行的验证代码

**特点**：
- 🤖 基于大模型API（GPT-4/Kimi等）自动生成
- 📦 支持三种输入格式：漏洞描述、CVE编号、HTTP数据包
- 🎯 自动识别漏洞类型（SQL注入、XSS、RCE等50+种）
- ✅ 生成安全的验证型POC（非破坏性）
- 💾 **自动保存到POC库**（新增）

**对应文件**：
```
services/llm_service.py          # 核心生成逻辑
api/routes.py                    # /api/generate-poc 端点
models/schemas.py                # POCRequest/POCResponse 数据模型
```

### 2️⃣ POC库管理系统 ⭐ 新功能

**功能**：统一管理所有生成的POC，支持搜索、执行、删除

**特点**：
- 📚 自动保存每个生成的POC，无覆盖问题
- 🔍 多条件搜索：漏洞类型、POC类型、关键词
- ⚡ 快速执行：选择任意POC，输入目标URL即可验证
- 📊 统计分析：POC总数、分类统计、使用历史
- 🗑️ 灵活管理：查看详情、删除无用POC

**对应文件**：
```
services/poc_library_service.py  # POC库管理核心服务
services/nuclei_service.py       # Nuclei扫描与模板服务
api/routes.py                    # 7个POC库API端点
pocs/                            # POC存储目录
  ├── poc_library.db             # SQLite数据库
  ├── python/                    # Python POC文件
  └── nuclei/                    # Nuclei模板
```

### 3️⃣ 多引擎POC执行

**功能**：支持Python和Nuclei两种POC执行引擎

**特点**：
- 🐍 **Python引擎**：动态加载模块执行，支持复杂逻辑
- ⚡ **Nuclei引擎**：调用Nuclei命令执行YAML模板，高效扫描
- 🎯 **智能路由**：根据POC类型自动选择执行引擎
- 📈 **结果追踪**：记录成功/失败次数，计算成功率

**对应文件**：
```
services/poc_library_service.py  # execute_poc() 路由逻辑
services/nuclei_service.py       # Nuclei扫描与模板服务
```

---

## 🏗️ 模块架构

### 完整目录结构

```
AI-POC/
├── main.py                      # 🚀 应用入口
├── config.py                    # ⚙️ 全局配置
├── requirements.txt             # 📦 依赖列表
│
├── api/                         # 🌐 API层
│   └── routes.py                # 路由定义（17个端点）
│
├── models/                      # 📋 数据模型层
│   └── schemas.py               # Pydantic数据模型
│
├── services/                    # 💼 业务逻辑层
│   ├── llm_service.py           # AI生成服务
│   ├── poc_library_service.py  # POC库管理服务
│   └── nuclei_service.py        # Nuclei扫描与模板服务
│
├── pocs/                        # 💾 POC存储目录
│   ├── README.md                # POC库使用文档
│   ├── poc_library.db           # SQLite数据库
│   ├── python/                  # Python POC存储
│   ├── nuclei/                  # Nuclei模板存储
│   └── metadata/                # POC元数据
│
└── frontend/                    # 🎨 前端界面
    ├── index.html               # 主页面（482行）
    ├── css/
    │   └── style.css            # 完整样式（1880行）
    └── js/
        └── app.js               # 交互逻辑（1118行）
```

### 核心模块说明

#### 📌 main.py - 应用入口
```python
功能：启动FastAPI应用，配置中间件，挂载前端静态文件
关键代码：
- app = FastAPI()
- app.add_middleware(CORSMiddleware)  # 跨域支持
- app.mount("/", StaticFiles(...))    # 挂载前端
- uvicorn.run(app, host, port)        # 启动服务器
```

#### 📌 api/routes.py - API路由
```python
功能：定义所有API端点，处理HTTP请求
端点列表：
1. POST /api/generate-poc        # 生成POC
2. GET  /api/pocs/search         # 搜索POC
3. GET  /api/pocs/{id}           # 获取POC详情
4. POST /api/pocs/{id}/execute   # 执行POC
5. DELETE /api/pocs/{id}         # 删除POC
6. GET  /api/pocs/statistics     # 统计信息
7. GET  /api/pocs/vuln-types     # 漏洞类型列表
8. GET  /api/pocs/{id}/code      # 获取POC文件内容
9. POST /api/config/llm          # 更新LLM配置
10. GET /api/config/llm          # 获取LLM配置
11. GET /api/nuclei/status       # 检查Nuclei状态
12. GET /api/nuclei/folders      # 获取模板目录
13. GET /api/nuclei/templates    # 分页获取模板
14. GET /api/nuclei/template/content # 查看模板内容
15. POST /api/nuclei/scan        # 执行Nuclei扫描
16. POST /api/nuclei/scan/stream # 流式扫描
17. POST /api/nuclei/cache/clear # 清除模板缓存
```

#### 📌 services/llm_service.py - AI生成服务
```python
功能：调用大模型API生成POC代码
核心方法：
- generate_initial_poc()         # 生成Python POC或人工操作指南
- update_config()                # 动态更新LLM配置
- get_current_config()           # 获取当前配置摘要
- _call_llm_api()                # 调用LLM API
- _parse_llm_json_response()     # 解析JSON响应
```

#### 📌 services/poc_library_service.py - POC库管理
```python
功能：POC的CRUD操作和执行管理
核心方法：
- save_poc()                     # 保存POC到库
- search_pocs()                  # 搜索POC
- get_poc_by_id()                # 获取POC详情
- execute_poc()                  # 执行POC（路由到引擎）
- delete_poc()                   # 删除POC
- get_statistics()               # 获取统计信息
```

#### 📌 services/nuclei_service.py - Nuclei服务
```python
功能：管理Nuclei模板并执行扫描
核心方法：
- check_nuclei_available()       # 检查Nuclei状态
- get_templates_by_folder()      # 分页获取模板列表
- get_template_content()         # 查看模板内容
- scan_single()                  # 扫描单个模板
- scan_multiple()                # 扫描多个模板
- scan_folder()                  # 扫描整个目录
- scan_stream_async()            # 流式返回扫描结果
```

#### 📌 frontend/ - 前端界面
```javascript
功能：提供Web用户界面，调用后端API
文件说明：
- index.html：页面结构（标签页、表单、模态框）
- style.css：暗色主题样式（响应式设计）
- app.js：交互逻辑（事件监听、API调用、DOM操作）
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip 包管理器
- 大模型API密钥（OpenAI/Kimi/通义千问等）

### 安装步骤

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**依赖包清单**：
```
fastapi>=0.110.0           # Web框架
uvicorn[standard]>=0.27.0  # ASGI服务器
pydantic>=2.6.0            # 数据验证
openai>=1.0.0              # LLM API SDK
PyYAML>=6.0.1              # Nuclei模板解析
dnspython>=2.4.0           # 部分POC与DNS处理
```

#### 2. 配置API密钥

当前实现不是通过 `config.py` 配置 LLM 参数。`config.py` 只包含：

- `API_HOST`
- `API_PORT`
- `SECURITY_WARNING`

LLM 配置的实际来源是：

- 前端页面中的“API设置”
- `POST /api/config/llm` 接口
- 持久化文件 `pocs/llm_config.json`

**方式一：通过前端页面配置**（推荐）

- 打开首页
- 在“大模型API设置”区域填写 `API Key`、`模型ID`、`Base URL`
- 点击“保存设置”

**方式二：通过接口配置**

```bash
curl -X POST "http://127.0.0.1:8000/api/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-api-key",
    "model_id": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    "base_url": "https://api.siliconflow.cn/v1",
    "temperature": 1
  }'
```

#### 3. 启动服务

```bash
python main.py
```

**启动成功输出**：
```
⚠️  警告：本工具仅用于授权的安全测试和研究目的
🚀 启动服务器: http://127.0.0.1:8000
📚 API文档: http://127.0.0.1:8000/docs
```

#### 4. 访问界面

- **Web界面**: http://127.0.0.1:8000/
- **Swagger文档**: http://127.0.0.1:8000/docs
- **ReDoc文档**: http://127.0.0.1:8000/redoc

---

## 📱 前端使用手册

### 界面布局

前端采用**标签页设计**，顶部导航栏切换功能模块：

```
┌─────────────────────────────────────────────────────┐
│  🛡️ POC Generator     [生成POC] [POC库]  API文档   │
├─────────────────────────────────────────────────────┤
│  ⚠️ 本工具仅用于授权的安全测试和研究目的            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [当前标签页内容区域]                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 模块1：POC生成器

#### 使用场景
需要为某个漏洞生成验证POC代码

#### 操作步骤

**步骤1：输入漏洞信息**

左侧输入区域支持三种格式：

1. **漏洞描述**（推荐）
```
目标网站 http://example.com/login 存在SQL注入漏洞
漏洞位置：登录页面的username参数
触发方式：使用单引号(')可以触发数据库错误
数据库类型：MySQL
```

2. **CVE编号**
```
CVE-2017-5638: Apache Struts2远程代码执行漏洞
版本：2.3.5-2.3.31
触发方式：通过Content-Type头注入OGNL表达式
```

3. **HTTP数据包**
```
POST /login HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded

username=admin'&password=123456

响应：You have an error in your SQL syntax
```

**步骤2：填写目标信息**（可选）
```
MySQL 5.7 - PHP 7.4 - Apache 2.4
```

**步骤3：点击"生成POC代码"**

AI将进行三步处理：
```
[进行中] 第1步：生成初始POC
[等待中] 第2步：代码评审
[等待中] 第3步：重新生成
```

整个过程需要30-90秒，请耐心等待。

**步骤4：查看生成结果**

右侧会显示：
- 📋 **漏洞描述信息**：提取的漏洞摘要
- 🏷️ **漏洞类型标签**：SQL注入/XSS/RCE等
- 💻 **POC验证代码**：完整的Python代码
- 📖 **使用说明**：代码说明和运行方法

**步骤5：操作POC代码**

- **复制代码**：点击"复制"按钮，代码自动复制到剪贴板
- **下载POC**：保存为 `.py` 文件，文件名格式：`poc_SQL注入_2025-01-13.py`
- **新建POC**：清空表单，开始新的生成

#### 快速示例

点击预设示例按钮，快速加载常见漏洞：

```
[SQL注入]  [XSS跨站]  [文件上传]  [SSRF]
```

---

### 模块2：POC库管理 ⭐

#### 使用场景
管理所有生成的POC，搜索、执行、删除

#### 界面布局

```
┌─────────────────────────────────────────────────┐
│  📊 统计卡片                                    │
│  ┌─────┐  ┌─────┐  ┌─────┐                    │
│  │总数 │  │Python│  │Nuclei│                   │
│  │ 15  │  │  12  │  │  3   │                   │
│  └─────┘  └─────┘  └─────┘                    │
├─────────────────────────────────────────────────┤
│  🔍 搜索和筛选                                  │
│  [搜索框...]  [漏洞类型▼]  [POC类型▼]  [🔄]  │
├─────────────────────────────────────────────────┤
│  📚 POC列表                                     │
│  ┌───────────────────────────────────────┐    │
│  │ 🐍 #1  PYTHON   SQL注入POC            │    │
│  │ MySQL时间盲注漏洞验证       3天前      │    │
│  └───────────────────────────────────────┘    │
│  ┌───────────────────────────────────────┐    │
│  │ ⚡ #2  NUCLEI   XSS漏洞检测            │    │
│  │ 反射型XSS扫描模板           今天       │    │
│  └───────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

#### 操作步骤

**步骤1：切换到POC库标签**

点击顶部导航栏的"POC库"按钮

**步骤2：查看统计信息**

顶部自动显示：
- POC总数
- Python POC数量
- Nuclei POC数量

**步骤3：搜索POC**

三种筛选方式：

1. **关键词搜索**：输入后延迟500ms自动搜索
```
搜索框输入：mysql
↓ 500ms延迟
自动搜索并显示包含"mysql"的POC
```

2. **漏洞类型筛选**：下拉选择
```
[所有漏洞类型▼]
 - SQLI (SQL注入)
 - XSS (跨站脚本)
 - RCE (远程代码执行)
 - UPLOAD (文件上传)
 ...
```

3. **POC类型筛选**
```
[所有POC类型▼]
 - Python
 - Nuclei
```

**步骤4：查看POC详情**

点击任意POC项，弹出详情模态框：

```
┌─────────────────────────────────────┐
│  📄 POC详情                 [✖]    │
├─────────────────────────────────────┤
│  POC ID: 1                          │
│  漏洞类型: SQLI                     │
│  POC类型: PYTHON                    │
│  创建时间: 2025-01-13 14:30:22     │
│  成功次数: 5                        │
│  失败次数: 2                        │
│                                     │
│  📝 漏洞描述                        │
│  MySQL时间盲注漏洞，位于登录页面...│
│                                     │
│  ▶️ 执行POC                         │
│  [输入目标URL...] [执行按钮]       │
│                                     │
│  📊 执行结果：                      │
│  ✅ 执行成功                        │
│  [+] 漏洞存在：响应延迟3秒         │
├─────────────────────────────────────┤
│  [🗑️ 删除POC]  [关闭]              │
└─────────────────────────────────────┘
```

**步骤5：执行POC**

在详情模态框中：
1. 输入目标URL：`http://test.com`
2. 点击"执行"按钮
3. 等待执行结果（显示成功/失败及输出）

**支持快捷键**：在URL输入框按回车直接执行

**步骤6：删除POC**（可选）

点击"删除POC"按钮，确认后删除：
- 删除数据库记录
- 删除POC文件
- 自动刷新列表

---

### 模块3：漏洞扫描验证

#### 使用场景
快速验证目标URL是否存在已生成的POC对应的漏洞

#### 操作步骤

**步骤1：输入目标URL**

```
目标URL: http://192.168.1.100
        或 https://example.com:8080
```

URL会自动标准化为：`http(s)://x.x.x.x:port/`

**步骤2：开始扫描**

点击"开始扫描"按钮，显示扫描进度

**步骤3：查看结果**

```
┌─────────────────────────────────┐
│  📊 扫描结果                    │
├─────────────────────────────────┤
│  🛡️ 漏洞检测结果：存在漏洞     │
│  🔗 目标URL: http://test.com   │
│  ℹ️  判断依据: 响应延迟3秒     │
│  📋 详细信息: ...               │
└─────────────────────────────────┘
```

---

## 🌐 后端API文档

### API端点总览

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/api/generate-poc` | POST | 生成POC | AI生成+自动保存 |
| `/api/pocs/search` | GET | 搜索POC | 多条件筛选 |
| `/api/pocs/{id}` | GET | POC详情 | 返回数据库记录 |
| `/api/pocs/{id}/execute` | POST | 执行POC | 路由到对应引擎 |
| `/api/pocs/{id}` | DELETE | 删除POC | 删除文件+记录 |
| `/api/pocs/statistics` | GET | 统计信息 | POC数量统计 |
| `/api/pocs/vuln-types` | GET | 漏洞类型 | 所有类型列表 |
| `/api/pocs/{id}/code` | GET | 查看代码 | 读取POC文件内容 |
| `/api/config/llm` | POST/GET | LLM配置 | 更新或读取模型配置 |
| `/api/nuclei/status` | GET | Nuclei状态 | 可执行文件和模板统计 |
| `/api/nuclei/folders` | GET | 模板目录 | 目录与数量 |
| `/api/nuclei/templates` | GET | 模板列表 | 分页与搜索 |
| `/api/nuclei/template/content` | GET | 模板内容 | 读取YAML源码 |
| `/api/nuclei/scan` | POST | 执行扫描 | 同步Nuclei扫描 |
| `/api/nuclei/scan/stream` | POST | 流式扫描 | SSE返回扫描结果 |
| `/api/nuclei/cache/clear` | POST | 清缓存 | 强制重建模板缓存 |

---

### 1. 生成POC

**端点**: `POST /api/generate-poc`

**请求示例**：
```json
{
  "vulnerability_info": "目标网站 http://example.com/login 存在SQL注入漏洞，位于username参数",
  "target_info": "MySQL 5.7 - PHP 7.4"
}
```

**响应示例**：
```json
{
  "success": true,
  "vulnerability_type": "SQL注入",
  "original_vulnerability_info": "目标网站...",
  "poc_code": "import requests\nimport time\n\n# POC代码...",
  "explanation": "该POC用于验证SQL注入漏洞...",
  "verifiable": true,
  "manual_steps": null,
  "warning": "⚠️ 警告：本工具仅用于授权的安全测试"
}
```

**cURL示例**：
```bash
curl -X POST "http://127.0.0.1:8000/api/generate-poc" \
  -H "Content-Type: application/json" \
  -d '{
    "vulnerability_info": "SQL注入漏洞",
    "target_info": "MySQL 5.7"
  }'
```

---

### 2. 搜索POC

**端点**: `GET /api/pocs/search`

**参数**：
- `vuln_type` (可选): 漏洞类型 (sqli, xss, rce等)
- `poc_type` (可选): POC类型 (python, nuclei)
- `keyword` (可选): 关键词搜索
- `limit` (可选): 返回数量限制，默认50
- `offset` (可选): 偏移量，默认0

**请求示例**：
```bash
# 搜索所有SQL注入类型的Python POC
curl "http://127.0.0.1:8000/api/pocs/search?vuln_type=sqli&poc_type=python&limit=10"

# 关键词搜索
curl "http://127.0.0.1:8000/api/pocs/search?keyword=mysql"
```

**响应示例**：
```json
{
  "success": true,
  "pocs": [
    {
      "id": 1,
      "vuln_type": "sqli",
      "vuln_name": "MySQL时间盲注POC",
      "vuln_description": "针对MySQL数据库的时间盲注漏洞验证",
      "poc_type": "python",
      "poc_file_path": "pocs/python/sqli_20250113_a1b2c3.py",
      "create_time": "2025-01-13T14:30:22",
      "last_used": "2025-01-13T15:20:10",
      "tags": "mysql,time-based,blind-sqli",
      "verifiable": 1,
      "manual_steps": null,
      "explanation": "通过报错信息判断是否存在注入。"
    }
  ],
  "total": 1
}
```

---

### 3. 执行POC

**端点**: `POST /api/pocs/{poc_id}/execute`

**请求体**：
```json
{
  "target_url": "http://test.com"
}
```

**响应示例（成功）**：
```json
{
  "success": true,
  "poc_id": 1,
  "target_url": "http://test.com",
  "result": {
    "vulnerable": true,
    "reason": "检测到SQL错误回显",
    "details": "响应体中包含数据库报错关键字"
  }
}
```

**响应示例（失败）**：
```json
{
  "success": false,
  "error": "连接超时"
}
```

**cURL示例**：
```bash
curl -X POST "http://127.0.0.1:8000/api/pocs/1/execute" \
  -H "Content-Type: application/json" \
  -d '{"target_url": "http://test.com"}'
```

---

### 4. 获取统计信息

**端点**: `GET /api/pocs/statistics`

**响应示例**：
```json
{
  "success": true,
  "statistics": {
    "total_pocs": 61,
    "python_pocs": 52,
    "nuclei_pocs": 0,
    "recent_used": [
      {"id": 124, "name": "远程命令执行_20251203_053824", "last_used": "2025-12-02 21:38:35"},
      {"id": 112, "name": "任意文件写入_20251128_035640", "last_used": "2025-11-27 19:56:54"}
    ]
  }
}
```

---

## 🔬 技术实现详解

### 数据流程图

#### POC生成流程

```
用户输入漏洞信息
    ↓
前端: generatePOC()
    ↓
POST /api/generate-poc (SSE流式响应)
    ↓
后端: llm_service.generate_initial_poc()
    ↓
┌─────────────────────────────────────┐
│ 单步生成流程                        │
│ - 构造提示词                        │
│ - 调用LLM API                       │
│ - 解析JSON响应                      │
│ - 判断 verifiable / manual_steps    │
│ - 发送进度: {type: "status", step: 1}│
└─────────────────────────────────────┘
    ↓
自动保存到POC库
    ↓
poc_library_service.save_poc()
    ↓
┌─────────────────────────────────────┐
│ 1. 生成唯一文件名                   │
│    格式: {vuln_type}_{timestamp}_{hash}.py│
│    示例: sqli_20250113_a1b2c3.py   │
│                                     │
│ 2. 保存文件到 pocs/python/          │
│    或保存到 pocs/metadata/          │
│                                     │
│ 3. 插入数据库记录                   │
│    INSERT INTO poc_records (...)   │
└─────────────────────────────────────┘
    ↓
发送最终结果: {type: "result", data: {...}}
    ↓
前端提示“已保存到POC库”
```

#### POC执行流程

```
用户在POC库选择POC #1
    ↓
点击"执行"按钮，输入目标URL
    ↓
前端: executePOC()
    ↓
POST /api/pocs/1/execute
    ↓
后端: poc_library_service.execute_poc(1, target_url)
    ↓
┌─────────────────────────────────────┐
│ 1. 查询数据库获取POC信息            │
│    SELECT * FROM poc_records WHERE id=1│
│                                     │
│ 2. 根据poc_type路由到对应引擎      │
│    if poc_type == "python":        │
│       → _execute_python_poc()      │
│    elif poc_type == "nuclei":      │
│       → nuclei_service.scan_single()│
└─────────────────────────────────────┘
    ↓
[Python引擎执行路径]
    ↓
┌─────────────────────────────────────┐
│ _execute_python_poc()               │
│                                     │
│ 1. 读取POC文件内容                  │
│    with open(poc_file_path) as f   │
│                                     │
│ 2. 动态导入模块                     │
│    spec = importlib.util.spec_from_file_location()│
│    module = importlib.util.module_from_spec()│
│                                     │
│ 3. 执行POC函数                      │
│    result = module.scan(target_url)  │
└─────────────────────────────────────┘
    ↓
[Nuclei引擎执行路径]
    ↓
┌─────────────────────────────────────┐
│ nuclei_service.scan_single()        │
│                                     │
│ 1. 检查nuclei.exe是否可用           │
│    check_nuclei_available()         │
│                                     │
│ 2. 执行nuclei命令                   │
│    nuclei.exe -u target -jsonl -silent -t template│
│                                     │
│ 3. 解析JSON输出                     │
│    for line in stdout.splitlines():│
│       data = json.loads(line)      │
│       findings.append(format(data))│
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 更新数据库字段                      │
│ UPDATE last_used = CURRENT_TIMESTAMP│
└─────────────────────────────────────┘
    ↓
返回执行结果
    ↓
前端显示结果 + Toast提示
```

---

### 数据库设计

**表名**: `poc_records`

```sql
CREATE TABLE poc_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vuln_type TEXT NOT NULL,              -- 漏洞类型 (sqli, xss, rce等)
    vuln_name TEXT NOT NULL,              -- POC名称
    vuln_description TEXT,                -- 漏洞描述
    poc_type TEXT DEFAULT 'python',       -- POC类型 (python/nuclei)
    poc_file_path TEXT NOT NULL,          -- POC文件路径
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,                  -- 最后使用时间
    tags TEXT,                            -- 标签（逗号分隔字符串）
    metadata TEXT,                        -- 元数据（JSON对象）
    verifiable BOOLEAN DEFAULT 1,         -- 是否可自动化验证
    manual_steps TEXT,                    -- 人工操作指南（JSON）
    explanation TEXT                      -- 说明信息
);

-- 索引
CREATE INDEX idx_vuln_type ON poc_records(vuln_type);
CREATE INDEX idx_poc_type ON poc_records(poc_type);
CREATE INDEX idx_create_time ON poc_records(create_time DESC);
```

**字段说明**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `id` | INTEGER | 主键，自增 | 1 |
| `vuln_type` | TEXT | 漏洞类型标识 | sqli, xss, rce |
| `vuln_name` | TEXT | POC显示名称 | MySQL时间盲注POC |
| `vuln_description` | TEXT | 详细描述 | 针对MySQL数据库... |
| `poc_type` | TEXT | POC类型 | python, nuclei |
| `poc_file_path` | TEXT | 文件相对路径 | pocs/python/sqli_xxx.py |
| `create_time` | TIMESTAMP | 创建时间 | 2025-01-13 14:30:22 |
| `last_used` | TIMESTAMP | 最后使用时间 | 2025-01-13 15:20:10 |
| `tags` | TEXT | 逗号分隔标签 | mysql,blind |
| `metadata` | TEXT | 扩展元数据JSON | {"author": "AI"} |
| `verifiable` | BOOLEAN | 是否可自动化验证 | 1 |
| `manual_steps` | TEXT | 人工操作指南JSON | {"steps":[...]} |
| `explanation` | TEXT | 说明信息 | 通过错误回显验证 |

---

### 文件存储策略

#### 文件命名规则

```python
# 格式：{漏洞类型}_{时间戳}_{内容哈希}.{扩展名}
# 示例：sqli_20250113_143022_a1b2c3.py

def generate_filename(vuln_type: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.md5(content.encode()).hexdigest()[:6]
    return f"{vuln_type}_{timestamp}_{hash_suffix}.py"
```

**命名优势**：
- ✅ 时间戳保证时序性
- ✅ 哈希值防止重复
- ✅ 漏洞类型前缀便于分类
- ✅ 文件名可读性高

#### 目录结构

```
pocs/
├── poc_library.db              # SQLite数据库
├── python/                     # Python POC
│   ├── sqli_20250113_a1b2c3.py
│   ├── xss_20250113_d4e5f6.py
│   └── rce_20250114_g7h8i9.py
├── nuclei/                     # Nuclei模板
│   ├── sqli_20250113_j1k2l3.yaml
│   └── xss_20250114_m4n5o6.yaml
└── metadata/                   # 元数据（可选）
    └── poc_1_metadata.json
```

---

### 混合执行引擎架构

**路由逻辑** (`poc_library_service.py:execute_poc()`):

```python
def execute_poc(self, poc_id: int, target_url: str) -> Dict:
    # 1. 查询POC信息
    poc = self.get_poc_by_id(poc_id)

    # 2. 根据类型路由到对应引擎
    if poc["poc_type"] == "python":
        result = self._execute_python_poc(
            poc["poc_file_path"],
            target_url
        )
    elif poc["poc_type"] == "nuclei":
        result = nuclei_service.scan_single(
            target_url,
            poc["poc_file_path"]
        )
    else:
        raise ValueError(f"不支持的POC类型: {poc['poc_type']}")

    # 3. 更新统计信息
    self._update_poc_stats(poc_id, result["success"])

    return result
```

**Python引擎**：动态模块加载

```python
def _execute_python_poc(self, poc_file: str, target_url: str) -> Dict:
    # 动态导入POC模块
    spec = importlib.util.spec_from_file_location("poc_module", poc_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 执行验证函数
    if hasattr(module, "verify"):
        result = module.verify(target_url)
        return {"success": True, "output": result}
    else:
        return {"success": False, "error": "POC缺少verify函数"}
```

**Nuclei服务**：命令行调用

```python
def scan_single(self, target_url: str, template_path: str, timeout: int = 60) -> Dict:
    full_path = self.templates_dir / Path(template_path)
    return self._execute_scan(target_url, [str(full_path)], timeout)
```

---

### 前端技术实现

#### 标签页切换

```javascript
function switchTab(tabName) {
    const generatorSection = document.querySelector('.generator-section');
    const librarySection = document.querySelector('.library-section');

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
```

#### 延迟搜索（防抖）

```javascript
let searchTimeout;
searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadPOCLibrary();  // 500ms后才执行
    }, 500);
});
```

**优势**：
- 减少不必要的API请求
- 提升用户体验（不会频繁刷新）
- 降低服务器负载

#### 相对时间显示

```javascript
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const days = Math.floor((now - date) / (1000 * 60 * 60 * 24));

    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (days < 30) return `${Math.floor(days / 7)}周前`;
    if (days < 365) return `${Math.floor(days / 30)}个月前`;
    return `${Math.floor(days / 365)}年前`;
}
```

**示例**：
- `2025-01-13 14:30:22` → "今天"
- `2025-01-10 10:00:00` → "3天前"
- `2024-12-20 08:00:00` → "3周前"

#### 动态POC列表渲染

```javascript
function renderPOCList(pocs) {
    const listContainer = document.getElementById('poc-list');
    listContainer.innerHTML = '';  // 清空现有内容

    pocs.forEach(poc => {
        const pocItem = document.createElement('div');
        pocItem.className = 'poc-item';
        pocItem.onclick = () => showPOCDetail(poc.id);

        pocItem.innerHTML = `
            <div class="poc-icon">
                <i class="fas fa-${poc.poc_type === 'nuclei' ? 'bolt' : 'python'}"></i>
            </div>
            <div class="poc-info">
                <div class="poc-header">
                    <span class="poc-id">#${poc.id}</span>
                    <span class="poc-type-badge ${poc.poc_type}">
                        ${poc.poc_type.toUpperCase()}
                    </span>
                </div>
                <div class="poc-name">${poc.vuln_name || `POC-${poc.id}`}</div>
                <div class="poc-description">
                    ${poc.vuln_description || '暂无描述'}
                </div>
            </div>
            <div class="poc-stats">
                <i class="fas fa-clock"></i>
                <span>${formatDate(poc.create_time)}</span>
            </div>
        `;

        listContainer.appendChild(pocItem);
    });
}
```

---

## ⚙️ 配置说明

### config.py 配置项

```python
class Settings:
    API_HOST: str = "127.0.0.1"           # 监听地址
    API_PORT: int = 8000                  # 监听端口
    SECURITY_WARNING: str = "..."         # 安全提示文案
```

### LLM 配置来源

当前版本的 LLM 配置不在 `config.py` 中维护，而是通过以下方式生效：

- 前端首页中的“API设置”
- `POST /api/config/llm` 接口
- 本地持久化文件 `pocs/llm_config.json`

运行时使用的关键参数包括：

- `api_key`
- `model_id`
- `base_url`
- `temperature`
- `max_tokens`

### 支持的大模型服务

| 服务商 | API Base | 模型示例 |
|--------|----------|----------|
| **OpenAI** | `https://api.openai.com/v1` | gpt-4, gpt-3.5-turbo |
| **硅基流动** | `https://api.siliconflow.cn/v1` | Kimi, Qwen, DeepSeek |
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-turbo, qwen-plus |
| **智谱AI** | `https://open.bigmodel.cn/api/paas/v4` | glm-4, glm-3-turbo |
| **Ollama** | `http://localhost:11434/v1` | llama2, mistral, codellama |

**配置示例**：

```json
{
  "api_key": "your-api-key",
  "model_id": "gpt-4",
  "base_url": "https://api.openai.com/v1",
  "temperature": 0.7
}

{
  "api_key": "your-api-key",
  "model_id": "moonshotai/Kimi-K2-Instruct-0905",
  "base_url": "https://api.siliconflow.cn/v1",
  "temperature": 0.7
}

{
  "api_key": "ollama",
  "model_id": "llama2",
  "base_url": "http://localhost:11434/v1",
  "temperature": 0.7
}
```

---

## 🛠️ 开发指南

### 添加新的POC引擎

假设要添加对Xray的支持：

**步骤1：创建引擎类** (`services/xray_engine.py`)

```python
class XrayEngine:
    def __init__(self):
        self.xray_path = self._find_xray_executable()

    def execute(self, poc_file: str, target_url: str) -> Dict:
        """执行Xray POC"""
        cmd = [self.xray_path, "webscan", "--poc", poc_file, "--url", target_url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return self._parse_output(result.stdout)
```

**步骤2：在POC库服务中注册** (`services/poc_library_service.py`)

```python
from services.xray_engine import XrayEngine

class POCLibraryService:
    def __init__(self):
        self.xray_engine = XrayEngine()  # 添加Xray引擎

    def execute_poc(self, poc_id: int, target_url: str) -> Dict:
        poc = self.get_poc_by_id(poc_id)

        if poc["poc_type"] == "python":
            return self._execute_python_poc(...)
        elif poc["poc_type"] == "nuclei":
            return nuclei_service.scan_single(target_url, poc["poc_file_path"])
        elif poc["poc_type"] == "xray":  # 添加xray路由
            return self.xray_engine.execute(...)
```

**步骤3：更新前端筛选选项** (`frontend/index.html`)

```html
<select id="filter-poc-type" class="filter-select">
    <option value="">所有POC类型</option>
    <option value="python">Python</option>
    <option value="nuclei">Nuclei</option>
    <option value="xray">Xray</option>  <!-- 添加选项 -->
</select>
```

---

## ❓ 常见问题

### Q1: 为什么POC库初始化失败？

**错误信息**：`Permission denied: 'pocs/poc_library.db'`

**原因**：`pocs/` 目录没有写权限

**解决方案**：
```bash
# Linux/Mac
chmod -R 755 pocs/

# Windows
# 右键 pocs 文件夹 → 属性 → 安全 → 编辑权限
```

---

### Q2: Nuclei POC执行失败

**错误信息**：`nuclei: command not found`

**原因**：当前实现默认从项目根目录读取 `nuclei.exe`

**解决方案**：
```bash
# Windows
# 1. 下载 nuclei 预编译版本
# 2. 将 nuclei.exe 放到项目根目录
# 3. 重新访问 /api/nuclei/status 检查状态
```

---

### Q3: LLM API调用超时

**错误信息**：`Timeout waiting for LLM response`

**原因**：网络延迟、API Key 无效、模型响应慢，或 Base URL/模型ID 配置错误

**解决方案**：
- 检查前端页面中的 `API Key`、`模型ID`、`Base URL`
- 调用 `GET /api/config/llm` 确认当前配置是否已生效
- 必要时重新通过 `POST /api/config/llm` 更新配置

---

### Q4: 数据库锁定错误

**错误信息**：`database is locked`

**原因**：多个进程同时访问SQLite数据库

**解决方案**：
1. 确保只运行一个服务器实例
2. 使用连接池：
```python
# services/poc_library_service.py
conn = sqlite3.connect(self.db_path, check_same_thread=False)
```

---

### Q5: 前端显示"无法连接到后端API"

**排查步骤**：

1. **检查服务器是否启动**
```bash
curl http://127.0.0.1:8000/api/pocs/statistics
```

2. **检查CORS配置**
```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. **检查防火墙**
```bash
# Linux
sudo ufw allow 8000

# Windows
# 控制面板 → 防火墙 → 高级设置 → 入站规则 → 新建规则 → 端口8000
```

---

## 📊 性能优化建议

### 数据库优化

```sql
-- 创建索引加速查询
CREATE INDEX idx_vuln_type ON poc_records(vuln_type);
CREATE INDEX idx_poc_type ON poc_records(poc_type);
CREATE INDEX idx_create_time ON poc_records(create_time DESC);

-- 定期清理旧POC
DELETE FROM poc_records
WHERE create_time < date('now', '-90 days')
AND last_used IS NULL;
```

### 前端优化

```javascript
// 使用虚拟滚动加载大量POC
function renderPOCList(pocs) {
    // 只渲染可见区域的POC
    const visiblePOCs = pocs.slice(0, 50);
    // ...
}

// 缓存API响应
const pocCache = new Map();
async function getPOCDetail(pocId) {
    if (pocCache.has(pocId)) {
        return pocCache.get(pocId);
    }
    const data = await fetch(`/api/pocs/${pocId}`);
    pocCache.set(pocId, data);
    return data;
}
```

---

## 🔒 安全建议

### 生产环境部署

1. **限制配置文件权限**
`pocs/llm_config.json` 当前会持久化 LLM 配置，部署时应限制该文件的读写权限，避免敏感信息泄露。

2. **添加认证中间件**
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.post("/api/generate-poc")
async def generate_poc(
    request: POCRequest,
    token: str = Depends(security)
):
    verify_token(token)  # 验证JWT token
    # ...
```

3. **使用HTTPS**
```nginx
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

4. **限流保护**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/generate-poc")
@limiter.limit("10/minute")  # 每分钟最多10次
async def generate_poc(request: POCRequest):
    # ...
```

---

## 📄 许可证

本项目仅供安全研究和教育用途。使用者需遵守相关法律法规。

**禁止用于**：
- ❌ 未经授权的安全测试
- ❌ 恶意攻击和破坏
- ❌ 其他非法用途

---

## 🙏 致谢

- FastAPI - 高性能Web框架
- OpenAI - 大模型API
- Nuclei - 漏洞扫描引擎
- Font Awesome - 图标库

---

## 📮 联系方式

如有问题或建议，请提交Issue。

---

**⚠️ 最后提醒：本工具仅用于授权的安全测试和研究目的，使用者需对其行为负责！**
