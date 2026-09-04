# MIGRATION — Service → Entity

Catalog-only on-demand prompt. Never copied to a target repository and never read
during normal install, authoring, or bootstrap. Open this file only when the user
explicitly requests a `Service → Entity migration`, then agree a separate migration
plan before editing anything.

`python-architecture` targets rich Entities (`python-entity.mdc`); `service.py` and
the `services` layer are legacy signals, not an alternative style. Migrate one
vertical scenario at a time and keep the linters green throughout.

## Steps

1. **Inventory.** List every public method of the component's `*Service` classes
   and all their callers.
2. **Classify** each method:
   - invariant or state change of one Entity → Entity method in `entities.py`;
   - pure rule with no natural single owner → named module-level domain function
     in `entities.py`;
   - I/O, transactions, scenario authorization, idempotency, retry, orchestration
     → Use Case method in `use_cases.py`.
3. **Move one vertical scenario at a time**, updating its tests in the same change.
   Entities stay pure: no `Container()`, no sessions, no ORM objects.
4. **Update the Repository** mapping for the moved Entity (`_to_entity` /
   `_update_row`; see `python-sqlalchemy.mdc`).
5. **Remove the old path** only after its last consumer is migrated: delete the
   `*Service` method, then `service.py`, then replace the `services` layer with
   `domain` in `layers.toml`.
6. **Verify:** `uv run la-linter project`, `dt-linter` on the entity / use-case
   paths, and the full test suite. Fix every finding before moving to the next
   scenario.

Stop and ask when a method mixes concerns: split it into its Entity, domain
function, and Use Case parts during classification instead of migrating it
verbatim.
