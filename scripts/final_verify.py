#!/usr/bin/env python3
"""
final_verify.py  v26.6.21.1305
底稿与报告一致性终检（FINAL VERIFY 步骤）。

逐项核查：
  WP 检查（底稿内部完整性）
    V-WP1  working-paper.md 全10章存在（标题层级正确）
    V-WP2  每章具备6段结构（§X.1–§X.6）
    V-WP3  无空置段落（每段至少有非标题内容）
    V-WP4  无未替换占位符（[TODO]、[从底稿...]、待填写等）

  报告检查（report/ 文件安全性）
    V-R1   report/ 目录下存在 .md 报告文件
    V-R2   报告包含"声明与限定条件"和"重大风险提示"关键节
    V-R3   报告中无"律师备忘"标题（内部记录未泄漏）
    V-R4   报告中无"⚠️ 待确认"（底稿草稿标记未泄漏）
    V-R5   报告中无"系统自动整合，待律师复核"（AI 注记未泄漏）

  交叉一致性（宽松告警）
    V-X1   🔴 高风险数量：底稿 §X.5 与报告"重大风险提示"节计数一致（误差≤1容忍）
    V-X2   材料限制：底稿 §X.3 中❌未获取高重要度项 → 报告免责声明有对应描述

用法:
    python3 final_verify.py --project /path/to/DD项目/

输出:
    逐项结论 + 终检报告 final-verify-<YYYYMMDD>.md
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── 常量 ─────────────────────────────────────────────────────────────────────

# working-paper 底稿中各章标题的 ## 模式（模板用 "## 1. 名称" 格式）
CHAPTER_HEADING_RE = re.compile(
    r"^##\s+"
    r"(?:第\s*(?:[一二三四五六七八九十]+|\d+)\s*章\s*[  　]?"  # 中文格式
    r"|(\d+)\.\s)"                                               # 数字格式
    r".+",
    re.MULTILINE,
)
CHAPTER_NUMS = list(range(1, 11))  # 1-10

# 每章 6 段的子标题模式（X.1 ~ X.6）
def section_re(ch: int) -> re.Pattern:
    return re.compile(
        rf"^###\s+{ch}\.\s*[1-6]\s",
        re.MULTILINE,
    )


# 占位符关键词
PLACEHOLDER_PATTERNS = [
    r"\[TODO\]",
    r"\[从底稿",
    r"\[待填",
    r"待填写\]",
    r"YYYY-MM-DD\]",
    r"\[LAW_FIRM\]",
    r"\[CLIENT_NAME\]",
    r"\[TARGET_COMPANY\]",
    r"\[LAWYERS\]",
    r"\[BASE_DATE\]",
    r"\[PURPOSE\]",
    r"\[MATERIAL_LIMITATIONS\]",
]

# 报告中不应出现的内部标记
LEAK_PATTERNS = [
    (r"律师备忘", "律师备忘（内部记录）出现在报告中"),
    (r"⚠️\\s*待确认",  '底稿"待确认"标记未清理'),
    (r"系统自动整合，待律师复核", "AI 自动整合注记未清理"),
]

# 报告必须包含的关键节
REPORT_REQUIRED_SECTIONS = [
    ("声明与限定条件",   r"声明与限定条件"),
    ("重大风险提示",     r"重大风险提示"),
    ("结论",            r"结论"),
    ("限制条件.*免责",  r"限制条件|免责声明"),
]


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def extract_chapter_blocks(text: str) -> dict[int, str]:
    """把 working-paper.md 拆成 {章节号: 章节全文} 字典"""
    blocks: dict[int, str] = {}
    # 找所有 ## 标题（二级），分割章节
    headings = list(re.finditer(r"^## .+", text, re.MULTILINE))
    for i, h in enumerate(headings):
        ch_num = _guess_chapter_num(h.group())
        if ch_num is None:
            continue
        start = h.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        blocks[ch_num] = text[start:end]
    return blocks


def _guess_chapter_num(heading: str) -> int | None:
    """从章节标题推断章节号 1-10"""
    # "## 第1章"  "## 第一章"  "## 1. 名称"
    m = re.search(r"第\s*(\d+)\s*章", heading)
    if m:
        return int(m.group(1))
    m = re.search(r"第\s*([一二三四五六七八九十]+)\s*章", heading)
    if m:
        chinese = "一二三四五六七八九十"
        return chinese.index(m.group(1)) + 1
    m = re.search(r"^##\s+(\d+)\.", heading)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 10 else None
    return None


def count_red_risks(text: str) -> int:
    """统计文本中 🔴 高风险 标记数"""
    return len(re.findall(r"🔴", text))


def extract_report_section(text: str, pattern: str) -> str:
    """提取报告中某节内容（到下一个同级标题为止）"""
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return ""
    start = m.start()
    next_h = re.search(r"^## ", text[start + 1:], re.MULTILINE)
    end = start + 1 + next_h.start() if next_h else len(text)
    return text[start:end]


# ─── 检查函数 ─────────────────────────────────────────────────────────────────

def check_vwp1(blocks: dict[int, str]) -> tuple[bool, str]:
    """V-WP1: 全10章存在"""
    missing = [n for n in CHAPTER_NUMS if n not in blocks]
    if missing:
        return False, f"缺失章节：{missing}"
    return True, f"全10章均存在"


def check_vwp2(blocks: dict[int, str]) -> tuple[bool, str]:
    """V-WP2: 每章6段结构完整"""
    issues = []
    for ch, text in blocks.items():
        found = len(re.findall(rf"###\s+{ch}\.[1-6]", text))
        if found < 6:
            issues.append(f"第{ch}章缺 {6-found} 段（找到 {found}/6）")
    if issues:
        return False, "；".join(issues[:5]) + (f"等共{len(issues)}章" if len(issues) > 5 else "")
    return True, "全10章均具备6段结构"


def check_vwp3(blocks: dict[int, str]) -> tuple[bool, str]:
    """V-WP3: 无空置段落"""
    issues = []
    for ch, text in blocks.items():
        sections = re.split(rf"###\s+{ch}\.[1-6]", text)
        for i, sec in enumerate(sections[1:], 1):   # sections[0] 是章节标题前内容
            lines = [l.strip() for l in sec.splitlines() if l.strip()]
            if not lines or all(l.startswith("#") for l in lines):
                issues.append(f"第{ch}章 §{ch}.{i}")
    if issues:
        return False, f"空置段落：{', '.join(issues[:6])}" + ("等" if len(issues) > 6 else "")
    return True, "无空置段落"


def check_vwp4(text: str) -> tuple[bool, str]:
    """V-WP4: 无未替换占位符"""
    found = []
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            found.append(pat.strip(r"[]\\"))
    if found:
        return False, f"发现 {len(found)} 个占位符未替换：{', '.join(found[:5])}"
    return True, "无未替换占位符"


def check_vr1(report_dir: Path) -> tuple[bool, str, list[Path]]:
    """V-R1: report/ 下有 .md 文件"""
    files = list(report_dir.glob("*.md"))
    if not files:
        return False, f"report/ 目录下无 .md 报告文件（{report_dir}）", []
    names = "、".join(f.name for f in files[:3])
    return True, f"找到 {len(files)} 个报告文件：{names}", files


def check_vr2(text: str) -> tuple[bool, str]:
    """V-R2: 报告包含关键节"""
    missing = []
    for name, pattern in REPORT_REQUIRED_SECTIONS:
        if not re.search(pattern, text):
            missing.append(name)
    if missing:
        return False, f"报告缺少关键节：{', '.join(missing)}"
    return True, "报告包含所有关键节（声明/结论/风险/免责）"


def check_vr3_r5(text: str) -> list[tuple[str, bool, str]]:
    """V-R3~R5: 报告中无内部标记泄漏"""
    results = []
    codes  = ["V-R3", "V-R4", "V-R5"]
    for (pat, desc), code in zip(LEAK_PATTERNS, codes):
        matches = re.findall(pat, text)
        if matches:
            results.append((code, False, f"报告中出现 {len(matches)} 处：{desc}"))
        else:
            results.append((code, True, f"未发现 {desc}"))
    return results


def check_vx1(wp_text: str, report_text: str) -> tuple[bool, str]:
    """V-X1: 🔴高风险数量一致（宽松，误差≤1）"""
    wp_count = count_red_risks(wp_text)
    r_sec    = extract_report_section(report_text, r"重大风险提示")
    r_count  = count_red_risks(r_sec) if r_sec else 0

    if wp_count == 0:
        return True, "底稿无🔴高风险项，报告无需重大风险提示"
    if r_sec == "":
        return False, f'底稿有 {wp_count} 个🔴高风险项，但报告未找到"重大风险提示"节'
    if abs(wp_count - r_count) > 1:
        return False, (f'🔴高风险计数差异：底稿 {wp_count} 项，报告"重大风险提示"节 {r_count} 项，'
                       f'相差 {abs(wp_count-r_count)}（容忍≤1）')
    return True, f"🔴高风险计数基本一致（底稿 {wp_count}，报告 {r_count}）"


def check_vx2(blocks: dict[int, str], report_text: str) -> tuple[bool, str]:
    """V-X2: 底稿 §X.3 中❌未获取高重要度项 → 报告免责声明有对应描述（宽松）"""
    disclaimer = extract_report_section(report_text, r"限制条件|免责声明")
    if not disclaimer:
        disclaimer = extract_report_section(report_text, r"声明与限定条件")

    missing_items = []
    for ch, text in blocks.items():
        # 找 §X.3 段落
        m = re.search(rf"###\s+{ch}\.3.*?\n(.*?)(?=###|\Z)", text, re.DOTALL)
        if not m:
            continue
        sec3 = m.group(1)
        # 找表格中 ❌ 标记的行
        for line in sec3.splitlines():
            if "❌" in line and ("高" in line or "重要" in line):
                # 从行中提取材料名（第二列）
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) >= 2:
                    missing_items.append((ch, cols[1]))

    if not missing_items:
        return True, "底稿 §X.3 无高重要度❌未获取项，无需免责说明"

    not_in_report = []
    for ch, name in missing_items:
        keyword = name[:8] if len(name) > 8 else name
        if keyword and keyword not in disclaimer:
            not_in_report.append(f"第{ch}章:{name}")

    if not_in_report:
        detail = "、".join(not_in_report[:5])
        return False, (f"{len(not_in_report)}/{len(missing_items)} 个❌未获取高重要度项"
                       f"未在报告免责声明中体现：{detail}")
    return True, f"全部 {len(missing_items)} 个❌未获取高重要度项已在报告免责声明中体现"


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def run(args) -> int:
    project_dir = Path(args.project)
    wp_path     = project_dir / "working-paper.md"
    report_dir  = project_dir / "report"
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = project_dir / f"final-verify-{date_str}.md"

    # 基础文件检查
    if not wp_path.exists():
        sys.exit(f"❌ 未找到 working-paper.md：{wp_path}")
    if not report_dir.exists():
        sys.exit(f"❌ 未找到 report/ 目录：{report_dir}")

    wp_text = wp_path.read_text(encoding="utf-8")
    blocks  = extract_chapter_blocks(wp_text)

    print(f"\n{'='*60}")
    print(f"🔍 底稿与报告一致性终检  {now_str}")
    print(f"   项目：{project_dir}")
    print(f"{'='*60}")

    results: list[tuple[str, str, bool, str]] = []  # (code, name, ok, detail)

    # ── 底稿检查 ──
    print("\n【底稿完整性】")
    for code, name, (ok, detail) in [
        ("V-WP1", "全10章存在",       check_vwp1(blocks)),
        ("V-WP2", "每章6段结构",       check_vwp2(blocks)),
        ("V-WP3", "无空置段落",        check_vwp3(blocks)),
        ("V-WP4", "无未替换占位符",    check_vwp4(wp_text)),
    ]:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {code} {name}")
        print(f"       {detail}")
        results.append((code, name, ok, detail))

    # ── 报告检查 ──
    print("\n【报告安全性】")
    vr1_ok, vr1_detail, report_files = check_vr1(report_dir)
    icon = "✅" if vr1_ok else "❌"
    print(f"  {icon} V-R1 报告文件存在")
    print(f"       {vr1_detail}")
    results.append(("V-R1", "报告文件存在", vr1_ok, vr1_detail))

    report_text = ""
    if report_files:
        # 合并所有报告文件内容（通常只有一个）
        report_text = "\n".join(f.read_text(encoding="utf-8") for f in report_files)

    for code, name, (ok, detail) in [
        ("V-R2", "报告包含关键节",  check_vr2(report_text) if report_text else (False, "无报告内容")),
    ]:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {code} {name}")
        print(f"       {detail}")
        results.append((code, name, ok, detail))

    leak_results = check_vr3_r5(report_text) if report_text else [
        ("V-R3", False, "无报告内容"),
        ("V-R4", False, "无报告内容"),
        ("V-R5", False, "无报告内容"),
    ]
    for code, ok, detail in leak_results:
        NAMES = {"V-R3": "无律师备忘泄漏", "V-R4": "无待确认标记", "V-R5": "无AI注记泄漏"}
        icon = "✅" if ok else "❌"
        print(f"  {icon} {code} {NAMES.get(code, code)}")
        print(f"       {detail}")
        results.append((code, NAMES.get(code, code), ok, detail))

    # ── 交叉一致性（告警级别，⚠️ 而非 ❌）──
    print("\n【交叉一致性（宽松告警）】")
    x1_ok, x1_detail = check_vx1(wp_text, report_text) if report_text else (False, "无报告内容")
    x2_ok, x2_detail = check_vx2(blocks, report_text)  if report_text else (False, "无报告内容")
    for code, name, ok, detail in [
        ("V-X1", "🔴高风险计数一致", x1_ok, x1_detail),
        ("V-X2", "材料限制免责覆盖", x2_ok, x2_detail),
    ]:
        icon = "✅" if ok else "⚠️ "
        print(f"  {icon} {code} {name}")
        print(f"       {detail}")
        results.append((code, name, ok, detail))

    # ── 结论 ──
    hard_checks  = [r for r in results if not r[0].startswith("V-X")]
    soft_checks  = [r for r in results if r[0].startswith("V-X")]
    hard_fail    = [r for r in hard_checks if not r[2]]
    soft_warn    = [r for r in soft_checks if not r[2]]

    all_hard_pass = (len(hard_fail) == 0)
    if all_hard_pass and not soft_warn:
        conclusion = "🟢 **终检全部通过，底稿与报告一致，可送审。**"
    elif all_hard_pass:
        conclusion = (f"🟡 **硬检查全部通过，但 {len(soft_warn)} 项宽松告警需人工核查后送审。**")
    else:
        conclusion = (f"🔴 **终检未通过（{len(hard_fail)} 项硬检查失败 + {len(soft_warn)} 项告警）。**"
                      f"请处置后重跑。")

    print(f"\n{'─'*60}")
    print(f"结论：{conclusion}")
    print(f"{'='*60}\n")

    # ── 写终检报告 ──
    lines = [
        f"# 底稿与报告一致性终检（final-verify-{date_str}.md）\n\n",
        f"> 检查时间：{now_str}  \n> 项目：{project_dir}  \n\n",
        "| 代码 | 检查项 | 结果 | 说明 |\n",
        "|------|--------|------|------|\n",
    ]
    for code, name, ok, detail in results:
        if code.startswith("V-X"):
            icon = "✅ 通过" if ok else "⚠️  告警"
        else:
            icon = "✅ 通过" if ok else "❌ 失败"
        lines.append(f"| {code} | {name} | {icon} | {detail} |\n")
    lines.append(f"\n---\n\n{conclusion}\n")
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"📄 终检报告已存档：{out_path.name}")

    return 0 if all_hard_pass else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="底稿与报告一致性终检 V-WP1~WP4 + V-R1~R5 + V-X1~X2（final_verify.py）"
    )
    parser.add_argument("--project", required=True, help="项目根目录")
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
