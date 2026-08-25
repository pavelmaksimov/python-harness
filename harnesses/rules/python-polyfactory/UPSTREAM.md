# Upstream map (maintainers only)

Refresh this catalog ID from Polyfactory docs. Do not link this file from
`.mdc` bodies or agent-facing siblings — it is for humans (or agents) updating
**python-harness**, not for day-to-day coding in a target repo.

Index: https://polyfactory.litestar.dev/latest/usage/index.html  
Package: https://github.com/litestar-org/polyfactory · PyPI `polyfactory`

| Local file | Refresh from |
|---|---|
| `python-polyfactory.mdc` | [Usage index](https://polyfactory.litestar.dev/latest/usage/index.html), [Declaring factories](https://polyfactory.litestar.dev/latest/usage/declaring_factories.html), [SQLAlchemyFactory](https://polyfactory.litestar.dev/latest/usage/library_factories/sqlalchemy_factory.html), [Factory configuration](https://polyfactory.litestar.dev/latest/usage/configuration.html) (persistence only) |
| `FACTORIES.md` | [Pydantic ModelFactory](https://polyfactory.litestar.dev/latest/usage/declaring_factories.html) (pydantic section), [SQLAlchemyFactory](https://polyfactory.litestar.dev/latest/usage/library_factories/sqlalchemy_factory.html) |
| `FIELDS.md` | [Factory fields](https://polyfactory.litestar.dev/latest/usage/fields.html), [post_generated](https://polyfactory.litestar.dev/latest/usage/decorators.html) |
| `CUSTOM_TYPES.md` | [Handling custom types](https://polyfactory.litestar.dev/latest/usage/handling_custom_types.html) |
| `COVERAGE.md` | [Model coverage](https://polyfactory.litestar.dev/latest/usage/model_coverage.html) |

Stack constraints (do not reintroduce from upstream):

- Call factories on the class — no [pytest fixtures](https://polyfactory.litestar.dev/latest/usage/fixtures.html).
- Persist ORM via `atransaction()` / `asession()` (`python-db-sessions`), not `__async_session__` + `commit()`.
- Keep Beanie / Odmantic / attrs / msgspec / TypedDict examples out unless the catalog gains those IDs.
