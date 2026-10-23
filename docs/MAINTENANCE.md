# 文档维护规范

> 文档组织规则 accepted；本文件约束文档维护，不意味着系统已开启自动维护。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第五篇 · 验证与参考](../README.md#part-evidence) › 第 23 章

**本章导航**

- [维护范围与入口](#maintenance-scope)
- [唯一权威与章节结构](#single-authority)
  - [篇、章、节与导航](#book-organization)
  - [编号与可点击链接](#stable-identifiers)
- [阶段、状态与证据](#roadmap-authority)
- [图表、图源与生成物](#diagram-authority)
- [一次变更的完成流程](#change-workflow)
- [历史与清理](#retirement-and-history)
<!-- book-nav:end -->

<a id="maintenance-scope"></a>
## 维护范围与入口

根 [README.md](../README.md) 是所有文档主入口；docs/README 是辅助目录。全部当前设计、图表、文档验证和来源索引均在 docs。H 盘保留旧实现说明和历史材料；新工程当前设计只在本工程更新，不在两处维护竞争版本。

`docs/provenance.json` 记录交接来源、原文件摘要、保留章节和旧参考链接去向；它是交接记录，不是持续从 H 盘同步的配置。新工程文档阅读、导航和检查不依赖 H 盘存在。

<a id="single-authority"></a>
## 唯一权威与章节结构

每个概念、规则、流程、目录树和验收定义只有一处完整正文，其他位置摘要链接。manifest 的 documents 登记 id、path、title、owns、reader_summary 与状态；book.parts 管理唯一篇章归属。主题变化应修订原权威页，不新增“最新总稿”覆盖旧规则。

<a id="book-organization"></a>
### 篇、章、节与导航

以篇分领域、章分职责；主题页一个 H1，H2/H3/H4 层级连续，每个标题有显式稳定锚点。机器生成 root README 与 docs/README 的章节目录，以及主题章的导航、前后章链接。显示序号可以变，文档 ID 和锚点保持稳定。

生成块 `book-tree`、`book-nav`、`book-footer` 不手改。新增/移动/删除文档时，先登记 manifest 和权威去向，再同步导航与入链。正文中的表格放在其权威章节；不要把表格截图作为唯一数据来源。

<a id="stable-identifiers"></a>
### 编号与可点击链接

保留需求 R/N、阶段 K、验收 M/V、健康 H、决策 ADR 和来源 S 编号，不重用已退役编号。跨文件采用相对路径加显式锚点，图片也使用相对路径；避免本机绝对盘符链接和 localhost 运行页成为文档必要入口。

Cursor/VS Code 打开整个工程，在 Markdown 预览中单击链接；源码视图可 Ctrl+单击。其他 Markdown 阅读器可直接读取 PNG 图与普通相对链接。旧工程路径只作为来源文字记录，不要求读者安装旧软件。

<a id="roadmap-authority"></a>
## 阶段、状态与证据

K0—K6 唯一实施定义归核心起步；M0—M6 仅是产品验收门。新工程从自己的证据起步，不把旧系统的“通过”继承过来。

accepted 表示目标/规则被采纳；proposed 是待实现设计；implemented 需本工程代码版本；verified 需测试输入、环境、结果和限制。每次交付先记录真实检查结果，再更新证据。文档渲染和链接通过不能证明运行性能、隔离或自主成长。

<a id="diagram-authority"></a>
## 图表、图源与生成物

架构图唯一可编辑源为 docs/diagrams/*.mmd，SVG 与 PNG 必须来自该源。图在相应主题正文内直接展示，图册集中提供主题、SVG 和源码入口。首次交接的图为旧文档已核查生成物的原字节迁入，其原摘要登记于 manifest；不是本轮重新渲染的结果。

修改图时使用经过锁定的 Mermaid 渲染工具。当前工程没有安装渲染器，也不依赖旧工程脚本；维护时可选官方 Mermaid CLI 的固定版本或独立渲染器，记录版本与环境。先输出 SVG/PNG，检查文字、裁切、布局与连线，再更新 manifest 的 source_sha256 与 artifacts 摘要，并在 docs/evidence 中记录实际过程。不得只改哈希来掩盖过期图片；当前检查器只核对摘要与登记，不会伪称已渲染。

表格使用 Markdown，公式或图中数据应有正文解释。图源、生成物、归属与来源变化一并修订；没有当前引用的图先核对去向，再决定退役，不复制成 old/final2。

<a id="change-workflow"></a>
## 一次变更的完成流程

1. 定位权威主题，核对最新用户要求、来源及影响范围。
2. 修改正文和必要图源，新增内容登记唯一章节；保留稳定编号。
3. 改图则渲染与目视核查，修复入链及资产引用。
4. 在工程根执行下面两条命令；第二条也检查导航是否过期。
5. 记录实际通过/失败/未运行项和设计边界，再交付当前入口。

```text
python tools/sync_doc_navigation.py --root .
python tools/check_docs.py --root .
```

两个脚本独立编写，仅使用 Python 标准库，不导入或执行旧工程工具。`--check` 可只检查导航；文档检查覆盖清单、章节层级、锚点、内部链接、图片与图源摘要、未登记文件及禁止的旧工程运行依赖。它不能替代设计审阅或业务测试。后续扩大文档格式时应同时扩展检查器，不能通过关闭检查放行坏链接。

<a id="retirement-and-history"></a>
## 历史与清理

尚未为本工程初始化 Git；后续按主人授权选择历史管理，不把本轮交接等同于建立代码仓库。不要复制旧全文作为当前树备份。删内容先记录去向、稳定编号和引用，恢复材料、私密资料、原始素材及用户数据不属于文档清理对象。

文档随实际工作更新，不擅自创建后台定时任务或承诺无人值守维护。设计规则本身变更时给出理由和受影响验收，不掩盖之前的失败结论。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：研究资料与证据边界](references.md)
<!-- book-footer:end -->
