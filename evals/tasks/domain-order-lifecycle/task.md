# Task

`project/components/orders/` grew around a "service" that keeps orders as dicts of dicts,
plus an anemic `Order` record that saves itself through the composition root. The team
wants a real domain model in this component.

Rework the component so that:

- an `Order` is identified by its id alone — two orders with the same id are the same
  order, whatever else changed;
- an order protects its own invariants at construction and on every public mutation;
- the status lifecycle is explicit and declared: `NEW → PAID`, `NEW → CANCELLED`,
  `PAID → CANCELLED`; every other transition is a bug and must fail loudly, and the
  allowed transitions are described as such instead of being implied by if/else chains;
- `pay()` and `cancel()` are the only ways to move an order forward; `cancel()` on a
  `PAID` or `CANCELLED` order raises `OrderCannotBeCancelled`;
- pricing (item subtotal − customer discount + 20% VAT) is reusable domain logic instead
  of inline arithmetic inside the use case;
- business-logic annotations name the project's domain types, not bare primitives;
- the use case stays a thin scenario: it resolves its collaborators through the project's
  composition root and delegates the arithmetic and the state changes to the domain.

There is no service layer in this project, and the domain must stay free of
infrastructure, composition-root and persistence imports.

`uv run python -c "from project.components.orders.entities import Order"` must work.
