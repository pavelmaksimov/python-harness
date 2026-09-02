---
name: ubiquitous-language
description: Maintains one project-wide DDD ubiquitous-language glossary while domain behavior is designed or changed. MUST USE when naming or renaming domain concepts, usecase, services, commands, events, states, or policies; creating or auditing the glossary; or reconciling business language with code. Not for generic Python, framework, or infrastructure names.
---

# Ubiquitous Language

Keep business conversation, requirements, tests, APIs, and code aligned around the same
domain terms. Treat code as evidence of current usage, not automatic authority over the
domain expert's meaning.

## Find the language

Keep exactly one glossary document. Use the user's path when specified; otherwise use root
`CONTEXT.md`. Create it lazily when the first term is agreed, not during installation. If the
repository already has several domain glossary documents, propose consolidating them into the
single chosen file instead of creating or maintaining another one.

## Work language-first

Before introducing or renaming a durable domain-bearing name:

1. Read the project glossary and search it for the proposed term and likely synonyms.
2. Search domain code, tests, API contracts, and requirements for how the concept is used.
3. Reuse the canonical term when it already means the intended concept.
4. If one word carries different meanings, or several words appear to mean the same thing,
   state the collision and ask the user or domain expert to settle the meaning. Every canonical
   name must have one project-wide meaning: qualify intersecting names into distinct terms such
   as `BillingAccount` and `UserAccount` instead of reusing `Account` in separate areas.
5. Once resolved, update the glossary in the same task, then use the canonical term in new
   or changed code with the repository's normal casing.

Do not block on generic technical names such as transport clients, serializers, framework
handlers, or local loop variables. The glossary owns business meaning, not the whole source
tree.

## Glossary format

`CONTEXT.md` is a glossary, not a design document or implementation inventory:

```markdown
# Ordering

The language used to accept and manage customer orders.

## Language

**Order**:
A customer's confirmed request to buy one or more products at agreed terms.
_Avoid_: Purchase, transaction

**Order Placed**:
A domain event stating that an Order was accepted.
_Avoid_: Order created, new order
```

- Define what a term **is** in one or two sentences, including a nearby non-example only
  when it prevents a real confusion.
- Pick one canonical term and put rejected synonyms under `_Avoid_`.
- Include only project-specific domain concepts. Omit modules, libraries, storage details,
  generic DDD vocabulary, and speculative terms.
- Preserve the language already chosen for the glossary. When the business term and code
  identifier must use different languages, add a `_Code_: CanonicalIdentifier` line rather
  than silently translating it differently across files.
- Group terms only when useful; keep entries easy to scan and search.

The document may group terms under domain-area headings, but a canonical name appears once and
has one meaning across the project. Do not create `CONTEXT-MAP.md` or nested `CONTEXT.md` files.

## Evolve the model deliberately

- **Add** a term only for a distinct, understood concept.
- **Rename** when wording changes but meaning does not; keep the old wording under `_Avoid_`
  while it remains likely to appear in code or conversation.
- **Split** an overloaded term into uniquely named concepts when it hides two meanings.
- **Merge** synonyms when they describe one meaning; keep one canonical term.
- **Retire** a term when the concept no longer exists; remove it when no maintained artifact
  needs the old vocabulary for comprehension.

When code contradicts the glossary, report the exact mismatch. Fix a small in-scope mismatch;
ask before a broad or compatibility-sensitive rename. Never rewrite existing APIs, events, or
database fields merely to make an audit green.

Record architectural decisions separately and sparingly. An ADR is appropriate only when a
decision is hard to reverse, surprising without context, and the result of a real trade-off.

## Audit

When asked for a language audit, compare durable domain names in code, tests, contracts, and
requirements with the project glossary. Report canonical matches, rejected synonyms, term
collisions, missing concepts, and duplicated meanings. Propose the smallest reconciliation;
do not apply mass renames without approval.

The task is complete when every domain term introduced or changed by the task is either aligned
with the project glossary or surfaced as an unresolved user decision, and each resolved model
change is captured in the glossary.
