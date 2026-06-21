#!/usr/bin/env python3
"""
reconcile_materials.py  v26.6.21.1305
Loop A 资料齐备性核验引擎

用法:
    python3 reconcile_materials.py \
        --project /path/to/DD项目/ \
        --batch   /path/to/materials/batch-02/ \
        --batch-no 2

功能:
    1. 把本批材料与 dd-checklist.md 逐项比对
    2. 只写 AI 轨（AI研判/AI置信/需复核），绝不触碰律师轨
    3. 冲突检测：律师已认定"已齐备"但新证据有疑 → 标 ⚠️，不覆盖
    4. 生成 研判报告-第k批.md、更新 materials-ledger.md、生成待补清单

约束（硬约束，不得放宽）:
    - 律师轨 7 列（律师认定/认定人/认定日期/律师批注/本项齐备标准）绝不写入
    - 匹配不确定的文件一律进"待人工归类"，不猜
    - 律师认定默认值保持"待认定"，本脚本不写此列
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── 常量 ────────────────────────────────────────────────────────────────────

VERDICT_RECEIVED = "✅已收"
VERDICT_PARTIAL  = "🟡部分"
VERDICT_MISSING  = "❌未收"
VERDICT_NA       = "⚪疑似不适用"

CONF_HIGH = "高"
CONF_MED  = "中"
CONF_LOW  = "低"

LAWYER_OK     = "已齐备"
LAWYER_NA     = "不适用"
LAWYER_WAIVED = "豁免"

# dd-checklist 表头各列索引（0-based，去掉两端空格后的列）
COL_ID       = 0
COL_NAME     = 1
COL_CHAPTER  = 2
COL_PRIORITY = 3
COL_AI_V     = 4   # AI研判
COL_AI_C     = 5   # AI置信
COL_REVIEW   = 6   # 需复核
COL_LAWYER   = 7   # 律师认定（只读）
COL_L_NAME   = 8   # 认定人（只读）
COL_L_DATE   = 9   # 认定日期（只读）
COL_L_NOTE   = 10  # 律师批注（只读）
COL_STANDARD = 11  # 本项齐备标准（只读）
COL_BATCH    = 12  # 最近批次

TOTAL_COLS = 13

# 关键词映射：清单项编号 → 文件名匹配关键词列表（优先级从高到低）
KEYWORD_MAP: dict[str, list[str]] = {
    "1.1": ["营业执照", "business_license", "yyzz"],
    "1.2": ["公司章程", "章程", "articles"],
    "1.3": ["章程修正案", "章程修订", "章程变更"],
    "1.4": ["变更登记", "工商变更"],
    "1.5": ["设立批准", "审批文件", "批准文件"],
    "1.6": ["议事规则", "议事程序"],
    "1.7": ["印章", "印章管理"],
    "1.8": ["信用信息", "企业信用", "信用公示"],
    "2.1": ["股东名册", "股东名单"],
    "2.2": ["出资证明书", "出资证明"],
    "2.3": ["股东主体", "股东营业", "股东身份"],
    "2.4": ["验资报告", "验资", "出资凭证", "银行进账"],
    "2.5": ["股权转让协议", "股权转让"],
    "2.6": ["增资扩股协议", "增资协议", "扩股"],
    "2.7": ["股权变动决议", "股东会决议"],
    "2.8": ["优先购买权", "放弃声明"],
    "2.9": ["代持协议", "代持", "隐名"],
    "2.10": ["一致行动协议", "一致行动"],
    "2.11": ["对赌协议", "业绩承诺", "对赌"],
    "2.12": ["股权质押", "质押登记"],
    "2.13": ["股权冻结", "冻结"],
    "3.1": ["组织架构图", "组织结构图", "架构图"],
    "3.2": ["分支机构", "子公司设置"],
    "3.3": ["董监高名单", "董事名单", "监事名单", "高管名单", "简历"],
    "3.4": ["任职", "聘任", "选举", "任职合法"],
    "3.5": ["薪酬", "薪资方案"],
    "3.6": ["股东会会议", "股东会记录", "股东会决议", "股东大会"],
    "3.7": ["董事会会议", "董事会记录", "董事会决议"],
    "3.8": ["监事会会议", "监事会记录", "监事会决议"],
    "3.9": ["内部管理制度", "管理制度", "规章制度", "财务管理制度"],
    "4.1": ["不动产权证", "房产证", "土地证", "不动产登记证"],
    "4.2": ["土地出让合同", "划拨决定"],
    "4.3": ["不动产登记查询", "登记查询", "抵押登记"],
    "4.4": ["建设工程", "规划许可", "施工许可", "竣工验收"],
    "4.5": ["租赁合同", "房屋租赁"],
    "4.6": ["设备清单", "固定资产清单", "设备采购"],
    "4.7": ["行驶证", "登记证", "车辆"],
    "4.8": ["商标注册证", "商标"],
    "4.9": ["专利证书", "专利"],
    "4.10": ["著作权登记", "软件著作权", "版权", "软著"],
    "4.11": ["域名", "ICP备案"],
    "4.12": ["知识产权许可", "许可合同", "授权合同"],
    "5.1": ["业务介绍", "商业计划书", "年度经营计划", "经营总结"],
    "5.2": ["销售合同", "服务合同", "客户合同", "前十大客户"],
    "5.3": ["采购合同", "供应商合同", "前十大供应商"],
    "5.4": ["合作协议", "合资协议", "联营协议", "战略合作"],
    "5.5": ["客户名单", "客户清单", "客户台账"],
    "5.6": ["供应商名单", "供应商清单", "供应商台账"],
    "5.7": ["许可证", "资质证书", "资质", "经营许可"],
    "5.8": ["特种经营许可", "特许经营"],
    "6.1": ["财务报表", "资产负债表", "利润表", "现金流量表"],
    "6.2": ["审计报告"],
    "6.3": ["管理报表", "内部报表"],
    "6.4": ["银行账户", "对账单", "银行流水"],
    "6.5": ["银行授信", "授信协议"],
    "6.6": ["税务登记", "纳税人资格"],
    "6.7": ["纳税申报", "税务申报表", "增值税申报", "所得税申报"],
    "6.8": ["税收优惠", "优惠政策文件"],
    "6.9": ["税务处罚", "税务罚款决定"],
    "7.1": ["员工名册", "员工名单", "花名册"],
    "7.2": ["劳动合同"],
    "7.3": ["高管劳动合同", "核心人员合同", "关键员工合同"],
    "7.4": ["社保缴纳", "社会保险", "社保"],
    "7.5": ["公积金缴纳", "住房公积金", "公积金"],
    "7.6": ["员工手册", "人事制度"],
    "7.7": ["竞业限制协议", "竞业协议", "竞业"],
    "7.8": ["保密协议", "NDA", "保密"],
    "7.9": ["股权激励", "期权计划"],
    "7.10": ["劳动仲裁", "劳动争议", "劳动诉讼"],
    "8.1": ["借款合同", "贷款合同", "银行借款"],
    "8.2": ["担保合同", "保证合同", "抵押合同", "质押合同"],
    "8.3": ["应付款明细", "应付账款"],
    "8.4": ["融资租赁合同", "融资租赁"],
    "8.5": ["对外担保合同", "为他人担保", "担保决议"],
    "8.6": ["应收账款明细", "账龄分析", "应收账款"],
    "8.7": ["其他应收款", "关联方往来"],
    "9.1": ["起诉状", "答辩状", "诉讼材料", "仲裁材料", "案件"],
    "9.2": ["判决书", "裁决书", "调解书"],
    "9.3": ["行政处罚决定", "行政处罚书", "处罚决定"],
    "9.4": ["裁判文书查询", "执行信息查询", "信用查询"],
    "10.1": ["对外投资", "被投资公司"],
    "10.2": ["关联方名单", "关联交易协议"],
    "10.3": ["环境影响评价", "环评", "排污许可证"],
    "10.4": ["环保验收", "竣工环保验收"],
    "10.5": ["安全生产许可证"],
    "10.6": ["消防验收", "消防备案"],
    "10.7": ["政府补贴", "补贴文件"],
    "10.8": [],  # 自定义项，开放匹配
}


# ─── 表格解析 ────────────────────────────────────────────────────────────────

def _split_row(line: str) -> list[str]:
    """把 | a | b | c | 拆成 ['a', 'b', 'c']（去头尾 |，每格 strip）"""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|[-| :]+\|\s*$", line))


def parse_checklist(path: Path) -> tuple[list[str], list[dict]]:
    """
    解析 dd-checklist.md（支持多章节多表格）。
    返回 (all_lines, items)：
      all_lines: 文件全行列表（含换行符），用于原位替换
      items: 每项 dict，含 '_line_idx' 指向 all_lines 中的行号
             以及 '_original_cols' 保存原始列表（供安全写回时使用）
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    items: list[dict] = []
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("|"):
            cols = _split_row(stripped)
            # 识别双轨表头
            if "编号" in cols and "AI研判" in cols:
                in_table = True
                continue
            if is_separator(stripped):
                continue
            if in_table and cols[COL_ID] and not cols[COL_ID].startswith("-"):
                if len(cols) < TOTAL_COLS:
                    cols += [""] * (TOTAL_COLS - len(cols))
                item = {
                    "编号": cols[COL_ID],
                    "资料项": cols[COL_NAME],
                    "章节": cols[COL_CHAPTER],
                    "重要程度": cols[COL_PRIORITY],
                    "AI研判": cols[COL_AI_V],
                    "AI置信": cols[COL_AI_C],
                    "需复核": cols[COL_REVIEW],
                    "律师认定": cols[COL_LAWYER],   # 只读，绝不由本脚本改写
                    "认定人": cols[COL_L_NAME],
                    "认定日期": cols[COL_L_DATE],
                    "律师批注": cols[COL_L_NOTE],
                    "本项齐备标准": cols[COL_STANDARD],
                    "最近批次": cols[COL_BATCH],
                    "_line_idx": i,
                    "_original_cols": list(cols),  # 保存原始解析结果
                }
                items.append(item)
            elif in_table:
                pass
        else:
            in_table = False

    return lines, items


def render_row(item: dict) -> str:
    """
    安全写回：只更新 AI 轨四列（AI研判/AI置信/需复核/最近批次），
    其余列（特别是律师轨 7-11 列）**原样保留**，绝不覆盖。
    """
    cols = list(item["_original_cols"])  # 从原始解析结果出发
    cols[COL_AI_V]  = item["AI研判"]
    cols[COL_AI_C]  = item["AI置信"]
    cols[COL_REVIEW] = item["需复核"]
    cols[COL_BATCH]  = item["最近批次"]
    # 律师轨 COL_LAWYER(7) ~ COL_STANDARD(11) 不碰
    return "| " + " | ".join(cols) + " |\n"


def write_checklist(path: Path, all_lines: list[str], items: list[dict]) -> None:
    """原位替换 AI 轨数据行，律师轨列不动，写回文件"""
    for item in items:
        all_lines[item["_line_idx"]] = render_row(item)
    path.write_text("".join(all_lines), encoding="utf-8")


# ─── 文件扫描与匹配 ───────────────────────────────────────────────────────────

READABLE_EXTS = {".txt", ".md", ".pdf", ".docx", ".doc", ".xlsx", ".xls",
                 ".csv", ".png", ".jpg", ".jpeg"}


def scan_batch(batch_path: Path) -> list[Path]:
    """扫描批次目录，返回所有文件"""
    if batch_path.is_dir():
        return [f for f in batch_path.rglob("*") if f.is_file()
                and not f.name.startswith(".")]
    elif batch_path.is_file():
        return [batch_path]
    return []


def _name_keywords(filename: str) -> set[str]:
    """从文件名提取可匹配的 token（去扩展名，拆分常见分隔符）"""
    stem = Path(filename).stem
    tokens = re.split(r"[_\-\s\(\)\[\]（）【】、，。]+", stem)
    return {t.strip() for t in tokens if t.strip()}


def match_file_to_items(filepath: Path, items: list[dict]
                        ) -> list[tuple[str, str, str]]:
    """
    尝试把一个文件匹配到清单项。
    返回 list of (item_id, confidence, reason)
    匹配不确定 → 返回空列表（由调用方归入"待人工归类"）
    """
    fname = filepath.name
    fname_lower = fname.lower()
    matches: list[tuple[str, str, str]] = []

    for item in items:
        item_id = item["编号"]
        keywords = KEYWORD_MAP.get(item_id, [])
        if not keywords:
            continue

        # 强匹配：文件名含关键词
        strong_hit = [kw for kw in keywords if kw in fname]
        weak_hit   = [kw for kw in keywords if kw.lower() in fname_lower]

        if strong_hit:
            reason = f"文件名命中关键词：{'、'.join(strong_hit[:2])}"
            matches.append((item_id, CONF_HIGH, reason))
        elif weak_hit:
            reason = f"文件名弱匹配：{'、'.join(weak_hit[:2])}（大小写不敏感）"
            matches.append((item_id, CONF_MED, reason))

    # 若命中多项 → 降为低置信（文件可能是合并文档）
    if len(matches) > 1:
        matches = [(iid, CONF_LOW, r + "（文件可能跨多项）") for iid, _, r in matches]

    return matches


# ─── 研判逻辑 ────────────────────────────────────────────────────────────────

def determine_verdict(item: dict, matched_files: list[tuple[Path, str, str]]
                      ) -> tuple[str, str, bool, str]:
    """
    决定 AI研判 / AI置信 / 需复核 / 审查意见。
    matched_files: list of (filepath, confidence, reason)
    返回 (verdict, confidence, needs_review, review_reason)
    """
    if not matched_files:
        return VERDICT_MISSING, CONF_HIGH, False, "本批次无匹配文件"

    # 综合置信：取所有匹配中最低的
    confs = [c for _, c, _ in matched_files]
    if CONF_LOW in confs:
        conf = CONF_LOW
    elif CONF_MED in confs:
        conf = CONF_MED
    else:
        conf = CONF_HIGH

    reasons = "；".join(r for _, _, r in matched_files)
    files_desc = "、".join(f.name for f, _, _ in matched_files[:3])
    if len(matched_files) > 3:
        files_desc += f"等共{len(matched_files)}份"

    # 判定研判值
    # 若本项"本项齐备标准"中有"历次""全套""近三年"等词，当只有1份时认为部分
    standard = item.get("本项齐备标准", "")
    multi_keywords = ["历次", "全套", "近三年", "所有", "全部", "各"]
    needs_multi = any(kw in (item["资料项"] + standard) for kw in multi_keywords)

    if len(matched_files) >= 1 and conf == CONF_HIGH and not needs_multi:
        verdict = VERDICT_RECEIVED
    elif len(matched_files) >= 1 and (conf in (CONF_MED, CONF_LOW) or needs_multi):
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_MISSING

    review_reason = f"匹配文件：{files_desc}；依据：{reasons}"

    # 需复核判定（规则来自 orchestration-guide §八）
    needs_review = False
    review_flag_reasons: list[str] = []

    if conf in (CONF_MED, CONF_LOW):
        needs_review = True
        review_flag_reasons.append(f"AI置信={conf}")

    if item["重要程度"] == "高" and verdict != VERDICT_RECEIVED:
        needs_review = True
        review_flag_reasons.append("重要程度=高且非✅已收")

    if review_flag_reasons:
        review_reason += f"；提请复核原因：{'、'.join(review_flag_reasons)}"

    return verdict, conf, needs_review, review_reason


def check_conflict(item: dict, new_verdict: str) -> bool:
    """
    检测冲突：律师已认定"已齐备"，但新证据显示可能有问题。
    (新证据=部分/未收 时触发)
    返回 True = 存在冲突
    """
    lawyer_val = item.get("律师认定", "").strip()
    if lawyer_val == LAWYER_OK and new_verdict in (VERDICT_PARTIAL, VERDICT_MISSING):
        return True
    # 律师标"不适用/豁免"，但本批出现该类文件
    if lawyer_val in (LAWYER_NA, LAWYER_WAIVED) and new_verdict == VERDICT_RECEIVED:
        return True
    return False


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def run(args) -> None:
    project_dir = Path(args.project)
    batch_path  = Path(args.batch)
    batch_no    = args.batch_no
    batch_label = f"第{batch_no}批"
    now_str     = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str    = datetime.now().strftime("%Y%m%d")

    checklist_path = project_dir / "dd-checklist.md"
    ledger_path    = project_dir / "materials-ledger.md"
    report_path    = project_dir / f"研判报告-{batch_label}.md"
    pending_path   = project_dir / f"待补充资料清单-{batch_label}-{date_str}.md"

    if not checklist_path.exists():
        sys.exit(f"❌ 未找到 dd-checklist.md：{checklist_path}\n"
                 "   请先运行 init 模式初始化项目。")

    # 1. 解析清单
    all_lines, items = parse_checklist(checklist_path)
    print(f"📋 加载清单：{len(items)} 项")

    # 2. 扫描批次文件
    batch_files = scan_batch(batch_path)
    print(f"📂 本批文件：{len(batch_files)} 份")
    if not batch_files:
        print("⚠️  批次目录为空，无文件可核验。")

    # 3. 文件 → 清单项映射
    #    file_to_items[file] = [(item_id, conf, reason), ...]
    #    item_to_files[item_id] = [(filepath, conf, reason), ...]
    file_to_items: dict[Path, list[tuple[str, str, str]]] = {}
    item_to_files: dict[str, list[tuple[Path, str, str]]] = {it["编号"]: [] for it in items}
    unmatched_files: list[Path] = []

    for fpath in batch_files:
        matches = match_file_to_items(fpath, items)
        if matches:
            file_to_items[fpath] = matches
            for iid, conf, reason in matches:
                item_to_files[iid].append((fpath, conf, reason))
        else:
            unmatched_files.append(fpath)

    print(f"🔗 匹配到清单：{len(file_to_items)} 份；待人工归类：{len(unmatched_files)} 份")

    # 4. 逐项研判，更新 AI 轨，检测冲突
    review_items:   list[tuple[dict, str, str]] = []  # (item, verdict, review_reason)
    conflict_items: list[tuple[dict, str]] = []       # (item, conflict_reason)
    new_covered:    list[str] = []  # 本批新增变为 ✅/🟡 的项编号

    for item in items:
        iid = item["编号"]
        matched = item_to_files.get(iid, [])

        # 跳过"待人工归类"项（不在 KEYWORD_MAP 或 item_id 不规范的）
        if iid not in KEYWORD_MAP:
            continue

        prev_verdict = item.get("AI研判", "").strip()

        # 累积模式：本批无该项证据 → 保留历史研判，不覆盖
        # 只有本批实际带来该项证据时才更新 AI 轨
        if not matched:
            continue

        verdict, conf, needs_review, review_reason = determine_verdict(item, matched)

        # 冲突检测
        conflict = check_conflict(item, verdict)
        if conflict:
            conflict_reason = (
                f"律师已认定={item.get('律师认定','?')}，"
                f"但本批研判={verdict}（{review_reason}）"
            )
            conflict_items.append((item, conflict_reason))
            needs_review = True
            review_reason = f"⚠️ 与既有律师认定冲突：{conflict_reason}"

        # 律师标"不适用/豁免"且新批次有新料 → 提请复核（已由 check_conflict 处理）

        # 记录本批新增覆盖项
        if (prev_verdict not in (VERDICT_RECEIVED, VERDICT_PARTIAL)
                and verdict in (VERDICT_RECEIVED, VERDICT_PARTIAL)):
            new_covered.append(iid)

        # 只写 AI 轨，绝不触碰律师轨
        item["AI研判"]  = verdict
        item["AI置信"]  = conf
        item["需复核"]  = "是" if needs_review else "否"
        item["最近批次"] = batch_label

        if needs_review:
            review_items.append((item, verdict, review_reason))

    # 5. 写回 dd-checklist.md（只改 AI 轨列）
    write_checklist(checklist_path, all_lines, items)
    print(f"✅ 已更新 dd-checklist.md")

    # 6. 更新 materials-ledger.md
    _update_ledger(ledger_path, batch_label, now_str, batch_path,
                   batch_files, new_covered, items, unmatched_files)
    print(f"✅ 已更新 materials-ledger.md")

    # 7. 生成研判报告（仅展开"需复核"项）
    _write_report(report_path, batch_label, now_str, review_items,
                  conflict_items, unmatched_files, items, new_covered)
    print(f"✅ 已生成 {report_path.name}")

    # 8. 生成待补充资料清单
    _write_pending(pending_path, batch_label, now_str, items)
    print(f"✅ 已生成 {pending_path.name}")

    # 9. 生成章节-材料映射表（供 draft/update 模式参考）
    map_path = project_dir / f"章节-材料映射表-{batch_label}.md"
    affected_chapters = _write_chapter_map(
        map_path, batch_label, now_str,
        file_to_items, unmatched_files, items,
        new_covered, conflict_items
    )
    print(f"✅ 已生成 {map_path.name}")

    # 10. 退出信号：关键资料（重要程度=高）是否（AI研判层面）基本覆盖
    high_items = [it for it in items if it["重要程度"] == "高"]
    high_covered = [it for it in high_items
                    if it["AI研判"] in (VERDICT_RECEIVED, VERDICT_NA)]
    high_lawyer_ok = [it for it in high_items
                      if it.get("律师认定", "").strip()
                      in (LAWYER_OK, LAWYER_NA, LAWYER_WAIVED)]

    print(f"\n{'='*55}")
    print(f"📊 核验小结（{batch_label}，{now_str}）")
    print(f"   本批新增覆盖清单项：{len(new_covered)} 项 "
          f"（编号：{', '.join(new_covered[:10])}{'...' if len(new_covered)>10 else ''}）")
    print(f"   提请复核：{len(review_items)} 项（含冲突 {len(conflict_items)} 项）")
    print(f"   待人工归类文件：{len(unmatched_files)} 份")
    print(f"   高重要度项 AI 研判覆盖：{len(high_covered)}/{len(high_items)}")
    print(f"   高重要度项 律师认定齐备：{len(high_lawyer_ok)}/{len(high_items)}")
    if affected_chapters:
        print(f"   受影响章节（Loop B 需重做）：{', '.join(sorted(affected_chapters))}")
        print(f"   → 运行 update_taskboard.py --mark-affected {','.join(sorted(affected_chapters))}")
    print(f"{'─'*55}")
    if len(high_lawyer_ok) == len(high_items) and len(high_items) > 0:
        print("🟢 关键资料（律师认定维度）已齐备，可推进定稿/出报告。")
    else:
        remaining = [it["编号"] for it in high_items
                     if it.get("律师认定","").strip()
                     not in (LAWYER_OK, LAWYER_NA, LAWYER_WAIVED)]
        print(f"🔴 关键资料尚未齐备（律师认定维度）。")
        print(f"   仍待认定的高重要度项：{', '.join(remaining[:15])}")
        print(f'   ➤ 请运行 adjudicate 模式，由律师对"需复核"项作出认定。')
    print(f"{'='*55}")
    print("⚠️  提醒：AI 研判仅为建议，资料是否齐备以律师认定为准。")


# ─── 辅助：写章节-材料映射表 ────────────────────────────────────────────────────

def _write_chapter_map(path: Path, batch_label: str, now_str: str,
                       file_to_items: dict,
                       unmatched: list[Path],
                       all_items: list[dict],
                       new_covered: list[str],
                       conflict_items: list) -> set[str]:
    """
    生成章节-材料映射表（供 draft/update 模式参考）。
    返回"受影响章节"集合（本批有新增/冲突项的章节）。
    """
    # 构建 item_id → item 快查表
    item_map = {it["编号"]: it for it in all_items}

    # 按章节归集：chapter → list of (file, item_id, conf, reason)
    chapter_to_files: dict[str, list[tuple[Path, str, str, str]]] = {}
    for fpath, matches in file_to_items.items():
        for (iid, conf, reason) in matches:
            it = item_map.get(iid)
            chapter = it["章节"] if it else "未知"
            chapter_to_files.setdefault(chapter, []).append((fpath, iid, conf, reason))

    # 受影响章节：本批有新增覆盖项或冲突项的章节
    affected_chapters: set[str] = set()
    for iid in new_covered:
        it = item_map.get(iid)
        if it:
            affected_chapters.add(it["章节"])
    for item, _ in conflict_items:
        affected_chapters.add(item["章节"])

    # 章节排序（按 第X章 中的数字）
    def chapter_sort_key(ch: str) -> int:
        m = __import__("re").search(r"(\d+)", ch)
        return int(m.group(1)) if m else 99

    sorted_chapters = sorted(chapter_to_files.keys(), key=chapter_sort_key)

    lines: list[str] = [
        f"# 章节-材料映射表—{batch_label}\n\n",
        f"> 生成时间：{now_str}  \n",
        f"> 说明：本表由 `reconcile_materials.py` 自动生成，供 draft/update 模式参考。  \n",
        f'> 一律保留"待人工归类"项，由律师确认后手动归类到对应章节。\n\n',
        f"---\n\n",
        f"## 一、按章节分组\n\n",
    ]

    if not sorted_chapters:
        lines.append("（本批无文件匹配到任何章节）\n\n")
    else:
        for chapter in sorted_chapters:
            chapter_files = chapter_to_files[chapter]
            tag = " ⚡受影响" if chapter in affected_chapters else ""
            lines.append(f"### {chapter}{tag}\n\n")
            lines.append("| 文件名 | 匹配清单项 | AI置信 | 说明 |\n")
            lines.append("|--------|---------|--------|------|\n")
            for fpath, iid, conf, reason in chapter_files:
                it = item_map.get(iid)
                item_name = f"{iid} {it['资料项']}" if it else iid
                lines.append(f"| `{fpath.name}` | {item_name} | {conf} | {reason[:40]} |\n")
            lines.append("\n")

    lines.append("## 二、待人工归类文件\n\n")
    if unmatched:
        lines.append("| 文件名 | 建议 |\n")
        lines.append("|--------|------|\n")
        for f in unmatched:
            lines.append(f"| `{f.name}` | 无法自动匹配，请律师确认归属后更新 dd-checklist.md |\n")
        lines.append("\n")
    else:
        lines.append("（本批所有文件均已匹配到清单项）\n\n")

    lines.append("## 三、受影响章节列表（供 update 模式 Loop B 使用）\n\n")
    if affected_chapters:
        chapter_nums = ",".join(
            str(__import__("re").search(r"(\d+)", ch).group(1))
            for ch in sorted(affected_chapters, key=chapter_sort_key)
        )
        lines.append(f"本批新增/冲突项涉及章节：{', '.join(sorted(affected_chapters, key=chapter_sort_key))}\n\n")
        lines.append(
            f"```bash\n"
            f"# 运行以下命令更新 task-board 受影响标记，再对受影响章节跑 draft --mode incremental\n"
            f"python3 scripts/update_taskboard.py \\\n"
            f"    --project <项目路径>/ \\\n"
            f"    --mark-affected {chapter_nums}\n"
            f"```\n\n"
        )
    else:
        lines.append("（本批无新增或冲突项，无章节需增量重写）\n\n")

    path.write_text("".join(lines), encoding="utf-8")
    return affected_chapters


# ─── 辅助：写台账 ──────────────────────────────────────────────────────────────

def _update_ledger(ledger_path: Path, batch_label: str, now_str: str,
                   batch_path: Path, batch_files: list[Path],
                   new_covered: list[str], items: list[dict],
                   unmatched: list[Path]) -> None:
    remaining = sum(
        1 for it in items
        if it["AI研判"] in (VERDICT_MISSING, VERDICT_PARTIAL, "")
        and it.get("律师认定", "").strip()
        not in (LAWYER_NA, LAWYER_WAIVED)
    )

    new_row = (
        f"| {batch_label} | {now_str[:10]} | （待填写） "
        f"| `{batch_path}` "
        f"| {now_str} "
        f"| {','.join(new_covered) or '无'} "
        f"| {remaining} |\n"
    )

    detail_block = (
        f"\n### {batch_label}（{now_str[:10]}）\n\n"
        f"**收到文件列表**：\n```\n"
        + "\n".join(f.name for f in batch_files)
        + "\n```\n\n"
        + (
            f"**待人工归类文件**：\n```\n"
            + "\n".join(f.name for f in unmatched)
            + "\n```\n\n"
            if unmatched else ""
        )
        + f"**本批核验小结**：\n"
        f"- 本批收到文件：{len(batch_files)} 份\n"
        f"- 本批新增清单项：{len(new_covered)} 项（编号：{','.join(new_covered) or '无'}）\n"
        f"- 仍待补数（AI研判维度）：{remaining} 项\n"
    )

    if ledger_path.exists():
        text = ledger_path.read_text(encoding="utf-8")
        # 在台账主表末尾追加行（找最后一个 | 第N批 格式的行后面插入）
        # 简化：直接在文件末尾追加
        text = text.rstrip("\n") + "\n" + new_row + detail_block
        ledger_path.write_text(text, encoding="utf-8")
    else:
        # 台账不存在，给个最简头部
        header = (
            "# 资料台账（自动生成）\n\n"
            "| 批次号 | 接收日期 | 提供方 | 材料存放路径 | 核验时间 | 本批新增清单项 | 遗留待补数 |\n"
            "|--------|---------|--------|------------|---------|--------------|----------|\n"
        )
        ledger_path.write_text(header + new_row + detail_block, encoding="utf-8")


# ─── 辅助：写研判报告 ──────────────────────────────────────────────────────────

def _write_report(path: Path, batch_label: str, now_str: str,
                  review_items: list[tuple[dict, str, str]],
                  conflict_items: list[tuple[dict, str]],
                  unmatched: list[Path],
                  all_items: list[dict],
                  new_covered: list[str]) -> None:

    lines: list[str] = [
        f"# 研判报告—{batch_label}\n\n",
        f"> 生成时间：{now_str}  \n",
        f"> **声明**：本报告由 AI 自动生成，仅为律师参考建议。",
        f"资料是否齐备，以律师认定为准。\n\n",
        f"---\n\n",
        f"## 一、冲突项（与既有律师认定冲突，共 {len(conflict_items)} 项）\n\n",
    ]

    if conflict_items:
        for item, reason in conflict_items:
            lines.append(
                f"### ⚠️ {item['编号']} {item['资料项']}\n\n"
                f"- **律师既有认定**：{item.get('律师认定','')}\n"
                f"- **本批AI研判**：{item.get('AI研判','')}\n"
                f"- **冲突说明**：{reason}\n\n"
                f"> 本脚本未修改律师认定。请在 adjudicate 模式中由律师决定是否改判。\n\n"
            )
    else:
        lines.append("（本批无冲突项）\n\n")

    lines.append(f"## 二、需复核项详述（共 {len(review_items)} 项）\n\n")
    if review_items:
        for item, verdict, reason in review_items:
            is_conflict = any(it["编号"] == item["编号"] for it, _ in conflict_items)
            prefix = "⚠️ " if is_conflict else ""
            lines.append(
                f"### {prefix}{item['编号']} {item['资料项']}\n\n"
                f"- **章节**：{item['章节']}  **重要程度**：{item['重要程度']}\n"
                f"- **AI研判**：{verdict}  **AI置信**：{item.get('AI置信','')}\n"
                f"- **律师认定（当前）**：{item.get('律师认定','待认定')}\n"
                f"- **审查意见**：{reason}\n\n"
            )
    else:
        lines.append("（本批无需复核项）\n\n")

    lines.append(f"## 三、待人工归类文件（共 {len(unmatched)} 份）\n\n")
    if unmatched:
        for f in unmatched:
            lines.append(f"- `{f.name}`\n")
        lines.append(
            "\n> 上述文件无法自动匹配到清单项，请律师手动归类后更新 dd-checklist.md。\n\n"
        )
    else:
        lines.append("（本批所有文件均已匹配）\n\n")

    lines.append(f"## 四、本批新增覆盖项（共 {len(new_covered)} 项）\n\n")
    if new_covered:
        for iid in new_covered:
            it = next((x for x in all_items if x["编号"] == iid), None)
            name = it["资料项"] if it else ""
            lines.append(f"- {iid} {name}\n")
    else:
        lines.append("（本批无新增覆盖项）\n\n")

    path.write_text("".join(lines), encoding="utf-8")


# ─── 辅助：写待补清单 ──────────────────────────────────────────────────────────

def _write_pending(path: Path, batch_label: str, now_str: str,
                   items: list[dict]) -> None:
    pending = [
        it for it in items
        if it["AI研判"] in (VERDICT_MISSING, VERDICT_PARTIAL, "")
        and it.get("律师认定", "").strip()
        not in (LAWYER_NA, LAWYER_WAIVED, LAWYER_OK)
    ]
    # 按重要程度排序（高→中→低）
    order = {"高": 0, "中": 1, "低": 2}
    pending.sort(key=lambda x: order.get(x["重要程度"], 3))

    lines: list[str] = [
        f"# 待补充资料清单—{batch_label}\n\n",
        f"> 截至：{now_str}  \n",
        f"> **说明**：本清单取自 dd-checklist.md 中 AI研判=❌/🟡 且律师认定≠已齐备/不适用/豁免 的项。",
        f"请律师确认后发送标的方催件。\n\n",
        f"| 编号 | 资料项 | 章节 | 重要程度 | AI研判 | 律师认定 | 备注 |\n",
        f"|------|--------|------|---------|--------|---------|------|\n",
    ]
    for it in pending:
        note = it.get("本项齐备标准", "") or it.get("律师批注", "")
        lines.append(
            f"| {it['编号']} | {it['资料项']} | {it['章节']} "
            f"| {it['重要程度']} | {it['AI研判'] or '—'} "
            f"| {it.get('律师认定','待认定')} | {note} |\n"
        )

    high_count = sum(1 for it in pending if it["重要程度"] == "高")
    lines.append(
        f"\n共 **{len(pending)}** 项待补充（高重要度 {high_count} 项）。\n\n"
        f'> AI 研判仅为参考，最终以律师认定为准。\n'
        f'> 标"待认定"项请律师尽快通过 adjudicate 模式完成认定。\n'
    )
    path.write_text("".join(lines), encoding="utf-8")


# ─── 入口 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Loop A 资料齐备性核验引擎（reconcile_materials.py）"
    )
    parser.add_argument("--project",  required=True,
                        help="项目根目录（含 dd-checklist.md）")
    parser.add_argument("--batch",    required=True,
                        help="本批材料文件夹路径，或单个文件路径")
    parser.add_argument("--batch-no", required=True, type=int,
                        help="批次编号（整数，如 1 / 2 / 3）")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
