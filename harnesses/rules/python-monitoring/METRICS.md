# llm_common Prometheus metrics

Names use **the package prefix** (today `genapp_`). Do not invent another prefix. Do not paste
private Grafana dashboard URLs.

Process gauges refresh on each `/prometheus` scrape. SQLAlchemy pool gauges do too, once registered.

## HTTP

| Metric | Type | Measures |
|---|---|---|
| `{prefix}http_requests_total` | Counter | HTTP requests |
| `{prefix}http_request_duration_sec` | Histogram | Latency |
| `{prefix}http_request_size_bytes` | Histogram | Request / response size |

Labels: `method`, `status`, `resource`, `app_type`, `env`, `app`. Size also has `direction`.

## Actions

| Metric | Type | Measures |
|---|---|---|
| `{prefix}action_count_total` | Counter | Action runs |
| `{prefix}action_duration_sec` | Histogram | Duration |
| `{prefix}action_size_total` | Counter | Optional payload size |

Labels: `name`, `env`, `app`. Count also has `status`, `error_name`.

## Process

| Metric | Type | Measures |
|---|---|---|
| `{prefix}process_resident_memory_bytes` | Gauge | RSS |
| `{prefix}process_threads` | Gauge | Threads |
| `{prefix}process_cpu_seconds_total` | Gauge | User + system CPU |
| `{prefix}process_soft_page_faults_total` | Gauge | Soft page faults |
| `{prefix}process_hard_page_faults_total` | Gauge | Hard page faults |
| `{prefix}process_voluntary_context_switches_total` | Gauge | Voluntary context switches |
| `{prefix}process_involuntary_context_switches_total` | Gauge | Involuntary context switches |
| `{prefix}glibc_malloc_arena_bytes` | Gauge | `mallinfo2.arena` |
| `{prefix}glibc_malloc_uordblks_bytes` | Gauge | `mallinfo2.uordblks` |
| `{prefix}glibc_malloc_fordblks_bytes` | Gauge | `mallinfo2.fordblks` |
| `{prefix}gc_generation_heap_counter` | Gauge | `gc.get_count()` per generation |

Labels: `env`, `app`. GC also has `generation`.

## LLM (only if the repo already calls LLMs)

| Metric | Type | Measures |
|---|---|---|
| `{prefix}llm_requests_total` | Counter | LLM requests |
| `{prefix}llm_tokens_total` | Counter | Tokens (`token_type`) |
| `{prefix}llm_request_all_tokens` | Histogram | Tokens per request (sum of types) |
| `{prefix}llm_request_tokens` | Histogram | Tokens per request by `token_type` |
| `{prefix}llm_errors_total` | Counter | Domain LLM errors (`name`) |

Shared labels: `env`, `app`, `agent_name`, `model_name`, `provider_name`, `tool_name`, `base_url`,
`is_fallback`. Helpers: `record_llm_request`, `record_llm_usage`, `record_llm_usage_from_response`,
`record_llm_metrics_after_model_request`, `record_llm_validation_error`.

## SQLAlchemy pool (when registered)

| Metric | Type | Measures |
|---|---|---|
| `{prefix}sql_pool_busy_connections` | Gauge | `pool.checkedout` |
| `{prefix}sql_pool_free_connections` | Gauge | `pool.checkedin` |
| `{prefix}sql_pool_size` | Gauge | `pool.size` |
| `{prefix}sql_pool_overflow_connections` | Gauge | `pool.overflow` |

Labels: `database`, `env`, `app`.
