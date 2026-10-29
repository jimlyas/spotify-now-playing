from flask import Flask, Response, jsonify, render_template
from base64 import b64encode

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import json
import os
import random
import re

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET_ID = os.getenv("SPOTIFY_SECRET_ID")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

# scope user-read-currently-playing/user-read-recently-played
SPOTIFY_URL_REFRESH_TOKEN = "https://accounts.spotify.com/api/token"
SPOTIFY_URL_NOW_PLAYING = "https://api.spotify.com/v1/me/player/currently-playing"
SPOTIFY_URL_RECENTLY_PLAY = "https://api.spotify.com/v1/me/player/recently-played?limit=10"

# Card frame: keep these identical to the AniList card so the two match.
CARD_PAD = 14
CARD_RADIUS = 12
CARD_BG = "#0d1117"


app = Flask(__name__)


def getAuth():
    return b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_SECRET_ID}".encode()).decode("ascii")


def refreshToken():
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN,
    }

    headers = {"Authorization": "Basic {}".format(getAuth())}

    response = requests.post(SPOTIFY_URL_REFRESH_TOKEN, data=data, headers=headers)
    body = response.json()

    if "access_token" not in body:
        print("Spotify token error:", response.status_code, body)
        raise RuntimeError("Spotify token request failed")

    return body["access_token"]


def recentlyPlayed():
    token = refreshToken()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(SPOTIFY_URL_RECENTLY_PLAY, headers=headers)

    if response.status_code == 204:
        return {}

    return response.json()


def nowPlaying():

    token = refreshToken()

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(SPOTIFY_URL_NOW_PLAYING, headers=headers)

    if response.status_code == 204:
        return {}

    return response.json()


def barGen(barCount):
    barCSS = ""
    left = 1
    for i in range(1, barCount + 1):
        anim = random.randint(1000, 1350)
        barCSS += ".bar:nth-child({})  {{ left: {}px; animation-duration: {}ms; }}".format(
            i, left, anim
        )
        left += 4

    return barCSS


def loadImageB64(url):
    resposne = requests.get(url)
    return b64encode(resposne.content).decode("ascii")


def makeSVG(data):
    barCount = 85
    contentBar = "".join(["<div class='bar'></div>" for i in range(barCount)])
    barCSS = barGen(barCount)

    if data == {}:
        content_bar = ""
        recent_plays = recentlyPlayed()
        size_recent_play = len(recent_plays["items"])
        idx = random.randint(0, size_recent_play - 1)
        item = recent_plays["items"][idx]["track"]
    else:
        item = data["item"]

    img = loadImageB64(item["album"]["images"][1]["url"])
    artistName = item["artists"][0]["name"].replace("&", "&amp;")
    songName = item["name"].replace("&", "&amp;")

    dataDict = {
        "content_bar": contentBar,
        "css_bar": barCSS,
        "artist_name": artistName,
        "song_name": songName,
        "img": img,
    }

    return render_template("spotify.html.j2", **dataDict), img


def frameSVG(svg, img=None, pad=CARD_PAD):
    """Wrap the rendered template in the same dark, rounded, bordered card as the
    AniList card, with the album art blurred and dimmed behind it. The original
    SVG is nested untouched (no scaling), so its layout and animations are
    unchanged. If its size can't be read, it is returned as-is."""
    start = re.search(r"<svg\b([^>]*)>", svg)
    if not start:
        return svg
    attrs = start.group(1)

    def number(name):
        found = re.search(rf'\s{name}="\s*([\d.]+)\s*(?:px)?\s*"', attrs)
        return float(found.group(1)) if found else None

    width, height = number("width"), number("height")
    if not (width and height):
        box = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"', attrs)
        if not box:
            return svg
        width, height = float(box.group(1)), float(box.group(2))
        attrs += f' width="{width:g}" height="{height:g}"'

    # drop any x/y the template set, we position the nested copy ourselves
    attrs = re.sub(r'\s(?:x|y)="[^"]*"', "", attrs)
    inner = svg[start.end():]  # everything after the original opening tag, including </svg>

    total_w = width + 2 * pad
    total_h = height + 2 * pad
    artwork = ""
    if img:
        artwork = (
            f'<image x="-40" y="-60" width="{total_w + 80:g}" height="{total_h + 120:g}" '
            f'preserveAspectRatio="xMidYMid slice" filter="url(#sp-blur)" '
            f'xlink:href="data:image/jpeg;base64,{img}"/>'
            f'<rect width="{total_w:g}" height="{total_h:g}" fill="url(#sp-shade)"/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{total_w:g}" height="{total_h:g}" viewBox="0 0 {total_w:g} {total_h:g}">'
        f'<defs>'
        f'<clipPath id="sp-card"><rect width="{total_w:g}" height="{total_h:g}" rx="{CARD_RADIUS}"/></clipPath>'
        f'<filter id="sp-blur" x="-10%" y="-10%" width="120%" height="120%">'
        f'<feGaussianBlur stdDeviation="18"/></filter>'
        f'<linearGradient id="sp-shade" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{CARD_BG}" stop-opacity="0.72"/>'
        f'<stop offset="1" stop-color="{CARD_BG}" stop-opacity="0.92"/>'
        f'</linearGradient></defs>'
        f'<g clip-path="url(#sp-card)">'
        f'<rect width="{total_w:g}" height="{total_h:g}" fill="{CARD_BG}"/>{artwork}'
        f'</g>'
        f'<rect x="0.5" y="0.5" width="{total_w - 1:g}" height="{total_h - 1:g}" rx="{CARD_RADIUS}" '
        f'fill="none" stroke="#ffffff" stroke-opacity="0.14"/>'
        f'<svg x="{pad}" y="{pad}"{attrs}>{inner}'
        f"</svg>"
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):

    data = nowPlaying()
    svg, img = makeSVG(data)
    svg = frameSVG(svg, img)

    resp = Response(svg, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "s-maxage=1, max-age=0, no-cache"

    return resp


if __name__ == "__main__":
    app.run(debug=True)
