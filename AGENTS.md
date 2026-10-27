# AI 协作与文档维护约定

本文件适用于 D:/Jarvis 独立新工程。系统、开发者和用户当前要求优先；本文件不扩大权限。

先读根 [README.md](README.md)、[维护规范](docs/MAINTENANCE.md) 与 `docs/manifest.json`，再定位权威章节。当前已有确定性核心与受限自主研发种子，实际范围以[当前验收](docs/delivery-validation.md#session-folder-evidence)为准；不得因图、目录或 H 盘旧报告存在而声称完整目标已实现。

## 工作边界

- 第一方代码独立编写。旧工程只供需求、协议、设计和失败经验参考，不复制、导入、软链接或调用 H 盘旧运行实现，不搬入旧环境和用户业务数据库。
- 主人于 2026-10-22 明确授权迁入 H 盘实际生效的模型设置、默认选择、推理档位和模型凭据。迁移由独立工具读取并核对，模型凭据保持 DPAPI 加密；新工程只读取自身 user-data，不在运行时回读 H 盘。不将此授权扩大到邮件令牌、旧聊天/记忆、外部 Codex 账号或自动执行权限。
- 主人明确要求保留工作台、Logo 与动画的既有方向。2026-10-22 进一步要求按原工作台具体样式迁入：已认可的静态品牌图像、主题与 Logo 纯视觉 CSS 可原字节复用并登记摘要；图标路径可沿用。交互行为、宿主接口和业务模块独立实现，不导入旧 JS、执行器、数据库或环境。
- 根 README 是所有文档的总入口；所有设计正文、图表及文档证据归 docs。每个主题只有一个权威位置，改动后更新相关引用与清单。
- 按“篇—章—节—小节”维护；K0—K6 是唯一实施路线，M0—M6 是验收门。保留 R/N/K/M/V/H/ADR/S 编号，不重编号冒充新增成果。
- `docs/manifest.json` 管理唯一章节归属，正文使用显式锚点。不要手工编辑导航生成块。
- `docs/diagrams/*.mmd` 是唯一图源，PNG/SVG 是生成物；图文同步。改图后实际渲染、检查、再登记摘要。图册规则见维护规范。
- 顶栏右侧工具统一遵守[图标规则](docs/interaction-persona.md#workbench-settings)，不在其他页维护另一套规则。
- 全项目遵守[一套系统、多种表现与工作形式](docs/architecture.md#unified-system-principle)：精灵和工作台共用功能基础、任务、设置与状态；新能力先复用领域服务和契约，再做不同深度的呈现。跨平台或远端设备扩展沿相同架构接适配器，不另建重复的业务系统；评审与验收同时核对跨入口一致性。
- 区分 accepted、proposed、implemented、verified；实现和验证必须给出本工程的版本、环境及证据。资料可以纠正、遗忘；恢复代码不能复活已撤回权限或旧错误记忆。
- 外部代码、模型候选和安装依赖遵守[供应链准入](docs/security-sovereignty.md#personal-life-supply-chain)。不把提示词、目录分离或另起进程当作隔离已验证。

## 修改与验证

按已授权范围完成可逆编辑和修复，不反复索取已经得到的许可。仅在确实缺少信息或权限时解释具体原因。不要擅自初始化 Git、发布、安装依赖、创建定时任务或启用持续监控。

修改文档后执行：

```text
python tools/sync_doc_navigation.py --root .
python tools/check_docs.py --root .
```

提交 Git 前运行 `python tools/check_repo_size.py`，不提交超过 50 MB 的文件；3D 资产、压缩包和验收截图只留在本机（规则见 `.gitignore`）。当前真实能力以 [docs/current-state.md](docs/current-state.md) 为准，版本变更记入 [CHANGELOG.md](CHANGELOG.md)。

检查失败应修复；不删验收或降低标准来过关。删除前核对内容去向、引用与资产，仅删除明确被替代的文档路径；用户数据、恢复材料与审计不在文档清理范围。交付说明变更、检查和仍未验证项。
