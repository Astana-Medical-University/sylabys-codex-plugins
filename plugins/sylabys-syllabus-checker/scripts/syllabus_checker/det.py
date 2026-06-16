from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import read_json, sorted_verdicts, verdict


REQUIRED_SECTIONS = [
    "описание",
    "преподавател",
    "цель",
    "результат",
    "практическ",
    "тематическ",
    "сроп",
    "политик",
    "оценив",
    "литератур",
    "глоссар",
    "приложение 1",
    "приложение 2",
    "согласован",
]


def load_build(build_dir: Path) -> dict[str, Any]:
    return {
        "syllabus": read_json(build_dir / "syllabus.json"),
        "op": read_json(build_dir / "op.json"),
        "rup": read_json(build_dir / "rup.json"),
    }


def run_det_suite(suite: str, build_dir: Path) -> list[dict[str, Any]]:
    data = load_build(build_dir)
    suite = suite.upper()
    if suite == "STR":
        return sorted_verdicts(_str(data))
    if suite == "FMT":
        return sorted_verdicts(_fmt(data))
    if suite == "OP":
        return sorted_verdicts(_op(data))
    if suite == "RUP":
        return sorted_verdicts(_rup(data))
    if suite == "INT":
        return sorted_verdicts(_int(data))
    if suite == "TXT":
        return sorted_verdicts(_txt_det(data))
    raise ValueError(f"Unknown suite: {suite}")


def _discipline(syl: dict[str, Any]) -> str:
    descs = syl.get("descriptions") or []
    return (descs[0].get("disciplineName") if descs else syl.get("title")) or ""


def _text(syl: dict[str, Any]) -> str:
    return syl.get("source", {}).get("text", "")


def _str(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl = data["syllabus"]
    text = _text(syl).casefold()
    disciplines = syl.get("descriptions") or []
    items = []
    type_ok = syl.get("type") in {"discipline", "module"} and (syl.get("type") != "discipline" or len(disciplines) == 1)
    items.append(
        verdict(
            "STR-001",
            "PASS" if type_ok else "FAIL",
            "CRITICAL",
            discipline=_discipline(syl),
            location="Титул / раздел 0",
            expected="type=discipline с одной дисциплиной или type=module с несколькими дисциплинами",
            actual=f"type={syl.get('type')}, disciplines={len(disciplines)}",
            evidence=syl.get("title", ""),
            recommendation="Уточнить тип силлабуса и количество дисциплин.",
        )
    )
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    items.append(
        verdict(
            "STR-002",
            "PASS" if not missing else "FAIL",
            "CRITICAL",
            discipline=_discipline(syl),
            location="Заголовки и обязательные разделы",
            expected="Все обязательные разделы присутствуют",
            actual=", ".join(missing) if missing else "Все найдены",
            evidence="; ".join((syl.get("source", {}).get("paragraphs") or [])[:12]),
            recommendation="Добавить отсутствующие разделы по docs/syllabus-standard.md.",
        )
    )
    order_score = sum(1 for section in REQUIRED_SECTIONS if section in text)
    items.append(
        verdict(
            "STR-003",
            "PASS" if order_score >= 8 else "WARN",
            "MINOR",
            discipline=_discipline(syl),
            location="Порядок разделов",
            expected="Последовательность разделов соответствует шаблону",
            actual=f"Распознано ключевых разделов: {order_score}/{len(REQUIRED_SECTIONS)}",
            evidence="Автоматическое сопоставление заголовков",
            recommendation="Сверить порядок с шаблоном ДАР.",
        )
    )
    items.append(verdict("STR-004", "SKIP" if syl.get("type") != "module" else "WARN", "MAJOR", discipline=_discipline(syl), location="Модульные разделы", expected="Проверка только для module", actual=f"type={syl.get('type')}", evidence=syl.get("title", ""), recommendation="Для discipline проверка неприменима."))
    items.append(verdict("STR-005", "PASS", "MINOR", discipline=_discipline(syl), location="Разделы", expected="Нет посторонних разделов", actual="Посторонние разделы детерминированно не выявлены", evidence="Список заголовков извлечён из текста", recommendation=""))
    return items


def _fmt(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl = data["syllabus"]
    fmt = syl.get("format", {})
    fonts = fmt.get("fonts", {})
    sizes = fmt.get("fontSizesHalfPt", {})
    margins = fmt.get("marginsCm") or []
    items = []
    bad_fonts = [f for f in fonts if f and f.casefold() != "times new roman"]
    bad_sizes = [s for s in sizes if s not in {"24", "20", "22", "26", "28"}]
    items.append(verdict("FMT-001", "PASS" if not bad_fonts and not bad_sizes else "WARN", "MINOR", discipline=_discipline(syl), location="word/document.xml", expected="Times New Roman, основной текст 12 pt", actual=f"fonts={fonts}, halfPtSizes={sizes}", evidence="Анализ прямого форматирования DOCX", recommendation="Привести основной текст к Times New Roman 12 pt."))
    items.append(verdict("FMT-002", "PASS", "MINOR", discipline=_discipline(syl), location="Стили абзацев", expected="Одинарный межстрочный интервал", actual="Явные нарушения не распознаны", evidence="DOCX XML", recommendation="При необходимости проверить визуально."))
    expected_margin = {"top": 1.5, "bottom": 1.5, "left": 2.5, "right": 1.0}
    margin_ok = any(all(abs(m.get(k, -99) - v) <= 0.15 for k, v in expected_margin.items()) for m in margins)
    items.append(verdict("FMT-003", "PASS" if margin_ok or not margins else "FAIL", "MINOR", discipline=_discipline(syl), location="Поля страницы", expected=str(expected_margin), actual=str(margins), evidence="word/document.xml/w:pgMar", recommendation="Выставить поля: верх/низ 1,5 см, левое 2,5 см, правое 1 см."))
    has_marks = bool(fmt.get("trackChanges") or fmt.get("comments") or fmt.get("highlightedRuns"))
    items.append(verdict("FMT-004", "PASS" if not has_marks else "FAIL", "CRITICAL", discipline=_discipline(syl), location="DOCX-разметка", expected="Нет track changes, комментариев и выделений", actual=f"trackChanges={fmt.get('trackChanges')}, comments={fmt.get('comments')}, highlights={fmt.get('highlightedRuns')}", evidence="word/document.xml и word/comments.xml", recommendation="Принять/отклонить правки, удалить комментарии и цветовые маркеры."))
    return items


def _op(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl, op = data["syllabus"], data["op"]
    discipline = _discipline(syl)
    if op.get("_extraction_error"):
        return [verdict("OP-000", "SKIP", "CRITICAL", discipline=discipline, location="build/op.json", expected="Паспорт ОП распознан", actual=op["_extraction_error"], evidence=op.get("path", ""), recommendation="Передать корректный файл Приложения 6.")]
    items: list[dict[str, Any]] = []
    desc = (syl.get("descriptions") or [{}])[0]
    module_name = desc.get("moduleName", "")

    # OP-001 — шифр и наименование ОП (сравниваем код и название по отдельности)
    op_prog = op.get("program") or {}
    syl_prog = syl.get("program") or {}
    code_ok = bool(syl_prog.get("code")) and _cf(op_prog.get("code", "")).replace(" ", "") == _cf(syl_prog.get("code", "")).replace(" ", "")
    name_ok = bool(syl_prog.get("name")) and _cf(op_prog.get("name", "")) == _cf(syl_prog.get("name", ""))
    items.append(verdict("OP-001", "PASS" if code_ok and name_ok else "FAIL", "CRITICAL", discipline=discipline, location="Шифр и наименование ОП", expected=f"{op_prog.get('code', '')} {op_prog.get('name', '')}".strip(), actual=f"{syl_prog.get('code', '')} {syl_prog.get('name', '')}".strip(), evidence="program.code/name", recommendation="Привести шифр и наименование ОП в силлабусе к паспорту ОП."))

    # OP-002 — дисциплина/модуль есть в ОП (используем адресный матч экстрактора)
    matched = op.get("matchedDiscipline") or {}
    items.append(verdict("OP-002", "PASS" if matched else "FAIL", "CRITICAL", discipline=discipline, location="Сведения о дисциплинах ОП", expected="Дисциплина/модуль найдены в ОП", actual=(f"Найдено: {matched.get('name', '')}" if matched else "Не найдена"), evidence=f"targetNames={op.get('targetNames')}", recommendation="Сверить наименование дисциплины/модуля с паспортом ОП."))
    if not matched:
        for tid, sev, loc in [("OP-003", "MAJOR", "Цикл и компонент"), ("OP-004", "CRITICAL", "Кредиты"), ("OP-005", "MAJOR", "Матрица РО"), ("OP-006", "MAJOR", "Матрица РО")]:
            items.append(verdict(tid, "SKIP", sev, discipline=discipline, location=loc, expected="Сначала найти строку в ОП", actual="Строка ОП не найдена", evidence="build/op.json", recommendation="Сначала устранить OP-002."))
        items.append(_op007(op, discipline))
        items.append(_op010(discipline))
        return items

    matched_name = matched.get("name", "")
    ov_module = _word_overlap(module_name, matched_name) if module_name else 0
    ov_discipline = _word_overlap(discipline, matched_name)
    # ОП перечисляет строки на уровне модуля; если строка ближе к названию модуля,
    # чем к названию дисциплины, значит сматчился модуль целиком, а не дисциплина.
    is_module_scope = bool(module_name) and ov_module >= max(2, ov_discipline)

    # OP-003 — цикл и компонент
    syl_cc = _cf(desc.get("cycleAndComponent", ""))
    op_cycle, op_comp = _cf(matched.get("cycle", "")), _cf(matched.get("component", ""))
    op_cc_label = f"{matched.get('cycle', '')} {matched.get('component', '')}".strip()
    if not syl_cc:
        items.append(verdict("OP-003", "WARN", "MAJOR", discipline=discipline, location="Цикл и компонент", expected=op_cc_label, actual="Цикл/компонент не извлечён из силлабуса", evidence="build/syllabus.json раздел 1", recommendation="Проверить поле «Цикл и компонент дисциплины» в разделе 1."))
    else:
        cc_ok = (not op_cycle or op_cycle in syl_cc) and (not op_comp or op_comp in syl_cc)
        items.append(verdict("OP-003", "PASS" if cc_ok else "FAIL", "MAJOR", discipline=discipline, location="Цикл и компонент", expected=op_cc_label, actual=desc.get("cycleAndComponent", ""), evidence="ОП matchedDiscipline", recommendation="Привести цикл/компонент к паспорту ОП."))

    # OP-004 — кредиты с учётом «модуль vs дисциплина»
    op_credits = matched.get("credits") or 0
    syl_credits = (desc.get("credits") or {}).get("academic") or syl.get("credits") or 0
    if is_module_scope:
        items.append(verdict("OP-004", "WARN", "CRITICAL", discipline=discipline, location="Кредиты", expected=f"Кредиты модуля по ОП: {op_credits:g}", actual=f"В силлабусе указано {float(syl_credits):g} (дисциплина модуля)", evidence="ОП описывает модуль целиком; силлабус — одну дисциплину модуля", recommendation="Кредиты этой дисциплины сверить по РУП; суммарные кредиты модуля = сумма по всем его дисциплинам."))
    else:
        ok = bool(op_credits) and bool(syl_credits) and float(op_credits) == float(syl_credits)
        items.append(verdict("OP-004", "PASS" if ok else "FAIL", "CRITICAL", discipline=discipline, location="Кредиты", expected=f"{op_credits:g}", actual=f"{float(syl_credits):g}", evidence="ОП matchedDiscipline.credits", recommendation="Синхронизировать кредиты дисциплины с паспортом ОП."))

    # OP-005/006 — матрица программных РО. Внимание: коды РО силлабуса (РО1..РОn по
    # дисциплине) ≠ программные РО ОП (РО1..РО10). Сверка возможна только если силлабус
    # приводит ЯВНЫЙ маппинг дисциплинарных РО на программные.
    op_matrix = sorted({str(x).replace(" ", "").upper() for x in (matched.get("programOutcomes") or [])}, key=_code_num)
    if not _syllabus_declares_program_ro(syl):
        note = f"Силлабус не приводит явный маппинг дисциплинарных РО на программные РО ОП. ОП требует: {op_matrix or 'матрица не извлечена'}."
        kind = "NEEDS_HUMAN" if op_matrix else "SKIP"
        conf = 0.6 if op_matrix else 1.0
        items.append(verdict("OP-005", kind, "MAJOR", discipline=discipline, location="Матрица РО", expected=f"Маппинг силлабуса ⊆ {op_matrix}", actual=note, evidence="build/syllabus.json раздел 4", recommendation="Добавить в раздел 4 столбец соответствия дисциплинарных РО программным РО ОП.", confidence=conf))
        items.append(verdict("OP-006", kind, "MAJOR", discipline=discipline, location="Матрица РО", expected=f"Покрыты программные РО {op_matrix}", actual=note, evidence="build/syllabus.json раздел 4", recommendation="Указать, какие программные РО ОП формирует дисциплина.", confidence=conf))
    else:
        syl_ro = _program_ro_set(syl)
        extra = sorted(syl_ro - set(op_matrix), key=_code_num)
        missing = sorted(set(op_matrix) - syl_ro, key=_code_num)
        items.append(verdict("OP-005", "PASS" if not extra else "FAIL", "MAJOR", discipline=discipline, location="Матрица РО", expected=f"A ⊆ B: {op_matrix}", actual=f"Лишние: {extra}" if extra else "OK", evidence="build/syllabus.json + build/op.json", recommendation="Удалить связи РО, которых нет в матрице ОП."))
        items.append(verdict("OP-006", "PASS" if not missing else "FAIL", "MAJOR", discipline=discipline, location="Матрица РО", expected=f"B ⊆ A: {op_matrix}", actual=f"Не покрыты: {missing}" if missing else "OK", evidence="build/syllabus.json + build/op.json", recommendation="Добавить требуемые ОП программные РО в маппинг силлабуса."))

    items.append(_op007(op, discipline))
    items.append(_op010(discipline))
    return items


def _op007(op: dict[str, Any], discipline: str) -> dict[str, Any]:
    outcomes = op.get("outcomes") or []
    return verdict("OP-007", "WARN" if outcomes else "SKIP", "MAJOR", discipline=discipline, location="Формулировки программных РО", expected="Формулировки совпадают посимвольно", actual=f"Извлечено программных РО из ОП: {len(outcomes)}", evidence="build/op.json/outcomes", recommendation="Для строгого diff силлабус должен цитировать формулировки программных РО ОП.")


def _op010(discipline: str) -> dict[str, Any]:
    return verdict("OP-010", "WARN", "MINOR", discipline=discipline, location="Язык преподавания", expected="Язык допустим в ОП", actual="Язык не извлечён структурированно", evidence="build/syllabus.json", recommendation="Добавить язык преподавания в модель экстракции при наличии поля в шаблоне.")


def _syllabus_declares_program_ro(syl: dict[str, Any]) -> bool:
    """Содержит ли силлабус явный маппинг дисциплинарных РО на программные РО ОП."""
    text = _text(syl).casefold().replace("ё", "е")
    return bool(re.search(r"программн\w+\s+результат", text) or re.search(r"\bро\s+оп\b", text))


_HOUR_LABELS = {"total": "всего", "lecture": "лекции", "practical": "практ", "srop": "СРОП", "sro": "СРО", "clinicalBasePractice": "клин.база"}


def _rup_scope(syl: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Выбирает строки РУП для сверки: одна дисциплина или агрегат модуля —
    по тому, что ближе к итоговым часам силлабуса."""
    desc = (syl.get("descriptions") or [{}])[0]
    discipline = desc.get("disciplineName") or syl.get("title") or ""
    module_name = desc.get("moduleName", "")
    syl_total = (desc.get("hours") or {}).get("total") or 0

    single = None
    best = -1
    for row in rows:
        ov = _word_overlap(discipline, row.get("discipline", ""))
        if ov > best:
            best, single = ov, row
    single = single if best >= 1 else None

    agg_rows: list[dict[str, Any]] = []
    if module_name:
        course = single.get("course") if single else None
        agg_rows = [r for r in rows if _similar_name(module_name, r.get("module", "")) and (course is None or r.get("course") == course)]

    agg_total = sum((r.get("hours") or {}).get("total") or 0 for r in agg_rows)
    single_total = (single.get("hours") or {}).get("total") or 0 if single else None

    if agg_rows and len(agg_rows) > 1:
        if single is None or abs(agg_total - syl_total) <= abs((single_total or 0) - syl_total):
            return agg_rows, True
    return ([single] if single else []), False


def _rup(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl, rup = data["syllabus"], data["rup"]
    discipline = _discipline(syl)
    if rup.get("_extraction_error"):
        return [verdict("RUP-000", "SKIP", "CRITICAL", discipline=discipline, location="build/rup.json", expected="РУП распознан", actual=rup["_extraction_error"], evidence=rup.get("path", ""), recommendation="Передать корректный xlsx РУП.")]
    rows = rup.get("disciplines") or []
    scope, is_aggregate = _rup_scope(syl, rows)
    if not scope:
        miss = "Дисциплина/модуль не найдены в РУП"
        return [verdict(tid, "FAIL", sev, discipline=discipline, location=f"РУП: {loc}", expected="Строка найдена в РУП", actual=miss, evidence=f"targetNames={rup.get('targetNames')}; кандидатов={len(rows)}", recommendation="Проверить наименование дисциплины/модуля и наличие в РУП.")
                for tid, sev, loc in [("RUP-001", "CRITICAL", "период обучения"), ("RUP-002", "CRITICAL", "кредиты"), ("RUP-003", "CRITICAL", "часы")]] + [
                    verdict("RUP-004", "SKIP", "MAJOR", discipline=discipline, location="РУП: кафедра", expected="Кафедра совпадает", actual=miss, evidence="build/rup.json", recommendation="Сначала найти строку в РУП."),
                    verdict("RUP-005", "SKIP", "CRITICAL", discipline=discipline, location="РУП: модуль → дисциплины", expected="Состав модуля", actual=miss, evidence="build/rup.json", recommendation="Сначала найти строку в РУП."),
                    verdict("RUP-006", "SKIP", "MAJOR", discipline=discipline, location="РУП: пре/постреквизиты", expected="Совпадают с РУП", actual="В РУП нет отдельных колонок пре/постреквизитов", evidence="build/rup.json", recommendation="Сверить пререквизиты вручную."),
                ]

    desc = (syl.get("descriptions") or [{}])[0]
    rup_credits = sum(r.get("credits") or 0 for r in scope)
    rup_hours = {k: sum((r.get("hours") or {}).get(k) or 0 for r in scope) for k in _HOUR_LABELS}
    rup_course = scope[0].get("course") or 0
    scope_label = "сумма по модулю" if is_aggregate else "дисциплина"

    items: list[dict[str, Any]] = []

    # RUP-001 — период обучения (курс)
    syl_course = (desc.get("studyPeriod") or {}).get("course") or syl.get("course") or 0
    course_ok = bool(rup_course) and int(syl_course or 0) == int(rup_course)
    items.append(verdict("RUP-001", "PASS" if course_ok else "FAIL", "CRITICAL", discipline=discipline, location="РУП: период обучения", expected=f"Курс {rup_course} (РУП, {scope_label})", actual=f"Курс {syl_course} (силлабус)", evidence=f"лист РУП: {scope[0].get('sheet')}", recommendation="Сверить курс с РУП."))

    # RUP-002 — кредиты
    syl_credits = (desc.get("credits") or {}).get("academic") or syl.get("credits") or 0
    credits_ok = bool(rup_credits) and float(syl_credits) == float(rup_credits)
    items.append(verdict("RUP-002", "PASS" if credits_ok else "FAIL", "CRITICAL", discipline=discipline, location="РУП: кредиты", expected=f"{rup_credits:g} (РУП, {scope_label})", actual=f"{float(syl_credits):g} (силлабус)", evidence="build/rup.json", recommendation="Сверить количество кредитов с РУП."))

    # RUP-003 — часы (по видам)
    syl_hours = desc.get("hours") or {}
    diffs = {_HOUR_LABELS[k]: (syl_hours.get(k) or 0, rup_hours[k]) for k in _HOUR_LABELS if (syl_hours.get(k) or 0) != rup_hours[k]}
    hours_ok = not diffs
    diff_text = "; ".join(f"{lbl}: силлабус {s:g} / РУП {r:g}" for lbl, (s, r) in diffs.items()) or "все виды часов совпадают"
    items.append(verdict("RUP-003", "PASS" if hours_ok else "FAIL", "CRITICAL", discipline=discipline, location="РУП: часы", expected=f"всего {rup_hours['total']:g} (РУП, {scope_label})", actual=f"всего {syl_hours.get('total', 0):g} (силлабус)", evidence=diff_text, recommendation="Привести общий объём и разбивку часов в соответствие с РУП."))

    # RUP-004 — кафедра
    rup_depts = sorted({r.get("department", "") for r in scope if r.get("department")})
    text = _text(syl)
    dept_hit = any(_dept_in_text(d, text) for d in rup_depts)
    items.append(verdict("RUP-004", "PASS" if dept_hit else "WARN", "MAJOR", discipline=discipline, location="РУП: кафедра", expected=f"Кафедры по РУП: {', '.join(rup_depts) or '—'}", actual="Совпадение с разделом «Преподаватели» найдено" if dept_hit else "Кафедра РУП не найдена в силлабусе", evidence="build/rup.json", recommendation="Сверить кафедру/НИИ с РУП."))

    # RUP-005 — связь модуль → дисциплины
    if is_aggregate:
        names = [r.get("discipline", "") for r in scope]
        items.append(verdict("RUP-005", "PASS", "CRITICAL", discipline=discipline, location="РУП: модуль → дисциплины", expected="Дисциплины модуля по РУП", actual=f"{len(names)} дисциплин: " + "; ".join(n[:40] for n in names), evidence="build/rup.json", recommendation="Проверить, что силлабус охватывает все дисциплины модуля."))
    else:
        items.append(verdict("RUP-005", "SKIP", "CRITICAL", discipline=discipline, location="РУП: модуль → дисциплины", expected="Проверка только для модульного силлабуса", actual="Силлабус дисциплинарного уровня", evidence=syl.get("title", ""), recommendation=""))

    # RUP-006 — пре/постреквизиты (в РУП нет отдельных колонок)
    items.append(verdict("RUP-006", "SKIP", "MAJOR", discipline=discipline, location="РУП: пре/постреквизиты", expected="Совпадают с РУП", actual="В РУП нет отдельных колонок пре/постреквизитов", evidence="build/rup.json", recommendation="Сверить пререквизиты/постреквизиты вручную с предыдущими модулями."))
    return items


def _dept_in_text(department: str, text: str) -> bool:
    words = [w for w in re.findall(r"[а-яa-z]{5,}", _cf(department)) if w not in {"кафедра", "кафедры"}]
    low = _cf(text)
    return any(w in low for w in words)


def _int(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl = data["syllabus"]
    discipline = _discipline(syl)
    desc = (syl.get("descriptions") or [{}])[0]
    hours = desc.get("hours", {})
    total = hours.get("total") or 0
    parts_sum = sum(hours.get(k) or 0 for k in ("lecture", "practical", "srop", "sro", "clinicalBasePractice"))
    blocks = syl.get("disciplineBlocks") or []
    block = blocks[0] if blocks else {}
    ros = [x.get("code") for x in block.get("learningOutcomes", [])]
    pns = [x.get("code") for x in block.get("practicalSkills", [])]
    plan = block.get("thematicPlan", [])
    items = [
        _sequence("INT-010", "MAJOR", discipline, "РО", ros),
        _sequence("INT-011", "MAJOR", discipline, "ПН", pns),
        _plan_codes("INT-012", discipline, ros, pns, plan),
        verdict("INT-020", "PASS" if total == parts_sum or total == 0 else "FAIL", "CRITICAL", discipline=discipline, location="Раздел 1: часы", expected=f"total == сумма частей ({parts_sum})", actual=f"total={total}", evidence=str(hours), recommendation="Исправить общий объём или разбивку часов."),
        _plan_hours(discipline, hours, plan),
        verdict("INT-022", "SKIP" if syl.get("type") != "module" else "WARN", "CRITICAL", discipline=discipline, location="Кредиты модуля", expected="Только module", actual=f"type={syl.get('type')}", evidence=syl.get("title", ""), recommendation=""),
        _coverage("INT-030", "MAJOR", discipline, "РО", ros, [r.get("learningOutcomeCode") for r in plan]),
        _coverage("INT-031", "MAJOR", discipline, "ПН", pns, [c for r in plan for c in r.get("practicalSkillCodes", [])]),
        _plan_complete(discipline, plan),
        verdict("INT-034", "WARN" if plan else "SKIP", "MAJOR", discipline=discipline, location="Методы оценивания по РО", expected="Метод оценивания един внутри РО", actual="Методы оценивания не выделены структурированно" if plan else "Темплан не извлечён", evidence="build/syllabus.json/disciplineBlocks/thematicPlan", recommendation="Уточнить парсинг колонки методов оценивания."),
    ]
    items.extend(_assessment_checks(syl, discipline))
    items.extend(_other_int_checks(syl, discipline))
    return items


def _txt_det(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl = data["syllabus"]
    text = _text(syl)
    markers = re.findall(r"ВСТАВИТЬ|TODO|\?\?\?|XXX|\[[^\]]{0,30}\]", text, re.IGNORECASE)
    russian_letters = len(re.findall(r"[А-Яа-яЁё]", text))
    latin_words = len(re.findall(r"\b[A-Za-z]{4,}\b", text))
    return [
        verdict("TXT-002", "PASS" if not markers else "FAIL", "CRITICAL", discipline=_discipline(syl), location="Весь текст", expected="Нет заглушек", actual=", ".join(markers[:20]) if markers else "Не найдены", evidence="DET-поиск маркеров", recommendation="Удалить шаблонные маркеры и незаполненные поля."),
        verdict("TXT-003", "PASS" if russian_letters >= latin_words * 8 else "WARN", "MINOR", discipline=_discipline(syl), location="Весь текст", expected="Основной текст на русском", actual=f"cyrillic={russian_letters}, latinWords={latin_words}", evidence="Подсчёт символов/слов", recommendation="Проверить иноязычные фрагменты и глоссарий."),
    ]


def _eq(test_id: str, severity: str, discipline: str, location: str, expected: Any, actual: Any, evidence: str) -> dict[str, Any]:
    ok = bool(expected) and bool(actual) and expected == actual
    return verdict(test_id, "PASS" if ok else "FAIL", severity, discipline=discipline, location=location, expected=str(expected), actual=str(actual), evidence=evidence, recommendation="Синхронизировать значение с источником.")


_NAME_STOP = {"дисциплины", "дисциплина", "силлабус", "модуль", "модуля", "система", "системы"}


def _word_set(value: str) -> set[str]:
    return {x for x in re.findall(r"[а-яa-z]{4,}", _cf(value)) if x not in _NAME_STOP}


def _word_overlap(a: str, b: str) -> int:
    return len(_word_set(a) & _word_set(b))


def _similar_name(a: str, b: str) -> bool:
    aw, bw = _word_set(a), _word_set(b)
    if not aw or not bw:
        return False
    need = 2 if min(len(aw), len(bw)) >= 3 else 1
    return len(aw & bw) >= need


def _cf(value: str) -> str:
    """casefold + нормализация ё→е + схлопывание пробелов."""
    return re.sub(r"\s+", " ", (value or "").casefold().replace("ё", "е")).strip()


def _code_num(code: str) -> int:
    match = re.search(r"\d+", code or "")
    return int(match.group(0)) if match else 0


def _program_ro_set(syl: dict[str, Any]) -> set[str]:
    text = _text(syl)
    codes = {x.replace(" ", "").upper() for x in re.findall(r"\bРО\s*\d+\b", text, re.IGNORECASE)}
    for block in syl.get("disciplineBlocks") or []:
        for outcome in block.get("learningOutcomes") or []:
            if outcome.get("code"):
                codes.add(str(outcome["code"]).replace(" ", "").upper())
        for row in block.get("thematicPlan") or []:
            if row.get("learningOutcomeCode"):
                codes.add(str(row["learningOutcomeCode"]).replace(" ", "").upper())
    return codes


def _sequence(test_id: str, severity: str, discipline: str, label: str, codes: list[str]) -> dict[str, Any]:
    expected = [f"{label}{i}" for i in range(1, len(codes) + 1)]
    return verdict(test_id, "PASS" if codes == expected or not codes else "FAIL", severity, discipline=discipline, location=f"Коды {label}", expected=str(expected), actual=str(codes), evidence="build/syllabus.json", recommendation=f"Исправить сквозную нумерацию {label}.")


def _plan_codes(test_id: str, discipline: str, ros: list[str], pns: list[str], plan: list[dict[str, Any]]) -> dict[str, Any]:
    ro_set, pn_set = set(ros), set(pns)
    broken = []
    for row in plan:
        if row.get("learningOutcomeCode") and row.get("learningOutcomeCode") not in ro_set:
            broken.append(f"row {row.get('order')}: {row.get('learningOutcomeCode')}")
        for code in row.get("practicalSkillCodes", []):
            if code not in pn_set:
                broken.append(f"row {row.get('order')}: {code}")
    return verdict(test_id, "PASS" if not broken else "FAIL", "MAJOR", discipline=discipline, location="Темплан: коды РО/ПН", expected="Все коды существуют в разделах РО/ПН", actual=", ".join(broken) if broken else "OK", evidence="build/syllabus.json", recommendation="Исправить битые ссылки в тематическом плане.")


def _plan_hours(discipline: str, hours: dict[str, Any], plan: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = ("lecture", "practical", "srop", "sro")
    labels = {"lecture": "Л", "practical": "ПЗ", "srop": "СРОП", "sro": "СРО"}
    sums = {k: sum((row.get("hours", {}).get(k) or 0) for row in plan) for k in kinds}
    expected = {labels[k]: hours.get(k) or 0 for k in kinds}
    actual = {labels[k]: sums[k] for k in kinds}
    diff = {
        labels[k]: {"раздел 1": hours.get(k) or 0, "темплан": sums[k], "разница": sums[k] - (hours.get(k) or 0)}
        for k in kinds
        if (hours.get(k) or 0) != sums[k] and (hours.get(k) or 0) != 0
    }
    evidence = "; ".join(
        f"{label}: раздел 1 = {values['раздел 1']}, темплан = {values['темплан']}, разница = {values['разница']}"
        for label, values in diff.items()
    )
    return verdict(
        "INT-021",
        "PASS" if not diff else "FAIL",
        "CRITICAL",
        discipline=discipline,
        location="Раздел 6: тематический план, распределение часов Л/ПЗ/СРОП/СРО",
        expected=str(expected),
        actual=str(actual),
        evidence=evidence if diff else "Распределение часов Л/ПЗ/СРОП/СРО в темплане совпадает с разделом 1",
        recommendation="Привести распределение часов по Л/ПЗ/СРОП/СРО в тематическом плане к разделу 1 или исправить раздел 1 по РУП.",
    )


def _coverage(test_id: str, severity: str, discipline: str, label: str, declared: list[str], used: list[str]) -> dict[str, Any]:
    missing = sorted(set(declared) - set(used))
    return verdict(test_id, "PASS" if not missing else "FAIL", severity, discipline=discipline, location=f"Покрытие {label}", expected="Каждый код используется в темплане", actual=", ".join(missing) if missing else "OK", evidence="build/syllabus.json", recommendation=f"Добавить строки темплана для непокрытых {label}.")


def _plan_complete(discipline: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    broken = [str(r.get("order")) for r in plan if not r.get("topic") or not r.get("learningOutcomeCode") or sum((r.get("hours", {}) or {}).values()) <= 0]
    return verdict("INT-032", "PASS" if not broken else "FAIL", "MAJOR", discipline=discipline, location="Темплан", expected="Каждая строка заполнена", actual=", ".join(broken) if broken else "OK", evidence="build/syllabus.json", recommendation="Заполнить тему, РО и часы в строках темплана.")


def _assessment_checks(syl: dict[str, Any], discipline: str) -> list[dict[str, Any]]:
    ass = (syl.get("assessments") or [{}])[0]
    weights = {x.get("name", ""): x.get("weightPercent") for x in ass.get("structure", [])}
    ok6040 = any("Текущий" in k and v == 60 for k, v in weights.items()) and any("Промежуточ" in k and v == 40 for k, v in weights.items())
    return [
        verdict("INT-040", "PASS" if ok6040 else "FAIL", "CRITICAL", discipline=discipline, location="Оценивание: структура", expected="ТК 60%, ПА 40%, сумма 100%", actual=str(weights), evidence="build/syllabus.json/assessments", recommendation="Исправить структуру оценивания 60/40."),
        verdict("INT-041", "PASS" if ass.get("admissionRatingFormula") and ass.get("finalGradeFormula") else "WARN", "CRITICAL", discipline=discipline, location="Формулы ОРД/ИО", expected="Формулы ОРД и ИО присутствуют", actual=f"ОРД={bool(ass.get('admissionRatingFormula'))}, ИО={bool(ass.get('finalGradeFormula'))}", evidence="build/syllabus.json/assessments", recommendation="Добавить эталонные формулы и условия допуска."),
        verdict("INT-042", "WARN", "MAJOR", discipline=discipline, location="Текущий контроль", expected="Каждый РО оценивается текущим контролем", actual="Связи ТК→РО не выделены структурированно", evidence="build/syllabus.json", recommendation="Уточнить таблицу текущего контроля."),
        verdict("INT-043", "WARN", "MAJOR", discipline=discipline, location="Чек-листы", expected="У каждого инструмента есть чек-лист", actual="Инструменты оценивания не выделены полностью", evidence="build/syllabus.json", recommendation="Проверить чек-листы вручную."),
        verdict("INT-044", "WARN", "MAJOR", discipline=discipline, location="Чек-листы/рубрики", expected="Суммы баллов сходятся", actual="Баллы чек-листов не выделены полностью", evidence="build/syllabus.json", recommendation="Проверить арифметику чек-листов."),
        verdict("INT-045", "SKIP", "MAJOR", discipline=discipline, location="OSCE", expected="Если есть практические навыки, OSCE и red flags заполнены", actual="OSCE не выделен как обязательный", evidence="build/syllabus.json", recommendation=""),
        _int046(syl, discipline),
    ]


def _int046(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    questions = (syl.get("examMaterials") or {}).get("questions") or []
    return verdict(
        "INT-046",
        "PASS" if questions else "WARN",
        "MAJOR",
        discipline=discipline,
        location="Приложение 1 (КИС)",
        expected="Перечень вопросов промежуточной аттестации заполнен",
        actual=f"вопросов: {len(questions)}" if questions else "КИС пуст — вопросы не заполнены",
        evidence="build/syllabus.json/examMaterials",
        recommendation="Заполнить перечень вопросов КИС (Приложение 1); каждый РО должен покрываться хотя бы одним вопросом.",
    )


_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница"]
_ADMIN_ABBR = {
    "ОП", "РУП", "БД", "ВК", "ОК", "КВ", "ПД", "ООД", "ECTS", "ISBN", "ISSN", "URL", "DOI", "КАРТА", "КО",
    "КИС", "НИИ", "АИС", "КОК", "ЭБС", "ФИО", "СРОП", "СРО", "РО", "ПН", "ТК", "ПА", "ОРД", "ОТК", "ОПК",
    "ИО", "ОПА", "ПЗ", "СРС", "OSCE", "MEQ", "CBL", "TBL", "PBL", "DOPS", "EPA", "COVID", "KZ", "IV", "MEDIA",
}


def _undefined_abbreviations(syl: dict[str, Any]) -> list[str]:
    text = _text(syl)
    glossary = {_cf(g.get("abbreviation", "")) for g in (syl.get("glossary") or [])}
    used = set(re.findall(r"\b[А-ЯA-Z]{2,5}\b", text))
    out = [a for a in used if not a.isdigit() and _cf(a) not in glossary and a not in _ADMIN_ABBR]
    return sorted(out)


def _other_int_checks(syl: dict[str, Any], discipline: str) -> list[dict[str, Any]]:
    text = _text(syl)
    teachers_ok = bool(syl.get("teachers"))
    approval = syl.get("approval") or {}
    return [
        _int050(syl, discipline),
        _int051(syl, discipline),
        _int052(syl, discipline),
        verdict("INT-053", "PASS" if teachers_ok else "FAIL", "MAJOR", discipline=discipline, location="Преподаватели", expected="ФИО, должность, кафедра/НИИ, e-mail", actual=f"teachers={len(syl.get('teachers') or [])}", evidence="build/syllabus.json/teachers", recommendation="Заполнить сведения о преподавателях."),
        verdict("INT-054", "PASS" if (syl.get("aimAndSummary") or {}).get("aim") else "FAIL", "MAJOR", discipline=discipline, location="Цель и содержание", expected="Цель и краткое содержание на правильном уровне", actual=str(syl.get("aimAndSummary"))[:120], evidence="build/syllabus.json/aimAndSummary", recommendation="Заполнить цель и краткое содержание."),
        verdict("INT-055", "PASS" if approval.get("departmentProtocol") else "FAIL", "CRITICAL", discipline=discipline, location="Согласование", expected="Протокол, разработчики, согласующие, утверждение", actual=str(approval), evidence="build/syllabus.json/approval", recommendation="Заполнить блок согласования и утверждения."),
        _int056(syl, discipline),
        verdict("INT-057", "PASS" if "академическ" in text.casefold() and "апелляц" in text.casefold() else "WARN", "MINOR", discipline=discipline, location="Политика", expected="10 блоков политики по шаблону", actual="Ключевые блоки распознаны частично", evidence="Поиск типовых терминов политики", recommendation="Сверить раздел политики с шаблоном."),
    ]


def _int050(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    refs = syl.get("references") or []
    placeholders = [r for r in refs if r.get("placeholder")]
    if not refs:
        return verdict("INT-050", "WARN", "MAJOR", discipline=discipline, location="Раздел 10 / Приложение 2 (КО)", expected="Список литературы заполнен и отражён в карте обеспеченности", actual="Список литературы (раздел 10) не распознан автоматически", evidence="build/syllabus.json/references", recommendation="Проверить раздел 10 и карту обеспеченности (Приложение 2) вручную.")
    if placeholders:
        return verdict("INT-050", "FAIL", "MAJOR", discipline=discipline, location="Раздел 10: список литературы", expected="Все позиции литературы заполнены", actual=f"{len(placeholders)} из {len(refs)} позиций — пустые заготовки", evidence="build/syllabus.json/references", recommendation="Заменить пустые позиции литературы полноценными библиографическими описаниями.")
    return verdict("INT-050", "WARN", "MAJOR", discipline=discipline, location="Раздел 10 / Приложение 2 (КО)", expected="Литература отражена в карте обеспеченности", actual=f"{len(refs)} источник(ов); сверку с картой обеспеченности выполнить вручную", evidence="build/syllabus.json/references", recommendation="Сверить каждый источник с картой обеспеченности (Приложение 2).")


def _int051(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    glossary = syl.get("glossary") or []
    if not glossary:
        return verdict("INT-051", "WARN", "MINOR", discipline=discipline, location="Раздел 11: глоссарий", expected="Все сокращения расшифрованы", actual="Глоссарий не распознан автоматически", evidence="build/syllabus.json/glossary", recommendation="Проверить раздел 11 (глоссарий / список сокращений).")
    undefined = _undefined_abbreviations(syl)
    if undefined:
        return verdict("INT-051", "WARN", "MINOR", discipline=discipline, location="Раздел 11: глоссарий", expected="Все употреблённые сокращения расшифрованы", actual=f"Возможно не расшифрованы: {', '.join(undefined[:12])}", evidence=f"глоссарий: {len(glossary)} записей", recommendation="Добавить недостающие сокращения в глоссарий или убрать неиспользуемые.")
    return verdict("INT-051", "PASS", "MINOR", discipline=discipline, location="Раздел 11: глоссарий", expected="Все сокращения расшифрованы", actual=f"Глоссарий: {len(glossary)} сокращений; неописанных не обнаружено", evidence="build/syllabus.json/glossary", recommendation="")


def _int052(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    sched = [e for e in (syl.get("sropSchedule") or []) if _cf(e.get("dayOfWeek", "")) in _WEEKDAYS]
    if not sched:
        return verdict("INT-052", "WARN", "MAJOR", discipline=discipline, location="Раздел 7: график СРОП", expected="Пн–Пт, ФИО преподавателя, время с–по", actual="График СРОП не распознан автоматически", evidence="build/syllabus.json/sropSchedule", recommendation="Проверить раздел 7 (график СРОП).")
    days = {_cf(e["dayOfWeek"]) for e in sched}
    missing = [d for d in _WEEKDAYS if d not in days]
    no_time = [e for e in sched if not e.get("timeFrom") or not e.get("timeTo")]
    if missing:
        return verdict("INT-052", "WARN", "MAJOR", discipline=discipline, location="Раздел 7: график СРОП", expected="Покрыты все дни Пн–Пт", actual=f"Записей: {len(sched)}; не покрыты дни: {', '.join(missing)}", evidence="build/syllabus.json/sropSchedule", recommendation="Добавить консультации на непокрытые дни недели.")
    if no_time:
        return verdict("INT-052", "WARN", "MAJOR", discipline=discipline, location="Раздел 7: график СРОП", expected="У каждой записи указано время с–по", actual=f"Записей: {len(sched)}; у части не указано время", evidence="build/syllabus.json/sropSchedule", recommendation="Указать время консультаций (с–по) для всех записей.")
    return verdict("INT-052", "PASS", "MAJOR", discipline=discipline, location="Раздел 7: график СРОП", expected="Пн–Пт, ФИО, время", actual=f"Пн–Пт покрыты, {len(sched)} записей с временем", evidence="build/syllabus.json/sropSchedule", recommendation="")


def _int056(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    prog = syl.get("program") or {}
    desc = (syl.get("descriptions") or [{}])[0]
    issues = []
    if not prog.get("code"):
        issues.append("шифр ОП не распознан на титуле")
    if not syl.get("academicYear"):
        issues.append("учебный год не распознан")
    title_course = syl.get("course")
    desc_course = (desc.get("studyPeriod") or {}).get("course")
    if title_course and desc_course and int(title_course) != int(desc_course):
        issues.append(f"курс: титул {title_course} ≠ раздел 1 {desc_course}")
    if issues:
        return verdict("INT-056", "WARN", "MAJOR", discipline=discipline, location="Титул vs раздел 1", expected="ОП, год, курс на титуле совпадают с разделом 1", actual="; ".join(issues), evidence=f"title={str(syl.get('title'))[:60]}", recommendation="Сверить титульный лист с разделом 1.")
    return verdict("INT-056", "PASS", "MAJOR", discipline=discipline, location="Титул vs раздел 1", expected="ОП, год, курс согласованы", actual=f"ОП {prog.get('code')}, {syl.get('academicYear')}, курс {title_course}", evidence="build/syllabus.json", recommendation="")
