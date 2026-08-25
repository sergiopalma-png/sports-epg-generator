# Sports XMLTV EPG Generator

Generates a single XMLTV guide (`sports_guide.xml`) covering upcoming and
in-progress games across NFL, NBA, MLB, NHL, WNBA, MLS, NCAA Football, and
NCAA Basketball, sourced from ESPN's public scoreboard API. All games are
mapped to one dummy channel (`sports-daily-guide`) so IPTV apps can attach
it to any custom/dummy stream.

The script uses only the Python standard library — no `pip install`
required.

## Files

- [`generate_epg.py`](generate_epg.py) — fetches ESPN scoreboards and writes `sports_guide.xml`.
- [`.github/workflows/update_epg.yml`](.github/workflows/update_epg.yml) — runs the generator daily (06:00 UTC) and on demand, committing any changes back to `main`.
- `sports_guide.xml` — the generated XMLTV output (committed by CI).

## Running locally

```bash
python3 generate_epg.py
```

This writes `sports_guide.xml` to the repository root. Warnings about
individual leagues or events (network errors, missing fields) are printed
to stderr but do not stop the run — the script always produces a valid
XMLTV file as long as at least one league returns data.

## 1. Hosting the guide with GitHub Pages

1. Push this repository to GitHub (if you haven't already).
2. In the repo, go to **Settings → Pages**.
3. Under **Build and deployment → Source**, select **Deploy from a branch**.
4. Under **Branch**, select `main` and folder `/ (root)`, then **Save**.
5. Wait a minute for GitHub Pages to build, then note the published URL, e.g.:

   ```
   https://<your-username>.github.io/<your-repo>/sports_guide.xml
   ```

   You can find the exact URL at the top of the Pages settings page once
   it's live.

The GitHub Actions workflow keeps `sports_guide.xml` up to date daily, and
since it's served straight from `main`, GitHub Pages will pick up each new
commit automatically.

## 2. Adding the guide to IPTVEditor

1. Log into [IPTVEditor](https://iptveditor.com/).
2. Open (or create) the playlist/profile you want the guide attached to.
3. Go to the **EPG** section and choose **Add Custom EPG Source** (or
   equivalent "Add EPG URL" option).
4. Paste your GitHub Pages URL from step 1 above, e.g.:

   ```
   https://<your-username>.github.io/<your-repo>/sports_guide.xml
   ```

5. Save, then trigger an EPG refresh/sync so IPTVEditor pulls in the
   `sports-daily-guide` channel and its programme listings.

## 3. Assigning the EPG channel to a dummy stream in TiviMate

1. In your IPTV provider's playlist (or a custom M3U you maintain), make
   sure there's a dummy/placeholder channel entry you want to use to
   display this guide, e.g.:

   ```
   #EXTINF:-1 tvg-id="sports-daily-guide",Daily US Sports Schedule
   http://your-dummy-stream-url
   ```

   The `tvg-id` should match the channel id used in the XMLTV file
   (`sports-daily-guide`).

2. Open **TiviMate** and go to **Settings → Playlists**, and make sure
   the playlist containing that dummy channel is added/refreshed.
3. Go to **Settings → EPG (TV Guide)** and add the same GitHub Pages URL
   as a custom EPG source:

   ```
   https://<your-username>.github.io/<your-repo>/sports_guide.xml
   ```

4. Force an EPG refresh from that same settings screen.
5. Open the channel list, find your dummy channel (**Daily US Sports
   Schedule**), and confirm the guide now shows game titles, times, and
   networks. If TiviMate doesn't auto-match it, long-press the channel →
   **Edit channel** → **EPG source** → manually select
   `sports-daily-guide`.

## Notes

- Game times in `sports_guide.xml` are in UTC (`+0000`), per the XMLTV
  spec; TiviMate/IPTVEditor will convert to the device's local timezone
  for display.
- Each event is given a fixed 3-hour duration, since ESPN's scoreboard
  API does not report actual game length.
- Broadcast network info (ESPN, TNT, NBC, regional sports networks, etc.)
  is included in the programme's subtitle and `<credits><presenter>`
  fields when ESPN provides it; not every event has broadcast data.
