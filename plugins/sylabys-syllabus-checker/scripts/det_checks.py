from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.syllabus_checker.common import REPORTS_DIR, write_json
from scripts.syllabus_checker.det import run_det_suite


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run deterministic syllabus checks.")
    parser.add_argument("--suite", required=True, choices=["STR", "FMT", "OP", "RUP", "INT", "TXT"])
    parser.add_argument("--build", default="build")
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    result = run_det_suite(args.suite, Path(args.build))
    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    write_json(out_dir / f"{args.suite.lower()}-det.json", result)
    sys.stdout.write(__import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
