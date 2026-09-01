#!/usr/bin/env python3
"""ViciAuto — consolidated ViciDial automation TUI (modular entry point)."""

import argparse

from colorama import init

from viciauto_core.app import ViciAutoApp

init(autoreset=True)


def main():
    parser = argparse.ArgumentParser(description="ViciAuto — ViciDial automation TUI.")
    parser.add_argument("--list-profiles", action="store_true", help="Show saved profiles and exit")
    args = parser.parse_args()

    app = ViciAutoApp()

    if args.list_profiles:
        app.config.list_profiles()
        return

    app.run()


if __name__ == "__main__":
    main()
