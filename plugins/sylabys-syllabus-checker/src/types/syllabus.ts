/**
 * Эталонная типизированная модель силлабуса
 * НАО «Медицинский университет Астана».
 *
 * Основано на шаблоне ДАР от 12.06.2026.
 * Язык контента — русский.
 *
 * Источник каждого поля помечен тегом в JSDoc:
 *   @source platonus  — синхронизируется из БД Platonus
 *   @source admin     — справочные/админ-данные, заводит отдел вуза
 *   @source pps       — заполняет составитель силлабуса
 *   @source computed  — вычисляется автоматически из других полей
 */

// ─────────────────────────────────────────────────────────────────────────
// Базовые алиасы
// ─────────────────────────────────────────────────────────────────────────

/** Идентификатор (UUID/строка). */
export type UUID = string;

/** Тип силлабуса: модуль или отдельная дисциплина. */
export type SyllabusType =
  | 'module'
  | 'discipline';

/** Вид контрольного мероприятия в шаблоне ДАР. */
export type AssessmentFormKind =
  | 'oral_exam'
  | 'written_exam'
  | 'testing'
  | 'clinical_case'
  | 'osce_station';

/** Раздел литературы. */
export type ReferenceKind = 'main' | 'additional';

/** Язык обеспеченности литературы в карте обеспеченности. */
export type ResourceLanguage = 'kk' | 'ru' | 'en';

// ─────────────────────────────────────────────────────────────────────────
// Корневая сущность
// ─────────────────────────────────────────────────────────────────────────

export interface Syllabus {
  id: UUID;

  /**
   * Тип силлабуса. На титуле указан как "Модуль / Дисциплина".
   * @source pps
   */
  type: SyllabusType;

  /**
   * Наименование модуля или дисциплины на титульном листе.
   * @source platonus | pps
   */
  title: string;

  /**
   * Учебный год, напр. "2026-2027".
   * @source platonus
   */
  academicYear: string;

  /**
   * Образовательная программа.
   * @source platonus
   */
  program: ProgramRef;

  /**
   * Количество кредитов: для модуля сумма дисциплин, для дисциплины ее кредиты.
   * @source platonus | computed
   */
  credits: number;

  /**
   * Курс обучения.
   * @source platonus
   */
  course: number;

  /**
   * Город и год издания на титульном листе.
   * @source pps
   */
  city: string;
  publicationYear: number;

  /**
   * Раздел 1: описание дисциплины или модуля.
   * Для модульного типа может повторяться по дисциплинам модуля.
   */
  descriptions: SyllabusDescription[];

  /**
   * Раздел 2: преподаватели.
   * @source platonus
   */
  teachers: Teacher[];

  /**
   * Раздел 3: цель и краткое содержание.
   * Для module — общие цель и содержание модуля; для discipline — дисциплины.
   * @source pps
   */
  aimAndSummary: AimAndSummary;

  /**
   * Разделы 4-6: РО, ПН и тематический план.
   * Для module заполняется по каждой дисциплине.
   */
  disciplineBlocks: DisciplineBlock[];

  /**
   * Раздел 7: график СРОП.
   * @source pps
   */
  sropSchedule: SropConsultation[];

  /**
   * Раздел 8: политика дисциплины/модуля.
   * @source pps
   */
  policy: Policy;

  /**
   * Раздел 9: оценивание.
   * Для module может повторяться по дисциплинам.
   * @source pps | computed
   */
  assessments: Assessment[];

  /**
   * Раздел 10: список литературы.
   * @source admin | platonus | pps
   */
  references: ReferenceItem[];

  /**
   * Раздел 11: глоссарий / список сокращений.
   * @source pps
   */
  glossary: GlossaryEntry[];

  /**
   * Приложение 1: КИС.
   * @source pps
   */
  examMaterials: ExamMaterials;

  /**
   * Приложение 2: карта обеспеченности.
   * @source admin | platonus
   */
  resourceCard: ResourceCard;

  /**
   * Раздел 12: согласование / утверждение.
   * @source pps | admin
   */
  approval: Approval;

  version: string;
  createdAt: string; // ISO
  updatedAt: string; // ISO
}

// ─────────────────────────────────────────────────────────────────────────
// Справочные ссылки
// ─────────────────────────────────────────────────────────────────────────

export interface ProgramRef {
  /** @source platonus — шифр, напр. "6B10123" */
  code: string;
  /** @source platonus — наименование, напр. "Медицина" */
  name: string;
  /** @source platonus — уровень образования */
  level: string;
}

/** Кафедра / НИИ. @source platonus */
export interface DepartmentRef {
  id?: UUID;
  name: string;
  address?: string;
}

/** Преподаватель. @source platonus */
export interface Teacher {
  fullName: string;
  position: string;
  departmentOrInstitute: DepartmentRef;
  email: string;
}

// ─────────────────────────────────────────────────────────────────────────
// Разделы 1-7
// ─────────────────────────────────────────────────────────────────────────

export interface SyllabusDescription {
  /** @source platonus — наименование модуля, только для module */
  moduleName?: string;
  /** @source platonus */
  disciplineName: string;
  /** @source platonus */
  program: ProgramRef;
  /** @source platonus — цикл и компонент дисциплины */
  cycleAndComponent: string;
  /** @source platonus */
  studyPeriod: StudyPeriod;
  /** @source platonus */
  credits: CreditInfo;
  /** @source platonus */
  hours: Hours;
  /** @source platonus | pps */
  formsOfClasses: string[];
  /** @source platonus */
  prerequisites: string[];
  /** @source platonus */
  postrequisites: string[];
}

export interface StudyPeriod {
  course: number;
  semester: string;
}

export interface CreditInfo {
  academic: number;
  ects?: number;
}

export interface Hours {
  total: number;
  lecture: number;
  practical: number;
  srop: number;
  sro: number;
  clinicalBasePractice?: number;
}

export interface AimAndSummary {
  aim: string;
  shortSummary: string;
}

export interface DisciplineBlock {
  disciplineName: string;
  learningOutcomes: LearningOutcome[];
  practicalSkills: PracticalSkill[];
  thematicPlan: ThematicPlanRow[];
}

export interface LearningOutcome {
  /** @source pps — код, напр. "РО1" */
  code: string;
  /** @source pps */
  description: string;
  /** @source pps — оценивание / инструменты из таблицы РО */
  assessmentInstruments: string[];
}

export interface PracticalSkill {
  /** @source pps — код, напр. "ПН1" */
  code: string;
  /** @source pps */
  description: string;
}

export interface ThematicPlanRow {
  order: number;
  /** @source pps */
  learningOutcomeCode: string;
  /** @source pps */
  practicalSkillCodes: string[];
  /** @source pps */
  topic: string;
  /** @source pps */
  hours: ThematicHours;
  /** @source pps */
  teachingMethods: string[];
}

export interface ThematicHours {
  lecture: number;
  practical: number;
  srop: number;
  sro: number;
}

export interface SropConsultation {
  teacherName: string;
  dayOfWeek: string;
  timeFrom: string;
  timeTo: string;
}

// ─────────────────────────────────────────────────────────────────────────
// Раздел 8: политика
// ─────────────────────────────────────────────────────────────────────────

export interface Policy {
  generalRequirements: string;
  attendance: string;
  absenceWorkOff: string;
  absencePenalties: string[];
  admissionRules: string;
  dressCodeAndClinicalBaseRules: string;
  mobileDevices: string;
  academicIntegrity: string;
  appeals: string;
  accessibility: string;
}

// ─────────────────────────────────────────────────────────────────────────
// Раздел 9 и Приложение 1: оценивание и КИС
// ─────────────────────────────────────────────────────────────────────────

export interface Assessment {
  disciplineName?: string;
  structure: AssessmentComponent[];
  currentControl: CurrentControlAssessment;
  intermediateAttestation: IntermediateAttestation;
  redFlags: RedFlag[];
  /** @source computed — ОРД = среднее арифметическое результатов ТК */
  admissionRatingFormula: string;
  /** @source computed — ИО = ОРД * 0.6 + ОПА * 0.4 */
  finalGradeFormula: string;
}

export interface AssessmentComponent {
  name: string;
  weightPercent: number;
  deadline: string;
  criteria: string;
}

export interface CurrentControlAssessment {
  oralExam?: ChecklistAssessment;
  writtenExam?: ChecklistAssessment;
  testing?: TestAssessment;
  clinicalCase?: ChecklistAssessment;
  osceStation?: OsceStationAssessment;
}

export interface IntermediateAttestation {
  oralExam?: ChecklistAssessment;
  writtenExam?: ChecklistAssessment;
  testing?: TestAssessment;
  clinicalCase?: ChecklistAssessment;
  osceStations?: OsceStationAssessment[];
  maxScore: number;
}

export interface ChecklistAssessment {
  kind: AssessmentFormKind;
  title: string;
  criteria: ChecklistCriterion[];
  maxScore: number;
}

export interface ChecklistCriterion {
  order: number;
  description: string;
  maxScore: number;
}

export interface TestAssessment {
  kind: 'testing';
  rows: TestAssessmentRow[];
  maxScore: number;
}

export interface TestAssessmentRow {
  order: number;
  questionCount: number;
  complexityLevel: string;
  scorePerQuestion: number;
  totalScore: number;
}

export interface OsceStationAssessment {
  kind: 'osce_station';
  skillCodes: string[];
  stationName: string;
  checklist?: ChecklistAssessment;
  maxScore: number;
}

export interface RedFlag {
  order: number;
  description: string;
  mark?: string;
}

export interface ExamMaterials {
  questions: ExamQuestion[];
  oralExam?: ChecklistAssessment;
  writtenExam?: ChecklistAssessment;
  testing?: TestAssessment;
  clinicalCase?: ChecklistAssessment;
  osceStations?: OsceStationAssessment[];
}

export interface ExamQuestion {
  number: number;
  text: string;
}

// ─────────────────────────────────────────────────────────────────────────
// Разделы 10-12 и Приложение 2
// ─────────────────────────────────────────────────────────────────────────

export interface ReferenceItem {
  kind: ReferenceKind;
  citation: string;
  url?: string;
}

export interface GlossaryEntry {
  abbreviation: string;
  definition: string;
}

export interface ResourceCard {
  department: string;
  disciplineName: string;
  program: ProgramRef;
  course: number;
  studentContingent: StudentContingent;
  items: ResourceCardItem[];
  totals?: ResourceCardTotals;
  approvals: ResourceCardApproval;
}

export interface StudentContingent {
  total: number;
  academicYear: string;
  byLanguage: Record<ResourceLanguage, number>;
}

export interface ResourceCardItem {
  kind: ReferenceKind;
  order: number;
  bibliographicDescription: string;
  editionType: string;
  requiredCopies: Record<ResourceLanguage, number>;
  libraryCopies: Record<ResourceLanguage, number>;
  electronicResources: Record<ResourceLanguage, number>;
  subscriptionUrl?: string;
}

export interface ResourceCardTotals {
  totalTitles?: number;
  supplyUnits?: number;
}

export interface ResourceCardApproval {
  libraryDirector?: string;
  subjectLibrarian?: string;
  departmentHead?: string;
  departmentReferent?: string;
  date?: string;
}

export interface Approval {
  departmentProtocol: string;
  protocolDate?: string;
  developers: string[];
  agreedBy: string[];
  academicWorkDepartmentDirector?: string;
}
