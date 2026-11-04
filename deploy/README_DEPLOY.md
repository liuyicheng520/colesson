# CoLesson 线上部署手册（47.120.18.218）

> 目标：把本地最新构建（安全修复 + 知识库 + 动效 + 375px 适配 + 智能体配置/实战演练闭环）同步到云服务器。

## 0. 部署产物

在本机执行：

```bash
python deploy/package_deploy.py
# 产出 deploy/colesson-bundle.zip（约 60-90 MB）
```

包含：`ai-teacher.jar`（宿主+SPA+教师端静态）、`zhixueti-backend/`（FastAPI 代码 + .env + KB 语料 + 向量库）、`config/application-local.properties`、systemd 单元、服务器安装脚本。

## 1. 服务器前置条件（首次）

- Java 17+：`java -version`
- Python 3.10+：`python3 -V`
- 端口 8082 放行（宝塔「安全」+ 云厂商安全组）
- 可选 MySQL：不装也能跑（宿主用 JSON 文件存储，学生端用 SQLite `USE_SQLITE=true`）

## 2. 上传与安装（SSH 方式）

```bash
# 本机：上传
scp deploy/colesson-bundle.zip root@47.120.18.218:/www/
# 服务器：
ssh root@47.120.18.218
mkdir -p /www/colesson && cd /www/colesson
unzip -o /www/colesson-bundle.zip -d .        # 解出 bundle/ 内容到当前目录
mv bundle/* . && rmdir bundle                  # 也可以直接保持 bundle/ 结构，脚本路径一致即可
bash server_setup.sh /www/colesson
```

脚本会：创建 venv → 装依赖 → 装 systemd 单元 → 启动。

## 2'. 宝塔面板方式（无 SSH 命令行习惯）

1. 「文件」上传 `colesson-bundle.zip` 到目标目录并解压
2. 「终端」执行 `bash /www/colesson/server_setup.sh /www/colesson`
3. 或不用 systemd：宝塔「网站 → Java 项目」添加项目，jar 路径 `/www/colesson/ai-teacher.jar`，JDK 选 17+，端口 8082

## 3. 更新已有部署

```bash
# 服务器：备份 → 替换 → 重启
cd /www/colesson
systemctl stop colesson
cp ai-teacher.jar ai-teacher.jar.bak.$(date +%m%d%H%M)
# 上传新 zip 解压覆盖（zhixueti-backend/data/edunexus.db 为运行数据，勿覆盖）
systemctl start colesson
```

**注意**：`zhixueti-backend/data/edunexus.db`（学生端用户/资源数据）与 `data/`（宿主 JSON 数据）是**运行数据**，更新时保留服务器上的，不要用包里的覆盖。

## 4. 验证

```bash
python deploy/verify_online.py                    # 默认打 47.120.18.218:8082
python deploy/verify_online.py http://<host>:8082 # 或指定地址
```

检查项：18 个关键页面状态码 + 学生端登录接口代理链路。

## 5. 日常运维

```bash
systemctl status colesson     # 状态（宿主会自动拉起 8000 的 FastAPI）
journalctl -u colesson -f     # 日志
systemctl restart colesson    # 重启
```

## 6. 常见问题

- **启动后 /student 打不开**：等 30-60s，宿主就绪后会自动拉起 FastAPI（日志出现「智学体已随宿主启动」）
- **知识库检索为空**：确认 `zhixueti-backend/data/vector_kb/` 已随包上传；或调 `POST /api/v1/kb/reindex`（管理员）重建
- **登录报跨域/桥接失败**：核对 `config/application-local.properties` 的 `zhixueti.bridge-secret` 与 `zhixueti-backend/.env` 的 `HOST_BRIDGE_SECRET` 一致
- **KB 检索首次慢**：`.env` 已带 `HF_HUB_OFFLINE=1`，若服务器首次装依赖联网慢属正常
