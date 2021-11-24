from discord.ext import commands
from typing import TYPE_CHECKING, List, Union, Tuple, Optional

BOTTYPE = commands.bot
if TYPE_CHECKING:
    from imports.main import Main
    BOTTYPE = Main
