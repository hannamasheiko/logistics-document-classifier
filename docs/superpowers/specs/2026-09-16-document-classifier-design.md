# Дизайн класифікатора логістичних документів

**Дата:** 2026-09-16.
**Статус:** high-level рішення Brainstorming погоджено; цей цілісний документ очікує перегляду та явного погодження користувачем.
**Planning та implementation:** не розпочато.

Документ узагальнює погоджений дизайн із розмови. Він не є implementation plan і не замінює `AI_WORKFLOW.md` / `AI_WORKFLOW_UA.md`, які залишаються engineering history. Кандидати та відкладені рішення позначені явно; їх не слід вважати обраною реалізацією.

## 1. Мета, вимоги та обмеження

### 1.1. Вихідне завдання

Роботодавець просить базовий класифікатор PDF документів американських логістичних компаній на Django. Як приклади типів наведено Invoice, BOL та POD. Результат має містити classification і confidence score; за низького score передбачено перехід на дорожчу/visual модель. Канал приймання PDF можна обрати: UI, API, email тощо — усі канали одночасно не вимагаються.

Field extraction із confidence окремих полів у завданні позначено optional. Після завершення бажано надати посилання на Git-репозиторій. Прикладів документів і ground-truth labels роботодавець не надав.

### 1.2. Погоджений planned delivery

Вебзастосунок приймає один PDF, обробляє його, показує та зберігає classification result, score й інформацію про fallback. До результату можна повернутися разом з оригінальним документом. Field extraction та field confidence входять у planned delivery, хоча в assignment вони optional.

Час на розробку — приблизно **2–3 дні**. Користувач обрав повніший scope з урахуванням дозволеного AI-assisted development, але зі збереженням пріоритету core classifier. Це не production-scale ML або calibration research project.

### 1.3. Принципи прийняття рішень

- Користувач погоджує значущі рішення про scope, архітектуру, реалізацію та Git history.
- Розвиток ітеративний: спочатку working vertical slice, перевірка, потім наступні capabilities.
- Вибір конкретних моделей, confidence formula та thresholds потребує практичної перевірки; цей документ не призначає їх довільно.
- До Planning переходимо лише після явного погодження цього документа. Коміти потребують окремого дозволу.

## 2. Scope / out-of-scope

### 2.1. Planned scope

- Django UI: upload flow, result page, мінімальна history/list view.
- Один PDF — один документ; документ може бути багатосторінковим.
- Початкові ліміти: **до 10 сторінок і до 10 МБ**. Збільшення обговорюється окремо за потреби.
- Text-layer PDF у першій ітерації; scanned PDF у наступній обов'язковій ітерації.
- Класи `INVOICE`, `BOL`, `POD`, `OTHER` з окремим semantic `UNCERTAIN`.
- Primary text classification та один спільний visual fallback для обох видів PDF у завершеному classification flow.
- Збереження оригіналів, metadata та результатів, включно з інформацією про model/fallback.
- Field extraction + field confidence як наступна запланована capability після стабільного core pipeline.
- Representative evaluation та відтворюваний запуск reviewer'ом.

### 2.2. Поза поточним scope

- Сегментація PDF-пакетів на кілька документів.
- Додаткові класи документів, зокрема окремий `BOL_POD`.
- Authentication, user accounts, повноцінний user cabinet.
- External object storage.
- Deduplication, result cache за file hash та пов'язана система cache invalidation.
- Окремий `primary text → stronger text` fallback.
- Background workers і queues для першої версії.
- Обов'язковий dataset на 60–100 документів або повноцінне calibration study.
- Multi-provider research без конкретної суттєвої технічної потреби.

Публічний deployment не погоджено як вимогу. Використання Compose для всього застосунку також не погоджено; поточне рішення стосується БД.

### 2.3. Пріоритет і contingency

Core classification pipeline реалізується й перевіряється першим. Після стабільного vertical slice додається planned extraction, яка не повинна залишити core pipeline незавершеним або погіршити його.

Extraction не є лише stretch goal «якщо залишиться час». Відмову від неї можна обговорити лише за реальної проблеми з часом або більшого, ніж очікувалося, обсягу core work. Перехід до фонової обробки можливий за практичної необхідності та наявності часу, а не як поточний план.

## 3. Document taxonomy та семантика результатів

### 3.1. Класи

| Клас | Погоджене значення |
|---|---|
| `INVOICE` | Рахунок за перевезення або логістичні послуги. Commercial Invoice на товари сюди не входить |
| `BOL` | Bill of Lading як окремий документ; підпис сам по собі не є достатньою підставою змінити тип на POD |
| `POD` | Окреме підтвердження доставки: Proof of Delivery / Signature Proof of Delivery / Delivery Receipt відповідного змісту |
| `OTHER` | Документ, зміст якого зрозумілий, але який не належить до цільових типів. Наприклад, Commercial Invoice на товари |

Назва або одне спільне поле не є універсальним правилом класифікації. Рахунок може посилатися на BOL; різні типи можуть містити адреси, дати, вагу та інформацію про доставку.

### 3.2. Результат обробки відокремлений від класу

| Результат | Значення |
|---|---|
| `ACCEPTED` | Класифікація primary або fallback пройшла погоджені перевірки прийнятності |
| `UNCERTAIN` | Pipeline завершився, але надійної класифікації немає; зберігається пояснення |
| Technical processing failure | Обробку не вдалося завершити через технічну помилку, наприклад parser/API failure або timeout |

Це семантичні категорії дизайну, а не затверджена схема Django enum/полів. `OTHER` не замінює uncertainty, unreadability чи technical failure. Відсутність придатного тексту в першій ітерації не робить документ `OTHER`.

### 3.3. Combined BOL/POD

- Якщо primary достатньо надійно встановлює, що документ комбінований BOL/POD, повертаємо `UNCERTAIN` з поясненням **без fallback**. Окремий клас для нього свідомо не входить до поточної taxonomy.
- Якщо primary не може визначити, чи це BOL, POD або combined BOL/POD, це classification uncertainty, яка в завершеному flow запускає один fallback.
- Конкретні ознаки й перевірки надійності такого встановлення відкладено. Самої заяви моделі недостатньо як уже визначеного правила.
- Попередня пропозиція автоматично відносити комбіновані форми до BOL не є чинним рішенням.

### 3.4. Що встановлено дослідженням

Переглянуто FedEx/FedEx Freight, UPS, DHL, XPO та Old Dominion як робочу вибірку на ринку США, не як доведений рейтинг «топ-5». XPO і документація FedEx розрізняють BOL, Delivery Receipt/SPOD та Freight Bill/Invoice; Old Dominion також підтверджує ці документи. Наявність типу в кабінеті не означає отримання відкритого заповненого PDF.

Офіційна форма FedEx Custom Critical поєднує BOL/POD, спільний опис вантажу та записи відправлення/доставки. Інструкції відривати ці частини не знайдено; гіпотезу про обов'язкову відривну форму не підтверджено. Заповнений після доставки примірник цієї форми не перевірявся.

Знайдені бланки та публічний POD — опорні приклади, не готовий evaluation set. Повного комплекту з 15 заповнених документів для п'яти перевізників не отримано. Інші досліджені типи — Rate Confirmation, Lumper Receipt, Weight Ticket, Packing List, Air Waybill, Certificate of Origin та Freight Claim — лише кандидати на майбутнє розширення.

Опорні джерела з Brainstorming:

- [XPO Document Finder](https://www.xpo.com/help-center/document-finder/)
- [Old Dominion forms](https://www.odfl.com/us/en/resources/fill-print-forms.html) та [FAQ](https://www.odfl.com/us/en/resources/freight-knowledge/old-dominion-faqs.html)
- [FedEx Custom Critical BOL/POD](https://www.fedex.com/content/dam/fedex/us-united-states/shipping/images/BillofLading.pdf)
- [FedEx document types, API guide 2021](https://www.fedex.com/us/developer/downloads/pdfs/2021/FedEx_WebServices_DevelopersGuide_v2021.pdf#page=919)

## 4. Архітектура та відповідальність компонентів

Нижче наведено логічні відповідальності. Це не рішення створювати окремі сервіси, framework layers чи конкретну структуру Python-модулів.

| Компонент / відповідальність | Роль |
|---|---|
| Django UI | Прийняти PDF, запустити обробку, показати результат, історію та доступ до оригіналу |
| Приймання й валідація | Перевірити тип і погоджені ліміти до створення attempt; не обрізати документ мовчки |
| Отримання тексту | Direct text extraction для text-layer PDF; OCR для scanned PDF у наступній ітерації |
| Primary text classifier | На основі отриманого тексту повернути candidate class і structured class-specific features/evidence |
| Routing | Детерміновано оцінити достатність і суперечності evidence, розрахувати routing score, прийняти результат, визначити semantic uncertainty або передати документ на один visual fallback |
| Visual fallback | Отримати зображення сторінок original PDF; повторно оцінити класифікацію, коли primary потребує escalation |
| Field extraction | Заплановане витягування полів із field confidence після стабільного core pipeline; деталі відкладено |
| Persistence | Зберегти PDF, metadata, classification/confidence і model/fallback information, а також extraction results при додаванні capability |

### 4.1. Погоджені технологічні межі

- **Django** — вимога assignment та основа UI/persistence.
- **OpenAI API** — провайдер за замовчуванням: користувач має досвід, доступ і billing. Інший провайдер розглядається лише за суттєвої переваги для конкретної важливої вимоги.
- **PostgreSQL** — єдина relational DB; **мінімальний Docker Compose для БД** — погоджений спосіб спростити запуск reviewer'ом.
- **Django local media storage** — original PDF; у relational data зберігається посилання/шлях до файла, не його вміст як PDF blob.
- **Синхронна обробка** в HTTP request — перша версія. Користувач очікує результат; тривалі операції обмежуються та помилки обробляються. Точні timeout settings не визначені.

## 5. Processing flow та ітеративний розвиток

### 5.1. Iteration 1 — initial working vertical slice

```text
Text-layer PDF
      |
      v
Text extraction
      |
      v
Primary text classifier
      |
      v
Routing
      |
      +-- Результат можна прийняти ------> ACCEPTED
      |
      +-- Результат не можна прийняти ---> UNCERTAIN
                                          (тимчасово без fallback)

Технічна помилка на будь-якому кроці ---> TECHNICAL FAILURE
                                        (не semantic UNCERTAIN)
```

Це проміжний working vertical slice, а не завершена версія для здачі: fallback тут ще відсутній. Файл, для якого неможливо отримати придатний текст підтримуваним способом, не класифікується як `OTHER`.

### 5.2. Iteration 2 — planned complete classification flow

```text
Text-layer PDF                         Scanned PDF
      |                                     |
      v                                     v
Direct text extraction                     OCR
      |                                     |
      +------------------+------------------+
                         |
                         v
              Primary text classifier
                         |
                         v
                  Routing decision
                         |
      +------------------+----------------------+
      |                  |                      |
      v                  v                      v
Результат можна   Встановлена taxonomy   Classification
прийняти          ambiguity             uncertainty
      |                  |                      |
      v                  v                      v
  ACCEPTED           UNCERTAIN          Один visual fallback
                  (без fallback)        <--- зображення сторінок
                                              original PDF
                                                |
                                                v
                                     Власні перевірки fallback
                                                |
                                     +----------+----------+
                                     |                     |
                                     v                     v
                                  ACCEPTED             UNCERTAIN
                                                    (із поясненням,
                                                   без нових викликів)

Технічна помилка на будь-якому кроці ---> TECHNICAL FAILURE
                                        (не semantic UNCERTAIN)
```

Visual fallback спільний для scanned і text-layer PDF. Він отримує original page images, а не лише повторно той самий витягнутий текст. OCR дає можливість використати той самий primary text classifier для сканів.

### 5.3. Наступна planned capability — extraction

Після стабільного core classification pipeline додається field extraction із field confidence, відображенням і збереженням результатів. Конкретні поля, schema, момент виклику extraction щодо classification outcome та механізм field confidence не затверджено. Діаграми вище описують classification flow; вони не визначають ще не погоджену extraction routing logic.

## 6. Confidence та правила escalation

### 6.1. Погоджене значення

Confidence потрібен насамперед для рішення **accept classification vs fallback**. Він окремий від OCR quality та не повинен без перевірки подаватися як статистично точна ймовірність правильності.

Низький score не означає `OTHER` і сам по собі не пояснює причину ненадійності. Сильніша модель може допомогти з інтерпретацією; зображення може додати інформацію, втрачену під час extraction/OCR. Жодне з цього не гарантує виправлення й не змінює меж taxonomy.

### 6.2. Evidence-based confidence/routing

LLM отримує текст після direct PDF extraction або OCR і повертає candidate class разом зі structured class-specific features та evidence. Для ознак використовується явна семантика на кшталт `present / absent / unclear`, а evidence має дозволяти перевірити, на якій частині документа ґрунтується результат.

Backend не приймає модельний score як готову відповідь. Він детерміновано перевіряє достатність і суперечності evidence та розраховує evidence-based routing score. Якщо погоджені acceptance checks пройдено, classification стає `ACCEPTED`; якщо evidence недостатні або суперечливі, завершений flow виконує один visual fallback, а Iteration 1 тимчасово повертає `UNCERTAIN`.

Для text path короткі evidence-цитати перевіряються на наявність у переданому тексті. Це підтверджує джерело, але не гарантує правильної semantic interpretation або правильності OCR. Ознаки мають розрізняти класи: спільні адреси, дати чи shipment identifiers самі по собі не визначають тип документа; відсутність необов'язкового поля не повинна автоматично знижувати score. Важливі contradictions не приховуються високою сумою балів.

Відсутність ознак `INVOICE`, `BOL` або `POD` не доводить `OTHER`: документ може бути неповним, погано прочитаним або неоднозначним. Прийняття `OTHER` також потребує погоджених evidence та backend checks.

Visual fallback отримує зображення сторінок original PDF і повертає structured visual evidence. Його результат проходить власні deterministic acceptance checks; primary formula, threshold і перевірка текстових цитат не переносяться на нього автоматично.

Конкретні class-specific features, правила достатності й суперечностей, формула score та thresholds визначаються і практично перевіряються на невеликому labeled evaluation set. Це уточнення одного погодженого механізму, а не паралельний вибір між різними confidence approaches. Score описується як explainable routing signal, а не калібрована probability of correctness.

### 6.3. Погоджені правила fallback

1. Якщо primary проходить погоджені checks — приймаємо результат.
2. Надійно встановлена combined BOL/POD ambiguity — одразу `UNCERTAIN` із поясненням, без fallback.
3. Classification uncertainty в завершеному flow — максимум один visual fallback на attempt.
4. Fallback проходить власні checks — його результат стає final accepted classification.
5. Fallback залишається ненадійним або документ реально неоднозначний — `UNCERTAIN` із поясненням, без додаткових модельних викликів лише заради вищого confidence.
6. Technical failure fallback — зберігаємо failed attempt і доступний primary result для діагностики; primary не стає accepted classification.
7. Primary threshold/confidence evaluation не переносимо автоматично на fallback. Його спосіб оцінювання перевіряємо окремо.

Обмеження «один fallback» стосується classification escalation. Конкретні правила технічних retries не визначено.

## 7. Persistence та користувацький сценарій

### 7.1. UI flow

Користувач вибирає PDF і натискає «Класифікувати». Система перевіряє вхід, обробляє прийнятий документ синхронно, зберігає результат і показує result page. У history/list view можна відкрити попередній результат разом з original PDF.

Результат містить клас, score та інформацію про застосування fallback; для uncertainty або failure — відповідне пояснення. Planned extraction додає extracted fields та їх confidence. Точний layout і тексти UI не визначені.

### 7.2. Категорії збережених даних

- Document metadata.
- Original PDF у local media storage.
- Classification result та confidence.
- Інформація про використану модель і fallback.
- Extracted fields та їх confidence після реалізації extraction.
- Для technical failure після прийняття PDF — запис про невдалу обробку, причина та original PDF.
- При failure fallback — також доступний primary result для діагностики.

Конкретна Django schema, кількість моделей, поля metadata, representation спроб і configuration/version information залишаються відкладеними. Повний OCR-текст і сирі API responses не погоджені як обов'язкові дані для збереження.

### 7.3. Приймання, помилки та повторні завантаження

- Файл, який не пройшов початкову перевірку типу або лімітів, відхиляємо до створення attempt; він не потрапляє в історію.
- Не класифікуємо лише перші сторінки при перевищенні ліміту й не приховуємо часткову обробку.
- Technical failure після прийняття PDF зберігаємо в history разом з документом і причиною.
- Кожне прийняте повторне завантаження створює нову processing attempt та новий запис, зокрема після failure. Попередній запис не перезаписуємо.
- Deduplication/result cache за file hash не додаємо: результат залежить також від model/prompt/pipeline/fallback configuration, а коректний reuse потребував би versioning та cache invalidation, не виправданих поточним scope.

## 8. Перевірка та критерії завершення

### 8.1. High-level acceptance criteria

Planned delivery має продемонструвати й перевірити:

- **Classification:** text-layer та scanned PDF; `INVOICE`, `BOL`, `POD`, `OTHER`; зафіксовані помилки та обмеження.
- **Routing:** прийняття primary result, escalation до visual fallback, завершення fallback як `ACCEPTED` або `UNCERTAIN`.
- **Taxonomy ambiguity:** встановлений combined BOL/POD → `UNCERTAIN` без fallback.
- **Technical failures:** відмінність від semantic uncertainty; неприйнятий primary result не видається за final accepted result.
- **Planned extraction:** витягування погоджених полів із field confidence та чесним описом значення score.
- **End-to-end:** upload → processing → result → повторне відкриття з history та original PDF; погоджені ліміти й повторні завантаження.
- **Reproducibility:** reviewer може запустити проєкт за перевіреною інструкцією та повторити перевірки.

### 8.2. Межі evaluation

Передбачено невеликий representative evaluation set, реалістичний для take-home. Конкретні документи, розмір, metrics, numerical targets, class-specific evidence rules, score formula та thresholds зараз не встановлюються.

Correctness extraction перевіряється на підготовлених evaluation examples із відомими очікуваними значеннями. Це **не вимога незалежного runtime ground-truth механізму для кожного поля**. Runtime validation/evidence додаються там, де це обґрунтовано; field-confidence mechanism відкладений.

Під час Brainstorming обговорено як можливі способи оцінювання: classification errors, помилки серед accepted results, частку escalation, виправлення та погіршення після fallback, час і вартість. Це не затверджений детальний протокол. Успішний API-виклик не є доказом правильної класифікації; відсутність помилок на кількох простих прикладах не доводить надійність routing.

## 9. Ключові trade-offs та обмеження

| Рішення | Обґрунтування з обговорення | Компроміс / межа |
|---|---|---|
| Text-first iteration | Спершу перевірити простий working vertical slice | До другої ітерації немає сканів і fallback; це ще не повна здача |
| OCR → спільний text classifier → visual fallback | Повторно використовуємо перевірений текстовий шлях; fallback отримує original images | OCR додає крок і може втрачати інформацію; visual не гарантує виправлення |
| Один classification fallback | Обмежує час і вартість, допускає чесний невизначений результат | Частина документів залишиться `UNCERTAIN` |
| Окрема semantic uncertainty | Не примушуємо комбіновані або ненадійні випадки до класу | Потрібні практично перевірені checks, а не лише заява моделі |
| Синхронна обробка | Пропорційна scope, без worker/queue | Очікування в HTTP request і ризик timeout; перегляд за потреби та наявності часу |
| Мінімальне persistence з PDF | Повернення до результатів і перевірка за оригіналом | Додає DB/files lifecycle; точні механізми ще не обрані |
| PostgreSQL замість SQLite | Користувач має досвід і невеликий implementation overhead; погоджено Compose для запуску БД | SQLite також достатньо для поточного функціоналу й не потребує сервера; PostgreSQL додає prerequisite reviewer'у |
| Local media storage | Достатньо для погодженого сценарію без складнішого сховища | Не обрано external object storage або production deployment design |
| Нова attempt на кожне завантаження | Зберігає попередні результати й не вводить некоректний reuse при зміні конфігурації | Повторні model calls мають додаткову вартість |
| Planned extraction після core | Повніший AI-assisted delivery без втрати пріоритету classifier | Реальна нестача часу може вимагати окремого перегляду scope |
| Evidence-based confidence як перевірюваний routing signal | Structured class-specific evidence та deterministic backend checks дають explainable routing; не обіцяємо статистичної точності без доказів | Features, formula і thresholds залежать від практичної evaluation; evidence від LLM може бути семантично помилковим |

## 10. Deferred decisions та статус погодження

### 10.1. До відповідного experiment/evaluation

- Конкретні OpenAI primary/fallback models та endpoints і точний structured-output format.
- Class-specific feature table/evidence, правила достатності й суперечностей, deterministic score formula, threshold та окремі fallback checks.
- Практична поведінка evidence-based routing для `present / absent / unclear`, `OTHER` і combined BOL/POD.
- Конкретні evaluation documents, розмітка, розмір набору, metrics та numerical targets.
- Практична користь fallback, його помилки й обмеження.

### 10.2. До Planning / implementation з погодженням значущих рішень

- PDF parser, OCR інструмент, деталі визначення придатності тексту та обробки вхідних PDF.
- Конкретні timeouts, technical retries, structured-output format.
- Django models, поля, enum names, representation primary/fallback attempts та configuration information.
- Деталі UI, відкриття original PDF, pagination, видалення записів/файлів, повідомлення.
- Версії залежностей, reviewer quickstart, точні команди та конфігурація запуску.
- Extraction fields/schema, persistence representation, місце extraction у flow та field-confidence mechanism.

Відкладання рішення означає, що його ще потрібно обрати й перевірити на відповідному етапі, а не що готова система може залишити його невизначеним. Цей документ не доручає реалізувати всі обговорені альтернативи.

### 10.3. Approval gate

Усі три mandatory high-level Brainstorming decisions закрито: planned extraction scope, місце спільного visual fallback, критерії завершення з уточненням evaluation correctness для extraction. Додаткових mandatory high-level питань перед підготовкою цього документа не виявлено.

**Цей design document ще очікує перегляду та явного погодження користувачем.** Лише після цього можливий перехід до Planning. На момент написання документа реалізації, практичного model experiment та перевірки application behavior немає; описані flows є погодженим дизайном, а не заявою про працездатність готового застосунку.
