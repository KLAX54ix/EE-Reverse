#!/usr/bin/env python3
"""Locate EE's operator new and probe esSegCircel construction."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE  # noqa: E402


def main():
    ee = EE()
    try:
        print("info:", ee.rpc("info"))
        print("\n-- find operator new / delete --")
        for name in ("??2@YAPAXI@Z", "??_U@YAPAXI@Z", "??2@YAPAXI@Z",
                     "??3@YAXPAX@Z", "malloc", "calloc"):
            try:
                r = ee.rpc("findExport", name)
            except Exception as exc:
                r = f"<{exc}>"
            print(f"  {name:<20} -> {r}")
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
