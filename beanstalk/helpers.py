# pylint: disable=missing-module-docstring,logging-fstring-interpolation

import asyncio
import contextlib
import logging
import os
import re
import subprocess
import tempfile

import discord
from discord.ext import commands


class Bot(commands.Bot):
    "A Bot with stuff."

    def __init__(self, config, db, **kwargs):
        self.cfg = config
        self.db = db  # pylint:disable=invalid-name
        self.http = None
        self.setup_done = False
        self.log = logging.getLogger("beanstalk")

        intents = discord.Intents.default()
        intents.members = True

        super().__init__(**kwargs, intents=intents)


def iso_8601_readable(original: str) -> str:
    "declutter a full iso8601 date string to make it more readable"

    return re.sub(r"(\d+-\d+-\d+)T(\d+:\d+).+", r"\1 \2", original)


def check_enabled(which: str):
    "command check to see if this command has been temporarily disabled"

    async def pred(ctx: commands.Context):
        if not ctx.bot.cfg["enabled"][which]:
            ctx.bot.log.warning(f"failure: command {which} is disabled")
            await ctx.message.add_reaction("❌")
            return False

        return True

    return commands.check(pred)


async def confirm_upload(ctx: commands.Context, path: str, name: str):
    "open a file and a dialog to confirm that it should get uploaded"
    display = subprocess.Popen(["eog", path], stderr=subprocess.DEVNULL)
    await asyncio.sleep(0.5)
    question = await asyncio.create_subprocess_exec(
        "zenity",
        "--question",
        f"--text=Upload for {ctx.author} to {ctx.channel} on {ctx.guild}?",
        "--timeout=90",
        "--width=300",
    )
    do_it = (await question.wait()) == 0
    display.terminate()

    if do_it:
        with open(path, "rb") as image:
            msg = await ctx.bot.get_channel(ctx.bot.cfg["cdn"]).send(
                file=discord.File(image, filename=name)
            )
            await ctx.send(msg.attachments[0].url)
    else:
        await ctx.message.add_reaction("❌")


@contextlib.contextmanager
def tempfilename(extension: str):
    """a context manager that yields the path to a newly-created temporary file and deletes
    it on cleanup"""

    handle, filename = tempfile.mkstemp(suffix=extension)
    os.close(handle)
    try:
        yield filename
    finally:
        os.unlink(filename)


async def play(filename: str):
    "resume when `filename` has been played using ffplay"

    return await (
        await asyncio.create_subprocess_exec(
            "ffplay",
            filename,
            "-autoexit",
            "-nodisp",
            "-hide_banner",
            "-loglevel",
            "warning",
            stdout=subprocess.DEVNULL,
        )
    ).wait()
