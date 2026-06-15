from __future__ import annotations

from typing import Any

from .common import verdict


def run_llm_heuristics(suite: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    suite = suite.upper()
    syl = data["syllabus"]
    discipline = ((syl.get("descriptions") or [{}])[0].get("disciplineName") or syl.get("title") or "")
    text = syl.get("source", {}).get("text", "")
    if suite == "OP":
        return [
            verdict("OP-008", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Краткое содержание", expected="Содержание семантически соответствует описанию ОП", actual="Автономный локальный прогон не выполняет полноценную LLM-семантику", evidence=(syl.get("aimAndSummary") or {}).get("shortSummary", "")[:500], recommendation="Запустить через Codex-агента syllabus-op или проверить экспертно.", confidence=0.6),
            verdict("OP-009", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Цель", expected="Цель не противоречит цели ОП", actual="Требуется семантическая экспертиза", evidence=(syl.get("aimAndSummary") or {}).get("aim", "")[:500], recommendation="Проверить цель ОП и цель силлабуса.", confidence=0.6),
        ]
    if suite == "INT":
        return [
            verdict("INT-033", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Темплан", expected="Связка тема → РО → метод → оценивание логична", actual="Требуется LLM/экспертная оценка", evidence="build/syllabus.json/disciplineBlocks/thematicPlan", recommendation="Запустить через Codex-агента syllabus-int.", confidence=0.6)
        ]
    if suite == "TXT":
        foreign = []
        low_title = discipline.casefold()
        for marker in ["стоматолог", "акушер", "гинеколог", "педиатр", "дыхатель", "сердечно"]:
            if marker in text.casefold() and marker not in low_title:
                foreign.append(marker)
        return [
            verdict("TXT-001", "WARN" if foreign else "PASS", "MAJOR", discipline=discipline, location="Темы/оценивание/КИС", expected="Нет копипаст-ошибок из чужой дисциплины", actual=", ".join(foreign) if foreign else "Не выявлены эвристически", evidence="Эвристический поиск доменных маркеров", recommendation="Проверить спорные фрагменты редактором.", confidence=0.72),
            verdict("TXT-004", "WARN", "MINOR", discipline=discipline, location="Формулировки РО", expected="РО сформулированы диагностично", actual="Требуется редакторская оценка измеримости глаголов", evidence="build/syllabus.json/disciplineBlocks/learningOutcomes", recommendation="Проверить активные измеримые глаголы.", confidence=0.7),
            verdict("TXT-005", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Весь текст", expected="Нет внутренних повторов и противоречий", actual="Полная проверка требует LLM", evidence="Документ извлечён в build/syllabus.json/source/text", recommendation="Запустить через Codex-агента syllabus-txt.", confidence=0.6),
        ]
    if suite == "FMT":
        return []
    if suite == "STR":
        return []
    if suite == "RUP":
        return []
    return []

