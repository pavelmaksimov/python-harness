# Альтернативный план — harness-eval на OpenResearch

## Цель сравнения

Реализовать второй вариант той же системы eval, используя OpenResearch как
backend оркестрации и истории экспериментов.

Оба варианта обязаны иметь одинаковые:

- нумерацию и правила выбора harness;
- восемь eval-проб и их fixtures;
- provider/model profiles;
- deterministic checks и judge rubrics;
- нормализованные `manifest.json`, `result.patch` и `report.md`;
- команды сравнения результатов.

Различается только инфраструктура выполнения:

- первый план хранит дерево запусков и историю собственным runner;
- этот план передаёт project, experiment tree, worktree, supervision, logs и
  immutable run archive установленному OpenResearch `orx 0.2.4`.

Так результаты двух реализаций можно сравнивать одним инструментом, не смешивая
разницу orchestration backend с влиянием harness или модели.

## Канонический выбор harness

Использовать без изменений единственную нумерованную таблицу из
`.tmp/eval_plan.md`.

После реализации её источником истины становится `evals/HARNESS_MATRIX.md`.
Оба backend читают один файл или один сгенерированный machine-readable manifest.
Вторую таблицу с номерами не создавать.

Сохраняются те же правила:

- существующие номера не меняются;
- новые harness добавляются только в конец;
- поддерживаются номера, диапазоны, `всё`, `кроме` и `исключи`;
- companions раскрываются автоматически;
- явное исключение обязательного companion блокирует запуск;
- run manifest содержит исходные номера и итоговые catalog IDs.

## Граница модулей

### Harness coordinator

Наш код остаётся управляющим модулем с маленьким интерфейсом:

- разобрать пользовательское направление и номера;
- выбрать task manifest;
- разрешить provider/model profile;
- создать или найти OpenResearch experiment node;
- запустить node, дождаться результата и нормализовать evidence;
- применить repair loop и обновить knowledge-base.

### OpenResearch backend

OpenResearch отвечает за:

- локальный project и experiment tree;
- изолированные experiment branches/worktrees;
- recorded commit каждого запуска;
- local/remote execution и supervision;
- run status, cancellation, waiting и terminal logs;
- связь вариантов, запусков, файлов, diff и артефактов.

### OpenCode subject и judge

Subject по-прежнему запускается через OpenCode с выбранным harness. Judge
работает отдельным read-only вызовом с фиксированным profile. OpenResearch не
подменяет subject-модель своим autoresearch-агентом.

## Однократное подключение проекта

У `orx 0.2.4` нет CLI-команды создания local project: официальный путь —
импортировать или создать проект через dashboard `orx up`.

Первичная настройка:

1. Проверить `orx --version` и `orx telemetry status`.
2. Запустить `orx up --no-agent --no-telemetry`.
3. Открыть локальный dashboard и импортировать текущий Git-репозиторий.
4. Получить project ID через `orx projects` и проверить его командой
   `orx project view <id>`.
5. Сохранить machine-local ID в `.tmp/orx-project.json`; в Git его не
   коммитить, поскольку ID относится к локальной SQLite-базе.

В будущих запусках агент сначала проверяет cached ID. Если cache отсутствует
или устарел, он разрешает проект по repository path через `orx projects`.
Повторно просить пользователя открыть dashboard нужно только когда проект ещё
не зарегистрирован или локальная OpenResearch-база была удалена.

Dashboard не обязан постоянно работать для CLI-managed local runs. Он нужен
для первичной регистрации и визуального просмотра дерева/результатов.

## Представление дерева экспериментов

Использовать один OpenResearch project для `python-harness`.

Для каждой из восьми eval-проб создать отдельный baseline root через
`orx create-experiment --baseline`:

1. `domain-order-lifecycle`;
2. `fastapi-order-api`;
3. `postgres-order-store`;
4. `orders-cli`;
5. `order-tests`;
6. `payment-http-client`;
7. `order-cache-rate-limit`;
8. `telegram-order-bot`.

Вариант конфигурации создаётся дочерним experiment node. Его fingerprint:

`task + harness selection hash + harness source commit + subject profile + judge profile`

Повторения с тем же fingerprint являются несколькими runs одного node. Любое
изменение harness, модели, judge, task/rubric или run command создаёт новый
дочерний node. Уже запускавшийся node не редактируется: исправленный вариант
становится его ребёнком, поэтому ошибочный путь остаётся видимым в lineage.

Node title остаётся коротким. Полное описание записывается через
`orx exp desc` и включает:

- task ID;
- исходные номера и раскрытые harness IDs;
- source commit и catalog VERSION;
- subject/judge profile names;
- knowledge revision;
- selection fingerprint;
- ожидаемый artifact contract.

## Run command

Каждый node получает фиксированную команду при создании:

```text
uv run python evals/orx_entrypoint.py execute \
  --task <task-id> \
  --include <canonical-numbers> \
  --subject-profile <profile> \
  --judge-profile <profile> \
  --selection <fingerprint>
```

Точные provider/model/variant не дублируются в command string. Они читаются из
profile-файлов записанного Git commit, а затем полностью фиксируются в run
manifest.

Coordinator создаёт node командой `orx create-experiment`, передавая этот
`--run-command`, и запускает его явно локально:

```text
orx exp run --backend local --timeout 30m --no-telemetry <experiment-id>
```

Флаг OpenResearch `--provider` не использовать: он означает compute provider,
а не LLM provider. В пользовательском интерфейсе говорить `model provider` и
передавать его только нашему resolver.

После запуска coordinator использует `orx exp wait`, `orx exp status`,
`orx runs` и `orx logs` вместо собственного process supervisor.

## Выполнение внутри node

`evals/orx_entrypoint.py` выполняет только предметную часть:

1. Проверяет записанный commit, task, harness matrix и profiles.
2. Разворачивает companions и материализует изолированный OpenCode config.
3. Запускает subject через `opencode run --pure --format json`.
4. Выполняет deterministic checks.
5. Запускает read-only judge.
6. Создаёт нормализованные artifacts.
7. Печатает краткий machine-readable итог и завершает процесс кодом 0/1/2.

OpenResearch сохраняет terminal log, recorded commit и run lineage. Subject и
judge не получают доступ к OpenResearch knowledge, другим experiment nodes или
глобальным инструкциям.

## Контракт артефактов

До успешного завершения entrypoint обязан создать:

- `manifest.json` — backend=`openresearch`, project/experiment/run IDs,
  selection, source commit, profiles, OpenCode/orx versions, knowledge revision,
  checks, attempts и timings;
- `result.patch` — diff результата относительно task fixture;
- `report.md` — judge scorecard и evidence;
- `status.json` — компактный machine-readable terminal status для supervisor.

Пути выводятся в конце лога с устойчивым префиксом
`HARNESS_EVAL_ARTIFACT=`. Секреты и абсолютные пользовательские пути перед этим
санитизируются.

Добавить `doctor`-smoke для каждой новой версии `orx`: он создаёт дешёвый
тестовый node, пишет marker artifact и проверяет, что файл доступен после
завершения run. Результат проверки сохраняется в OpenResearch profile.

Если конкретная версия OpenResearch сохраняет commit/log, но не позволяет
стабильно получить произвольные artifacts, автоматически включается exporter:
он копирует только три нормализованных файла в `evals/history/`, сохраняя
OpenResearch project/experiment/run IDs. Полные workspace и логи не
дублируются.

## Сравнение с первым backend

Команда `compare` читает нормализованный manifest, а не внутреннюю SQLite-базу
OpenResearch. Она принимает любые комбинации:

- custom runner против custom runner;
- OpenResearch против OpenResearch;
- custom runner против OpenResearch.

Сравнение разрешено только для одинакового task/rubric hash. Отчёт показывает:

- harness selection и source commits;
- subject/judge profiles;
- backend и его version;
- checks, structural metrics и judge score;
- число попыток, repair steps и wall time;
- различия result patches.

Таким образом оценивается не только полученный дизайн, но и цена самой
инфраструктуры: объём собственного кода, надёжность, число ручных действий и
время восстановления после ошибок.

## Provider/model profiles

Использовать ту же Git-базу profiles, что в первом плане.

Если проверенного профиля нет, эксперимент не создаётся и не запускается:

1. Agent выполняет `opencode models <provider> --verbose`.
2. Показывает пользователю 2–5 понятных кандидатов.
3. Пользователь выбирает модель без необходимости вводить точный ID.
4. Resolver сохраняет точное значение после успешного smoke/run.

OpenResearch `orx up --model` не использовать как источник subject-модели:
этот параметр управляет dashboard agent proxy и смешивает управляющего агента
с тестируемым subject.

## Самообучение и repair loop

Использовать общую с первым планом Git-базу `evals/knowledge/`, добавив stages:

- `orx_project_resolution`;
- `orx_experiment_create`;
- `orx_local_run`;
- `orx_supervision`;
- `orx_artifact_retrieval`.

Repair loop:

1. Проверить known incident до первой попытки.
2. Применить подтверждённый remedy и пропустить сохранённые ложные пути.
3. При неизвестной ошибке выполнить не более трёх безопасных различных проб.
4. Для transient failure повторить run того же node.
5. Если меняется configuration, profile, run command или код entrypoint —
   создать child node и сохранить старый как отрицательный результат.
6. После успеха записать remedy с project/experiment/run evidence.

Coordinator сам может исправлять repo-local adapter/runner и добавлять
regression test. Он не обновляет `orx`, не меняет OpenResearch database/auth,
не выбирает remote compute и не удаляет projects/runs без разрешения.

## Безопасность и стоимость

- Каждый вызов `orx` получает `--no-telemetry`; persistent telemetry status
  должен оставаться `off`.
- Основные eval запускаются только с `--backend local`.
- OpenResearch managed compute, SSH, Slurm, Kubernetes, Ray, Modal, HF Jobs и
  Tinker находятся вне первой версии и требуют отдельного подтверждения.
- Autoresearch loop не используется: он может менять гипотезу и код, нарушая
  контролируемое сравнение harness.
- Subject сохраняет узкие permissions из первого плана.
- OpenResearch credentials и local SQLite не читаются напрямую; используется
  только публичный CLI.
- `orx delete`, `orx update`, `orx login/logout`, cancel чужого run и изменение
  существовавшего evidence node запрещены без явной команды пользователя.

## Агентский пользовательский интерфейс

Корневой `AGENTS.md` указывает на единый `evals/RUNBOOK.md`. Backend выбирается
одним словом или profile default:

- `проверь CLI через OpenRouter на backend OpenResearch, включи 1-6,25-26`;
- `повтори прошлый Postgres эксперимент через orx`;
- `сравни custom run X с OpenResearch run Y`.

Агент сам выполняет `doctor`, разрешает project/node/run IDs и не просит
пользователя копировать точные CLI-параметры. Пользователь выбирает только
модель, если для provider ещё нет подтверждённого profile.

## Раздельная реализация агентами

1. Агент OpenResearch adapter: project resolution, node creation, run/wait/log.
2. Агент artifacts: entrypoint, normalized outputs и exporter fallback.
3. Агент repair: OpenResearch incidents, profile и versioned doctor.
4. Восемь отдельных агентов: те же task manifests, fixtures, checks и rubrics,
   что в первом backend; реализация не должна содержать backend-specific logic.
5. Интегратор проверяет cross-backend schema и compare.

Для независимого сравнения второй вариант реализуется в отдельной ветке и
worktree. Общие fixtures/table/schema можно скопировать из зафиксированного
baseline commit, но нельзя импортировать custom orchestration implementation.

## Проверка и критерии готовности

- Cached project ID восстанавливается без ручного поиска; stale ID безопасно
  переопределяется через публичный CLI.
- Восемь baseline roots создаются по одному разу и не дублируются.
- Одинаковый fingerprint повторно использует node; изменённая конфигурация
  создаёт child node.
- `orx exp run --backend local` запускает зафиксированную command и записывает
  status/log.
- Failed и timeout runs остаются в tree как evidence.
- Marker artifact переживает завершение run либо включается проверенный
  exporter fallback.
- OpenResearch и custom manifests проходят одну JSON-schema validation.
- Cross-backend compare работает без чтения OpenResearch SQLite.
- Provider/model никогда не выбирается или заменяется без пользователя.
- Known incident сокращает число повторных неэффективных действий.
- Telemetry остаётся отключённой; remote compute не используется.
- Удаление OpenResearch полностью не лишает Git-базу profiles/incidents и
  экспортированные нормализованные результаты смысла.

## Известный компромисс

OpenResearch уменьшает объём собственного кода для supervision, worktrees,
lineage и evidence, но добавляет локальную SQLite-базу, одноразовую регистрацию
project через dashboard и зависимость от CLI/version semantics. Именно эти
затраты должны измеряться при сравнении с первым планом.

## Источники реализации

- OpenResearch repository и основные гарантии:
  https://github.com/alphaXiv/OpenResearch
- Официальный agent skill и CLI contract:
  https://github.com/alphaXiv/OpenResearch/blob/main/SKILL.md

`VERSION` каталога Python harness не повышается: alternative eval backend не
меняет installable harness или install semantics.
