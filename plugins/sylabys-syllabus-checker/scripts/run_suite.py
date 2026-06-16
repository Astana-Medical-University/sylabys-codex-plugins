from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.syllabus_checker.common import AGENTS, sorted_verdicts, write_json
from scripts.syllabus_checker.det import load_build, run_det_suite
from scripts.syllabus_checker.llm_heuristics import run_llm_heuristics


def run_agent_suite(suite: str, build_dir: Path, reports_dir: Path) -> str:
    profile = AGENTS[suite]
    reports_dir.mkdir(parents=True, exist_ok=True)
    det = run_det_suite(suite, build_dir)
    data = load_build(build_dir)
    llm = run_llm_heuristics(suite, data)
    combined = sorted_verdicts(det + llm)
    write_json(reports_dir / profile.output, combined)
    non_pass = [item for item in combined if item.get("verdict") not in {"PASS", "SKIP"}]
    fails = sum(1 for item in combined if item.get("verdict") == "FAIL")
    warns = sum(1 for item in combined if item.get("verdict") == "WARN")
    human = sum(1 for item in combined if item.get("verdict") == "NEEDS_HUMAN")
    return (
        f"{profile.name}: {len(combined)} тестов, "
        f"{fails} FAIL, {warns} WARN, {human} NEEDS_HUMAN, non-pass={len(non_pass)}"
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run one Sylabys syllabus suite for a Codex subagent.")
    parser.add_argument("--suite", required=True, choices=sorted(AGENTS))
    parser.add_argument("--build", required=True, help="Directory with extracted build JSON files")
    parser.add_argument("--reports", required=True, help="Directory where the suite JSON report is written")
    args = parser.parse_args()
    summary = run_agent_suite(args.suite, Path(args.build).resolve(), Path(args.reports).resolve())
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
