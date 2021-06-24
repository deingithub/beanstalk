# pylint: disable=missing-module-docstring,logging-fstring-interpolation

import asyncio
import json
import logging
import pathlib
import random
import re
import sqlite3
import subprocess
import os
from copy import copy
import tempfile
from typing import Optional
import shlex

import aiohttp
import discord
import gtts
from discord.ext import commands, tasks

from .helpers import Bot, check_enabled, confirm_upload, play, tempfilename, safe_play
from .mpris import mpris_data, mpris_is_playing, mpris_names
from .parcel import fetch_paket, render_parcel

cfg = {}
with open("config.json") as f:
    cfg = json.loads(f.read())

cfg["enabled"] = {
    "ss": True,
    "np": True,
    "proc": False,
    "wc": True,
    "tts": True,
    "play": True,
}


db = sqlite3.connect("./private.sqlite3")
db.row_factory = sqlite3.Row
db.executescript(
    """
    create table if not exists parcels (
        id integer primary key,
        user_id integer not null,
        service text not null,
        number text not null,
        last_status text not null
    );
    """
)

bot = Bot(
    cfg,
    db,
    command_prefix=("c!", "css!", "cass, "),
    activity=discord.Activity(type=discord.ActivityType.watching, name="the waffle"),
    help_command=None,
    case_sensitive=False,
)

pubdb = sqlite3.connect("./public.sqlite3")
pubdb.row_factory = sqlite3.Row


logging.basicConfig(
    style="{", format="{levelname} {name}: {message}", level=logging.INFO
)
logging.getLogger("discord.gateway").addFilter(lambda row: row.levelno > logging.INFO)


@bot.event
async def on_command(ctx: commands.Context):
    "log issued commands"
    ctx.bot.log.getChild(ctx.command.name).info(
        f"running for {ctx.author} in {ctx.channel} in {ctx.guild}:\n\t{ctx.message.content}"
    )


@bot.event
async def on_message(msg: discord.Message):
    "process commands and enable/disable"

    if bot.user in msg.mentions:
        await msg.add_reaction("🧇")

    if await bot.is_owner(msg.author) and (
        msg.clean_content.startswith("+") or msg.clean_content.startswith("-")
    ):
        found_any = False

        # disable/enable commands, and then…
        for target in msg.clean_content[1:].split(","):
            if target in bot.cfg["enabled"]:
                found_any = True
                bot.cfg["enabled"][target] = msg.clean_content[0] == "+"

        # pretend we actually saw a help command if anything changed
        if found_any:
            msg_clone = copy(msg)
            msg_clone.content = "css!help"
            await bot.process_commands(msg_clone)

        return

    if (
        msg.guild
        and msg.guild.id in cfg["approved_guilds"]
        and not msg.author.id in cfg["killfile"]
    ) or await bot.is_owner(msg.author):
        await bot.process_commands(msg)


@bot.command(name="help")
async def _help(ctx: commands.Context):
    "print this"

    def syntax(command):
        out = "css!"
        if not command.aliases:
            out += command.qualified_name
        else:
            out += f"[{command.qualified_name}"
            for alias in command.aliases:
                out += f",{alias}"

            out += "]"

        return out

    longest_name_len = len(
        syntax(sorted(bot.commands, key=lambda c: len(syntax(c)), reverse=True)[0])
    )
    text = f"`  {'about'.rjust(longest_name_len)}` 🧇 cass stalkbot v{random.randrange(39000000)}\n"
    for command in sorted(bot.commands, key=lambda c: c.qualified_name):
        enabled = "✅"
        enable_aliases = [
            alias
            for alias in ([command.qualified_name] + command.aliases)
            if alias in ctx.bot.cfg["enabled"]
        ]
        if enable_aliases and not ctx.bot.cfg["enabled"][enable_aliases[0]]:
            enabled = "❌"

        text += f"`  {syntax(command).rjust(longest_name_len)}` {enabled} {command.short_doc}\n"

    await ctx.send(text)


@bot.command(aliases=["np", "fm"])
@check_enabled("np")
async def playing(ctx: commands.Context):
    "Display which music i'm hearing right now"

    if ctx.invoked_with == "fm":
        await ctx.send("i dont use lastfm btw")
        return

    embed = discord.Embed(
        color=discord.Colour.dark_magenta(), title="Cass is listening to"
    )
    players = [name for name in mpris_names() if mpris_is_playing(name)]
    if not players:
        embed.title += "… Nothing, apparently."
    else:
        data = mpris_data(players[0])
        if data.get("title"):
            embed.title += f" \"{data['title']}\""
        else:
            embed.title += " Unknown"

        if data.get("artist"):
            data["artist"] = data["artist"].removesuffix(" - Topic")

        embed.description = f"From **{data.get('album', 'Unknown')}** "
        embed.description += f"by **{data.get('artist', 'Unknown')}**"
        if data.get("title") and data.get("artist"):
            maybe_lyrics = data["artist"] + " " + data["title"] + " lyrics"
            maybe_lyrics = re.sub(r"[^a-z]+", "-", maybe_lyrics.lower())
            embed.description += (
                f"\n[Best Guess For Lyrics](https://genius.com/{maybe_lyrics})"
            )
        if data.get("artUrl"):
            path = pathlib.Path(data["artUrl"].removeprefix("file://"))
            cdn_channel = bot.get_channel(cfg["cdn"])

            with path.open("rb") as image:
                msg = await cdn_channel.send(
                    file=discord.File(image, filename="image" + path.suffix)
                )

                embed.set_thumbnail(url=msg.attachments[0].url)

    await ctx.send(embed=embed)


@bot.command(aliases=["ss"])
@check_enabled("ss")
async def screenshot(ctx: commands.Context):
    "Make a screenshot and post it"

    with tempfilename(".png") as filename:
        subprocess.run(
            [
                "dbus-send",
                "--print-reply",
                "--session",
                "--dest=org.gnome.Shell",
                "/org/gnome/Shell/Screenshot",
                "org.gnome.Shell.Screenshot.Screenshot",
                "boolean:false",
                "boolean:true",
                f"string:{filename}",
            ],
            check=True,
        )
        subprocess.run(["mogrify", "-blur", "0x8", filename], check=True)

        await confirm_upload(ctx, filename, "screenshot.png")


@bot.command(aliases=["wc", "gif", "wcgif"])
@check_enabled("wc")
async def webcam(ctx: commands.Context, frames: int = 90):
    "Make a short gif using my webcam and post it"

    if frames < 1 or frames > 180:
        await ctx.message.add_reaction("❌")
        return

    with tempfilename(".gif") as filename:
        await asyncio.create_subprocess_exec(
            "notify-send", f"wc: {ctx.author}", f"{ctx.channel} on {ctx.guild}"
        )
        await play("on.mp3")
        await asyncio.gather(
            ctx.message.add_reaction("🎥"),
            (
                await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-loglevel",
                    "warning",
                    "-hide_banner",
                    "-y",
                    "-input_format",
                    "mjpeg",
                    "-video_size",
                    "1024x768",
                    "-framerate",
                    "30",
                    "-i",
                    "/dev/video0",
                    "-vframes",
                    str(frames),
                    "-vf",
                    "scale=400x300",
                    filename,
                )
            ).wait(),
            ctx.message.add_reaction("⌛"),
        )
        await asyncio.gather(
            play("off.mp3"),
            ctx.message.remove_reaction("🎥", bot.user),
            confirm_upload(ctx, filename, "webcam.gif"),
        )

        await ctx.message.remove_reaction("⌛", bot.user)


@bot.command(aliases=["folder", "f"])
async def file(ctx: commands.Context, glob: str = ""):
    "Post a random file"

    files = list(pathlib.Path("./file").glob(glob.replace("/", "") + "*"))
    if not files:
        await ctx.send("not found")
        return

    with random.choice(files).open("rb") as the_file:
        await ctx.send(the_file.name.removeprefix("file/"), file=discord.File(the_file))


@bot.command()
@check_enabled("tts")
async def tts(ctx: commands.Context, *, text: str):
    "Make Google TTS say something to me"

    if len(text) > 500:
        await ctx.message.add_reaction("❌")
        return

    await ctx.message.add_reaction("⌛")

    with tempfilename(".mp3") as filename:
        sound = gtts.gTTS(f"{ctx.author.display_name} in {ctx.channel}: {text}")
        sound.save(filename)
        await asyncio.gather(
            ctx.message.remove_reaction("⌛", ctx.bot.user),
            play(filename),
            ctx.message.add_reaction("▶️"),
        )


@bot.command()
async def sql(ctx: commands.Context, *, text: str):
    "Run queries against a shared SQL database"

    text = text.removeprefix("```sql").removeprefix("```").removesuffix("```")

    try:
        with db:
            cur = pubdb.execute(text)
            rows = cur.fetchall()
            output = ""
            if rows:
                output += "\n" + ", ".join(rows[0].keys()) + "\n"

                for row in rows:
                    output += ", ".join([repr(x) for x in tuple(row)]) + "\n"

            blocks = [f"```\n{len(rows)} rows returned"]
            for line in output.split("\n"):
                if len(line) + len(blocks[-1]) < 1990:
                    blocks[-1] += "\n" + line
                else:
                    blocks.append(f"```\n{line}")

            for block in blocks:
                await ctx.send(block + "```")

    except sqlite3.DatabaseError as exc:
        await ctx.send(f"```\n{exc.__class__.__name__}: {exc}```")


@bot.command(name="play")
@check_enabled("play")
async def _play(ctx: commands.Context, url: Optional[str], offset: Optional[int] = 0):
    "Play a youtube-dl compatible url or attachment. Optional offset in seconds after URL."

    if attachments := ctx.message.attachments:
        if attachments[0].size > 8 * 1024 * 1024:
            await ctx.reply(":x: file too large (max 8 MB)")
            return

        if not (
            attachments[0].content_type.startswith("video/")
            or attachments[0].content_type.startswith("audio/")
        ):
            await ctx.reply(":x: doesn't look like an audio file")
            return

        with tempfilename(attachments[0].filename) as filename:
            await asyncio.gather(
                ctx.message.add_reaction("⏳"),
                attachments[0].save(filename),
            )
            await asyncio.gather(
                ctx.message.remove_reaction("⏳", bot.user),
                ctx.message.add_reaction("▶️"),
                asyncio.create_subprocess_exec(
                    "notify-send",
                    f"play: {ctx.author}",
                    f"{ctx.channel} on {ctx.guild}",
                ),
                safe_play(filename, offset),
            )

    if url:
        with tempfilename(".mp3") as filename:
            data = await asyncio.create_subprocess_exec(
                "youtube-dl", "-e", url, stdout=subprocess.PIPE
            )

            await asyncio.gather(data.wait(), ctx.message.add_reaction("⏳"))
            title = str(await data.stdout.read(), encoding="utf-8").strip()

            download = await asyncio.create_subprocess_exec(
                "youtube-dl",
                "-x",
                "--audio-format",
                "mp3",
                "--max-filesize",
                "8M",
                "--no-continue",
                "--postprocessor-args",
                f"-metadata title={shlex.quote(title)}",
                "-o",
                filename,
                url,
                stdout=subprocess.PIPE,
            )
            await download.wait()

            if b"File is larger than max-filesize" in await download.stdout.read():
                await ctx.send(":x: file too large (max 8 MB)")
                return

            await asyncio.gather(
                ctx.message.remove_reaction("⏳", bot.user),
                ctx.message.add_reaction("▶️"),
                asyncio.create_subprocess_exec(
                    "notify-send",
                    f"play: {ctx.author}",
                    f"{ctx.channel} on {ctx.guild}",
                ),
                safe_play(filename, offset),
            )


@bot.group(invoke_without_command=True, case_insensitive=True)
async def paket(ctx: commands.Context):
    "Alle Pakete anschauen"

    parcels = db.execute(
        "SELECT * FROM parcels WHERE user_id = ?", (ctx.author.id,)
    ).fetchall()
    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s parcels",
        description="Add parcels to track using\n"
        "`css!paket add <dhl|hermes|asendia> <tracking number>`\n"
        + "and remove them from tracking using\n"
        "`css!paket stop <tracking number or #ID>`",
    )
    if not parcels:
        embed.description = "None.\n" + embed.description
    else:
        async with ctx.typing():
            for parcel in parcels:
                data = await fetch_paket(ctx.bot, parcel["service"], parcel["number"])
                embed.add_field(**render_parcel(parcel, data))

    await ctx.send(embed=embed)


@paket.command()
async def add(ctx: commands.Context, service: str, number: str):
    "Neues Paket tracken"

    if data := await fetch_paket(ctx.bot, service, number):
        with db:
            db.execute(
                "INSERT INTO parcels(user_id, service, number) VALUES(?,?,?)",
                (ctx.author.id, service, number),
            )
        await ctx.send(f"added {number}: {data['status']}")
    else:
        await ctx.send(f":x: couldn't add {number}, bad API response")


@paket.command()
async def stop(ctx: commands.Context, number: str):
    "Paket nicht mehr tracken"

    if not db.execute(
        "SELECT * FROM parcels WHERE user_id = ? AND id = ? OR number = ?",
        (ctx.author.id, number, number),
    ).fetchone():
        await ctx.send(":x: not found")
        return

    with db:
        db.execute(
            "DELETE FROM parcels WHERE user_id = ? AND id = ? OR number = ?",
            (ctx.author.id, number, number),
        )
        await ctx.send(f"deleted {number}")


@paket.command()
async def ass(ctx: commands.Context):
    "thanks fran"
    await ctx.send("horny!")


@tasks.loop(hours=1.0)
async def check_for_parcel_updates():
    "regularly fetch all parcels and notify via dm if there's updates to their status"
    bot.log.info("checking for parcel updates")
    all_parcels = db.execute("SELECT * FROM parcels").fetchall()
    for parcel in all_parcels:
        data = await fetch_paket(bot, parcel["service"], parcel["number"])
        if not data:
            bot.log.error(f"couldn't refresh parcel data for {parcel['id']}")
        if data and str(data) != parcel["last_status"]:
            bot.log.info(
                f"notifying {bot.get_user(parcel['user_id'])} for {parcel['id']}"
            )
            await bot.get_user(parcel["user_id"]).send(
                embed=discord.Embed(title="Update!").add_field(
                    **render_parcel(parcel, data)
                )
            )
    bot.log.info("done checking")


@bot.event
async def on_ready():
    "on start bring up the http session and start tasks"
    if not bot.setup_done:
        bot.log.info(f"Hi there from {bot.user}")
        bot.actual_http = aiohttp.ClientSession()
        check_for_parcel_updates.start()
        bot.setup_done = True


bot.run(cfg["token"])
