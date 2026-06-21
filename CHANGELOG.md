# CHANGELOG

## v26.6.21.1305（2026-06-21）—— Loop 化全面升级

> 上一版本：v26.4.29.1545（2026-04-29）
>
> 本次更新基于三份规划文档（总执行计划 + 补充方案一/二）分 9 个阶段（Phase 0~8）实施，
> 历经约 2 个完整工作对话完成。核心目标：把每批材料到位→核验→律师认定→底稿更新的
> 完整推进，从手动多轮操作变为两个可循环的半自动 Loop。

---

### 一、整体架构变化

**Before（v26.4.29）**

```
init → draft → check → report
（4 个模式，每步手动触发，无状态机，无台账）
```

**After（v26.6.21）**

```
init
  ↓
[Loop A] intake → adjudicate（每批料重复）
  ↓
[Loop B] update → draft --mode incremental（只重做受影响章节）
  ↓
check → report → final_verify.py
```

新增三层状态追踪：
- **dd-checklist.md**：双轨清单（AI 研判轨 + 律师认定轨）
- **task-board.md**：章级状态机（未开始/进行中/已自检/待人工/已完成）
- **adjudication-log.md**：律师认定台账（每次认定/改判留痕）

---

### 二、新增文件

#### 脚本（`scripts/`）

| 文件 | 功能 |
|------|------|
| `reconcile_materials.py` | Loop A 核心引擎：材料匹配→AI 研判→双轨清单更新→台账→待补清单→章节映射表 |
| `update_taskboard.py` | 章节状态机更新：单章更新（状态/批次/断点）+ 批量标记受影响章节 |
| `check_gates.py` | 项目级推进闸门检查（AC-P1~P5），只读，输出结构化报告 |
| `fetch_enterprise_data.py` | 工商数据按章节批量拉取（调用 yd-enterprise-info，支持 dry-run） |
| `final_verify.py` | 底稿与报告一致性终检（V-WP1~4 + V-R1~5 + V-X1~2） |

#### 参考文档（`references/`）

| 文件 | 功能 |
|------|------|
| `acceptance-criteria.md` | 验收标准手册（AC-C1~C7 章级 + AC-P1~P5 项目级），阶段 0 冻结 |
| `orchestration-guide.md` | run-dd 编排规则手册（Loop 骨架/full-staged/断点清单/状态机 schema/双轨字段 schema） |

#### 资产模板（`assets/`）

| 文件 | 功能 |
|------|------|
| `dd-checklist-template.md` | 双轨尽调清单模板（88 条检查项，10 章，律师认定默认"待认定"） |
| `materials-ledger-template.md` | 资料台账模板（批次追加格式） |

---

### 三、修改文件

#### `scripts/init_project.py`

- **新增**：生成 `dd-checklist.md`（从 `assets/dd-checklist-template.md` 复制）
- **新增**：生成 `materials-ledger.md`（从 `assets/materials-ledger-template.md` 复制）
- **新增**：生成 `adjudication-log.md`（空认定台账，含表头）
- **新增**：生成 `task-board.md`（10章状态机，初始状态全为"未开始"）
- **新增**：`generate_task_board(args)` 函数，含"章节/状态/数据基准批次/受影响/断点事项/自检备注"6 列
- **新增**：`generate_adjudication_log()` 函数
- **新增**：`copy_template(src_name, dst_path)` 函数
- **修改**：`generate_chapter_section()` 章节头部新增"数据基准批次"字段
- **修改**：`main()` 中整合以上新生成逻辑，生成文件数从 2 增至 8

#### `SKILL.md`

- **版本号更新**：`v26.4.29.1545` → `v26.6.21.1305`
- **工作流程图**：更新为 Loop A/B 结构
- **模式数量**：四种 → 八种
- **新增模式 5**：intake（资料核验）
- **新增模式 6**：adjudicate（律师终裁）
- **新增模式 7**：update（增量更新，Loop B）
- **新增模式 8**：run-dd（一键尽调编排）
- **模式 2（draft）更新**：新增步骤 4（填"数据基准批次"字段）、步骤 6（章级自检 AC-C1~C7 + update_taskboard.py 调用）；章节头部格式示例更新；支持 `--mode incremental`
- **外部数据源节**：新增"自动化路径"（fetch_enterprise_data.py），与"手动路径"并列

---

### 四、核心设计决策

#### 1. 双轨清单与律师轨保护

`dd-checklist.md` 每行 13 列，分两轨：

- **AI 研判轨**（列 5/6/7/13：AI研判/AI置信/需复核/最近批次）：由 `reconcile_materials.py` 写入
- **律师认定轨**（列 8~12：律师认定/认定人/认定日期/律师批注/本项齐备标准）：**任何脚本绝不改写**

实现方式：`parse_checklist()` 将每行原始列存入 `item["_original_cols"]`；`render_row()` 只更新 4 个 AI 轨列，其余从 `_original_cols` 原样还原。

律师认定默认值：`待认定`（绝不默认"已齐备"）。

#### 2. 累计批次模式

`reconcile_materials.py` 的 `run()` 函数在材料比对后：

```python
if not matched:
    continue  # 本批无匹配 → 继承历史研判，不覆写
```

确保第2批到位后，第1批已认定的历史研判结果不被清空。

#### 3. 冲突检测

`check_conflict(item, new_verdict)` 返回 True 的两种情形：

- 律师认定=已齐备 且 AI研判 ∈ {🟡部分, ❌未收}
- 律师认定 ∈ {不适用, 豁免} 且 AI研判=✅已收

冲突项在研判报告中标 ⚠️，并被写入章节-材料映射表的"受影响章节"。

#### 4. 章节受影响机制

`_write_chapter_map()` 函数根据两类条件计算"受影响章节"：

- 本批有新文件覆盖的章节（`new_covered`）
- 本批触发冲突的清单项所在章节（`conflict_items`）

受影响章节列表写入 `章节-材料映射表-第k批.md`，供 update 模式和 `update_taskboard.py --mark-affected` 使用。

#### 5. 推进闸门（AC-P1~P5）

`check_gates.py` 实现五项校验，任一失败则不可出报告：

| 代码 | 检查逻辑 |
|------|---------|
| AC-P1 | 遍历 task-board.md 所有章节行，状态须 ∈ {已自检, 已完成} |
| AC-P2 | 遍历 dd-checklist.md 重要程度=高的项，律师认定须 ∈ {已齐备, 不适用, 豁免} |
| AC-P3 | 存在冲突（律师认定与 AI研判矛盾）且 adjudication-log.md 中无对应认定记录 |
| AC-P4 | working-paper.md"附：免责限制条件"节中须含高重要度未齐备项编号 |
| AC-P5 | task-board.md 无"待人工"状态章节 |

#### 6. 工商数据章节映射

`fetch_enterprise_data.py` 内置章节→子命令映射（与 `external-apis.md` 对齐）：

- 第1章：`base-info`, `change`, `abnormal`, `serious-violation`
- 第2章：`base-info`, `equity-pledge`, `equity-frozen`
- 第4章：`brand`, `patent`, `soft-right`, `copyright-work`, `website`
- 第6章：`tax-arrears`（建议）
- 第8章：`outbound-guarantee`, `equity-pledge`
- 第9章：`litigation-stat/doc/executed/dishonest/admin-penalty` + 4 个建议
- 第10章：`outbound-invest`
- 第5、7章：无适用接口，自动跳过

USCC 自动从 `project-info.md` 读取；凭证只走环境变量 `CHINESELAW_API_KEY`，脚本不接受也不写入任何凭证参数。

#### 7. 底稿与报告终检（V-WP/R/X）

`final_verify.py` 分三组检查：

- **V-WP1~4（硬检查）**：底稿 10 章完整、6 段结构、无空段、无占位符
- **V-R1~5（硬检查）**：报告存在、含关键节、无律师备忘泄漏、无草稿标记、无 AI 注记
- **V-X1~2（宽松告警）**：🔴高风险计数一致（误差≤1）、❌未获取高重要度项在报告免责声明中有对应描述

---

### 五、设计约束（全阶段通用）

以下约束贯穿所有阶段，任何代码均不得违背：

1. **律师轨只读**：任何脚本/自动流程不得改写律师认定五列，只有 adjudicate 模式由律师指示写入
2. **律师认定默认值**：必须是"待认定"，绝不能默认"已齐备"
3. **不猜归类**：材料匹配不确定时一律进"待人工归类"，不允许 AI 猜测归属后写入
4. **留痕**：每批核验、每次认定/改判、每次增量改动都写台账/认定日志
5. **凭证安全**：CHINESELAW_API_KEY 等凭证只走环境变量，绝不入库（任何 .md / .py 文件均不含凭证）
6. **向后兼容**：原 init/draft/check/report 四模式与既有项目结构完全向后兼容

---

### 六、已知限制

- **材料匹配精度**：`reconcile_materials.py` 使用关键词匹配（文件名→清单项），对重名文件或非标准命名的材料可能匹配失准，此时应进"待人工归类"由律师手动归类
- **V-X2 宽松性**：终检对"§X.3 未获取项"在报告中的覆盖采用关键词前缀匹配，可能存在误判；律师在送审前仍须目视核查免责声明节
- **多章并行约束**：run-dd 模式下多章分析可并行，但写入 `working-paper.md` 时须串行落盘，否则存在文件冲突风险

---

### 七、向后兼容说明

本版对 v26.4.29 的项目**完全向后兼容**：

- 原 init/draft/check/report 四种触发词及行为不变
- 已有项目（未使用双轨清单）可继续使用原 4 模式
- 如需升级旧项目至双轨模式：在项目根目录补建 `dd-checklist.md`（从模板复制）和 `task-board.md`（从 init 脚本生成），即可接入 intake/adjudicate 流程

---

## v26.4.29.1545（2026-04-29）

- 企业信息查询从 legal-due-diligence 拆分为独立 Skill（yd-enterprise-info）
- yd-enterprise-info 支持 22 个元典接口，全部支持自动翻页
- section-guide.md 各章新增 yd-enterprise-info 调用提示
- 新增 `references/chineselaw/enterprise-endpoints-summary.md` 接口速查表

## v26.4.25.2039（2026-04-25）

- 新增元典"按名称/股票简称检索"接口（search-company）
- init 支持 `--name-lookup` 智能路由

## v26.4.25.2006（2026-04-25）

- 新增元典"按 id/USCC 详情"接口（company-detail）

## v26.4.20（2026-04-20）

- 基础版本：4 种工作模式（init/draft/check/report）、10 章工作流、底稿与报告两阶段输出
