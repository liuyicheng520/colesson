# 金砖大赛 2026 · BRICS2026-ST-143 · 参赛编号 A-159

项目：智课共生——多智能体个性化互动学习系统（本科组）

## 交付物

`output/` 下两份可直接提交的 Word 文档，均基于大赛官方模板填写，封面、版式、表格结构与模板一致：

| 文件 | 说明 | 篇幅 |
|---|---|---|
| A-159_智课共生_项目作品说明文档.docx | 项目作品说明文档（七章＋附录） | 5 页，正文约 4000 字 |
| A-159_智课共生_安全架构专项设计说明书.docx | 安全架构专项设计说明书（七章＋附录） | 5 页，正文约 4600 字 |

`render/` 下为两份文档的 PDF 预览（由 LibreOffice 转换，仅用于快速查看，正式提交用 docx）。

## 内容依据

两份文档的事实、数据与实现细节均取自项目现有材料，未作虚构：

- `docs/提交材料/AiC2026_智课共生_创新方案.docx`（背景、痛点、功能、成果）
- 参赛材料《技术报告》《设计与开发文档》《测试数据与性能指标报告》
- 源码实测：`zhixueti-backend/app/security/*`（输入防护、事实校验、审计、安全流水线）、
  `app/llm/{gateway,safety}.py`（多供应商网关与降级、两级内容审核）、
  `src/main/java/com/contest/{AuthService,AuthController,ZhixuetiProxyFilter,ZhixuetiAuthBridge,CodeJudgeService}.java`
  （BCrypt、会话 Cookie、三级管理员、反向代理、桥接密钥、判题沙箱）、
  `app/services/{profile_fusion,permission_service,admin_audit_service}.py`（画像权重、RBAC、审计）

关键数据：知识库 2119 条切片、离线检索 14/14、单元测试 18 例通过 17 例、
5 个接口平均延迟 18.33 ms／P95 最大 38.73 ms、101 份课件解析压测、300 条问答评测。

## 重新生成

```bash
cd docs/提交材料/BRICS2026_A159
python -I build.py
```

- `content_works.py` / `content_security.py`：两份文档的正文（改文字只改这里）
- `build.py`：读模板 → 填封面 → 按章节填表格单元格 → 保存到 `output/`

正文样式：宋体 10.5 pt、固定行距 15 pt、首行缩进 2 字符、两端对齐；小标题用黑体加粗。
封面的「项目名称」较长，已拆为主副两行（副标题悬挂缩进对齐到值的位置），避免折行断字。
