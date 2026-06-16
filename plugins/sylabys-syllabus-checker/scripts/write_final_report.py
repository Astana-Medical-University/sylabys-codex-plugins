from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.syllabus_checker.arbitration import write_final_reports
from scripts.syllabus_checker.common import AGENTS, write_json


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Write final Sylabys syllabus audit after suite subagents finish.")
    parser.add_argument("--build", required=True, help="Directory with extracted build JSON files")
    parser.add_argument("--reports", required=True, help="Directory with str/fmt/op/rup/int/txt suite JSON files")
    args = parser.parse_args()
    build_dir = Path(args.build).resolve()
    reports_dir = Path(args.reports).resolve()
    missing = [profile.output for profile in AGENTS.values() if not (reports_dir / profile.output).exists()]
    final = write_final_reports(reports_dir, build_dir)
    write_json(
        reports_dir / "agent-run.json",
        {
            "mode": "codex-subagents",
            "missingSuiteReports": missing,
            "status": final["status"],
            "summary": final["summary"],
        },
    )
    if missing:
        print("MISSING SUITE REPORTS: " + ", ".join(missing))
    print(f"FINAL: {final['status']} {final['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
