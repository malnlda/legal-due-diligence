---
name: legal-due-diligence
description: |
  中国法律尽职调查底稿与报告撰写工具。支持公司主体尽职调查的完整工作流：
  项目初始化→资料核验（intake）→律师终裁（adjudicate）→底稿逐章撰写→完整性检查→报告生成。
  涵盖10大调查板块（主体资格、股权结构、公司治理、核心资产、业务经营、
  财税、劳动人事、债权债务、诉讼仲裁、其他事项），
  输出专业规范的尽调底稿（.md）和尽调报告（.md）。
  Use when user says '尽职调查', '尽调', '底稿', 'due diligence', 'DD报告',
  '尽调报告', '法律尽调', or needs to write legal due diligence working papers or reports.
metadata:
  author: Chengzhe Mo
  version: "26.6.21.1305"
compatibility: Designed for Claude Code. Requires Python 3.10+ for initialization script.
---

# 法律尽职调查 Skill v26.6.21.1305

> 分享版本：v26.6.21.1305  
> 使用提示：示例中的 `路径：[项目存放路径]` 需要替换为你自己的本机目录后再使用。

> **本版新增**：资料齐备性核验（intake）+ 律师终裁（adjudicate）双轨机制，支持分批收料的增量推进工作流。原四模式（init/draft/check/report）完全向后兼容。

> **本版新增（Phase 3/4）**：draft 增量模式（`--mode incremental`，新料到位后只重做受影响章节）；新增 update（增量更新）模式统筹 intake → 受影响章节定位 → draft 增量的完整 Loop B 流程。

> **本版新增**：企业工商数据查询已独立拆分为 `yd-enterprise-info` skill（22 个子命令，支持翻页拉取全量数据）。
> 本 skill 通过调用 `yd-enterprise-info` 获取辅助数据，详见 [§ 外部数据源（可选增强）](#外部数据源可选增强)。

## 目标

为中国律师提供系统化的法律尽职调查底稿编写与报告生成工具。

**核心价值**：
- **调查全面**：10大标准板块、200+检查项，不遗漏重要事项
- **用语规范**：标准法律用语，表述专业严谨
- **两阶段输出**：底稿（律师内部记录）→ 报告（客户交付文件）
- **风险识别**：三级风险评估，系统化识别法律风险

---

## 工作流程

```
  init 初始化
      ↓
  intake 资料核验（每批料到就跑一次）    ←─────────────────┐
      ↓                                                    │
  adjudicate 律师终裁（强制人工断点）                        │  Loop A
      ↓                                                    │  每来一批新料
  update 增量更新（定位受影响章节）                          │  重复
      ↓                                                    │
  draft --mode incremental（只重做受影响章节）──────────────┘
      ↓
  check 完整性检查
      ↓
  report 生成报告
```

**两个 Loop：**
- **Loop A（核验）**：`intake → adjudicate` 每批料触发一次；AI 出研判，律师做终裁。
- **Loop B（推进）**：每批料核验后，`update` 先定位受影响章节，再以 `draft --mode incremental` 只重做这些章节（增量模式）。

**全程约束**：资料是否齐备以**律师认定**为唯一权威，AI 研判仅为参考建议；推进闸门（能否出报告）以律师认定列为准。

---

## 八种工作模式

### 模式 1：init（项目初始化）

**触发词**：`初始化尽调项目`、`新建尽调`、`init DD`

**操作步骤**：
1. 运行 `scripts/init_project.py`，在指定路径创建项目目录
2. 生成项目信息文件 `project-info.md`
3. 为10个章节各生成底稿模板文件

**必须获取的输入**：
- `project_path`：项目存放路径
- `target_company`：目标公司全称
- `client_name`：委托人名称

**可选输入**（有默认值）：
- `base_date`：调查基准日（默认当日）
- `purpose`：调查目的（如"股权收购"、"投资入股"）
- `law_firm`：律师事务所名称
- `lawyers`：经办律师姓名（可多个）
- `uscc`：目标公司统一社会信用代码（可选；记录于 `project-info.md`；init 完成后提示对应的 yd-enterprise-info 命令）

**输出**：项目目录结构如下：
```
[项目名称]-DD/
├── project-info.md       # 项目基本信息与进度跟踪
├── working-paper.md      # 完整底稿（10章合一，单一文件）
├── raw/                  # 原始数据留痕（外部 API 响应）
│   └── chineselaw/       # 元典开放平台原始 JSON
└── report/
    └── (报告生成后存放于此)
```

---

### 模式 2：draft（撰写底稿）

**触发词**：`写底稿`、`撰写第X章`、`draft`、`分析材料并写入底稿`

**操作步骤**：
1. 读取 [references/section-guide.md](references/section-guide.md) 中**对应章节**的调查指南
2. **检查是否可用外部 API**：若该章节在 [references/external-apis.md](references/external-apis.md) 中列出适用接口，且项目目录 `raw/` 下已有相应 JSON，**优先读取并整合**
3. 阅读用户提供的调查材料（支持文件路径或粘贴文本）
4. 按底稿六段结构撰写该章节内容；同时**填写章节头部"数据基准批次"字段**（写入当前批次号，如"第2批"；若材料未经 intake 则写当前日期"YYYY-MM-DD 首次撰写"）
5. 写入项目根目录的 `working-paper.md`（单一底稿文件，定位至对应章节更新）
6. **章级自检**（对照 [references/acceptance-criteria.md](references/acceptance-criteria.md) AC-C1–AC-C7，写入后立即执行）：

   | # | 检查项 | 通过条件 |
   |---|--------|---------|
   | AC-C1 | §X.4 每项发现注明来源 | 无未引用来源的裸述 |
   | AC-C2 | §X.4 无模糊数量词（约、若干、数月等） | 关键词扫描 |
   | AC-C3 | §X.3 已列出所有未获取材料并说明影响 | 与 dd-checklist 对应章❌/🟡项交叉核 |
   | AC-C4 | §X.5 每条风险三级标注+法律依据 | 无仅有描述而缺法律依据的风险条目 |
   | AC-C5 | 如使用 API 数据：不入§X.2、§X.4 标注调用时间、冲突处标风险 | 有 API 数据时逐条核 |
   | AC-C6 | 章节头部"数据基准批次"字段非空，与 task-board 一致 | 字段已填 |
   | AC-C7 | 六段结构（§X.1–§X.6）均存在，无空置段落 | 结构完整 |

   - **全部通过** → 运行 `python3 scripts/update_taskboard.py --project <路径> --chapter X --status 已自检 --notes "AC-C1~C7全通过"`
   - **未通过** → 自动修正，最多重试 2 次；2 次后仍有未通过项 → 运行 `python3 scripts/update_taskboard.py --project <路径> --chapter X --status 待人工 --notes "<未通过项列表>" --checkpoint "<具体断点说明>"`，并告知律师

**必须获取的输入**：
- `chapter`：章节编号（1-10）或章节名称
- `materials`：调查材料（文件路径列表 或 粘贴的文本内容）

**可选输入**：
- `project_path`：项目路径（若上下文中已有则无需重复提供）
- `append`：是否追加模式（默认覆写）
- `--mode incremental`（增量模式）：新一批料到位后，仅在已有章节基础上**补充新材料的发现与影响**，不整章覆写；旧内容加注"据第k批更新"标记。触发时机见 update 模式。

**底稿六段结构**（每章必须包含）：

```markdown
## 第[编号]章 [章节名称]

> **状态**：进行中　**数据基准批次**：第k批　**最后更新**：YYYY-MM-DD

### [编号].1 调查范围与方法
（说明本章调查了什么、采用了什么调查方法）

### [编号].2 已获取材料清单
| 序号 | 材料名称 | 形式 | 日期/期间 | 备注 |
|------|---------|------|----------|------|

### [编号].3 未获取/待补充材料
| 序号 | 材料名称 | 重要程度 | 状态 | 影响说明 |
|------|---------|---------|------|---------|

### [编号].4 调查发现
（详细、客观地记录所有发现，引用具体文件和数据）

### [编号].5 风险提示
| 序号 | 风险事项 | 等级 | 事实依据 | 法律依据 | 处理建议 |
|------|---------|------|---------|---------|---------|

### [编号].6 律师备忘
（内部工作记录：疑点、待确认事项、后续工作安排）
```

**底稿写作核心规则**：

1. **引用具体**：每项发现必须注明信息来源（"经查阅[文件名称]，……"）
2. **数据精确**：涉及金额、日期、比例等必须精确引用，不得概括
3. **发现与意见分离**：§4调查发现 只记事实，§5风险提示 才作评价
4. **缺失即记录**：未获取的材料必须列入§3，并说明对调查结论的影响
5. **风险三级标注**：
   - 🔴 **高风险**：可能导致交易失败或重大损失
   - 🟡 **中风险**：可能影响交易条件或增加成本
   - 🟢 **低风险**：影响较小，可通过常规措施解决
6. **备忘坦诚**：§6律师备忘 记录真实疑虑，不必考虑措辞

---

### 模式 3：check（完整性检查）

**触发词**：`检查底稿`、`check`、`完整性检查`

**操作步骤**：
1. 读取项目根目录的 `working-paper.md`
2. 逐章检查六段结构是否完整
3. 统计材料获取情况
4. 汇总风险发现
5. 生成检查报告

**输出**：
```markdown
# 尽调底稿完整性检查报告

## 总览
| 章节 | 状态 | 已获取材料 | 缺失材料 | 风险数量 |
|------|------|-----------|---------|---------|

## 缺失材料汇总
（全部未获取材料的统一清单）

## 风险汇总
（全部风险点的统一清单，按等级排序）

## 后续工作建议
（基于检查结果的工作安排建议）
```

---

### 模式 4：report（生成报告）

**触发词**：`生成报告`、`出报告`、`写报告`、`report`

**操作步骤**：
1. 读取 [references/report-standards.md](references/report-standards.md) 获取报告写作规范
2. 读取 [assets/report-template.md](assets/report-template.md) 获取报告框架模板
3. 读取项目根目录的 `working-paper.md`（单一底稿文件，含全部10章）
4. 执行底稿→报告转化（见下方转化规则）
5. 生成完整报告，存入 `report/` 目录

**底稿→报告转化规则**：

| 底稿部分 | 报告对应 | 转化方式 |
|---------|---------|---------|
| 调查范围与方法 | 各章"调查范围" | 简化，去除方法细节 |
| 已获取材料清单 | 附件"文件清单" | 汇总为统一附件 |
| 未获取/待补充材料 | "声明与限定条件"§限制条件 | 转为免责限定表述 |
| 调查发现 | 各章"基本情况"/"调查结果" | 精炼为客户可读的客观叙述 |
| 风险提示 | 各章"律师意见" + 结论"重大风险提示" | 增加法律分析，提出建议 |
| 律师备忘 | **不体现** | 完全删除 |

**报告语言转化**：

| 底稿用语 | 报告用语 |
|---------|---------|
| 经查阅XX文件 | 经本所律师查验，…… |
| ⚠️ 待确认 | 截至本报告出具之日，本所律师未能核实…… |
| 🔴 高风险 | 本所律师特别提请委托人关注：…… |
| 🟡 中风险 | 本所律师提示委托人注意：…… |
| 🟢 低风险 | 本所律师建议委托人关注：…… |
| ❌ 未获取 | 因未获取XX材料，本所律师无法就此事项发表意见 |

---

### 模式 5：intake（资料核验）

> **⚠️ 核心声明**：AI 研判仅为建议，资料是否齐备以**律师认定**为唯一权威。本模式只写 AI 轨，不写律师轨。

**触发词**：`核验资料`、`资料齐备性`、`查缺`、`待补清单`、`intake`、`收到一批材料`

**操作步骤**：
1. 定位项目根目录的 `dd-checklist.md`（若不存在则提示先运行 init）
2. 运行 `scripts/reconcile_materials.py`：
   ```bash
   python3 scripts/reconcile_materials.py \
       --project /path/to/DD项目/ \
       --batch   /path/to/materials/batch-02/ \
       --batch-no 2
   ```
3. 读取脚本输出（研判报告、待补清单），整理成给律师看的核验小结
4. 醒目提示：**"AI 研判仅为建议，齐备以律师认定为准；请运行 adjudicate 模式完成终裁"**

**输出文件**（由脚本生成）：
- `dd-checklist.md`：AI 轨刷新（AI研判/AI置信/需复核/最近批次）
- `materials-ledger.md`：台账追加本批记录
- `研判报告-第k批.md`：需复核项详述（含冲突项标 ⚠️）
- `待补充资料清单-第k批-YYYYMMDD.md`：可直接发给标的方催件

**可独立使用**：不进 run-dd 编排也能单次核验，满足"本周来一批料、快速出待补清单"的即时需求。

---

### 模式 6：adjudicate（律师终裁）

> **强制人工断点**：本模式是 CP-6，必须由律师执行，AI 不得跳过或代替律师做认定。

**触发词**：`认定齐备`、`复核清单`、`资料认定`、`adjudicate`、`我来定齐备`

**操作步骤**：
1. AI 读取 `dd-checklist.md`，筛出 `需复核=是` 的项，按"重要程度→章节"排序
2. AI 连同各项审查意见（见 `研判报告-第k批.md`）汇总成"**提请律师复核清单**"呈给律师
3. 律师用自然语言逐项裁决，例如：
   ```
   1.2 认定为"部分-需补"，必须补 2021 年前章程及决议；
   4.9 豁免，本项目不涉及专利；
   6.1 认定"已齐备"，样本量本项目可接受；
   其余未标星项，采纳 AI 建议。
   ```
4. AI 把裁决**代笔写入**律师轨各字段（律师认定/认定人/认定日期/律师批注），并追加到 `adjudication-log.md`
5. AI 回读确认变更摘要，给律师最终复核

**批量采纳**：对"需复核=否"的项，律师可一次性"批量采纳 AI 研判"，AI 代笔写入并在律师批注标"批量采纳 AI 建议，YYYY-MM-DD"。

**律师轨写入规则**（AI 代笔时必须遵守）：
- `律师认定` 枚举：待认定 / 已齐备 / 部分-可推进 / 部分-需补 / 不适用 / 豁免
- `认定日期` 格式：YYYY-MM-DD
- 冲突项（⚠️ 标星）：**必须**由律师逐项裁决，不能批量略过
- 每次认定/改判均追加 `adjudication-log.md` 一行（时间/编号/原认定/新认定/认定人/理由/触发批次）

**输出**：更新后的 `dd-checklist.md` 律师轨 + 追加 `adjudication-log.md`

**推进闸门**（认定完成后自动检查）：  
所有"重要程度=高"项律师认定 ∈ {已齐备, 不适用, 豁免} → 提示"关键资料齐备，可推进 draft/check/report"  
否则 → 列出仍待补的高重要度项，等下一批或律师豁免

---

### 模式 7：update（增量更新，Loop B）

> **定位**：每批料经 intake → adjudicate 后，触发 Loop B 的增量底稿更新。  
> 只重做受本批新料影响的章节，不整批覆写。

**触发词**：`增量更新`、`更新底稿`、`update`、`新料到了更新`、`本批影响章节重做`

**操作步骤**：
1. 读取最新一批的 `章节-材料映射表-第k批.md`，提取"受影响章节列表"
2. 运行 `update_taskboard.py --mark-affected` 更新 task-board 受影响标记：
   ```bash
   python3 scripts/update_taskboard.py \
       --project /path/to/DD项目/ \
       --mark-affected 1,4          # 章节号从映射表第三节读取
   ```
3. 对每个受影响章节，读取：
   - 该章当前底稿内容（`working-paper.md` 对应章节）
   - 本批该章新增材料（从 `章节-材料映射表-第k批.md` 第一节读取）
   - `dd-checklist.md` 该章项目（新增/变更/冲突项）
4. 以 `draft --mode incremental` 增量方式更新该章：
   - §X.2 已获取材料清单：**追加**新材料行，不删旧行
   - §X.3 未获取材料：根据最新 checklist 中该章项目状态**刷新**（移出已收项、保留待补项）
   - §X.4 调查发现：在相关段落后追加"**据第k批更新（YYYY-MM-DD）**："标注，然后补写新发现
   - §X.5 风险提示：若新料带来新风险则追加；若旧风险已解除则注明"经第k批材料核实已消解"
   - §X.6 律师备忘：追加本批新注意事项
5. 更新章节头部"数据基准批次"字段为当前批次，"最后更新"字段为今日
6. 对更新后的章节执行 AC-C1–C7 自检，运行 `update_taskboard.py` 写回结果
7. 同步 report 免责声明（见下方"报告免责声明对接"）

**报告免责声明对接**（每次 adjudicate 完成 / 每次 update 完成后自动执行）：
- 读取 `dd-checklist.md`，提取**律师认定 ∈ {部分-需补, 待认定}** 且重要程度=高的项
- 在 `working-paper.md` 结尾"附：免责限制条件"节（若无则自动创建）同步更新：
  - 新增项：补写"因未取得 XX 材料，本所律师无法就此事项发表意见"
  - 已消解项（律师已改判为 已齐备/不适用/豁免）：移出该条
- 此操作仅更新 working-paper.md，不修改 dd-checklist 律师轨

**增量模式注意事项**：
- 绝不删除已有发现（历史信息留痕）；仅追加或注明更新
- 若某章仍有高重要度 checklist 项=❌未收 且律师认定=待认定 → §X.3 保留待补记录 + task-board 该章断点事项标注"第k批仍缺：XX"
- 受影响章节的 task-board 状态先置"进行中"，完成自检后置"已自检"（或"待人工"）

---

### 模式 8：run-dd（一键尽调编排，Loop A + Loop B）

> **定位**：串起 `init → intake → adjudicate → update → draft → check → report` 全流程，内置 Loop A/B 循环与强制人工断点。律师给一次目标（材料夹 + 项目信息），AI 自动编排，遇断点停下来等律师指令。

**触发词**：`一键尽调`、`run-dd`、`跑全流程`、`从头开始跑`

**启动时必须获取的输入**：
- `materials_dir`：材料夹路径（含第一批资料）
- `target_company`：目标公司全称
- `client_name`：委托人名称
- `project_path`：项目存放路径
- `mode`：运行模式（`staged` 默认 / `full`），未指明默认 staged 并提示律师

**可选输入**：
- `base_date`：调查基准日
- `purpose`：调查目的
- `uscc`：目标公司统一社会信用代码（有则自动规划 yd-enterprise-info 拉取）
- `batch_no`：本批材料批次号（默认 1）

**7 步循环骨架**（对应 [references/orchestration-guide.md](references/orchestration-guide.md) §二）：

```
1. PLAN
   a. 运行 init 模式：建项目目录（task-board / dd-checklist / materials-ledger / adjudication-log）
   b. 扫描材料夹，调用 reconcile_materials.py 预扫 → 生成章节-材料映射表
   c. 若提供 USCC → 自动调用 fetch_enterprise_data.py 拉取工商数据（先 dry-run 预览，律师确认后执行）：
      ```bash
      # 预览（不执行）
      python3 scripts/fetch_enterprise_data.py --project /path/ --dry-run
      # 实际拉取（需 export CHINESELAW_API_KEY=你的KEY）
      python3 scripts/fetch_enterprise_data.py --project /path/
      # 只拉取特定章节
      python3 scripts/fetch_enterprise_data.py --project /path/ --chapters 1,4,9
      ```
   d. task-board 各章初始状态=未开始

2. LOOP A — 资料齐备性核验
   a. reconcile 脚本比对清单 → 写 AI 研判轨（AI研判/AI置信/需复核）
   b. 生成 研判报告-第k批.md（展开"需复核"项）
   c. ★ CP-6 强制断点：adjudicate 模式汇总"需复核"项 → 律师终裁 → 写律师认定轨
   d. 推进闸门检查：
      - 高重要度项全部律师认定 ∈ {已齐备, 不适用, 豁免} → 可推进 LOOP B
      - 否则 → 出"待补充资料清单"，staged 模式在此停；full 模式继续写未受阻章节

3. LOOP B — 章节撰写与增量推进（多章可并行）
   对每个受影响章节（各章分析可并行，写入 working-paper.md 时串行落盘）：
   a. 读材料 + 工商数据（如适用；若 raw/chineselaw/ 已有 JSON 则自动读取）
   b. draft 全量首次 / draft --mode incremental 增量重做
   c. 章级自检 AC-C1–C7 → update_taskboard.py 写回结果（已自检 / 待人工）
   > **并行写章注意事项**：多个子任务同时分析材料是安全的；但写入 working-paper.md
   > 时必须串行（一章写完再写下一章），避免文件冲突。AI 子任务写入顺序由编排层保证。

4. CHECK
   a. 跑完整性检查（check 模式），汇总缺失材料与风险
   b. 能自动补 → 回 LOOP B；不能补 → 进断点清单

5. CHECKPOINT — 强制人工断点汇总
   汇总所有 task-board 状态=待人工 事项，律师逐项处置
   staged 模式在此停止；full 模式处置完继续

6. REPORT — 推进闸门 + 生成报告
   a. 运行推进闸门检查：
      ```bash
      python3 scripts/check_gates.py --project /path/to/DD项目/
      ```
   b. AC-P1–P5 全部通过 → 生成报告（report 模式）
   c. 未全通过 → 列出未通过项，律师处置后重新 check_gates

7. FINAL VERIFY
   运行底稿与报告一致性终检：
   ```bash
   python3 scripts/final_verify.py --project /path/to/DD项目/
   ```
   逐项核查 V-WP1~WP4（底稿结构）、V-R1~R5（报告安全性）、V-X1~X2（交叉一致性）
   → 输出 final-verify-YYYYMMDD.md + 遗留问题清单
```

**强制人工断点**（出现以下任一情形，AI 立即停，不自行判定）：

| # | 触发条件 | AI 动作 |
|---|---------|--------|
| CP-1 | 某章"重要程度=高"材料均未取得 | 汇报缺失项及影响，等律师指示 |
| CP-2 | §X.5 出现 🔴 高风险事项 | 列出高风险项（含法律依据），等律师处置 |
| CP-3 | 法律定性存疑（代持/抽逃/违规担保等） | 描述歧义点，等律师拍板 |
| CP-4 | 外部 API 数据与目标公司材料不一致 | 列出冲突点，等律师认定以哪个为准 |
| CP-5 | 任何"对外承诺"或"正式意见"措辞 | 停止，律师审定后继续 |
| **CP-6** | **每批 reconcile 完成，需律师认定齐备性** | **adjudicate 模式 → 律师终裁；绝不跳过** |

**staged vs full 选择**：

| 模式 | 退出时机 | 适用场景 |
|------|---------|---------|
| **staged（默认）** | 每批 LOOP A 认定完成 + 受影响章节增量完成 | 材料分批到位、需阶段性交付 |
| **full** | FINAL VERIFY 完成，或遇强制断点 | 材料基本齐备、需快速出完整初稿 |

**推进闸门使用方法**：

律师下令出报告前，AI 运行：
```bash
python3 scripts/check_gates.py --project /path/to/DD项目/
```
输出 AC-P1~P5 逐项结论，写入 `gate-check-YYYYMMDD.md`。全部通过后方可执行 report 模式。

---

## 快速参考：10大调查板块

| # | 板块 | 核心关注 |
|---|------|---------|
| 1 | 公司基本信息与主体资格 | 营业执照、章程、变更登记、信用信息、印章 |
| 2 | 股权结构与股东信息 | 股东名册、出资验资、股权转让、代持、质押冻结 |
| 3 | 公司治理与组织结构 | 组织架构、三会运作、决议程序、内部制度 |
| 4 | 核心资产 | 不动产权属、设备清单、知识产权、权利负担 |
| 5 | 业务经营与合同管理 | 主营业务、核心合同、客户供应商、业务资质 |
| 6 | 财务与税务 | 财报审计、银行账户、纳税申报、税收优惠 |
| 7 | 劳动人事管理 | 劳动合同、社保公积金、竞业保密、劳动争议 |
| 8 | 重大债权债务与担保 | 银行借款、应付款、对外担保、应收账款 |
| 9 | 诉讼、仲裁与行政处罚 | 未决/已决案件、行政处罚、潜在纠纷 |
| 10 | 其他重要文件 | 对外投资、关联交易、环保安全生产 |

各板块的详细调查指南（调查要点、红旗标志、标准发现语言），请参阅 [references/section-guide.md](references/section-guide.md)。

报告的格式规范、声明模板、语言标准，请参阅 [references/report-standards.md](references/report-standards.md)。

---

## 外部数据源（可选增强）

本 skill 通过调用独立的 **`yd-enterprise-info`** skill 接入元典开放平台企业工商数据，用于辅助底稿撰写。
所有外部数据**仅作为线索与初稿**，不得替代律师对原始材料的核验。

### 依赖 Skill

| Skill | 功能 | 子命令数 |
|---|---|---|
| `yd-enterprise-info` | 22 个子命令覆盖工商全量数据（股东、变更、商标、专利、诉讼等），支持翻页拉取 | 22 |

- 安装路径：`~/.claude/skills/yd-enterprise-info/`
- 配置文档：[references/chineselaw/enterprise-endpoints-summary.md](references/chineselaw/enterprise-endpoints-summary.md)
- 完整规范：[references/external-apis.md](references/external-apis.md)

### 典型调用流程

**第一步：检索目标公司（仅知名称时）**

```bash
python3 ~/.claude/skills/yd-enterprise-info/scripts/yd_enterprise_info.py \
    search-company --name "目标公司全称或股票简称"
```

**第二步（自动化路径）：用 fetch_enterprise_data.py 一键按章节拉取**

```bash
export CHINESELAW_API_KEY=你的KEY
# 预览将要执行的命令（dry-run，无需 API Key）
python3 scripts/fetch_enterprise_data.py --project /path/to/DD项目/ --dry-run
# 实际拉取所有有适用接口的章节（1/2/3/4/6/8/9/10）
python3 scripts/fetch_enterprise_data.py --project /path/to/DD项目/
# 只拉取特定章节
python3 scripts/fetch_enterprise_data.py --project /path/to/DD项目/ --chapters 1,4,9
```

- USCC 自动从 `project-info.md` 读取（`init` 时传入 `--uscc` 即可存档）
- 拉取日志写入 `raw/chineselaw/fetch-log.md`（可追溯）
- 失败项在终端提示，需在底稿 §X.6 律师备忘中注明原因

**第二步（手动路径）：直接调用 yd-enterprise-info 子命令**

```bash
export CHINESELAW_API_KEY=xxxx
USCC=91110108MA0074PN30
OUT=/path/to/project/raw/chineselaw/
python3 ~/.claude/skills/yd-enterprise-info/scripts/yd_enterprise_info.py \
    base-info --tyshxydm $USCC --output $OUT --yes
python3 ~/.claude/skills/yd-enterprise-info/scripts/yd_enterprise_info.py \
    litigation-doc --tyshxydm $USCC --output $OUT --yes
# 更多子命令见 yd-enterprise-info 的 chapter-mapping.md
```

### 凭证

- 环境变量 `CHINESELAW_API_KEY`
- **任何凭证不得入库**到 skill 包或项目仓库

### 引用规范（写入底稿时必须遵守）

1. **不入材料清单**：API 数据**不得**列入 §X.2 已获取材料清单
2. **明确来源**：在 §X.4 调查发现 段首注明"经查阅元典开放平台接口（调用时间 YYYY-MM-DD HH:MM，原始数据见 `raw/chineselaw/<文件名>`）"
3. **冲突即风险**：若 API 数据与目标公司提供材料不一致，必须在 §X.5 风险提示中标注 🟡 中或 🔴 高风险
4. **失败留痕**：API 调用失败时在 §X.6 律师备忘中记录时间与原因

完整规则详见 [references/external-apis.md](references/external-apis.md)。

---

## 使用示例

### 示例 1：初始化

```
帮我初始化一个尽调项目：
- 目标公司：广州XX农业科技有限公司
- 委托人：深圳XX投资有限公司
- 路径：[项目存放路径]
- 基准日：2026-03-20
- 目的：股权收购
```

### 示例 1b：初始化并拉取工商信息（已知 USCC）

```
帮我初始化一个尽调项目：
- 目标公司：北京华宇元典信息服务有限公司
- 统一社会信用代码：91110108MA0074PN30
- 委托人：深圳XX投资有限公司
- 路径：[项目存放路径]
```

→ init 完成后，按提示运行 `yd-enterprise-info base-info` 等命令拉取工商数据。

### 示例 2：写底稿

```
请帮我撰写第2章"股权结构与股东信息"的底稿。
材料路径：/path/to/materials/02-股权/
```

或者：

```
请分析以下材料，写入底稿第1章：
[粘贴材料内容]
```

### 示例 3：检查

```
底稿写得差不多了，帮我做一次完整性检查。
```

### 示例 4：生成报告

```
底稿已全部完成，请帮我生成尽调报告。
```

### 示例 5：单章报告预览

```
先帮我把第1章底稿转成报告格式看看效果。
```
