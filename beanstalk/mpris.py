# pylint: disable=missing-module-docstring,logging-fstring-interpolation

import re
import subprocess
import typing


def mpris_names() -> typing.List[str]:
    "list all possible current MPRIS2 providers for use with the other functions"

    all_names = str(
        subprocess.run(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.DBus",
                "--print-reply",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.ListNames",
            ],
            capture_output=True,
            check=True,
        ).stdout,
        encoding="utf-8",
    )
    return re.findall(r"(org\.mpris\.MediaPlayer2[^\"]+)", all_names)


def mpris_is_playing(who: str) -> bool:
    "return if a MPRIS2 provider is currently playing something"

    try:
        disgusting = str(
            subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    f"--dest={who}",
                    "--print-reply",
                    "/org/mpris/MediaPlayer2",
                    "org.freedesktop.DBus.Properties.Get",
                    "string:org.mpris.MediaPlayer2.Player",
                    "string:PlaybackStatus",
                ],
                capture_output=True,
                check=True,
            ).stdout,
            encoding="utf-8",
        )
        return "Paused" not in disgusting and "Stopped" not in disgusting
    except:  # pylint: disable=bare-except
        return False


def mpris_data(whose: str) -> dict:
    "return a dict {title, artist, album, artUrl} for the media played by a MPRIS2 provider"

    match_next_string = r"\"\n[^\"]+\"(.+)\""
    disgusting = str(
        subprocess.run(
            [
                "dbus-send",
                "--session",
                f"--dest={whose}",
                "--print-reply",
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties.Get",
                "string:org.mpris.MediaPlayer2.Player",
                "string:Metadata",
            ],
            capture_output=True,
            check=True,
        ).stdout,
        encoding="utf-8",
    )
    result = {
        k: re.search(k + match_next_string, disgusting)
        for k in ("title", "artist", "album", "artUrl")
    }
    result = {k: v[1] for k, v in result.items() if v}
    return result
