from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.syllabus_checker.arbitration import write_final_reports
from scripts.syllabus_checker.common import AGENTS, BUILD_DIR, REPORTS_DIR, config_list, load_config, write_json
from scripts.syllabus_checker.det import load_build, run_det_suite
from scripts.syllabus_checker.llm_heuristics import run_llm_heuristics


def run_agent_suite(suite: str, build_dir: Path, reports_dir: Path) -> str:
    profile = AGENTS[suite]
    det = run_det_suite(suite, build_dir)
    data = load_build(build_dir)
    llm = run_llm_heuristics(suite, data)
    combined = sorted(det + llm, key=lambda x: (x.get("testId", ""), x.get("verdict", "")))
    write_json(reports_dir / profile.output, combined)
    non_pass = [x for x in combined if x.get("verdict") not in {"PASS", "SKIP"}]
    fails = sum(1 for x in combined if x.get("verdict") == "FAIL")
    warns = sum(1 for x in combined if x.get("verdict") == "WARN")
    human = sum(1 for x in combined if x.get("verdict") == "NEEDS_HUMAN")
    return f"{profile.icon} {profile.name} ({profile.role}): {len(combined)} тестов, {fails} FAIL, {warns} WARN, {human} NEEDS_HUMAN, non-pass={len(non_pass)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full syllabus check with six background suite agents.")
    parser.add_argument("docx", help="Syllabus .docx path")
    parser.add_argument("--op", help="OP passport .docx path")
    parser.add_argument("--rup", help="RUP .xlsx path")
    parser.add_argument("--build", help="Directory for extracted build JSON files")
    parser.add_argument("--reports", help="Directory for audit report files")
    parser.add_argument("--output-root", help="Write build/ and reports/ under this folder")
    args = parser.parse_args()

    build_dir, reports_dir = _resolve_output_dirs(args)

    for directory in (build_dir, reports_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    extract_cmd = [sys.executable, str(Path(__file__).with_name("extract.py")), args.docx]
    if args.op:
        extract_cmd.extend(["--op", args.op])
    if args.rup:
        extract_cmd.extend(["--rup", args.rup])
    extract_cmd.extend(["--build", str(build_dir)])
    subprocess.run(extract_cmd, check=True)

    summaries: list[str] = []
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="syllabus-agent") as pool:
        futures = {pool.submit(run_agent_suite, suite, build_dir, reports_dir): suite for suite in AGENTS}
        for future in as_completed(futures):
            summaries.append(future.result())

    missing = [profile.output for profile in AGENTS.values() if not (reports_dir / profile.output).exists()]
    if missing:
        for suite, profile in AGENTS.items():
            if profile.output in missing:
                summaries.append(run_agent_suite(suite, build_dir, reports_dir))

    final = write_final_reports(reports_dir, build_dir)
    write_json(reports_dir / "agent-run.json", {"agents": summaries, "status": final["status"], "summary": final["summary"]})
    print("\n".join(sorted(summaries)))
    print(f"FINAL: {final['status']} {final['summary']}")
    return 0


def _resolve_output_dirs(args: argparse.Namespace) -> tuple[Path, Path]:
    config = load_config()
    build_name = (config_list(config, "outputs", "buildDirName") or ["build"])[0]
    reports_name = (config_list(config, "outputs", "reportsDirName") or ["reports"])[0]
    if args.output_root:
        root = Path(args.output_root).resolve()
        return root / build_name, root / reports_name
    build_dir = Path(args.build).resolve() if args.build else BUILD_DIR
    reports_dir = Path(args.reports).resolve() if args.reports else REPORTS_DIR
    return build_dir, reports_dir


if __name__ == "__main__":
    raise SystemExit(main())
