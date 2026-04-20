# CDP Proxy API 参考

服务地址：`http://localhost:3456`

启动方式（由 check-deps.mjs 自动管理，无需手动执行）：
```bash
node ~/.workbuddy/skills/web-access/scripts/check-deps.mjs
```

强制停止：`pkill -f cdp-proxy.mjs`

---

## API 端点

### GET /health
健康检查，返回代理状态。
```
{"status":"ok","connected":true,"sessions":2,"chromePort":9222}
```

### GET /targets
列出所有已打开的页面 tab。
```bash
curl -s http://localhost:3456/targets
```
返回数组，每项包含 `targetId`、`title`、`url` 等字段。

### GET /new?url=URL
创建新的后台 tab 并等待页面加载。
```bash
curl -s "http://localhost:3456/new?url=https://example.com"
# {"targetId":"XXXXX"}
```

### GET /close?target=ID
关闭指定 tab。
```bash
curl -s "http://localhost:3456/close?target=XXXXX"
```

### GET /navigate?target=ID&url=URL
在已有 tab 中导航到新 URL（自动等待加载）。
```bash
curl -s "http://localhost:3456/navigate?target=XXXXX&url=https://example.com"
```

### GET /back?target=ID
后退一页。
```bash
curl -s "http://localhost:3456/back?target=XXXXX"
```

### GET /info?target=ID
获取页面基本信息（标题、URL、加载状态）。
```bash
curl -s "http://localhost:3456/info?target=XXXXX"
# {"title":"Example","url":"https://example.com","ready":"complete"}
```

### POST /eval?target=ID
在页面中执行 JavaScript，POST body 为 JS 表达式。
```bash
# 获取页面标题
curl -s -X POST "http://localhost:3456/eval?target=XXXXX" -d 'document.title'

# 提取所有链接
curl -s -X POST "http://localhost:3456/eval?target=XXXXX" \
  -d 'JSON.stringify([...document.querySelectorAll("a")].map(a=>({text:a.textContent.trim(),href:a.href})))'

# 填写输入框
curl -s -X POST "http://localhost:3456/eval?target=XXXXX" \
  -d 'document.querySelector("input[name=q]").value="search term"; "ok"'
```
**注意**：返回值必须是可序列化的（字符串、数字、对象），DOM 节点需提取属性。

### POST /click?target=ID
通过 JS 模拟点击（快速，覆盖大多数场景）。POST body 为 CSS 选择器。
```bash
curl -s -X POST "http://localhost:3456/click?target=XXXXX" -d 'button.submit'
curl -s -X POST "http://localhost:3456/click?target=XXXXX" -d '#login-btn'
```

### POST /clickAt?target=ID
模拟真实浏览器鼠标点击事件（算用户手势，可触发文件对话框等）。
```bash
curl -s -X POST "http://localhost:3456/clickAt?target=XXXXX" -d 'input[type=file]'
```

### POST /setFiles?target=ID
直接为文件 input 设置本地文件，绕过文件选择对话框。
```bash
curl -s -X POST "http://localhost:3456/setFiles?target=XXXXX" \
  -H "Content-Type: application/json" \
  -d '{"selector":"input[type=file]","files":["/path/to/file.png"]}'
```

### GET /scroll?target=ID&y=N&direction=down|up|top|bottom
滚动页面。
```bash
# 向下滚动 3000px
curl -s "http://localhost:3456/scroll?target=XXXXX&y=3000"
# 滚动到底部
curl -s "http://localhost:3456/scroll?target=XXXXX&direction=bottom"
# 滚动到顶部
curl -s "http://localhost:3456/scroll?target=XXXXX&direction=top"
```

### GET /screenshot?target=ID&file=/path/to/output.png
截图。
```bash
# 保存到文件
curl -s "http://localhost:3456/screenshot?target=XXXXX&file=/tmp/shot.png"
# 返回二进制（不指定 file 参数）
curl -s "http://localhost:3456/screenshot?target=XXXXX" > /tmp/shot.png
```

---

## 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Chrome 未开启远程调试端口` | Chrome 未开启调试 | 访问 `chrome://inspect/#remote-debugging` 勾选 Allow remote debugging |
| `attach 失败` | target ID 无效或已关闭 | 重新 `/targets` 获取最新 ID |
| `CDP 命令超时` | 页面响应慢 | 等待页面加载后重试 |
| `端口 3456 已被占用` | 已有非 proxy 进程 | `lsof -i:3456` 查看，必要时 kill |

---

## 常用操作组合

### 登录后抓取数据
```bash
# 1. 打开登录页
curl -s "http://localhost:3456/new?url=https://site.com/login"
# 记下 targetId，以下用 $TID 代替

# 2. 填写表单并提交
curl -s -X POST "http://localhost:3456/eval?target=$TID" \
  -d 'document.querySelector("#username").value="user"; document.querySelector("#password").value="pass"; "ok"'
curl -s -X POST "http://localhost:3456/click?target=$TID" -d 'button[type=submit]'

# 3. 等待跳转后提取数据
curl -s -X POST "http://localhost:3456/eval?target=$TID" \
  -d 'JSON.stringify([...document.querySelectorAll(".item")].map(el=>el.textContent.trim()))'
```

### 截图分析页面状态
```bash
TID=$(curl -s "http://localhost:3456/new?url=https://example.com" | python3 -c "import sys,json; print(json.load(sys.stdin)['targetId'])")
curl -s "http://localhost:3456/screenshot?target=$TID&file=/tmp/page.png"
# 然后可以用 read_file 工具读取截图分析
```
