# pylint: disable=missing-module-docstring,logging-fstring-interpolation,line-too-long

import asyncio
import json
import re
import subprocess

from .helpers import Bot, iso_8601_readable


async def fetch_hermes_paket(bot: Bot, number: str) -> dict:
    "extract hermes parcel info"

    async with bot.actual_http.get(
        f"https://www.myhermes.de/services/tracking/shipments?search={number}"
    ) as req:
        try:
            data = await req.json()
            return {
                "status": data[0]["lastStatus"]["description"],
                "update_time": data[0]["lastStatus"]["dateTime"],
                "url": f"https://www.myhermes.de/empfangen/sendungsverfolgung/sendungsinformation/#{number}",
            }

        except Exception as exc:  # pylint: disable=broad-except
            bot.log.error("couldn't extract packet info", exc_info=exc)
            return None


async def fetch_asendia_paket(bot: Bot, number: str) -> dict:
    "extract asendia parcel info"
    try:
        async with bot.actual_http.get(
            f"https://a1api2.asendia.io/api/A1/TrackingBranded/Tracking?trackingKey=AE654169-0B14-45F9-8498-A8E464E13D26&trackingNumber={number}",
            headers={
                "Authorization": "Basic Q3VzdEJyYW5kLlRyYWNraW5nQGFzZW5kaWEuY29tOjJ3cmZzelk4cXBBQW5UVkI=",
                "X-AsendiaOne-ApiKey": "32337AB0-45DD-44A2-8601-547439EF9B55",
            },
        ) as req:
            data = await req.json()
            return {
                "status": data["trackingBrandedDetail"][0]["eventDescription"],
                "update_time": iso_8601_readable(data["trackingBrandedDetail"][0]["eventOn"]),
                "url": f"https://a1.asendiausa.com/tracking/?trackingnumber={number}",
            }

    except Exception as exc:  # pylint: disable=broad-except
        bot.log.error("couldn't extract packet info", exc_info=exc)
        return None


async def fetch_dhl_paket(bot: Bot, number: str) -> dict:
    "extract dhl parcel info"

    try:
        process = await asyncio.create_subprocess_exec(
            "curl",
            f"https://www.dhl.de/int-verfolgen/search?language=de&piececode={number}",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        output = str((await process.communicate())[0])
        pain = re.search(r"""initialState: JSON.parse\("(.+)"\)""", output)[1].replace('\\\\"', '"')
        pain = re.sub(r"\\\\u([0-9A-F]+)", lambda match: chr(int(match[1], 16)), pain)
        data = json.loads(pain)
        return {
            "status": data["sendungen"][0]["sendungsdetails"]["sendungsverlauf"]["kurzStatus"],
            "update_time": iso_8601_readable(
                data["sendungen"][0]["sendungsdetails"]["sendungsverlauf"]["datumAktuellerStatus"]
            ),
            "url": f"https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html?piececode={number}",
        }

    except Exception as exc:  # pylint: disable=broad-except
        bot.log.error("couldn't extract packet info", exc_info=exc)
        return None


async def fetch_paket(bot: Bot, service: str, number: str) -> dict:
    "dispatch to per-service packet info fetch"

    data = {}

    if service == "hermes":
        data = await fetch_hermes_paket(bot, number)
    elif service == "dhl":
        data = await fetch_dhl_paket(bot, number)
    elif service == "asendia":
        data = await fetch_asendia_paket(bot, number)
    else:
        raise ValueError("bad service")

    with bot.db:
        bot.db.execute(
            "UPDATE parcels SET last_status = ? WHERE service = ? AND number = ?",
            (str(data), service, number),
        )

    return data


def render_parcel(parcel: dict, data: dict) -> dict:
    "render parcel data into an embed.add_field **able args dict"

    return {
        "name": f"✅ {parcel['service']} {parcel['number']} (#{parcel['id']})",
        "value": f"[{data['update_time']}: {data['status']}]({data['url']})"
        if data
        else "Couldn't fetch data.",
    }
