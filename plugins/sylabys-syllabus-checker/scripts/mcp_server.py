from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable or "python"
SUITES = {
    "STR": "structure and required syllabus sections",
    "FMT": "DOCX formatting, margins, comments, tracked changes and template hygiene",
    "OP": "aim, learning outcomes and OP alignment",
    "RUP": "credits, study period and hour distribution alignment with curriculum",
    "INT": "internal consistency of topics, Bloom levels, outcomes, practical skills, assessment and hours",
    "TXT": "language quality, bibliography and final-control wording",
}

SERVER_NAME = "sylabys-syllabus-checker"
TOOL_NAME = "prepare_syllabus_audit"
TOOL_DESCRIPTION = (
    "Prepare a Sylabys syllabus audit plan for @sylabys-syllabus-checker. "
    "Returns exact commands and prompts for six real Codex subagents; does not replace subagents."
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

    extract_command = [PYTHON, str(PLUGIN_ROOT / "scripts" / "extract.py"), syllabus, "--build", str(build_dir)]
    if op:
        extract_command.extend(["--op", op])
    if rup:
        extract_command.extend(["--rup", rup])

    suite_commands = {
        suite: [
            PYTHON,
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
        PYTHON,
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


def prepare_syllabus_audit(
    syllabus_path: str,
    output_root: str | None = None,
    op_path: str | None = None,
    rup_path: str | None = None,
) -> dict[str, Any]:
    return build_audit_plan(syllabus_path, output_root, op_path, rup_path)


def _plugin_version() -> str:
    manifest = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _tool_descriptor() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "syllabus_path": {
                    "type": "string",
                    "description": "Path to the syllabus .docx file.",
                },
                "output_root": {
                    "type": "string",
                    "description": "Optional folder where build/ and reports/ should be written.",
                },
                "op_path": {
                    "type": "string",
                    "description": "Optional explicit path to the educational program passport.",
                },
                "rup_path": {
                    "type": "string",
                    "description": "Optional explicit path to the curriculum/RUP file.",
                },
            },
            "required": ["syllabus_path"],
            "additionalProperties": False,
        },
    }


def _success(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def _handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")

    if method == "initialize":
        protocol_version = (message.get("params") or {}).get("protocolVersion", "2024-11-05")
        return _success(
            message_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": _plugin_version()},
                "instructions": (
                    "Use prepare_syllabus_audit first, then run the returned extraction command, "
                    "spawn six real Codex subagents, and run final arbitration."
                ),
            },
        )

    if method == "tools/list":
        return _success(message_id, {"tools": [_tool_descriptor()]})

    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL_NAME:
            return _error(message_id, -32602, f"Unknown tool: {params.get('name')}")
        arguments = params.get("arguments") or {}
        try:
            result = prepare_syllabus_audit(
                syllabus_path=str(arguments.get("syllabus_path") or ""),
                output_root=arguments.get("output_root"),
                op_path=arguments.get("op_path"),
                rup_path=arguments.get("rup_path"),
            )
        except Exception as exc:
            return _success(
                message_id,
                {
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                    "isError": True,
                },
            )
        return _success(
            message_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": False,
            },
        )

    if method and method.startswith("notifications/"):
        return None

    return _error(message_id, -32601, f"Method not found: {method}")


def serve() -> None:
    for raw_line in sys.stdin.buffer:
        line = raw_line.decode("utf-8").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = _handle_request(message)
        except Exception as exc:
            response = _error(None, -32700, f"Parse error: {type(exc).__name__}: {exc}")
        if response is not None:
            payload = json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
            sys.stdout.buffer.write(payload.encode("utf-8"))
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    serve()
