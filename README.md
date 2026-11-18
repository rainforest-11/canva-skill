# canva-skill

让 **DeepSeek Harness (DSH)** 能用中文直接指挥 **Canva 可画**做设计：说一句「做张海报」，就走完 **生成 → 挑图 → 取 design_id → 改字改色 → 导出 PNG/PDF** 的全流程。

面向中国大陆网络环境——Canva 国际版 MCP 在这里**根本连不上**，本仓库的核心就是解决这件事。

```
你：做一张 AI 技术分享会海报，深色底，极简
DSH：[生成 4 个候选，全部列图给你选]
你：第 3 个
DSH：[取到 design_id → 导出 PNG → 落到本地]
```

---

## 目录

- [它解决什么问题](#它解决什么问题)
- [工作原理](#工作原理)
- [环境要求](#环境要求)
- [安装技能](#安装技能)
- [接通 Canva MCP](#接通-canva-mcp)
- [验证接通](#验证接通)
- [用法](#用法)
- [design-id.py](#design-idpy)
- [工作流细节](#工作流细节)
- [故障排查](#故障排查)
- [已知限制](#已知限制)
- [FAQ](#faq)
- [License](#license)

---

## 它解决什么问题

Canva 官方远程 MCP 端点是 `https://mcp.canva.com/mcp`，协议是 Streamable HTTP + OAuth 2.1 + 动态客户端注册（DCR）。这套东西本身没问题，问题在于**授权同意页挂在 `www.canva.com` 上**，而：

```
中国大陆 IP 访问 www.canva.com
  → 302 https://www.canva.cn/?display-com-option=true
  → OAuth 的 state / PKCE / redirect_uri 全部对不上
  → 授权链断在中间，永远拿不到 token
```

试过但**无效**的绕过方式：`?display-com-option=com`、cookie `canva_country=US`、请求头 `X-Country: US`、`Accept-Language: en-US`、强制 IPv4、伪装完整浏览器 UA。Canva 是**按出口 IP 判定**的，改这些没用。

好消息是 Canva 中国版有一整套**完整可用的镜像端点** `https://mcp.canva.cn`，支持同样的 DCR + PKCE + loopback 回调，本机直连即可，不需要代理，也不需要去开发者门户注册应用、不需要 client secret。

接通之后还有两个坑，这个技能主要就是在填它们：

1. **`generate-design` 返回的链接不是 `design_id`。** 形如 `https://www.canva.cn/d/V5U4YghpJDrT-oA` 的尾串是「建议 slug」，直接拿去调工具必报错。真 ID 是 11 位的 `DAHbMx4Ch24`，只有在**登录态的浏览器**里打开链接、从地址栏才能拿到。`scripts/design-id.py` 负责自动把它刮出来。
2. **编辑是事务制的。** 不 commit 等于没改；每次 `keep_open` 都要求先比对改前/改后缩略图再动手。

---

## 工作原理

```
┌─────────────┐   MCP over Streamable HTTP    ┌──────────────────┐
│ DeepSeek    │ ────────────────────────────► │ mcp.canva.cn/mcp │
│ Harness     │ ◄──────────────────────────── │  (中国版镜像)     │
└─────────────┘         29 个工具               └────────┬─────────┘
       │                                                 │ OAuth 2.1
       │ 读 SKILL.md 决定怎么调                           ▼
       │                                        ┌──────────────────┐
       │                                        │ www.canva.cn     │
       │                                        │ 登录 + 授权同意页 │
       │                                        └──────────────────┘
       ▼
┌─────────────────────────┐
│ dsh-mcp-connector 插件   │  负责 DCR 注册、PKCE、起本地回调、换 token
└─────────────────────────┘
```

- **`dsh-mcp-connector`** 是 DSH 的 MCP 连接器插件，内置 OAuth2-PKCE 流程：动态注册客户端 → 生成 code_verifier/challenge → 起一个 `127.0.0.1` 随机端口的回调服务器 → 打开浏览器 → 收 code → 换 token。
- token 有四小时有效期，过期自动用 refresh_token 续期，**只有第一次需要人工点「允许」**。
- 本技能（`SKILL.md`）是**操作手册**：告诉 DSH 29 个工具怎么串起来用、哪些参数是什么形状、踩过的坑在哪。

---

## 环境要求

| 项 | 要求 |
| --- | --- |
| DSH | 任意近期版本，`desktop` 或 `web` profile 均可 |
| 插件 | `dsh-mcp-connector`（OAuth2-PKCE 支持） |
| 账号 | **Canva 可画（canva.cn）**账号，不是国际版 canva.com |
| 网络 | 能直连 `mcp.canva.cn` / `www.canva.cn`，**不需要代理** |
| Python | ≥ 3.8，仅 `design-id.py` 需要，纯标准库 |
| 浏览器 | Edge 或 Chrome，且**已登录 Canva** |

> ⚠️ **canva.cn（可画）和 canva.com 是两个独立体系**，账号不互通。你的可画账号只能走本仓库的国内版路径。

---

## 安装技能

技能就是两个文件，拷到 DSH 的技能目录即可：

```
~/.dsh/skills/canva/
├── SKILL.md
└── scripts/
    └── design-id.py
```

**Windows**

```powershell
# 从本仓库直接拷
xcopy /E /I canva "%USERPROFILE%\.dsh\skills\canva"

# 或者用 git（如果你装了）
git clone https://github.com/rainforest-11/canva-skill.git
xcopy /E /I canva-skill\canva "%USERPROFILE%\.dsh\skills\canva"
```

**macOS / Linux**

```bash
mkdir -p ~/.dsh/skills
cp -r canva ~/.dsh/skills/canva
```

**验证装好了**：重启 DSH，让它重新扫描技能目录。之后问它「你会用 canva 吗」，或者直接说「做张海报」，它会自动加载 `canva` 技能。

技能是**按需加载**的——不触发相关任务时不占上下文。

---

## 接通 Canva MCP

技能只是说明书，底下需要有 `mcp.canva.cn` 这条连接。两条路，选一。

### 路线 A：一键走连接器市场（如果你用的连接器带 canva 卡片）

打开 DSH 的 MCP 连接器面板 → 找到 **Canva 可画** → 连接。

**但如果你的连接器里 canva 卡片写死的是国际版 `mcp.canva.com`，这条路在大陆必然失败**，走路线 B。

判断方法：连接失败时报 `浏览器授权回调失败：no callback received within 300000ms`，且浏览器里被 302 到 `www.canva.cn` —— 就是撞上了。

### 路线 B：自建连接（推荐，大陆环境唯一可靠方案）

自己写一份连接器描述，指向国内版端点，再让连接器装上。

**1. 保存描述文件** `canva-cn.json`：

```json
{
  "schemaVersion": 1,
  "id": "canva-cn",
  "name": "Canva 可画（中国版）",
  "vendor": "Canva",
  "category": "设计创意",
  "homepage": "https://www.canva.dev/docs/mcp/",
  "auth": {
    "mode": "oauth2-pkce",
    "issuer": "https://mcp.canva.cn",
    "scope": "",
    "clientName": "DeepSeek Harness - Canva MCP",
    "tokenEndpointAuthMethod": "none",
    "apiKeyHeader": "X-Api-Key",
    "grantSharing": "connector"
  },
  "servers": [
    {
      "serverKey": "canva",
      "serverName": "canva",
      "url": "https://mcp.canva.cn/mcp",
      "transport": "streamable-http",
      "headers": {
        "Accept": "application/json, text/event-stream"
      }
    }
  ]
}
```

几个字段的意思：

| 字段 | 值 | 为什么 |
| --- | --- | --- |
| `auth.mode` | `oauth2-pkce` | 走 DCR + PKCE，不需要 client secret |
| `auth.issuer` | `https://mcp.canva.cn` | 连接器从这里拉 `.well-known` 元数据 |
| `auth.scope` | `""` | Canva 不校验 scope 值，空串也过，最终由服务端展开成 16 个权限 |
| `tokenEndpointAuthMethod` | `none` | DCR 注册的是公开客户端，没有 secret |
| `servers[0].url` | `https://mcp.canva.cn/mcp` | 真正的 MCP 端点 |
| `headers.Accept` | `application/json, text/event-stream` | Streamable HTTP 必须同时接受这两种 |

**2. 把它托管到一个本地 HTTP 地址**

连接器的 `installFromUrl` 需要一个 URL，不能直接吃本地路径。起个临时服务：

```bash
cd <canva-cn.json 所在目录>
python -m http.server 39001
```

**3. 触发安装**

先拿到当前的 GUI 端口（DSH 界面上显示的地址，形如 `http://127.0.0.1:50723`），然后：

```bash
curl -s -X POST http://127.0.0.1:<GUI端口>/mcp-connector/api \
  -H "Origin: http://127.0.0.1:<GUI端口>" \
  -H "Content-Type: application/json" \
  -d '{"method":"installFromUrl","params":{"url":"http://127.0.0.1:39001/canva-cn.json","scope":"global"}}'
```

> `Origin` 头是必须的，连接器用它做 CSRF 防护（`isTrustedWebRequest`），缺了直接 403。

成功会返回：

```json
{
  "ok": true,
  "message": "已连接 \"Canva 可画（中国版）\"（1 个 MCP server），共 1 条",
  "detail": { "keys": ["canva-cn-canva"], "grantKey": "grant:default:3cb4cb8fb11a91ae" }
}
```

对 `oauth2-pkce` 类型的卡片，`installFromUrl` **会自动接着触发 OAuth 授权**，浏览器会被拉起来。

**4. 在浏览器里点「允许」**

会看到一个标题为「关联至Canva可画」的页面：

```
Canva可画AI连接器想要访问你的Canva可画帐户
当前账号：<你的账号>
权限：读取你的用户个人资料 / 读取设计元数据 / 创建设计 / 读取设计内容 / ...
[允许]  [取消]
```

**回调监听只等 300 秒**（`callbackTimeoutMs` 默认 300000）。超时就会失败，报：

```
连接失败: 浏览器授权回调失败：no callback received within 300000ms
```

失败不要紧，重跑第 3 步即可，会重新注册一个新客户端。**记得在这 5 分钟内点完。**

点完「允许」后回调地址会收到 `?code=...&state=...`，连接器自动换 token 并落盘。

**5. 关掉临时服务**

```bash
# Ctrl+C，或者
kill %1
```

---

## 验证接通

**第一层：连接状态**

```bash
curl -s -X POST http://127.0.0.1:<GUI端口>/mcp-connector/api \
  -H "Origin: http://127.0.0.1:<GUI端口>" \
  -H "Content-Type: application/json" \
  -d '{"method":"status","params":{}}'
```

要看到：

```
canva-cn-canva | Canva 可画（中国版） | https://mcp.canva.cn/mcp | healthy | err: none
```

**第二层：真调一个只读工具**

```
search-designs({ query: "海报", limit: 3 })
```

返回真实设计条目（含 11 位 `design_id`、`edit_url`、缩略图 URL）就说明全链路通了。

> ❌ **别用 `get-logged-in-account-details` 验收**。这个工具虽然出现在 tools/list 里，但调用必报
> `MCP error -32602: Tool get-logged-in-account-details not found`。用它验收会误判成没连上。

---

## 用法

装好之后不需要记工具名，用自然语言说就行。

### 从零做一张海报

```
做一张 AI 技术分享会海报，深色背景，标题「DeepSeek Harness 实战分享」，
副标题「2026.11.20 · 线上直播」，极简现代风格
```

DSH 会：

1. 调 `generate-design`，**等几十秒**，拿到 4 个候选
2. **把 4 张缩略图全部下载、编号列出来给你选**（这一步不会替你决定）
3. 你选一个后，去浏览器打开链接、跑 `design-id.py` 拿到真 ID
4. `export-design` 导出 PNG，下到本地交给你

### 指定类型

`design_type` 支持四种：

| 值 | 用途 |
| --- | --- |
| `poster` | 海报、传单、横幅 |
| `presentation` | PPT、演示文稿、报告 |
| `xiaohongshu` | 小红书笔记、种草图 |
| `resume` | 简历 |

```
做一份三个月的项目汇报 PPT，商务风，蓝灰配色
做一张小红书封面的种草图，关于咖啡，暖色调
```

### 改已有设计

```
把 DAHbMx4Ch24 的标题改成「实战分享会」，日期改成 2026.11.20
```

走的是事务制：打开事务 → 改 → 给你看改后预览 → 你确认 → commit。

### 换尺寸

```
把这个设计改成 1080x1080 的方形，用在朋友圈
```

会生成**一个新设计**，原设计不动。

### 导出其他格式

```
导出成 PDF，A4 尺寸
导出成 PPTX，我要继续在 PowerPoint 里改
```

---

## design-id.py

`generate-design` 吐出来的链接尾串**不是** `design_id`，这个脚本负责把真 ID 找出来。

它的做法是：从 Edge / Chrome 的浏览历史里搜 `canva.cn/design/<11位>/`，取最新一条。因为浏览器运行时会**锁住** History 文件，脚本走的是「复制快照 + sqlite 只读」。

```bash
python scripts/design-id.py                      # 最新的一个（默认 Edge）
python scripts/design-id.py --all                # 所有历史 ID，新 → 旧
python scripts/design-id.py --browser chrome     # 换成 Chrome
python scripts/design-id.py --within 10          # 只要最近 10 分钟内的
python scripts/design-id.py --check              # 只看 History 能不能读，不解析
```

| 参数 | 作用 |
| --- | --- |
| `--browser {edge,chrome}` | 查哪个浏览器的历史，默认 `edge` |
| `--within MINUTES` | 只看这个时间窗口内的访问记录 |
| `--all` | 列出所有不同的 ID，而不是只给最新的 |
| `--check` | 只报告 `histories: N, design ids: M`，用于确认环境 |

**退出码非零**表示没找到，附带提示：

```
no /design/<id> URL in history.
The candidate link most likely never loaded (Canva login wall, or the
international canva.com region block). Open it manually in a logged-in
browser, confirm the address bar shows /design/<id>/..., then retry.
```

这**通常不是脚本坏了**，而是链接撞了登录墙或被地区拦截——去浏览器里手动打开确认一下。

---

## 工作流细节

### 缩略图必须伪装 UA

```bash
# ❌ 403，返回 754801 字节的 Cloudflare 页冒充图片
curl "https://www.canva.cn/api/short/<thumb_id>" -o cand.png

# ✅ 200 image/png
curl -sL \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0" \
  -H "Referer: https://www.canva.cn/" \
  "https://www.canva.cn/api/short/<thumb_id>" -o cand.png
```

下完务必用 PIL 验一下是真图（`Image.open(p).size`），别把 403 页面当图片交付。

### 导出

```javascript
// 先查支持哪些格式
get-export-formats({ design_id: "DAHbMx4Ch24" })
// → {"formats":{"pdf":{},"jpg":{},"png":{},"pptx":{},"gif":{},"mp4":{}}}

// 再导出
export-design({ design_id: "DAHbMx4Ch24", format: { type: "png", lossless: true } })
```

`format` 的可选键：

| 键 | 适用 | 说明 |
| --- | --- | --- |
| `type` | 全部 | `pdf` / `png` / `jpg` / `gif` / `pptx` / `mp4` / `csv` |
| `lossless` | png | 无损压缩，默认 true |
| `as_single_image` | png | 多页合成一张 |
| `transparent_background` | png | 透明底 |
| `export_quality` | 多种 | `regular` / `pro` |
| `size` | pdf | `a4` / `a3` / `letter` / `legal` |
| `width` / `height` | png/jpg/gif | 输出像素尺寸 |
| `quality` | jpg | 1–100 |
| `pages` | 全部 | 1-based 页码数组 |

返回：

```json
{ "job": { "id": "0e713f30-...", "status": "success",
           "urls": ["https://export-download.canva.cn/4Ch24/...png?X-Amz-Expires=81732&..."] } }
```

> ⏰ 那串 signed URL 带 `X-Amz-Expires`，实测约 **20 小时**后失效，**过期只能重新导出**。拿到就立刻下。
> 下载本身不需要特殊 UA。

### 改图：事务制

```javascript
// 1. 开事务，拿 transaction_id 和元素的 locator_id
read-design({ design_id, open_transaction: true,
              filter: { fields: ["design_content"], page_indices: [1] } })
// → { transaction: { transaction_id: "5628896162629615140" }, design_content: {...} }

// 2. 应用操作，事务保持打开
edit-design({ transaction_id, page_index: 1,
              operations: [{ type: "replace_text",
                             locator_id: "PB66CxV1knH785yl-LBvWdG2vWzZQVdpn",
                             text: "新标题" }],
              finalize: "keep_open" })
// → { status: "edits_unverified", thumbnail_urls: [...], document: {...} }

// 3. 确认无误后落盘（不可撤销）
edit-design({ transaction_id, finalize: "commit" })
// 或者丢弃
edit-design({ transaction_id, finalize: "cancel", operations: [] })
```

`operations[].type` 常用的：

| 操作 | 参数 |
| --- | --- |
| `replace_text` | `{locator_id, text}` |
| `find_and_replace_text` | `{locator_id, find_text, replace_text}` |
| `format_text` | `{locator_id, formatting}` — 字号/字重/颜色/对齐/行高 |
| `update_fill` | `{locator_id, asset_type, asset_id, alt_text}` |
| `add_text` | `{page_id, text, top, left, width}` |
| `insert_shape` | `{page_id, top, left, width, height, path, ...}` |
| `recolor_element` | `{locator_id, color}` |
| `position_element` | `{locator_id, top, left}` |
| `resize_element` | `{locator_id, width, height}` |
| `delete_element` | `{locator_id}` |
| `add_page` | `{width, height, title}` |

**两个关键点**：

1. `page_index` 是 **1-based**。
2. `add_text` / `insert_shape` 这类**新建元素**传 `page_id`（`design_content.pages[0].id`，形如 `PBcBxnvRx70Hn9WY`），**不是** `locator_id`。元素级 `locator_id`（形如 `PB66CxV1knH785yl-LBlVJ6GW3LKGl2zk`，即 `page_id-element_id`）只用于改**已有**元素。

**每次 `keep_open` 都要照 `next_required_action` 做**：把返回的 `thumbnail_urls[0]` 下下来看一眼，确认没有误改，再决定继续还是 commit。别连着盲改。

---

## 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `no callback received within 300000ms` | 5 分钟内没点「允许」 | 重跑 `installFromUrl`，这次手放在鼠标上 |
| 授权页 302 到 `www.canva.cn` 首页 | 用了国际版 `mcp.canva.com` | 换 `mcp.canva.cn` |
| 授权页显示 Cloudflare 拦截页 | 地区风控 | 同样换 `mcp.canva.cn` |
| `Must be a design ID or a full Canva design share URL` | 传了 suggestion 链接或 `edit_url` | 用 `design-id.py` 取真 ID |
| `String must contain exactly 11 character(s)` | 同上，ID 长度不对 | 同上 |
| 缩略图 403 / 打不开 | 缺浏览器 UA | 加 UA + `Referer` |
| 导出的 PNG 一片空白 | ID 拿错了（可能是另一条 suggestion，对应空白设计） | 浏览器打开 `canva.cn/design/<id>` 核对 |
| `resolve-shortlink` 报 `Shortlink not found` | 那不是 shortlink，是 edit_url | 不用管，直接走 `design-id.py` |
| `Tool get-logged-in-account-details not found` | 该工具服务端缺失 | 换 `search-designs` 验收 |
| 连接 `unhealthy` | token 过期且刷新失败 | `{"method":"reconnect","params":{"key":"canva-cn-canva"}}` |
| `403` on `/mcp-connector/api` | 缺 `Origin` 头 | 加上 `Origin: http://127.0.0.1:<GUI端口>` |
| GUI 端口连不上 | 端口每次启动会变 | 从 DSH 界面上的地址重新取 |

**连接被误删了怎么办**：重走一遍[路线 B](#路线-b自建连接推荐大陆环境唯一可靠方案)，两分钟的事。

---

## 已知限制

- **需要 Canva Pro 的能力**：`resize-design` 的完整形态、`autofill-design`、`*brand-template*` 系列。免费账号 `list-brand-kits` 返回 `{"items":[]}`。
- **`upload-asset-from-url` 只吃公网 HTTPS**。本地图片要先托管到可公开访问的地址，或在 Canva 编辑器里手工上传。
- **速率限制**：`generate-design` 约 20 次/分，`export-design` 约 20 次/分，`generate-image` 约 10 次/分，`upload-asset-from-url` 约 30 次/分。
- **`generate-design` 很慢**，几十秒到一分钟级。别设短超时。
- **`search-designs` 是唯一干净的 ID 入口**——它返回的 `design_id` 是真的 11 位 ID，可以直接拿去 read/export，绕开 suggestion 链接的麻烦。
- **`canva.com` 和 `canva.cn` 账号不互通**，本仓库只覆盖国内版。
- 技能里写死的 `canva-cn-canva` 是连接 key，如果你改过连接名，需要同步改 `SKILL.md`。

---

## FAQ

**Q：为什么不直接用 `mcp.canva.com`？**
A：大陆 IP 访问 `www.canva.com` 一律 302 到 `canva.cn`，OAuth 授权页永远打不开，链条断死。`mcp.canva.cn` 是官方中国版的镜像，功能一致。

**Q：需要去 Canva 开发者门户注册应用吗？**
A：不需要。`mcp.canva.cn` 支持动态客户端注册（DCR），连接器会在授权时自动注册一个临时客户端，`token_endpoint_auth_method: none`，不需要 client secret。

**Q：token 会过期吗？**
A：access token 四小时有效，但带 refresh_token，连接器会自动续。**只有第一次需要点「允许」**。

**Q：为什么生成的设计链接打不开？**
A：那只是建议链接，不带登录 cookie 时会被 `303 → /api/action?token=... → 302 → /login/`。必须在已登录的浏览器里打开。

**Q：4 个候选可以一次性全导出吗？**
A：技术上可以，但没必要——白烧配额。技能会先让你选，选完只导那一个。

**Q：能让它自己决定选哪张吗？**
A：可以，明确说「你自己定」就行。默认行为是**等你选**。

**Q：本机能用但公司/学校网络不行？**
A：`mcp.canva.cn` 和 `www.canva.cn` 都得通。如果被墙或被限制，本方案无解——这不是代理能解决的问题，是端点本身的可达性。

---

## License

[MIT](LICENSE)
