# LabOps

**实验室资源管理与智能运营平台**。这是一个以 Python 后端、Agent 工具调用和 RAG 检索为重点的应用项目：学生查询资源并申请预约，管理员审核与管理资源；AI 助手可以查询真实业务数据，并在用户明确确认后提交受控预约。

> 本仓库只提供源码、数据库迁移和合成测试样例；不包含真实账号、业务数据、私有知识文档、API Key 或 Docker 镜像。

## 技术栈

| 层次 | 技术 | 用途 |
| --- | --- | --- |
| 前端 | Vue 3、Vite、Element Plus、Axios、Vue Router | 学生与管理员界面、AI 流式交互 |
| 后端 | Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x | API、输入校验、业务服务、事务控制 |
| 数据 | PostgreSQL、pgvector、Alembic | 业务持久化、向量存储、Schema 迁移 |
| Agent | LangGraph、LangChain、OpenAI-compatible LLM、SSE | 工具编排、受控业务操作、流式事件 |
| RAG | 现有 Embedding API、PostgreSQL 全文检索、RRF | 文档向量化、混合召回、来源追踪 |
| 工程 | JWT、bcrypt、RBAC、pytest、Docker Compose、Nginx | 身份与权限、验证、可复现运行 |

## 核心设计

### 预约与设备维护

实验室预约与设备预约分别判断冲突。提交申请时，在 PostgreSQL 事务中锁定对应资源行，再检查时段重叠；待审核、已通过和使用中的预约占用资源，已拒绝和已取消的预约不占用资源。预约支持审核、取消、签到、签退、完成，以及预约结束仍未签到的异常处理。

学生可以申报设备故障并查看自己的工单；管理员可以查看全部工单、开始维修和完成维修。故障会使设备不可预约，并中断受影响的预约；维修完成后恢复设备状态。通知、审计与运营统计基于持久化业务记录生成。

### Agent：工具结果与业务写入分离

LangGraph 单 Agent 通过 Service 层工具查询实验室、设备、预约、维修状态、知识库和运营统计。前端通过 SSE 接收模型内容、工具开始与结束、错误和结构化预约预览。

自然语言预约遵循以下边界：

```text
用户提出需求 → Agent 调用工具 → 工具返回结构化预览
                                  ↓
                      用户核对并点击确认
                                  ↓
            后端重新校验用户、参数、有效期与资源冲突 → 写入预约
```

模型的文字回复不会直接创建预约。确认凭证只保存哈希，绑定用户和预约参数，有五分钟有效期；重复确认返回同一预约。请求 ID、工具执行结果与耗时用于定位一次 Agent 调用，模型提供用量时才记录 token 数。

### RAG：混合检索与可追溯来源

知识索引支持 Markdown、TXT、PDF、DOCX、XLSX、PPTX。文档经过解析、清洗、分块后，按内容哈希增量更新，并保留版本、文件来源和分块位置。检索结合 pgvector 向量距离、PostgreSQL 全文检索与 RRF 排序，支持 Top-K 与来源追踪。

当前 4096 维向量使用**精确余弦排序**；全文检索使用 GIN 索引。仓库提供合成文档和固定评测问题，用于计算 Recall@K、Precision@K、MRR、无答案拒答率和延迟。合成评测结果不能替代实际知识语料的质量验收。

## 源码结构

```text
lab-agent/
  backend/
    app/api/             # FastAPI 路由
    app/services/        # 预约、Agent、RAG 等业务服务
    app/models/          # SQLAlchemy 模型
    app/fixtures/        # 合成文档与固定评测集
    app/scripts/         # 索引、迁移与隔离验收工具
    migrations/          # Alembic 版本
    tests/               # pytest 测试
  frontend/
    src/views/           # 学生端与管理员端页面
    src/api/             # HTTP 接口封装
compose.yaml             # 本地部署配置；无需向 Docker Hub 发布镜像
```

## 本地开发

准备 Python 3.12、Node.js 22.18+、PostgreSQL 和 pgvector。使用**全新、可丢弃的开发数据库**；数据库管理员先启用 `vector` 扩展。不要将下面的迁移命令直接用于已有业务数据库。

```bash
cd lab-agent/backend
cp .env.example .env
# 在 .env 中设置开发数据库 DATABASE_URL 和 JWT_SECRET_KEY；AI 功能另需现有模型与 Embedding 配置
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

另开终端启动前端。Vite 开发代理会将 `/api` 和 `/uploads` 转发给本地后端：

```bash
cd lab-agent/frontend
npm ci
npm run dev
```

未配置 LLM/Embedding Key 时，普通资源与预约功能仍可运行，AI 对话和向量索引不可用。`lab-agent/backend/data/kb/` 默认不随仓库分发；索引任何本地文档前，应确认其允许发送到所配置的第三方 Embedding 服务。

## 验证

```bash
cd lab-agent/backend
.venv/bin/pytest -q

cd ../frontend
npm run build
```

pytest 中的 SQLite 单元测试与真实 PostgreSQL 验收分开。`app.scripts.postgres_acceptance` 在已核实的 `labops` 测试集群中使用固定名称的临时数据库，检查 Alembic、并发预约、确认幂等、跨用户权限与维修闭环；若同名数据库已存在则拒绝覆盖。CI 配置见 `.github/workflows/verify.yml`。可选的 `--live-ai` 仅使用合成文档调用当前模型与 Embedding 服务，不会索引本地私有文档。

## 数据与仓库边界

原始 MySQL 数据、PostgreSQL 持久化卷、`.env`、上传文件、备份和本地知识文档都不属于本仓库。迁移工具不会在应用启动时自动导入历史数据；使用它们前必须识别源库与目标库，并完成备份及恢复验证。请勿使用 `git add -f` 强行加入被忽略的本地数据。
