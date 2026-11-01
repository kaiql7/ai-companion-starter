# 从零写出 AI 伴侣全栈项目

参考项目：`E:\PycharmProjects\ai-companion-starter`

目标不是一口气复制现成代码，而是建立一个可以反复使用的 AI 应用开发骨架：

```text
浏览器页面
  → HTTP 请求
  → FastAPI 路由
  → Pydantic 参数校验
  → 业务服务
  → 模拟模型 / DeepSeek
  → SQLAlchemy
  → SQLite / MySQL
```

现有项目已经通过 `5` 个接口测试。学习时建议新建一个目录，例如 `my-companion`，每个阶段都让项目保持“能运行、能验证”。

---

## 先理解每个文件为什么存在

| 文件或目录 | 责任 | 不应该负责什么 |
|---|---|---|
| `run.py` | 启动 Uvicorn | 不写聊天业务 |
| `app/main.py` | 定义 HTTP 路由、组装依赖 | 不直接拼 SQL |
| `app/schemas.py` | 定义请求和响应的数据格式 | 不保存数据 |
| `app/services.py` | 编排聊天、安全检查、历史读取 | 不生成 HTML |
| `app/llm.py` | 封装 Mock 和 DeepSeek | 不访问数据库 |
| `app/models.py` | 定义数据库表 | 不处理 HTTP |
| `app/db.py` | 创建数据库引擎和会话 | 不写业务判断 |
| `app/prompts.py` | 保存提示词和安全文案 | 不执行网络请求 |
| `app/static/index.html` | 页面结构、样式和交互 | 不保存 API Key |
| `tests/test_api.py` | 验证完整 API 行为 | 不消耗真实模型额度 |

这就是**分层**：每层只做一类事情。项目变大后，分层能避免所有代码都堆进 `main.py`。

---

## 阶段 1：先让一个 FastAPI 服务跑起来

### 创建环境

```powershell
cd E:\PycharmProjects
mkdir my-companion
cd my-companion
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi "uvicorn[standard]"
```

创建：

```text
my-companion/
├── app/
│   ├── __init__.py
│   └── main.py
└── run.py
```

`app/main.py` 先只写一个健康检查：

```python
from fastapi import FastAPI

app = FastAPI(title="My Companion")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`run.py`：

```python
import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
```

启动：

```powershell
python run.py
```

访问：

- `http://127.0.0.1:8765/health`
- `http://127.0.0.1:8765/docs`

### 本阶段验收

1. `/health` 返回 `{"status":"ok"}`。
2. `/docs` 能看到自动接口文档。
3. 修改 `main.py` 后，服务能自动重新加载。

### 本阶段知识点

- FastAPI 创建 Web API。
- Uvicorn 真正监听端口并处理 HTTP 请求。
- `reload=True` 只适合开发环境。
- FastAPI 的 `/docs` 是根据路由和类型自动生成的。

---

## 阶段 2：先定义接口，再写实现

不要一开始就在路由中随便接收字典。先规定聊天接口收什么、返回什么。

创建 `app/schemas.py`：

```python
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    provider: str
    safety_triggered: bool = False
```

在 `main.py` 中先返回一个模拟响应：

```python
from app.schemas import ChatRequest, ChatResponse


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return ChatResponse(
        conversation_id=1,
        reply=f"我收到了：{payload.message}",
        provider="mock",
    )
```

### 本阶段验收

在 `/docs` 中调用 `POST /api/chat`：

```json
{"message": "今天有点累"}
```

应该得到结构化响应。输入空字符串或超过 4000 字时，应得到 `422`。这不是你手写的错误，而是 Pydantic 自动校验的结果。

### 本阶段知识点

- 请求模型和响应模型是前后端之间的“数据合同”。
- `response_model` 会过滤和校验返回数据。
- `conversation_id` 为空代表新对话，有值代表继续旧对话。

---

## 阶段 3：先把模型替换成 Mock

不要在项目还没跑通时就接入真实 API。先定义统一的模型接口：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


class LLMClient(ABC):
    provider: str

    @abstractmethod
    def complete(self, messages: Sequence[ModelMessage]) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    provider = "mock"

    def complete(self, messages: Sequence[ModelMessage]) -> str:
        latest = messages[-1].content if messages else ""
        return f"我在听。你刚才说的是：{latest}"
```

路由改成依赖抽象接口，而不是写死某个模型：

```python
llm = MockLLMClient()


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    reply = llm.complete([
        ModelMessage(role="user", content=payload.message)
    ])
    return ChatResponse(
        conversation_id=1,
        reply=reply,
        provider=llm.provider,
    )
```

### 为什么值得多写这层

以后可以无缝增加：

- DeepSeek 客户端；
- 本地 Ollama；
- 其他兼容聊天接口的模型；
- 测试用固定回复客户端。

路由不需要知道模型的 HTTP 地址、密钥格式和错误结构。

完整实现见参考项目的 `app/llm.py`。

---

## 阶段 4：加入数据库与业务服务

先设计数据关系：

```text
conversations 1 ───── N messages
```

- `conversations`：一段对话。
- `messages`：这段对话中的每条用户或助手消息。
- 删除会话时，级联删除它的消息。

建议字段：

```text
conversations:
  id, title, created_at, updated_at

messages:
  id, conversation_id, role, content, created_at
```

安装：

```powershell
python -m pip install "sqlalchemy>=2.0,<3"
```

这一步的实现顺序是：

1. `app/db.py`：创建 `Engine`、`Base` 和 `Session`。
2. `app/models.py`：定义 `Conversation` 和 `Message` 表。
3. 应用启动时执行 `create_all()`。
4. `app/services.py`：把“创建会话、保存消息、获取历史”等业务操作串起来。
5. `app/main.py`：路由只负责接收 HTTP 请求和调用服务。

聊天服务应完成以下流程：

```text
收到 ChatRequest
  → 查找或创建 conversation
  → 保存用户消息
  → 读取最近历史
  → 添加 system prompt
  → 调用 LLM
  → 保存助手消息
  → 返回结构化结果
```

为什么只读取最近历史？因为不能无限把全部消息交给模型，否则请求会越来越长、越来越慢、越来越贵。参考项目使用 `HISTORY_LIMIT` 控制上限。

### 本阶段验收

1. 第一次发送消息后，数据库出现一个会话和两条消息。
2. 带着 `conversation_id` 再发送消息，数据加入同一会话。
3. `GET /api/conversations/{id}` 能按时间返回完整历史。
4. 删除会话后，它的消息也一起删除。

数据库层完整实现见：

- `app/db.py`
- `app/models.py`
- `app/services.py`

---

## 阶段 5：写一个最小聊天页面

页面第一版不要追求漂亮，先打通浏览器与 API。

核心 JavaScript：

```javascript
let conversationId = null;

async function sendMessage(content) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      message: content,
      conversation_id: conversationId
    })
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }

  conversationId = data.conversation_id;
  return data.reply;
}
```

FastAPI 用 `FileResponse` 提供首页：

```python
from pathlib import Path
from fastapi.responses import FileResponse


STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
```

页面需要处理四种状态：

1. 健康检查中；
2. 等待模型回复；
3. 正常回复；
4. 请求失败或触发安全回复。

### 本阶段验收

- 浏览器能显示页面。
- 输入消息后出现用户气泡。
- 请求期间按钮禁用，避免重复提交。
- 收到响应后显示助手气泡。
- 请求失败时显示错误，而不是页面无反应。

完整页面见 `app/static/index.html`。

---

## 阶段 6：接入真实 DeepSeek

安装 HTTP 客户端：

```powershell
python -m pip install "httpx>=0.27,<1" "python-dotenv>=1.0,<2"
```

创建 `.env`：

```dotenv
LLM_MODE=deepseek
DEEPSEEK_API_KEY=你的真实Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DATABASE_URL=sqlite:///./companion.db
HISTORY_LIMIT=20
```

服务端读取：

```python
api_key=os.getenv("DEEPSEEK_API_KEY", "").strip()
```

发送请求：

```python
response = httpx.post(
    f"{base_url}/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
    },
    timeout=40,
)
response.raise_for_status()
data = response.json()
reply = data["choices"][0]["message"]["content"]
```

必须处理：

- 超时；
- HTTP 状态错误；
- 网络不可达；
- 返回 JSON 无法解析；
- 返回内容为空。

把这些异常转换成自己的 `LLMError`，再由 FastAPI 返回明确的错误状态，例如 `502`。

### API Key 规则

- 只放在服务端 `.env` 或环境变量中。
- 不能写进 `index.html`。
- 不能提交到 Git。
- `.gitignore` 必须有 `.env`。

完整客户端见参考项目的 `app/llm.py`。

---

## 阶段 7：提示词、安全边界和测试

### 提示词

`app/prompts.py` 应该明确：

- 助手不是人类；
- 不进行医学或心理诊断；
- 不制造依赖；
- 不索取无关敏感信息；
- 危机场景应该引导求助。

提示词不是“越热情越好”。AI 陪伴产品尤其需要明确边界。

### 安全检查

参考项目在调用模型前检查明显的危机关键词，并直接返回求助文案。这是教学演示，不是完整的心理危机识别系统，不能作为真实产品的唯一安全措施。

### 自动测试

```powershell
python -m pip install "pytest>=8,<9"
python -m pytest -q
```

至少测试：

1. 健康检查返回 `200`；
2. 新消息创建会话；
3. 第二轮消息进入同一会话；
4. 空消息返回 `422`；
5. 不存在的会话返回 `404`；
6. 危机输入不调用模型；
7. 模型超时返回明确错误；
8. 删除后历史不可再查询。

当前参考项目的实际测试结果是：

```text
5 passed
```

---

## 推荐的七天实现顺序

| 天数 | 当天目标 | 完成标志 |
|---|---|---|
| 第 1 天 | FastAPI、Uvicorn、健康检查 | 浏览器看到 `/health` 和 `/docs` |
| 第 2 天 | Pydantic 请求与响应模型 | 非法输入自动返回 `422` |
| 第 3 天 | Mock 模型与服务分层 | `POST /api/chat` 返回模拟回复 |
| 第 4 天 | SQLAlchemy 表与数据库会话 | 两次消息写入同一会话 |
| 第 5 天 | 原生 HTML、CSS、JavaScript | 页面完成真实请求和错误显示 |
| 第 6 天 | DeepSeek、环境变量和异常处理 | 页面顶部显示 DeepSeek 已连接 |
| 第 7 天 | 提示词、安全检查、自动测试 | 测试全部通过 |

每天只增加一个主要能力，并保留一个可运行版本。不要先一次性写完全部文件。

---

## 遇到问题时按这个顺序排查

### 页面打不开

1. 终端是否有 `Uvicorn running`？
2. 地址和端口是否一致？
3. 进程是否已经退出？
4. 是否被其他程序占用了端口？

### `/docs` 能打开，但聊天失败

1. 在 `/docs` 直接调用 `POST /api/chat`。
2. 查看浏览器开发者工具的 Network 响应。
3. 再查看终端服务端错误。
4. 最后才检查模型 API。

### DeepSeek 失败

1. `LLM_MODE` 是否为 `deepseek`？
2. 环境变量是否在启动服务的同一个进程里？
3. Key 是否有余额和正确权限？
4. 模型名称是否有效？
5. 网络是否能够访问 API 地址？

### 数据库没有数据

1. 当前工作目录是否正确？
2. `DATABASE_URL` 指向哪个文件？
3. 请求是否真的提交成功？
4. 事务是否执行了 `commit()`？

---

## 写完基础项目后，怎样继续提升

优先级建议：

1. 错误处理：模型超时、空返回和重复提交。
2. 对话列表：显示最近会话。
3. 人设选择：学习教练、倾听者、树洞等。
4. 历史摘要：长对话先压缩旧消息。
5. 调用预算：每日次数和 Token 上限。
6. 用户认证：每个用户只能看到自己的会话。
7. 数据库迁移：使用 Alembic，而不是依赖 `create_all()`。
8. 部署：日志、监控、备份、HTTPS 和速率限制。

当项目只有本地 SQLite、没有登录、没有速率限制时，不要直接公开到互联网。

