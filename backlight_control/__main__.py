import asyncio
from contextlib import suppress
import logging
import sys

import yaml

from .hub import LightControlHub

CONF_LOG_LEVEL = 'log_level'


async def main_coro(config):
    logging.basicConfig(
        level=getattr(logging, config.get(CONF_LOG_LEVEL, ""), logging.INFO))
    mon = LightControlHub(config)
    with suppress(asyncio.CancelledError):
        await mon.start()

def print_usage():
    print(f"Usage: {sys.argv[0]} <config_file>")

def main():
    if len(sys.argv) != 2:
        print_usage()
        exit(1)
    try:
        with open(sys.argv[1], 'r') as config_file:
            config = yaml.safe_load(config_file.read())
    except OSError:
        print(f"Failed to read config file: {sys.argv[1]}\n\n")
        print_usage()
        exit(1)
    asyncio.run(main_coro(config))


if __name__ == "__main__":
    main()
