from __future__ import annotations

import logging
import os
import sys
import typing as t
from logging import StreamHandler, FileHandler
handler_console = StreamHandler(stream=sys.stdout)
handler_console.setLevel(logging.DEBUG)


logging_handlers = [
        handler_console,
]

logging.basicConfig(
    format="%(asctime)s | %(name)25s | %(funcName)25s | %(levelname)6s | %(message)s",
    datefmt="%b %d %H:%M:%S",
    level=logging.DEBUG,
    handlers=logging_handlers
)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
log = logging.getLogger(__name__)


