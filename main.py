from discord.ext import commands
from discord import Intents, Status, Game
from datetime import datetime

from bot.utils.extensions import EXTENSIONS
from bot.constants import DEBUG_SERVER_ID, PREFIX, DISCORD_TOKEN


class Bot(commands.Bot):
    EXTENSIONS = EXTENSIONS  # type: ignore

    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            case_insensitive=True,
            status=Status.dnd,
            activity=Game(name="with your mind"),
            debug_guilds=[DEBUG_SERVER_ID],
        )

        self.active_since = datetime.now()

        for ext in EXTENSIONS:
            self.load_extension(ext)

    async def on_ready(self):
        print(f"{bot.user.name} is on ready.")  # type: ignore


bot = Bot()

bot.run(DISCORD_TOKEN)
