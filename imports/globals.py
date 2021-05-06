from typing import TYPE_CHECKING

BOT = None
WEBDICT = {}

if TYPE_CHECKING:
    from imports.main import Main
    BOT: Main