import psutil

from discord.ext import commands
from discord.commands import slash_command
from discord.commands.context import ApplicationContext
from discord import Embed
from discord.commands.options import Option
from discord.utils import format_dt

from bot.utils.checks import is_admin
from bot.utils.extensions import EXTENSIONS
from bot.constants import DEBUG_SERVER_ID


OPT_EXTS = [e.split('.')[-1] for e in EXTENSIONS]

class AdminIO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.extension_state = []

    @slash_command(name="load", guild_ids=(DEBUG_SERVER_ID,))
    @commands.check(is_admin)
    async def load_cog(self, ctx: ApplicationContext, extension: str):
        """Loads a unloaded cog to the bot."""
        for ext in EXTENSIONS:
            if ext.split(".")[-1] == extension:
                self.bot.load_extension(ext)
                await ctx.respond("☑️", ephemeral=True)
                return
        await ctx.respond("❎", ephemeral=True)

    def get_progress_bar(self, percent, full, empty):
        """
        Get the visible requirement to meet 100% of an arbitrary
        limit or goal.
        """
        percentage = round(percent * 20)
        return (
            "".join([full if i < percentage else empty for i in range(20)])
            + f" [{percent * 100}%]"
        )

    @slash_command(name="sysinf", guild_ids=(DEBUG_SERVER_ID,))
    @commands.check(is_admin)
    async def uptime(self, ctx: ApplicationContext):
        """
        View host system information.
        """
        cpu_percent = psutil.cpu_percent()
        ram_percent = psutil.virtual_memory().percent

        cpu_usage = self.get_progress_bar(cpu_percent / 100, "⣿", "⣀")
        ram_usage = self.get_progress_bar(ram_percent / 100, "⣿", "⣀")
        embed = (
            Embed(title="Contemporary Info")
            .set_author(name="SYSTEM INFORMATION")
            .add_field(
                name="Uptime",
                value=f"{format_dt(self.bot.active_since, 'F')}"
                f"\n{format_dt(self.bot.active_since, 'R')}",
            )
            .add_field(name="CPU", value=f"```{cpu_usage}```", inline=False)
            .add_field(name="RAM", value=f"```{ram_usage}```", inline=False)
        )
        await ctx.respond(embed=embed)

    @slash_command(name="unload", guild_ids=(DEBUG_SERVER_ID,))
    @commands.check(is_admin)
    async def unload_cog(
        self,
        ctx: ApplicationContext,
        extension: Option(str, choices=OPT_EXTS), # type:ignore
    ):
        """
        Unloads an loaded cog to the bot.
        """
        for ext in EXTENSIONS:
            if ext.split(".")[-1] == extension:
                self.bot.unload_extension(ext)
                await ctx.respond("☑️", ephemeral=True)
                return
        await ctx.respond("❎", ephemeral=True)

    @slash_command(name="reload", guild_ids=(DEBUG_SERVER_ID,))
    @commands.check(is_admin)
    async def reload_cog(
        self,
        ctx: ApplicationContext,
        extension: Option(str, choices=OPT_EXTS), # type:ignore
    ):
        """
        Reloads a loaded cog to the bot.
        """
        for ext in EXTENSIONS:
            if ext.split(".")[-1] == extension:
                try:
                    self.bot.reload_extension(ext)
                except:
                    pass
                await ctx.respond("☑️", ephemeral=True)
                return
        await ctx.respond("❎", ephemeral=True)

    @slash_command(name="restart", guild_ids=(DEBUG_SERVER_ID,))
    @commands.check(is_admin)
    async def restart(self, ctx: ApplicationContext):
        """
        Reloads every cog connected to the bot.
        """
        faulty = ""
        excep = None
        for ext in EXTENSIONS:
            try:
                self.bot.reload_extension(ext)
            except Exception as e:
                excep = e
                faulty += f"\n`{ext}`"
        if excep:
            await ctx.respond(f"❎ {faulty}", ephemeral=True)
            raise excep
        else:
            await ctx.respond("☑️", ephemeral=True)


def setup(bot):
    bot.add_cog(AdminIO(bot))
    print("IO.cog is loaded")
