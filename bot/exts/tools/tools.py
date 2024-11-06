from discord.commands import slash_command
from discord.ext import commands
from discord import ApplicationContext, File
import string
from os import path, getenv
from io import StringIO
from bot.constants import DEBUG_SERVER_ID
from cloudflare import AsyncCloudflare

printable = ["▲", *string.printable]


def remove_ascii_codes(text):
    """
    Removes ASCII codes from text while preserving readable characters.

    Args:
        text (str): Input text containing ASCII codes

    Returns:
        str: Cleaned text with ASCII codes removed
    """
    cleaned_text = "".join(char for char in text if char in printable)
    return cleaned_text


class Tools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = AsyncCloudflare()

    @slash_command(name="show-logs", guild_ids=(DEBUG_SERVER_ID,))
    async def show_logs(self, ctx: ApplicationContext, project_name: str, link: str):
        deployment_id = path.basename(link)
        logs: dict = await self.client.pages.projects.deployments.history.logs.get(
            deployment_id,
            account_id=getenv("CLOUDFLARE_ACCOUNT_ID"),
            project_name=project_name,
        )  # type: ignore

        data = StringIO(
            "\n".join(
                f"{l['ts']}\t{remove_ascii_codes(l['line'])}"
                for l in logs["data"]
                if any(a in l["line"] for a in ["WARN", "▲", "⚡️"])
            )
        )

        await ctx.respond(files=[File(data, filename="log.txt")])  # type: ignore


def setup(bot):
    bot.add_cog(Tools(bot))
    print("Tools.cog is loaded")
