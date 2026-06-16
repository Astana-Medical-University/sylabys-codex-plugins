from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .common import inspect_docx_format, normalize_text, parse_first_number, read_docx, read_xlsx, stable_id


PROGRAM_CODE_RE = re.compile(r"\b\d[А-ЯA-Z]\d{5}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+\s*@\s*[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# ─────────────────────────────────────────────────────────────────────────
# Нормализация (ключевой фикс: ё→е, чтобы метки документа совпадали с кодом)
# ─────────────────────────────────────────────────────────────────────────


def _norm(value: str) -> str:
    """Приводит к нижнему регистру, нормализует ё→е и схлопывает пробелы."""
    return re.sub(r"\s+", " ", (value or "").casefold().replace("ё", "е")).strip()


def _label(value: str) -> str:
    """Нормализованная метка без хвоста «(часов)», «:» и т.п."""
    text = _norm(value)
    text = re.sub(r"\([^)]*\)", "", text)
    return text.strip(" :;.-")


def _program_from_text(text: str) -> dict[str, str]:
    code_match = PROGRAM_CODE_RE.search(text)
    name = ""
    name_match = re.search(r"«([^»]{2,80})»", text)
    if name_match:
        name = normalize_text(name_match.group(1))
    if not name:
        for candidate in ("Общая медицина", "Медицина", "Педиатрия", "Стоматология", "Фармация"):
            if candidate.casefold() in text.casefold():
                name = candidate
                break
    return {"code": code_match.group(0) if code_match else "", "name": name, "level": ""}


# ─────────────────────────────────────────────────────────────────────────
# Поиск таблиц по сигнатуре заголовка
# ─────────────────────────────────────────────────────────────────────────


def _header_index(table: list[list[str]], must_have: Iterable[str], limit: int = 4) -> int | None:
    """Возвращает индекс строки-заголовка, содержащей все подстроки must_have."""
    needles = [_norm(x) for x in must_have]
    for idx in range(min(limit, len(table))):
        joined = _norm(" ".join(table[idx]))
        if all(n in joined for n in needles):
            return idx
    return None


def _find_table(tables: list[list[list[str]]], must_have: Iterable[str], limit: int = 4) -> tuple[list[list[str]], int] | None:
    for table in tables:
        idx = _header_index(table, must_have, limit=limit)
        if idx is not None:
            return table, idx
    return None


def _columns(header: list[str], mapping: dict[str, Iterable[str]]) -> dict[str, int]:
    """mapping: имя_поля -> список подстрок-кандидатов. Первая совпавшая колонка выигрывает."""
    cols: dict[str, int] = {}
    norm_header = [_norm(c) for c in header]
    for field, needles in mapping.items():
        for col_idx, cell in enumerate(norm_header):
            if col_idx in cols.values():
                continue
            if any(n in cell for n in (_norm(x) for x in needles)):
                cols[field] = col_idx
                break
    return cols


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return normalize_text(row[idx])


def _number_cell(row: list[str], idx: int | None) -> float:
    value = _cell(row, idx)
    if value in {"-", "–", "—", ""}:
        return 0
    return parse_first_number(value) or 0


# ─────────────────────────────────────────────────────────────────────────
# Раздел 1: таблица «Показатель | Сведения»
# ─────────────────────────────────────────────────────────────────────────

# Метка раздела 1 -> (поле, как трактовать значение). Порядок важен: сроп до сро.
_DESC_LABELS: list[tuple[str, str]] = [
    ("наименование модуля", "moduleName"),
    ("наименование дисциплины", "disciplineName"),
    ("шифр и наименование образовательной программы", "program"),
    ("уровень образования", "level"),
    ("цикл и компонент", "cycleAndComponent"),
    ("период обучения", "studyPeriod"),
    ("количество академических кредитов", "credits"),
    ("общий объем дисциплины", "total"),
    ("объем лекций", "lecture"),
    ("объем практических занятий", "practical"),
    ("объем сроп", "srop"),
    ("объем сро", "sro"),
    ("объем практики на клинической базе", "clinicalBasePractice"),
    ("пререквизиты", "prerequisites"),
    ("постреквизиты", "postrequisites"),
]


def _match_desc_field(label: str) -> str | None:
    for needle, field in _DESC_LABELS:
        if field == "sro":
            # «объем сро» не должно цепляться за «объем сроп»
            if "объем сро" in label and "сроп" not in label:
                return field
            continue
        if needle in label:
            return field
    return None


def _parse_description_table(tables: list[list[list[str]]]) -> dict[str, Any]:
    found = _find_table(tables, ["показатель"], limit=2) or _find_table(tables, ["общий объем"], limit=20)
    raw: dict[str, str] = {}
    if not found:
        return raw
    table, _ = found
    for row in table:
        if len(row) < 2:
            continue
        field = _match_desc_field(_label(row[0]))
        if field and field not in raw:
            raw[field] = normalize_text(" ".join(row[1:]))
    return raw


def _split_list(value: str) -> list[str]:
    parts = re.split(r"[;,]|\sи\s", value)
    return [normalize_text(p) for p in parts if normalize_text(p) and normalize_text(p) not in {"-", "–", "—"}]


def _course_semester(value: str) -> tuple[int, str]:
    course = 0
    course_match = re.search(r"([1-7])\s*курс", value, re.IGNORECASE)
    if course_match:
        course = int(course_match.group(1))
    semester = ""
    sem_match = re.search(r"([1-9])\s*семестр", value, re.IGNORECASE)
    if sem_match:
        semester = sem_match.group(1)
    return course, semester


# ─────────────────────────────────────────────────────────────────────────
# Раздел 2: преподаватели
# ─────────────────────────────────────────────────────────────────────────


def _parse_teachers(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    found = _find_table(tables, ["должность"], limit=2)
    if not found:
        return []
    table, header_idx = found
    cols = _columns(
        table[header_idx],
        {
            "fullName": ["ф.и.о", "фио", "преподавател"],
            "position": ["должность"],
            "department": ["кафедра", "нии", "клиническая база"],
            "email": ["e-mail", "почта", "email"],
        },
    )
    if "fullName" not in cols:
        return []
    teachers = []
    for row in table[header_idx + 1 :]:
        full_name = _cell(row, cols.get("fullName"))
        if not full_name or _norm(full_name) in {"ф.и.о", "фио"}:
            continue
        teachers.append(
            {
                "fullName": full_name,
                "position": _cell(row, cols.get("position")),
                "departmentOrInstitute": {"name": _cell(row, cols.get("department"))},
                "email": _first_email(_cell(row, cols.get("email"))),
            }
        )
    return teachers


def _first_email(value: str) -> str:
    match = EMAIL_RE.search(value or "")
    return match.group(0).replace(" ", "") if match else normalize_text(value)


# ─────────────────────────────────────────────────────────────────────────
# Разделы 4-5: РО и ПН
# ─────────────────────────────────────────────────────────────────────────


def _parse_coded_table(
    tables: list[list[list[str]]],
    code_prefix: str,
    header_marks: list[str],
    code_marks: list[str],
    extra_cols: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    found = _find_table(tables, header_marks, limit=2)
    if not found:
        return []
    table, header_idx = found
    mapping = {"code": code_marks, "description": ["формулировк", "результат", "навык"]}
    if extra_cols:
        mapping.update(extra_cols)
    cols = _columns(table[header_idx], mapping)
    code_col = cols.get("code")
    desc_col = cols.get("description")
    if desc_col is None:
        return []
    out: dict[str, dict[str, Any]] = {}
    for row in table[header_idx + 1 :]:
        code = _normalize_code(_cell(row, code_col), code_prefix)
        desc = _cell(row, desc_col)
        if not code or not desc:
            continue
        entry: dict[str, Any] = {"code": code, "description": desc}
        if extra_cols:
            for field in extra_cols:
                entry[field] = _cell(row, cols.get(field))
        out.setdefault(code, entry)
    return [out[c] for c in sorted(out, key=_code_number)]


def _normalize_code(value: str, prefix: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    digits = re.search(r"\d+", value)
    if not digits:
        return ""
    return f"{prefix}{int(digits.group(0))}"


def _code_number(code: str) -> int:
    match = re.search(r"\d+", code or "")
    return int(match.group(0)) if match else 0


def _learning_outcomes(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    rows = _parse_coded_table(
        tables,
        "РО",
        header_marks=["код ро"],
        code_marks=["код ро", "ро"],
        extra_cols={"instruments": ["оценивание", "инструмент"]},
    )
    result = []
    for row in rows:
        instruments = [x for x in _split_list(row.get("instruments", "")) if x]
        result.append({"code": row["code"], "description": row["description"], "assessmentInstruments": instruments})
    return result


def _practical_skills(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    rows = _parse_coded_table(tables, "ПН", header_marks=["код пн"], code_marks=["код пн", "пн"])
    return [{"code": r["code"], "description": r["description"]} for r in rows]


def _synthesize_learning(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """РО из тематического плана, когда отдельной таблицы РО нет (комбинированный шаблон)."""
    seen: dict[str, dict[str, Any]] = {}
    for row in plan:
        code = row.get("learningOutcomeCode")
        if code and code not in seen:
            seen[code] = {"code": code, "description": row.get("learningOutcomeText", ""), "assessmentInstruments": []}
    return [seen[c] for c in sorted(seen, key=_code_number)]


def _synthesize_skills(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in plan:
        codes = row.get("practicalSkillCodes") or []
        text = row.get("practicalSkillText", "")
        for code in codes:
            if code not in seen:
                seen[code] = {"code": code, "description": text if len(codes) == 1 else ""}
    return [seen[c] for c in sorted(seen, key=_code_number)]


# ─────────────────────────────────────────────────────────────────────────
# Раздел 6: тематический план
# ─────────────────────────────────────────────────────────────────────────


def _extract_thematic_plan(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = 1
    for table in tables:
        header_idx, columns = _thematic_plan_columns(table)
        if header_idx is None:
            continue
        current_ro = ""
        current_topic = ""
        for row in table[header_idx:]:
            joined = " | ".join(row)
            if "итого" in joined.casefold():
                continue
            ro_value = _cell(row, columns.get("ro"))
            topic = _cell(row, columns.get("topic"))
            ro_code = _ro_from_cell(ro_value) or _ro_from_cell(joined)
            if ro_code:
                current_ro = ro_code
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
            assessment = _cell(row, columns.get("assessment"))
            rows.append(
                {
                    "order": order,
                    "learningOutcomeCode": current_ro,
                    "learningOutcomeText": _strip_code(_cell(row, columns.get("ro")), "РО"),
                    "practicalSkillCodes": _pn_codes_from_column(pn_value),
                    "practicalSkillText": _strip_code(pn_value, "ПН"),
                    "topic": topic or current_topic,
                    "hours": hours,
                    "teachingMethods": [_cell(row, columns.get("methods"))] if _cell(row, columns.get("methods")) else [],
                    "assessmentMethods": _split_list(assessment) if assessment else [],
                }
            )
            order += 1
    return rows


def _strip_code(value: str, prefix: str) -> str:
    """Убирает префикс кода («РО1», «ПН 2 (…)») и возвращает оставшийся текст."""
    text = re.sub(rf"^\s*{prefix}\s*\d+\s*[).:]?\s*", "", value or "", flags=re.IGNORECASE)
    return normalize_text(text)


def _ro_from_cell(value: str) -> str:
    """Код РО из ячейки тематического плана: «РО2» или голое «2» -> «РО2»."""
    if not value:
        return ""
    explicit = re.search(r"\bРО\s*(\d+)\b", value, re.IGNORECASE)
    if explicit:
        return f"РО{int(explicit.group(1))}"
    bare = re.fullmatch(r"\s*(\d{1,2})\s*", value)
    if bare:
        return f"РО{int(bare.group(1))}"
    return ""


def _pn_codes(value: str) -> list[str]:
    explicit = [f"ПН{int(m)}" for m in re.findall(r"\bПН\s*(\d+)\b", value or "", re.IGNORECASE)]
    return explicit


def _pn_codes_from_column(value: str) -> list[str]:
    """Коды ПН из колонки тематического плана: «ПН1, ПН2» или голые «1, 2» -> [ПН1, ПН2]."""
    explicit = _pn_codes(value)
    if explicit:
        return explicit
    return [f"ПН{int(m)}" for m in re.findall(r"\b(\d{1,2})\b", value or "")]


def _thematic_plan_columns(table: list[list[str]]) -> tuple[int | None, dict[str, int]]:
    # Вариант с двухстрочным заголовком: часы Л/ПЗ/СРОП/СРО вынесены в подстроку.
    for idx in range(min(4, max(0, len(table) - 1))):
        top = [_norm(c) for c in table[idx]]
        bottom = [_norm(c) for c in table[idx + 1]]
        if "тема" not in " ".join(top):
            continue
        joined_bottom = " ".join(bottom)
        if "сроп" not in joined_bottom or "сро" not in joined_bottom:
            continue
        cols: dict[str, int] = {}
        for ci, cell in enumerate(top):
            if "результат обучения" in cell or "код ро" in cell or cell == "ро":
                cols.setdefault("ro", ci)
            elif ("практическ" in cell and "навык" in cell) or "код пн" in cell or cell == "пн":
                cols.setdefault("pn", ci)
            elif "тема" in cell:
                cols.setdefault("topic", ci)
            elif ("метод" in cell and "оцен" in cell) or "оценочн" in cell or "оценивани" in cell:
                cols.setdefault("assessment", ci)
            elif "метод" in cell:
                cols.setdefault("methods", ci)
        for ci, cell in enumerate(bottom):
            if cell in {"л", "лекция", "лекции"} or "лекц" in cell:
                cols.setdefault("lecture", ci)
            elif cell == "пз" or "практич" in cell:
                cols.setdefault("practical", ci)
            elif cell == "сроп":
                cols.setdefault("srop", ci)
            elif cell == "сро":
                cols.setdefault("sro", ci)
        if {"ro", "topic", "lecture", "practical", "srop", "sro"}.issubset(cols):
            return idx + 2, cols
    for idx, row in enumerate(table[:5]):
        normalized = [_norm(cell) for cell in row]
        joined = " ".join(normalized)
        if "тема" not in joined or "сроп" not in joined or "сро" not in joined:
            continue
        columns: dict[str, int] = {}
        for col_idx, cell in enumerate(normalized):
            if "код ро" in cell or cell == "ро":
                columns.setdefault("ro", col_idx)
            elif "код" in cell and "пн" in cell or cell == "пн":
                columns.setdefault("pn", col_idx)
            elif "тема" in cell:
                columns.setdefault("topic", col_idx)
            elif cell in {"л", "лекция", "лекции"} or "лекц" in cell:
                columns.setdefault("lecture", col_idx)
            elif cell == "пз" or "практич" in cell:
                columns.setdefault("practical", col_idx)
            elif cell == "сроп":
                columns.setdefault("srop", col_idx)
            elif cell == "сро":
                columns.setdefault("sro", col_idx)
            elif "метод" in cell:
                columns.setdefault("methods", col_idx)
        required = {"ro", "topic", "lecture", "practical", "srop", "sro"}
        if required.issubset(columns):
            return idx + 1, columns
    return None, {}


# ─────────────────────────────────────────────────────────────────────────
# Раздел 9: структура оценивания (60/40)
# ─────────────────────────────────────────────────────────────────────────


def _assessment_structure(tables: list[list[list[str]]], text: str) -> list[dict[str, Any]]:
    found = _find_table(tables, ["компонент оценивания"], limit=2) or _find_table(tables, ["удельный вес"], limit=2)
    result: list[dict[str, Any]] = []
    if found:
        table, header_idx = found
        cols = _columns(
            table[header_idx],
            {"name": ["компонент"], "weight": ["удельный вес", "вес"], "deadline": ["срок"], "criteria": ["критери"]},
        )
        for row in table[header_idx + 1 :]:
            name = _cell(row, cols.get("name"))
            weight = _number_cell(row, cols.get("weight"))
            if not name or weight <= 0:
                continue
            kind = "Текущий контроль" if "текущ" in _norm(name) else ("Промежуточная аттестация" if "промежуточ" in _norm(name) else name)
            result.append({"name": kind, "weightPercent": weight, "deadline": _cell(row, cols.get("deadline")), "criteria": _cell(row, cols.get("criteria"))})
    if result:
        return result
    # Текстовый фолбэк
    if re.search(r"текущ\w+\s+контрол\w+[^0-9]{0,60}60\s*%?", text, re.IGNORECASE):
        result.append({"name": "Текущий контроль", "weightPercent": 60, "deadline": "", "criteria": ""})
    if re.search(r"промежуточн\w+\s+аттестаци\w+[^0-9]{0,60}40\s*%?", text, re.IGNORECASE):
        result.append({"name": "Промежуточная аттестация", "weightPercent": 40, "deadline": "", "criteria": ""})
    return result


# ─────────────────────────────────────────────────────────────────────────
# Раздел 11: глоссарий
# ─────────────────────────────────────────────────────────────────────────


def _parse_glossary(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    found = _find_table(tables, ["сокращение", "расшифровка"], limit=2)
    if not found:
        return []
    table, header_idx = found
    out = []
    for row in table[header_idx + 1 :]:
        if len(row) < 2:
            continue
        abbr = normalize_text(row[0])
        definition = normalize_text(" ".join(row[1:]))
        if abbr and definition:
            out.append({"abbreviation": abbr, "definition": definition})
    return out


# ─────────────────────────────────────────────────────────────────────────
# Приложение 1: КИС
# ─────────────────────────────────────────────────────────────────────────


def _parse_exam_questions(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    found = _find_table(tables, ["вопрос"], limit=2)
    if not found:
        return []
    table, header_idx = found
    cols = _columns(table[header_idx], {"number": ["№"], "text": ["вопрос"]})
    text_col = cols.get("text")
    if text_col is None:
        return []
    out = []
    for row in table[header_idx + 1 :]:
        question = _cell(row, text_col)
        if len(question) < 5:  # пустые шаблонные строки «1 | »
            continue
        out.append({"number": _number_cell(row, cols.get("number")) or len(out) + 1, "text": question})
    return out


# ─────────────────────────────────────────────────────────────────────────
# Раздел 7: график СРОП (консультации)
# ─────────────────────────────────────────────────────────────────────────


def _parse_time_range(value: str) -> tuple[str, str]:
    match = re.search(r"(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})", value or "")
    if match:
        return match.group(1).replace(".", ":"), match.group(2).replace(".", ":")
    return "", ""


def _parse_srop_schedule(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    found = _find_table(tables, ["день недели"], limit=3)
    if not found:
        return []
    table, header_idx = found
    cols = _columns(table[header_idx], {"teacher": ["ф.и.о", "фио", "преподавател"], "day": ["день недели"], "time": ["время"]})
    if "day" not in cols:
        return []
    out = []
    for row in table[header_idx + 1 :]:
        day = _cell(row, cols.get("day"))
        teacher = _cell(row, cols.get("teacher"))
        if not day and not teacher:
            continue
        time_from, time_to = _parse_time_range(_cell(row, cols.get("time")))
        out.append({"teacherName": teacher, "dayOfWeek": day, "timeFrom": time_from, "timeTo": time_to})
    return out


# ─────────────────────────────────────────────────────────────────────────
# Раздел 10: список литературы
# ─────────────────────────────────────────────────────────────────────────


def _parse_references(paragraphs: list[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    kind: str | None = None
    for para in paragraphs:
        low = _norm(para)
        if "основная литература" in low:
            kind = "main"
            continue
        if "дополнительная литература" in low:
            kind = "additional"
            continue
        if kind and (low.startswith(("11.", "12.")) or "глоссар" in low or "приложение" in low or "согласование" in low):
            kind = None
            continue
        if kind and re.match(r"^\d+[.)]", para.strip()):
            citation = re.sub(r"^\d+[.)]\s*", "", para.strip())
            placeholder = not re.sub(r"[_\s.№«»\"-]", "", citation)
            refs.append({"kind": kind, "citation": citation, "placeholder": placeholder})
    return refs


# ─────────────────────────────────────────────────────────────────────────
# Раздел 12: согласование / утверждение
# ─────────────────────────────────────────────────────────────────────────


def _filled(value: str) -> str:
    """Считает значение заполненным, только если это не шаблонный пропуск из подчёркиваний."""
    text = normalize_text(value)
    stripped = re.sub(r"[_\s.№«»\"-]", "", text)
    return text if stripped else ""


def _parse_approval(text: str) -> dict[str, Any]:
    protocol = ""
    proto_match = re.search(r"протокол\s*№\s*(\S+)", text, re.IGNORECASE)
    if proto_match:
        protocol = _filled(proto_match.group(1))
    protocol_date = ""
    date_match = re.search(r"протокол[^\n]{0,40}?(\d{1,2}[.\s][\d]{1,2}[.\s]\d{2,4})", text, re.IGNORECASE)
    if date_match:
        protocol_date = normalize_text(date_match.group(1))
    developers = []
    dev_match = re.search(r"разработчик\w*\s*:?\s*([^\n]{0,200})", text, re.IGNORECASE)
    if dev_match:
        value = _filled(dev_match.group(1))
        if value:
            developers = _split_list(value)
    return {
        "departmentProtocol": protocol,
        "protocolDate": protocol_date,
        "developers": developers,
        "agreedBy": [],
    }


# ─────────────────────────────────────────────────────────────────────────
# Текстовые фолбэки (используются, если таблиц нет) + back-compat для тестов
# ─────────────────────────────────────────────────────────────────────────


def _lines(text: str) -> list[str]:
    return [normalize_text(x) for x in text.splitlines() if normalize_text(x)]


def _slice_after(text: str, needle: str, limit: int) -> str:
    low = _norm(text)
    idx = low.find(_norm(needle))
    if idx < 0:
        return ""
    return normalize_text(text[idx : idx + limit])


def _extract_title(text: str) -> str:
    compact = "\n".join(_lines(text[:2500]))
    match = re.search(r"СИЛЛАБУС\s+(?:Модуль|Дисциплина)[^:]*:?\s*(.+?)\s*20\s*\d", compact, re.IGNORECASE | re.DOTALL)
    if match:
        return normalize_text(match.group(1))
    return ""


def _main_syllabus_text(text: str) -> str:
    match = re.search(r"\n\s*(?:Приложение\s*2|КАРТА\s+обеспеченности)\b", text, re.IGNORECASE)
    return text[: match.start()] if match else text


def _number_after_label(text: str, labels: list[str], *, allow_inline: bool = True) -> float:
    lines = _lines(text)
    label_set = [_norm(label) for label in labels]
    for idx, line in enumerate(lines):
        low = _label(line)
        if not any(_label_matches(low, label) for label in label_set):
            continue
        inline = re.sub("|".join(re.escape(label) for label in labels), "", line, flags=re.IGNORECASE).strip(" :-")
        if allow_inline:
            value = parse_first_number(inline)
            if value is not None:
                return value
        collected: list[str] = []
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


def _extract_hours(text: str) -> dict[str, float]:
    return {
        "total": _number_after_label(text, ["общий объем дисциплины", "общий объем"], allow_inline=False),
        "lecture": _number_after_label(text, ["объем лекций"], allow_inline=False),
        "practical": _number_after_label(text, ["объем практических занятий"], allow_inline=False),
        "srop": _number_after_label(text, ["объем сроп", "сроп"], allow_inline=False),
        "sro": _number_after_label(text, ["объем сро", "сро"], allow_inline=False),
        "clinicalBasePractice": _number_after_label(text, ["объем практики на клинической базе", "практики на клинической базе"], allow_inline=False),
    }


def _extract_course(text: str) -> int:
    main_text = _main_syllabus_text(text)
    period_match = re.search(r"период\s+обучения.{0,120}?\b([1-7])\s*курс\b", main_text, re.IGNORECASE | re.DOTALL)
    if period_match:
        return int(period_match.group(1))
    lines = _lines(text)
    for idx, line in enumerate(lines):
        low = _norm(line)
        if "карта обеспеченности" in low or "всего контингент" in low:
            break
        inline_match = re.fullmatch(r"курс\s*[:\-]?\s*([1-7])(?:\D.*)?", low)
        if inline_match:
            return int(inline_match.group(1))
        if low.strip(" :;") != "курс":
            continue
        for next_line in lines[idx + 1 : idx + 3]:
            value = parse_first_number(next_line)
            if value is not None and 1 <= value <= 7 and float(value).is_integer():
                return int(value)
    return 0


def _extract_credits(text: str, syllabus_type: str) -> float:
    main_text = _main_syllabus_text(text)
    top_level = _number_after_label(main_text, ["количество кредитов"], allow_inline=True)
    if top_level:
        return top_level
    if syllabus_type == "module":
        return 0
    return _number_after_label(main_text, ["количество академических кредитов", "количество кредитов"], allow_inline=False)


# ─────────────────────────────────────────────────────────────────────────
# Сборка модели силлабуса
# ─────────────────────────────────────────────────────────────────────────


def _build_syllabus(doc: dict[str, Any], path: Path) -> dict[str, Any]:
    text = doc.get("text", "")
    tables = doc.get("tables", [])
    desc = _parse_description_table(tables)

    title = _extract_title(text) or path.stem
    academic_year = ""
    year_match = re.search(r"20\d{2}\s*[-–]\s*20\d{2}", text)
    if year_match:
        academic_year = year_match.group(0).replace(" ", "").replace("–", "-")

    module_name = desc.get("moduleName", "")
    syllabus_type = "module" if module_name or re.search(r"\bмодул", title + "\n" + text[:1500], re.IGNORECASE) else "discipline"

    discipline_name = desc.get("disciplineName") or _extract_discipline_name(text) or title
    program = _program_from_text(desc.get("program", "")) if desc.get("program") else _program_from_text(text)

    course, semester = _course_semester(desc.get("studyPeriod", "")) if desc.get("studyPeriod") else (_extract_course(text), "")

    if "credits" in desc:
        credits = parse_first_number(desc["credits"]) or 0
    else:
        credits = _extract_credits(text, syllabus_type)

    if any(k in desc for k in ("total", "lecture", "practical", "srop", "sro")):
        hours = {
            "total": parse_first_number(desc.get("total", "")) or 0,
            "lecture": parse_first_number(desc.get("lecture", "")) or 0,
            "practical": parse_first_number(desc.get("practical", "")) or 0,
            "srop": parse_first_number(desc.get("srop", "")) or 0,
            "sro": parse_first_number(desc.get("sro", "")) or 0,
            "clinicalBasePractice": parse_first_number(desc.get("clinicalBasePractice", "")) or 0,
        }
    else:
        hours = _extract_hours(text)

    teachers = _parse_teachers(tables)
    learning = _learning_outcomes(tables)
    skills = _practical_skills(tables)
    plan = _extract_thematic_plan(tables)
    if not learning:  # комбинированный шаблон: РО/ПН встроены в тематический план
        learning = _synthesize_learning(plan)
    if not skills:
        skills = _synthesize_skills(plan)
    glossary = _parse_glossary(tables)
    questions = _parse_exam_questions(tables)
    structure = _assessment_structure(tables, text)
    approval = _parse_approval(text)
    srop_schedule = _parse_srop_schedule(tables)
    references = _parse_references(doc.get("paragraphs", []))

    now = datetime.now(timezone.utc).isoformat()
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
                "moduleName": module_name,
                "disciplineName": discipline_name,
                "program": program,
                "cycleAndComponent": desc.get("cycleAndComponent", ""),
                "studyPeriod": {"course": course, "semester": semester},
                "credits": {"academic": credits, "ects": credits},
                "hours": hours,
                "formsOfClasses": [],
                "prerequisites": _split_list(desc.get("prerequisites", "")),
                "postrequisites": _split_list(desc.get("postrequisites", "")),
            }
        ],
        "teachers": teachers,
        "aimAndSummary": {
            "aim": _slice_after(text, "цель дисциплины", 500) or _slice_after(text, "цель", 500),
            "shortSummary": _slice_after(text, "краткое содержание", 700),
        },
        "disciplineBlocks": [
            {
                "disciplineName": discipline_name,
                "learningOutcomes": learning,
                "practicalSkills": skills,
                "thematicPlan": plan,
            }
        ],
        "sropSchedule": srop_schedule,
        "policy": {},
        "assessments": [
            {
                "disciplineName": discipline_name,
                "structure": structure,
                "currentControl": {},
                "intermediateAttestation": {"maxScore": 100},
                "redFlags": [],
                "admissionRatingFormula": _slice_after(text, "оценка рейтинга допуска", 250),
                "finalGradeFormula": _extract_final_formula(text),
            }
        ],
        "references": references,
        "glossary": glossary,
        "examMaterials": {"questions": questions},
        "resourceCard": {},
        "approval": approval,
        "source": doc,
        "format": inspect_docx_format(path),
        "version": "0.2.0",
        "createdAt": now,
        "updatedAt": now,
    }


def _extract_final_formula(text: str) -> str:
    match = re.search(r"ИО\s*=\s*[^\n]{3,80}", text)
    return normalize_text(match.group(0)) if match else _slice_after(text, "итоговая оценка", 250)


def _extract_discipline_name(text: str) -> str:
    lines = _lines(text)
    for idx, line in enumerate(lines):
        if _norm(line) != "наименование дисциплины":
            continue
        for next_line in lines[idx + 1 : idx + 4]:
            if len(next_line) > 4 and "шифр" not in _norm(next_line):
                return normalize_text(next_line)
    return ""


def extract_syllabus(path: Path) -> dict[str, Any]:
    return _build_syllabus(read_docx(path), path)


# ─────────────────────────────────────────────────────────────────────────
# Таргетированный извлекатель ОП: только строка нужной дисциплины
# ─────────────────────────────────────────────────────────────────────────


def _similar_name(a: str, b: str) -> bool:
    stop = {"дисциплины", "дисциплина", "силлабус", "модуль", "модуля", "система", "системы"}
    aw = {x for x in re.findall(r"[а-яa-z]{4,}", _norm(a)) if x not in stop}
    bw = {x for x in re.findall(r"[а-яa-z]{4,}", _norm(b)) if x not in stop}
    if not aw or not bw:
        return False
    overlap = len(aw & bw)
    return overlap >= max(2, min(3, len(aw) // 2))


def _op_ro_columns(table: list[list[str]], header_idx: int) -> dict[int, str]:
    """Колонка -> код программного РО, считанные из строки-подзаголовка матрицы."""
    for row in table[header_idx : header_idx + 3]:
        codes = {idx: _normalize_code(cell, "РО") for idx, cell in enumerate(row) if re.fullmatch(r"\s*РО\s*\d+\s*", cell, re.IGNORECASE)}
        if codes:
            return codes
    return {}


def _build_op(doc: dict[str, Any], target_names: list[str]) -> dict[str, Any]:
    if doc.get("_extraction_error"):
        return {"path": doc.get("path", ""), "_extraction_error": f"ОП не прочитан: {doc['_extraction_error']}", "program": {}, "outcomes": [], "disciplines": [], "matchedDiscipline": {}}
    text = doc.get("text", "")
    tables = doc.get("tables", [])
    program = _program_from_text(text)

    found = _find_table(tables, ["наименование модул", "цикл", "кредиты"], limit=3) or _find_table(tables, ["краткое описание дисциплины"], limit=3)
    discipline_row: dict[str, Any] = {}
    program_outcomes: list[str] = []
    if found:
        table, header_idx = found
        cols = _columns(
            table[header_idx],
            {"name": ["наименование модул", "наименование дисциплины", "наименование"], "summary": ["краткое описание"], "cycle": ["цикл"], "component": ["компонент"], "credits": ["кредит"]},
        )
        ro_cols = _op_ro_columns(table, header_idx)
        name_col = cols.get("name", 1)
        best = None
        for row in table[header_idx + 1 :]:
            name = _cell(row, name_col)
            if len(name) < 6:
                continue
            if any(_similar_name(t, name) for t in target_names if t):
                best = row
                break
        if best is not None:
            matrix = sorted({code for idx, code in ro_cols.items() if idx < len(best) and best[idx].strip() in {"+", "✓"}}, key=_code_number)
            program_outcomes = matrix
            discipline_row = {
                "name": _cell(best, name_col),
                "summary": _cell(best, cols.get("summary")),
                "cycle": _cell(best, cols.get("cycle")),
                "component": _cell(best, cols.get("component")),
                "credits": _number_cell(best, cols.get("credits")),
                "programOutcomes": matrix,
            }

    outcomes = _op_program_outcomes(tables, text)
    return {
        "path": doc.get("path", ""),
        "program": program,
        "targetNames": [t for t in target_names if t],
        "matchedDiscipline": discipline_row,
        "programOutcomes": program_outcomes,
        "outcomes": outcomes,
        "disciplines": [discipline_row] if discipline_row else [],
        "source": doc,
    }


def _op_program_outcomes(tables: list[list[list[str]]], text: str) -> list[dict[str, str]]:
    """Формулировки программных РО1..РО10 из ОП (для строгого diff OP-007)."""
    out: dict[str, str] = {}
    for match in re.finditer(r"\b(РО\s*\d+)\b\s*[–\-:.]?\s*([А-ЯA-Z][^\n]{15,400})", text):
        code = _normalize_code(match.group(1), "РО")
        if code:
            out.setdefault(code, normalize_text(match.group(2)))
    return [{"code": c, "text": out[c]} for c in sorted(out, key=_code_number)]


def extract_op(path: Path | None, target_names: list[str] | None = None) -> dict[str, Any]:
    if not path:
        return {"path": "", "_extraction_error": "Фикстура ОП не найдена", "program": {}, "outcomes": [], "disciplines": [], "matchedDiscipline": {}}
    return _build_op(read_docx(path), target_names or [])


# ─────────────────────────────────────────────────────────────────────────
# Таргетированный извлекатель РУП: только строки нужной дисциплины
# ─────────────────────────────────────────────────────────────────────────


def _rup_course_from_sheet(name: str) -> int:
    match = re.search(r"([1-7])\s*курс", name, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _rup_columns(header: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for ci, cell in enumerate(header):
        n = _norm(cell)
        if "наименование" in n and "модул" in n:
            cols.setdefault("module", ci)
        elif "наименование" in n and "дисциплин" in n:
            cols.setdefault("discipline", ci)
        elif "кафедр" in n:
            cols.setdefault("department", ci)
        elif "форма контроля" in n or "бакылау тури" in n:
            cols.setdefault("control", ci)
        elif "ects" in n:
            cols.setdefault("ects", ci)
        elif "кредит" in n:
            cols.setdefault("credits", ci)
        elif "всего часов" in n or "барлык сагат" in n:
            cols.setdefault("total", ci)
        elif "клин" in n and "практик" in n:
            cols.setdefault("clinicalBasePractice", ci)
        elif "лекци" in n or "дарист" in n:
            cols.setdefault("lecture", ci)
        elif "практик" in n and "навык" not in n:
            cols.setdefault("practical", ci)
        elif "сроп" in n or "обож" in n:
            cols.setdefault("srop", ci)
        elif "результат" in n and "обуч" in n:
            cols.setdefault("programOutcomes", ci)
    if "sro" not in cols:
        for ci, cell in enumerate(header):
            n = _norm(cell)
            if "сро" in n and "сроп" not in n and "обож" not in n and ci not in cols.values():
                cols["sro"] = ci
                break
    return cols


def _rup_ro_codes(value: str) -> list[str]:
    return [f"РО{int(x)}" for x in re.findall(r"\d+", value or "")]


def _build_rup(wb: dict[str, Any], target_names: list[str]) -> dict[str, Any]:
    if wb.get("_extraction_error"):
        return {"path": wb.get("path", ""), "_extraction_error": f"РУП не прочитан: {wb['_extraction_error']}", "disciplines": []}
    targets = [t for t in target_names if t]
    disciplines: list[dict[str, Any]] = []
    for sheet, rows in wb.get("sheets", {}).items():
        if "курс" not in _norm(sheet):  # пропускаем сводные листы, считаем по курсовым
            continue
        course = _rup_course_from_sheet(sheet)
        header_idx, cols = None, {}
        for i, row in enumerate(rows[:30]):
            joined = _norm(" ".join(row))
            if "наименование" in joined and "кредит" in joined:
                cols = _rup_columns(row)
                if "discipline" in cols and "credits" in cols:
                    header_idx = i
                    break
        if header_idx is None:
            continue
        last_module = ""
        for row in rows[header_idx + 1 :]:
            raw_module = _cell(row, cols.get("module"))
            if raw_module:
                last_module = raw_module
            module = raw_module or last_module
            discipline = _cell(row, cols.get("discipline"))
            if not discipline:
                continue
            if not any(_similar_name(t, module) or _similar_name(t, discipline) for t in targets):
                continue
            disciplines.append(
                {
                    "sheet": sheet,
                    "course": course,
                    "module": module,
                    "discipline": discipline,
                    "department": _cell(row, cols.get("department")),
                    "controlForm": _cell(row, cols.get("control")),
                    "credits": _number_cell(row, cols.get("credits")),
                    "ects": _number_cell(row, cols.get("ects")),
                    "hours": {
                        "total": _number_cell(row, cols.get("total")),
                        "lecture": _number_cell(row, cols.get("lecture")),
                        "practical": _number_cell(row, cols.get("practical")),
                        "srop": _number_cell(row, cols.get("srop")),
                        "sro": _number_cell(row, cols.get("sro")),
                        "clinicalBasePractice": _number_cell(row, cols.get("clinicalBasePractice")),
                    },
                    "programOutcomes": _rup_ro_codes(_cell(row, cols.get("programOutcomes"))),
                    "raw": row,
                }
            )
    wb["disciplines"] = disciplines
    wb["targetNames"] = targets
    return wb


def extract_rup(path: Path | None, target_names: list[str] | None = None) -> dict[str, Any]:
    if not path:
        return {"path": "", "_extraction_error": "Фикстура РУП не найдена", "disciplines": []}
    return _build_rup(read_xlsx(path), target_names or [])
