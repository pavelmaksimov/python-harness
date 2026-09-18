Часть родительской задачи MY-45 («лаборатория экспериментов»), **план A** — собственный
runner лаборатории (`custom` backend). Общий backend-neutral слой и восемь проб уже
сделаны двумя stage-1 задачами, они смержены/лежат в ветках рядом; ты добавляешь
только backend.

План-источник приложен: `.tmp/eval_plan.md` (план A — «самоуправляемая система
harness-eval»: агентский интерфейс, база опыта и самообучение, самовосстановление,
история экспериментов, OpenCode и безопасность, раздельная реализация агентами,
критерии готовности). Скачать:

```bash
mkdir -p memory/.tmp/plans
multica attachment download <attachment-id> -o ./memory/.tmp/plans
```

Fallback: `git show agent/code-flash/my-45:.tmp/eval_plan.md > memory/.tmp/plans/eval_plan.md`.

## Что уже есть (не переделывать)

Вторые задачи MY-45 (stage 1) дают:

- `evals/HARNESS_MATRIX.md` — единственная таблица «номер ↔ catalog ID»;
- `evals/core/**` — matrix, selection (номера/диапазоны/`всё`/`кроме`, замыкание
  companions, конфликты), profiles, knowledge (incidents/providers/INDEX/sanitization),
  sandbox-материализация, `execute_experiment`, checks runner, judge, artifacts,
  compare, validate, CLI (`uv --cache-dir /home/user/.cache/uv run --no-project python -m evals.core.cli ...`);
- `evals/schema/run-manifest.schema.json` — нормализованный манифест;
- `evals/core/backend_api.py` — протокол `Backend` (`name`, `version`, `doctor(repair)`,
  `run(RunRequest) -> BackendResult`, `status(run_id)`), обнаружение через
  `evals/backends/*/backend.py` с атрибутом `BACKEND`;
- `evals/tasks/**`, `evals/_fixtures/**` — восемь проб с fixtures, checks и rubrics;
- `evals/RUNBOOK.md`.

Проверь наличие этих файлов в своём checkout. Если их нет — влей ветки stage 1 в свою
ветку, не меняя их содержимое:

```bash
git branch -a | grep -i 'my-45\|eval'                    # найти ветки stage 1
git fetch origin <core-branch> <probes-branch>
git merge origin/<core-branch> origin/<probes-branch>
```

Точные имена веток смотри также в комментариях родительской задачи
(`multica issue get 01a0afe8-f64f-7574-b39d-123603ae6144 --output json`, затем
`multica issue comment list <id> --roots-only --summary`) и в дочерних задачах MY-45 core/probes.

## Зона владения

```text
evals/backends/custom/**          backend, supervisor, repair loop, README, tests
```

Не создавать и не менять: `evals/core/**`, `evals/schema/**`, `evals/tasks/**`,
`evals/_fixtures/**`, `evals/HARNESS_MATRIX.md`, `evals/RUNBOOK.md`, `evals/plans/**`,
`evals/backends/openresearch/**`, `evals/orx_entrypoint.py`, `evals/tests/**`,
`AGENTS.md`, `README.md`, `VERSION`, `SOURCES.md`, `harnesses/**`, `skills/**`.

## Что именно сделать

1. **`evals/backends/custom/backend.py`** — реализация `Backend` (`name = "custom"`),
   экспонирует `BACKEND`; дополнительного реестра-файла не создавай (обнаружение
   сканирует `evals/backends/*/backend.py`).
2. **Supervision** — собственный супервизор прогона вокруг
   `evals.core.execute.execute_experiment(request, artifact_dir)`:
   wall-clock timeout, отмена, запись журнала попыток (`action`, `duration_ms`,
   `result`, использованный `incident`), терминальный статус
   `success|failed|timeout|error`. Supervision, worktrees и lineage — твоя зона,
   предметная часть (sandbox, subject, checks, judge, артефакты) — `evals/core`.
3. **История** — каталог прогона `evals/history/<task>/<run-id>/` с `manifest.json`
   (нормализованная схема; `backend.name = "custom"`, версия, ids), `result.patch`,
   `report.md`, `status.json`; в конце прогона печатается
   `HARNESS_EVAL_ARTIFACT=<путь до каталога рана>`. Секреты и абсолютные
   пользовательские пути санитизируются перед записью.
4. **Repair loop** (по плану A, раздел «Самовосстановление»):
   сначала известный incident (API knowledge слой), затем не более трёх различных
   безопасных диагностических попыток; после успеха сохранить fingerprint, неудачные
   действия и минимальное рабочее решение. Дефект eval-runner/idempotency — править
   tracked-код в своей зоне, добавлять regression test, коммитить и повторять прогон с
   чистого состояния. **Остановиться и спросить разрешение** человека, если требуется:
   установка/обновление OpenCode, изменение auth или global config, смена
   provider/model, ослабление permissions. Стадии incident'ов — `custom_*`.
5. **`doctor [--repair]`** — проверка opencode version, `OPENCODE_CONFIG_DIR`, наличия
   subject/judge профилей, uv-кэша, прав на sandbox; безопасные remedies: порядок
   CLI-аргументов, поддерживаемый variant, формат JSON, локальная конфигурация,
   timeout, устаревший cache. Секреты не читать, выбор пользователя не менять.
6. **Тесты** `evals/backends/custom/tests/**` (stdlib `unittest`) с фейковым subject
   через `RunRequest.subject_command`: успех, timeout, битый JSON, отсутствующая модель,
   неподдерживаемый variant; плюс проверка контракта каталога прогона
   (`manifest.json` валиден по схеме, `status.json`, `HARNESS_EVAL_ARTIFACT`, патч
   восстанавливается из fixture) и идемпотентности repair-записей.
   Запуск: `uv --cache-dir /home/user/.cache/uv run --no-project python -m unittest discover -s evals/backends/custom/tests -t .`
7. **`evals/backends/custom/README.md`** — английский: backend-специфичные детали
   (supervisor, history, repair, doctor), которые RUNBOOK не дублирует.
8. **Реальный doctor** — выполнить `... cli.py doctor --backend custom` и
   `opencode --version` (в этом окружении `opencode 1.18.31`) и привести вывод в
   комментарии. Реальный прогон subject'а выполняй только если есть проверенный
   профиль provider/model; если профиля нет — **не выбирай модель сам**, а спроси
   человека в комментарии (это и есть штатный сценарий выбора модели).
9. Телеметрия и безопасность: `opencode` без sharing/auto-update/OTel, внешние плагины
   не загружаются; предел прав subject'а — из плана A (workspace + `uv run pytest`,
   `uv run ruff check`, `git status`, `git diff`); judge read-only; runner не читает
   auth-файлы и не инспектирует process environment.

## Критерии приёмки

- `doctor` (без `--repair`) выполняется и печатает структурированный отчёт; вывод приведён.
- Фейковый subject покрывает success, timeout, malformed JSON, missing model,
  unsupported variant — тесты зелёные, команда и вывод приведены.
- Контракт каталога прогона подтверждён тестом: `manifest.json` проходит
  `evals.core.validate`, есть `result.patch`, `report.md`, `status.json`,
  напечатан `HARNESS_EVAL_ARTIFACT=`.
- Известный incident применяется до первой попытки (тест на подставленном incident'е).
- После трёх безуспешных remedies цикл останавливается (тест).
- `evals/core/**`, `evals/tasks/**`, `evals/HARNESS_MATRIX.md`, `evals/RUNBOOK.md`,
  `AGENTS.md`, `VERSION`, `README.md` не изменены: соответствующие `git diff` пусты.
- В коммитах нет секретов и абсолютных путей: `git grep -nE '/home/[a-z]' HEAD -- evals/backends` пуст.

## Общие рамки

- Работай в своём worktree (его выдал runtime), не в `/home/user/my/python-harness`.
  Коммить мелкими шагами Conventional Commits: незакоммиченное не видно ревью.
- Прочитай корневой `AGENTS.md` репозитория целиком — это правила проекта.
- Документы в репозитории — на английском; пояснения в комментарии можно на русском.
- Перед реализацией набросай короткий план в `memory/.tmp/` (не коммить), ориентир —
  `HARNESS_ANALYSIS_TEMPLATE.md`.
- Только stdlib; Python — через uv с существующим кэшем (`--cache-dir /home/user/.cache/uv`).
- Smoke-артефакты — в `memory/.tmp/evals/` (gitignored); прогоны в `evals/history/`
  не коммить, историю создаёт реальный эксперимент пользователя.
- В конце: пуш ветки в `origin` и PR с заголовком `<ключ своей задачи>: <краткое описание>`
  (ключ вида `MY-48`, без closing keywords вроде `Closes`), в комментарии — ветка,
  путь worktree, команды ревью (`git diff dev...<branch>`), PR URL, что проверено и чем.

Если упираешься в пробел общего слоя — не форкай его: сделай адаптер в
`evals/backends/custom/` и явно опиши пробел в финальном комментарии.
