# legal-due-diligence

中国法律尽职调查 Skill 分享版。

- 版本：v26.4.25.2039
- 适用环境：Claude Code
- 运行要求：Python 3.10+

## 这个 Skill 是做什么的

这是一个用于中国法律尽职调查工作的写作型 Skill，覆盖完整工作流：

- 项目初始化
- 尽调底稿逐章撰写
- 完整性检查
- 尽调报告生成

支持的核心场景包括：

- 法律尽调
- 尽调底稿撰写
- DD 报告生成
- 公司主体尽调项目管理

## 目录结构

```text
legal-due-diligence-v26.4.25.2039/
├── SKILL.md
├── README.md
├── assets/
│   ├── report-template.md
│   └── working-paper-template.md
├── references/
│   ├── report-standards.md
│   ├── section-guide.md
│   ├── external-apis.md            # 外部 API 接入索引
│   └── chineselaw/
│       ├── company-detail.md       # 元典「按 id/USCC 详情」接口规范
│       └── company-info.md         # 元典「按名称检索」接口规范
└── scripts/
    ├── init_project.py             # 含 --uscc / --name-lookup 智能路由
    └── chineselaw_client.py        # 元典开放平台 API 客户端（多子命令）
```

## 安装方法

### 方法一：手动复制安装

1. 解压压缩包。
2. 将文件夹 `legal-due-diligence-v26.4.25.2039` 复制到你的 Claude Skills 目录。
3. **建议将文件夹重命名为 `legal-due-diligence`**，以保持与 Skill 名称一致。

常见目录示例：

```bash
~/.claude/skills/
```

安装后的目标结构建议如下：

```text
~/.claude/skills/legal-due-diligence/
├── SKILL.md
├── README.md
├── assets/
├── references/
└── scripts/
```

### 方法二：作为分享包保存

如果你只是想留档或转发，可以直接保留当前目录名 `legal-due-diligence-v26.4.25.2039`；
真正用于本地调用时，再改名为 `legal-due-diligence` 更稳妥。

## 使用方式

当用户提到下列需求时，可以调用本 Skill：

- 尽职调查
- 尽调
- 底稿
- due diligence
- DD报告
- 尽调报告
- 法律尽调

## 四种工作模式

### 1. init：初始化尽调项目

用途：
- 创建项目目录
- 生成 `project-info.md`
- 生成 `working-paper.md`
- 创建 `report/` 目录

示例：

```text
帮我初始化一个尽调项目：
- 目标公司：广州XX农业科技有限公司
- 委托人：深圳XX投资有限公司
- 路径：[项目存放路径]
- 基准日：2026-03-20
- 目的：股权收购
```

### 2. draft：撰写底稿

用途：
- 根据材料撰写某一章底稿
- 将内容写入 `working-paper.md`

示例：

```text
请帮我撰写第2章“股权结构与股东信息”的底稿。
材料路径：/path/to/materials/02-股权/
```

### 3. check：检查底稿完整性

用途：
- 检查 10 章结构是否完整
- 汇总缺失材料
- 汇总风险点
- 给出后续工作建议

示例：

```text
底稿写得差不多了，帮我做一次完整性检查。
```

### 4. report：生成尽调报告

用途：
- 将底稿转化为正式法律尽职调查报告
- 输出至 `report/` 目录

示例：

```text
底稿已全部完成，请帮我生成尽调报告。
```

## 使用提醒

### 1. 路径占位符需要自行替换

本分享版中的示例路径：

```text
路径：[项目存放路径]
```

这是占位写法，**使用时请替换为你自己的本机目录**，例如你实际准备存放项目的路径。

### 2. 示例公司名称均为占位示例

文档中的公司名、委托人名称、字段模板等均为示例或占位内容，使用时请按项目实际情况替换。

### 3. 这是分享版，不含真实项目材料

本包仅包含：
- Skill 说明
- 模板文件
- 参考资料
- 初始化脚本

不包含任何真实客户、真实项目或真实尽调底稿。

## 主要文件说明

- `SKILL.md`：Skill 主说明文件
- `scripts/init_project.py`：项目初始化脚本（支持 `--uscc` 自动拉取工商信息）
- `scripts/chineselaw_client.py`：元典开放平台 API 客户端
- `assets/working-paper-template.md`：底稿模板
- `assets/report-template.md`：报告模板
- `references/section-guide.md`：分章节调查指南
- `references/report-standards.md`：报告转化和语言规范
- `references/external-apis.md`：外部 API 接入索引与通用规则
- `references/chineselaw/company-detail.md`：元典「按 id/USCC 详情」接口字段映射与引用规范
- `references/chineselaw/company-info.md`：元典「按名称/股票简称检索」接口规范

## 外部 API 配置（可选）

如需启用元典开放平台接口（v26.4.25.2006 新增）：

```bash
export CHINESELAW_API_KEY=你的_api_key
```

凭证**绝不入库**到 skill 包或项目仓库。详情见 `references/external-apis.md`。

## 适合谁用

适合以下用户：

- 中国执业律师
- 律所实习生 / 初年级律师
- 需要标准化尽调工作流的法律团队
- 希望把底稿与报告写作流程结构化的人

## 注意事项

- 本 Skill 偏重法律尽调的**结构化写作与输出规范**。
- 财务、税务、评估等专业问题，仍建议结合对应专业意见使用。
- 公开信息查询结果可能存在延迟或遗漏，实际项目中仍应注意交叉核验。

## 版本说明

当前分享版为：`v26.4.25.2039`

### 版本说明

- v26.4.25.2039：新增元典「按名称/股票简称检索」接口（`company-info`）；init 支持 `--name-lookup` 智能路由
- v26.4.25.2006：新增元典「按 id/USCC 详情」接口（`company-detail`）
- v26.4.20：基础版本（4 模式 + 10 章工作流）

如后续继续迭代，建议同步维护：
- `metadata.version`
- 文件夹版本号
- 压缩包文件名
- README 中的版本说明
