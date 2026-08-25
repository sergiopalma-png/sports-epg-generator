#!/usr/bin/env python3
"""
Sports XMLTV EPG Generator

Pulls today's/upcoming scoreboard data from ESPN's public site API for a
set of leagues (NFL, NBA, MLB, NHL, WNBA, MLS, NCAA Football, NCAA
Basketball) and renders it as a single XMLTV guide (sports_guide.xml)
under one dummy channel, so it can be consumed by IPTV EPG tools such as
IPTVEditor / TiviMate.

Standard library only -- no external pip dependencies.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.dom import minidom
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHANNEL_ID = "sports-daily-guide"
CHANNEL_NAME = "Daily US Sports Schedule"
OUTPUT_FILE = "sports_guide.xml"

REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_EVENT_DURATION_HOURS = 3
USER_AGENT = (
    "Mozilla/5.0 (compatible; SportsEPGGenerator/1.0; "
    "+https://github.com/) Python-urllib"
)

# Maps a human-readable league name to its ESPN scoreboard endpoint.
LEAGUE_ENDPOINTS = {
    "NFL": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "NBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "MLB": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "NHL": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "WNBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
    "MLS": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
    "NCAA Football": (
        "https://site.api.espn.com/apis/site/v2/sports/football/"
        "college-football/scoreboard"
    ),
    "NCAA Basketball": (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        "mens-college-basketball/scoreboard"
    ),
}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_scoreboard(league: str, url: str) -> dict:
    """Fetch and parse a single ESPN scoreboard endpoint.

    Returns an empty dict (rather than raising) on any network, HTTP, or
    JSON error so that one failing league does not abort the whole run.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        print(f"[WARN] {league}: HTTP error {exc.code} fetching {url}", file=sys.stderr)
        return {}
    except urllib.error.URLError as exc:
        print(f"[WARN] {league}: network error fetching {url}: {exc.reason}", file=sys.stderr)
        return {}
    except TimeoutError:
        print(f"[WARN] {league}: timed out fetching {url}", file=sys.stderr)
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[WARN] {league}: invalid JSON from {url}: {exc}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_broadcast_names(competition: dict) -> list[str]:
    """Pull broadcast network names (ESPN, TNT, NBC, local RSNs, etc.)
    out of a competition object, trying the couple of shapes ESPN uses.
    """
    names: list[str] = []

    for broadcast in competition.get("broadcasts", []) or []:
        for name in broadcast.get("names", []) or []:
            if name and name not in names:
                names.append(name)

    if not names:
        for geo in competition.get("geoBroadcasts", []) or []:
            media = geo.get("media", {}) or {}
            name = media.get("shortName")
            if name and name not in names:
                names.append(name)

    return names


def extract_events(league: str, scoreboard: dict) -> list[dict]:
    """Turn one league's raw scoreboard JSON into a flat list of simple
    event dicts: title, start (ISO 8601), status, broadcasts.
    """
    events = []

    for event in scoreboard.get("events", []) or []:
        try:
            event_id = event.get("id", "unknown")
            title = event.get("shortName") or event.get("name")
            start_time = event.get("date")

            if not title or not start_time:
                print(
                    f"[WARN] {league}: skipping event {event_id} missing title/date",
                    file=sys.stderr,
                )
                continue

            status = (
                event.get("status", {})
                .get("type", {})
                .get("shortDetail")
                or event.get("status", {}).get("type", {}).get("description")
                or "Scheduled"
            )

            competitions = event.get("competitions", []) or []
            broadcasts: list[str] = []
            if competitions:
                broadcasts = extract_broadcast_names(competitions[0])

            events.append(
                {
                    "league": league,
                    "title": title,
                    "start": start_time,
                    "status": status,
                    "broadcasts": broadcasts,
                }
            )
        except (AttributeError, TypeError, KeyError) as exc:
            print(f"[WARN] {league}: malformed event skipped ({exc})", file=sys.stderr)
            continue

    return events


def collect_all_events() -> list[dict]:
    all_events: list[dict] = []
    for league, url in LEAGUE_ENDPOINTS.items():
        print(f"Fetching {league} scoreboard...", file=sys.stderr)
        scoreboard = fetch_scoreboard(league, url)
        if not scoreboard:
            continue
        league_events = extract_events(league, scoreboard)
        print(f"  -> {len(league_events)} event(s)", file=sys.stderr)
        all_events.extend(league_events)
    return all_events


# ---------------------------------------------------------------------------
# XMLTV generation
# ---------------------------------------------------------------------------

def parse_iso8601(value: str) -> datetime | None:
    """Parse an ESPN ISO 8601 timestamp (e.g. 2026-08-25T17:00Z) into an
    aware UTC datetime. Returns None if the value can't be parsed.
    """
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def xmltv_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S +0000")


def build_xmltv(events: list[dict]) -> ET.Element:
    tv = ET.Element(
        "tv",
        attrib={
            "generator-info-name": "sports-epg-generator",
            "generator-info-url": "https://github.com/",
        },
    )

    channel = ET.SubElement(tv, "channel", attrib={"id": CHANNEL_ID})
    display_name = ET.SubElement(channel, "display-name")
    display_name.text = CHANNEL_NAME

    skipped = 0
    for event in sorted(events, key=lambda e: e["start"]):
        start_dt = parse_iso8601(event["start"])
        if start_dt is None:
            print(
                f"[WARN] {event['league']}: unparseable start time "
                f"'{event['start']}' for '{event['title']}', skipping",
                file=sys.stderr,
            )
            skipped += 1
            continue

        stop_dt = start_dt + timedelta(hours=DEFAULT_EVENT_DURATION_HOURS)

        programme = ET.SubElement(
            tv,
            "programme",
            attrib={
                "start": xmltv_timestamp(start_dt),
                "stop": xmltv_timestamp(stop_dt),
                "channel": CHANNEL_ID,
            },
        )

        title = ET.SubElement(programme, "title", attrib={"lang": "en"})
        title.text = event["title"]

        sub_title_text = event["league"]
        if event["broadcasts"]:
            sub_title_text += " on " + "/".join(event["broadcasts"])
        sub_title = ET.SubElement(programme, "sub-title", attrib={"lang": "en"})
        sub_title.text = sub_title_text

        desc = ET.SubElement(programme, "desc", attrib={"lang": "en"})
        desc.text = f"{event['title']} ({event['league']}) - {event['status']}"

        if event["broadcasts"]:
            credits_elem = ET.SubElement(programme, "credits")
            for network in event["broadcasts"]:
                presenter = ET.SubElement(credits_elem, "presenter")
                presenter.text = network

        category = ET.SubElement(programme, "category", attrib={"lang": "en"})
        category.text = event["league"]

    if skipped:
        print(f"[INFO] Skipped {skipped} event(s) with unparseable start times", file=sys.stderr)

    return tv


def write_xmltv(tv_element: ET.Element, path: str) -> None:
    rough_string = ET.tostring(tv_element, encoding="utf-8")
    pretty = minidom.parseString(rough_string).toprettyxml(indent="  ", encoding="UTF-8")

    # toprettyxml adds a bunch of blank lines for elements with no children
    # text; strip them for a cleaner diff-friendly output file.
    lines = [line for line in pretty.decode("utf-8").splitlines() if line.strip()]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    events = collect_all_events()

    if not events:
        print("[ERROR] No events collected from any league; aborting.", file=sys.stderr)
        # Still write a valid (empty) XMLTV file so downstream consumers
        # don't choke on a missing/malformed file.
        tv = build_xmltv([])
        write_xmltv(tv, OUTPUT_FILE)
        return 1

    tv = build_xmltv(events)
    write_xmltv(tv, OUTPUT_FILE)

    print(f"Wrote {len(events)} event(s) to {OUTPUT_FILE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
