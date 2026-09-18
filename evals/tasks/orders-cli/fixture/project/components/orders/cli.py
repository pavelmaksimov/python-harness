"""Orders command-line entry point."""

import argparse
import asyncio

from project.components.orders.repositories import OrderRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orders")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", default="NEW")

    cancel_parser = subparsers.add_parser("cancel")
    cancel_parser.add_argument("order_id", type=int)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = OrderRepository()

    if args.command == "list":
        for order in asyncio.run(repository.all()):
            print(f"{order['id']}\t{order['status']}")
        return 0

    if args.command == "cancel":
        answer = input(f"cancel order {args.order_id}? [y/N] ")
        if answer.strip().lower() != "y":
            print("aborted")
            return 1
        asyncio.run(repository.cancel(args.order_id))
        print(f"order {args.order_id} cancelled")
        return 0

    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
