# canva-skill

给 [DeepSeek Harness](https://github.com/deepseek-ai) 用的 **Canva 可画**操作技能。装了之后，直接说「做一张海报」就能走完 **生成 → 挑图 → 取 design_id → 导出 PNG/PDF** 全流程。

## 这个仓库解决什么问题

Canva 官方 MCP 端点（`https://mcp.canva.com/mcp`）在中国大陆**不可用**——OAuth 同意页在 `www.canva.com`，会被 302 到 `canva.cn`，授权链断在中间。好在 Canva 中国版有完整可用的镜像端点 `https://mcp.canva.cn/mcp`，支持动态客户端注册（DCR）+ PKCE + loopback 回调，不需要开发者门户、不需要 client secret。

接通之后还有两个坑，这个技能主要就是在填这两个坑：

1. **`generate-design` 返回的链接不是 design_id。** `https://www.canva.cn/d/V5U4YghpJDrT-oA` 里的 slug 拿去调任何工具都会报错，真 ID 是 11 位的 `DAHbMx4Ch24`，只有在登录态浏览器里打开链接、从地址栏才能拿到。`scripts/design-id.py` 从浏览器 History 里把它刮出来。
2. **编辑是事务制的。** 不 commit 等于没改，而且每次 `keep_open` 都要先比对改前/改后缩略图再动手。

## 安装

把 `canva/` 整个目录放到 DSH 的技能目录：

```bash
# Windows
xcopy /E /I canva "%USERPROFILE%\.dsh\skills\canva"

# macOS / Linux
cp -r canva ~/.dsh/skills/canva
```

重启 DSH 后，`available-skills` 里会出现 `canva`，说「做张海报」就会自动加载。

## 先接通 MCP

技能只是操作手册，底下需要 `mcp.canva.cn` 这条连接。用 `dsh-mcp-connector` 装一条自定义连接器描述：

```json
{
  "id": "canva-cn",
  "name": "Canva 可画（中国版）",
  "vendor": "Canva",
  "category": "设计创意",
  "auth": {
    "mode": "oauth2-pkce",
    "issuer": "https://mcp.canva.cn",
    "scope": "",
    "clientName": "DeepSeek Harness - Canva MCP",
    "tokenEndpointAuthMethod": "none",
    "grantSharing": "connector"
  },
  "servers": [{
    "serverKey": "canva",
    "serverName": "canva",
    "url": "https://mcp.canva.cn/mcp",
    "transport": "streamable-http",
    "headers": { "Accept": "application/json, text/event-stream" }
  }]
}
```

把它托管到一个本地 HTTP 地址，然后用连接器的 `installFromUrl` 安装（`oauth2-pkce` 卡片会自动触发授权流程）。浏览器里点一次「允许」即可，token 四小时有效、过期自动用 refresh_token 续。

装好后 `mcp_connector_status` 应显示 `canva-cn-canva | healthy`，29 个 `mcp__canva__*` 工具可用。

## 用法

```
做一张 AI 技术分享会的海报，深色底，极简风格
```

`generate-design` 一次给 4 个候选，技能会**全部下载缩略图编号列出来让你选**，选完才取 ID 导出——不会自己替你定，也不会提前把 4 个都导出浪费配额。

想直接操作已有设计：

```
把这版海报标题改成「实战分享会」，日期改成 2026.11.20
```

## scripts/design-id.py

从 Edge / Chrome 的浏览历史里找出最近打开过的 Canva 设计 ID。纯标准库，不需要装依赖。

```bash
python scripts/design-id.py              # 最新一个
python scripts/design-id.py --all        # 全部，新→旧
python scripts/design-id.py --within 10 --browser chrome
python scripts/design-id.py --check      # 只看 History 能不能读
```

浏览器会锁着 History 文件，脚本走的是「复制快照 + sqlite 只读」。拿不到 ID 时退出非零并提示——通常意味着链接撞了登录墙或被地区拦截，不是脚本坏了。

## 已知限制

- `resize-design` 的完整能力、`autofill-design`、`*brand-template*` 系列**需要 Canva Pro**。
- `upload-asset-from-url` 只接受公网 HTTPS 地址。
- `get-logged-in-account-details` 虽在 tools/list 里，调用必报 `-32602 not found`，别拿它验收连接，用 `search-designs`。
- 导出的 signed URL 带 `X-Amz-Expires`（约 20 小时），过期只能重新导出。

## License

MIT
