# Rubric — domain-order-lifecycle

Judge the final workspace state against the criteria below. Each criterion is scored
0–4; cite the file paths that carry the evidence.

## identity by id

| Score | Meaning |
|---|---|
| 4 | `Order` is defined once in `project/components/orders/entities.py`, identity is the id, equality and hashing follow identity (not field-by-field comparison), and no universal base class was introduced. |
| 3 | Identity semantics are right but one detail is off (for example hashing left enabled on a mutable entity). |
| 2 | The entity exists but equality is still field-based or inherited from a value-object pattern. |
| 1 | Only the type was renamed; identity is not modelled. |
| 0 | No entity in the domain module; the record stays a dict. |

Evidence: `project/components/orders/entities.py` (class definition, `__eq__`/`__hash__`).

## invariants on every mutation

| Score | Meaning |
|---|---|
| 4 | Constructing an invalid order and calling any public mutator on a state that forbids it raises the component's own error; the rule is enforced inside the entity, not by callers. |
| 3 | Invariants are enforced on the main paths, with one mutator left unchecked. |
| 2 | Invariants exist but live outside the entity (validators called by the use case) or return booleans instead of failing. |
| 1 | Only construction is validated. |
| 0 | No invariant enforcement. |

Evidence: `project/components/orders/entities.py`, `project/components/orders/exceptions.py`.

## declared state transitions

| Score | Meaning |
|---|---|
| 4 | The lifecycle is an explicit state set plus declared transitions; an illegal call fails with the project's FSM error, and no if/else pyramid or string comparison decides legality. |
| 3 | A state enum and a transition table exist, but transitions are still partly decided by hand-written guards. |
| 2 | States are enumerated, transitions are checked with ad-hoc conditionals only. |
| 1 | Status stays a bare string but is centralized in one module. |
| 0 | Transitions remain implicit or scattered. |

Evidence: the order component's domain modules and the FSM helper module.

## layer-safe orchestration

| Score | Meaning |
|---|---|
| 4 | Domain modules import only the standard library, the component's own modules and shared types; the use case resolves collaborators through the composition root, contains no pricing arithmetic and no persistence client, and remains readable at a glance. |
| 3 | Layering is correct but the use case still carries one piece of mechanics (for example response shaping or an extra branch). |
| 2 | The pricing rule moved, but the use case still builds collaborators itself or the domain reaches outside its layer. |
| 1 | Only file names changed; imports still violate the layer boundaries. |
| 0 | The refactor leaves the domain dependent on infrastructure and the use case fat. |

Evidence: the order component's `entities.py` and `use_cases.py`, and the import block of
every touched domain module.
