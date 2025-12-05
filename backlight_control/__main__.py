import asyncio
import logging
from os import R_OK, access, path
import sys

import yaml

from .hub import LightControlHub

CONF_LOG_LEVEL = "log_level"


async def main_coro(config):
    logging.basicConfig(
        level=getattr(logging, config.get(CONF_LOG_LEVEL, ""), logging.INFO)
    )
    mon = LightControlHub(config)
    try:
        await mon.start()
    except asyncio.CancelledError:
        mon.stop()


def print_usage():
    print(f"Usage: {sys.argv[0]} <config_file>")


def main():
    if len(sys.argv) != 2:
        print_usage()
        exit(1)
    if not (path.isfile(sys.argv[1]) and access(sys.argv[1], R_OK)):
        print(f"Path is not a file or not readable:\n\t{sys.argv[1]}\n")
        print_usage()
        exit(1)
    try:
        with open(sys.argv[1]) as config_file:
            config = yaml.safe_load(config_file.read())
    except OSError as e:
        print(f"Failed to read config file:\n\t{sys.argv[1]}\n\t{e}\n")
        print_usage()
        exit(1)
    asyncio.run(main_coro(config))


if __name__ == "__main__":
    main()
