# legal-due-diligence

中国法律尽职调查 Skill 分享版 · v26.6.21.1305

适用环境：Claude Code · 运行要求：Python 3.10+

---

## 这个 Skill 是做什么的

这是一个面向中国律师团队的法律尽职调查全流程辅助工具。它在 Claude Code 中作为 Skill 运行，将尽调的整个工作流结构化为可追溯、可循环推进的半自动流水线。

**本版（v26.6.21.1305）的核心升级**是"Loop 化"——引入资料核验循环（Loop A）和增量底稿推进循环（Loop B），并配套律师终裁断点机制、双轨尽调清单、推进闸门检查，从此每次新材料到位时，只需一条指令便能完成核验→认定→更新底稿的完整推进。

### 核心价值

- **资料核验自动化**：每批材料到位后，自动比对尽调清单，输出 AI 研判与待补清单
- **律师终裁机制**：AI 研判仅为建议，资料是否齐备由律师通过 adjudicate 模式做最终认定，全程可追溯
- **双轨清单**：AI 研判轨与律师认定轨并行，任何脚本均不得改写律师轨，只有律师通过 adjudicate 模式才能写入
- **增量推进**：新料到位后只重做受影响章节，不整批覆写底稿
- **推进闸门**：出报告前自动校验 5 项项目级验收标准（AC-P1~P5），全部通过方可出报告
- **调查全面**：10 大标准板块、88 条检查项，不遗漏重要事项
- **两阶段输出**：底稿（律师内部记录）→ 报告（客户交付文件）

---

## 与 yd-enterprise-info 的协作关系

本版继续维持 v26.4.29 确立的分工架构：

| Skill | 职责 |
|---|---|
| **legal-due-diligence**（本 Skill）| 尽调全流程：资料核验、律师认定、底稿撰写、报告生成 |
| **[yd-enterprise-info](https://github.com/malnlda/yd-enterprise-info)** | 企业工商数据拉取：22 个元典接口、自动翻页 |

新增 `scripts/fetch_enterprise_data.py`，可按章节批量调用 yd-enterprise-info，无需手动逐个敲命令。

---

## 安装方法

将 `legal-due-diligence-v26.6.21.1305` 文件夹复制到你的 Claude Skills 目录，并**建议重命名为 `legal-due-diligence`**：

```bash
# 典型安装路径
~/.claude/skills/legal-due-diligence/
~/.claude/skills/yd-enterprise-info/    # 如需工商数据拉取
```

安装后的目录结构：

```text
legal-due-diligence/
├── SKILL.md                            # Skill 主说明（Claude 读取入口）
├── README.md                           # 本文件
├── CHANGELOG.md                        # 版本更新日志
├── assets/
│   ├── dd-checklist-template.md        # 双轨尽调清单模板（88 条，10 章）
│   ├── materials-ledger-template.md    # 资料台账模板
│   ├── report-template.md              # 报告模板
│   └── working-paper-template.md       # 底稿模板
├── references/
│   ├── acceptance-criteria.md          # 验收标准（AC-C1~C7 章级 / AC-P1~P5 项目级）
│   ├── orchestration-guide.md          # run-dd 编排规则手册
│   ├── section-guide.md                # 分章节调查指南
│   ├── report-standards.md             # 报告写作规范
│   ├── external-apis.md                # 外部数据源索引
│   └── chineselaw/
│       └── enterprise-endpoints-summary.md
└── scripts/
    ├── init_project.py                 # 项目初始化（生成双轨文件结构）
    ├── reconcile_materials.py          # 资料核验引擎（Loop A 核心）
    ├── update_taskboard.py             # 章节状态机更新
    ├── check_gates.py                  # 项目级推进闸门检查（AC-P1~P5）
    ├── fetch_enterprise_data.py        # 工商数据按章节批量拉取
    └── final_verify.py                 # 底稿与报告一致性终检
```

---

## 工作流程概览

```
  init 初始化
      ↓
  intake 资料核验（每批料到就跑一次）      ←──────────────────┐
      ↓                                                       │
  adjudicate 律师终裁（强制人工断点 CP-6）                     │  Loop A
      ↓                                                       │  每来一批新料
  update 增量更新（定位受影响章节）                             │  重复
      ↓                                                       │
  draft --mode incremental（只重做受影响章节）─────────────────┘
      ↓
  check 完整性检查
      ↓
  report 生成报告
      ↓
  final_verify.py 终检（V-WP/R/X 全套）
```

**两个 Loop：**

- **Loop A（核验）**：`intake → adjudicate`，每批料触发一次。AI 出研判，律师做终裁，结果写入台账。
- **Loop B（推进）**：`update → draft --mode incremental`，每批料核验后只重做受影响章节。

**全程约束**：资料是否齐备以律师认定为唯一权威；推进闸门以律师认定列为准，不以 AI 研判为准。

---

## 八种工作模式

### 模式 1　init（项目初始化）

**触发词**：`初始化尽调项目`、`新建尽调`、`init DD`

创建项目目录，生成所有必要文件（双轨尽调清单、资料台账、认定台账、任务看板、底稿、报告目录）。

```text
帮我初始化一个尽调项目：
- 目标公司：广州XX农业科技有限公司
- 委托人：深圳XX投资有限公司
- 路径：[项目存放路径]
- 基准日：2026-06-20
- 目的：股权收购
- USCC：91440101MA9XXXXXXX     ← 可选，有则记录供工商数据拉取
```

生成的文件：`project-info.md` / `working-paper.md` / `dd-checklist.md` / `materials-ledger.md` / `adjudication-log.md` / `task-board.md` / `report/` / `raw/chineselaw/`

---

### 模式 2　draft（撰写底稿）

**触发词**：`写底稿`、`撰写第X章`、`draft`

按六段结构（§X.1 调查范围→§X.6 律师备忘）撰写或更新指定章节。写完后自动执行章级自检 AC-C1~C7，结果写入 task-board.md。

支持 `--mode incremental`：新料到位后在已有内容基础上追加，不整章覆写。

```text
请帮我撰写第2章"股权结构与股东信息"的底稿。
材料路径：/path/to/materials/02-股权/
```

---

### 模式 3　check（完整性检查）

**触发词**：`检查底稿`、`check`、`完整性检查`

逐章检查六段结构是否完整，汇总缺失材料与风险发现，生成检查报告。

---

### 模式 4　report（生成报告）

**触发词**：`生成报告`、`出报告`、`report`

将底稿转化为正式法律尽职调查报告。运行前建议先通过 `check_gates.py` 确认推进闸门全部通过。

---

### 模式 5　intake（资料核验）

**触发词**：`核验资料`、`资料齐备性`、`查缺`、`intake`、`收到一批材料`

> ⚠️ AI 研判仅为建议，资料是否齐备以**律师认定**为唯一权威。本模式只写 AI 研判轨。

每批材料到位后运行，自动比对尽调清单：

```bash
python3 scripts/reconcile_materials.py \
    --project /path/to/DD项目/ \
    --batch   /path/to/materials/batch-02/ \
    --batch-no 2
```

**输出**：
- `dd-checklist.md`：AI 研判轨刷新（AI研判/AI置信/需复核/最近批次）
- `materials-ledger.md`：台账追加本批记录
- `研判报告-第k批.md`：需复核项详述（含冲突项 ⚠️ 标注）
- `待补充资料清单-第k批-YYYYMMDD.md`：可直接发给标的方催件
- `章节-材料映射表-第k批.md`：受影响章节列表（供 update 模式使用）

**核心设计**：
- 累计批次模式：本批无匹配的清单项，继承上一批 AI 研判，不覆写
- 律师轨保护：`律师认定/认定人/认定日期/律师批注/本项齐备标准` 五列，脚本绝不改写
- 冲突检测：律师认定=已齐备 但 AI研判=❌未收，或律师认定=不适用 但 AI研判=✅已收，自动标 ⚠️

---

### 模式 6　adjudicate（律师终裁）

**触发词**：`认定齐备`、`复核清单`、`adjudicate`、`我来定齐备`

> 强制人工断点（CP-6）：本模式必须由律师执行，AI 不得跳过。

律师逐项（或批量）做出认定，AI 代笔写入律师认定轨：

```text
1.2 认定为"部分-需补"，必须补 2021 年前章程及决议；
4.9 豁免，本项目不涉及专利；
6.1 认定"已齐备"，样本量本项目可接受；
其余未标星项，批量采纳 AI 建议。
```

每次认定/改判自动追加 `adjudication-log.md` 一行。

---

### 模式 7　update（增量更新，Loop B）

**触发词**：`增量更新`、`更新底稿`、`update`、`新料到了更新`

读取最新批次的 `章节-材料映射表`，定位受影响章节，对每章以 `draft --mode incremental` 方式只追加新发现，不整章覆写。同步更新任务看板和免责声明节。

---

### 模式 8　run-dd（一键尽调编排）

**触发词**：`一键尽调`、`run-dd`、`跑全流程`、`从头开始跑`

串起完整 7 步骨架（PLAN→LOOP A→LOOP B→CHECK→CHECKPOINT→REPORT→FINAL VERIFY），内置 Loop A/B 和 6 个强制人工断点（CP-1~CP-6）。

支持 **staged（默认）** / **full** 两种运行模式：

| 模式 | 退出时机 | 适用场景 |
|------|---------|---------|
| **staged（默认）** | 每批 Loop A 完成 + 受影响章节增量完成 | 材料分批到位、需阶段性交付 |
| **full** | FINAL VERIFY 完成或遇强制断点 | 材料基本齐备、需快速出完整初稿 |

出报告前运行推进闸门检查：

```bash
python3 scripts/check_gates.py --project /path/to/DD项目/
```

全部通过（AC-P1~P5）后方可执行 report 模式。

---

## 脚本速查

| 脚本 | 用途 | 典型命令 |
|------|------|---------|
| `init_project.py` | 项目初始化 | `python3 scripts/init_project.py --project /path/ --target 公司名 --client 委托人` |
| `reconcile_materials.py` | 资料核验（Loop A 引擎）| `python3 scripts/reconcile_materials.py --project /path/ --batch /path/batch-02/ --batch-no 2` |
| `update_taskboard.py` | 更新任务看板章节状态 | `python3 scripts/update_taskboard.py --project /path/ --chapter 1 --status 已自检` |
| `check_gates.py` | 项目级推进闸门检查 | `python3 scripts/check_gates.py --project /path/` |
| `fetch_enterprise_data.py` | 按章节批量拉取工商数据 | `python3 scripts/fetch_enterprise_data.py --project /path/ --dry-run` |
| `final_verify.py` | 底稿与报告一致性终检 | `python3 scripts/final_verify.py --project /path/` |

所有脚本通过 `python3 <脚本名> --help` 查看完整参数说明。

---

## 双轨尽调清单

`dd-checklist.md` 是本 Skill 的核心状态文件，每行 13 列：

```
| 编号 | 资料项 | 章节 | 重要程度 | AI研判 | AI置信 | 需复核 | 律师认定 | 认定人 | 认定日期 | 律师批注 | 本项齐备标准 | 最近批次 |
```

**AI 研判轨**（cols 5/6/7/13）：由 `reconcile_materials.py` 写入，反映当前批次 AI 匹配结果。

**律师认定轨**（cols 8~12）：**任何脚本均不得写入**，只能通过 adjudicate 模式由律师指示写入。

律师认定枚举值：`待认定（默认）` / `已齐备` / `部分-可推进` / `部分-需补` / `不适用` / `豁免`

---

## 推进闸门（AC-P1~P5）

运行 `check_gates.py` 时逐项校验，全部通过方可出报告：

| 代码 | 检查项 |
|------|--------|
| AC-P1 | task-board 全10章状态 ∈ {已自检, 已完成} |
| AC-P2 | dd-checklist 所有"重要程度=高"项，律师认定 ∈ {已齐备, 不适用, 豁免} |
| AC-P3 | 无未消解冲突项（有律师复裁记录则视为消解） |
| AC-P4 | working-paper.md "附：免责限制条件"节收录了所有高重要度未齐备项 |
| AC-P5 | task-board 无"待人工"状态章节 |

---

## 强制人工断点（CP-1~CP-6）

以下任一情形触发，AI 必须停下来汇总，**不得自行判定或跳过**：

| 编号 | 触发条件 |
|------|---------|
| CP-1 | 某章所需"重要程度=高"的材料均未取得 |
| CP-2 | 底稿 §X.5 出现 🔴 高风险事项 |
| CP-3 | 法律定性存疑（代持/抽逃出资/违规担保等） |
| CP-4 | 外部 API 数据与目标公司材料不一致 |
| CP-5 | 任何"对外承诺"或"正式意见"措辞 |
| **CP-6** | **每批资料核验后，需律师认定齐备性（Loop A 必经节点）** |

---

## 10大调查板块

| # | 板块 | 核心关注 |
|---|------|---------|
| 1 | 公司基本信息与主体资格 | 营业执照、章程、变更登记、信用信息 |
| 2 | 股权结构与股东信息 | 股东名册、出资验资、股权转让、代持、质押冻结 |
| 3 | 公司治理与组织结构 | 组织架构、三会运作、决议程序、内部制度 |
| 4 | 核心资产 | 不动产权属、设备清单、知识产权、权利负担 |
| 5 | 业务经营与合同管理 | 主营业务、核心合同、客户供应商、业务资质 |
| 6 | 财务与税务 | 财报审计、银行账户、纳税申报、税收优惠 |
| 7 | 劳动人事管理 | 劳动合同、社保公积金、竞业保密、劳动争议 |
| 8 | 重大债权债务与担保 | 银行借款、应付款、对外担保、应收账款 |
| 9 | 诉讼、仲裁与行政处罚 | 未决/已决案件、行政处罚、潜在纠纷 |
| 10 | 其他重要文件 | 对外投资、关联交易、环保安全生产 |

---

## 适合谁用

- 中国执业律师 / 律所实习生 / 初年级律师
- 需要把尽调工作流标准化、可追溯化的法律团队
- 在 Claude Code 环境中处理批量材料审核的法律工作者

---

## 使用提醒

- 路径占位符（`[项目存放路径]`）在使用时请替换为本机实际目录
- 本分享包不含任何真实客户材料或项目数据
- 财务、税务、评估等专业事项仍需结合相应专业意见
- 公开信息查询结果可能存在延迟或遗漏，请交叉核验

---

## 版本历史

| 版本 | 主要更新 |
|------|---------|
| **v26.6.21.1305**（当前）| Loop 化升级：新增 intake/adjudicate/update/run-dd 四模式；双轨尽调清单；Loop A/B 循环；6 个强制人工断点；推进闸门；工商数据按章节批量拉取；底稿与报告一致性终检 |
| v26.4.29.1545 | 企业信息查询拆分为独立 Skill（yd-enterprise-info）；支持 22 个接口自动翻页 |
| v26.4.25.2039 | 新增元典"按名称/股票简称检索"接口 |
| v26.4.25.2006 | 新增元典"按 id/USCC 详情"接口 |
| v26.4.20 | 基础版本（4 模式 + 10 章工作流） |

详细更新日志见 [CHANGELOG.md](CHANGELOG.md)。
