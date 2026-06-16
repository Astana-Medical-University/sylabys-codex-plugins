from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "STR": "structure and required syllabus sections",
    "FMT": "DOCX formatting, margins, comments, tracked changes and template hygiene",
    "OP": "aim, learning outcomes and OP alignment",
    "RUP": "credits, study period and hour distribution alignment with curriculum",
    "INT": "internal consistency of topics, Bloom levels, outcomes, practical skills, assessment and hours",
    "TXT": "language quality, bibliography and final-control wording",
}

mcp = FastMCP(
    "sylabys-syllabus-checker",
    instructions=(
        "Prepare Sylabys syllabus audits. This MCP tool does not perform the full audit itself: "
        "Codex must spawn six real subagents, one per suite, then run final arbitration."
    ),
)


def _resolve_source_root(syllabus_path: str, output_root: str | None = None) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve()
    if syllabus_path:
        candidate = Path(syllabus_path).expanduser()
        if candidate.suffix.casefold() == ".docx":
            return candidate.resolve().parent
        return candidate.resolve()
    return Path.cwd().resolve()


def build_audit_plan(
    syllabus_path: str,
    output_root: str | None = None,
    op_path: str | None = None,
    rup_path: str | None = None,
) -> dict[str, Any]:
    source_root = _resolve_source_root(syllabus_path, output_root)
    build_dir = source_root / "build"
    reports_dir = source_root / "reports"
    syllabus = str(Path(syllabus_path).expanduser().resolve()) if syllabus_path else ""
    op = str(Path(op_path).expanduser().resolve()) if op_path else ""
    rup = str(Path(rup_path).expanduser().resolve()) if rup_path else ""

    extract_command = ["python", str(PLUGIN_ROOT / "scripts" / "extract.py"), syllabus, "--build", str(build_dir)]
    if op:
        extract_command.extend(["--op", op])
    if rup:
        extract_command.extend(["--rup", rup])

    suite_commands = {
        suite: [
            "python",
            str(PLUGIN_ROOT / "scripts" / "run_suite.py"),
            "--suite",
            suite,
            "--build",
            str(build_dir),
            "--reports",
            str(reports_dir),
        ]
        for suite in SUITES
    }
    suite_reports = {suite: str(reports_dir / f"{suite.lower()}.json") for suite in SUITES}
    final_command = [
        "python",
        str(PLUGIN_ROOT / "scripts" / "write_final_report.py"),
        "--build",
        str(build_dir),
        "--reports",
        str(reports_dir),
    ]

    subagent_prompts = {
        suite: (
            f"Ты Codex-субагент suite {suite} для Sylabys Syllabus Checker. "
            f"Задача: {description}. Не спавнь других агентов и не редактируй исходные DOCX/XLSX. "
            f"Запусти команду: {' '.join(suite_commands[suite])}. "
            f"Проверь, что создан файл {suite_reports[suite]}. "
            "Финально сообщи только suite, количество тестов, FAIL/WARN/NEEDS_HUMAN и путь к JSON."
        )
        for suite, description in SUITES.items()
    }

    return {
        "mode": "plugin-mcp-plus-real-codex-subagents",
        "pluginRoot": str(PLUGIN_ROOT),
        "sourceRoot": str(source_root),
        "syllabusPath": syllabus,
        "opPath": op,
        "rupPath": rup,
        "buildDir": str(build_dir),
        "reportsDir": str(reports_dir),
        "extractCommand": extract_command,
        "suiteCommands": suite_commands,
        "suiteReports": suite_reports,
        "subagentPrompts": subagent_prompts,
        "finalCommand": final_command,
        "finalReportPdf": str(reports_dir / "final-report.pdf"),
        "instructionsForCodex": [
            "Run extractCommand in the main thread.",
            "Spawn six real Codex subagents in parallel: STR, FMT, OP, RUP, INT, TXT.",
            "Give each subagent only its matching subagentPrompts item and paths.",
            "Wait for all six subagents.",
            "If a suite JSON is missing, rerun that same suite once via a Codex subagent.",
            "Run finalCommand in the main thread.",
            "Answer in Russian with the human-readable audit result and finalReportPdf path.",
            "Do not use scripts/run_check.py unless the user explicitly asks for emergency non-subagent fallback.",
        ],
    }


@mcp.tool(
    name="prepare_syllabus_audit",
    description=(
        "Prepare a Sylabys syllabus audit plan for @sylabys-syllabus-checker. "
        "Returns exact commands and prompts for six real Codex subagents; does not replace subagents."
    ),
)
def prepare_syllabus_audit(
    syllabus_path: str,
    output_root: str | None = None,
    op_path: str | None = None,
    rup_path: str | None = None,
) -> dict[str, Any]:
    return build_audit_plan(syllabus_path, output_root, op_path, rup_path)


if __name__ == "__main__":
    mcp.run("stdio")
