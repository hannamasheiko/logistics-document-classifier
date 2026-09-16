# AI-assisted engineering history

Це curated record змістовної інженерної роботи, а не транскрипт. Оригінальні промпти нижче збережені без мовного редагування; англійський переклад розташовано одразу після кожного. Короткі підтвердження узагальнено в рішеннях, а не відтворено як окремі етапи.

## 1. Правила співпраці

Перед проєктуванням користувач замовив repository-level `AGENTS.md` із правилами прийняття рішень, явного погодження комітів, перевірки результатів, захисту секретів та ведення цього журналу. Асистент створив файл, згрупував 15 правил за темами та прочитав його назад для перевірки. Користувач погодив інструкції й заборонив поки робити коміт.

**Original approval (English):**

> I approve `AGENTS.md` as the repository instructions. Do not commit it yet. We can proceed to the next step.

Початкова заборона створювати `AI_WORKFLOW.md` стосувалася лише кроку створення інструкцій. Поточний checkpoint створено за наступним явним запитом користувача. Погодження інструкцій не є погодженням архітектури чи реалізації.

## 2. Brainstorming — in progress

**Checkpoint:** 2026-09-15. **Статус:** незавершений; фінальний дизайн не погоджено. Planning та implementation не розпочато. Цей logical stage не завершений комітом.

### 2.1. Вихідне завдання та рамки аналізу

Роботодавець просить базовий класифікатор PDF логістичних документів США на Django, із confidence та переходом на дорожчу/visual модель при низькому score. Invoice, BOL і POD наведено як приклади. Витягування полів із confidence — optional. Канал подання PDF можна обрати; репозиторій бажано надати після завершення.

Прикладів PDF та правильних міток роботодавець не надав. Асистент застосував Superpowers Brainstorming; початковий огляд виявив лише `AGENTS.md` серед звичайних файлів, `git log` повідомив, що комітів немає.

**Оригінальний промпт (українською):**

> Починаємо роботу над тестовим завданням.
>
> Нижче я наводжу **оригінальний текст завдання від роботодавця без змін**:
>
> **Короткий опис завдання:**
> зробити базовий док-класифікатор для документів американських логістичних компаній (наприклад, Invoice, BOL, POD тощо)
> PDF на вході (у будь-якому вигляді - UI upload, API request, email тощо), класифікація з confidence score. зміна моделі на дорожчу/visual при низькому скорі
>
> опціонально - витягти поля + confidence score для них
> стек - Django, будь-який OCR/LLM на твій розсуд
>
> по готовності бажано залити на git і надіслати лінк на репо (можна публічно, або можу надіслати username, якщо буде приватним)
>
> **На цьому етапі використай Superpowers Brainstorming.**
>
> Поки що **нічого не реалізовуй, не встановлюй залежності та не ініціалізуй Django**. Я хочу спочатку пройти повноцінний етап аналізу й проєктування рішення разом із тобою.
>
> Під час brainstorming:
>
> - проаналізуй вимоги завдання та відокрем явні вимоги від припущень;
> - визнач неоднозначності й питання, які реально впливають на дизайн;
> - допоможи визначити розумний scope тестового завдання;
> - розглянь архітектуру обробки PDF, включно з text-based та scanned/image PDFs;
> - окремо й критично розбери `confidence score`: що саме він має означати в цій системі, як його можна отримувати та наскільки він є надійним;
> - окремо розбери умову переходу на дорожчу/visual модель при низькому score: коли такий fallback дійсно додає цінність і яку нову інформацію або capability він дає;
> - визнач, які рішення щодо document taxonomy (Invoice, BOL, POD, `OTHER`, можливі додаткові типи) нам необхідно прийняти;
> - optional field extraction поки розглядай як окреме розширення після основного classification pipeline;
> - запропонуй альтернативи там, де вони справді суттєві, з trade-offs, але **не приймай значущі рішення замість мене**.
>
> Не намагайся одразу видати фінальну архітектуру та implementation plan. Веди brainstorming інтерактивно відповідно до Superpowers workflow: досліджуй проблему, став мені питання, коли потрібне моє рішення, і поступово формуй дизайн.
>
> До Planning перейдемо окремо лише після того, як я явно погоджу дизайн.

### 2.2. Taxonomy: обмежити першу ітерацію, перевірити неоднозначність

Користувач обрав ітеративний розвиток: спочатку три типи, перевірка, потім розширення. Асистент уточнив, що в завданні BOL означає Bill of Lading, а не загальне «bill». Погоджено `OTHER` для зрозумілих сторонніх документів, окремо від невпевненості, нечитабельності та технічних помилок. Один PDF — один документ, можливо багатосторінковий; сегментація пакетів поза scope.

`INVOICE` звужено за вибором користувача до рахунків за перевезення/логістичні послуги. Commercial Invoice на товари — `OTHER` у першій версії.

Асистент спочатку пропонував залишати підписаний/комбінований BOL у класі BOL. Користувач попросив докази й реальні офіційні приклади перед погодженням меж BOL/POD.

**Оригінальний промпт (українською):**

> Так, дивись, давай бери за основу топ-5 американських компаній за доставкою, наприклад FedEx, American Express, DPT, UPC і так далі. І подивись перелік їхніх документів, які вони передають, як BOL, POD, invoice. І сформуй з них перелік, який чітко класифікується. Там, де ти позначив документи, які на собі мають і ту, і ту форму. Скоріше за все, це відривна форма, коли документ розділяється на дві частини: одна залишається як BOL, інша як POD. Тому документ в первинному плані, він має обидві ці частини, але по факту ми маємо розпізнавати їх окремо. Якщо ти знайдеш інформацію, що BOL і POD все одно залишаються в одному документі, то це треба вводити додатковий класифікатор, як BOL слеш POD. Але це буде потім, на первинному етапі ми маємо чітко класифікувати документи. Роби цей аналіз.

**Дослідження та корекція:**

- Асистент явно обрав FedEx/FedEx Freight, UPS, DHL, XPO та Old Dominion як робочу вибірку на ринку США, не як доведений рейтинг топ-5. Компанії й підрозділи мають різні види перевезень; їхні форми не є одним універсальним комплектом.
- XPO та документація FedEx розрізняють BOL, Delivery Receipt/SPOD і Freight Bill/Invoice. Old Dominion підтверджує окремі BOL, POD та invoices.
- Знайдено відкриті офіційні бланки BOL, POD у державному архіві та офіційні матеріали про рахунки. Не отримано повного набору з 15 заповнених зразків. Частина клієнтських документів доступна лише після входу.
- Форма FedEx Custom Critical має обидві назви, спільний опис вантажу, записи відправлення й доставки та позначення копій для сторін. Інструкцію відривати одну частину від іншої не знайдено. Фізичний поділ не доведений; заповнений після доставки екземпляр цієї форми не перевірено.
- Остаточно користувач погодив: комбінований BOL/POD повертає невизначений результат із поясненням; це не `OTHER`, не примусовий BOL/POD і не новий клас у першій ітерації. Попередню пропозицію автоматично відносити комбіновані форми до BOL відхилено.
- Кандидати на майбутнє розширення: Rate Confirmation, Lumper/Unloading Receipt, Weight Ticket, Packing List, Air Waybill, Certificate of Origin, Freight Claim. Їх не додано до поточного scope.

**Опорні джерела:**

- [XPO Document Finder](https://www.xpo.com/help-center/document-finder/)
- [Old Dominion: форми](https://www.odfl.com/us/en/resources/fill-print-forms.html), [FAQ](https://www.odfl.com/us/en/resources/freight-knowledge/old-dominion-faqs.html)
- [FedEx Freight BOL](https://www.fedexfreight.com/content/dam/web/us/documents/uniform-straight-bol.pdf)
- [FedEx Custom Critical BOL/POD](https://www.fedex.com/content/dam/fedex/us-united-states/shipping/images/BillofLading.pdf)
- [FedEx POD у Connecticut Siting Council, сторінки 4–6](https://portal.ct.gov/-/media/csc/2_ems-medialibrary/fairfield/congressst/sprint/emsprint051171018filingcongressstpdf.pdf?hash=7E87BC50025933C9CBC9EA7DEFE1B8F0&rev=029cdcd94e2d440d871e8b58598e1b33#page=6)
- [FedEx API guide 2021, типи документів, сторінки 919–921](https://www.fedex.com/us/developer/downloads/pdfs/2021/FedEx_WebServices_DevelopersGuide_v2021.pdf#page=919)
- [UPS Freight Invoice Instructions](https://dtciportal.ups.com/tools/forms/freight_invoice.pdf) — пошуковий індекс надав зміст, пряме відкриття інструментом завершилося помилкою.
- [C.H. Robinson: необхідні документи](https://www.chrobinson.com/en-us/carriers/carrier-support/support-required-paperwork/)

### 2.3. Ітерації PDF processing і fallback

**Оригінальний промпт (українською):**

> Я для початку хочу зробити PDF із текстовим шаром. Тобто, щоб ми пройшли, от це в нас там три класи, і PDF — окремий документ подається із текстом. Коли ми розробимо, відтестуємо і будемо впевнені, що все працює, тоді ускладнимо до сканованого PDF теж, що є зображенням. Тобто я обов'язково це хочу включити, але коли ми пройдемо цей перший базовий шар.

**Погоджений напрям:**

1. Перша ітерація: text-layer PDF → витягування тексту → недорога текстова модель → classification result.
2. Наступна обов'язкова ітерація: scanned PDF → OCR → той самий текстовий класифікатор → за потреби visual-модель з оригінальними зображеннями.
3. Optional field extraction розглядається після основного classification pipeline.

Обговорено альтернативу «дешева visual → сильніша visual»; користувач обрав OCR → text → visual fallback. Асистент уточнив власне попереднє спрощення: сильніша текстова модель потенційно може краще інтерпретувати той самий текст, але не відновить інформацію, втрачену під час extraction/OCR. Visual fallback може додати інформацію зі сторінки, проте не усуває неоднозначність taxonomy і не гарантує виправлення. Конкретні моделі й умови маршрутизації залишаються відкритими.

### 2.4. Confidence: заперечення проти передчасного вибору

**Оригінальний промпт (українською):**

> Загалом погоджуюся з трактуванням confidence як оцінки впевненості в правильності класифікації, окремої від OCR quality. Але поки не хочу фіксувати рішення, що в першій робочій версії це має бути саме self-reported score від LLM.
>
> Оскільки за умовою завдання низький confidence має запускати fallback на дорожчу/visual модель, цей score впливаватиме на routing системи, а не буде лише інформаційним полем.
>
> Тому перед вибором підходу хочу окремо розібрати:
>
> - які сигнали впевненості реально доступні для моделей/API, які ми можемо використати для classification;
> - чи можемо отримати більш об'єктивний сигнал, ніж просто попросити LLM згенерувати число `0–1` — наприклад model probabilities/logprobs, якщо обраний API/model це підтримує;
> - які практичні альтернативи self-reported confidence мають сенс саме для невеликого take-home без побудови окремої ML-системи;
> - як confidence/routing signal можна перевірити на невеликому labeled evaluation set;
> - і тільки після цього вибрати конкретну реалізацію confidence для першої версії.
>
> Self-reported LLM confidence можемо залишити одним із кандидатів або V0, але я не хочу поки автоматично робити його фінальним routing signal.

Асистент визнав передчасність рекомендації self-reported score. Досліджено logprobs, self-report, узгодженість повторних відповідей, перевірки ознак і другий LLM-перевіряльник. Жоден з них не затверджено як остаточну формулу.

Logprob характеризує ймовірність вихідного токена за конкретного контексту, не автоматично ймовірність правильності класу. Обговорено короткі коди класів, необхідність перевірити tokenization, неповноту top-logprobs, непридатність усереднення всього JSON та відмінність ranking signal від calibration. OpenAI Docs застосовано для перевірки документації. Реальних викликів моделей не було.

**Оригінальний промпт (українською):**

> PI provider у нас уже фактично обраний: **OpenAI API**. Я вже маю з ним практичний досвід, налаштований доступ і billing, тому для цього take-home хочу використовувати його за замовчуванням.
>
> Іншого провайдера варто розглядати лише якщо під час проєктування з'ясується, що для конкретної важливої вимоги цього завдання він дає суттєву технічну перевагу над OpenAI. Не хочу додавати multi-provider research без конкретної потреби.
>
> Також врахуй constraint по scope: це take-home assignment з приблизно **2–3 днями доступного часу на розробку**. Тому рішення повинно бути технічно обґрунтованим і демонструвати ключові вимоги завдання, але без перетворення роботи на production-scale ML/calibration research project.
>
> Щодо confidence наразі зафіксуй:
>
> - self-reported LLM confidence не вважаємо каліброваною ймовірністю правильності;
> - logprobs в OpenAI API виглядають як потенційно корисніший routing signal і їх варто практично перевірити для конкретної обраної моделі/endpoint;
> - confidence у нашій системі насамперед потрібен для рішення `accept classification vs fallback`, а не для заяви про статистично точну ймовірність;
> - не закладаємо обов'язковий dataset на 60–100 документів або повноцінне calibration study;
> - натомість передбачимо невеликий representative evaluation set, реалістичний для take-home, щоб перевірити classification та поведінку routing/fallback;
> - конкретний threshold і остаточний спосіб розрахунку confidence не фіксуємо без практичної перевірки.

**Погоджено:** OpenAI за замовчуванням, бюджет 2–3 дні, невеликий evaluation set без затвердженої кількості. Пропозицію асистента про 60–100 документів не прийнято як вимогу. Logprobs — кандидат, self-report — не фінальне рішення. Score не є OCR quality.

**Ідеї перевірки, ще не фінальний протокол:** порівняти classification errors, частку прийнятих результатів, помилки серед прийнятих, частку помилок, спрямованих на fallback, та виправлення/погіршення після fallback. Не налаштовувати threshold на фінальних тестових прикладах; уникати витоку однакових шаблонів. Якщо помилок замало, не заявляти доведену надійність routing.

**Джерела:** [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [OpenAI Responses](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), [Guo et al., calibration](https://proceedings.mlr.press/v70/guo17a.html). Наявність параметрів у документації не замінює перевірки обраної моделі/endpoint.

### 2.5. UI та persistence: від одноразової відповіді до мінімальної історії

Користувач обрав вебінтерфейс завантаження PDF з кнопкою класифікації та результатом: тип, score, інформація про fallback. Варіант лише API endpoint не обрано.

Асистент запропонував обробку без persistence. Користувач заперечив проти автоматичного спрощення й попросив оцінити use case з optional extraction. Обговорено одноразовий результат/JSON, історію лише результатів та історію з оригінальним PDF. Field extraction саме по собі не потребує persistence; повернення до результату й перевірка за оригіналом дають йому конкретну цінність.

**Оригінальний промпт (українською):**

> Обираю persistence, але хочу залишити його мінімальним і пропорційним scope тестового.
> Основний сценарій бачу так: користувач завантажує PDF → система обробляє його → показує classification result і, якщо реалізуємо optional extraction, extracted fields → результат зберігається, щоб до нього можна було повернутися разом з оригінальним документом.
> Тому наразі бачу сенс зберігати metadata документа, original PDF, classification result і confidence, інформацію про використану модель/fallback, а також extracted fields та їх confidence, якщо реалізуємо extraction.
> Для persistent relational data я схиляюся до **PostgreSQL**, оскільки вже добре з ним працюю і його використання не створює для мене значного додаткового implementation overhead. Але перш ніж зафіксувати це рішення, оціни, чи дає PostgreSQL у цьому проєкті достатню практичну користь порівняно з SQLite, з урахуванням простоти запуску проєкту reviewer'ом.
> Самі PDF можна зберігати через Django local media storage, якщо під час brainstorming не з'явиться причина для складнішого рішення.
> Не хочу перетворювати persistence на повноцінний user cabinet: без authentication, user accounts, external object storage чи додаткової інфраструктури без окремої потреби.
> Достатньо upload flow, result page і мінімальної history/list view.
> Продовжуй brainstorming.

**Альтернативи й рішення:** SQLite достатньо для поточних даних і простіше запускається; PostgreSQL не потрібен лише через JSON fields. Аргумент користувача — практичний досвід і малий overhead для нього. Асистент запропонував PostgreSQL як єдину БД з мінімальним Docker Compose для БД, щоб спростити відтворюваний запуск reviewer'ом; користувач погодив. Підтримка двох БД не входить у погоджений напрям. Compose для всього застосунку не погоджували.

**Погоджено зберігати:** metadata, original PDF, classification/confidence, model/fallback information; extracted fields/confidence лише якщо optional extraction буде реалізовано. PDF — local media, relational data — PostgreSQL. Точну модель даних ще не спроєктовано. Пропозиції асистента щодо статусів помилок та детальних записів спроб не слід вважати погодженою схемою.

**Джерела порівняння:** [Django JSONField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#jsonfield), [Django FileField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#filefield), [Django databases](https://docs.djangoproject.com/en/5.2/ref/databases/), [SQLite: appropriate uses](https://www.sqlite.org/whentouse.html).

## 3. Зведення прийнятих рішень

| Область | Погоджено |
|---|---|
| Процес | Інтерактивний Brainstorming; фінальний дизайн і Planning потребують окремого погодження |
| Час | Приблизно 2–3 дні розробки |
| Стек | Django, OpenAI API за замовчуванням |
| Вхід | Один PDF — один документ; спочатку текстовий шар; скани наступною обов'язковою ітерацією |
| Класи | INVOICE за логістичні послуги, BOL, POD, OTHER |
| Неоднозначність | Комбінований BOL/POD — невизначений результат із поясненням, без нового класу |
| Майбутні скани | OCR → текстова класифікація → за потреби visual fallback |
| Confidence | Routing signal, окремий від OCR quality; logprobs перевірити; формула/threshold відкриті |
| Evaluation | Невеликий representative set; без обов'язкових 60–100 прикладів чи calibration study |
| UI | Upload flow, result page, мінімальна history/list view |
| Persistence | Metadata, PDF, classification/confidence, model/fallback; optional extracted fields/confidence |
| Storage | PostgreSQL, мінімальний Compose для БД, Django local media для PDF |
| Поза поточним scope | Authentication/accounts, external object storage, сегментація PDF, додаткові класи |
| Optional | Field extraction після основного pipeline; ще не обрані поля або механізм confidence |

## 4. Відкриті питання — не прийняті рішення

- **Останнє питання перед checkpoint:** асистент запропонував синхронну обробку в HTTP request замість background worker/queue. Користувач ще не відповів. Синхронність не погоджена.
- Конкретні OpenAI models/endpoints; практична підтримка logprobs і формату відповіді.
- Формула confidence, threshold, умови запуску/завершення fallback, поведінка при невпевненому fallback.
- Конкретні PDF extraction/OCR інструменти, обмеження розміру/сторінок і часу обробки.
- Склад і розмір evaluation set, джерела придатних документів, критерії прийнятності якості.
- Точна схема даних, статуси, спосіб зберігання спроб/fallback, поведінка повторних завантажень і видалення.
- Деталі reviewer quickstart, запуск Django, deployment (не замовлений), оформлення UI.
- Чи встигнемо optional extraction; які поля й оцінювання їхньої надійності потрібні.
- Фінальний дизайн і implementation plan не складено та не затверджено.

## 5. Виконана робота, перевірка та межі checkpoint

- До checkpoint створено лише `AGENTS.md`; у цьому кроці створено `AI_WORKFLOW.md` за явним запитом користувача.
- Проведено read-only огляд контексту й web research офіційних джерел. Висновки з документації не є результатами тестування застосунку або API моделей.
- Django не ініціалізовано, залежності не встановлено, application code не реалізовано. API моделей не викликали; секрети не читали.
- Для документації виконано перевірку структури, парності оригіналів/перекладів і відділення погоджених рішень від відкритих. Application tests не запускали: реалізації немає.
- Цей файл — проміжний checkpoint, не завершення Brainstorming. Наступне питання brainstorming очікує перегляду checkpoint користувачем.

## 6. Запит на цей checkpoint

**Оригінальний промпт (українською):**

> Перш ніж продовжимо brainstorming, хочу зафіксувати поточний проміжний результат у `AI_WORKFLOW.md`.
>
> Не завершуй Brainstorming і не переходь до Planning або implementation. Це лише checkpoint документації.
>
> Створи `AI_WORKFLOW.md` відповідно до правил з `AGENTS.md` і зафіксуй у ньому поточний meaningful engineering history цього проєкту на основі нашої фактичної розмови в цьому thread.
>
> Для поточного етапу:
>
> - збережи мої meaningful original prompts українською та додай поруч English translation;
> - не перетворюй файл на raw transcript і не включай кожне коротке повідомлення;
> - зафіксуй важливі питання, альтернативи, мої уточнення/заперечення та рішення, до яких ми вже дійшли;
> - чітко відділи вже прийняті рішення від питань, які ще залишаються відкритими;
> - не вигадуй reasoning або decisions, яких у нашій розмові не було;
> - познач поточний brainstorming stage як незавершений / in progress;
> - поки що не додавай commit, оскільки цей logical stage ще триває.
>
> Після створення покажи мені структуру `AI_WORKFLOW.md` і коротко скажи, які частини нашої розмови ти включив, а які свідомо не включив. Не продовжуй наступне brainstorming-питання, доки я не перегляну цей checkpoint.

## 7. Мовне розділення документації та продовження Brainstorming

**Період:** 2026-09-15–2026-09-16. Попередній checkpoint залишається історичним записом стану на той момент. Після нього користувач попросив створити дві змістово еквівалентні мовні версії: `AI_WORKFLOW.md` англійською та `AI_WORKFLOW_UA.md` українською. Наявну engineering history розділено за мовами без зміни рішень або хронології.

Після цього Brainstorming продовжено з останнього питання без відповіді. Завершено такі high-level рішення:

- Для take-home обробка залишається синхронною. Worker/queue не додається; більшу execution model переглянемо лише за фактичної потреби в лімітах.
- Один PDF — один документ із лімітами 10 сторінок і 10 МБ. Система не обробляє мовчки лише частину завеликого документа.
- Кожне прийняте завантаження створює нову processing attempt, зокрема повторне завантаження та retry після failure. File-hash deduplication або result cache не додаються, бо коректний reuse потребував би versioning model/prompt/pipeline і cache invalidation.
- На одну attempt припадає максимум один classification fallback. Успішний fallback може стати final classification; ненадійний fallback завершується semantic `UNCERTAIN`. Технічна помилка fallback залишається technical failure, а доступний primary result зберігається лише для діагностики.
- Надійно визначений combined BOL/POD є встановленою taxonomy ambiguity та завершується `UNCERTAIN` без fallback. Невпевненість, чи документ є BOL, POD або combined, є classification uncertainty і може запустити єдиний fallback.
- Iteration 1 — working vertical slice для text-layer PDF без fallback. Iteration 2 додає scanned PDF через OCR і один спільний visual fallback для scanned та text-layer inputs. Окремий stronger-text fallback не планується.
- Field extraction перейшов зі stretch goal до planned delivery після стабілізації core classifier. Classification зберігає вищий implementation priority, а відмова від extraction можлива лише як contingency через реальну проблему з часом або core pipeline.
- Критерії завершення охоплюють classification, routing/fallback, semantic ambiguity, technical failures, extraction із перевіркою проти відомих expected values, upload/result/history flow і відтворюваний запуск reviewer'ом. Від runtime extraction не очікується незалежний ground-truth oracle.

Запропоновану feature-based classification ідею зафіксовано під час Brainstorming як кандидата: модель може повертати class-specific evidence зі значеннями `present / absent / unclear`, а backend — рахувати rule-based match score. На цьому етапі користувач явно відклав feature tables, ваги, формулу та threshold до завершення цілісного high-level design.

### 7.1. Завершення Brainstorming і погодження дизайну

Після закриття решти mandatory decisions створено окремий design document: `docs/superpowers/specs/2026-09-16-document-classifier-design.md`. Він фіксує architecture, processing flows, responsibilities, scope, deferred decisions і trade-offs. Він не замінює цю engineering history.

**Оригінальний промпт (українською):**

> Так, я думаю, структура цього final brainstorm design document-у підходить. Створи по ній окремий документ і там розпиши те, що ми з тобою вже утвердили, з'ясували і проговорили під час цього брейншторму. Нічого не видаляй та не додавай по своїй, те, що не обговорено і не узгоджено. Поки до планінгу не переходь.

Користувач переглянув і погодив дизайн, оголосив Brainstorming завершеним та явно дозволив перехід до Planning.

**Оригінальний промпт (українською):**

> Design document переглянула, погоджую. Brainstorming на цьому вважаємо завершеним. Переходь до Planning і склади implementation plan на основі погодженого дизайну, зберігаючи ітеративний підхід: від першого working vertical slice до повного planned delivery. Включи в план також моменти, де перед реалізацією потрібно провести experiment або прийняти deferred technical decision. Після створення плану не починай implementation — спочатку я хочу його переглянути.

## 8. Planning — порядок реалізації та зниження ризику

Перший implementation plan розміщував повний Django intake/persistence foundation перед primary AI experiment. Користувач поставив цей порядок під сумнів, оскільки model/API/evidence path є найризикованішою частиною і може бути перевірений без фіксації application schema. План виправлено: standalone feasibility experiment передує Django models, PostgreSQL і persistence.

Потім користувач розділив короткий feasibility probe і формальну evaluation. Виправлена послідовність:

1. **Task 1 / G1 — initial AI feasibility:** кілька контрольних text-layer PDF із відомими expected results; перевірка OpenAI structured output, class-specific evidence та принципової придатності deterministic routing. Manifest, tuning/held-out split, production schema або робочий threshold не потрібні.
2. **Task 2 / G0 — application foundation:** після G1 обираємо версії, production PDF parser, мінімальне persistence representation та intake semantics. Task не очікує фінальних routing settings.
3. **Task 2E / GE — systematic primary evaluation:** створюємо малий representative manifest і tuning/held-out classification split, уточнюємо evidence rules та routing score й обираємо початковий робочий threshold. Після G1 цей етап може йти паралельно з foundation, але Task 3 не інтегрує routing до review GE.
4. **Tasks 3–4 — Iteration 1:** реалізуємо та перевіряємо text-layer classifier, routing, persistence, upload/result/history UI і доступ до original PDF.
5. **Tasks 5–6 — Iteration 2:** додаємо OCR і спільний visual fallback, потім перевіряємо повний classification flow.
6. **Tasks 7–8 — planned extraction:** погоджуємо вузький extraction contract і реалізуємо його без створення другої широкої AI research-системи.
7. **Task 9 / G4 — delivery review:** запускаємо фінальну evaluation та reproducibility checks і звітуємо про фактичні limitations.

**Оригінальний промпт (українською):**

> Чи не варто розділити initial AI feasibility experiment і формальну підготовку evaluation set? Для першого experiment мені здається достатнім кілька контрольних документів з очікуваними результатами, а manifest, tuning/held-out split і більш системну evaluation можна сформувати вже після того, як ми перевіримо model/API/confidence candidates. Як ти це бачиш?

Користувач погодив це розділення. Документи feasibility надалі не вважаються незалежними held-out examples, а малий evaluation set не використовується для заяв про calibration або загальну статистичну надійність.

## 9. Planning — корекції архітектури та scope

### 9.1. Межі application, services та AI

Перша версія плану мала плаский пакет `documents/`, де поруч розміщувалися Django views/models, PDF/OCR functions, routing, pipeline orchestration і OpenAI logic. Користувач попросив чіткіші межі відповідальності без кількох Django apps або зайвих abstractions.

Погоджена структура зберігає один Django app і розділяє:

- Django application layer у корені app для models, forms, views, URLs, templates і migrations;
- `documents/services/` для PDF/OCR processing, deterministic routing, orchestration та persistence lifecycle;
- `documents/ai/` для OpenAI calls, prompts, structured-response validation, classification та extraction.

Services можуть напряму використовувати Django ORM. Repository pattern, domain framework, provider framework, worker system або додаткові Django apps не додаються. Конкретні dataclasses, shared types, function signatures і test snippets прибрано з плану, бо мінімальний AI contract має спочатку бути результатом G1 і GE.

**Оригінальний промпт (українською):**

> Ще одне питання до цієї частини плану: мені не дуже подобається запропонована пласка структура `documents/`, де поруч лежать Django views/models, PDF/OCR processing, routing, pipeline та AI/LLM logic. Чи не варто логічно розділити хоча б Django application layer, processing/services і AI layer, не переускладнюючи маленький проєкт? І водночас конкретні dataclasses/function signatures я б не фіксувала до feasibility experiment, оскільки мінімальний AI contract якраз має бути одним із його результатів. Як би ти переглянув цю структуру?

### 9.2. Вибір evidence-based confidence/routing

Користувач переглянув попередній confidence investigation і запропонував одну основну architecture: LLM отримує extracted/OCR text і повертає candidate class зі structured class-specific features/evidence; backend детерміновано оцінює достатність і суперечності evidence та рахує routing score. Достатні evidence приймаються; недостатні або суперечливі evidence у завершеному flow спрямовуються в єдиний visual fallback. Score явно не є probability of correctness.

Підхід прийнято як технічно достатній для вимоги assignment «classification with confidence score + expensive/visual fallback at low score». Обов'язкове дослідження logprobs, self-reported confidence і паралельних confidence mechanisms прибрано. До альтернатив повертаємося лише за конкретного blocker в evidence-based підході.

Збережені обмеження:

- детермінований розрахунок не робить evidence від LLM автоматично правдивими;
- текстові evidence-цитати перевіряються проти input text, але збіг не доводить правильної semantic interpretation або правильності OCR;
- features мають розрізняти класи, а не винагороджувати generic field presence; важливі contradictions не приховуються високим total score;
- відсутність evidence цільових класів не встановлює автоматично `OTHER`;
- visual fallback отримує original page images, повертає structured visual evidence та проходить власні checks; primary thresholds і перевірки text quotes не копіюються автоматично.

**Оригінальний промпт (українською):**

> Я хочу повернутися до самої концепції confidence, бо поточний plan з investigation logprobs та кількох confidence candidates здається мені переускладненим.
> Я зараз бачу можливий pipeline приблизно так: ми визначаємо для кожного класу характерні/критичні ознаки документа; LLM отримує текст після PDF extraction/OCR і повертає structured classification разом із знайденими class-specific evidence/features; backend уже детерміновано оцінює достатність цих evidence і рахує routing/confidence score. Якщо evidence достатньо — приймаємо classification, якщо недостатньо або вони суперечливі — йдемо у visual fallback, після якого отримуємо final class або `UNCERTAIN`. Сам score при цьому не називаємо probability of correctness — його придатність і threshold перевіряємо на невеликому labeled evaluation set із відомими правильними класами.
> Чи є ця концепція технічно правильною для нашої задачі й достатньою для вимоги `classification with confidence score + expensive/visual fallback at low score`? Якщо так, чи можемо взяти її за основну архітектуру і прибрати investigation кількох альтернативних confidence mechanisms? Якщо ні — поясни конкретно, де в цьому pipeline проблема і чого в ньому не вистачає.

Implementation plan, а потім і погоджений design document синхронізовано з цим evidence-based напрямом. Design більше не подає confidence mechanisms як паралельні candidates. Точні features, deterministic rules, score formula і thresholds залишаються результатами bounded feasibility/evaluation, а не припущеннями, зафіксованими в документації.

### 9.3. Field extraction звужено до невеликої planned capability

Початковий Task 7 нагадував другу AI subsystem із власним широким investigation confidence, model choice, input/call strategy і validation. Користувач попросив пропорційну take-home реалізацію.

Task 7 тепер є коротким extraction contract and validation checkpoint:

- невеликий class-specific field schema для `INVOICE`, `BOL` і `POD`;
- structured results `value / status / evidence`;
- deterministic validators лише там, де вони мають сенс;
- один простий explainable field-confidence calculation на основі status, evidence, validation і contradictions;
- кілька вручну підготовлених examples із відомими expected values, зокрема missing/unclear і semantic-error cases;
- чітке правило, що extraction errors не змінюють уже accepted classification.

Окремого порівняння extraction models, confidence mechanisms, input strategies, calibration study або extraction tuning/held-out split немає. Task 8 реалізує погоджений contract і перевіряє його на expected examples.

**Оригінальний промпт (українською):**

> По Task 7 у мене лишається сумнів щодо масштабу. Field extraction входить у planned delivery, але зараз він виглядає майже як друга окрема AI-система з власним experiment щодо confidence, input/call strategy, validation тощо. Чи можемо ми для take-home зробити це простіше: невеликий class-specific набір полів, structured extraction з evidence, deterministic validation там, де вона можлива, і простий explainable field-confidence approach — без окремого широкого дослідження кількох механізмів? Оціни, що з поточного Task 7 реально необхідне, а що можна спростити без втрати якості рішення.

### 9.4. Фінальний sanity check scope і три скорочення

Фінальний review встановив, що повний planned delivery реалістичний приблизно за три сфокусовані дні, але не є комфортною дводенною реалізацією. Жодної ключової capability assignment не втрачено. Прибрано або скорочено три активності без помітної цінності для reviewer'а:

1. Task 5 обирає один поширений local OCR/render stack і запускає smoke test. Альтернатива розглядається лише за конкретного blocker; обов'язкове порівняння OCR libraries прибрано.
2. Task 2/G0 не проєктує deletion UI або retention policy. Прийняті PDF залишаються в local media; rejected uploads і temporary processing files очищаються.
3. Task 9 вручну перевіряє один text-layer case, один scanned/visual-fallback case і повторне відкриття result/history з original PDF та extracted fields. Uncertainty, technical failures, duplicates і invalid limits залишаються в automated tests замість дубльованої повної browser matrix.

Evaluation command, малий classification held-out set, PostgreSQL із мінімальним Compose, local media, history, visual-fallback experiment і короткий G3 checkpoint збережено, бо вони дають пряму цінність reviewer'у або реалізують погоджені вимоги.

**Оригінальний промпт (українською):**

> Після внесення останньої правки зроби фінальний sanity check усього implementation plan. Не пропонуй нову архітектуру й не розширюй scope. Перевір тільки, чи план реально відповідає бюджету 2–3 дні, чи немає зайвих formalities/infrastructure/experiments, які не дають reviewer’у помітної цінності, і чи не втрачено жодну ключову capability з assignment. Якщо бачиш, що щось можна безпечно спростити або прибрати — назви конкретно що і чому. Якщо plan уже збалансований, так і скажи.

Користувач погодив саме ці три скорочення та попросив не змінювати інші частини plan.

## 10. Поточний стан, перевірка та статус commit

- Brainstorming завершено; design document погоджено та синхронізовано з поточною evidence-based confidence/routing architecture.
- Planning усе ще перебуває на review користувача. Поточний implementation plan: `docs/superpowers/plans/2026-09-16-document-classifier-implementation-plan.md`.
- Plan зберігає всі core capabilities assignment: Django PDF upload, `INVOICE`/`BOL`/`POD`/`OTHER`, classification score, visual fallback за низького score, scanned PDF через OCR, semantic uncertainty, technical failures, мінімальні persistence/history і planned field extraction із confidence.
- Planning edits перевірено через targeted diffs/searches, порядок tasks, пошук застарілих references і Markdown fence checks. Працездатність application не заявлялася як перевірена.
- Django не ініціалізовано, dependencies не встановлено, application code і tests не створено, OpenAI API calls не виконано, секрети не читали.
- Цей documentation stage зафіксовано в initial commit `Add initial project design and implementation plan`. Дозвіл закомітити й запушити цю документацію не розпочинає application implementation.
