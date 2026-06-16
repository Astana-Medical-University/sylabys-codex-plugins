from __future__ import annotations

import re
from typing import Any

from .common import verdict


# Недиагностичные начала формулировок РО (без измеримого действия).
_WEAK_RO_START = re.compile(r"^(зна(ть|ет|ют)|поним(ать|ает)|име(ть|ет)\s+представлени|ознаком|изуч(ить|ает))", re.IGNORECASE)


def _txt004(syl: dict[str, Any], discipline: str) -> dict[str, Any]:
    outcomes = [o for b in (syl.get("disciplineBlocks") or []) for o in (b.get("learningOutcomes") or [])]
    weak = []
    for o in outcomes:
        desc = re.sub(r"^\d+[.)]\s*", "", str(o.get("description", "")).strip())
        if _WEAK_RO_START.match(desc):
            weak.append(o.get("code"))
    if not outcomes:
        return verdict("TXT-004", "SKIP", "MINOR", discipline=discipline, location="Формулировки РО", expected="РО сформулированы диагностично", actual="РО не извлечены", evidence="build/syllabus.json", recommendation="")
    if weak:
        return verdict("TXT-004", "WARN", "MINOR", discipline=discipline, location="Формулировки РО", expected="РО начинаются с измеримого глагола (применяет, анализирует, демонстрирует…)", actual=f"Недиагностичные формулировки: {', '.join(c for c in weak if c)}", evidence="build/syllabus.json/disciplineBlocks/learningOutcomes", recommendation="Переформулировать РО через измеримые глаголы действия вместо «знать/понимать».", confidence=0.8)
    return verdict("TXT-004", "PASS", "MINOR", discipline=discipline, location="Формулировки РО", expected="РО сформулированы диагностично", actual=f"{len(outcomes)} РО с измеримыми глаголами", evidence="build/syllabus.json/disciplineBlocks/learningOutcomes", recommendation="", confidence=0.8)


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
        return [
            verdict("TXT-001", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Темы/оценивание/КИС", expected="Нет копипаст-ошибок из чужой дисциплины", actual="Семантическая проверка чужеродного контента требует LLM", evidence="build/syllabus.json/source/text", recommendation="Запустить через Codex-агента syllabus-txt для смыслового сравнения с предметом дисциплины.", confidence=0.6),
            _txt004(syl, discipline),
            verdict("TXT-005", "NEEDS_HUMAN", "MAJOR", discipline=discipline, location="Весь текст", expected="Нет внутренних повторов и противоречий", actual="Полная проверка требует LLM", evidence="Документ извлечён в build/syllabus.json/source/text", recommendation="Запустить через Codex-агента syllabus-txt.", confidence=0.6),
        ]
    if suite == "FMT":
        return []
    if suite == "STR":
        return []
    if suite == "RUP":
        return []
    return []

