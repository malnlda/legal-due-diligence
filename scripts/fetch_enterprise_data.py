#!/usr/bin/env python3
"""
fetch_enterprise_data.py  v26.6.21.1305
工商数据自动拉取器：在 run-dd 循环中，按章节自动调用 yd-enterprise-info 拉取数据到 raw/chineselaw/。

用法:
    # 拉取所有有适用接口的章节
    python3 fetch_enterprise_data.py --project /path/to/DD项目/

    # 只拉取第1、4章
    python3 fetch_enterprise_data.py --project /path/to/DD项目/ --chapters 1,4

    # 预览命令但不执行
    python3 fetch_enterprise_data.py --project /path/to/DD项目/ --dry-run

    # 显式传入 USCC（覆盖 project-info.md 中的记录）
    python3 fetch_enterprise_data.py --project /path/to/DD项目/ --uscc 91110108MA0074PN30

凭证（必须在环境变量中，绝不接受命令行参数）:
    export CHINESELAW_API_KEY=你的KEY

输出:
    raw/chineselaw/               — 各子命令 JSON 原始数据（由 yd-enterprise-info 写入）
    raw/chineselaw/fetch-log.md   — 本次拉取记录（追加）

安全约束:
    - 凭证只走环境变量 CHINESELAW_API_KEY，绝不接受 --key 等参数，绝不写入任何文件
    - 本脚本不修改 dd-checklist.md / task-board.md / working-paper.md
    - 所有数据落盘到 raw/chineselaw/，不直接写入底稿
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─── 章节 → yd-enterprise-info 子命令映射 ─────────────────────────────────────
# 与 references/external-apis.md 及 references/chineselaw/enterprise-endpoints-summary.md 保持一致
# 格式：chapter_no → (必调命令列表, 建议调用命令列表)

CHAPTER_COMMANDS: dict[int, tuple[list[str], list[str]]] = {
    1:  (["base-info", "change"],
         ["abnormal", "serious-violation"]),
    2:  (["base-info", "equity-pledge", "equity-frozen"],
         []),
    3:  (["base-info"],
         []),
    4:  (["brand", "patent", "soft-right"],
         ["copyright-work", "website"]),
    5:  ([],
         []),                                          # 第5章无适用接口
    6:  ([],
         ["tax-arrears"]),
    7:  ([],
         []),                                          # 第7章无适用接口
    8:  (["outbound-guarantee", "equity-pledge"],
         []),
    9:  (["litigation-stat", "litigation-doc", "executed", "dishonest", "admin-penalty"],
         ["court-announcement", "court-hearing", "equity-frozen", "serious-violation"]),
    10: (["outbound-invest"],
         []),
}

YD_SKILL_DEFAULT = Path.home() / ".claude" / "skills" / "yd-enterprise-info"
YD_SCRIPT_NAME  = "scripts/yd_enterprise_info.py"


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def read_uscc_from_project_info(project_dir: Path) -> str:
    """从 project-info.md 中读取 USCC（统一社会信用代码）"""
    info_path = project_dir / "project-info.md"
    if not info_path.exists():
        return ""
    text = info_path.read_text(encoding="utf-8")
    m = re.search(r"\|\s*\*\*统一社会信用代码\*\*\s*\|\s*([A-Za-z0-9]+)\s*\|", text)
    return m.group(1).strip() if m else ""


def find_yd_script(skill_path: Path) -> Path | None:
    """找到 yd_enterprise_info.py 的绝对路径"""
    candidate = skill_path / YD_SCRIPT_NAME
    return candidate if candidate.exists() else None


def append_fetch_log(log_path: Path, entries: list[dict]) -> None:
    """追加拉取记录到 fetch-log.md"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n## 拉取记录 {now_str}\n\n",
             "| 章节 | 子命令 | 状态 | 备注 |\n",
             "|------|--------|------|------|\n"]
    for e in entries:
        lines.append(f"| {e['chapter']} | `{e['cmd']}` | {e['status']} | {e['note']} |\n")

    if not log_path.exists():
        log_path.write_text(
            "# 工商数据拉取日志（fetch-log.md）\n\n"
            "> 由 fetch_enterprise_data.py 自动追加，不得手动修改数据记录行。\n",
            encoding="utf-8",
        )
    with log_path.open("a", encoding="utf-8") as f:
        f.writelines(lines)


# ─── 核心逻辑 ─────────────────────────────────────────────────────────────────

def run(args) -> int:
    project_dir = Path(args.project)
    raw_dir     = project_dir / "raw" / "chineselaw"
    log_path    = raw_dir / "fetch-log.md"

    # 1. 校验项目目录
    if not project_dir.exists():
        sys.exit(f"❌ 项目目录不存在：{project_dir}")
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 2. 获取 USCC
    uscc = (args.uscc or "").strip() or read_uscc_from_project_info(project_dir)
    if not uscc:
        sys.exit(
            "❌ 未找到 USCC（统一社会信用代码）。\n"
            "   方法 1：运行 init 时传入 --uscc XXXXXX\n"
            "   方法 2：运行本脚本时传入 --uscc XXXXXX"
        )

    # 3. 凭证检查
    api_key = os.environ.get("CHINESELAW_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit(
            "❌ 未找到凭证。请先运行：\n"
            "   export CHINESELAW_API_KEY=你的KEY\n"
            "   凭证只走环境变量，本脚本绝不接受 --key 等参数。"
        )

    # 4. 找 yd 脚本
    skill_path = Path(args.skill_path) if args.skill_path else YD_SKILL_DEFAULT
    yd_script  = find_yd_script(skill_path)
    if yd_script is None and not args.dry_run:
        sys.exit(
            f"❌ 未找到 yd-enterprise-info 脚本：{skill_path / YD_SCRIPT_NAME}\n"
            "   请确认已安装 yd-enterprise-info skill，或用 --skill-path 指定安装路径。"
        )

    # 5. 确定要处理的章节
    if args.chapters:
        try:
            requested = [int(c.strip()) for c in args.chapters.split(",")]
        except ValueError:
            sys.exit(f"❌ --chapters 格式错误，应为逗号分隔的数字，如 1,4,9")
        invalid = [c for c in requested if c not in CHAPTER_COMMANDS]
        if invalid:
            sys.exit(f"❌ 无效章节号：{invalid}，合法值 1-10")
    else:
        requested = list(CHAPTER_COMMANDS.keys())

    # 只保留有适用接口的章节
    chapters_to_run = [c for c in requested
                       if CHAPTER_COMMANDS[c][0] or CHAPTER_COMMANDS[c][1]]
    skipped = [c for c in requested if c not in chapters_to_run]

    print(f"\n{'='*60}")
    print(f"🏢 工商数据拉取  USCC={uscc}")
    print(f"   项目：{project_dir}")
    print(f"   输出：{raw_dir}")
    if args.dry_run:
        print("   模式：DRY RUN（只打印命令，不实际执行）")
    print(f"{'='*60}")

    if skipped:
        print(f"⏭️  跳过无接口章节：{skipped}（第5、7章无适用子命令）\n")

    # 6. 按章节执行子命令
    log_entries: list[dict] = []
    total_ok = total_err = 0

    for ch in chapters_to_run:
        required, optional = CHAPTER_COMMANDS[ch]
        all_cmds = [(c, "必调") for c in required] + [(c, "建议") for c in optional]
        print(f"\n  第{ch}章（共 {len(all_cmds)} 个子命令）")

        for cmd, kind in all_cmds:
            cli = (
                f"python3 {yd_script or '<yd-script>'} "
                f"{cmd} --tyshxydm {uscc} --output {raw_dir}/ --yes"
            )
            print(f"    [{kind}] {cmd}")

            if args.dry_run:
                print(f"       ➜  {cli}")
                log_entries.append({"chapter": f"第{ch}章", "cmd": cmd,
                                    "status": "DRY_RUN", "note": kind})
                continue

            # 实际调用
            try:
                result = subprocess.run(
                    ["python3", str(yd_script), cmd,
                     "--tyshxydm", uscc, "--output", str(raw_dir) + "/", "--yes"],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    print(f"       ✅ 成功")
                    log_entries.append({"chapter": f"第{ch}章", "cmd": cmd,
                                        "status": "✅成功", "note": kind})
                    total_ok += 1
                else:
                    err_summary = (result.stderr or result.stdout or "").strip()[:120]
                    print(f"       ❌ 失败：{err_summary}")
                    log_entries.append({"chapter": f"第{ch}章", "cmd": cmd,
                                        "status": "❌失败",
                                        "note": f"{kind} | {err_summary}"})
                    total_err += 1
            except subprocess.TimeoutExpired:
                print(f"       ⏱️  超时（120s）")
                log_entries.append({"chapter": f"第{ch}章", "cmd": cmd,
                                    "status": "⏱️超时", "note": kind})
                total_err += 1
            except Exception as e:
                print(f"       ❌ 异常：{e}")
                log_entries.append({"chapter": f"第{ch}章", "cmd": cmd,
                                    "status": "❌异常", "note": str(e)[:80]})
                total_err += 1

    # 7. 写拉取日志
    append_fetch_log(log_path, log_entries)

    # 8. 汇总
    print(f"\n{'─'*60}")
    if args.dry_run:
        print(f"DRY RUN 完成，共规划 {len(log_entries)} 个子命令调用")
    else:
        print(f"拉取完成：✅ {total_ok} 成功  ❌ {total_err} 失败")
        if total_err:
            print("   失败项已记录到 fetch-log.md，请在底稿 §X.6 律师备忘中说明原因")
    print(f"📄 日志已追加：raw/chineselaw/fetch-log.md")
    print(f"{'='*60}\n")

    if total_err and not args.dry_run:
        print(
            "⚠️  提示：数据拉取不完整，请在底稿相关章节 §X.6 律师备忘中注明：\n"
            "   「经查阅元典开放平台，[子命令] 接口拉取失败（[时间]），原因：[失败原因]，"
            "   暂无数据，建议后续重试后补入。」"
        )
    return 0 if (total_err == 0 or args.dry_run) else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="工商数据自动拉取器：按章节调用 yd-enterprise-info（fetch_enterprise_data.py）"
    )
    parser.add_argument("--project",    required=True,
                        help="项目根目录")
    parser.add_argument("--uscc",       default="",
                        help="统一社会信用代码（可覆盖 project-info.md 中的记录）")
    parser.add_argument("--chapters",   default="",
                        help="要拉取的章节号，逗号分隔，如 1,4,9（不传则拉取所有有接口的章节）")
    parser.add_argument("--skill-path", default="",
                        help=f"yd-enterprise-info 安装路径（默认 {YD_SKILL_DEFAULT}）")
    parser.add_argument("--dry-run",    action="store_true",
                        help="只打印命令，不实际执行（不需要 API Key）")
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
