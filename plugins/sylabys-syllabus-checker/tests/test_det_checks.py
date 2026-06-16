from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.mcp_server import build_audit_plan
from scripts.run_suite import run_agent_suite
from scripts.syllabus_checker.arbitration import _document_snapshot
from scripts.syllabus_checker.det import run_det_suite
from scripts.syllabus_checker.extractor import _extract_course, _extract_credits, _extract_thematic_plan


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def make_build(root: Path) -> Path:
    build = root / "build"
    build.mkdir()
    syllabus = {
        "type": "discipline",
        "title": "Тестовая дисциплина",
        "program": {"code": "6В10123", "name": "Медицина", "level": ""},
        "descriptions": [
            {
                "disciplineName": "Тестовая дисциплина",
                "program": {"code": "6В10123", "name": "Медицина", "level": ""},
                "cycleAndComponent": "БД ВК",
                "studyPeriod": {"course": 4, "semester": "7"},
                "credits": {"academic": 3, "ects": 3},
                "hours": {"total": 90, "lecture": 10, "practical": 20, "srop": 10, "sro": 20, "clinicalBasePractice": 0},
            }
        ],
        "disciplineBlocks": [
            {
                "disciplineName": "Тестовая дисциплина",
                "learningOutcomes": [{"code": "РО1", "description": "Применяет", "assessmentInstruments": []}],
                "practicalSkills": [{"code": "ПН1", "description": "Демонстрирует"}],
                "thematicPlan": [
                    {
                        "order": 1,
                        "learningOutcomeCode": "РО2",
                        "practicalSkillCodes": ["ПН9"],
                        "topic": "Тема",
                        "hours": {"lecture": 1, "practical": 1, "srop": 1, "sro": 1},
                        "teachingMethods": [],
                    }
                ],
            }
        ],
        "teachers": [],
        "aimAndSummary": {"aim": "", "shortSummary": ""},
        "assessments": [{"structure": [], "admissionRatingFormula": "", "finalGradeFormula": ""}],
        "approval": {"departmentProtocol": "", "developers": [], "agreedBy": []},
        "source": {"text": "Описание цель результат программные результаты обучения тематический план оценивание", "paragraphs": ["Тест"]},
        "format": {"fonts": {}, "fontSizesHalfPt": {}, "marginsCm": []},
    }
    op = {
        "program": {"code": "6В10123", "name": "Медицина", "level": ""},
        "outcomes": [{"code": "РО1", "text": "x"}],
        "targetNames": ["Тестовая дисциплина"],
        "matchedDiscipline": {"name": "Тестовая дисциплина", "cycle": "БД", "component": "ВК", "credits": 3, "programOutcomes": ["РО1", "РО3"]},
        "disciplines": [{"name": "Тестовая дисциплина", "raw": [], "programOutcomes": ["РО1", "РО3"]}],
    }
    rup = {
        "targetNames": ["Тестовая дисциплина"],
        "disciplines": [
            {
                "sheet": "4 курс 2023",
                "course": 4,
                "module": "Тестовый модуль",
                "discipline": "Тестовая дисциплина",
                "department": "Кафедра тестовой дисциплины",
                "controlForm": "э",
                "credits": 3,
                "ects": 3,
                "hours": {"total": 90, "lecture": 10, "practical": 20, "srop": 10, "sro": 20, "clinicalBasePractice": 0},
                "programOutcomes": ["РО1"],
                "raw": [],
            }
        ],
    }
    _write(build / "syllabus.json", syllabus)
    _write(build / "op.json", op)
    _write(build / "rup.json", rup)
    return build


class DetChecksTest(unittest.TestCase):
    def test_internal_hour_and_code_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = make_build(Path(tmp))
            result = {item["testId"]: item for item in run_det_suite("INT", build)}
            self.assertEqual(result["INT-012"]["verdict"], "FAIL")
            self.assertEqual(result["INT-020"]["verdict"], "FAIL")
            self.assertEqual(result["INT-021"]["verdict"], "FAIL")
            self.assertIn("ПЗ", result["INT-021"]["evidence"])
            self.assertIn("СРОП", result["INT-021"]["evidence"])

    def test_rup_matches_course_credits_and_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = make_build(Path(tmp))
            result = {item["testId"]: item for item in run_det_suite("RUP", build)}
            self.assertEqual(result["RUP-001"]["verdict"], "PASS")
            self.assertEqual(result["RUP-002"]["verdict"], "PASS")
            self.assertEqual(result["RUP-003"]["verdict"], "PASS")

    def test_op_matrix_reports_extra_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = make_build(Path(tmp))
            result = {item["testId"]: item for item in run_det_suite("OP", build)}
            self.assertEqual(result["OP-005"]["verdict"], "FAIL")
            self.assertEqual(result["OP-006"]["verdict"], "FAIL")

    def test_extract_thematic_plan_hours_from_new_template_columns(self) -> None:
        table = [
            ["№", "Код РО", "Код(ы) ПН", "Тема", "Л", "ПЗ", "СРОП", "СРО", "Методы обучения"],
            ["1", "РО1", "ПН1", "Артериальная гипертензия", "-", "2", "1", "3", "CBL"],
            ["2", "РО2", "ПН2", "Бронхиальная астма", "1", "4", "2", "5", "TBL"],
        ]
        plan = _extract_thematic_plan([table])
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["hours"], {"lecture": 0, "practical": 2.0, "srop": 1.0, "sro": 3.0})
        self.assertEqual(plan[1]["hours"], {"lecture": 1.0, "practical": 4.0, "srop": 2.0, "sro": 5.0})

    def test_mcp_audit_plan_uses_subagent_suites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            syllabus = root / "test.docx"
            syllabus.write_bytes(b"placeholder")
            plan = build_audit_plan(str(syllabus))
            self.assertEqual(plan["mode"], "plugin-mcp-plus-real-codex-subagents")
            self.assertEqual(set(plan["suiteCommands"]), {"STR", "FMT", "OP", "RUP", "INT", "TXT"})
            self.assertIn("Spawn six real Codex subagents", " ".join(plan["instructionsForCodex"]))
            self.assertTrue(plan["finalReportPdf"].endswith("final-report.pdf"))

    def test_run_suite_writes_named_suite_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = make_build(root)
            reports = root / "reports"
            summary = run_agent_suite("STR", build, reports)
            self.assertIn("syllabus-str", summary)
            self.assertTrue((reports / "str.json").exists())
            payload = json.loads((reports / "str.json").read_text(encoding="utf-8"))
            self.assertIsInstance(payload, list)

    def test_course_parser_ignores_resource_card_contingent(self) -> None:
        text = """
        СИЛЛАБУС
        Модуль: Анатомия
        Количество кредитов: 6
        Описание дисциплины (модуля)
        Период обучения
        1 курс, 1 семестр
        Количество академических кредитов
        2
        Приложение 2 — КО (Карта обеспеченности)
        КАРТА обеспеченности учебной литературой
        Курс ______________
        Всего контингент обучающихся 735 на 1 сентября
        """
        self.assertEqual(_extract_course(text), 1)
        self.assertEqual(_extract_credits(text, "module"), 6)

    def test_module_snapshot_does_not_print_invalid_course_or_single_discipline_credits(self) -> None:
        snapshot = _document_snapshot(
            {
                "type": "module",
                "title": "Анатомия",
                "course": 735,
                "credits": 2.0,
                "program": {"code": "6В10123", "name": "Медицина"},
                "descriptions": [
                    {
                        "disciplineName": "Анатомия",
                        "program": {"code": "6В10123", "name": "Медицина"},
                        "studyPeriod": {"course": 735},
                        "credits": {"academic": 0, "ects": 0},
                    }
                ],
            }
        )
        self.assertIn("курс не распознан", snapshot["courseCredits"])
        self.assertIn("кредиты модуля не извлечены", snapshot["courseCredits"])
        self.assertNotIn("735, 2.0 кредитов", snapshot["courseCredits"])


if __name__ == "__main__":
    unittest.main()
