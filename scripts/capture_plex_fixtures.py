#!/usr/bin/env python3
"""Capture real Plex API responses for test fixtures.

This script connects to your Plex server and captures actual API responses
for use as test fixtures. It walks through:
1. OAuth login (PIN flow - opens browser)
2. Server selection
3. Libraries (movies and TV shows)
4. A movie with streams
5. A TV show -> season -> episode hierarchy
6. Setting audio/subtitle tracks

Usage:
    uv run python scripts/capture_plex_fixtures.py

    uv run python scripts/capture_plex_fixtures.py --interactive

    uv run python scripts/capture_plex_fixtures.py --token YOUR_TOKEN --url http://localhost:32400
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

PLEX_TV_URL = "https://plex.tv"
CLIENT_ID = f"salsa-fixture-capture-{uuid.uuid4().hex[:8]}"

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "plex_responses"


def get_plex_headers(token: str | None = None) -> dict:
    """Get standard Plex headers."""
    headers = {
        "Accept": "application/json",
        "X-Plex-Client-Identifier": CLIENT_ID,
        "X-Plex-Product": "SALSA",
        "X-Plex-Version": "1.0.0",
        "X-Plex-Platform": "Python",
    }
    if token:
        headers["X-Plex-Token"] = token
    return headers


async def plex_oauth_flow() -> tuple[str, str, str]:
    """
    Perform Plex OAuth PIN flow.

    Returns: (token, username, email)
    """
    print_header("Plex Authentication")

    async with httpx.AsyncClient() as client:
        print("Creating authentication PIN...")
        response = await client.post(
            f"{PLEX_TV_URL}/api/v2/pins",
            headers=get_plex_headers(),
            params={"strong": "true"},
        )
        response.raise_for_status()
        pin_data = response.json()

        pin_id = pin_data["id"]
        pin_code = pin_data["code"]

        auth_url = f"https://app.plex.tv/auth#?clientID={CLIENT_ID}&code={pin_code}&context%5Bdevice%5D%5Bproduct%5D=SALSA"

        print(f"\nPIN Code: {pin_code}")
        print("\nOpening browser for Plex login...")
        print(f"If browser doesn't open, visit: {auth_url}")

        webbrowser.open(auth_url)

        print("\nWaiting for authentication", end="", flush=True)

        for _ in range(120):
            await asyncio.sleep(1)
            print(".", end="", flush=True)

            response = await client.get(
                f"{PLEX_TV_URL}/api/v2/pins/{pin_id}",
                headers=get_plex_headers(),
                params={"code": pin_code},
            )
            response.raise_for_status()
            pin_status = response.json()

            if pin_status.get("authToken"):
                token = pin_status["authToken"]
                print(" ✓")

                response = await client.get(
                    f"{PLEX_TV_URL}/api/v2/user",
                    headers=get_plex_headers(token),
                )
                response.raise_for_status()
                user = response.json()

                username = user.get("username", "Unknown")
                email = user.get("email", "")

                print(f"\nLogged in as: {username} ({email})")
                return token, username, email

        print(" ✗")
        raise TimeoutError("Authentication timed out after 2 minutes")


async def get_plex_servers(token: str) -> list[dict]:
    """Get list of available Plex servers."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PLEX_TV_URL}/api/v2/resources",
            headers=get_plex_headers(token),
            params={"includeHttps": 1, "includeRelay": 1},
        )
        response.raise_for_status()
        resources = response.json()

        servers = [r for r in resources if r.get("provides") == "server"]
        return servers


async def select_server(token: str) -> str:
    """Let user select a Plex server and return its URL."""
    print_header("Server Selection")

    print("Fetching available servers...")
    servers = await get_plex_servers(token)

    if not servers:
        raise ValueError("No Plex servers found!")

    print("\nAvailable servers:")
    all_connections = []
    for server in servers:
        name = server.get("name", "Unknown")
        owned = "owned" if server.get("owned") else "shared"
        print(f"\n  {name} ({owned}):")

        for conn in server.get("connections", []):
            uri = conn.get("uri", "")
            local = "local" if conn.get("local") else "remote"
            relay = " [relay]" if conn.get("relay") else ""
            idx = len(all_connections) + 1
            all_connections.append({"uri": uri, "name": name, "conn": conn})
            print(f"    [{idx}] {uri} ({local}{relay})")

    while True:
        try:
            choice = input("\nSelect server connection number: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(all_connections):
                selected = all_connections[idx]
                server_url = selected["uri"]

                print(f"\nTesting connection to {server_url}...")
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{server_url}/identity",
                        headers=get_plex_headers(token),
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    identity = response.json()
                    version = identity.get("MediaContainer", {}).get("version", "?")
                    print(f"✓ Connected! Server version: {version}")

                return server_url
            print("Invalid selection, try again.")
        except ValueError:
            print("Please enter a number.")
        except httpx.ConnectError:
            print("✗ Connection failed! Try another.")
        except httpx.HTTPStatusError as e:
            print(f"✗ HTTP error: {e.response.status_code}")


class PlexCapture:
    """Capture Plex API responses."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client: httpx.AsyncClient | None = None
        self.captured: dict[str, dict] = {}

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "X-Plex-Token": self.token,
                "X-Plex-Client-Identifier": "salsa-test-capture",
                "X-Plex-Product": "SALSA Test Capture",
                "X-Plex-Version": "1.0.0",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def get(self, path: str, name: str) -> dict:
        """Make GET request and capture response."""
        url = f"{self.base_url}{path}"
        print(f"  GET {path}...")
        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()
        self.captured[name] = data
        return data

    async def put(self, path: str, name: str) -> dict | None:
        """Make PUT request and capture response."""
        url = f"{self.base_url}{path}"
        print(f"  PUT {path}...")
        response = await self.client.put(url)
        response.raise_for_status()
        if response.content:
            data = response.json()
            self.captured[name] = data
            return data
        self.captured[name] = {"status": "success", "status_code": response.status_code}
        return None

    def save_fixtures(self):
        """Save all captured responses to fixture files."""
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

        for name, data in self.captured.items():
            filepath = FIXTURES_DIR / f"{name}.json"
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Saved: {filepath.name}")

        combined_path = FIXTURES_DIR / "_all_fixtures.json"
        with open(combined_path, "w") as f:
            json.dump(
                {
                    "captured_at": datetime.now().isoformat(),
                    "base_url": self.base_url,
                    "fixtures": self.captured,
                },
                f,
                indent=2,
            )
        print(f"  Saved: {combined_path.name}")


def print_header(text: str):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")


def print_item(label: str, value: str, indent: int = 0):
    """Print labeled item."""
    prefix = "  " * indent
    print(f"{prefix}{label}: {value}")


def select_item(
    items: list[dict],
    prompt: str,
    key_field: str = "ratingKey",
    title_field: str = "title",
) -> dict | None:
    """Let user select an item from a list."""
    if not items:
        print("  No items available!")
        return None

    print(f"\n{prompt}")
    for i, item in enumerate(items):
        title = item.get(title_field, "Unknown")
        key = item.get(key_field, "?")
        item_type = item.get("type", "")
        year = item.get("year", "")
        extra = f" ({year})" if year else ""
        extra += f" [{item_type}]" if item_type else ""
        print(f"  [{i+1}] {title}{extra} (key: {key})")

    while True:
        try:
            choice = input("\nEnter number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print("Invalid selection, try again.")
        except ValueError:
            print("Please enter a number.")


def select_stream(streams: list[dict], stream_type: str) -> dict | None:
    """Let user select a stream."""
    if not streams:
        print(f"  No {stream_type} streams available!")
        return None

    print(f"\n{stream_type} streams:")
    for i, stream in enumerate(streams):
        lang = stream.get("language", stream.get("languageCode", "Unknown"))
        codec = stream.get("codec", "?")
        title = stream.get("displayTitle", stream.get("title", ""))
        selected = " [SELECTED]" if stream.get("selected") else ""
        channels = f" {stream.get('channels')}ch" if stream.get("channels") else ""
        print(f"  [{i+1}] {lang} - {codec}{channels} - {title}{selected} (id: {stream['id']})")

    while True:
        try:
            prompt = f"\nSelect {stream_type} stream (or 's' to skip, '0' to disable subs): "
            choice = input(prompt).strip()
            if choice.lower() == "s":
                return None
            idx = int(choice)
            if idx == 0 and stream_type == "subtitle":
                return {"id": 0, "disable": True}
            idx -= 1
            if 0 <= idx < len(streams):
                return streams[idx]
            print("Invalid selection, try again.")
        except ValueError:
            print("Please enter a number.")


async def capture_interactive(capture: PlexCapture):
    """Interactive mode - step through and select items."""

    print_header("Step 1: Server Identity")
    identity = await capture.get("/identity", "server_identity")
    print_item("Server", identity.get("MediaContainer", {}).get("machineIdentifier", "Unknown"))
    print_item("Version", identity.get("MediaContainer", {}).get("version", "Unknown"))

    print_header("Step 2: Libraries")
    libs_data = await capture.get("/library/sections", "libraries")
    libraries = libs_data.get("MediaContainer", {}).get("Directory", [])

    video_libs = [l for l in libraries if l.get("type") in ("movie", "show")]

    while True:
        lib = select_item(video_libs, "Select a library to explore:", key_field="key")
        if not lib:
            break

        lib_key = lib["key"]
        lib_type = lib["type"]

        print_header(f"Step 3: Library Items - {lib['title']}")
        items_data = await capture.get(
            f"/library/sections/{lib_key}/all", f"library_{lib_key}_items"
        )
        items = items_data.get("MediaContainer", {}).get("Metadata", [])

        if lib_type == "movie":
            movie = select_item(items, "Select a movie:")
            if movie:
                await explore_movie(capture, movie)
        else:
            show = select_item(items, "Select a TV show:")
            if show:
                await explore_show(capture, show)

        cont = input("\nExplore another library? (y/n): ").strip().lower()
        if cont != "y":
            break


async def explore_movie(capture: PlexCapture, movie: dict):
    """Explore a movie's streams."""
    rating_key = movie["ratingKey"]
    title = movie.get("title", "Unknown")

    print_header(f"Movie: {title}")

    metadata = await capture.get(
        f"/library/metadata/{rating_key}?checkFiles=1", f"movie_{rating_key}_metadata"
    )

    item = metadata.get("MediaContainer", {}).get("Metadata", [{}])[0]
    media = item.get("Media", [{}])[0]
    part = media.get("Part", [{}])[0]
    streams = part.get("Stream", [])

    part_id = part.get("id")
    print_item("Part ID", str(part_id))

    audio_streams = [s for s in streams if s.get("streamType") == 2]
    subtitle_streams = [s for s in streams if s.get("streamType") == 3]

    print(f"\n  Found {len(audio_streams)} audio streams, {len(subtitle_streams)} subtitle streams")

    audio = select_stream(audio_streams, "audio")
    if audio and part_id:
        await capture.put(
            f"/library/parts/{part_id}?audioStreamID={audio['id']}&allParts=1",
            f"movie_{rating_key}_set_audio",
        )
        print(f"  ✓ Set audio to stream {audio['id']}")

    subtitle = select_stream(subtitle_streams, "subtitle")
    if subtitle and part_id:
        stream_id = 0 if subtitle.get("disable") else subtitle["id"]
        await capture.put(
            f"/library/parts/{part_id}?subtitleStreamID={stream_id}&allParts=1",
            f"movie_{rating_key}_set_subtitle",
        )
        print(f"  ✓ Set subtitle to stream {stream_id}")


async def explore_show(capture: PlexCapture, show: dict):
    """Explore a TV show's hierarchy."""
    rating_key = show["ratingKey"]
    title = show.get("title", "Unknown")

    print_header(f"TV Show: {title}")

    await capture.get(f"/library/metadata/{rating_key}", f"show_{rating_key}_metadata")

    seasons_data = await capture.get(
        f"/library/metadata/{rating_key}/children", f"show_{rating_key}_seasons"
    )
    seasons = seasons_data.get("MediaContainer", {}).get("Metadata", [])

    season = select_item(seasons, "Select a season:", title_field="title")
    if not season:
        return

    await explore_season(capture, season, show_title=title)


async def explore_season(capture: PlexCapture, season: dict, show_title: str = ""):
    """Explore a season's episodes."""
    rating_key = season["ratingKey"]
    title = season.get("title", "Unknown")

    print_header(f"Season: {show_title} - {title}")

    await capture.get(f"/library/metadata/{rating_key}", f"season_{rating_key}_metadata")

    episodes_data = await capture.get(
        f"/library/metadata/{rating_key}/children", f"season_{rating_key}_episodes"
    )
    episodes = episodes_data.get("MediaContainer", {}).get("Metadata", [])

    print(f"\n  Found {len(episodes)} episodes")

    if episodes:
        first_ep = episodes[0]
        first_ep_key = first_ep["ratingKey"]
        await capture.get(
            f"/library/metadata/{first_ep_key}?checkFiles=1",
            f"episode_{first_ep_key}_metadata_sample",
        )

    episode = select_item(episodes, "Select an episode:", title_field="title")
    if not episode:
        return

    await explore_episode(capture, episode)


async def explore_episode(capture: PlexCapture, episode: dict):
    """Explore an episode's streams."""
    rating_key = episode["ratingKey"]
    title = episode.get("title", "Unknown")
    index = episode.get("index", "?")

    print_header(f"Episode {index}: {title}")

    metadata = await capture.get(
        f"/library/metadata/{rating_key}?checkFiles=1", f"episode_{rating_key}_metadata"
    )

    item = metadata.get("MediaContainer", {}).get("Metadata", [{}])[0]
    media = item.get("Media", [{}])[0]
    part = media.get("Part", [{}])[0]
    streams = part.get("Stream", [])

    part_id = part.get("id")
    print_item("Part ID", str(part_id))

    audio_streams = [s for s in streams if s.get("streamType") == 2]
    subtitle_streams = [s for s in streams if s.get("streamType") == 3]

    print(f"\n  Found {len(audio_streams)} audio streams, {len(subtitle_streams)} subtitle streams")

    audio = select_stream(audio_streams, "audio")
    if audio and part_id:
        await capture.put(
            f"/library/parts/{part_id}?audioStreamID={audio['id']}&allParts=1",
            f"episode_{rating_key}_set_audio",
        )
        print(f"  ✓ Set audio to stream {audio['id']}")

    subtitle = select_stream(subtitle_streams, "subtitle")
    if subtitle and part_id:
        stream_id = 0 if subtitle.get("disable") else subtitle["id"]
        await capture.put(
            f"/library/parts/{part_id}?subtitleStreamID={stream_id}&allParts=1",
            f"episode_{rating_key}_set_subtitle",
        )
        print(f"  ✓ Set subtitle to stream {stream_id}")


async def capture_automatic(capture: PlexCapture):
    """Automatic mode - capture standard fixtures without interaction."""

    print_header("Capturing Standard Fixtures")

    print("\n1. Server identity...")
    await capture.get("/identity", "server_identity")

    print("2. Libraries...")
    libs_data = await capture.get("/library/sections", "libraries")
    libraries = libs_data.get("MediaContainer", {}).get("Directory", [])

    movie_lib = next((l for l in libraries if l.get("type") == "movie"), None)
    show_lib = next((l for l in libraries if l.get("type") == "show"), None)

    if movie_lib:
        lib_key = movie_lib["key"]
        print(f"3. Movie library '{movie_lib['title']}'...")
        items_data = await capture.get(
            f"/library/sections/{lib_key}/all", f"library_{lib_key}_movies"
        )
        movies = items_data.get("MediaContainer", {}).get("Metadata", [])

        if movies:
            movie = movies[0]
            movie_key = movie["ratingKey"]
            print(f"   - Movie '{movie.get('title')}'...")
            await capture.get(
                f"/library/metadata/{movie_key}?checkFiles=1", f"movie_{movie_key}_metadata"
            )

    if show_lib:
        lib_key = show_lib["key"]
        print(f"4. TV library '{show_lib['title']}'...")
        items_data = await capture.get(
            f"/library/sections/{lib_key}/all", f"library_{lib_key}_shows"
        )
        shows = items_data.get("MediaContainer", {}).get("Metadata", [])

        if shows:
            show = shows[0]
            show_key = show["ratingKey"]
            print(f"   - Show '{show.get('title')}'...")
            await capture.get(f"/library/metadata/{show_key}", f"show_{show_key}_metadata")

            seasons_data = await capture.get(
                f"/library/metadata/{show_key}/children", f"show_{show_key}_seasons"
            )
            seasons = seasons_data.get("MediaContainer", {}).get("Metadata", [])

            if seasons:
                season = seasons[0]
                season_key = season["ratingKey"]
                print(f"   - Season '{season.get('title')}'...")
                await capture.get(
                    f"/library/metadata/{season_key}", f"season_{season_key}_metadata"
                )

                episodes_data = await capture.get(
                    f"/library/metadata/{season_key}/children", f"season_{season_key}_episodes"
                )
                episodes = episodes_data.get("MediaContainer", {}).get("Metadata", [])

                if episodes:
                    episode = episodes[0]
                    ep_key = episode["ratingKey"]
                    print(f"   - Episode '{episode.get('title')}'...")
                    await capture.get(
                        f"/library/metadata/{ep_key}?checkFiles=1", f"episode_{ep_key}_metadata"
                    )

    print("\n✓ Automatic capture complete!")


async def main():
    parser = argparse.ArgumentParser(description="Capture Plex API responses for test fixtures")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument(
        "--url", default=os.environ.get("PLEX_URL"), help="Server URL (skip server selection)"
    )
    parser.add_argument(
        "--token", default=os.environ.get("PLEX_TOKEN"), help="Plex token (skip OAuth)"
    )
    args = parser.parse_args()

    token = args.token
    server_url = args.url

    try:
        if not token:
            token, _username, _email = await plex_oauth_flow()
        else:
            print("Using provided token...")

        if not server_url:
            server_url = await select_server(token)
        else:
            print(f"Using provided server URL: {server_url}")

        async with PlexCapture(server_url, token) as capture:
            if args.interactive:
                await capture_interactive(capture)
            else:
                await capture_automatic(capture)

            print_header("Saving Fixtures")
            capture.save_fixtures()

            print(f"\n✓ Done! Fixtures saved to {FIXTURES_DIR}")

    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code}")
        if e.response.status_code == 401:
            print("Authentication failed")
        sys.exit(1)
    except httpx.ConnectError as e:
        print(f"\nConnection failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
