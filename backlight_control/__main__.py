import asyncio
from contextlib import suppress
import logging
import sys

from .hub import LightControlHub


async def main_coro():
    logging.basicConfig(level=logging.DEBUG)
    mon = LightControlHub(int(sys.argv[1]) if len(sys.argv) == 2 else 30)
    with suppress(asyncio.CancelledError):
        await mon.start()


def main():
    asyncio.run(main_coro())


if __name__ == "__main__":
    main()
