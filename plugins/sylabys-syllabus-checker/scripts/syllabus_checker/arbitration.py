from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .common import AGENTS, BUILD_DIR, REPORTS_DIR, SEVERITY_ORDER, VERDICT_ORDER, config_list, load_config, read_json, write_json


STAGE_MAP = {
    "FMT": "1. Оформление",
    "STR": "2. Структура",
    "RUP": "3. Сверка с РУП",
    "OP": "— Сверка с ОП",
    "INT": "9-20. Внутренняя согласованность",
    "TXT": "— Качество текста",
}


def load_suite_reports(reports_dir: Path = REPORTS_DIR) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for profile in AGENTS.values():
        path = reports_dir / profile.output
        if path.exists():
            items.extend(read_json(path))
        else:
            items.append(
                {
                    "testId": f"{profile.suite}-AGENT",
                    "verdict": "FAIL",
                    "severity": "CRITICAL",
                    "discipline": "",
                    "location": str(path),
                    "expected": "Отчёт агента создан",
                    "actual": "Файл отсутствует",
                    "evidence": profile.name,
                    "recommendation": "Перезапустить агента один раз и проверить TOML-регистрацию.",
                    "confidence": 1.0,
                }
            )
    return items


def final_status(items: list[dict[str, Any]]) -> str:
    if any(x.get("verdict") == "FAIL" and x.get("severity") == "CRITICAL" for x in items):
        return "ОТКЛОНЁН"
    if any(x.get("verdict") == "FAIL" and x.get("severity") == "MAJOR" for x in items):
        return "НА ДОРАБОТКУ"
    if any(x.get("verdict") == "WARN" for x in items):
        return "ПРИНЯТ С ЗАМЕЧАНИЯМИ"
    return "ПРИНЯТ"


def deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    non_pass = [x for x in items if x.get("verdict") != "PASS"]
    has_rup_hours = any(x.get("testId") == "RUP-003" and x.get("verdict") == "FAIL" for x in non_pass)
    result = []
    for item in non_pass:
        if has_rup_hours and item.get("testId") == "INT-021":
            item = dict(item)
            item["cascadeOf"] = "RUP-003"
            item["verdict"] = "SKIP"
            item["recommendation"] = "Каскадное замечание: устранить первичное расхождение часов с РУП."
        result.append(item)
    return sorted(
        result,
        key=lambda x: (
            SEVERITY_ORDER.get(x.get("severity", "WARN"), 9),
            VERDICT_ORDER.get(x.get("verdict", "PASS"), 9),
            x.get("testId", ""),
        ),
    )


def write_final_reports(reports_dir: Path = REPORTS_DIR, build_dir: Path | None = None) -> dict[str, Any]:
    all_items = load_suite_reports(reports_dir)
    issues = deduplicate(all_items)
    counts = Counter(x.get("verdict") for x in all_items)
    status = final_status(all_items)
    build_dir = build_dir or reports_dir.parent / "build"
    syllabus = read_json(build_dir / "syllabus.json") if (build_dir / "syllabus.json").exists() else {}
    final = {
        "status": status,
        "summary": dict(sorted(counts.items())),
        "issues": issues,
        "needsHuman": [x for x in issues if x.get("verdict") == "NEEDS_HUMAN"],
        "humanAudit": build_human_audit(status, counts, issues, syllabus),
    }
    markdown_path = reports_dir / "final-report.md"
    html_path = reports_dir / "final-report.html"
    pdf_path = reports_dir / "final-report.pdf"
    markdown_path.write_text(render_markdown(final, syllabus, build_dir), encoding="utf-8")
    pdf_result = write_pdf_report(markdown_path, pdf_path, html_path)
    final["artifacts"] = {
        "markdown": str(markdown_path),
        "html": str(html_path),
        "pdf": str(pdf_path) if pdf_path.exists() else "",
        "pdfStatus": pdf_result,
    }
    write_json(reports_dir / "final-report.json", final)
    return final


def write_pdf_report(markdown_path: Path, pdf_path: Path, html_path: Path | None = None) -> str:
    html_path = html_path or markdown_path.with_suffix(".html")
    html_path.write_text(_markdown_to_html_document(markdown_path.read_text(encoding="utf-8")), encoding="utf-8")
    config = load_config()
    env_skip = str(config.get("pdf", {}).get("envSkip", "SYLABYS_SKIP_PDF"))
    if not config.get("pdf", {}).get("enabled", True) or os.environ.get(env_skip, "").casefold() in {"1", "true", "yes", "on"}:
        return "PDF пропущен настройкой окружения. HTML сохранён рядом с отчётом."
    browser = _find_browser(config)
    if not browser:
        return "PDF не создан: не найден headless-браузер. HTML сохранён рядом с отчётом."
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()
    with tempfile.TemporaryDirectory(prefix="sylabys-pdf-") as user_data:
        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except Exception as exc:
            return f"PDF не создан: {type(exc).__name__}: {exc}. HTML сохранён рядом с отчётом."
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        return f"PDF не создан: браузер вернул код {completed.returncode}. {stderr[:400]}"
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return "PDF не создан: браузер завершился без файла PDF."
    return "PDF создан"


def _find_browser(config: dict[str, Any] | None = None) -> Path | None:
    config = config or load_config()
    pdf_config = config.get("pdf", {}) if isinstance(config.get("pdf"), dict) else {}
    env_name = str(pdf_config.get("envBrowser") or "SYLABYS_PDF_BROWSER")
    env_browser = os.environ.get(env_name)
    if env_browser:
        candidate = Path(env_browser).expanduser()
        if candidate.exists():
            return candidate
        found = shutil.which(env_browser)
        if found:
            return Path(found)
    for name in config_list(config, "pdf", "browserNames"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for raw_path in config_list(config, "pdf", "browserPaths"):
        candidate = Path(raw_path).expanduser()
        if candidate.exists():
            return candidate
    return None


def _markdown_to_html_document(markdown: str) -> str:
    body = _markdown_to_html(markdown)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Аудит силлабуса</title>
  <style>
    @page {{ size: A4 landscape; margin: 12mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: Arial, "Segoe UI", sans-serif;
      color: #111827;
      font-size: 10px;
      line-height: 1.35;
    }}
    h1 {{ font-size: 20px; margin: 0 0 12px; }}
    h2 {{ font-size: 15px; margin: 18px 0 8px; padding-top: 3px; border-top: 1px solid #d1d5db; }}
    h3 {{ font-size: 12px; margin: 14px 0 6px; }}
    p {{ margin: 5px 0; }}
    ul, ol {{ margin: 5px 0 8px 18px; padding: 0; }}
    li {{ margin: 2px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 7px 0 10px; page-break-inside: auto; }}
    tr {{ page-break-inside: avoid; page-break-after: auto; }}
    th, td {{ border: 1px solid #9ca3af; padding: 4px 5px; vertical-align: top; word-break: break-word; }}
    th {{ background: #eef2ff; font-weight: 700; }}
    blockquote {{ margin: 6px 0; padding: 5px 8px; border-left: 3px solid #6b7280; background: #f9fafb; }}
    code {{ font-family: Consolas, "Courier New", monospace; font-size: 9px; background: #f3f4f6; padding: 1px 3px; }}
    strong {{ font-weight: 700; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("|") and "|" in stripped[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            out.append(_table_to_html(table_lines))
            continue
        if stripped.startswith("# "):
            out.append(f"<h1>{_inline(stripped[2:].strip())}</h1>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{_inline(stripped[3:].strip())}</h2>")
        elif stripped.startswith("### "):
            out.append(f"<h3>{_inline(stripped[4:].strip())}</h3>")
        elif stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{_inline(item)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif stripped.startswith(">"):
            quote = stripped.lstrip("> ").strip()
            out.append(f"<blockquote>{_inline(quote)}</blockquote>")
        else:
            out.append(f"<p>{_inline(stripped)}</p>")
        i += 1
    return "\n".join(out)


def _table_to_html(lines: list[str]) -> str:
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    html_rows = []
    for idx, row in enumerate(rows):
        tag = "th" if idx == 0 else "td"
        html_rows.append("<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in row) + "</tr>")
    return "<table>" + "".join(html_rows) + "</table>"


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def build_human_audit(
    status: str,
    counts: Counter[str],
    issues: list[dict[str, Any]],
    syllabus: dict[str, Any],
) -> dict[str, Any]:
    return {
        "plainStatus": _plain_status(status),
        "document": _document_snapshot(syllabus),
        "dataQualityWarnings": _data_quality_warnings(syllabus),
        "finalControl": _final_control(syllabus),
        "mainFindings": _main_findings(issues),
        "remediationRows": _remediation_rows(issues),
        "literature": _literature_audit(issues, syllabus),
        "suggestedFinalQuestions": _suggested_final_questions(syllabus),
        "summary": dict(sorted(counts.items())),
    }


def render_markdown(final: dict[str, Any], syllabus: dict[str, Any] | None = None, build_dir: Path | None = None) -> str:
    build_dir = build_dir or BUILD_DIR
    syllabus = syllabus or (read_json(build_dir / "syllabus.json") if (build_dir / "syllabus.json").exists() else {})
    audit = final.get("humanAudit") or build_human_audit(
        final["status"],
        Counter(final.get("summary", {})),
        final.get("issues", []),
        syllabus,
    )
    doc = audit["document"]
    lines = [
        f"# Аудит силлабуса «{doc['title']}»",
        "",
        f"Дата проверки: {str(syllabus.get('createdAt', ''))[:10] or 'не указана'}",
        "",
        "Проверенные файлы:",
        f"- силлабус: `{syllabus.get('source', {}).get('path', 'не указано')}`",
        f"- ОП: `{_fixture_path('op', build_dir)}`",
        f"- РУП: `{_fixture_path('rup', build_dir)}`",
        "",
        "## 1. Исполнительное заключение",
        "",
    ]
    lines.extend(
        [
            audit["plainStatus"],
            "",
            "Главная зона риска - не отдельная техническая ошибка, а согласование документа по вертикали: паспорт силлабуса, ОП, РУП, результаты обучения, тематический план и оценивание должны читаться как одна логика.",
            "",
            f"Вердикт по выравниванию: **{final['status']}**. Ниже указано, что именно исправить, где исправить и какой уровень исправления требуется.",
            "",
            "## 2. Фактические данные из документов",
            "",
            "| Позиция | Данные силлабуса | Вывод |",
            "|---|---|---|",
        ]
    )
    for position, value, conclusion in _facts_rows(syllabus, doc):
        lines.append(f"| {position} | {value} | {conclusion} |")
    lines.append("")
    lines.extend(["## 3. Оговорки по извлечению", ""])
    if audit["dataQualityWarnings"]:
        for item in audit["dataQualityWarnings"]:
            lines.append(f"- {item}")
    else:
        lines.append("- Ключевые паспортные поля силлабуса распознаны достаточно для первичного аудита.")
    lines.append("")

    lines.extend(
        [
            "## 4. Что исправить",
            "",
            "| Где исправить | Уровень исправления | Доказательство | Что не так | Как исправить |",
            "|---|---|---|---|---|",
        ]
    )
    for row in audit["remediationRows"]:
        lines.append(
            f"| {row['where']} | {row['level']} | {row['evidence']} | {row['problem']} | {row['fix']} |"
        )
    lines.append("")

    lines.extend(["## 5. Форма итогового контроля", ""])
    lines.extend(
        [
            "Форма итогового контроля, выписанная отдельно:",
            "",
        ]
    )
    for item in audit["finalControl"]:
        lines.append(f"> {item}")
    lines.append("")
    lines.extend(
        [
            "Рекомендуемая единая редакция:",
            "",
            "> Итоговый контроль проводится в форме комплексного экзамена: письменный MEQ/модифицированный эссе-вопрос и оценка практических навыков OSCE/ОСКЭ с клиническим кейсом. Текущий контроль составляет 60%, промежуточная аттестация - 40%, допуск - при ОРД не менее 50%.",
            "",
            "## 6. Литература",
            "",
        ]
    )
    for item in audit["literature"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.extend(["## 7. Рекомендуемые вопросы для итогового контроля", "", "| Вопрос / задание | Формат | Уровень Bloom |", "|---|---|---|"])
    for idx, question in enumerate(audit["suggestedFinalQuestions"], start=1):
        fmt = "Клинико-теоретический вопрос" if idx <= 4 else "Ситуационная задача"
        bloom = "Analyze / Apply" if idx <= 6 else "Analyze"
        lines.append(f"| {question} | {fmt} | {bloom} |")
    lines.append("")
    lines.extend(["## 8. Приоритетные изменения для внесения", ""])
    for idx, row in enumerate(audit["remediationRows"][:10], start=1):
        lines.append(f"{idx}. {row['where']}: {row['fix']} ({row['level']}).")
    lines.append("")
    lines.extend(["## 9. На ручную экспертизу", ""])
    if final["needsHuman"]:
        for item in final["needsHuman"]:
            lines.append(f"- {item.get('testId')}: {item.get('evidence') or item.get('actual')}")
    else:
        lines.append("- Нет отдельных пунктов, требующих ручной экспертизы.")
    lines.extend(["", "## 10. Техническое приложение", ""])
    by_stage: dict[str, list[dict[str, Any]]] = {}
    for item in final["issues"]:
        prefix = str(item.get("testId", "")).split("-")[0]
        by_stage.setdefault(STAGE_MAP.get(prefix, prefix), []).append(item)
    for stage, items in by_stage.items():
        lines.append(f"### {stage}")
        for item in items:
            cascade = f" (каскад от {item['cascadeOf']})" if item.get("cascadeOf") else ""
            lines.append(f"- **{item['severity']} / {item['verdict']} / {item['testId']}**{cascade}: {item.get('actual') or item.get('location')}")
            if item.get("evidence"):
                lines.append(f"  Доказательство: {item['evidence']}")
            if item.get("recommendation"):
                lines.append(f"  Рекомендация: {item['recommendation']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _plain_status(status: str) -> str:
    if status == "ОТКЛОНЁН":
        return "В текущем виде документ нельзя спокойно утверждать: есть критические расхождения и признаки незавершённого оформления."
    if status == "НА ДОРАБОТКУ":
        return "Документ в целом собираем, но перед утверждением нужны содержательные исправления."
    if status == "ПРИНЯТ С ЗАМЕЧАНИЯМИ":
        return "Блокирующих нарушений не найдено, но есть замечания, которые лучше закрыть до финальной версии."
    return "Блокирующих замечаний по автоматической и агентной проверке не найдено."


def _document_snapshot(syllabus: dict[str, Any]) -> dict[str, str]:
    desc = (syllabus.get("descriptions") or [{}])[0]
    program = desc.get("program") or syllabus.get("program") or {}
    credits = desc.get("credits") or {}
    credit_value = credits.get("academic") if isinstance(credits, dict) else syllabus.get("credits")
    return {
        "title": syllabus.get("title") or "не распознано",
        "program": f"{program.get('code', '')} {program.get('name', '')}".strip() or "не распознано",
        "discipline": desc.get("disciplineName") or syllabus.get("title") or "не распознано",
        "courseCredits": f"{desc.get('studyPeriod', {}).get('course') or syllabus.get('course') or 'не распознано'}, {credit_value if credit_value not in (None, '') else 'не распознано'} кредитов",
    }


def _fixture_path(kind: str, build_dir: Path = BUILD_DIR) -> str:
    path = build_dir / f"{kind}.json"
    if not path.exists():
        return "не указано"
    try:
        return read_json(path).get("path") or "не указано"
    except Exception:
        return "не указано"


def _facts_rows(syllabus: dict[str, Any], doc: dict[str, str]) -> list[tuple[str, str, str]]:
    desc = (syllabus.get("descriptions") or [{}])[0]
    hours = desc.get("hours") or {}
    return [
        ("ОП", doc["program"], "Сверить с паспортом ОП"),
        ("Модуль/дисциплина", doc["discipline"], "Требует унификации названия" if ";" in doc["discipline"] else "Распознано"),
        ("Курс и кредиты", doc["courseCredits"], "Сверить с РУП и ОП"),
        ("Часы", f"всего {hours.get('total', 0)}, ПЗ {hours.get('practical', 0)}, СРОП {hours.get('srop', 0)}, СРО {hours.get('sro', 0)}", "Раздел 1 распознан; суммы темплана требуют сверки"),
        ("Итоговый контроль", "; ".join(_final_control(syllabus)), "Форму нужно оставить единообразной во всех разделах"),
    ]


def _remediation_rows(issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        _issue_to_remediation(item)
        for item in issues
        if item.get("verdict") not in {"PASS", "SKIP"} and _is_actionable_issue(item)
    ]
    priority = {"Критический": 0, "Существенный": 1, "Точечный": 2, "Ручная экспертиза": 3, "Редакционный": 4}
    rows.sort(key=lambda row: (priority.get(row["level"], 9), row["where"]))
    compact: list[dict[str, str]] = []
    seen = set()
    for row in rows:
        key = (row["where"], row["problem"])
        if key in seen:
            continue
        seen.add(key)
        compact.append(row)
    return compact or [
        {
            "where": "Силлабус в целом",
            "level": "Точечный",
            "evidence": "Критичных замечаний нет",
            "problem": "Остались только уточнения",
            "fix": "Проверить документ перед утверждением визуально.",
        }
    ]


def _issue_to_remediation(item: dict[str, Any]) -> dict[str, str]:
    test_id = str(item.get("testId", ""))
    where = _where_for_test(test_id, item)
    level = _level_for_issue(item)
    evidence = _clean_cell(item.get("evidence") or item.get("actual") or test_id, 180)
    problem = _problem_for_test(test_id, item)
    fix = _fix_for_test(test_id, item)
    return {"where": where, "level": level, "evidence": evidence, "problem": problem, "fix": fix}


def _level_for_issue(item: dict[str, Any]) -> str:
    if item.get("verdict") == "NEEDS_HUMAN":
        return "Ручная экспертиза"
    if item.get("verdict") == "WARN":
        return "Точечный" if item.get("severity") != "MAJOR" else "Существенный"
    if item.get("severity") == "CRITICAL":
        return "Критический"
    if item.get("severity") == "MAJOR":
        return "Существенный"
    if item.get("verdict") == "WARN":
        return "Точечный"
    return "Редакционный"


def _is_actionable_issue(item: dict[str, Any]) -> bool:
    if item.get("testId") in {"INT-022", "STR-004"} and not item.get("recommendation"):
        return False
    return True


def _where_for_test(test_id: str, item: dict[str, Any]) -> str:
    prefix = test_id.split("-")[0]
    explicit = str(item.get("location") or "").strip()
    mapping = {
        "FMT": "Оформление DOCX",
        "STR": "Структура силлабуса",
        "OP": "Раздел 1 и матрица ОП",
        "RUP": "Раздел 1 и РУП",
        "INT": "Внутренняя согласованность",
        "TXT": "Текст и литература",
    }
    return explicit if explicit and not explicit.startswith("build/") else mapping.get(prefix, "Силлабус")


def _problem_for_test(test_id: str, item: dict[str, Any]) -> str:
    actual = _clean_cell(item.get("actual") or "", 160)
    catalog = {
        "FMT-004": "В документе остались следы рабочей правки: track changes, комментарии или выделения.",
        "FMT-003": "Поля страницы не соответствуют шаблону.",
        "STR-002": "Не найдены обязательные структурные разделы.",
        "OP-002": "Дисциплина не сопоставилась со строкой паспорта ОП.",
        "OP-006": "Не подтверждено покрытие требуемых программных результатов обучения.",
        "RUP-001": "Период обучения не подтвержден по РУП.",
        "RUP-002": "Кредиты не подтверждены по РУП.",
        "RUP-003": "Часы не подтверждены по РУП.",
        "INT-021": "Распределение часов Л/ПЗ/СРОП/СРО в тематическом плане не совпадает с разделом описания.",
        "INT-030": "Не все РО покрыты тематическим планом.",
        "INT-031": "Не все практические навыки покрыты тематическим планом.",
        "INT-040": "Структура оценивания 60/40 не выделена однозначно.",
        "INT-053": "Сведения о преподавателях не извлечены как структурированный блок.",
        "INT-055": "Блок согласования и утверждения неполный.",
        "TXT-002": "В тексте или литературе есть шаблонные маркеры и незаполненные библиографические поля.",
    }
    return catalog.get(test_id, actual or "Требуется уточнение по результату проверки.")


def _fix_for_test(test_id: str, item: dict[str, Any]) -> str:
    recommendation = _clean_cell(item.get("recommendation") or "", 220)
    catalog = {
        "FMT-004": "Принять или отклонить все правки, удалить комментарии и цветовые выделения; сохранить финальную чистую версию DOCX.",
        "FMT-003": "Выставить поля по шаблону ДАР: верх/низ 1,5 см, левое 2,5 см, правое 1 см.",
        "STR-002": "Добавить отсутствующие разделы или привести их заголовки к стандарту силлабуса.",
        "OP-002": "Унифицировать название дисциплины/модуля с паспортом ОП; для модульного документа развести дисциплины отдельными строками.",
        "OP-006": "Добавить явную матрицу соответствия РО дисциплины к РО ОП и убрать лишние связи.",
        "RUP-001": "Сверить курс, семестр и период обучения с РУП.",
        "RUP-002": "Сверить количество кредитов с РУП и паспортом ОП.",
        "RUP-003": "Сверить общий объем и разбивку часов с РУП.",
        "INT-021": "Исправить тематический план так, чтобы по каждому виду занятий Л/ПЗ/СРОП/СРО сумма строк совпала с разделом 1; если раздел 1 неверен, синхронизировать его с РУП.",
        "INT-030": "Для каждого РО добавить темы, часы, методы обучения и оценивание.",
        "INT-031": "Для каждого ПН добавить темы или станции/кейсы, где навык формируется и оценивается.",
        "INT-040": "Описать текущий контроль 60%, промежуточную аттестацию 40%, формулу, допуск и чек-листы в одном месте без противоречий.",
        "INT-053": "Заполнить таблицу преподавателей: ФИО, должность, кафедра/клиническая база, e-mail.",
        "INT-055": "Заполнить разработчиков, согласующих, протокол кафедры и утверждение.",
        "TXT-002": "Исправить библиографию: заменить [и др.], [s. l.], [б. и.], [Электронный ресурс] на полноценные описания или удалить заготовки.",
    }
    return catalog.get(test_id, recommendation or "Проверить пункт вручную и внести правку в соответствующий раздел силлабуса.")


def _clean_cell(value: Any, limit: int = 180) -> str:
    text = str(value).replace("|", "/")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text or "не указано"


def _data_quality_warnings(syllabus: dict[str, Any]) -> list[str]:
    warnings = []
    desc = (syllabus.get("descriptions") or [{}])[0]
    discipline = str(desc.get("disciplineName") or "")
    hours = desc.get("hours") or {}
    credits = desc.get("credits") or {}
    if discipline in {"", "(модуля)", "(модуль)"}:
        warnings.append("Название дисциплины извлечено ненадёжно. Нужно проверить титул и раздел 1: без этого сверка с ОП и РУП может давать ложные срабатывания.")
    if (credits.get("academic") if isinstance(credits, dict) else syllabus.get("credits")) in (0, 0.0, "", None):
        warnings.append("Кредиты не распознаны как структурированное поле. Для строгой сверки с ОП/РУП это нужно исправить в экстракции или в исходном шаблоне.")
    if any((hours.get(k) or 0) > 500 for k in ("lecture", "practical", "sro", "srop", "clinicalBasePractice")):
        warnings.append("Часы распознаны с явной ошибкой, например год мог попасть в поле лекций. Выводы по часам нужно подтверждать визуально по документу.")
    return warnings


def _final_control(syllabus: dict[str, Any]) -> list[str]:
    text = syllabus.get("source", {}).get("text", "")
    items = []
    low = text.casefold()
    if "meq" in low or "модифицирован" in low:
        items.append("Промежуточная аттестация заявлена как комплексный экзамен: 1-й этап - письменный MEQ/модифицированный эссе-вопрос, максимум 100 баллов.")
    if "osce" in low or "оскэ" in low or "оске" in low:
        items.append("2-й этап - оценка практических навыков: OSCE/ОСКЭ плюс клинический кейс, максимум 100 баллов.")
    if "орд" in low and "0,6" in low and "0,4" in low:
        items.append("Итоговая оценка считается по формуле с весами: рейтинг допуска 60% и промежуточный контроль 40%.")
    for marker in [
        "Промежуточная аттестация по каждой дисциплине",
        "Письменный экзамен",
        "Оценка практических навыков выполняется",
        "ИО=",
    ]:
        fragment = _slice_sentence(text, marker)
        if fragment and len(items) < 3:
            items.append(fragment)
    if not items:
        return ["Форма итогового контроля не выделена структурированно. Нужно проверить раздел оценивания и приложение с КИС вручную."]
    return items[:5]


def _main_findings(issues: list[dict[str, Any]]) -> list[str]:
    findings = []
    by_id = {item.get("testId"): item for item in issues}
    if "FMT-004" in by_id:
        findings.append("Файл выглядит как рабочая версия: в DOCX есть следы правок, комментариев или цветовых выделений. Перед утверждением их нужно принять/удалить.")
    if "STR-002" in by_id:
        findings.append(f"Структура неполная: автоматическая проверка не нашла обязательные разделы ({by_id['STR-002'].get('actual')}).")
    if any(k in by_id for k in ("OP-001", "OP-002", "OP-006")):
        findings.append("Связь с образовательной программой требует проверки: есть расхождения по паспорту ОП, названию/шифру или покрытию программных результатов обучения.")
    if any(k in by_id for k in ("RUP-001", "RUP-002", "RUP-003", "INT-020", "INT-021")):
        findings.append("Учебный план и часы нельзя считать подтверждёнными: нужно вручную сверить дисциплину в РУП, кредиты, общий объём и разбивку часов.")
    if any(k in by_id for k in ("INT-012", "INT-030", "INT-031", "INT-032", "INT-033")):
        findings.append("Связка 'результаты обучения - практические навыки - темы - оценивание' не доказана полностью. Это главный содержательный блок для доработки.")
    if "INT-040" in by_id:
        findings.append("Оценивание нужно привести к прозрачной схеме: текущий контроль, промежуточная аттестация, веса, чек-листы и условия допуска должны читаться без двусмысленности.")
    if "INT-055" in by_id:
        findings.append("Блок согласования и утверждения неполный. Формально такой документ нельзя закрывать как финальный.")
    if not findings:
        findings.append("Критичных содержательных расхождений в агрегированном отчёте не осталось.")
    return findings


def _literature_audit(issues: list[dict[str, Any]], syllabus: dict[str, Any]) -> list[str]:
    text = syllabus.get("source", {}).get("text", "")
    items = []
    if any(item.get("testId") == "TXT-002" for item in issues):
        items.append("В списке литературы или тексте есть шаблонные маркеры вроде '[и др.]', '[Электронный ресурс]', '[s. l.]'. Их нужно заменить полноценным библиографическим описанием или убрать.")
    if "ГЭОТАР" in text or "GEOTAR" in text or "studentlibrary" in text:
        items.append("База литературы по внутренним болезням выглядит релевантной для кардио-респираторного модуля, но библиографию нужно вычистить и унифицировать.")
    if "2024" in text or "2025" in text:
        items.append("Есть свежие источники 2024-2025 годов; их стоит оставить как приоритетные, особенно профильные кардиология/пульмонология.")
    if not items:
        items.append("Литература не извлечена как отдельный структурированный список. Нужно проверить раздел 10 и карту обеспеченности вручную.")
    return items


def _suggested_final_questions(syllabus: dict[str, Any]) -> list[str]:
    plan = []
    for block in syllabus.get("disciplineBlocks") or []:
        plan.extend(block.get("thematicPlan") or [])
    topics = []
    seen = set()
    for row in plan:
        topic = str(row.get("topic") or "").strip()
        topic = " ".join(topic.split())
        if len(topic) < 20:
            continue
        key = topic[:90].casefold()
        if key in seen:
            continue
        seen.add(key)
        topics.append(topic)
    if not topics:
        topics = _topics_from_text(syllabus.get("source", {}).get("text", ""))
    questions = []
    for topic in topics[:12]:
        clean = topic.strip(" .")
        if ":" in clean:
            clean = clean.split(":", 1)[1].strip() or clean
        clean = re.sub(r",\s*[а-яё]\.?$", "", clean, flags=re.IGNORECASE).strip()
        if clean.casefold() == "плеврит":
            clean = "Плеврит: диагностика, дифференциальная диагностика и принципы лечения"
        questions.append(f"Раскройте клинико-диагностический подход и принципы лечения по теме: {clean[:220]}.")
    if questions:
        return questions
    return [
        "Сформулируйте диагностический алгоритм по ключевой нозологии дисциплины.",
        "Обоснуйте выбор лабораторно-инструментальных методов исследования.",
        "Разберите клинический случай с постановкой предварительного диагноза и планом ведения.",
    ]


def _topics_from_text(text: str) -> list[str]:
    candidate_patterns = [
        r"Артериальная гипертензия[^.\n]{20,260}",
        r"Стабильная стенокардия[^.\n]{20,220}",
        r"Острый коронарный синдром[^.\n]{20,220}",
        r"Острая сердечная недостаточность[^.\n]{0,220}",
        r"Хроническая сердечная недостаточность[^.\n]{0,220}",
        r"Пневмония[^.\n]{20,220}",
        r"Бронхиальная астма[^.\n]{0,220}",
        r"ХОБЛ[^.\n]{0,220}",
        r"Плеврит[^.\n]{0,220}",
        r"Дыхательная недостаточность[^.\n]{0,220}",
    ]
    topics = []
    seen = set()
    for pattern in candidate_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            topic = " ".join(match.group(0).split()).strip(" :;,.")
            key = topic[:60].casefold()
            if key and key not in seen:
                seen.add(key)
                topics.append(topic)
                break
    return topics


def _slice_sentence(text: str, marker: str, limit: int = 360) -> str:
    idx = text.casefold().find(marker.casefold())
    if idx < 0:
        return ""
    fragment = " ".join(text[idx : idx + limit].split())
    return fragment.rstrip(" ,;")
