# legal-due-diligence

面向中国公司类法律尽职调查的写作技能：以单一底稿逐章分析材料，由律师判断是否补件；律师要求出报告后逐章转化为正式尽调报告，并可起草主要法律问题清单（问题与处理措施合一）；首先撰写 Markdown 文稿，待整稿完成、律师指令后按参考终稿样式转换为排版良好的 DOCX。

## 工作方式

```
确定项目问题 → 逐章阅读材料 → 顺序续写同一份 Markdown 底稿 → 律师判断是否补件
→ 逐章转为报告 → 法律文风复核 → （律师指令后）转换为 DOCX 成稿
                                    ↘ （可选）主要法律问题清单
```

核心约定：

- **一个项目只有两份文稿**：一份底稿、一份报告（各自先为 Markdown，定稿后转 DOCX）；律师要求时另有一份主要法律问题清单。
- **一次对话只写一章**，在既有文稿基础上顺序续写，不改动已写好的前文；发现前文问题在对话中报告，由律师决定。主要法律问题清单属于跨章节汇总，可以在一次对话中完成。
- **先事实、后意见**：事实段完整交代材料内容和勾稽关系；律师意见完成「事实 → 规则 → 判断 → 影响 → 建议」的推理链。
- **少用表格**：只有现行基本登记信息、现行股权结构等结构化数据才用表格；历史沿革分段完整列举，法律分析一律用连贯段落。
- **报告作确定性陈述**：底稿可以坦率记录缺件和疑点；报告和问题清单正文不得出现“现有材料不能证明”“无法确认”“未提供”等调查限制式表述，统一限定集中在“声明与限定条件”。
- **问题清单不分级、问题与措施合一**：交易类项目按"先决条件"和"交割后处理事项"分两组，非交易类项目只列一份清单；每个问题与其处理措施写在同一条目中。
- **历史沿革分段完整列举**：公司登记事项、股权和董事监事高级管理人员的历次变更逐次分段、写明依据文件、完整列明变更前后内容，不使用表格，不作概述。
- **报告全文中文**：仅证照编号、域名、依法登记的外文名称等无法回避的原文可以保留。
- **不预设项目类型**：根据已经确定的项目目的或委托范围调整问题，不默认股权收购、资产收购、增资、合资、融资、重组或一般合规核查中的任一场景。

## 目录结构

```
legal-due-diligence/
├── SKILL.md                       # 入口：不可变规则、任务路由、标准工作流
├── agents/
│   └── openai.yaml
├── references/
│   ├── working-paper-workflow.md  # 单一 Markdown 底稿工作流
│   ├── report-writing.md          # 报告骨架与逐章写作规则
│   ├── history-records.md         # 历史沿革写法（分段完整列举）
│   ├── issue-list.md              # 主要法律问题清单（可选）
│   ├── legal-style.md             # 法律中文文风与去 AI 化规则
│   ├── chapter-map.md             # 项目化章节地图（十章导航）
│   ├── quality-gates.md           # 章级质量检查
│   ├── docx-format.md             # 成稿 DOCX 转换规范
│   ├── public-information.md      # 外部信息与法律检索规则
│   └── research-tool-routing.md   # 企业信息与司法案例检索工具路由
├── scripts/
│   └── sync_skill.py              # 多运行时安装、检查与同步
└── tests/
    └── test_sync_skill.py         # 安装器的标准库测试
```

## 单一正本与运行时

本 GitHub 仓库是技能的唯一正本。各运行时技能目录中的内容都是由正本生成的安装副本，不应直接编辑；更新时先更新本仓库，再重新同步全部使用中的运行时。

Codex 模型、Codex CLI 和 Hermes Agent 是三个不同层次的概念：

- **Codex 模型**是完成推理和写作的模型，不是本地技能目录，也不会自行决定从哪个目录加载技能；
- **Codex CLI**是运行模型和加载本地技能的宿主；Codex 当前的 USER 级技能目录是 `$HOME/.agents/skills`，本技能默认安装到 `$HOME/.agents/skills/legal-due-diligence`；
- **Hermes Agent**是另一套代理运行时。Ophilia 是 Hermes 的 profile；仓库默认把本技能同步到该 profile 自己的 `skills/legal/` 下。

谁直接执行尽调任务，谁就必须能发现本技能。如果 Hermes 只是把任务交给 Codex CLI 执行，Codex 侧安装是必需的；仍建议让 Hermes/Ophilia 发现同一版本，供 Ophilia 理解任务、正确路由并验收结果。仓库默认采用两个物理安装副本，均从本仓库同步，不应彼此复制或分别维护。

## macOS 安装与同步

安装器需要 Python 3.10 或更高版本，且仅使用 Python 标准库。它只把运行时需要的 `SKILL.md`、`agents/` 和 `references/` 镜像到目标目录，不会复制 `.git`、`tests`、`scripts`、缓存或其他开发文件。同步会删除目标技能目录中正本已不存在的文件以及本地额外文件，因此不要在安装副本中保存自定义内容。

以下命令均在本仓库根目录执行。

### Codex CLI

不指定目标时默认只处理 Codex：

```bash
python3 scripts/sync_skill.py --dry-run
python3 scripts/sync_skill.py
python3 scripts/sync_skill.py --check
```

上述命令的默认目标是 `${HOME}/.agents/skills/legal-due-diligence`。`--check` 不写盘；完全一致时退出码为 `0`，存在缺失、修改或陈旧文件时退出码为 `1`。如需指定另一个容纳各 skill 目录的 Codex skills 目录，可传入 `--codex-skills-dir PATH`；最终目标是 `PATH/legal-due-diligence`。

Codex 支持 symlinked skill folders，因此也可以自行把 `${HOME}/.agents/skills/legal-due-diligence` 建成指向本仓库的符号链接。不过，本仓库的同步脚本采用可重建的物理镜像，并会把目标符号链接视为类型冲突；请在“符号链接”与“运行同步脚本”两种管理方式中择一。

### 当前 Ophilia profile 的 Hermes Agent

Hermes 目标必须明确选择 profile，防止安装到错误的 Hermes home。当前 profile 的路径可不含用户名地写为：

```bash
export HERMES_HOME="${HOME}/.hermes/profiles/ophilia"
```

安装目标为 `${HERMES_HOME}/skills/legal/legal-due-diligence`。

同时安装并检查 Codex 与当前 Ophilia profile：

```bash
python3 scripts/sync_skill.py --dry-run --codex --hermes
python3 scripts/sync_skill.py --codex --hermes
python3 scripts/sync_skill.py --check --codex --hermes
```

`--hermes` 只有在 `HERMES_HOME` 已设置时才会运行。也可以不设置环境变量，逐次显式传入 profile：

```bash
python3 scripts/sync_skill.py --codex \
  --hermes-home "${HOME}/.hermes/profiles/ophilia"
python3 scripts/sync_skill.py --check --codex \
  --hermes-home "${HOME}/.hermes/profiles/ophilia"
```

仅设置 `HERMES_HOME` 不会自动选择 Hermes 目标；还需传入 `--hermes`，或者直接使用 `--hermes-home PATH`。

### 可选：由 Codex 与 Hermes 共享同一目录

Hermes 可以在其配置中把 `${HOME}/.agents/skills` 加入 `skills.external_dirs`，从而直接扫描 Codex 的 USER 级技能目录，不再为 Hermes 维护第二份物理副本。例如，配置的相应部分可写为：

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
```

这是一种可选架构，不是仓库同步脚本的默认行为。Hermes 对同名技能的优先级是 project → profile-local skills → `skills.create_dir` → `external_dirs`；因此，若 profile-local 中仍有旧版 `legal-due-diligence`，它会遮蔽 external 目录中的版本。不同来源的同名技能不会合并。选择共享目录方案时，应先自行处理这些同名旧副本；仓库默认提供的保守方案仍是同步到 Hermes profile-local。

### 从 GitHub 更新

```bash
export HERMES_HOME="${HOME}/.hermes/profiles/ophilia"
git pull --ff-only
python3 scripts/sync_skill.py --dry-run --codex --hermes
python3 scripts/sync_skill.py --codex --hermes
python3 scripts/sync_skill.py --check --codex --hermes
```

这样 GitHub 仓库始终是正本，Codex 的 `${HOME}/.agents/skills/legal-due-diligence` 与 Hermes profile-local 目标只是同一正本的可重建镜像。若只运行 Codex，可省略 `--hermes`；若只运行 Hermes，可省略 `--codex`。

### 可选：Claude Code

兼容目标可通过 `--claude` 安装到 `~/.claude/skills/legal-due-diligence`，或用 `--claude-home PATH` 指定其他 Claude home。例如，同时检查三个运行时：

```bash
python3 scripts/sync_skill.py --check --codex --hermes --claude
```

## 使用示例

底稿阶段：

> 使用 $legal-due-diligence 分析「[本轮章节]」。本项目目的或委托范围为……，材料路径为……，请续写主底稿……md；不要预设未说明的交易类型。

报告阶段：

> 使用 $legal-due-diligence，根据主底稿和原始材料撰写报告「[本轮章节]」，续写报告……md。报告作确定性陈述，底稿中的调查限制按 report-writing.md 第五节改写为事实或交易措施。

问题清单阶段（可选）：

> 使用 $legal-due-diligence，根据主底稿起草主要法律问题清单，时点为报告前；本项目为交易类项目，按交割先决条件和交割后处理事项分两组。

成稿阶段：

> 报告已写完并经我审阅，请按 docx-format.md 的版式把……md 转换为 DOCX。

## 版本

当前版本 `0.5.1`。

完整的版本演进和变更说明见 [CHANGELOG.md](CHANGELOG.md)；可下载的历史版本见 [GitHub Releases](https://github.com/malnlda/legal-due-diligence/releases)。
