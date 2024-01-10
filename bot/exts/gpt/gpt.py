import openai
import discord
from discord.commands import slash_command
from discord.ext import commands
from bot.constants import DEBUG_SERVER_ID, SEC_DEBUG_SERVER_ID

MAX_HISTORY_CHARS = 6000


def split_long_message(message, max_length=3500):
    """Split a long message into chunks of a specified max length."""
    return [message[i : i + max_length] for i in range(0, len(message), max_length)]


def trim_history(history, max_chars=MAX_HISTORY_CHARS):
    """Trim the history to be within the max character limit."""
    total_chars = sum(len(m["content"]) for m in history)
    while total_chars > max_chars and len(history) > 1:
        removed_message = history.pop(0)
        total_chars -= len(removed_message["content"])
    return history


class GPTRelay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}
        self.openai_client = openai.OpenAI()
        self.allowed_mime_types = ["image/png", "image/jpeg", "image/gif"]
        self.system_message = "You are a helpful A.I. assistant."

    def determine_model(self, message):
        if message.attachments:
            model = "gpt-4-vision-preview"
        else:
            model = "gpt-4"

        return model

    async def create_content(self, message):
        if message.attachments:
            content = [{"type": "text", "text": message.content}]
            for file in message.attachments:
                if not file.content_type in self.allowed_mime_types:
                    await self.reply_error(
                        message,
                        "Bad File Upload",
                        f"The file uploaded '{file.filename}' is not an accepted file type.",
                    )
                    return
                else:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": file.url,
                            },
                        }
                    )
        else:
            content = message.content

        return content

    async def relay_response(self, message: discord.Message, model: str, response: str):
        message_parts = split_long_message(response)
        for part in message_parts:
            await message.reply(
                part + f"\n\n`> Model: {model} · System: {self.system_message}`"
                if part == message_parts[-1]
                else "",
                mention_author=False,
            )

    async def reply_error(self, message: discord.Message, title: str, error: str):
        embed = discord.Embed(
            title=title,
            description=f"An error occurred: {error}",
            color=discord.Color.red(),
        )
        await message.reply(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.guild is None
            or message.guild.id not in [DEBUG_SERVER_ID, SEC_DEBUG_SERVER_ID]
            or message.author == self.bot.user
        ):
            return

        if "gpt" not in message.channel.name:  # type: ignore
            return

        # prepare a trimmed history of the conversation
        channel_history = trim_history(
            self.conversation_history.get(
                message.channel.id,
                [
                    {
                        "role": "system",
                        "content": self.system_message,
                    },
                ],
            )
        )
        content = await self.create_content(message)
        if content is None:
            return

        model = self.determine_model(message)

        channel_history.append({"role": "user", "content": content})

        async with message.channel.typing():
            try:
                response = self.openai_client.chat.completions.create(
                    model=model, messages=channel_history, max_tokens=500
                )

                if response.choices and len(response.choices) > 0:
                    reply = response.choices[0].message.content
                    await self.relay_response(message, model, reply)  # type: ignore
                    channel_history.append({"role": "assistant", "content": reply})

            except openai.BadRequestError as e:
                await self.reply_error(
                    message,
                    "Bad Request",
                    "There was an issue with the request to OpenAI. Please check the API key and try again.",
                )
                print(f"InvalidRequestError: {e}")

            except openai.OpenAIError as e:
                await self.reply_error(
                    message,
                    "OpenAI Service Error",
                    "An error occurred with the OpenAI service.",
                )
                print(f"OpenAIError: {e}")

            except Exception as e:
                await self.reply_error(
                    message,
                    "Unexpected Error",
                    "An unexpected error occurred.",
                )
                print(f"Error: {e}")

    @slash_command(name="clear-gpt", guild_ids=(DEBUG_SERVER_ID, SEC_DEBUG_SERVER_ID))
    async def clearhistory(self, ctx):
        """Clears the conversation history for the channel."""
        if ctx.channel.id in self.conversation_history:
            del self.conversation_history[ctx.channel.id]
            await ctx.respond("Conversation history cleared.")
        else:
            await ctx.respond("No conversation history to clear.")


def setup(bot):
    bot.add_cog(GPTRelay(bot))
    print("GPTRelay.cog is loaded")
