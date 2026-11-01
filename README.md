# 小伴：AI 智能伴侣 Starter

这是“AI 应用全栈开发基础”阶段的配套项目。它把以下知识放进一条完整链路：

```text
浏览器
  → HTTP + JSON
  → FastAPI 参数校验
  → 对话服务
  → DeepSeek / 模拟模型
  → SQLAlchemy
  → SQLite / MySQL
```

默认使用模拟模型和 SQLite，不需要 API Key、数据库账号或前端构建工具就能运行。

## 1. 启动

在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

打开：

- 对话页面：<http://127.0.0.1:8765/>
- 自动接口文档：<http://127.0.0.1:8765/docs>
- 健康检查：<http://127.0.0.1:8765/health>

本项目默认使用 `8765` 端口，因为这台电脑的 `8000` 已被 Docker/WSL 服务占用。需要换端口时，可在 `.env` 中增加 `APP_PORT=其他端口`。

## 2. 切换真实 DeepSeek

编辑 `.env`：

```dotenv
LLM_MODE=deepseek
DEEPSEEK_API_KEY=你的真实Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

重启项目后，页面顶部应显示“DeepSeek 已连接”。

DeepSeek 使用 OpenAI 兼容的聊天补全接口。本项目直接使用 `httpx` 发出：

```http
POST https://api.deepseek.com/chat/completions
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

请求体的核心字段是：

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "角色和安全边界"},
    {"role": "user", "content": "用户消息"}
  ],
  "stream": false
}
```

API Key 只能放在服务端环境变量中，不能写进浏览器 JavaScript 或提交到 Git。

## 3. 切换 MySQL

如果已经安装 Docker：

```powershell
docker compose up -d
```

然后修改 `.env`：

```dotenv
DATABASE_URL=mysql+pymysql://companion:companion-password@127.0.0.1:3306/ai_companion?charset=utf8mb4
```

重新启动 FastAPI。首次启动会自动创建 `conversations` 和 `messages` 表。

> 这是教学项目使用的简单建表方式。正式项目应使用 Alembic 管理数据库迁移，不能靠每次启动自动建表解决线上表结构变更。

## 4. 接口

### 新建对话

```powershell
curl.exe -X POST http://127.0.0.1:8765/api/chat `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"今天有点累\"}'
```

返回：

```json
{
  "conversation_id": 1,
  "reply": "……",
  "provider": "mock",
  "safety_triggered": false
}
```

### 继续同一段对话

```json
{
  "message": "主要是学习压力",
  "conversation_id": 1
}
```

### 查询历史

```text
GET /api/conversations/1
```

### 删除对话

```text
DELETE /api/conversations/1
```

## 5. 数据模型

```text
conversations 1 ─── N messages
```

- `conversations` 保存一段对话的标题以及创建、更新时间。
- `messages` 保存每条用户或助手消息。
- `messages.conversation_id` 是外键。
- 删除对话时，ORM 级联删除属于它的消息。

## 6. 代码阅读顺序

1. `app/schemas.py`：用 Pydantic 校验 HTTP 输入输出。
2. `app/models.py`：用 SQLAlchemy 定义数据库表。
3. `app/db.py`：创建引擎和数据库会话。
4. `app/llm.py`：抽象模型客户端，提供模拟和真实两种实现。
5. `app/services.py`：编排对话、历史、安全检查和持久化。
6. `app/main.py`：暴露 FastAPI 路由并组装依赖。
7. `app/static/index.html`：用原生 JavaScript 调用 API。
8. `tests/test_api.py`：验证正常流程、异常和安全分支。

## 7. 运行测试

```powershell
pytest -q
```

测试使用临时 SQLite 文件和模拟模型，不会消耗 DeepSeek 额度。

## 8. 当前实现的边界

- 只保存最近 `HISTORY_LIMIT` 条消息给模型，避免上下文无限增长。
- 未实现用户注册、登录和租户隔离，因此不能直接公开部署。
- 危机词检测只是演示，不应作为真实产品的唯一安全措施。
- 没有速率限制、成本预算、内容审核和可观测性。
- 自动建表只适合学习；正式环境应使用数据库迁移。

## 9. 推荐练习

1. 给 `GET /api/conversations` 增加“最近对话列表”。
2. 给对话增加 `system_persona` 字段，让用户选择“学习教练”或“倾听者”。
3. 使用触发器或服务逻辑实现“超过 30 条后总结旧对话”。
4. 为 DeepSeek 超时、空返回和重复提交写测试。
5. 增加每日调用次数和 Token 预算上限。
6. 添加 `alembic` 迁移，删除自动建表。
7. 加入登录与用户数据隔离后再考虑部署。

更系统的 12 天教学路线见上级目录的《AI应用全栈开发基础-12天学习手册.md》。
