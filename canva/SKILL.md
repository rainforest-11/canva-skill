---
name: canva
description: Drive Canva (可画) poster and design work through the canva MCP tools - generate a design, recover its design_id, edit text/colors in a transaction, resize, and export PNG/PDF. Use whenever the user asks for a poster, 海报, 封面, 小红书图, PPT, 简历, or any Canva/可画 design work, or mentions design_id, export, 导出, mcp.canva.cn.
---

# Canva 可画操作

本机已接通 Canva 中国版 MCP（`https://mcp.canva.cn/mcp`），29 个 `mcp__canva__*` 工具可用。
**每次动手前先确认连接还在**：

```bash
curl -s -X POST http://127.0.0.1:<当前GUI端口>/mcp-connector/api \
  -H "Origin: http://127.0.0.1:<当前GUI端口>" -H "Content-Type: application/json" \
  -d '{"method":"status","params":{}}'
```

看 `connections[].key == "canva-cn-canva"` 且 `connectionState == "healthy"`。
GUI 端口不是固定的，从运行上下文里的 `Current DeepSeek Harness Web GUI URL` 取。
不健康就 `{"method":"reconnect","params":{"key":"canva-cn-canva"}}`；OAuth 过期会自动用 refresh_token 续。

## 一条铁律：generate-design 给的链接不是 design_id

`generate-design` 返回的 `url` 长这样：

```
https://www.canva.cn/d/V5U4YghpJDrT-oA      ← 这是"建议链接"，不是设计 ID
```

直接用会炸，两种报错：

```
Invalid arguments for tool read-design: Must be a design ID or a full Canva design share URL at design_id
Invalid arguments for tool get-export-formats: String must contain exactly 11 character(s) at design_id
```

真正的 `design_id` 是 **11 位**的 `DAHbMx4Ch24`，只有在**登录态的浏览器**里打开那个链接才会出现，
地址栏变成 `https://www.canva.cn/design/DAHbMx4Ch24/...`。`resolve-shortlink` 对这类 slug 报
`Shortlink not found`，帮不上忙。

**恢复设计 ID**：在已登录 Canva 的浏览器里打开候选链接，然后跑
（路径相对本 skill 目录，纯 Python 标准库，无需安装依赖）

```bash
python scripts/design-id.py              # 最新一个 ID
python scripts/design-id.py --all        # 所有历史 ID，新→旧
python scripts/design-id.py --within 10 --browser chrome
python scripts/design-id.py --check      # 只看 History 能不能读
```

脚本从浏览器 History 里刮 `/design/<11位>/`，因为 History 被浏览器锁着，走的是复制快照 + sqlite 只读。
拿不到 ID 时它退出非零并提示——通常意味着链接撞了登录墙或被地区拦截，不是脚本坏了。

打开链接的可靠方式（Windows）：

```powershell
Set-Clipboard -Value "https://www.canva.cn/d/<slug>"
# 然后在对焦的 Edge 窗口 ^l ^v {ENTER}
```

## 多方案必须先让用户选（硬规则）

只要摆到台面上的东西**不止一个**，就停下来问，别自己替用户决定：

- `generate-design` 一次回 4 个候选 → **全部下载缩略图、编号列出**，等用户点名再走下一步
- 用户给了多版需求（不同风格 / 不同尺寸 / 不同文案）→ 每版都做出来，一起摆出来选
- `search-brand-templates` / `search-designs` 命中多条 → 先列出来让用户挑
- `resize-design` 会另行生成**新设计**，也算多方案

例外（不必问）：用户已明确说「就按这个来」「你自己定」「随便给我一版」，或只有唯一可行解时。

摆候选时给**缩略图 + 一句话观感**（配色/版式/适合什么场合），不要只丢一串链接或 ID 让用户自己点。
用户选定后再取 design_id、再导出——**别提前把 4 个都导出浪费配额**。

## 标准流程

| 步骤 | 工具 | 要点 |
| --- | --- | --- |
| 1 生成 | `generate-design({query, design_type})` | `design_type` ∈ `poster` / `presentation` / `xiaohongshu` / `resume`；`query` **用用户原语言写**，别翻成英文 |
| 2 挑图 | 下载缩略图 → **问用户选哪个** | 见「多方案必须先让用户选」+「缩略图必须带 UA」 |
| 3 取 ID | 浏览器打开 + `design-id.py` | 见上一节 |
| 4 校对 | `read-design({design_id, filter:{fields:[...]}})` | `fields` ∈ `design_metadata` / `page_metadata` / `design_content` / `thumbnails` / `presenter_notes` |
| 5 导出 | `get-export-formats` → `export-design` | 先查格式，再导 |
| 6 落地 | `curl -sL "<job.urls[0]>" -o out.png` | signed URL **会过期**，拿到就立刻下 |

`generate-design` 一次给 4 个候选，慢（十几秒到一分钟级），别设短超时。
**这 4 个必须全部给用户过目，等用户挑一个再取 ID 导出。**

### 导出参数

`get-export-formats` 返回 `{"formats":{"pdf":{},"jpg":{},"png":{},"pptx":{},"gif":{},"mp4":{}}}`。

```
export-design({design_id, format: {type:"png", lossless:true}})
```

`format.type` ∈ `pdf|png|jpg|gif|pptx|mp4|csv`。其余可选键：
`as_single_image`(png 多页合成一张)、`transparent_background`、`export_quality`(`regular|pro`)、
`size`(pdf: `a4|a3|letter|legal`)、`width`/`height`、`lossless`、`quality`、`pages`(1-based)。

返回 `{"job":{"id","status":"success","urls":["https://export-download.canva.cn/..."]}}`。
那串 URL 带 `X-Amz-Expires`（实测 7 万秒级，约 20 小时），**过期只能重新导出**。
下载不需要特殊 UA。

## 缩略图必须带 UA

`https://www.canva.cn/api/short/<thumb_id>` 用 curl 默认 UA 一律 `403`，返回 754801 字节的
Cloudflare 页冒充图片。必须伪装：

```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0" \
     -H "Referer: https://www.canva.cn/" \
     "https://www.canva.cn/api/short/<thumb_id>" -o cand.png
```

下完用 PIL 验证是真图（`Image.open(...).size`），别直接把 403 页当图交付。

## 改图：事务制，不 commit 等于没改

编辑是事务，`edit-design` 同时承担「应用操作」和「提交/丢弃」：

1. `read-design({design_id, open_transaction: true, filter:{fields:["design_content"]}})`
   → 拿 `transaction_id`，同时拿到元素的 `locator_id`
2. `edit-design({transaction_id, page_index, operations:[...], finalize:"keep_open"})`
   → 应用操作并保持事务打开
3. `edit-design({transaction_id, finalize:"commit"})` → **真正落盘**；`"cancel"` 丢弃

`operations[].type` 常用：`replace_text`({locator_id,text})、`find_and_replace_text`
({locator_id,find_text,replace_text})、`update_fill`({locator_id,asset_type,asset_id,alt_text})、
`format_text`({locator_id,formatting})、`add_text`、`resize_element`、`position_element`、
`insert_shape`、`replace_shape`、`recolor_element`、`rotate_element`、`crop_media`、
`add_page`、`delete_element`、`reorder_page`、`replace_speaker_notes`。
`page_index` 是 **1-based**。

官方要求：commit 前给用户看预览、拿到明确同意。`finalize:"commit"` 不可撤销。

**本机实跑确认的行为**：`open_transaction:true` 确实回传 `{"transaction":{"transaction_id":"5628896162629615140"}}`；
`keep_open` 回 `{"status":"edits_unverified", "thumbnail_urls":[...], "document":{...},
"edit_operation_results":[{"status":"applied_unverified"}]}`，并附 `next_required_action` 要求
**先比对改前/改后缩略图再动手**；`{"finalize":"cancel","operations":[]}` 回 `{"status":"cancelled"}`，设计无损。

**每个 `keep_open` 都要照它说的做**：把返回的 `thumbnail_urls[0]` 下载下来看一眼
（这些 signed URL 不需要 UA），确认没有误改，再决定继续还是 commit。别连着盲改。

`add_text` / `insert_shape` 这类**新建元素**要传 `page_id`（就是 `design_content.pages[0].id`，
形如 `PBcBxnvRx70Hn9WY`），不是 `locator_id`；改已有元素才用元素级 `locator_id`。

## 尺寸适配

`resize-design({design_id, design_type})`，`design_type` 两种形态：

```
{type:"preset", name:"presentation"|"whiteboard"}
{type:"custom", width:1080, height:1080}
```

生成**新**设计、原设计不动。`doc` / `email` 预设不支持。

## 权限与限制

- `resize-design` 的完整能力、`autofill-design`、`*brand-template*` 系列**需 Canva Pro**；
  当前账号 `list-brand-kits` 返回 `{"items":[]}`，品牌模板走不通。
- `upload-asset-from-url` 只吃**公网 HTTPS**。本机文件先托管到可公开访问的地址，
  或改用编辑器手工上传。素材率限制约 30 次/分。
- `generate-design` 约 20 次/分，`export-design` 约 20 次/分，`generate-image` 约 10 次/分。
- `get-logged-in-account-details` 虽在 tools/list 里，但调用必报
  `MCP error -32602: Tool get-logged-in-account-details not found`。**别用它验收连接**，
  用 `search-designs` 或 `list-brand-kits`。
- `search-designs` 返回的 `design_id` 是真的 11 位 ID，可以直接拿去 read/export，
  这是绕开「suggestion 链接」麻烦的干净入口。
- `edit_url` / `view_url` 是网页地址，不是 `design_id`，混用会报上面那两条错误。

## 验收连接的最小动作

```
search-designs({limit:3})
```

返回真实设计条目（含 11 位 `design_id`、`edit_url`、缩略图）就说明全链路通了。

## 出问题怎么查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `Must be a design ID or a full Canva design share URL` | 传了 suggestion 链接或 view_url | 用 `design-id.py` 取真 ID |
| `String must contain exactly 11 character(s)` | 同上，短了 | 同上 |
| 缩略图 403 / 图片打不开 | 缺浏览器 UA | 加 UA + Referer |
| 导出的 PNG 一片空白 | 拿到的 ID 不对（可能就是 suggestion）或设计本身空 | 打开 `canva.cn/design/<id>` 核对 |
| `Tool get-logged-in-account-details not found` | 该工具在服务端缺失 | 换 `search-designs` 验收 |
| 连接 `unhealthy` | OAuth 过期且刷新失败 | `reconnect`，必要时重走 OAuth |
| 授权页打不开 / 302 到 canva.cn | 用了国际版 `mcp.canva.com` | 必须是 `mcp.canva.cn` |

大陆 IP 访问 `www.canva.com` 会被 302 到 `canva.cn`，**国际版 MCP 这条路根本走不通**；
本机用的是国内镜面 `mcp.canva.cn`。若连接被删需重建，参照记忆：自建连接器描述
（`id: canva-cn`, `auth.mode: oauth2-pkce`, `issuer: https://mcp.canva.cn`,
`servers[0].url: https://mcp.canva.cn/mcp`, `serverKey/serverName: canva`,
`transport: streamable-http`, `headers:{"Accept":"application/json, text/event-stream"}`）
经 `installFromUrl` 安装，会走 DCR + PKCE + loopback 回调，需要在浏览器点一次「允许」。
