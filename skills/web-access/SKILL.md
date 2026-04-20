---
name: web-access
description: >
  This skill should be used when the user needs to access the web beyond simple
  search or static page fetching — including logging into sites, interacting with
  dynamic pages, scraping content behind authentication, automating browser
  operations, or performing any task that requires operating a real browser.
  Triggers include: "帮我登录", "抓取这个页面", "自动点击", "浏览器操作",
  "需要登录才能看", "动态页面", "截个图", and similar web interaction requests.
---

# web-access

完整联网能力扩展：三层通道调度 + 浏览器 CDP 直连 + 并行分治。

## 前置检查

开始任何浏览器 CDP 操作前，先运行环境检查脚本确认就绪：

```bash
node ~/.workbuddy/skills/web-access/scripts/check-deps.mjs
```

若检查未通过，引导用户完成设置：
- **Node.js 22+**：必需（使用原生 WebSocket）。低于 22 可用但需安装 `ws` 模块。
- **Chrome remote-debugging**：在 Chrome 地址栏访问 `chrome://inspect/#remote-debugging`，勾选 **"Allow remote debugging for this browser instance"**，可能需重启浏览器。

检查通过后，在回复中向用户直接展示以下须知，再执行 CDP 操作：

```
温馨提示：部分站点对浏览器自动化操作检测严格，存在账号封禁风险。已内置防护措施但无法完全避免，继续操作即视为接受。
```

## 浏览哲学

**像人一样思考，兼顾高效与适应性完成任务。**

执行任务时不过度依赖预设步骤，而是带着目标进入，边看边判断，遇到阻碍就解决，发现内容不够就深入——全程围绕「我要达成什么」做决策。

## 联网工具选择

确保信息真实性，一手信息优于二手信息。

| 场景 | 工具 |
|------|------|
| 搜索摘要或关键词结果，发现信息来源 | **WebSearch 工具** |
| URL 已知，需定向提取特定信息 | **WebFetch 工具** |
| URL 已知，需要原始 HTML 源码 | **execute_command: curl** |
| 非公开内容，或已知静态层无效的平台 | **浏览器 CDP** |
| 需要登录态、交互操作，或需要在浏览器内自由导航探索 | **浏览器 CDP** |

**Jina**（可选预处理层）：第三方服务，可将网页转为 Markdown，节省 token 但可能有信息损耗。
`curl -s "https://r.jina.ai/https://example.com"`

## 浏览器 CDP 模式

通过 CDP Proxy 直连用户日常 Chrome，天然携带登录态，无需启动独立浏览器。

### 启动 Proxy

```bash
node ~/.workbuddy/skills/web-access/scripts/check-deps.mjs
```

check-deps.mjs 会自动检测 Chrome 调试端口并以后台守护进程方式启动 cdp-proxy.mjs（监听 localhost:3456）。Proxy 启动后保持运行，重启需 Chrome 重新授权。

### Proxy API 调用（通过 execute_command 执行 curl）

```bash
# 列出用户已打开的 tab
curl -s http://localhost:3456/targets

# 创建新后台 tab
curl -s "http://localhost:3456/new?url=https://example.com"

# 执行任意 JS（POST body 为表达式）
curl -s -X POST "http://localhost:3456/eval?target=TARGET_ID" -d 'document.title'

# 截图保存到本地
curl -s "http://localhost:3456/screenshot?target=TARGET_ID&file=/tmp/shot.png"

# 点击元素（CSS 选择器）
curl -s -X POST "http://localhost:3456/click?target=TARGET_ID" -d 'button.submit'

# 滚动页面
curl -s "http://localhost:3456/scroll?target=TARGET_ID&y=3000"

# 关闭 tab
curl -s "http://localhost:3456/close?target=TARGET_ID"
```

详细 API 参考：加载 `references/cdp-api.md`

### 三种点击方式

1. `/click` — JS 层面 `.click()`，简单快速，覆盖大多数场景
2. `/clickAt` — 真实 CDP 鼠标事件，可触发文件对话框、绕过部分反自动化检测
3. `/setFiles` — 直接设置文件 input，绕过文件选择对话框

## 并行调研：子 Agent 分治策略

任务包含多个独立调研目标时，合理分治给子 Agent 并行执行，提升效率。

## 信息核实类任务

核实目标是**一手来源**，而非更多二手报道。

## 站点经验

操作中积累的特定网站经验，按域名存储在 `~/.workbuddy/skills/web-access/references/site-patterns/` 下。

确定目标网站后，读取对应站点经验文件（如存在）：
```
~/.workbuddy/skills/web-access/references/site-patterns/{domain}.md
```

## References 索引

- `references/cdp-api.md`：需要 CDP API 详细参考时加载
- `references/site-patterns/{domain}.md`：确定目标网站后读取对应站点经验
