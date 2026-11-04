# 来源与改动边界

上游：`https://github.com/fastapi/full-stack-fastapi-template`

开始开发时的提交：`f4bcfaba7c85be3c6332cc74a20819f586dcdbc6`。MIT 许可证保留在根目录。原始文件可从上述提交追溯；发布版已移除不启用的模板页面、生成客户端、旧测试与旧部署配置。

## 复用

- FastAPI / React 的前后端工程布局。
- SQLModel 用户基础模型、密码哈希和 JWT helper（`app/core/security.py`）。
- 原 UI、生成客户端与旧业务路由已从发布版移除；上游提交仍可追溯。

## 新增与重构

- 新增 `backend/app/lab/`：设备、预约、故障、审计、Outbox、站内消息和幂等记录领域模型；事务服务、API、后台任务和演示数据。
- `frontend/src/lab/`：LabLink 业务页面和视觉系统；改写入口、构建和依赖配置。
- 数据库引擎支持 SQLite 本机模式、PostgreSQL 部署模式；新的 Alembic 迁移链。
- 新增业务不变量测试、浏览器验收脚本、构建和 CI、启动与部署配方、架构及面试说明。
- 用独立配置替换原模板的强制 PostgreSQL / 云服务假设，并兼容 Python 3.12。

不要把上游生成客户端、账号工具和未启用的原模板功能写成自己实现的功能。`git diff` 与新增文件用于审查具体改动；未对外发布或推送。
