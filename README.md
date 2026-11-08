# 智课共生 CoLesson

> AI 互动智课生成与实时问答系统 —— 传智杯 · AI WEB 网页开发挑战赛 参赛作品

![Java](https://img.shields.io/badge/Java-17-blue) ![Spring Boot](https://img.shields.io/badge/Spring%20Boot-2.7-green) ![Python](https://img.shields.io/badge/Python-3.10+-yellow) ![FastAPI](https://img.shields.io/badge/FastAPI-0.1xx-009688) ![Vue](https://img.shields.io/badge/Vue-3.x-42b883) ![License](https://img.shields.io/badge/License-MIT-lightgrey)

**智课共生** 是面向高校教学场景的 AI 教学平台：教师上传 PPT 即可生成讲稿并发布为班级智课；学生获得基于个人画像与本地知识库（RAG）的讲义、习题、知识图谱、拓展阅读、实战演练与 AI 视频讲解；管理端提供数据大盘、内容治理、智能体编排与系统配置的全链路运营能力。

---

## ✨ 功能特性

### 教师端
- PPT 上传解析 → 讲稿生成（AI/本地模板双通道）→ 保存为智课项目
- 班级管理：邀请码入班、作业布置与批改、公告、签到
- 智课发布到班级（仅本班可见）、学情回看

### 学生端（SPA）
- 画像构建：六维学习画像诊断，驱动个性化生成
- 资源中心 / 资源广场：多模态资源浏览与知识星图
- 智能答疑：流式回答 + 知识库引用溯源
- 学习路径、学习数据、实战演练自测（作答草稿 / 对照参考答案 / 自评）

### 管理端
- 数据大盘：KPI、平台趋势、功能使用占比、热门知识点 TOP10
- HUD 控制台：全屏可视化（粒子协作网络 + 实时事件流 + 异常监控）
- 内容治理：资源审核发布、生成内容管理、文档审核、内容安全（敏感词 + 事实校验）
- 账号与配置：用户/管理员账号、菜单权限、画像维度、学习路径、智能体定义、系统参数（LLM Key 热配置）

---

## 🧱 技术栈与架构

```
浏览器（三端）
   │  http://127.0.0.1:8082
   ▼
┌──────────────────────── Spring Boot 宿主 :8082 ────────────────────────────┐
│  教师端多页应用 · 学生/管理端 SPA 静态资源 · 认证/班级/作业/项目 API        │
│  ZhixuetiProxyFilter：/api/v1/* 反向代理 → 内部 FastAPI                     │
│  ZhixuetiAuthBridge：登录后按身份同步账号（X-Host-Secret 桥接）             │
│  ZhixuetiBackendLauncher：随宿主自动拉起 FastAPI 进程                       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌──────────────────────── FastAPI 智学体 :8000 ──────────────────────────────┐
│  多智能体编排（8 Agent 流水线） · RAG（ChromaDB 向量检索）                  │
│  LLM 网关（DeepSeek / 通义千问 / 星火 / mock 多级降级） · 内容安全校验      │
│  存储：SQLite（USE_SQLITE）或 MySQL                                        │
└───────────────────────────────────────────────────────────────────────────┘
```

| 层 | 技术 |
|---|---|
| 宿主 | Java 17 · Spring Boot 2.7 · OkHttp · BCrypt |
| AI 服务 | Python 3.10+ · FastAPI · SQLAlchemy · ChromaDB · fastembed |
| 前端 | Vue 3 · TypeScript · Element Plus · ECharts · Vite |
| 存储 | MySQL（可选）/ JSON 文件（宿主）+ SQLite（AI 服务） |

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| JDK | 17+ | 宿主服务构建与运行 |
| Maven | 3.8+ | 宿主构建（或使用 IDEA 自带） |
| Python | 3.10 – 3.12 | AI 服务 |
| Node.js | 18+ | 前端构建（仅需改前端时） |
| MySQL | 8.x（可选） | 不配置时自动回退 JSON/SQLite 存储 |

### 1. 获取代码

```bash
git clone https://github.com/<你的账号>/colesson.git
cd colesson
```

### 2. 配置 AI 服务

```bash
cd zhixueti-backend
copy .env.example .env      # Windows；macOS/Linux 用 cp
# 编辑 .env：填入 DEEPSEEK_API_KEY（或其他 LLM Key）
# 未配置任何 Key 时自动使用本地 mock 模板，全流程仍可运行（输出带演示水印）
```

### 3. 安装 AI 服务依赖

```bash
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt     # Windows
# source venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

### 4. 构建 & 启动

```bash
# 方式一：一键（Windows）
start.bat

# 方式二：手动构建并运行（推荐）
mvn -q -DskipTests package
java -jar target/ai-teacher-1.0-SNAPSHOT.jar
```

启动后打开 **http://127.0.0.1:8082** —— FastAPI 会随宿主自动拉起，无需单独启动。

### 5. 默认账号

| 端 | 账号 | 密码 | 说明 |
|---|---|---|---|
| 管理端 | `lyc` | `admin123` | 超级管理员（首次部署后请修改） |
| 学生端 | 注册即可 | — | 或使用 `stu01 / Demo2026`（需先执行账号初始化脚本） |

> 管理员账号初始化：`cd zhixueti-backend && PYTHONPATH=. venv/Scripts/python scripts/ensure_admin_lyc.py`

---

## ⚙️ 环境配置说明（zhixueti-backend/.env）

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 推荐 | DeepSeek 密钥；未填时回退 mock 提供商 |
| `LLM_DEFAULT_PROVIDER` | 否 | `deepseek` / `qwen` / `spark` / `mock`（默认按可用 Key 自动选择） |
| `LLM_FALLBACK_PROVIDER` | 否 | 主提供商失败时的兜底（默认 `mock`） |
| `JWT_SECRET_KEY` | **必填** | 学生端 JWT 签名密钥；留用默认值时服务拒绝启动 |
| `HOST_BRIDGE_SECRET` | **必填** | 宿主↔AI 服务桥接共享密钥，需与宿主 `zhixueti.bridge-secret` 一致 |
| `USE_SQLITE` | 否 | `true` 时 AI 服务使用 SQLite（默认），否则 MySQL |
| `KB_ENABLED` / `LOCAL_KB_DIR` | 否 | 本地向量知识库开关与语料目录 |
| `HF_HUB_OFFLINE` | 否 | `1` 时离线运行，跳过 fastembed 联网下载 |

宿主侧配置：`config/application-local.properties`（参考 `config/application-local.properties.example`，含 MySQL 连接与 `zhixueti.bridge-secret`）。

---

## 📁 目录结构

```
CoLesson-V2/
├── src/main/java/com/contest/      # Spring Boot 宿主（认证/班级/项目/反代/桥接）
├── src/main/resources/static/      # 教师端多页应用 + 学生/管理端 SPA 入口
├── zhixueti-frontend/              # 学生/管理端 SPA 源码（Vue3 + TS）
├── zhixueti-backend/               # FastAPI：多智能体/RAG/LLM 网关
│   ├── app/agents/                 #   8 个智能体定义与编排
│   ├── app/llm/                    #   LLM 网关与多提供商
│   ├── app/security/               #   事实校验/内容安全
│   └── scripts/                    #   管理员初始化等脚本
├── deploy/                         # 部署套件（打包脚本/systemd/验证脚本）
├── docs/                           # 项目文档与答辩材料
└── data/                           # 运行数据（不入库）
```

---

## 📋 主要 API

| 模块 | 路径 | 说明 |
|---|---|---|
| 认证 | `POST /auth/login` · `POST /api/v1/auth/login` | 宿主会话 / 学生端 JWT |
| 资源生成 | `POST /api/v1/resources/generate` | 多智能体流水线（SSE 进度） |
| 知识库 | `GET /api/v1/kb/search` · `POST /api/v1/kb/reindex` | 向量检索 / 重建索引 |
| 智能体 | `GET /api/v1/agents/definitions` · `PUT /api/v1/agents/definitions/{code}` | 定义与配置 |
| 管理 | `/api/v1/admin/*` · `/admin-api/*` | 内容治理 / 宿主运维 |

---

## 📐 代码规范

- **通用**：`.editorconfig`（UTF-8 / LF / 缩进：Java·Python 4 空格，其余 2 空格）
- **前端**：`.prettierrc.json`；组件组合式 API（`<script setup>`）
- **Java**：类名大驼峰、方法小驼峰、常量大写；Controller 只做参数校验与编排
- **Python**：PEP 8；服务层负责业务，仓储层负责持久化
- **提交信息**：`feat|fix|docs|chore|refactor(scope): 描述`，如 `feat(rag): 知识库引用入库`
- 提交前自检：`mvn -q -DskipTests package`（宿主）+ `npm run build`（前端）+ `python -m compileall app`（AI 服务）

---

## 🧪 常见问题

- **启动后 /student 打不开？** 等 30–60 秒，宿主就绪后会自动拉起 FastAPI（日志出现「智学体已随宿主启动」）。
- **知识库检索为空？** 确认 `KB_ENABLED=true` 且 `zhixueti-backend/data/knowledge/raw/` 有语料；或调 `POST /api/v1/kb/reindex` 重建。
- **生成内容带「演示模式」水印？** 未配置 LLM Key，属预期降级行为；配置 Key 后同一条流水线输出真实 AI 内容。
- **MySQL 连接失败？** 检查 `config/application-local.properties`；不配置也可运行（JSON/SQLite 兜底）。

---

## 📄 License

[MIT](LICENSE) © 智课共生团队
