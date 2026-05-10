# Archive

本目录存放已归档、不再维护的代码。保留 git 历史供回溯参考。

## frontend/

桌面 Web 前端（React + TypeScript + Vite）。

- **最后一次功能改动**：`7986760 fix align web task dates with Asia/Shanghai semantics`
- **归档原因**：移动端已完整覆盖所有核心功能（Today / Plan / Board / History / Knowledge），桌面端不再投入维护。
- **与移动端的关系**：移动端 `mobile_frontend/` 已独立迭代，功能上超集于此桌面端。
- **注意**：`archive/frontend/` 的 `package.json` 内容原样保留，不在 CI 上构建。
