# DDD Ubiquitous-Language Harness Research

Date: 2026-09-02

## Question

How should a Python coding-agent harness keep domain vocabulary aligned with code as the
model evolves, without turning the glossary into a second schema or a noisy CI gate?

## DDD constraint

Traditional DDD scopes ubiquitous language to a bounded context and can therefore permit one
word to carry different meanings across contexts. This catalog deliberately chooses a stricter
project convention: one glossary document and one project-wide meaning per canonical name.
When meanings differ, the concepts receive distinct names instead of overlapping by context.
The language is developed with domain experts and used in conversation, documentation, tests,
and code
([Eric Evans' DDD Reference](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf),
[Martin Fowler on Bounded Context](https://martinfowler.com/bliki/BoundedContext.html),
[Microsoft's domain-analysis guidance](https://learn.microsoft.com/azure/architecture/microservices/model/domain-analysis)).

This gives the harness a clear ownership rule:

- code, schemas, APIs, tests, and history show which names exist;
- the agreed glossary and domain experts decide what those concepts mean;
- the agent detects disagreement and keeps the two aligned;
- ambiguous meaning is a user decision, not an opportunity for the agent to guess.

## Existing approaches

| Approach | Useful mechanism | Limitation for this catalog |
|---|---|---|
| [CodeAlive-AI `ubiquitous-language`](https://github.com/CodeAlive-AI/ai-driven-development/tree/main/skills/ubiquitous-language) | Proactive lookup; grep-first Index; canonical, forbidden, legacy, unresolved, and context-tagged names; explicit add/rename/split/merge lifecycle; optional Git-history mining | Excellent brownfield toolbox, but the frequent-path skill, format versioning, registry invariants, and SQLite history index are too much machinery for the first Python-harness version |
| [helderberto `domain-modeling`](https://github.com/helderberto/agent-skills/blob/main/skills/domain-modeling/SKILL.md) | Small `CONTEXT.md`; tight definitions and Avoid lists; terms are sharpened with concrete edge cases and updated as they crystallize | No systematic audit or legacy registry |
| [ZunoSmartLabs `domain-modeling`](https://github.com/ZunoSmartLabs/zsl-superpowers/blob/main/skills/engineering/domain-modeling/SKILL.md) | Context-local `CONTEXT.md`, root `CONTEXT-MAP.md`, and deliberately sparse ADRs | Broader domain-modeling package than vocabulary maintenance alone |
| [mattpocock deprecated `ubiquitous-language`](https://github.com/mattpocock/skills/tree/main/skills/deprecated/ubiquitous-language) and [softspark variant](https://github.com/softspark/ai-toolkit/blob/main/app/skills/ubiquitous-language/SKILL.md) | Extract terms, synonyms, relationships, examples, and ambiguities from a conversation into one file | Mostly an explicit one-shot generation flow; weak connection to subsequent code changes |
| [Microsoft DDD design skill](https://github.com/microsoft/amplifier-bundle-systems-design/tree/main/skills/design-philosophy-domain-driven) | Treats language collisions as evidence of a missing context boundary and separates strategic from tactical DDD | Architecture lens rather than an operational glossary workflow |
| [aristorinjuang `ddd-agent-skill`](https://github.com/aristorinjuang/ddd-agent-skill) | Full assess, Event Storming, context map, tactical model, implementation, and audit lifecycle | Much broader than the requested language harness; would make a glossary opt-in drag in an entire DDD process |
| [fabriqaai `conceptual-model-pass`](https://github.com/fabriqaai/conceptual-model-pass) | Language-first review gates, term classification, competency questions, and separation of domain meaning from implementation | Strong for planning sessions, but not a persistent repository feedback loop |
| [DDD Crew context mapping](https://github.com/ddd-crew/context-mapping) | Makes relationships and translations between bounded contexts explicit; recommends small maps built for a concrete question | Collaborative modeling material, not an agent-installable maintenance skill |
| [Context Mapper](https://github.com/ContextMapper/context-mapper-dsl) | Machine-readable context model, validators, diagrams, service contracts, and architecture checks | Adds a DSL and JVM-oriented toolchain; disproportionate for a Markdown vocabulary layer in Python projects |
| [jMolecules](https://github.com/xmolecules/jmolecules) | DDD semantics become explicit code markers that ArchUnit and other tooling can verify | Java-specific; Python already has separate `layers-linter` and `domain-types-linter` concerns |
| [`dddlint`](https://github.com/benomahony/dddlint) | Path/context-scoped forbidden words, aliases, duplicate-name detection, CI/pre-commit/LSP integration | Young and fast-moving; would duplicate glossary configuration, and the inspected repository metadata did not establish a license suitable for vendoring |

## What to keep from the alternatives

The useful common core is small:

1. **Consult before naming.** Search the glossary before a durable domain name is added or
   renamed. This is the missing feedback loop in one-shot glossary generators.
2. **Code is evidence, not authority.** Existing identifiers show current usage, including
   drift and legacy mistakes; they do not settle business meaning.
3. **Canonical term plus Avoid list.** This gives both forward guidance and a cheap reverse
   lookup for known synonyms without a separate configuration file.
4. **Human-gated ambiguity.** Synonym and polysemy detection can be automated; choosing the
   intended meaning or declaring a context boundary cannot.
5. **Project-wide unique language.** Keep one glossary. If a term carries several meanings,
   split it into distinct canonical names such as `BillingAccount` and `UserAccount`.
6. **Explicit evolution.** Distinguish add, rename, split, merge, and retire. A wording change
   is not the same as a model change.
7. **Audit without automatic mass rename.** Contracts, persisted fields, and events may carry
   compatibility obligations even when their language is stale.
8. **ADRs only for load-bearing decisions.** A context boundary, ownership transfer, or
   consequential semantic split may deserve an ADR; an ordinary new noun does not
   ([MADR](https://adr.github.io/madr/)).

## Selected design for `python-harness`

The catalog should add one optional installable skill named `ubiquitous-language` and a small
handoff in the existing always-on `python-workflow` rule.

### Artifact

- Keep exactly one root `CONTEXT.md` and create it only after the first term is agreed.
- Keep it a glossary: term, one- or two-sentence definition, and rejected synonyms under
  `_Avoid_`.
- Keep implementation inventories, database details, generic DDD vocabulary, and speculative
  terms out.
- Preserve the project's glossary language. Add an optional `_Code_` mapping only when the
  business language and code language differ.
- Group terms by domain area inside that file when useful, but never duplicate a canonical name
  or create context-specific glossary files.

`CONTEXT.md` was chosen over CodeAlive's `docs/THESAURUS.md` because it gives the project both
the context and its language in one small convention. It also avoids a format version, a
duplicated machine registry, multiple context documents, and several permanent empty sections
before real usage proves they are needed.

### Trigger and lifecycle

The installed skill runs when a task creates or renames a domain concept, command, event,
state, or policy, or when the user asks to model or audit terminology.
Generic framework and infrastructure names do not trigger it.

For each affected concept the agent:

1. reads the single project glossary;
2. searches code, tests, contracts, and requirements for current usage;
3. reuses the canonical term, or surfaces a synonym/polysemy collision;
4. asks the user only when business meaning remains unresolved;
5. updates the glossary in the same task once the meaning is agreed;
6. uses the approved term in new or changed artifacts;
7. reports broad or compatibility-sensitive renames instead of applying them silently.

The glossary therefore behaves like a steering wheel rather than a museum label: every new
domain-bearing name passes it on the way into the code, and discoveries from the code flow
back into it.

## Deliberately deferred

- No third-party dependency or new linter.
- No CI failure on unknown identifiers; that would confuse technical vocabulary with domain
  vocabulary.
- No global forbidden-word list. Words such as `Service`, `Handler`, or `Model` are sometimes
  valid outside the domain layer.
- No `CONTEXT-MAP.md` or nested glossaries; domain-area grouping stays inside `CONTEXT.md`.
- No versioned glossary format or duplicate YAML configuration.
- No SQLite Git-history index. Plain `git log`, `git show`, and `git blame` are sufficient
  until recurring brownfield ambiguity proves otherwise.
- No generated diagrams or context DSL.

If deterministic enforcement becomes necessary, the narrow next step is a checker that reads
known `_Avoid_` entries and scans explicitly configured domain paths. It should not attempt to
infer new business concepts or context boundaries.

## Relationship to the existing catalog

- `ubiquitous-language` owns **what a domain concept is called and means here**.
- `domain-types-linter` owns **where primitives must become domain-specific Python types**.
- `layers-linter` owns **which modules and contexts may import each other**.
- tests own **the executable behavior described with those terms**.
- ADRs own **why a costly or surprising semantic/boundary decision was made**.

These layers reinforce each other without duplicating configuration or responsibility.
