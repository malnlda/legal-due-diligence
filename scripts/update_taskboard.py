#!/usr/bin/env python3
"""
update_taskboard.py  v26.6.21.1305
更新 task-board.md 中指定章节的状态字段。

用法:
    python3 update_taskboard.py \
        --project /path/to/DD项目/ \
        --chapter 1 \
        --status 已自检 \
        [--batch   第2批] \
        [--affected 是] \
        [--checkpoint "高风险：XXX，等待律师处置"] \
        [--notes    "AC-C1~C7全通过"]

    # 批量标记多章受影响（reconcile 后更新）
    python3 update_taskboard.py \
        --project /path/to/DD项目/ \
        --mark-affected 1,2,4

可更新字段（只传对应参数，不传的字段原样保留）:
    --status       : 未开始 / 进行中 / 已自检 / 待人工 / 已完成
    --batch        : 数据基准批次，如"第2批"
    --affected     : 受影响列，是 / 否
    --checkpoint   : 断点事项（传空字符串 "" 清除）
    --notes        : 自检备注（传空字符串 "" 清除）

task-board.md 表头（冻结，与 orchestration-guide.md §六 一致）:
    | 章节 | 状态 | 数据基准批次 | 受影响 | 断点事项 | 自检备注 |

约束:
    - 只改指定章节行，其他行原样保留
    - 参数未传的字段不改
"""

import argparse
import re
import sys
from pathlib import Path

# task-board 表头列索引（0-based，去掉两端 | 后的列）
COL_CHAPTER    = 0
COL_STATUS     = 1
COL_BATCH      = 2
COL_AFFECTED   = 3
COL_CHECKPOINT = 4
COL_NOTES      = 5

STATUS_VALUES  = {"未开始", "进行中", "已自检", "待人工", "已完成"}
AFFECTED_VALUES = {"是", "否"}


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|[-| :]+\|\s*$", line))


def chapter_key(chapter_spec: str) -> str:
    """把 '1' 或 '第1章' 统一成可匹配 task-board 第1列的前缀"""
    spec = chapter_spec.strip()
    if spec.startswith("第") and "章" in spec:
        return spec  # 已是 "第X章" 格式，直接用
    try:
        n = int(spec)
        return f"第{n}章"
    except ValueError:
        return spec


def find_chapter_line(lines: list[str], chapter_prefix: str) -> int | None:
    """在 task-board 表格中找到包含指定章节的行号，返回 None 则未找到"""
    in_table = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|"):
            cols = _split_row(stripped)
            if "章节" in cols and "状态" in cols:
                in_table = True
                continue
            if is_separator(stripped):
                continue
            if in_table and cols and cols[COL_CHAPTER].startswith(chapter_prefix):
                return i
        else:
            if in_table and stripped == "":
                continue
            in_table = False
    return None


def render_updated_row(cols: list[str], args) -> str:
    """把解析出的原始列按 args 中有值的字段更新后拼回"""
    # 扩展到至少 6 列
    while len(cols) < 6:
        cols.append("")
    if args.status is not None:
        cols[COL_STATUS] = args.status
    if args.batch is not None:
        cols[COL_BATCH] = args.batch
    if args.affected is not None:
        cols[COL_AFFECTED] = args.affected
    if args.checkpoint is not None:
        cols[COL_CHECKPOINT] = args.checkpoint
    if args.notes is not None:
        cols[COL_NOTES] = args.notes
    return "| " + " | ".join(cols[:6]) + " |\n"


def update_single_chapter(lines: list[str], chapter_spec: str, args) -> bool:
    """找到章节行并更新，返回 True=成功，False=未找到"""
    prefix = chapter_key(chapter_spec)
    idx = find_chapter_line(lines, prefix)
    if idx is None:
        return False
    cols = _split_row(lines[idx].strip())
    lines[idx] = render_updated_row(cols, args)
    return True


def mark_affected_chapters(lines: list[str], chapter_list: list[str]) -> None:
    """把多个章节的"受影响"列批量置为"是"；其余章节的受影响列置为"否"（本轮新鲜度清零）"""
    affected_set = {chapter_key(c.strip()) for c in chapter_list}
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|"):
            cols = _split_row(stripped)
            if "章节" in cols and "状态" in cols:
                in_table = True
                continue
            if is_separator(stripped):
                continue
            if in_table and cols and len(cols) >= 6:
                chapter_col = cols[COL_CHAPTER]
                matched = any(chapter_col.startswith(p) for p in affected_set)
                cols[COL_AFFECTED] = "是" if matched else "否"
                while len(cols) < 6:
                    cols.append("")
                lines[i] = "| " + " | ".join(cols[:6]) + " |\n"
        else:
            if in_table and stripped == "":
                continue
            in_table = False


def run(args) -> None:
    project_dir = Path(args.project)
    tb_path = project_dir / "task-board.md"

    if not tb_path.exists():
        sys.exit(f"❌ 未找到 task-board.md：{tb_path}\n   请先运行 init 模式初始化项目。")

    lines = tb_path.read_text(encoding="utf-8").splitlines(keepends=True)

    if args.mark_affected:
        chapter_list = [c.strip() for c in args.mark_affected.split(",") if c.strip()]
        mark_affected_chapters(lines, chapter_list)
        tb_path.write_text("".join(lines), encoding="utf-8")
        print(f'✅ 已标记 {len(chapter_list)} 个章节为"受影响"：{", ".join(chapter_list)}')
        return

    if not args.chapter:
        sys.exit("❌ 必须指定 --chapter 或 --mark-affected")

    # 校验状态值
    if args.status and args.status not in STATUS_VALUES:
        sys.exit(f"❌ 无效状态值：{args.status}\n   合法值：{', '.join(sorted(STATUS_VALUES))}")
    if args.affected and args.affected not in AFFECTED_VALUES:
        sys.exit(f'❌ 无效受影响值：{args.affected}，应为"是"或"否"')

    ok = update_single_chapter(lines, args.chapter, args)
    if not ok:
        sys.exit(f"❌ 未在 task-board.md 中找到章节：{chapter_key(args.chapter)}")

    tb_path.write_text("".join(lines), encoding="utf-8")

    # 打印更新摘要
    updates = []
    if args.status:     updates.append(f"状态={args.status}")
    if args.batch:      updates.append(f"数据基准批次={args.batch}")
    if args.affected:   updates.append(f"受影响={args.affected}")
    if args.checkpoint is not None:
        updates.append(f"断点事项={'（已清除）' if args.checkpoint == '' else args.checkpoint}")
    if args.notes is not None:
        updates.append(f"自检备注={'（已清除）' if args.notes == '' else args.notes}")
    print(f"✅ 已更新 task-board.md — 第{args.chapter}章：{'; '.join(updates)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="更新 task-board.md 中指定章节的状态字段（update_taskboard.py）"
    )
    parser.add_argument("--project",       required=True, help="项目根目录")
    parser.add_argument("--chapter",       help="章节编号，如 1 或 第1章（与 --mark-affected 二选一）")
    parser.add_argument("--status",        help="新状态值：未开始/进行中/已自检/待人工/已完成")
    parser.add_argument("--batch",         help='数据基准批次，如"第2批"')
    parser.add_argument("--affected",      help="受影响：是 / 否")
    parser.add_argument("--checkpoint",    help="断点事项（传空字符串清除）")
    parser.add_argument("--notes",         help="自检备注（传空字符串清除）")
    parser.add_argument("--mark-affected", metavar="CHAPTERS",
                        help="批量标记受影响章节，逗号分隔，如 1,2,4；其余章节置为否")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
