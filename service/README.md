# Plus 授权服务

这是 Plus 的云端授权和任务编排服务。Plus 核心代码只部署在服务端，普通用户不访问私有仓库，也不下载 Plus Skill。

## 数据边界

本服务只接收邀请码兑换信息、项目内容哈希、模块分数、等级、问题严重度/标签、代码行数和修复状态。
它不会接收源码、源码片段、文件内容或本地凭据。精确修复由用户本机 Agent 根据任务在本地完成。

## Cloudflare 部署

```text
npm install -g wrangler
wrangler login
wrangler d1 create architecture-review-plus
# 将返回的 database_id 写入 wrangler.toml
wrangler d1 execute architecture-review-plus --file schema.sql
wrangler secret put TOKEN_SECRET
wrangler secret put ADMIN_TOKEN
wrangler deploy
```

健康检查：`GET /health`。客户端流程：兑换邀请码、上传审计摘要、创建修复任务、轮询任务并回传状态。

管理员生成一次性邀请码（只在响应中显示一次）：

```text
curl -X POST https://your-worker.workers.dev/v1/admin/invites \
  -H "x-admin-token: YOUR_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{"label":"friend-001","maxUses":1}'
```
