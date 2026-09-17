# Harness selection matrix

This file is the source of truth for public harness numbers, catalog IDs, and
selection rules. Existing numbers must never be reassigned; append new entries.
`plans/custom-runner.md` (plan A) is the historical source, preserved verbatim.
The table and selection rules below are copied verbatim from that source.

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
