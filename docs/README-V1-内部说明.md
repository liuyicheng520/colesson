# CoLesson 智课共生（教师端 + 学生端）

本目录是项目的**唯一代码库与启动目录**（2026-10-25 整合完成）。旧树 `D:\Code\智课共生项目\ai-teacher 5\ai-teacher` 已停止使用，仅作历史存档，其全部有效改动已合并进本目录：

- 后端 Java：以本目录 `src/main/java` 为准（含 2026-10-17 最新的 13 个类）
- 学生端前端 SPA：本目录 `zhixueti-frontend`（含知识图谱视图、展开式顶栏、点击粒子特效、课堂/作业最新改动）
- 教师端多页应用：`src/main/resources/static`（app.css / app.js / teacher/*.html 等）

## 启动方式

### 方式一：一键脚本（需 PATH 里有 JDK 17 和 Maven）
```
start.bat
```
访问 http://127.0.0.1:8082

### 方式二：直接跑已构建的 jar（推荐）
```
"D:\Program_files\Java\jdk-21.0.10\bin\java.exe" -Dfile.encoding=UTF-8 -jar target/ai-teacher-1.0-SNAPSHOT.jar
```
pom 强制 JDK 17，若用 JDK 21+ 构建需加 `-Denforcer.skip=true`（IntelliJ 自带 Maven：
`"D:\Develop_software\JetBrains\IntelliJ IDEA 2025.3.4\plugins\maven\lib\maven3\bin\mvn.cmd" -q -DskipTests -Denforcer.skip=true package`）

## 组件与端口

| 组件 | 端口 | 说明 |
|---|---|---|
| Spring Boot 主应用 | 8082 | 教师端多页应用 + 学生端 SPA + 全部宿主 API |
| 智学体 FastAPI | 127.0.0.1:8000 | `zhixueti.auto-start=true` 时随宿主自动拉起（目录 `zhixueti-backend/`），通过 8082 反代访问 |
| MySQL | 3306 | 默认尝试连接 `zhike_gongsheng` 库；没配密码时自动回退 JSON 文件存储（`data/`） |

## 前端开发

学生端 SPA 源码在 `zhixueti-frontend/`：
```
cd zhixueti-frontend
npm install      # 首次
npm run dev      # 开发（3000 端口，/api 代理到 8000）
npm run build    # 构建并自动同步 dist 到 src/main/resources/static/ 与
                 # target/classes/static/（sync-to-spring.py；旧 mjs 版在本机
                 # 会崩溃已弃用），之后重打 jar 生效
```
教师端多页应用直接编辑 `src/main/resources/static/` 下的 html/css/js，重打 jar 生效。

## 配置

- 敏感配置放 `config/application-local.properties`（参考 `config/application-local.properties.example`：MySQL 密码、AI_API_KEY）
- AI 生成、数字人等功能需要 API Key，其余功能无需 Key

## 安全配置（2026-10-25 加固）

- **桥接共享密钥**：宿主与学生端之间的 `/auth/sync-student` 需携带 `X-Host-Secret` 头。两端必须一致：
  - 学生端：`zhixueti-backend/.env` 的 `HOST_BRIDGE_SECRET`
  - 宿主：`config/application-local.properties` 的 `zhixueti.bridge-secret`（或环境变量 `ZHIXUETI_BRIDGE_SECRET`）
  - 学生端 `.env` 的 `JWT_SECRET_KEY` 未配置（仍是源码默认值）时服务会**拒绝启动**
- **教师自助注册开关**：`auth.allow-teacher-self-register`（默认 true 便于演示）；生产部署建议置 `false`
- **代码判题沙箱**：仅支持 macOS sandbox-exec 隔离执行；其它平台一律拒绝运行学生代码（不再提供无沙箱开关）
- 演示对比模式入口已隐藏，答辩演示时在页面 URL 加 `?demo=1` 即可显示

## 测试账号（本地）

- 教师：`teacheck1 / Teach2026a`
- 学生：`spalocal1 / Spa2026a`
- 管理员（管理端 SPA / 数据大盘）：`admin / Admin2026a`
  - 入口：认证中心 → 「管理入口」→ 管理端登录 → 自动进入 `/admin/dashboard`（数据大盘：总用户数、日活、平台趋势、热门知识点等）
  - 管理员账号存于 `zhixueti-backend/data/edunexus.db`（SQLite sys_user 表，user_type=3）

## 目录说明

- `src/` 后端 Java 源码 + 静态资源
- `zhixueti-frontend/` 学生端 SPA 源码（Vue3 + Vite + Element Plus）
- `zhixueti-backend/` 智学体 Python FastAPI 后端（独立 venv）
- `config/` 本地私有配置（不入库）
- `data/` 运行时数据（JSON 存储、生成的音频等）
- `logs/` 日志
- `target/` Maven 构建产物
- `_hw_patch/` 历史作业接口补丁草稿，可删
