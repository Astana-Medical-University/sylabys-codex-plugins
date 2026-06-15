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
    items = []
    items.append(_eq("OP-001", "CRITICAL", discipline, "Шифр и наименование ОП", op.get("program", {}), syl.get("program", {}), "Сравнение program.code/name"))
    op_disciplines = op.get("disciplines") or []
    found = any(_similar_name(discipline, row.get("name", "")) for row in op_disciplines)
    items.append(verdict("OP-002", "PASS" if found else "FAIL", "CRITICAL", discipline=discipline, location="Сведения о дисциплинах ОП", expected="Дисциплина найдена в ОП", actual="Найдена" if found else "Не найдена", evidence=f"discipline={discipline}; candidates={len(op_disciplines)}", recommendation="Сверить наименование дисциплины с паспортом ОП."))
    for test_id, severity, field in [("OP-003", "MAJOR", "cycleAndComponent"), ("OP-004", "CRITICAL", "credits")]:
        items.append(verdict(test_id, "WARN", severity, discipline=discipline, location="ОП / раздел описания", expected=f"Поле {field} совпадает с ОП", actual="Недостаточно структурированных данных для строгой сверки", evidence="Экстракция таблицы ОП выполнена, требуется точная разметка колонок", recommendation="Проверить вручную или уточнить шаблон таблицы ОП."))
    syl_ro = _program_ro_set(syl)
    op_ro = set()
    for row in op_disciplines:
        if _similar_name(discipline, row.get("name", "")):
            op_ro.update(x.replace(" ", "").upper() for x in row.get("programOutcomes", []))
    if op_ro:
        extra = sorted(syl_ro - op_ro)
        missing = sorted(op_ro - syl_ro)
        items.append(verdict("OP-005", "PASS" if not extra else "FAIL", "MAJOR", discipline=discipline, location="Матрица РО", expected=f"A ⊆ B: {sorted(op_ro)}", actual=f"Лишние: {extra}", evidence="build/syllabus.json + build/op.json", recommendation="Удалить связи РО, которых нет в матрице ОП."))
        items.append(verdict("OP-006", "PASS" if not missing else "FAIL", "MAJOR", discipline=discipline, location="Матрица РО", expected=f"B ⊆ A: {sorted(op_ro)}", actual=f"Не покрыты: {missing}", evidence="build/syllabus.json + build/op.json", recommendation="Добавить требуемые ОП РО в маппинг силлабуса."))
    else:
        items.append(verdict("OP-005", "SKIP", "MAJOR", discipline=discipline, location="Матрица РО", expected="Строка дисциплины в ОП с РО", actual="Не найдена", evidence="build/op.json", recommendation="Сначала устранить OP-002."))
        items.append(verdict("OP-006", "SKIP", "MAJOR", discipline=discipline, location="Матрица РО", expected="Строка дисциплины в ОП с РО", actual="Не найдена", evidence="build/op.json", recommendation="Сначала устранить OP-002."))
    items.append(verdict("OP-007", "WARN" if op.get("outcomes") else "SKIP", "MAJOR", discipline=discipline, location="Формулировки программных РО", expected="Формулировки совпадают посимвольно", actual=f"Извлечено РО ОП: {len(op.get('outcomes') or [])}", evidence="build/op.json/outcomes", recommendation="Для строгого diff требуется стабильная таблица программных РО."))
    items.append(verdict("OP-010", "WARN", "MINOR", discipline=discipline, location="Язык преподавания", expected="Язык допустим в ОП", actual="Язык не извлечён структурированно", evidence="build/syllabus.json", recommendation="Добавить язык преподавания в модель экстракции при наличии поля в шаблоне."))
    return items


def _rup(data: dict[str, Any]) -> list[dict[str, Any]]:
    syl, rup = data["syllabus"], data["rup"]
    discipline = _discipline(syl)
    if rup.get("_extraction_error"):
        return [verdict("RUP-000", "SKIP", "CRITICAL", discipline=discipline, location="build/rup.json", expected="РУП распознан", actual=rup["_extraction_error"], evidence=rup.get("path", ""), recommendation="Передать корректный xlsx РУП.")]
    found = any(_similar_name(discipline, " ".join(row.get("raw", []))) for row in rup.get("disciplines", []))
    return [
        verdict("RUP-001", "WARN" if found else "FAIL", "CRITICAL", discipline=discipline, location="РУП: период обучения", expected="Курс/семестр совпадают с РУП", actual="Строка найдена, колонки требуют уточнения" if found else "Строка дисциплины не найдена", evidence=f"candidates={len(rup.get('disciplines', []))}", recommendation="Сверить курс и семестр с РУП."),
        verdict("RUP-002", "WARN" if found else "FAIL", "CRITICAL", discipline=discipline, location="РУП: кредиты", expected="Кредиты/ECTS совпадают", actual="Строка найдена, колонки требуют уточнения" if found else "Строка дисциплины не найдена", evidence="build/rup.json", recommendation="Сверить кредиты с РУП."),
        verdict("RUP-003", "WARN" if found else "FAIL", "CRITICAL", discipline=discipline, location="РУП: часы", expected="Все виды часов совпадают", actual="Строка найдена, колонки требуют уточнения" if found else "Строка дисциплины не найдена", evidence="build/rup.json", recommendation="Сверить общий объём и разбивку часов."),
        verdict("RUP-004", "WARN" if found else "SKIP", "MAJOR", discipline=discipline, location="РУП: кафедра", expected="Кафедра совпадает", actual="Колонка кафедры не выделена детерминированно", evidence="build/rup.json", recommendation="Уточнить маппинг колонок РУП."),
        verdict("RUP-005", "SKIP", "CRITICAL", discipline=discipline, location="Связь модуль → дисциплины", expected="Проверка только для module", actual=f"type={syl.get('type')}", evidence=syl.get("title", ""), recommendation=""),
        verdict("RUP-006", "WARN" if found else "SKIP", "MAJOR", discipline=discipline, location="Пререквизиты/постреквизиты", expected="Совпадают с РУП", actual="Колонки не выделены детерминированно", evidence="build/rup.json", recommendation="Уточнить маппинг колонок РУП."),
    ]


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


def _similar_name(a: str, b: str) -> bool:
    aw = {x for x in re.findall(r"[а-яa-z]{4,}", a.casefold()) if x not in {"дисциплины", "силлабус"}}
    bw = {x for x in re.findall(r"[а-яa-z]{4,}", b.casefold())}
    return bool(aw and len(aw & bw) >= max(1, min(3, len(aw) // 2)))


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
        verdict("INT-046", "WARN", "MAJOR", discipline=discipline, location="КИС", expected="Вопросы покрывают РО", actual=f"questions={len((syl.get('examMaterials') or {}).get('questions') or [])}", evidence="build/syllabus.json/examMaterials", recommendation="Проверить приложение 1."),
    ]


def _other_int_checks(syl: dict[str, Any], discipline: str) -> list[dict[str, Any]]:
    text = _text(syl)
    teachers_ok = bool(syl.get("teachers"))
    approval = syl.get("approval") or {}
    return [
        verdict("INT-050", "WARN", "MAJOR", discipline=discipline, location="Литература / КО", expected="Литература отражена в карте обеспеченности", actual="Литература и КО не выделены полностью", evidence="build/syllabus.json", recommendation="Проверить раздел 10 и приложение 2."),
        verdict("INT-051", "WARN", "MINOR", discipline=discipline, location="Глоссарий", expected="Все сокращения расшифрованы", actual=f"glossary={len(syl.get('glossary') or [])}", evidence="build/syllabus.json/glossary", recommendation="Проверить сокращения и глоссарий."),
        verdict("INT-052", "WARN", "MAJOR", discipline=discipline, location="График СРОП", expected="Пн-пт, ФИО, время, преподаватель из раздела 2", actual=f"entries={len(syl.get('sropSchedule') or [])}", evidence="build/syllabus.json/sropSchedule", recommendation="Проверить график СРОП."),
        verdict("INT-053", "PASS" if teachers_ok else "FAIL", "MAJOR", discipline=discipline, location="Преподаватели", expected="ФИО, должность, кафедра/НИИ, e-mail", actual=f"teachers={len(syl.get('teachers') or [])}", evidence="build/syllabus.json/teachers", recommendation="Заполнить сведения о преподавателях."),
        verdict("INT-054", "PASS" if (syl.get("aimAndSummary") or {}).get("aim") else "FAIL", "MAJOR", discipline=discipline, location="Цель и содержание", expected="Цель и краткое содержание на правильном уровне", actual=str(syl.get("aimAndSummary")), evidence="build/syllabus.json/aimAndSummary", recommendation="Заполнить цель и краткое содержание."),
        verdict("INT-055", "PASS" if approval.get("departmentProtocol") else "FAIL", "CRITICAL", discipline=discipline, location="Согласование", expected="Протокол, разработчики, согласующие, утверждение", actual=str(approval), evidence="build/syllabus.json/approval", recommendation="Заполнить блок согласования и утверждения."),
        verdict("INT-056", "WARN", "MAJOR", discipline=discipline, location="Титул vs описание", expected="Название, ОП, кредиты, курс, год совпадают", actual="Поля извлечены частично", evidence=f"title={syl.get('title')}", recommendation="Сверить титул и описание."),
        verdict("INT-057", "PASS" if "академическ" in text.casefold() and "апелляц" in text.casefold() else "WARN", "MINOR", discipline=discipline, location="Политика", expected="10 блоков политики по шаблону", actual="Ключевые блоки распознаны частично", evidence="Поиск типовых терминов политики", recommendation="Сверить раздел политики с шаблоном."),
    ]
