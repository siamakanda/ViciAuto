#!/usr/bin/env python3
"""ViciAuto — consolidated ViciDial automation TUI (modular entry point)."""

import argparse
import sys

from colorama import Fore, Style, init

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

    try:
        app.run()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted — shutting down.{Style.RESET_ALL}")
        sys.exit(130)


if __name__ == "__main__":
    main()
