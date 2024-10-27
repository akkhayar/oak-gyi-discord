import openai
import discord
import asyncio

from discord.commands import slash_command
from asyncio import sleep
from discord.ext import commands
from traceback import print_exc
from bot.constants import DEBUG_SERVER_ID, SEC_DEBUG_SERVER_ID

MAX_HISTORY_CHARS = 6000


def split_long_message(message, max_length=1900):
    """Split a long message into chunks that respect word boundaries and new lines, with a specified max length."""
    words = message.split(" ")
    chunks = []
    current_chunk = ""

    for word in words:
        # Check if adding the next word would exceed the max_length
        if len(current_chunk + word + " ") > max_length:
            # If it does, add the current chunk to chunks and start a new chunk
            chunks.append(current_chunk.strip())
            current_chunk = word + " "
        else:
            # If not, add the word to the current chunk
            current_chunk += word + " "

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def trim_history(history, max_chars=MAX_HISTORY_CHARS):
    """Trim the history to be within the max character limit."""
    total_chars = sum(len(m["content"]) for m in history)
    while total_chars > max_chars and len(history) > 1:
        removed_message = history.pop(0)
        total_chars -= len(removed_message["content"])
    return history


ALLOWED_MIME_TYPES = ["image/png", "image/jpeg", "image/gif"]
GPT_IMAGE_MODELS = ["dall-e-3"]


class GPTRelay(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.conversation_history = {}
        self.openai_client = openai.OpenAI()
        self.allowed_dm = [705000432518430720, 368671236370464769]
        self.system_message = "You are a helpful A.I. assistant."

        self.queue = asyncio.Queue()
        self.bot.loop.create_task(self.queue_worker())

    async def determine_model(self, message):
        if message.attachments:
            model = "o1-preview"
        elif await self.is_dalle_prompt(message.content):
            model = "dall-e-3"
        else:
            model = "o1-preview"

        return model

    async def is_dalle_prompt(self, prompt: str):
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Determine if the following input is a request to generate an image. Respond with either 'Yes' or 'No'.\n\n"
                            f"Input: {prompt}"
                        ),
                    }
                ],
                max_tokens=30,
            )
        except Exception:
            print_exc()
        else:
            return response.choices[0].message.content.lower() == "yes"
        return False

    async def create_content(self, message):
        if message.attachments:
            content = [{"type": "text", "text": message.content}]
            for file in message.attachments:
                if not file.content_type in ALLOWED_MIME_TYPES:
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
            if part == message_parts[-1]:
                part += f"\n\n`> Model: {model} · System: {self.system_message}`"

            if part == message_parts[0]:
                await message.reply(part, mention_author=False)
            else:
                await message.channel.send(part)
            await sleep(0.5)

    async def reply_error(self, message: discord.Message, title: str, error: str):
        embed = discord.Embed(
            title=title,
            description=f"An error occurred: {error}",
            color=discord.Color.red(),
        )
        await message.reply(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if message.guild:
            if message.guild.id not in [DEBUG_SERVER_ID, SEC_DEBUG_SERVER_ID]:
                return

            if "gpt" not in message.channel.name:  # type: ignore
                return
        else:
            if message.author.id not in self.allowed_dm:
                return

        await self.queue.put(self.process_message(message))

    async def queue_worker(self):
        """A worker that processes tasks from the queue."""
        while True:
            task = await self.queue.get()
            try:
                await task
            finally:
                self.queue.task_done()

    async def process_message(self, message: discord.Message):
        async with message.channel.typing():
            model = await self.determine_model(message)

        if model in GPT_IMAGE_MODELS:
            runner = self.openai_client.images.generate
            kwargs = {
                "model": model,
                "prompt": message.content,
                "size": "1024x1024",
                "quality": "standard",
                "n": 1,
            }
        else:
            # prepare a trimmed history of the conversation
            channel_history = trim_history(
                self.conversation_history.get(
                    message.channel.id,
                    [{"role": "system", "content": self.system_message}],
                )
            )
            content = await self.create_content(message)
            if content is None:
                return
            channel_history.append({"role": "user", "content": content})

            runner = self.openai_client.chat.completions.create
            kwargs = {
                "model": model,
                "messages": channel_history,
                "max_tokens": 500,
            }

        async with message.channel.typing():
            try:
                response = runner(**kwargs)

                if kwargs["model"] in GPT_IMAGE_MODELS:
                    await message.reply(response.data[0].url, mention_author=False)
                else:
                    reply = response.choices[0].message.content
                    await self.relay_response(message, model, reply)  # type: ignore
                    if message.channel.id in self.conversation_history:
                        self.conversation_history[message.channel.id].append(
                            {"role": "assistant", "content": reply}
                        )

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
                print_exc()

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
