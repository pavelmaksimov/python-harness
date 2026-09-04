---
name: python-stdlib-first-review
description: MUST USE for reviewing Python code for stdlib and batteries-included replacement opportunities — before hand-rolling iteration, caching, or data-structure helpers.
---

# Python stdlib review

Suggest-mode review knowledge: spot a hand-rolled shape, name the exact
batteries-included replacement, check the trap. This catalog owns the skill;
the products belong to upstream (CPython stdlib needs no install;
`cachetools` is `uv add cachetools` only when used).

## How to review

1. Match the **hand-rolled shape** in the tables below.
2. Suggest the **use-instead** call with a one-line diff sketch. Soft tone:
   suggestion, not a blocker — the author may have a measured reason.
3. Check **Traps** before commenting; drop the suggestion when a trap fires.

## itertools

| Hand-rolled shape | Use instead | Notes |
|---|---|---|
| Nested `for` flattening lists | `itertools.chain.from_iterable(rows)` | Lazily flattens one level |
| Manual sliding window / `items[i], items[i+1]` | `itertools.pairwise(it)` (3.10+) | Yields consecutive pairs |
| Manual chunking loop with index arithmetic | `itertools.batched(it, n)` (3.12+) | Last batch may be short |
| Manual group accumulation into dicts | `itertools.groupby(sorted_rows, key=...)` | Input must be sorted by the same key first |
| Nested loops over two lists | `itertools.product(a, b)` | Add `repeat=` for powers |
| Recursive permute/combine helpers | `permutations`, `combinations`, `combinations_with_replacement` | Prefer over hand recursion |
| Manual running total in a loop | `itertools.accumulate(it)` | Accepts `func` and `initial` |
| Manual `zip` with fill value | `itertools.zip_longest(a, b, fillvalue=...)` | Uneven lengths only |
| Manual skip/take loops | `islice`, `takewhile`, `dropwhile`, `filterfalse`, `compress` | Compose instead of flag variables |
| `map(f, ...)` with tuple unpacking | `itertools.starmap(f, pairs)` | Cleaner than `lambda t: f(*t)` |
| `while` counter / toggle loop | `count`, `cycle`, `repeat` | Infinite — always pair with a stop |

## functools

| Hand-rolled shape | Use instead | Notes |
|---|---|---|
| Manual `dict` memo cache in function body | `functools.lru_cache(maxsize=...)` / `functools.cache` (3.9+) | Args must be hashable; no TTL |
| Per-instance lazy attribute with `_cache` field | `functools.cached_property` | No setter; subclass override replaces it |
| `lambda` / closure only fixing leading args | `functools.partial(f, arg)` | Keeps `__name__` intent clearer than lambda |
| Manual accumulation loop (`total = ...; for ...`) | `functools.reduce(f, it, initial)` | Only when no builtin (`sum`, `min`, `max`, `any`, `all`) fits |
| Decorator losing `__name__` / signature | `functools.wraps(f)` | Always in custom decorators |
| Manual `<`/`==` boilerplate for ordering | `functools.total_ordering` | Define `__eq__` + one ordering method |
| `if/elif` chain switching on argument type | `functools.singledispatch` | Extensible without touching the dispatcher |

## cachetools (only third-party here)

Package: `uv add cachetools`. API: `cached(cache)`, `cachedmethod`,
`TTLCache(maxsize, ttl)`, `LRUCache(maxsize)`, `LFUCache`, `RRCache`,
`keys.hashkey` for custom keys.

| Hand-rolled shape | Use instead | Notes |
|---|---|---|
| `lru_cache` that also needs expiry | `@cached(TTLCache(maxsize=..., ttl=...))` | TTL evicts only on access; pick `timer` deliberately |
| Shared eviction across several functions | One `LRUCache` object passed to several `@cached(cache)` | Shared accounting beats per-function `maxsize` |
| Per-method memo dict on `self` | `cachetools.cachedmethod(lambda self: self.cache)` | Cache lives with the instance |
| Manual `time.time()` expiry bookkeeping | `TTLCache` | Deletes the timestamp-compare block |

## collections, heapq, bisect, operator

| Hand-rolled shape | Use instead | Notes |
|---|---|---|
| Manual frequency dict (`d[k] = d.get(k, 0) + 1`) | `collections.Counter` + `most_common(n)` | Arithmetic (`+`, `-`, `\|`) composes multisets |
| `dict.setdefault` / `if k not in d` init pattern | `collections.defaultdict(list)` (or `set`, `int`) | Changes missing-key semantics — see traps |
| List as queue with `pop(0)` | `collections.deque` (`popleft`/`append`) | `pop(0)` is O(n); deque is O(1) |
| `sorted(...)[:n]` / `[-n:]` for leaders | `heapq.nlargest(n, it)` / `nsmallest` | Avoids full sort; `key=` supported |
| Manual k-way merge of sorted inputs | `heapq.merge(*sorted_lists)` | Lazy, single sorted stream |
| Manual sorted-insert loop | `bisect.insort(lst, x)` / `bisect_left` / `bisect_right` | Keeps the list sorted invariant |
| `lambda x: x["key"]` / `x.attr` sort keys | `operator.itemgetter` / `attrgetter` / `methodcaller` | Faster and picklable |
| Ad-hoc record class with `__repr__`/`__eq__` | `collections.namedtuple` (or stdlib `dataclass`) | Named fields with tuple semantics |

## Other stdlib sightings

| Hand-rolled shape | Use instead | Notes |
|---|---|---|
| `os.path.join` / string path surgery | `pathlib.Path` (`/` operator, `.glob`, `.read_text`) | Never concatenate separators by hand |
| Manual mean/median/stdev | `statistics.mean` / `median` / `stdev` | Knows empty-input and precision edge cases |
| `name in ("if", "for", ...)` keyword check | `keyword.iskeyword(name)` / `keyword.kwlist` | Tracks version-specific keywords |
| Manual line-wrap / indent-strip / `...` truncation | `textwrap.wrap` / `fill` / `dedent`, truncation via `shorten(text, width)` | `shorten` collapses whitespace and appends `placeholder=" [...]"` (counts toward `width`); `break_long_words` / `break_on_hyphens` options |
| Manual min/max loop | Builtins `min` / `max` with `key=` and `default=` | `default=` covers the empty case |
| Manual index loop (`for i in range(len(x))`) | `enumerate(x)` (add `start=`) | Pairs naturally with unpacking |
| Manual parallel loop with indexing | `zip(a, b)` / `zip(..., strict=True)` (3.10+) | `strict=True` catches length drift |

## Traps (drop the suggestion when they fire)

- `groupby` only groups **consecutive** equal keys — unsorted input silently
  yields duplicate groups. Demand the `sorted()` call in the same diff.
- `lru_cache` / `cache` never expire, pin `self` on methods (leak), and fail on
  unhashable args (list/dict). TTL or size sharing → `cachetools`.
- `batched` (3.12+) / `pairwise` (3.10+) / `zip(strict=True)` (3.10+) are
  version-gated — check the repo's minimum Python before suggesting.
- `Counter` / `defaultdict` change missing-key behavior from `KeyError` to a
  default — when the `KeyError` is load-bearing, keep the plain `dict`.
- `reduce` hurts readability when a builtin or comprehension says it directly;
  suggest it only after `sum`/`min`/`max`/`any`/`all`/comprehension fail.
- `heapq` needs the heap invariant (`heapify` first); it is not a substitute
  for a general sort of an already-materialized list.
- `TTLCache` eviction happens lazily on access, not in the background — never
  suggest it as a real-time expiry guarantee.

## When not to apply

- The hand-rolled version carries measured performance or domain semantics
  (early exit, custom ordering, bounded memory) the library call would lose.
- The repo pins an older Python than the suggested helper requires.
- Test doubles or teaching examples where explicitness is the point.

## Review comment shape

`Suggest: replace <hand-rolled shape> with <exact call> — <one-line why>.
Trap checked: <trap>.` One suggestion per shape; never block the review on
this skill alone.
