from __future__ import annotations

if __name__ == "__main__":
    import locale
    import sys

    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error as error:
        print(f"[commander] failed to use system locale: {error}", file=sys.stderr)

    from commander.app import main

    raise SystemExit(main())
