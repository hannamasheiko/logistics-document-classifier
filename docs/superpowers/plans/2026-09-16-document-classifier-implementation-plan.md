# Document Classifier Implementation Plan

> **For agentic workers:** після явного погодження користувачем виконувати план task-by-task із superpowers:executing-plans. Subagent-driven-development — лише за окремо погодженого способу виконання. Checkbox позначає виконану й перевірену дію, а не сам факт написання коду. Не починати execution під час підготовки цього плану.

**Goal:** реалізувати перевірений Django document-processing застосунок: classification текстових і сканованих PDF, один visual fallback, persistence/UI/history та planned field extraction із confidence.

**Architecture:** синхронний Django upload flow створює окрему attempt на кожне прийняте завантаження. Text extraction або OCR живить спільний primary classifier: LLM повертає candidate class та structured class-specific features/evidence. Backend детерміновано оцінює достатність і суперечності evidence, рахує routing score та приймає classification, встановлює semantic uncertainty або викликає один visual fallback. PostgreSQL зберігає metadata/results, local media — original PDF.

**Tech Stack:** Django, PostgreSQL, Docker Compose для БД, OpenAI API, Python; конкретні версії, PDF/OCR libraries та OpenAI models обираються через gates нижче.

**Spec:** [Погоджений дизайн](../specs/2026-09-16-document-classifier-design.md).

**Статус:** design document погоджено користувачем у thread; Brainstorming завершено. Цей implementation plan очікує перегляду. Історичний approval status усередині design document не є новою забороною Planning; сам design document тут не редагується.

## Global Constraints

- Бюджет: приблизно **2–3 дні**; оцінки нижче — робочий розподіл часу, не гарантія строку.
- Один PDF — один документ, можливо багатосторінковий; **до 10 сторінок і до 10 МБ**. Не обрізати мовчки.
- Класи: `INVOICE` за логістичні послуги, `BOL`, `POD`, `OTHER`; Commercial Invoice на товари — `OTHER`.
- `ACCEPTED`, semantic `UNCERTAIN` та technical failure відокремлені.
- Надійно встановлений combined BOL/POD → `UNCERTAIN` без fallback; сумнів між BOL/POD/combined → classification uncertainty.
- Iteration 1 без fallback — проміжна, не фінальна здача. Iteration 2 має OCR та один visual fallback для обох видів PDF. Stronger-text fallback не додається.
- Maximum one classification fallback на attempt. Technical retries потребують окремого обмеження; не використовувати retries для підвищення confidence.
- Confidence — evidence-based routing score, який рахує backend, не probability of correctness і не OCR quality. Primary/fallback evidence checks та thresholds перевіряються окремо. Logprobs, self-reported confidence і порівняння альтернативних confidence mechanisms не входять до обов’язкового experiment; повертатися до альтернатив лише за конкретного виявленого недоліку та погодження користувача.
- Field extraction + field confidence входять у planned delivery після стабільного core. Скорочення scope — лише окремо погоджена contingency.
- Одна PostgreSQL DB, local media, мінімальний UI/history; без accounts/authentication, queues/workers, external object storage, deduplication/cache або додаткових класів.
- Кожне прийняте завантаження — нова attempt. Попередні записи не перезаписуються. Initial rejection не створює attempt; subsequent failure зберігається з PDF.
- Не читати, не друкувати, не включати у файли/коміти секретні значення. Конфігураційні приклади містять лише назви змінних і порожні/явно несправжні значення; API runtime отримує секрет без його виведення агентом.
- Не робити коміти автоматично. Перед кожним запропонованим комітом: підсумок stage, фактичні checks/results і proposed message.
- `AI_WORKFLOW.md` і `AI_WORKFLOW_UA.md` зберігаються лише як historical snapshots Brainstorming, Planning і Task 1. Не оновлювати, не синхронізувати, не перекладати й не читати їх як prerequisite для наступних tasks.

## 1. Як виконувати план і приймати deferred decisions

План задає конкретні deliverables, перевірки та запропоновані файлові межі. Нижче зафіксовані погоджені межі відповідальності; конкретні AI contracts/types/signatures визначаються після feasibility experiment, а schema — у відповідному foundation gate. Залежний код не пишеться до закриття відповідного gate. Самі experiments ще не проведені.

Кожен gate завершується коротким reviewable записом: кандидати, фактичні приклади/результати, вартість/час за наявності, обмеження, рекомендація. Користувач погоджує значущий вибір; незалежну роботу можна продовжувати. Після відповідного gate описати погоджений контракт і залежні перевірки перед реалізацією; не визначати їх наперед замість результатів experiment.

| Gate | Коли | Що вирішуємо | Що блокує |
|---|---|---|---|
| G1 | Task 1, без application foundation | Мінімальний AI feasibility на контрольних PDF; structured class-specific evidence від model/API, придатність deterministic routing та мінімальний result contract, без робочого threshold | Фіксація schema/application foundation у Task 2 та початок systematic evaluation у Task 2E |
| G0 | Task 2, після G1 | Версії, text parser, базова schema/storage lifecycle, трактування 10 МБ у bytes, unreadable/encrypted input policy | Production foundation та PDF intake |
| GE | Task 2E, після G1; незалежно від завершення Task 2 | Representative evaluation manifest/split, перевірені primary acceptance/ambiguity checks, score calculation та початковий робочий threshold | Інтеграція погодженого routing у Task 3 та підтвердження перевіреного vertical slice; не блокує foundation/UI structure |
| G2 | Task 5 | OCR/renderer, page/text sufficiency policy, mixed-page PDFs, ліміти render/time, visual model, fallback acceptance та bounded technical retries | Scanned/visual production path |
| G3 | Task 7 | Короткий extraction contract: невеликий class-specific schema, value/status/evidence, deterministic validators, explainable field-confidence formula, expected examples та failure behavior | Extraction implementation у Task 8 |
| G4 | Task 9 | Оцінка фактичних результатів проти критеріїв здачі, чесні limitations або конкретне виправлення | Оголошення planned delivery завершеним |

Якщо evidence-based підхід не проходить experiment, зафіксувати конкретний недолік і погодити корекцію або альтернативу; не запускати автоматично дослідження інших confidence mechanisms і не вигадувати результат. Якщо час вичерпується, обговорити contingency до відмови від planned extraction.

## 2. Запропонована структура файлів

У репозиторії поки є документація та `.gitignore`; application structure не існує. Перед execution перечитати поточні AGENTS і стан файлів, зберегти чужі зміни.

```text
manage.py
requirements.txt                       # pinned узгоджені runtime/test dependencies
compose.yaml                           # лише PostgreSQL і persistent DB volume
.env.example                           # тільки non-secret placeholders
README.md                              # reviewer quickstart і limitations
config/{__init__,settings,urls,wsgi}.py  # Django configuration
documents/                             # Django app
  {__init__,apps,models,forms,views,urls}.py
  migrations/
  services/
    processing.py                      # synchronous flow, attempt lifecycle/persistence
    pdf.py                             # inspect/text/render, обрані libraries
    ocr.py                             # OCR, лише після G2
    routing.py                         # backend acceptance/ambiguity/fallback decisions
  ai/
    classification.py                  # OpenAI text/visual calls, response validation
    extraction.py                      # structured field extraction calls/parsing, лише після G3
    prompts/{classification,visual,extraction}.txt
  templates/documents/{upload,result,history}.html
  management/commands/evaluate_documents.py
  tests/{test_intake,test_routing,test_pipeline,test_views,test_extraction}.py
  tests/fixtures/                      # невеликі дозволені/синтетичні PDF
evaluation/
  manifest.json                        # labels, expected fields, provenance, split/group
  documents/                           # лише дозволені для поширення fixtures
  results/                             # компактні sanitized evaluation artifacts
experiments/
  primary_confidence.py
  scanned_fallback.py
docs/experiments/
  primary-confidence.md
  scanned-fallback.md
docs/decisions/
  field-extraction-contract.md         # погоджений у G3 вузький extraction contract
```

Не створювати невикористані модулі наперед. Не вводити repository pattern, provider framework, vector DB або orchestration framework. `.gitignore` змінювати лише після читання його наявного вмісту; PDFs користувача/media, локальна конфігурація із секретами та сирі API dumps не потрапляють у Git.

### Межі відповідальності та уточнення контрактів

Один Django app `documents` містить три логічні частини:

- **Django application layer** у корені app: models/persistence representation, forms, views, URLs і templates для upload/result/history/original.
- **`services/`**: processing flow, отримання тексту/зображень, OCR, routing та збереження результатів. Services можуть безпосередньо використовувати Django ORM; окремий repository layer не потрібний.
- **`ai/`**: OpenAI calls, prompts, перевірка формату модельної відповіді та перетворення її на результат для processing. AI layer повертає candidate class та structured class-specific features/evidence; backend routing вирішує, чи прийняти результат, виконати fallback або завершити з `UNCERTAIN`.

Дерево задає логічні межі, а не остаточний перелік файлів. Не створювати окремі Django apps, domain layer або provider framework для цього розділення. OCR та extraction модулі додаються у своїх ітераціях.

Контракти уточнюються послідовно:

1. **Task 1 / G1:** мінімальний AI result contract на основі фактичного structured class-specific evidence від API; experiment незалежний від application modules.
2. **Task 2 / G0:** application/persistence representation з урахуванням результатів G1.
3. **Task 2E / GE:** score, routing checks і залежні частини контракту.
4. **Відповідна iteration:** конкретні Python types, dataclasses за потреби, function signatures та тести перед реалізацією; visual/OCR contract після G2, extraction implementation types після погодженого G3 contract.

До цих gates план фіксує відповідальності, потрібні результати та поведінкові сценарії, а не назви типів, поля dataclasses або signatures. Відсутній/невалідний score не підміняється нулем. Backend checks не довіряють безумовно booleans від LLM; результати не містять credentials або сирих sensitive API payloads. Extraction value/status/evidence semantics і validation rules визначаються в G3.

### Evidence-based confidence/routing: погоджений підхід і обмеження

LLM повертає candidate class, class-specific features та evidence; backend застосовує детерміновані правила достатності/суперечностей і рахує score. Достатні evidence та acceptance checks → `ACCEPTED`; недостатні або суперечливі evidence → один visual fallback у повному flow або тимчасовий `UNCERTAIN` в Iteration 1. Надійно встановлений combined BOL/POD → `UNCERTAIN` без fallback. Technical failure залишається окремим outcome.

- Детермінований розрахунок не гарантує достовірність evidence від LLM. Для text path перевіряти наявність коротких evidence-цитат у вхідному тексті; збіг підтверджує джерело, але не правильність семантичної інтерпретації. Після OCR така перевірка також не доводить правильність розпізнавання оригіналу.
- Ознаки мають розрізняти класи, а не просто рахувати заповнені поля. Спільні адреси/дати/shipment numbers самі по собі не визначають клас; відсутність необов’язкового поля не повинна автоматично знижувати score. Важливі contradictions не приховуються високою сумою балів.
- Відсутність ознак цільових класів не доводить `OTHER`: це може бути неповний/погано прочитаний або неоднозначний документ. Прийняття `OTHER` також потребує обґрунтованого evidence та перевірених правил.
- Visual fallback отримує зображення original PDF і може використати layout та інформацію, втрачену під час extraction/OCR. Він повертає structured evidence, яке проходить власні backend acceptance checks; його відповідь не приймається автоматично. Спосіб перевірки visual evidence, score і threshold перевірити окремо у G2, не переносити механічно primary rules/threshold або перевірку текстових цитат.
- Score пояснюється в README/UI як evidence-based routing signal, не калібрована ймовірність. Конкретні classification features, rules, formula та threshold визначаються й перевіряються у відповідних experiments; тут вони не фіксуються. Для field extraction G3 погоджує один простий explainable score на основі evidence та доступної deterministic validation, без порівняння альтернативних confidence mechanisms.

Processing розрізняє initial rejection і technical failure після intake та зберігає відповідний стан. Fallback не запускає наступну escalation. Режим iteration визначає application configuration, не поле користувача.

## 3. Послідовність і working milestones

| Milestone | Tasks | Результат |
|---|---|---|
| AI feasibility та review | 1, G1 | Незалежний experiment на кількох PDF; structured evidence, придатність deterministic routing і мінімальний result contract, без Django/DB/persistence |
| Application foundation | 2, G0 після G1 | Schema, dependencies та intake/persistence на основі результатів experiment |
| Systematic evaluation | 2E, GE; може виконуватися поряд із Task 2 | Manifest, tuning/held-out examples та перевірені routing settings після feasibility |
| Iteration 1 | 3–4 після Task 2 і GE | Реальний text-layer PDF → OpenAI → result/history/original; без fallback |
| Iteration 2 | 5–6 | Scanned OCR та спільний visual fallback, semantic/technical outcomes |
| Planned extraction | 7–8 | Короткий extraction contract checkpoint, потім structured extraction, persistence/UI та regression core |
| Planned delivery | 9 | Evaluation report, reproducible startup, documented limitations |

Орієнтовний розподіл: день 1 — Tasks 1–4, включно з Task 2E; день 2 — Tasks 5–6 і короткий G3 checkpoint; день 3 — Tasks 8–9 та corrections. Для двох днів проміжки стискаються, але planned extraction не зникає автоматично. Classification/fallback experiments мають вузькі цілі та обмежений погоджений бюджет викликів, а extraction не відкриває окреме порівняльне дослідження.

## Task 1: Незалежний AI feasibility / evidence-based routing experiment (G1)

**Status:** complete; G1 approved. Production score/threshold and demonstrated routing quality remain deferred to Task 2E.

**Files:** create `experiments/primary_confidence.py`, `docs/experiments/primary-confidence.md`; використати кілька дозволених контрольних PDF. Manifest у цьому task не створюється. Prompt experiment зберігати в `experiments/primary_confidence.py`; application prompt переноситься в Task 3 після погодження контракту.

**Consumes:** погоджена taxonomy та кілька representative text-layer PDF. Не залежить від G0, Django, models, PostgreSQL, migrations, intake або persistence. **Produces:** feasibility report, погоджений primary model/endpoint для structured evidence та висновок про придатність deterministic routing, мінімальний result contract для Task 2 та гіпотези checks для перевірки у Task 2E. Не визначає робочий threshold.

- [x] Прочитати repository instructions і git state; підготувати standalone Python experiment із мінімальними узгодженими dependencies для OpenAI та отримання тексту. Не створювати Django scaffold, `documents/` modules, DB schema або persistence. Отримувати текст локально в experiment; production parser і application contracts ще не фіксувати.
- [x] Взяти кілька контрольних text-layer PDF з вручну визначеними expected results; у короткому experiment report записати походження й можливість поширення. Спірні очікування уточнити з користувачем. Не вимагати manifest, повного покриття класів або tuning/held-out split на цьому кроці; blank/synthetic приклади позначати відповідно.
- [x] Перевірити офіційну документацію OpenAI щодо structured output для обраного model/endpoint і погодити live-call budget. Не вимагати logprobs або self-reported score.
- [x] Сформувати компактний reviewable набір class-specific diagnostic features/evidence для feasibility, з розрізненням present/absent/unclear; не розгортати масштабний feature engineering. Конкретну форму structured response уточнювати за experiment, не фіксувати Python types наперед.
- [x] Перевірити, чи model/API реально повертає candidate class та потрібне structured evidence. Документ трактувати як дані, не інструкції змінити taxonomy. Не друкувати API key або environment.
- [x] На контрольних PDF перевірити evidence-цитати проти вхідного тексту та вручну оцінити їхню семантичну релевантність. Зафіксувати missing/unclear, непідтверджені або суперечливі evidence, зокрема ризик хибного OTHER.
- [x] Перевірити можливість застосувати компактні deterministic sufficiency/contradiction rules до отриманого evidence; порівняти classification і запропоновану routing behavior з відомими очікуваннями. Зберегти evidence, outcomes, пробні scores/checks, latency/usage та обмеження. Це перевірка одного підходу, не порівняння confidence mechanisms.
- [x] Запропонувати мінімальний evidence-based result contract та гіпотези backend checks для Task 2E. Не обирати робочий threshold і не заявляти підтверджену routing quality: лише правильні відповіді на простих прикладах ще не доводять корисність escalation signal.
- [x] Подати G1 користувачу з фактичними feasibility results та обмеженнями. Після погодження зафіксувати experiment model/prompt/config identifiers; передати findings у Task 2 та Task 2E.

**Exit:** report містить висновок про придатність structured evidence і deterministic routing або конкретний blocker/недостатність даних. Кілька прикладів підтверджують feasibility й напрям, а не надійність threshold на всьому наборі; systematic evaluation починається у Task 2E та продовжується у наступних stages. Review G1 передує фіксації schema та application foundation у Task 2. Production classifier не інтегрується з непогодженим score. Runtime ground truth не вводиться.

## Task 2: Foundation decisions та перевірюваний intake/persistence

**Status:** complete; G0 approved. Implementation committed in `ba213c9`.

**Files:** create `requirements.txt`, `compose.yaml`, `.env.example`, `manage.py`, `config/`, `documents/{apps,models,forms}.py`, `documents/services/pdf.py`, `documents/migrations/`; modify `.gitignore`, `README.md`; test `documents/tests/test_intake.py`.

**Consumes:** spec, результати й мінімальний result contract із Task 1/G1; погодження foundation у G0. Task 2 не очікує GE або остаточних confidence settings. **Produces:** PostgreSQL-backed processing attempt, перевірка PDF, file storage та розрізнення initial rejection і subsequent technical failure; конкретні types/names визначаються у G0.

- [x] Прочитати repository instructions і `.gitignore`; перевірити git state без читання sensitive configuration. Визначити потребу в isolation перед application changes, не перезаписувати наявні файли.
- [x] Підготувати G0: підібрати сумісні Django/Python/PostgreSQL/OpenAI SDK versions; використати результати мінімального text extraction із Task 1 та обрати production text PDF parser за extraction, page counting, license та setup. Не додавати OCR dependencies на цьому кроці.
- [x] На основі перевіреного в Task 1 result contract запропонувати одну model для processing attempt: file reference, original name, size/pages/timestamps, processing status, nullable accepted label/score, score method, primary/fallback normalized observations, failure stage/reason, model/config identifiers. Extraction data додати тільки після G3. JSON для variable observations — пропозиція, не затверджена раніше schema.
- [x] У G0 явно визначити: bytes для 10 МБ; що вважається initial rejection (не PDF, перевищення, неможливість перевірити pages/encryption); технічний збій після успішного intake. Прийняті PDF зберігаються в local media; rejected uploads і temporary processing files очищаються. Окремі deletion UI, retention policy або automatic retention service не проєктувати.
- [x] Отримати погодження G0 перед залежною реалізацією; зафіксувати вибір у README без окремого історичного workflow log.
- [x] Створити мінімальний Django scaffold і Compose БД; встановити тільки узгоджені dependencies. Файл `.env.example` заповнити без реальних секретів. Django/OpenAI отримують налаштування runtime без їх друку.
- [x] Написати regression tests на Django TestCase з fixtures без live API: rejected upload не створює запис; два прийняті завантаження одного PDF створюють два різні записи; original PDF існує у storage. Конкретні assertions визначити після G0.

- [x] Запустити failing cases для 11 сторінок, перевищення bytes, renamed non-PDF і повторного валідного upload; перевірити failure саме потрібної поведінки.
- [x] Реалізувати model, migration, intake та local storage; metadata не довіряє лише extension/MIME. Не тримати DB transaction відкритою під час майбутніх LLM/OCR calls.
- [x] Запустити `docker compose up -d`, `python manage.py migrate`, `python manage.py check`, `python manage.py test documents.tests.test_intake`; очікування — working DB, schema та PASS boundary tests.

**Exit:** intake/storage перевірені на PostgreSQL; rejected input не створює attempt/media leftovers; accepted repeats — різні записи. Це ще не classifier demo.

## Task 2E: Systematic primary evaluation після feasibility (GE)

**Status:** complete; GE approved. Implementation committed in `f8a93c0`.

**Files:** create `evaluation/manifest.json`, дозволені `evaluation/documents/` fixtures; extend `experiments/primary_confidence.py`, `docs/experiments/primary-confidence.md`; save sanitized results у `evaluation/results/`.

**Consumes:** Task 1/G1: model/API для structured evidence, мінімальний evidence contract та findings щодо deterministic routing. Не потребує Django models/PostgreSQL або завершення Task 2; application foundation та підготовка evaluation можуть просуватися незалежно. **Produces:** representative manifest/split, перевірені primary score calculation, acceptance/ambiguity checks та початковий робочий threshold для Task 3.

- [x] Підготувати невеликий representative text-layer set для чотирьох класів і combined ambiguity. Manifest містить provenance, expected label/outcome, template group, split та право поширення; не задавати обов'язкової кількості 60–100.
- [x] Узгодити спірні labels. Розділити tuning та held-out без однакових шаблонів у двох групах. Документи, використані для вибору моделей/prompts у feasibility, не вважати незалежними held-out examples.
- [x] На tuning examples уточнити evidence-based score calculation, sufficiency/contradiction checks, правила прийняття OTHER, ambiguity checks і threshold; no-label/missing-score/invalid-output не перетворювати автоматично на OTHER.
- [x] Записати expected/actual outcomes, scores/method, помилки серед accepted, правильні classifications, відправлені на escalation, uncertainty, evidence errors/contradictions та обмеження; запропонувати конкретні routing settings користувачу для GE. Мала кількість помилок не доводить calibrated probability або routing reliability.
- [x] Після погодження заморозити model/prompt/config/checks і перевірити held-out без підбору на ньому. Зберегти фактичний результат; якщо перевірка виявляє проблему, явно повернутися до review, не приховувати retuning як незалежну перевірку.

**Exit:** GE закрито reviewable evaluation report і погодженими routing settings або явно зафіксовано причину, що блокує їх прийняття. Foundation та UI structure можуть розвиватися, але vertical slice не оголошується перевіреним без цієї evaluation. Fallback/extraction evaluation залишаються у своїх наступних tasks.

## Task 3: Text classification, routing і attempt lifecycle

**Files:** create/modify `documents/services/{routing,processing}.py`, `documents/ai/classification.py`, `documents/ai/prompts/classification.txt`; test `documents/tests/{test_routing,test_pipeline}.py`. Місце спільних типів визначити за погодженим після experiment контрактом, без обов’язкового `contracts.py` наперед.

**Consumes:** model/API напрям із Task 1/G1, погоджені score/checks із Task 2E/GE, Task 2 attempt. **Produces:** primary text classification, backend routing та synchronous attempt lifecycle без fallback у першій iteration; конкретні types/signatures — за результатами G1 і GE.

- [ ] Написати pure routing tests для accepted, established ambiguity та unresolved observation; використовувати погоджені checks. Перевірити, що неприйнята primary відповідь у першій iteration завершується як `UNCERTAIN` без fallback, а established ambiguity не запускає fallback і після його додавання. Додати сценарії непідтверджених evidence-цитат, contradictions попри високий сумарний score та відсутніх target features, які не повинні автоматично давати OTHER.

- [ ] Запустити `python manage.py test documents.tests.test_routing`; переконатися, що відсутня routing implementation спричиняє очікуваний failure.
- [ ] Реалізувати routing із пріоритетом established ambiguity, потім acceptance checks, потім escalation або interim uncertainty. Candidate label не заповнює final accepted label, поки routing не прийняв результат.
- [ ] Реалізувати OpenAI call/strict response validation згідно G1 та GE; persist тільки normalized observations. Invalid response/API timeout — technical failure за погодженою політикою, не автоматичний OTHER.
- [ ] Написати pipeline tests з fake OpenAI boundary: accepted BOL, OTHER, uncertain, extraction-of-text failure, invalid model response, API timeout. Assertion: failure зберігає PDF/reason; final label порожній у non-accepted outcome.
- [ ] Реалізувати synchronous lifecycle з короткими DB writes до/після external work. В Iteration 1 не викликати renderer/OCR/fallback.
- [ ] Запустити `python manage.py test documents.tests.test_routing documents.tests.test_pipeline`; потім невеликий погоджений live smoke з реальним text PDF. Mocks підтверджують control flow, live examples — фактичну інтеграцію; звітувати окремо.

**Exit:** text path працює з реальною primary model, усі non-accepted cases відокремлені від accepted results.

## Task 4: Working vertical slice через UI/history

**Files:** create `documents/{views,urls}.py`, `templates/documents/{upload,result,history}.html`, `tests/test_views.py`; modify `config/urls.py`, `README.md`.

**Consumes:** Tasks 1–3. **Produces:** upload POST → result redirect, history/result GET, original PDF access.

- [ ] Написати Django client tests: valid upload створює attempt і переводить на result; invalid input не створює запис; history показує кілька attempts одного PDF; non-accepted result не показується як accepted.
- [ ] Запустити tests до реалізації views/templates, перевірити очікувані failures.
- [ ] Реалізувати прості Django templates/forms без нового frontend framework; результат показує score method/limitations, original link та reason для UNCERTAIN/failure.
- [ ] Original PDF видавати за record reference, не довільним user-supplied filesystem path; tests перевіряють unknown record та нормальне відкриття збереженого файла. Без accounts — shared demo history, не приватний user cabinet.
- [ ] Запустити `python manage.py test documents.tests.test_views`, потім браузером пройти upload → result → history → original для реального text document та uncertainty/error example.
- [ ] Подати користувачу фактичні stage results і limitations. Не комітити без окремого дозволу.

**Milestone 1:** reviewer може пройти text-only flow end-to-end. Відсутність fallback явно зазначена як проміжний стан. Перевірити core перед додаванням сканів.

## Task 5: OCR/rendering та visual fallback experiment (G2)

**Files:** create `experiments/scanned_fallback.py`, `docs/experiments/scanned-fallback.md`; extend evaluation fixtures/manifest.

**Consumes:** working Milestone 1, G1 primary. **Produces:** погоджений OCR/render pipeline, visual model та власні fallback checks.

- [ ] Додати scanned examples, paired text/scan де можливо, unclear/poor scan і combined example. Позначити synthetic scans окремо.
- [ ] Обрати один поширений локальний OCR/render stack за quality, license та простотою setup і виконати smoke test на погоджених scanned examples. Альтернативний stack розглядати лише за конкретного blocker у вибраному варіанті; не проводити обов'язкове порівняння candidates і не вводити окремий OCR service.
- [ ] Запропонувати text-sufficiency/page policy: як відрізняємо image-only від зіпсованого text layer, що робимо зі змішаними сторінками та частково прочитаним PDF. Не пропускати мовчки непрочитані сторінки; погодити підтримку або явний unsupported outcome.
- [ ] Перевірити rendering усіх дозволених сторінок: image dimensions/quality, temporary cleanup та ресурсні межі; вибір render resolution не замінює 10-page limit.
- [ ] Прогнати OCR → погоджений primary, а для escalation — visual model із зображеннями того самого original PDF. Перевірити цей самий fallback на text-layer PDF.
- [ ] Перевірити structured visual evidence та власні deterministic fallback score/acceptance checks на labeled examples; не копіювати primary threshold і не приймати відповідь visual model автоматично. Відокремити виправлені помилки, нові помилки та unresolved cases.
- [ ] Погодити загальні time bounds і bounded technical retries з урахуванням SDK defaults; один classification fallback не означає дозволу на нескінченні HTTP retries.
- [ ] Подати G2 із recommendation, sanitized evidence, latency/cost та limitations; отримати погодження перед production інтеграцією. Якщо на доступних examples немає реального primary failure, не видавати штучно піднятий threshold за доведену корисність fallback.

**Exit:** OCR та visual path перевірені на прикладах, а policies для unreadable/partial content не приховані в коді.

## Task 6: Planned complete classification pipeline

**Files:** create `documents/services/ocr.py`, `documents/ai/prompts/visual.txt`; modify `documents/services/{pdf,routing,processing}.py`, `documents/ai/classification.py`, settings/dependencies/README; extend `documents/tests/{test_pipeline,test_routing,test_views}.py`.

**Consumes:** G2. **Produces:** rendering сторінок, OCR, visual classification та fallback routing у повному processing flow; конкретні contracts/types/signatures визначаються після G2.

- [ ] Додати integration tests із fake model boundary: accepted primary та established ambiguity не викликають visual model; classification uncertainty викликає її один раз зі зображеннями original PDF; semantic uncertainty або technical fallback failure не мають final accepted label; при fallback failure зберігається primary result для діагностики.

- [ ] Реалізувати G2 page/text/OCR policy. Не трактувати OCR service failure як semantic uncertainty або OTHER.
- [ ] Реалізувати один visual escalation; fallback routing може лише прийняти classification або завершити з `UNCERTAIN`. Technical exception перехоплює lifecycle і зберігає failure stage/reason.
- [ ] Зберігати primary/fallback model information та прийнятий final result; не обирати просто найбільший score двох різних scoring methods.
- [ ] Реалізувати погоджені timeout/retry/resource/temporary cleanup bounds; перевірити failure не залишає attempt помилково ACCEPTED.
- [ ] Запустити `python manage.py test documents.tests`; окремо real-parser/OCR tests на PDF fixtures та погоджений live evaluation для обох input types.
- [ ] Браузером перевірити scanned upload, text-layer escalation, established ambiguity і technical failure; перевірити history/original після кожного.
- [ ] Подати користувачу фактичні результати verification для Milestone 2; коміт лише за окремим дозволом.

**Milestone 2:** повний погоджений classification flow працює й перевірений; extraction — наступна planned capability, не випадковий бонус.

## Task 7: Extraction contract and validation checkpoint (G3)

**Files:** create `docs/decisions/field-extraction-contract.md`; extend `evaluation/manifest.json` кількома expected field examples. Не створювати окремий extraction experiment або tuning/held-out split.

**Consumes:** stable classification flow, доступний text/OCR/visual context та кілька representative examples. **Produces:** один погоджений вузький contract для Task 8: class-specific fields, structured value/status/evidence, validators, explainable field-confidence calculation, execution rule та failure behavior.

- [ ] Запропонувати невеликий корисний class-specific schema для `INVOICE`, `BOL` і `POD` — орієнтовно 3–5 полів на клас, із value type та semantics для `present`, `missing` і `unclear`. Не витягувати невизначене «все»; для `OTHER` і semantic `UNCERTAIN` extraction не запускати.
- [ ] Для кожного поля визначити structured result `value/status/evidence`. Evidence має дозволяти reviewer перевірити джерело значення; для text/OCR input перевіряється наявність цитати у переданому тексті, але це не вважається доказом правильної semantic role або правильності OCR.
- [ ] Визначити лише корисні deterministic validators для погоджених полів: формат/parseability дати, суми або identifier, допустима порожність та прості consistency checks. Валідний формат не доводить, що знайдене значення має правильну роль; semantic errors не приховувати normalization.
- [ ] Погодити одну просту explainable field-confidence formula на основі status, підтвердженого evidence, validation result і contradictions. Score описує якість extraction evidence, а не probability of correctness; не порівнювати alternative confidence mechanisms, models або thresholds.
- [ ] Зафіксувати один execution/input rule, що використовує вже погоджений processing context, без окремого порівняння text/visual/call strategies. Якщо доступного context недостатньо для надійного extraction, поле або весь extraction result позначається `unclear`/`unavailable` згідно contract, а не запускає новий classification fallback.
- [ ] Додати кілька вручну підготовлених expected examples із known values, missing/unclear cases та хоча б одним wrong-semantic-role або contradictory case. Не використовувати LLM output як ground truth і не створювати окремий extraction tuning/held-out split.
- [ ] Погодити persistence/UI representation для value, status, evidence, validation details і score. Invalid model response або extraction technical failure зберігаються окремо та не змінюють уже `ACCEPTED` classification; доступний partial extraction зберігати лише якщо це прямо дозволяє погоджений contract.
- [ ] Подати G3 як короткий reviewable contract із schema, examples, formula, limitations та failure behavior. Після погодження зафіксувати його перед Task 8; не проводити широкий model/confidence/input experiment.

**Exit:** погоджено вузький extraction contract, expected examples, explainable score і failure semantics; Task 8 може реалізувати їх без нових дослідницьких гілок.

## Task 8: Planned extraction у збереженому result flow

**Files:** create `documents/ai/extraction.py`, `documents/ai/prompts/extraction.txt`, `documents/tests/test_extraction.py`; modify `documents/models.py`, migration, `documents/services/processing.py`, result template та evaluation command.

**Consumes:** погоджений G3 contract і його expected examples. **Produces:** persisted/displayed structured value/status/evidence, validation details та explainable field-confidence без зміни accepted classification при extraction failure.

- [ ] Написати tests для погодженого schema: valid value/evidence, missing і unclear status, wrong semantic role, contradiction, evidence absent, invalid response та technical failure. Expected values брати з G3 examples; окремо перевірити, що extraction failure не змінює accepted classification.
- [ ] Запустити tests до implementation, перевірити relevant failures.
- [ ] Реалізувати один погоджений structured extraction flow і parsing без нового provider abstraction або runtime вибору між alternative models/input strategies; додати evidence checks, deterministic validators і score тільки в обсязі G3.
- [ ] Додати migration/persistence representation та result UI; score label чесно пояснює метод, не обіцяє 100% correctness.
- [ ] Перевірити restart/reopen result: поля, confidence та original PDF доступні з history.
- [ ] Запустити `python manage.py migrate`, `python manage.py test documents.tests`; виконати кілька погоджених G3 expected examples і core regression evaluation. Окремо звітувати про extraction errors і будь-які зміни classification/routing; окремий tuning/held-out extraction run не потрібний.
- [ ] Переконатися, що G3 extraction failure behavior не переписує core classification всупереч погодженому правилу; подати користувачу фактичні результати stage.

**Milestone 3:** вузький planned extraction integrated; value/status/evidence, validators, explainable score та failure isolation перевірені на expected examples, mandatory core не регресував.

## Task 9: Delivery evaluation, reviewer quickstart та review gate

**Files:** `documents/management/commands/evaluate_documents.py`, `evaluation/results/`, `README.md`; fix only files with конкретними findings.

**Consumes:** Milestones 1–3 та погоджені evaluation criteria. **Produces:** reviewable planned delivery з actual results/limitations, без автоматичного publish/commit.

- [ ] Завершити evaluation command з явними `--manifest` і `--output` arguments; live calls лише при явному запуску, не під час звичайних unit tests. Report зберігає model/prompt/config identifiers, classification outcomes, expected/actual labels, routing scores/methods, fallback use, latency/usage where available; для погоджених extraction examples — expected/actual fields, status/evidence/validation/score.
- [ ] Запустити frozen classification held-out set без threshold retuning на ньому. Показати абсолютні counts, per-class confusions, accepted errors, escalation/fallback corrections/degradations і semantic uncertainty. Extraction перевірити на погоджених G3 expected examples без окремого extraction split або calibration claim.
- [ ] Окремо виконати automated branch tests для rare failures; не видавати mock routing tests за емпіричну якість LLM.
- [ ] Перевірити fresh reviewer setup: prerequisites, dependency install, PostgreSQL startup, migration, local media, OpenAI configuration без виведення секретів, Django start та перший sample upload.
- [ ] Запустити фінальні перевірки:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test documents.tests
python manage.py evaluate_documents --manifest evaluation/manifest.json --output evaluation/results/final.json
```

Остання команда використовує live API лише за погодженого бюджету та налаштованого runtime доступу; її неможливість відображається як невиконана перевірка, не PASS. Django tests працюють на PostgreSQL і не звертаються до live API.

- [ ] Браузером пройти три короткі сценарії: один text-layer upload; один scanned document із visual fallback; повторне відкриття result/history з original PDF та extracted fields. Uncertainty, technical failure, duplicate upload і invalid limits покрити automated tests, не дублювати повною ручною browser matrix.
- [ ] Записати фактичні результати, unresolved limitations і correction iterations. Якщо змінився prompt/threshold, повторити релевантну evaluation та позначити її новою версією; не приховувати попередні failures.
- [ ] Надати G4 review: що виконано, що перевірено, що не вдалося перевірити, deviations від spec. При scope problem обговорити contingency, а не оголосити часткову реалізацію повною.
- [ ] Перед будь-яким комітом підготувати summary/tests/results і proposed commit message; чекати explicit commit approval. Push/public repository creation — лише в окремо авторизованому кроці.

**Exit:** користувач отримав concrete delivery review. Наявність плану або зелених mocks не означає, що всі criteria виконані.

## 4. Матриця покриття погодженого дизайну

| Вимога spec | Tasks / gates |
|---|---|
| Django/PostgreSQL/local media/Compose DB | 2, G0 після G1, 9 |
| 10 МБ / 10 pages, no partial truncation, rejection before attempt | 2, 4, 6 |
| New attempt per accepted upload, preserve failures/original | 2, 3, 4, 6 |
| Text-layer first working slice | 1/G1 → 2/G0 та 2E/GE → 3–4 |
| Scanned OCR, shared text primary, image fallback for both inputs | 5–6, G2 |
| ACCEPTED / semantic UNCERTAIN / technical failure | 3–6, 9 |
| Established combined ambiguity skips fallback | 1, 2E/GE, 3, 5–6 |
| One fallback, independent checks, primary diagnostics on failure | 5–6, G2 |
| Evidence-based score, deterministic routing та перевірка обмежень, no calibration claim | 1/G1, 2E/GE, 5/G2 |
| Upload/result/history/original | 4, 6, 8–9 |
| Planned fields + explainable field confidence after stable core | 7–8, G3 |
| Expected examples for extraction, no runtime oracle or separate tuning/held-out split | 7–9 |
| Representative classification evaluation/reproducible reviewer setup | 2E/GE, 5, 9; extraction expected examples — 7–9 |
| No automatic scope reduction or commits | Global constraints, 8–9 |

## 5. Self-review та handoff

План перевірити проти spec за матрицею вище: усі mandatory capabilities мають task, classification/fallback experiments завершуються concrete decision gates, technical failures не перетворюються на OTHER/UNCERTAIN, extraction не стала stretch goal або другою широкою AI-дослідницькою системою. Поведінкові сценарії задають потрібні перевірки; конкретні test assertions і Python interfaces визначаються після відповідних gates, а не наперед. Після G1/G0/GE/G2 уточнюються залежні classification contracts; G3 фіксує вузький extraction contract перед реалізацією.
