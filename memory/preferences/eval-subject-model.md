# Модели subject и judge для harness-eval экспериментов

Источник: комментарии vur21 в MY-45 (2026-09-17).

## Subject (тестируемый агент)

«Когда дойдёшь до запуска экспериментов, используй opencode/go deepseek flash 4.1 low» (дословно).
- Provider: каталог `opencode`; модель — семейство DeepSeek Flash 4.1; variant — `low`.

## Judge (оценщик)

«Для судьи модель opencode/zai glm flash 5.3 flash max» (дословно).
- Provider: `opencode`, провайдер `zai`; модель — семейство GLM Flash 5.3; «flash max» —
  вероятно variant/max-режим; точное сопоставление по каталогу моделей при первом прогоне.

## Правила применения (общие)

- Точные model ID сверяются через `opencode models <provider> --verbose` перед первым
  прогоном; неоднозначное сопоставление — показать кандидатов пользователю.
- Профили сохраняются в `evals/knowledge/providers/` только после успешного smoke/run
  (правило планов A/B: модель молча не подменяется).
- Subject и judge — два разных фиксированных профиля; не смешивать.

## Прогресс

- Задача MY-45 (лаборатория экспериментов); stage 1 done (MY-46 core, MY-47 probes);
  stage 2 в работе: MY-48 (custom runner), MY-49 (OpenResearch).
