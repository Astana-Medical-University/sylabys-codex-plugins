from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import inspect_docx_format, normalize_text, parse_first_number, read_docx, read_xlsx, stable_id


PROGRAM_CODE_RE = re.compile(r"\b\d[А-ЯA-Z]\d{5}\b")


def _program_from_text(text: str) -> dict[str, str]:
    code_match = PROGRAM_CODE_RE.search(text)
    name = ""
    for candidate in ("Медицина", "Педиатрия", "Общая медицина"):
        if candidate.casefold() in text.casefold():
            name = candidate
            break
    return {"code": code_match.group(0) if code_match else "", "name": name, "level": ""}


def _extract_hours(text: str) -> dict[str, float]:
    return {
        "total": _number_after_label(text, ["общий объем дисциплины", "общий объем"], allow_inline=False),
        "lecture": _number_after_label(text, ["объем лекций"], allow_inline=False),
        "practical": _number_after_label(text, ["объем практических занятий"], allow_inline=False),
        "srop": _number_after_label(text, ["объем сроп", "сроп"], allow_inline=False),
        "sro": _number_after_label(text, ["объем сро", "сро"], allow_inline=False),
        "clinicalBasePractice": _number_after_label(text, ["объем практики на клинической базе", "практики на клинической базе"], allow_inline=False),
    }


def _extract_learning_outcomes(text: str) -> list[dict[str, Any]]:
    outcomes: dict[str, str] = {}
    for match in re.finditer(r"\bРО\s*([0-9]+)\b[.:;\-\s]*(.{0,260})", text, flags=re.IGNORECASE):
        code = f"РО{int(match.group(1))}"
        desc = normalize_text(match.group(2).split("\n")[0])
        outcomes.setdefault(code, desc)
    return [
        {"code": code, "description": desc, "assessmentInstruments": []}
        for code, desc in sorted(outcomes.items(), key=lambda item: int(re.search(r"\d+", item[0]).group(0)))
    ]


def _extract_practical_skills(text: str) -> list[dict[str, Any]]:
    skills: dict[str, str] = {}
    for match in re.finditer(r"\bПН\s*([0-9]+)\b[.:;\-\s]*(.{0,220})", text, flags=re.IGNORECASE):
        code = f"ПН{int(match.group(1))}"
        skills.setdefault(code, normalize_text(match.group(2).split("\n")[0]))
    return [
        {"code": code, "description": desc}
        for code, desc in sorted(skills.items(), key=lambda item: int(re.search(r"\d+", item[0]).group(0)))
    ]


def _extract_thematic_plan(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    rows = []
    order = 1
    for table in tables:
        header_idx, columns = _thematic_plan_columns(table)
        if header_idx is None:
            continue
        current_ro = ""
        current_topic = ""
        for row in table[header_idx + 1 :]:
            joined = " | ".join(row)
            if "итого" in joined.casefold():
                continue
            ro_value = _cell(row, columns.get("ro"))
            topic = _cell(row, columns.get("topic"))
            ro_match = re.search(r"\bРО\s*\d+\b", ro_value or joined, re.IGNORECASE)
            if ro_match:
                current_ro = ro_match.group(0).replace(" ", "").upper()
            if topic:
                current_topic = topic
            hours = {
                "lecture": _number_cell(row, columns.get("lecture")),
                "practical": _number_cell(row, columns.get("practical")),
                "srop": _number_cell(row, columns.get("srop")),
                "sro": _number_cell(row, columns.get("sro")),
            }
            if not current_ro or (not topic and sum(hours.values()) <= 0):
                continue
            pn_value = _cell(row, columns.get("pn"))
            rows.append(
                {
                    "order": order,
                    "learningOutcomeCode": current_ro,
                    "practicalSkillCodes": [x.replace(" ", "").upper() for x in re.findall(r"\bПН\s*\d+\b", pn_value or joined, re.IGNORECASE)],
                    "topic": topic or current_topic,
                    "hours": hours,
                    "teachingMethods": [_cell(row, columns.get("methods"))] if _cell(row, columns.get("methods")) else [],
                    "assessmentMethods": [],
                }
            )
            order += 1
    return rows


def _thematic_plan_columns(table: list[list[str]]) -> tuple[int | None, dict[str, int]]:
    for idx in range(min(4, max(0, len(table) - 1))):
        top = [_normalize_header_cell(cell) for cell in table[idx]]
        bottom = [_normalize_header_cell(cell) for cell in table[idx + 1]]
        joined_top = " ".join(top)
        joined_bottom = " ".join(bottom)
        if "количество" not in joined_top or "час" not in joined_top:
            continue
        if not {"пз", "сроп", "сро"}.issubset(set(bottom)):
            continue
        columns: dict[str, int] = {}
        for col_idx, cell in enumerate(top):
            if "ро" in cell and ("результат" in cell or "код" in cell):
                columns["ro"] = col_idx
            elif "пн" in cell or "практический навык" in cell:
                columns["pn"] = col_idx
            elif "тема" in cell:
                columns["topic"] = col_idx
        for col_idx, cell in enumerate(bottom):
            if cell in {"л", "лекция", "лекции"} or "лекц" in cell:
                columns["lecture"] = col_idx
            elif cell in {"пз", "практические занятия", "практическое занятие"} or "практич" in cell:
                columns["practical"] = col_idx
            elif cell == "сроп":
                columns["srop"] = col_idx
            elif cell == "сро":
                columns["sro"] = col_idx
        required = {"ro", "topic", "lecture", "practical", "srop", "sro"}
        if required.issubset(columns):
            return idx + 1, columns

    for idx, row in enumerate(table[:5]):
        normalized = [_normalize_header_cell(cell) for cell in row]
        joined = " ".join(normalized)
        if "тема" not in joined or "сроп" not in joined or "сро" not in joined:
            continue
        columns: dict[str, int] = {}
        for col_idx, cell in enumerate(normalized):
            if cell in {"код ро", "ро"} or ("код" in cell and "ро" in cell):
                columns["ro"] = col_idx
            elif "код" in cell and "пн" in cell:
                columns["pn"] = col_idx
            elif cell == "тема" or "тема" in cell:
                columns["topic"] = col_idx
            elif cell in {"л", "лекция", "лекции"} or "лекц" in cell:
                columns["lecture"] = col_idx
            elif cell in {"пз", "практические занятия", "практическое занятие"} or "практич" in cell:
                columns["practical"] = col_idx
            elif cell == "сроп":
                columns["srop"] = col_idx
            elif cell == "сро":
                columns["sro"] = col_idx
            elif "метод" in cell:
                columns["methods"] = col_idx
        required = {"ro", "topic", "lecture", "practical", "srop", "sro"}
        if required.issubset(columns):
            return idx, columns
    return None, {}


def _normalize_header_cell(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").casefold().replace("ё", "е")).strip()


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return normalize_text(row[idx])


def _number_cell(row: list[str], idx: int | None) -> float:
    value = _cell(row, idx)
    if value in {"-", "–", "—"}:
        return 0
    return parse_first_number(value) or 0


def extract_syllabus(path: Path) -> dict[str, Any]:
    doc = read_docx(path)
    text = doc.get("text", "")
    paragraphs = doc.get("paragraphs", [])
    title = _extract_title(text) or path.stem
    academic_year = ""
    year_match = re.search(r"20\d{2}\s*[-–]\s*20\d{2}", text)
    if year_match:
        academic_year = year_match.group(0).replace(" ", "").replace("–", "-")
    course = int(_number_after_label(text, ["курс"], allow_inline=False) or 0)
    credits = _number_after_label(text, ["количество академических кредитов", "количество кредитов"], allow_inline=False)
    syllabus_type = "module" if re.search(r"\bмодул", title + "\n" + text[:1500], re.IGNORECASE) else "discipline"
    discipline_name = _extract_discipline_name(text) or title
    hours = _extract_hours(text)
    program = _program_from_text(text)
    now = datetime.now(timezone.utc).isoformat()
    learning = _extract_learning_outcomes(text)
    skills = _extract_practical_skills(text)
    plan = _extract_thematic_plan(doc.get("tables", []))
    return {
        "id": stable_id(str(path.resolve())),
        "type": syllabus_type,
        "title": title,
        "academicYear": academic_year,
        "program": program,
        "credits": credits,
        "course": course,
        "city": "Астана" if "астана" in text.casefold() else "",
        "publicationYear": int(academic_year[:4]) if academic_year else 0,
        "descriptions": [
            {
                "disciplineName": discipline_name,
                "program": program,
                "cycleAndComponent": "",
                "studyPeriod": {"course": course, "semester": ""},
                "credits": {"academic": credits, "ects": credits},
                "hours": hours,
                "formsOfClasses": [],
                "prerequisites": [],
                "postrequisites": [],
            }
        ],
        "teachers": [],
        "aimAndSummary": {"aim": _slice_after(text, "цель", 500), "shortSummary": _slice_after(text, "краткое содержание", 700)},
        "disciplineBlocks": [
            {
                "disciplineName": discipline_name,
                "learningOutcomes": learning,
                "practicalSkills": skills,
                "thematicPlan": plan,
            }
        ],
        "sropSchedule": [],
        "policy": {},
        "assessments": [
            {
                "disciplineName": discipline_name,
                "structure": _assessment_structure(text),
                "currentControl": {},
                "intermediateAttestation": {"maxScore": 100},
                "redFlags": [],
                "admissionRatingFormula": _slice_after(text, "орд", 250),
                "finalGradeFormula": _slice_after(text, "ио", 250),
            }
        ],
        "references": [],
        "glossary": [],
        "examMaterials": {"questions": []},
        "resourceCard": {},
        "approval": {"departmentProtocol": "", "developers": [], "agreedBy": []},
        "source": doc,
        "format": inspect_docx_format(path),
        "version": "0.1.0",
        "createdAt": now,
        "updatedAt": now,
    }


def _slice_after(text: str, needle: str, limit: int) -> str:
    low = text.casefold()
    idx = low.find(needle.casefold())
    if idx < 0:
        return ""
    return normalize_text(text[idx : idx + limit])


def _lines(text: str) -> list[str]:
    return [normalize_text(x) for x in text.splitlines() if normalize_text(x)]


def _number_after_label(text: str, labels: list[str], *, allow_inline: bool = True) -> float:
    lines = _lines(text)
    label_set = [label.casefold() for label in labels]
    for idx, line in enumerate(lines):
        low = line.casefold().strip(" :;")
        if not any(_label_matches(low, label) for label in label_set):
            continue
        inline = re.sub("|".join(re.escape(label) for label in labels), "", line, flags=re.IGNORECASE).strip(" :-")
        if allow_inline:
            value = parse_first_number(inline)
            if value is not None:
                return value
        collected = []
        for next_line in lines[idx + 1 : idx + 6]:
            if re.search(r"[A-Za-zА-Яа-яЁё]{3,}", next_line) and collected:
                break
            if re.search(r"\d", next_line) or next_line in {"-", "–"}:
                collected.append(next_line)
            elif collected:
                break
        joined = "".join(x for x in collected if re.search(r"\d", x))
        if joined:
            value = parse_first_number(joined)
            if value is not None:
                return value
    return 0


def _label_matches(line: str, label: str) -> bool:
    if label == "объем сро":
        return "объем сро" in line and "сроп" not in line
    if label in {"курс", "сро", "сроп"}:
        return line == label or line.startswith(f"{label} ")
    return label in line


def _extract_title(text: str) -> str:
    compact = "\n".join(_lines(text[:2500]))
    match = re.search(r"СИЛЛАБУС\s+(?:Модуль|Дисциплина)\s*:?\s*(.+?)\s*20\s*\d", compact, re.IGNORECASE | re.DOTALL)
    if match:
        return normalize_text(match.group(1))
    return ""


def _extract_discipline_name(text: str) -> str:
    lines = _lines(text)
    for idx, line in enumerate(lines):
        if line.casefold() != "наименование дисциплины":
            continue
        groups: list[list[str]] = [[]]
        for next_line in lines[idx + 1 : idx + 16]:
            low = next_line.casefold()
            if "шифр" in low or "образовательн" in low:
                break
            if re.fullmatch(r"\d+\)", next_line):
                if groups[-1]:
                    groups.append([])
                continue
            if len(next_line) > 4:
                groups[-1].append(next_line)
        values = [normalize_text(" ".join(group)) for group in groups if group]
        if values:
            return "; ".join(values)
    return ""


def _assessment_structure(text: str) -> list[dict[str, Any]]:
    result = []
    if re.search(r"текущ\w+\s+контрол\w+[^0-9]{0,40}60\s*%", text, re.IGNORECASE):
        result.append({"name": "Текущий контроль", "weightPercent": 60, "deadline": "", "criteria": ""})
    if re.search(r"промежуточн\w+\s+аттестаци\w+[^0-9]{0,40}40\s*%", text, re.IGNORECASE):
        result.append({"name": "Промежуточная аттестация", "weightPercent": 40, "deadline": "", "criteria": ""})
    return result


def extract_op(path: Path | None) -> dict[str, Any]:
    if not path:
        return {"path": "", "_extraction_error": "Фикстура ОП не найдена", "program": {}, "outcomes": [], "disciplines": []}
    doc = read_docx(path)
    text = doc.get("text", "")
    outcomes = []
    for match in re.finditer(r"\bРО\s*([0-9]+)\b[.:;\-\s]*(.{10,500})", text, re.IGNORECASE):
        outcomes.append({"code": f"РО{int(match.group(1))}", "text": normalize_text(match.group(2).split("\n")[0])})
    disciplines = []
    for table in doc.get("tables", []):
        for row in table:
            joined = " | ".join(row)
            if len(joined) < 20 or not re.search(r"кредит|РО\s*1|\+", joined, re.IGNORECASE):
                continue
            disciplines.append({"name": max(row, key=len), "raw": row, "programOutcomes": re.findall(r"РО\s*\d+", joined, re.IGNORECASE)})
    return {"path": str(path), "program": _program_from_text(text), "outcomes": outcomes, "disciplines": disciplines, "source": doc}


def extract_rup(path: Path | None) -> dict[str, Any]:
    if not path:
        return {"path": "", "_extraction_error": "Фикстура РУП не найдена", "disciplines": []}
    wb = read_xlsx(path)
    disciplines = []
    for sheet, rows in wb.get("sheets", {}).items():
        for row in rows:
            joined = " | ".join(row)
            if re.search(r"принц|диаг|леч|дых|серд", joined, re.IGNORECASE):
                disciplines.append({"sheet": sheet, "raw": row})
    wb["disciplines"] = disciplines
    return wb
