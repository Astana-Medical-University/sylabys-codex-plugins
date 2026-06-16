from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.syllabus_checker.common import BUILD_DIR, REPO_ROOT, config_list, find_fixture, load_config, write_json
from scripts.syllabus_checker.extractor import extract_op, extract_rup, extract_syllabus


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract syllabus, OP and RUP fixtures to build/*.json.")
    parser.add_argument("docx", help="Syllabus .docx path")
    parser.add_argument("--op", help="OP passport .docx path")
    parser.add_argument("--rup", help="RUP .xlsx path")
    parser.add_argument("--build", default=str(BUILD_DIR), help="Directory for extracted build JSON files")
    args = parser.parse_args()

    docx = Path(args.docx).resolve()
    if not docx.exists():
        raise SystemExit(f"Силлабус не найден: {docx}")
    if args.op and not Path(args.op).expanduser().exists():
        raise SystemExit(f"Передан путь к ОП, но файл не найден: {args.op}")
    if args.rup and not Path(args.rup).expanduser().exists():
        raise SystemExit(f"Передан путь к РУП, но файл не найден: {args.rup}")
    config = load_config()
    roots = [docx.parent, Path.cwd(), REPO_ROOT]
    op = Path(args.op).resolve() if args.op else find_fixture(
        config_list(config, "fixtures", "op", "patterns"),
        roots=roots,
        extensions=config_list(config, "fixtures", "op", "extensions"),
    )
    rup = Path(args.rup).resolve() if args.rup else find_fixture(
        config_list(config, "fixtures", "rup", "patterns"),
        roots=roots,
        extensions=config_list(config, "fixtures", "rup", "extensions"),
    )

    build_dir = Path(args.build).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    syllabus = extract_syllabus(docx)
    source = syllabus.get("source", {})
    if source.get("_extraction_error") or not source.get("text"):
        raise SystemExit(f"Силлабус не удалось прочитать (пустой текст). Причина: {source.get('_extraction_error', 'неизвестна')}")
    write_json(build_dir / "syllabus.json", syllabus)

    # Адресная сверка: из ОП и РУП тянем только строки этой дисциплины/модуля.
    desc = (syllabus.get("descriptions") or [{}])[0]
    target_names = [
        desc.get("disciplineName") or "",
        desc.get("moduleName") or "",
        syllabus.get("title") or "",
    ]
    write_json(build_dir / "op.json", extract_op(op, target_names))
    write_json(build_dir / "rup.json", extract_rup(rup, target_names))
    write_json(build_dir / "manifest.json", {"syllabus": str(docx), "op": str(op) if op else "", "rup": str(rup) if rup else "", "targetNames": [t for t in target_names if t]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
