# POC库管理系统

## 目录结构

```
pocs/
├── poc_library.db      # SQLite数据库（自动创建）
├── python/             # Python POC脚本存储目录
├── nuclei/             # Nuclei模板存储目录
└── metadata/           # POC元数据存储目录
```

## 功能特性

### 1. 多POC管理
- 每次生成的POC会自动保存到库中，不再覆盖
- 支持Python和Nuclei两种POC类型
- 每个POC都有唯一ID和详细的元数据

### 2. POC搜索
- 按漏洞类型搜索（sqli, xss, rce等）
- 按POC类型过滤（python/nuclei）
- 关键词搜索
- 标签过滤

### 3. POC执行
- 支持根据ID执行任意POC
- 自动路由到对应的执行引擎（Python/Nuclei）
- 记录执行历史和成功率

### 4. 统计分析
- POC总数和类型分布
- 最近使用的POC
- 成功率最高的POC
- 漏洞类型统计

## API接口

### POC库管理API

#### 1. 搜索POC
```http
GET /api/pocs/search?vuln_type=sqli&poc_type=python&keyword=mysql&limit=20
```

#### 2. 获取POC详情
```http
GET /api/pocs/{poc_id}
```

#### 3. 执行指定POC
```http
POST /api/pocs/{poc_id}/execute
Content-Type: application/json

{
    "target_url": "http://example.com"
}
```

#### 4. 删除POC
```http
DELETE /api/pocs/{poc_id}
```

#### 5. 获取统计信息
```http
GET /api/pocs/statistics
```

#### 6. 获取所有漏洞类型
```http
GET /api/pocs/vuln-types
```

## 使用示例

### 1. 生成并自动保存POC

```bash
# 生成POC（会自动保存到库）
curl -X POST http://localhost:8000/api/generate-poc \
  -H "Content-Type: application/json" \
  -d '{"vulnerability_info": "SQL注入漏洞"}'
```

### 2. 搜索POC

```bash
# 搜索所有SQL注入类型的POC
curl "http://localhost:8000/api/pocs/search?vuln_type=sqli"
```

### 3. 执行POC

```bash
# 执行ID为1的POC
curl -X POST http://localhost:8000/api/pocs/1/execute \
  -H "Content-Type: application/json" \
  -d '{"target_url": "http://test.com"}'
```

## 数据库Schema

```sql
CREATE TABLE poc_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vuln_type TEXT NOT NULL,              -- 漏洞类型
    vuln_name TEXT NOT NULL,              -- POC名称
    vuln_description TEXT,                -- 漏洞描述
    poc_type TEXT DEFAULT 'python',       -- POC类型
    poc_file_path TEXT NOT NULL,          -- POC文件路径
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,                  -- 最后使用时间
    success_count INTEGER DEFAULT 0,      -- 成功次数
    fail_count INTEGER DEFAULT 0,         -- 失败次数
    tags TEXT,                            -- 标签
    metadata TEXT                         -- 元数据（JSON）
);
```

## 注意事项

1. **文件命名规则**: POC文件名格式为 `{漏洞类型}_{时间戳}_{哈希}.py`
2. **数据库位置**: `pocs/poc_library.db`
3. **文件清理**: 删除POC记录时会同时删除对应的文件
4. **Nuclei支持**: 需要先安装Nuclei（https://github.com/projectdiscovery/nuclei）

## Nuclei集成

### 安装Nuclei

```bash
# Linux/Mac
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Windows
# 下载预编译版本：https://github.com/projectdiscovery/nuclei/releases
```

### 使用Nuclei模板

系统会自动检测Nuclei是否安装，如果安装了Nuclei，可以导入和执行Nuclei模板。

## 开发说明

### 核心服务文件

- `services/poc_library_service.py` - POC库管理核心服务
- `services/nuclei_engine.py` - Nuclei执行引擎
- `api/routes.py` - API路由定义

### 扩展POC类型

要添加新的POC类型（如Xray），需要：

1. 在`poc_library_service.py`中添加新的执行引擎方法
2. 在`execute_poc`方法中添加类型路由
3. 更新`save_poc`方法支持新类型的文件保存

## 问题排查

### 问题1：POC库初始化失败

**解决**: 确保`pocs`目录有写权限

### 问题2：Nuclei执行失败

**解决**:
1. 检查Nuclei是否安装：`nuclei -version`
2. 确保Nuclei在系统PATH中

### 问题3：数据库锁定

**解决**: 检查是否有多个进程同时访问数据库