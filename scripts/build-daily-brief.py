import argparse
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json


for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(key, None)


try:
    LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesDailyBrief/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml, application/json, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return body.decode(charset, errors="replace")


def fetch_json(url: str, timeout: int = 20) -> dict:
    return json.loads(fetch_text(url, timeout=timeout))


def rss_titles(url: str, limit: int = 3) -> list[str]:
    try:
        root = ET.fromstring(fetch_text(url))
        titles: list[str] = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title")
            if title:
                titles.append(" ".join(title.split()))
            if len(titles) >= limit:
                break

        if not titles:
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title")
                if title:
                    titles.append(" ".join(title.split()))
                if len(titles) >= limit:
                    break

        return titles or [f"RSS has no readable titles: {url}"]
    except Exception as exc:
        return [f"RSS unavailable: {url} ({type(exc).__name__})"]


def format_range(times: list[str], values: list[float], threshold: float) -> str:
    hits = [times[i] for i, value in enumerate(values) if float(value) >= threshold]
    if not hits:
        return "khong co khung ro"
    return f"{hits[0][11:16]}-{hits[-1][11:16]}"


def build_brief(location: str, latitude: float, longitude: float) -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "hourly": "temperature_2m,precipitation_probability,uv_index",
            "forecast_days": 1,
            "timezone": "Asia/Bangkok",
        }
    )
    weather = fetch_json(f"https://api.open-meteo.com/v1/forecast?{query}")
    current = weather["current"]
    hourly = weather["hourly"]

    rain_peak = max(float(v) for v in hourly["precipitation_probability"])
    uv_peak = max(float(v) for v in hourly["uv_index"])
    hot_peak = max(float(v) for v in hourly["temperature_2m"])
    rain_window = format_range(hourly["time"], hourly["precipitation_probability"], 40)

    vn_news = rss_titles("https://vnexpress.net/rss/thoi-su.rss", 3)
    world_news = rss_titles("https://feeds.bbci.co.uk/news/world/rss.xml", 3)

    now = datetime.now(LOCAL_TZ)
    lines: list[str] = [
        f"Chao buoi sang. {now:%d/%m/%Y %H:%M} - {location}",
        "",
        "Thoi tiet:",
        f"- Hien tai: {current['temperature_2m']}°C, am {current['relative_humidity_2m']}%, gio {current['wind_speed_10m']} km/h",
        f"- Nhiet cao nhat hom nay: {hot_peak:.1f}°C",
        f"- Kha nang mua cao nhat: {rain_peak:.0f}%; khung de mua: {rain_window}",
        f"- UV cao nhat: {uv_peak:.1f}",
        "",
        "Goi y nhanh:",
        "- Mang ao mua/o neu ra ngoai." if rain_peak >= 40 else "- Thoi tiet co ve on, van kiem tra bau troi truoc khi di xa.",
        "- Tranh nang gat va dung chong nang neu di lau ngoai troi." if uv_peak >= 6 else "- UV khong qua cang theo forecast hien tai.",
        "",
        "Tin Viet Nam:",
    ]
    lines.extend(f"- {title}" for title in vn_news)
    lines.extend(["", "Tin the gioi:"])
    lines.extend(f"- {title}" for title in world_news)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", default="Hue")
    parser.add_argument("--latitude", type=float, default=16.4637)
    parser.add_argument("--longitude", type=float, default=107.5909)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    print(build_brief(args.location, args.latitude, args.longitude))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
