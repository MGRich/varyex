from typing import TYPE_CHECKING

BOT = None

if TYPE_CHECKING:
    from imports.main import Main
    BOT: Main