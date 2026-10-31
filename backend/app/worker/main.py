"""Fail closed until durable queue and checkpoint adapters are implemented."""

import sys


def main():
    print(
        "Worker unavailable: PostgreSQL job leasing and durable checkpoint storage are not wired.",
        file=sys.stderr,
    )
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
