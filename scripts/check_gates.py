#!/usr/bin/env python3
"""
check_gates.py  v26.6.21.1305
项目级推进闸门检查（AC-P1 ~ AC-P5）。

用法:
    python3 check_gates.py --project /path/to/DD项目/

输出:
    逐项打印 AC-P1~P5 通过/未通过，最终给出"可出报告 / 不可出报告"结论。
    同时写入 gate-check-<YYYYMMDD>.md 存档。

AC-P1  所有10章 task-board 状态 ∈ {已自检, 已完成}
AC-P2  dd-checklist 所有"重要程度=高"项，律师认定 ∈ {已齐备, 不适用, 豁免}
AC-P3  dd-checklist 无"未消解冲突"（律师已认定 ∈ {已齐备,不适用,豁免} 但 AI研判仍显示
       矛盾状态，且未在 adjudication-log 中出现对应改判记录）
AC-P4  working-paper.md "附：免责限制条件"节 与 dd-checklist 律师认定=
       {部分-需补, 待认定} 的高重要度项一致（收录了所有未齐备项）
AC-P5  task-board 无"待人工"状态章节（或有书面豁免记录）

约束:
    本脚本只读文件，不修改任何文件。
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── 常量 ────────────────────────────────────────────────────────────────────

LAWYER_OK_SET  = {"已齐备", "不适用", "豁免"}
LAWYER_PENDING = {"部分-需补", "待认定", "部分-可推进"}

STATUS_PASS = {"已自检", "已完成"}

COL_ID       = 0
COL_NAME     = 1
COL_CHAPTER  = 2
COL_PRIORITY = 3
COL_AI_V     = 4
COL_REVIEW   = 6
COL_LAWYER   = 7


# ─── 解析工具 ────────────────────────────────────────────────────────────────

def _split(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep(line: str) -> bool:
    return bool(re.match(r"^\s*\|[-| :]+\|\s*$", line))


def parse_checklist(path: Path) -> list[dict]:
    items: list[dict] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cols = _split(stripped)
        if "编号" in cols and "AI研判" in cols:
            in_table = True
            continue
        if is_sep(stripped):
            continue
        if in_table and cols and cols[COL_ID] and not cols[COL_ID].startswith("-"):
            while len(cols) < 13:
                cols.append("")
            items.append({
                "编号":     cols[COL_ID],
                "资料项":   cols[COL_NAME],
                "章节":     cols[COL_CHAPTER],
                "重要程度": cols[COL_PRIORITY],
                "AI研判":   cols[COL_AI_V],
                "需复核":   cols[COL_REVIEW],
                "律师认定": cols[COL_LAWYER],
            })
    return items


def parse_taskboard(path: Path) -> list[dict]:
    chapters: list[dict] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cols = _split(stripped)
        if "章节" in cols and "状态" in cols:
            in_table = True
            continue
        if is_sep(stripped):
            continue
        if in_table and cols and cols[0].startswith("第"):
            while len(cols) < 6:
                cols.append("")
            chapters.append({
                "章节":   cols[0],
                "状态":   cols[1],
                "断点":   cols[4] if len(cols) > 4 else "",
            })
    return chapters


def parse_adjlog(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cols = _split(stripped)
        if "编号" in cols and "新认定" in cols:
            in_table = True
            continue
        if is_sep(stripped):
            continue
        if in_table and len(cols) >= 5 and cols[0]:
            rows.append({"时间": cols[0], "编号": cols[1],
                         "新认定": cols[4], "认定人": cols[5] if len(cols) > 5 else ""})
    return rows


def read_working_paper_disclaimer(path: Path) -> str:
    """提取 working-paper.md 中"附：免责限制条件"节内容"""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^#+\s+附[：:]\s*免责限制条件.*$", text, re.MULTILINE)
    if not m:
        return ""
    start = m.start()
    next_h = re.search(r"^#+ ", text[start + 1:], re.MULTILINE)
    end = start + 1 + next_h.start() if next_h else len(text)
    return text[start:end]


# ─── AC 检查函数 ──────────────────────────────────────────────────────────────

def check_ac_p1(chapters: list[dict]) -> tuple[bool, str]:
    """AC-P1: 所有章节状态 ∈ {已自检, 已完成}"""
    not_pass = [c for c in chapters if c["状态"] not in STATUS_PASS]
    if not_pass:
        detail = "；".join(f"{c['章节']}={c['状态']}" for c in not_pass[:5])
        if len(not_pass) > 5:
            detail += f"等共{len(not_pass)}章"
        return False, f"共 {len(not_pass)} 章未通过：{detail}"
    return True, f"全部 {len(chapters)} 章状态 ∈ {{已自检, 已完成}}"


def check_ac_p2(items: list[dict]) -> tuple[bool, str]:
    """AC-P2: 高重要度项律师认定 ∈ {已齐备, 不适用, 豁免}"""
    high = [it for it in items if it["重要程度"] == "高"]
    not_pass = [it for it in high if it["律师认定"].strip() not in LAWYER_OK_SET]
    if not_pass:
        ids = "、".join(it["编号"] for it in not_pass[:10])
        if len(not_pass) > 10:
            ids += f"等共{len(not_pass)}项"
        return False, f"共 {len(not_pass)}/{len(high)} 个高重要度项律师认定未齐备：{ids}"
    return True, f"全部 {len(high)} 个高重要度项律师认定 ∈ {{已齐备, 不适用, 豁免}}"


def check_ac_p3(items: list[dict], adjlog: list[dict]) -> tuple[bool, str]:
    """
    AC-P3: 无未消解冲突。
    冲突定义（与 reconcile_materials.py 对齐）:
      - 律师认定=已齐备 且 AI研判 ∈ {🟡部分, ❌未收}
      - 律师认定 ∈ {不适用, 豁免} 且 AI研判=✅已收
    若该编号在 adjudication-log 中存在认定记录（律师已做出裁决），视为已消解。
    """
    adjudicated_ids = {row["编号"] for row in adjlog if row.get("认定人")}

    conflicts = []
    for it in items:
        lv = it["律师认定"].strip()
        av = it["AI研判"].strip()
        conflict = False
        if lv == "已齐备" and av in ("🟡部分", "❌未收"):
            conflict = True
        elif lv in ("不适用", "豁免") and av == "✅已收":
            conflict = True
        if conflict and it["编号"] not in adjudicated_ids:
            conflicts.append(it)

    if conflicts:
        ids = "、".join(f"{it['编号']}（律师={it['律师认定']}, AI={it['AI研判']}）"
                       for it in conflicts[:5])
        if len(conflicts) > 5:
            ids += f"等共{len(conflicts)}项"
        return False, f"存在 {len(conflicts)} 项未消解冲突：{ids}"
    return True, "无未消解冲突项"


def check_ac_p4(items: list[dict], wp_text: str) -> tuple[bool, str]:
    """
    AC-P4: working-paper "附：免责限制条件"节收录了所有律师认定=部分-需补/待认定 的高重要度项。
    判定方式：检查这些项的编号是否出现在免责条件节中。
    若无"附：免责限制条件"节则直接失败。
    """
    high_pending = [it for it in items
                    if it["重要程度"] == "高"
                    and it["律师认定"].strip() in LAWYER_PENDING]

    if not high_pending:
        return True, "无高重要度未齐备项，无需免责声明"

    if not wp_text:
        return False, (f'working-paper.md 中未找到"附：免责限制条件"节，'
                       f'但有 {len(high_pending)} 个高重要度项律师认定未齐备')

    missing = [it for it in high_pending if it["编号"] not in wp_text]
    if missing:
        ids = "、".join(it["编号"] for it in missing[:5])
        return False, (f'以下高重要度未齐备项未写入免责条件节：{ids}，'
                       f'请在 working-paper.md 更新"附：免责限制条件"节')
    return True, f"全部 {len(high_pending)} 个高重要度未齐备项已写入免责条件节"


def check_ac_p5(chapters: list[dict]) -> tuple[bool, str]:
    """AC-P5: task-board 无"待人工"状态章节"""
    blocked = [c for c in chapters if c["状态"] == "待人工"]
    if blocked:
        detail = "；".join(
            f"{c['章节']}（{c['断点'][:30] if c['断点'] else '未填断点说明'}）"
            for c in blocked[:3]
        )
        return False, f'共 {len(blocked)} 章处于"待人工"状态，断点未消解：{detail}'
    return True, "无待人工断点章节"


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def run(args) -> int:
    project_dir = Path(args.project)
    checklist_path = project_dir / "dd-checklist.md"
    taskboard_path = project_dir / "task-board.md"
    adjlog_path    = project_dir / "adjudication-log.md"
    wp_path        = project_dir / "working-paper.md"
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = project_dir / f"gate-check-{date_str}.md"

    missing = [p for p in [checklist_path, taskboard_path] if not p.exists()]
    if missing:
        sys.exit(f"❌ 缺少必要文件：{', '.join(str(p) for p in missing)}\n"
                 "   请先运行 init 模式初始化项目。")

    items    = parse_checklist(checklist_path)
    chapters = parse_taskboard(taskboard_path)
    adjlog   = parse_adjlog(adjlog_path)
    wp_text  = read_working_paper_disclaimer(wp_path)

    print(f"\n{'='*60}")
    print(f"📋 项目级推进闸门检查  {now_str}")
    print(f"   项目：{project_dir}")
    print(f"{'='*60}")

    checks = [
        ("AC-P1", "所有章节已自检/已完成",        check_ac_p1(chapters)),
        ("AC-P2", "高重要度项律师认定齐备",        check_ac_p2(items)),
        ("AC-P3", "无未消解冲突",                  check_ac_p3(items, adjlog)),
        ("AC-P4", "免责声明与未齐备项一致",        check_ac_p4(items, wp_text)),
        ("AC-P5", "无待人工断点章节",              check_ac_p5(chapters)),
    ]

    passed = 0
    report_lines: list[str] = [
        f"# 推进闸门检查报告（gate-check-{date_str}.md）\n\n",
        f"> 检查时间：{now_str}  \n",
        f"> 项目路径：{project_dir}  \n\n",
        f"| # | 检查项 | 结果 | 说明 |\n",
        f"|---|--------|------|------|\n",
    ]

    for code, name, (ok, detail) in checks:
        icon = "✅" if ok else "❌"
        status = "通过" if ok else "未通过"
        print(f"  {icon} {code} {name}")
        print(f"       {detail}")
        report_lines.append(f"| {code} | {name} | {icon} {status} | {detail} |\n")
        if ok:
            passed += 1

    all_pass = (passed == len(checks))
    conclusion = "🟢 **全部通过，可推进出报告。**" if all_pass else \
                 f"🔴 **未通过（{len(checks)-passed}/{len(checks)} 项），不可出报告。请处置上述未通过项后重新检查。**"

    print(f"\n{'─'*60}")
    print(f"结论：{conclusion}")
    print(f"{'='*60}\n")

    report_lines.append(f"\n---\n\n{conclusion}\n\n")
    if not all_pass:
        report_lines.append(
            "> 提示：处置完断点后，重新运行：\n"
            "> ```bash\n"
            f"> python3 scripts/check_gates.py --project {project_dir}/\n"
            "> ```\n"
        )

    output_path.write_text("".join(report_lines), encoding="utf-8")
    print(f"📄 检查结果已存档：{output_path.name}")

    return 0 if all_pass else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="项目级推进闸门检查 AC-P1~P5（check_gates.py）"
    )
    parser.add_argument("--project", required=True, help="项目根目录")
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
