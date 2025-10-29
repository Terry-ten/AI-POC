# AI 生成 PoC 自动化验证方案

## 核心问题

你的实际场景是：
1. 发送漏洞信息给 AI（URL + 漏洞描述）
2. AI 返回验证脚本（PoC/Exploit）
3. **无法在真实环境运行该脚本**
4. 需要验证 AI 生成的脚本是否真的能检测/利用该漏洞

## 解决方案架构

```
AI 生成的 PoC → 自动化测试系统 → 验证结果
                      ↓
      [一键式多漏洞类型靶场 + 智能适配]
```

### 核心思路

**一个通用的 Docker 容器 + 动态漏洞注入 = 测试所有类型的 Web 漏洞**

不需要为每种漏洞单独搭环境，而是：
- 一个基础 Web 服务容器
- 根据漏洞类型动态生成存在该漏洞的端点
- 自动修改 AI 脚本的目标地址
- 运行并验证结果

## 详细设计

### 1. 通用漏洞靶场容器

#### Docker 镜像设计

```dockerfile
# Dockerfile - 通用 Web 漏洞靶场
FROM python:3.11-slim

# 安装必要工具
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install flask flask-cors requests beautifulsoup4 lxml

# 创建工作目录
WORKDIR /app

# 复制靶场服务器代码
COPY vulnerable_app.py /app/
COPY requirements.txt /app/

# 暴露端口
EXPOSE 5000

# 启动服务
CMD ["python", "vulnerable_app.py"]
```

#### 动态漏洞端点生成器

```python
# vulnerable_app.py - 动态生成存在漏洞的端点
from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os
import subprocess

app = Flask(__name__)

# ============= SQL 注入漏洞端点 =============
@app.route('/vuln/sqli/login', methods=['GET', 'POST'])
def sqli_login():
    """存在 SQL 注入的登录端点"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # 故意的 SQL 注入漏洞
        conn = sqlite3.connect(':memory:')
        c = conn.cursor()
        c.execute("CREATE TABLE users (username TEXT, password TEXT)")
        c.execute("INSERT INTO users VALUES ('admin', 'admin123')")

        # 不安全的查询
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        try:
            result = c.execute(query).fetchall()
            conn.close()

            if result:
                return jsonify({"success": True, "message": "Login successful", "user": result[0][0]})
            else:
                return jsonify({"success": False, "message": "Invalid credentials"})
        except Exception as e:
            return jsonify({"error": str(e), "vulnerable": True})

    return '''
    <form method="post">
        Username: <input name="username"><br>
        Password: <input name="password"><br>
        <input type="submit">
    </form>
    '''

@app.route('/vuln/sqli/search', methods=['GET'])
def sqli_search():
    """存在 SQL 注入的搜索端点"""
    keyword = request.args.get('q', '')

    conn = sqlite3.connect(':memory:')
    c = conn.cursor()
    c.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    c.execute("INSERT INTO products VALUES (1, 'Laptop', 999.99)")
    c.execute("INSERT INTO products VALUES (2, 'Mouse', 29.99)")

    # 故意的 SQL 注入
    query = f"SELECT * FROM products WHERE name LIKE '%{keyword}%'"
    try:
        results = c.execute(query).fetchall()
        conn.close()
        return jsonify({"results": results, "query": query})
    except Exception as e:
        return jsonify({"error": str(e), "query": query, "vulnerable": True})

# ============= XSS 漏洞端点 =============
@app.route('/vuln/xss/reflect', methods=['GET'])
def xss_reflect():
    """反射型 XSS"""
    name = request.args.get('name', 'Guest')
    # 直接输出用户输入，不转义
    return f"<h1>Hello, {name}!</h1>"

@app.route('/vuln/xss/stored', methods=['GET', 'POST'])
def xss_stored():
    """存储型 XSS"""
    if request.method == 'POST':
        comment = request.form.get('comment', '')
        # 存储到内存（生产环境会存数据库）
        if not hasattr(app, 'comments'):
            app.comments = []
        app.comments.append(comment)
        return jsonify({"success": True, "message": "Comment posted"})

    # 显示评论，不转义
    if not hasattr(app, 'comments'):
        app.comments = []

    html = "<h1>Comments</h1>"
    for comment in app.comments:
        html += f"<p>{comment}</p>"

    html += '''
    <form method="post">
        <textarea name="comment"></textarea>
        <input type="submit">
    </form>
    '''
    return html

@app.route('/vuln/xss/dom', methods=['GET'])
def xss_dom():
    """DOM 型 XSS"""
    return '''
    <script>
        var url = new URL(window.location);
        var msg = url.searchParams.get("msg");
        document.write("<h1>" + msg + "</h1>");
    </script>
    '''

# ============= 路径遍历漏洞端点 =============
@app.route('/vuln/path_traversal/read', methods=['GET'])
def path_traversal():
    """路径遍历漏洞"""
    filename = request.args.get('file', 'index.txt')

    try:
        # 故意不做路径检查
        with open(filename, 'r') as f:
            content = f.read()
        return jsonify({"success": True, "content": content})
    except Exception as e:
        return jsonify({"error": str(e), "vulnerable": True})

# ============= 命令注入漏洞端点 =============
@app.route('/vuln/cmdi/ping', methods=['GET'])
def command_injection():
    """命令注入漏洞"""
    host = request.args.get('host', '127.0.0.1')

    try:
        # 故意不做输入验证
        result = subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
        return jsonify({"success": True, "output": result})
    except Exception as e:
        return jsonify({"error": str(e), "vulnerable": True})

# ============= SSRF 漏洞端点 =============
@app.route('/vuln/ssrf/fetch', methods=['GET'])
def ssrf():
    """SSRF 漏洞"""
    url = request.args.get('url', '')

    try:
        import requests
        # 故意不做 URL 白名单检查
        response = requests.get(url, timeout=5)
        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "content": response.text[:500]  # 限制返回长度
        })
    except Exception as e:
        return jsonify({"error": str(e), "vulnerable": True})

# ============= XXE 漏洞端点 =============
@app.route('/vuln/xxe/parse', methods=['POST'])
def xxe():
    """XXE 漏洞"""
    xml_data = request.data.decode('utf-8')

    try:
        from lxml import etree
        # 故意允许外部实体
        parser = etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=False)
        root = etree.fromstring(xml_data.encode(), parser)

        return jsonify({
            "success": True,
            "parsed": etree.tostring(root).decode(),
            "vulnerable": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "vulnerable": True})

# ============= 文件上传漏洞端点 =============
@app.route('/vuln/upload/file', methods=['POST'])
def file_upload():
    """文件上传漏洞（不检查文件类型）"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"})

    # 故意不检查文件类型和内容
    upload_path = os.path.join('/tmp', file.filename)
    file.save(upload_path)

    return jsonify({
        "success": True,
        "filename": file.filename,
        "path": upload_path,
        "vulnerable": True
    })

# ============= CSRF 漏洞端点 =============
@app.route('/vuln/csrf/transfer', methods=['POST'])
def csrf():
    """CSRF 漏洞（无 token 验证）"""
    from_account = request.form.get('from', '')
    to_account = request.form.get('to', '')
    amount = request.form.get('amount', '0')

    # 故意不检查 CSRF token
    return jsonify({
        "success": True,
        "message": f"Transferred ${amount} from {from_account} to {to_account}",
        "vulnerable": True
    })

# ============= 信息泄露端点 =============
@app.route('/vuln/info_leak/debug', methods=['GET'])
def info_leak():
    """信息泄露（暴露调试信息）"""
    return jsonify({
        "debug": True,
        "database": "mysql://root:password123@localhost/app",
        "api_key": "sk-1234567890abcdef",
        "internal_ip": "192.168.1.100",
        "vulnerable": True
    })

# ============= 认证绕过端点 =============
@app.route('/vuln/auth_bypass/admin', methods=['GET'])
def auth_bypass():
    """认证绕过"""
    user_id = request.args.get('user_id', '')

    # 故意的弱认证逻辑
    if user_id == '1' or user_id == 'admin' or user_id == '1 OR 1=1':
        return jsonify({
            "success": True,
            "role": "admin",
            "message": "Welcome admin!",
            "vulnerable": True
        })
    else:
        return jsonify({"success": False, "message": "Access denied"})

# ============= 健康检查 =============
@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({"status": "healthy", "message": "Vulnerable app is running"})

@app.route('/')
def index():
    """首页 - 列出所有漏洞端点"""
    return jsonify({
        "message": "Vulnerable Web Application for PoC Testing",
        "endpoints": {
            "SQL Injection": [
                "/vuln/sqli/login",
                "/vuln/sqli/search?q=keyword"
            ],
            "XSS": [
                "/vuln/xss/reflect?name=<script>alert(1)</script>",
                "/vuln/xss/stored",
                "/vuln/xss/dom?msg=<script>alert(1)</script>"
            ],
            "Path Traversal": [
                "/vuln/path_traversal/read?file=../../../../etc/passwd"
            ],
            "Command Injection": [
                "/vuln/cmdi/ping?host=127.0.0.1"
            ],
            "SSRF": [
                "/vuln/ssrf/fetch?url=http://169.254.169.254/latest/meta-data/"
            ],
            "XXE": [
                "/vuln/xxe/parse (POST XML)"
            ],
            "File Upload": [
                "/vuln/upload/file (POST multipart/form-data)"
            ],
            "CSRF": [
                "/vuln/csrf/transfer"
            ],
            "Info Leak": [
                "/vuln/info_leak/debug"
            ],
            "Auth Bypass": [
                "/vuln/auth_bypass/admin?user_id=1"
            ]
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 2. 自动化验证系统

#### PoC 验证器

```python
# poc_validator.py - 自动化验证 AI 生成的 PoC
import docker
import requests
import time
import re
import subprocess
import os
import tempfile

class PoCValidator:
    """PoC 自动化验证器"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.container = None
        self.base_url = None

    def start_vulnerable_app(self):
        """启动漏洞靶场容器"""
        print("🚀 启动漏洞靶场容器...")

        # 构建镜像
        self.docker_client.images.build(
            path=".",
            tag="vuln-app:latest",
            rm=True
        )

        # 启动容器
        self.container = self.docker_client.containers.run(
            "vuln-app:latest",
            detach=True,
            ports={'5000/tcp': None},  # 随机端口
            remove=True
        )

        # 等待容器启动
        time.sleep(3)

        # 获取容器端口
        self.container.reload()
        port = self.container.ports['5000/tcp'][0]['HostPort']
        self.base_url = f"http://localhost:{port}"

        # 健康检查
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✅ 靶场启动成功: {self.base_url}")
                    return True
            except:
                time.sleep(1)

        print("❌ 靶场启动失败")
        return False

    def stop_vulnerable_app(self):
        """停止漏洞靶场容器"""
        if self.container:
            print("🛑 停止靶场容器...")
            self.container.stop()
            self.container = None

    def detect_vulnerability_type(self, poc_code):
        """检测 PoC 的漏洞类型"""
        # 通过代码特征判断漏洞类型
        patterns = {
            'sqli': [
                r"(?i)(union\s+select|or\s+1=1|'.*or.*')",
                r"(?i)(sql|inject|query)",
                r"(?i)(username|password).*(\"|')"
            ],
            'xss': [
                r"(?i)(<script|alert\(|onerror=)",
                r"(?i)(xss|cross.?site)",
                r"(?i)(innerHTML|document\.write)"
            ],
            'path_traversal': [
                r"(?i)(\.\.\/|\.\.\\)",
                r"(?i)(path|traversal|directory)",
                r"(?i)(\/etc\/passwd|C:\\\\Windows)"
            ],
            'cmdi': [
                r"(?i)(;|&&|\|\|)\s*(cat|ls|whoami|ping)",
                r"(?i)(command|injection|exec|system)",
                r"(?i)(shell|bash|cmd)"
            ],
            'ssrf': [
                r"(?i)(169\.254\.169\.254|localhost|127\.0\.0\.1)",
                r"(?i)(ssrf|server.?side.?request)",
                r"(?i)(url=|fetch\()"
            ],
            'xxe': [
                r"(?i)(<!DOCTYPE|<!ENTITY|SYSTEM)",
                r"(?i)(xxe|xml|entity)",
                r"(?i)(file:///|php://)"
            ],
            'upload': [
                r"(?i)(upload|file|multipart)",
                r"(?i)(\.php|\.jsp|\.asp)",
                r"(?i)(shell|webshell)"
            ],
            'csrf': [
                r"(?i)(csrf|cross.?site.?request)",
                r"(?i)(token|referer)",
                r"(?i)(transfer|delete|update)"
            ]
        }

        detected_types = []
        for vuln_type, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, poc_code):
                    detected_types.append(vuln_type)
                    break

        return detected_types if detected_types else ['unknown']

    def get_vulnerable_endpoint(self, vuln_type):
        """根据漏洞类型获取对应的靶场端点"""
        endpoints = {
            'sqli': [
                '/vuln/sqli/login',
                '/vuln/sqli/search'
            ],
            'xss': [
                '/vuln/xss/reflect',
                '/vuln/xss/stored',
                '/vuln/xss/dom'
            ],
            'path_traversal': [
                '/vuln/path_traversal/read'
            ],
            'cmdi': [
                '/vuln/cmdi/ping'
            ],
            'ssrf': [
                '/vuln/ssrf/fetch'
            ],
            'xxe': [
                '/vuln/xxe/parse'
            ],
            'upload': [
                '/vuln/upload/file'
            ],
            'csrf': [
                '/vuln/csrf/transfer'
            ]
        }

        return endpoints.get(vuln_type, [])

    def modify_poc_target(self, poc_code, original_target, vuln_type):
        """修改 PoC 的目标地址为本地靶场"""
        endpoints = self.get_vulnerable_endpoint(vuln_type)
        if not endpoints:
            return poc_code

        # 选择第一个端点
        new_target = f"{self.base_url}{endpoints[0]}"

        # 替换目标 URL
        # 匹配常见的 URL 模式
        url_patterns = [
            (r'(https?://[^\s\'"]+)', new_target),
            (r'(target\s*=\s*["\'])[^"\']+(["\'])', f'\\1{new_target}\\2'),
            (r'(url\s*=\s*["\'])[^"\']+(["\'])', f'\\1{new_target}\\2'),
            (r'(URL\s*=\s*["\'])[^"\']+(["\'])', f'\\1{new_target}\\2'),
        ]

        modified_code = poc_code
        for pattern, replacement in url_patterns:
            modified_code = re.sub(pattern, replacement, modified_code)

        return modified_code

    def run_poc(self, poc_code, language='python'):
        """运行 PoC 代码"""
        print(f"🔧 运行 PoC ({language})...")

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as f:
            f.write(poc_code)
            poc_file = f.name

        try:
            if language == 'python':
                result = subprocess.run(
                    ['python', poc_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            elif language == 'bash':
                result = subprocess.run(
                    ['bash', poc_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                return {"success": False, "error": f"Unsupported language: {language}"}

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "PoC execution timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            # 清理临时文件
            os.unlink(poc_file)

    def analyze_result(self, poc_output, vuln_type):
        """分析 PoC 执行结果"""
        stdout = poc_output.get('stdout', '')
        stderr = poc_output.get('stderr', '')
        combined = stdout + stderr

        # 成功指标
        success_indicators = {
            'sqli': [
                'admin',
                'success',
                'vulnerable',
                'true',
                'login successful'
            ],
            'xss': [
                '<script>',
                'alert',
                'vulnerable',
                'injected'
            ],
            'path_traversal': [
                'root:',
                '/etc/passwd',
                'vulnerable',
                'success'
            ],
            'cmdi': [
                'root',
                'uid=',
                'vulnerable',
                'command executed'
            ],
            'ssrf': [
                'ami-',
                'meta-data',
                'vulnerable',
                '169.254'
            ],
            'xxe': [
                'root:',
                'ENTITY',
                'vulnerable',
                'file://'
            ],
            'upload': [
                'uploaded',
                'success',
                'vulnerable',
                '.php'
            ],
            'csrf': [
                'transferred',
                'success',
                'vulnerable'
            ]
        }

        indicators = success_indicators.get(vuln_type, [])

        # 检查是否包含成功指标
        found_indicators = []
        for indicator in indicators:
            if indicator.lower() in combined.lower():
                found_indicators.append(indicator)

        # 判断是否成功
        is_successful = len(found_indicators) > 0
        confidence = len(found_indicators) / len(indicators) if indicators else 0

        return {
            "successful": is_successful,
            "confidence": confidence,
            "indicators_found": found_indicators,
            "output_sample": combined[:500]  # 限制输出长度
        }

    def validate_poc(self, poc_code, original_target=None, language='python'):
        """
        完整的 PoC 验证流程

        Args:
            poc_code: AI 生成的 PoC 代码
            original_target: 原始目标地址（可选）
            language: PoC 语言（python/bash）

        Returns:
            验证结果
        """
        try:
            # 1. 启动靶场
            if not self.start_vulnerable_app():
                return {"success": False, "error": "Failed to start vulnerable app"}

            # 2. 检测漏洞类型
            vuln_types = self.detect_vulnerability_type(poc_code)
            print(f"🔍 检测到漏洞类型: {', '.join(vuln_types)}")

            results = []

            # 3. 对每种检测到的漏洞类型进行测试
            for vuln_type in vuln_types:
                print(f"\n📝 测试漏洞类型: {vuln_type}")

                # 4. 修改 PoC 目标地址
                if original_target:
                    modified_poc = self.modify_poc_target(poc_code, original_target, vuln_type)
                else:
                    modified_poc = poc_code

                # 5. 运行 PoC
                poc_output = self.run_poc(modified_poc, language)

                # 6. 分析结果
                analysis = self.analyze_result(poc_output, vuln_type)

                results.append({
                    "vulnerability_type": vuln_type,
                    "poc_executed": poc_output.get('success', False),
                    "vulnerability_confirmed": analysis['successful'],
                    "confidence": analysis['confidence'],
                    "indicators": analysis['indicators_found'],
                    "output": poc_output
                })

                # 打印结果
                if analysis['successful']:
                    print(f"✅ 漏洞验证成功 (置信度: {analysis['confidence']:.2%})")
                else:
                    print(f"❌ 漏洞验证失败")

            return {
                "success": True,
                "results": results,
                "overall_success": any(r['vulnerability_confirmed'] for r in results)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

        finally:
            # 7. 清理资源
            self.stop_vulnerable_app()


# ============= 使用示例 =============

def main():
    """示例用法"""

    # AI 生成的 PoC（示例）
    poc_code = """
import requests

target = "http://example.com/login"
data = {
    "username": "admin' OR '1'='1",
    "password": "anything"
}

response = requests.post(target, data=data)
if "success" in response.text or "admin" in response.text:
    print("✅ SQL Injection successful!")
    print(response.text)
else:
    print("❌ SQL Injection failed")
"""

    # 创建验证器
    validator = PoCValidator()

    # 验证 PoC
    result = validator.validate_poc(
        poc_code=poc_code,
        original_target="http://example.com/login",
        language="python"
    )

    # 打印结果
    print("\n" + "="*60)
    print("验证结果:")
    print("="*60)
    if result['success']:
        print(f"总体结果: {'✅ 成功' if result['overall_success'] else '❌ 失败'}")
        for r in result['results']:
            print(f"\n漏洞类型: {r['vulnerability_type']}")
            print(f"PoC 执行: {'✅' if r['poc_executed'] else '❌'}")
            print(f"漏洞确认: {'✅' if r['vulnerability_confirmed'] else '❌'}")
            print(f"置信度: {r['confidence']:.2%}")
            print(f"发现指标: {', '.join(r['indicators'])}")
    else:
        print(f"❌ 验证失败: {result.get('error')}")


if __name__ == "__main__":
    main()
```

### 3. 简化使用流程

#### 一键验证脚本

```python
# quick_validate.py - 一键验证 AI 生成的 PoC
import sys
import argparse
from poc_validator import PoCValidator

def quick_validate(poc_file, target=None):
    """
    一键验证 PoC

    Usage:
        python quick_validate.py poc.py
        python quick_validate.py poc.py --target http://example.com/login
    """
    # 读取 PoC 文件
    with open(poc_file, 'r') as f:
        poc_code = f.read()

    # 检测语言
    if poc_file.endswith('.py'):
        language = 'python'
    elif poc_file.endswith('.sh'):
        language = 'bash'
    else:
        language = 'python'  # 默认

    # 验证
    validator = PoCValidator()
    result = validator.validate_poc(poc_code, target, language)

    # 输出结果
    if result['success'] and result['overall_success']:
        print("\n✅ PoC 验证成功！AI 生成的脚本是有效的。")
        return 0
    else:
        print("\n❌ PoC 验证失败！AI 生成的脚本可能无效。")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='验证 AI 生成的 PoC')
    parser.add_argument('poc_file', help='PoC 文件路径')
    parser.add_argument('--target', help='原始目标地址（可选）')

    args = parser.parse_args()
    sys.exit(quick_validate(args.poc_file, args.target))
```

#### 使用方法

```bash
# 1. 构建靶场镜像（仅首次需要）
docker build -t vuln-app:latest .

# 2. 验证 AI 生成的 PoC
python quick_validate.py ai_generated_poc.py

# 3. 指定原始目标（自动替换）
python quick_validate.py ai_generated_poc.py --target http://real-target.com/vuln
```

## 核心优势

### ✅ 解决的问题

1. **不碰真实环境**：所有测试在本地 Docker 容器中进行
2. **一键式验证**：无需手动搭建不同的靶场环境
3. **自动化流程**：检测漏洞类型 → 启动靶场 → 修改目标 → 运行 → 验证
4. **支持多种漏洞**：SQL注入、XSS、路径遍历、命令注入、SSRF、XXE 等
5. **智能分析**：根据输出自动判断 PoC 是否成功

### 📊 验证流程

```
AI 生成 PoC
    ↓
检测漏洞类型 (SQL注入/XSS/路径遍历等)
    ↓
启动对应的漏洞端点 (Docker 容器)
    ↓
自动替换目标地址 (真实目标 → 本地靶场)
    ↓
在沙箱中运行 PoC
    ↓
分析输出判断是否成功
    ↓
返回验证结果 + 置信度
```

## 扩展功能

### 1. 支持更多语言的 PoC

```python
def run_poc(self, poc_code, language):
    """支持多种语言"""
    runners = {
        'python': ['python', '-c', poc_code],
        'bash': ['bash', '-c', poc_code],
        'node': ['node', '-e', poc_code],
        'php': ['php', '-r', poc_code],
        'ruby': ['ruby', '-e', poc_code],
    }
    # ...
```

### 2. 并发验证多个 PoC

```python
def batch_validate(self, poc_list):
    """批量验证多个 PoC"""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(self.validate_poc, poc_list)

    return list(results)
```

### 3. 生成详细报告

```python
def generate_report(self, results, output_file='report.html'):
    """生成 HTML 报告"""
    # 生成包含截图、日志、分析的详细报告
    pass
```

### 4. 与 AI API 集成

```python
class AIIntegratedValidator:
    """与 AI API 集成的验证器"""

    def validate_with_ai(self, vulnerability_info):
        """
        完整流程:
        1. 发送漏洞信息给 AI
        2. AI 返回 PoC
        3. 自动验证 PoC
        4. 返回结果
        """
        # 1. 调用 AI API
        poc_code = self.call_ai_api(vulnerability_info)

        # 2. 自动验证
        validator = PoCValidator()
        result = validator.validate_poc(poc_code)

        # 3. 如果验证失败，可以让 AI 重新生成
        if not result['overall_success']:
            poc_code = self.call_ai_api(
                vulnerability_info,
                feedback=result  # 提供验证失败的反馈
            )
            result = validator.validate_poc(poc_code)

        return result
```

## 部署建议

### Docker Compose 一键启动

```yaml
# docker-compose.yml
version: '3.8'

services:
  vuln-app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
    volumes:
      - ./vulnerable_app.py:/app/vulnerable_app.py

  validator:
    build: ./validator
    depends_on:
      - vuln-app
    volumes:
      - ./pocs:/pocs
      - ./results:/results
    command: python validator_service.py
```

### 云端部署

可以部署到云端，提供 API 接口：

```python
# API 服务
@app.route('/api/validate', methods=['POST'])
def api_validate():
    """API 接口"""
    poc_code = request.json.get('poc_code')
    target = request.json.get('target')

    validator = PoCValidator()
    result = validator.validate_poc(poc_code, target)

    return jsonify(result)
```

然后你就可以通过 HTTP API 提交 PoC 进行验证。

## 总结

这个方案可以：
- ✅ 自动验证 AI 生成的各类 Web 漏洞 PoC
- ✅ 不需要接触真实目标环境
- ✅ 不需要为每种漏洞单独搭环境
- ✅ 一键启动，自动化流程
- ✅ 支持 SQL注入、XSS、路径遍历、命令注入、SSRF、XXE 等常见漏洞

**这个方案能解决你的问题吗？**