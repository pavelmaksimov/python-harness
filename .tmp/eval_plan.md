# План — самоуправляемая система harness-eval

## Цель

Пользователь сообщает направление обычным текстом, например:

- `проверь CLI через OpenRouter, включи 1-6 и 25-26`;
- `запусти тест Postgres, всё стандартное, но исключи 2 и 32`;
- `повтори эксперимент 7, добавь harness 33`.

Репозиторный агент сам выбирает задание, разворачивает зависимости harness,
восстанавливает проверенный профиль OpenCode provider/model/variant, чинит
безопасные проблемы запуска и сохраняет результат с накопленным опытом.

Опыт запуска остаётся в управляющем контуре и не попадает в prompt
тестируемого агента. Это не позволяет накопленным подсказкам незаметно менять
сам эксперимент.

## Пользовательский контракт выбора harness

Номера ниже — стабильный публичный интерфейс. Существующие строки нельзя
перенумеровывать или переиспользовать; новые harness добавляются только в конец.
Эта таблица является единственным источником соответствия номера и catalog ID.

| № | Harness ID | Полоса | Что проверяет | Обязательные companions / ограничения | Основная eval-проба |
|---:|---|---|---|---|---|
| 1 | `conventional-commits` | core | Формат и предложение commit message | Входит в каждый core-набор | Общий workflow |
| 2 | `keep-a-changelog` | core optional | Запись завершённых изменений в changelog | Только по явному включению | Общий workflow |
| 3 | `python-tooling` | core | uv, Ruff, Black, isort, pre-commit | Базовый core | Все кодовые пробы |
| 4 | `python-workflow` | core | Навигация, проверки, исследование и завершение задачи | Базовый core | Общий workflow |
| 5 | `python-libs` | core | Индекс общих библиотек и маршрутизация к helper rules | Базовый core | Все кодовые пробы |
| 6 | `python-architecture` | core | Модули, Entity, use cases, DI, exceptions, settings, logging | Базовый core; обычно вместе с 28 и 29 | `domain-order-lifecycle` |
| 7 | `python-fsm` | core | Явные состояния и допустимые переходы | Использует 5 и 6 | `domain-order-lifecycle` |
| 8 | `python-retry` | core | Retry для временных и безопасных операций | Использует 5; не применять к неидемпотентным операциям | `payment-http-client` |
| 9 | `python-stdlib-first-review` | core skill | Замена самописных конструкций stdlib-возможностями | Подключается как OpenCode skill | Все кодовые пробы |
| 10 | `python-tests` | core | Functional-first тесты, doubles, layout, no patch | Автоматически добавляет 11, 12 и 30 | `order-tests` |
| 11 | `python-freezegun` | core tests | Управление временем без patch | Требует 10 | `order-tests` |
| 12 | `python-polyfactory` | core tests | Сложные типизированные тестовые данные | Требует 10; ORM-часть требует 17 и 19 | `order-tests` |
| 13 | `python-semver` | core optional | Версионирование публичной библиотеки | Только для публикуемой библиотеки | Будущая library-проба |
| 14 | `python-fastapi` | adapter | HTTP API, versioning, error boundary, SSE | Использует 6 | `fastapi-order-api` |
| 15 | `python-jwt` | adapter | JWT access tokens и password hashing | Требует 14, 17 и 19 | Будущая auth-проба |
| 16 | `python-base-client` | adapter | Outbound HTTP adapter и error mapping | Использует 5 и 6 | `payment-http-client` |
| 17 | `python-sqlalchemy` | adapter | ORM models, mapping и repositories | DB bundle: 17, 18, 19 и 20 | `postgres-order-store` |
| 18 | `sqlalchemy` | adapter skill | Практики SQLAlchemy 2.x | Требует 17 и 19 | `postgres-order-store` |
| 19 | `python-db-sessions` | adapter | Engine, session и transaction lifecycle | Требует 17 | `postgres-order-store` |
| 20 | `python-alembic` | adapter | Async migrations и autogenerate | Требует 17 и 19 | `postgres-order-store` |
| 21 | `python-sqladmin` | adapter optional | Operator admin panel | Требует 14, 17 и 19 | Будущая admin-проба |
| 22 | `python-redis` | adapter | Cache keys, repository и Redis transactions | С тестами также требует 10 | `order-cache-rate-limit` |
| 23 | `python-fastapi-limiter` | adapter | Rate limiting FastAPI routes | Требует 14 и 22 | `order-cache-rate-limit` |
| 24 | `python-telegram` | adapter | Telegram handlers, polling и error wrappers | Использует 6 | `telegram-order-bot` |
| 25 | `python-typer` | adapter | Typer commands, async bridge и exit codes | Требует 26 | `orders-cli` |
| 26 | `cli-design` | adapter skill | CLI command tree и stdout/stderr contract | Требует 25 | `orders-cli` |
| 27 | `python-monitoring` | adapter | Prometheus endpoint, middleware и action metrics | Обычно вместе с 14 | Будущая monitoring-проба |
| 28 | `layers-linter` | enforcement | Импортные границы между слоями | Стандартно вместе с 6 | `domain-order-lifecycle` |
| 29 | `domain-types-linter` | enforcement | Domain types в аннотациях бизнес-логики | Стандартно вместе с 6 | `domain-order-lifecycle` |
| 30 | `patch-linter` | enforcement | Запрет patch и monkeypatch в тестах | Требует 10 | `order-tests` |
| 31 | `di-linter` | enforcement optional | DI001/DI002 и запрет скрытого конструирования | Использует 6; только по явному включению | `domain-order-lifecycle` |
| 32 | `dddlint` | enforcement optional | Уникальность имён символов | Только по явному включению | Все кодовые пробы |
| 33 | `python-coverage` | enforcement optional | Full или diff coverage gate | Требует 10; режим выбирается отдельно | `order-tests` |

Правила разбора пользовательского текста:

- поддерживать номера, диапазоны, `всё`, `всё стандартное`, `кроме` и
  `исключи`;
- сначала раскрывать включения, затем companions, затем применять исключения;
- явное исключение обязательного companion считается конфликтом: эксперимент
  не запускается, агент кратко объясняет зависимость;
- перед запуском агент показывает одну строку с исходными номерами и полностью
  развёрнутыми catalog IDs;
- manifest сохраняет и пользовательские номера, и итоговый набор IDs;
- если выбранный harness ещё не покрыт eval-пробой, агент останавливается и
  предлагает создать отдельное ограниченное задание.

## Агентский интерфейс

В корневой `AGENTS.md` добавить короткий обязательный указатель: при запросе
тестирования harness, модуля, provider или повторения эксперимента читать
`evals/RUNBOOK.md`.

Пользователь не обязан запускать CLI. Runbook ведёт агента через команды:

- `plan --module cli --provider openrouter --include 1-6,25-26 --exclude 2` —
  разрешить aliases, номера, companions, задание и профиль без запуска;
- `run --module cli --provider openrouter ...` — doctor, repair, subject,
  checks, judge и запись history;
- `profiles` — показать уже проверенные параметры provider/model/variant;
- `select --changed-from REF` — определить eval-пробы после изменения harness;
- `compare RUN_A RUN_B` — сравнить версии harness или модели;
- `doctor --repair` — проверить OpenCode и применить безопасные remedies.

Каждый шаг Runbook заканчивается проверяемым условием завершения. Справочные
детали provider resolution и incidents раскрываются по указателям только при
соответствующей ветке, чтобы не перегружать постоянный контекст агента.

## Выбор provider и модели

Provider можно назвать разговорно. Агент сопоставляет alias с OpenCode provider
и сначала ищет ранее подтверждённый профиль.

Если профиль существует и совместим с текущей версией OpenCode, используются
сохранённые точные `provider/model`, variant и аргументы. Повторный поиск не
выполняется.

Если профиля нет или сохранённая модель исчезла:

1. Выполнить `opencode models <provider> --verbose`.
2. Показать пользователю 2–5 подходящих вариантов с понятными именами,
   возможностями и доступной стоимостью.
3. Не запускать эксперимент, пока пользователь не выберет вариант.
4. Преобразовать человеческий выбор в точный ID и сохранить профиль только
   после успешного smoke/run.

Модель нельзя менять молча. Judge использует отдельный фиксированный профиль;
при его отсутствии действует тот же процесс выбора.

## База опыта и самообучение

Хранить в Git только очищенные структурированные данные:

- `evals/knowledge/providers/<alias>.json` — точные provider/model/variant,
  дружелюбное имя, роль subject/judge, OpenCode version, metadata snapshot,
  проверочный run ID и дата успеха;
- `evals/knowledge/incidents/<fingerprint>.json` — стадия сбоя,
  нормализованный симптом, применимость, неудачные попытки, подтверждённый
  remedy, проверка, число повторений и `superseded_by`;
- `evals/knowledge/INDEX.md` — генерируемый краткий индекс.

Каждый run manifest дополнительно хранит журнал попыток: действие, длительность,
результат и использованный incident. В knowledge-base попадает только решение,
после которого повторный запуск стал успешным. Сырые JSONL-логи и model catalog
cache остаются в `memory/.tmp/evals/`.

Перед записью knowledge runner удаляет токены, абсолютные пользовательские
пути, содержимое env и другие секреты. Ревизия knowledge-base фиксируется в
каждом эксперименте.

Это операционное самообучение, а не fine-tuning: система улучшает выбор команд,
параметров и remedies, не изменяя модель и не подмешивая прошлые решения в
subject prompt.

## Самовосстановление

1. Найти точное известное incident по стадии, OpenCode version и provider.
2. Сразу применить подтверждённый remedy, пропуская сохранённые ложные пути.
3. Если записи нет — выполнить не более трёх различных безопасных
   диагностических попыток.
4. После успеха сохранить fingerprint, неудачные действия и минимальное
   рабочее решение.
5. При дефекте eval-runner исправить tracked-код, добавить regression test,
   закоммитить исправление и повторить эксперимент с чистого состояния.
6. Если требуется установка/обновление OpenCode, изменение auth/global config,
   смена provider/model или ослабление permissions — остановиться и запросить
   разрешение.

Resolver может исправлять порядок CLI-аргументов, поддерживаемый variant,
формат JSON, локальную конфигурацию, timeout и устаревший cache. Он не читает
секреты и не меняет пользовательский выбор.

## Eval-пробы

Первая версия содержит восемь независимо запускаемых заданий:

1. `domain-order-lifecycle` — доменная модель, модули, FSM и границы слоёв.
2. `fastapi-order-api` — HTTP API, versioning и error boundary.
3. `postgres-order-store` — ORM, repository, sessions и Alembic.
4. `orders-cli` — Typer, async bridge и CLI contract.
5. `order-tests` — functional tests, factories, time и no-patch.
6. `payment-http-client` — outbound HTTP, error mapping и retry.
7. `order-cache-rate-limit` — Redis и FastAPI rate limiting.
8. `telegram-order-bot` — handlers, DI, logging и errors.

Task manifest содержит aliases, покрываемые номера и IDs, fixture, rules,
skills, templates, checks и rubric. Матрица выше остаётся единственным
пользовательским списком; внутреннее обратное отображение генерируется из task
manifests и проверяется командой `validate`.

## История экспериментов

Каждый запуск сохраняется в `evals/history/<task>/<run-id>/`:

- `manifest.json` — исходные номера, раскрытые IDs, source commit/VERSION,
  хэши harness, knowledge revision, OpenCode version, subject/judge profiles,
  попытки, checks и метрики;
- `result.patch` — воспроизводимый diff созданного проекта;
- `report.md` — нормализованный scorecard judge с оценками 0–4 и
  доказательствами по файлам.

При грязном Git-состоянии запуск по умолчанию запрещён. Failed и timeout runs
тоже сохраняются, чтобы не терять диагностическую историю. Сравнение разрешено
для одинакового task/rubric; различия harness, модели и knowledge revision
показываются явно.

## OpenCode и безопасность

- Выбранные `.mdc` материализуются в изолированный `AGENTS.md`; skills — в
  `.opencode/skills` экспериментального workspace.
- Используются `opencode run --pure --format json`, отдельный
  `OPENCODE_CONFIG_DIR` и отключённое project-config discovery.
- Subject может менять только экспериментальный workspace и выполнять узкий
  список `uv run pytest`, `uv run ruff check`, `git status` и `git diff`.
- Внешние каталоги, web, subagents, push и остальные shell-команды запрещены.
- Judge работает read-only.
- Sharing, auto-update и OpenTelemetry отключены; внешние plugins не загружаются.
- Provider credentials читает OpenCode; runner не открывает auth-файлы и не
  инспектирует process environment.

## Раздельная реализация агентами

1. Агент coordinator: runner, parsing номеров, resolver и Runbook.
2. Агент knowledge: profiles, incidents, sanitization и repair loop.
3. Восемь отдельных агентов: по одному на каждую eval-пробу, каждый меняет
   только свой каталог.
4. Интегратор переносит reviewable commits, генерирует индекс и выполняет
   общую проверку.

Существующую ветку `agent/eval-http-mocks` использовать только как источник
проверенных fixtures и рубрик; её OMP-specific runner не переносить целиком.

## Проверка и критерии готовности

- Текстовые включения, исключения, диапазоны и `всё кроме` разрешаются
  детерминированно.
- Конфликт с обязательным companion блокирует запуск до исправления выбора.
- Неизвестный provider/model возвращает варианты и не запускает эксперимент.
- Успешный выбор переиспользуется без повторного поиска точных параметров.
- Известная ошибка сразу использует подтверждённый remedy.
- Новый сбой сохраняет ложные пути только после найденного успешного решения.
- После трёх безуспешных remedies цикл останавливается.
- Knowledge-base не попадает в subject context.
- Fake OpenCode покрывает success, timeout, malformed JSON, unsupported
  variant и missing model.
- Patch восстанавливает результат из fixture; compare показывает изменения
  checks, metrics и judge score.
- Profiles, incidents и reports проходят secret/path sanitization.
- `VERSION` каталога не повышается: installable harness и install semantics не
  меняются.
