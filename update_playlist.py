import os
import base64
import time
import requests
from playwright.sync_api import sync_playwright

# 1. Define all your target channels and their page URLs
CHANNELS = {
    "Viasat": "https://live.viks.tv/023422-viasat_nature.html",
    "ICTV": "https://live.viks.tv/111213-ictv_tv-kanal.html",
    "2+2": "https://live.viks.tv/021117-22-tv.html",
    "1+1": "https://live.viks.tv/021922-pervyy-kanal.html",
    "Pobeda": "https://live.viks.tv/024922-pobeda.html",
    "MTV80": "https://live.viks.tv/021022-vh1-classic.html",
    "MTV00": "https://live.viks.tv/027522-vh1-europe.html",
    "Eralash": "https://live.viks.tv/023622-eralash.html",
    "NATGEO": "https://live.viks.tv/022422-national-geographic.html",
    "EUROSPORT2": "https://live.viks.tv/023622-evrosport2-tv.html",
    "EUROSPORT": "https://live.viks.tv/027721-evrosport-tv.html",
    "MOSFILM": "https://live.viks.tv/106326-mosfilm.html",
    "MIR": "https://live.viks.tv/025522-mir.html",
    "R24": "https://live.viks.tv/091810-rossiya_24_tv.html",
    "RTRPLANETA": "https://live.viks.tv/098410-rtr_rossiya.html",
    "RUSSIA1": "https://live.viks.tv/092022-rossiya1_tv.html",
    "DISCOVERY": "https://live.viks.tv/029122-discovery.html",
    "NATGEOWILD": "https://live.viks.tv/029422-nat-geo-wild.html",
    "RUSSIARTR": "https://live.viks.tv/099610-rossiya-rtr.html",
    "Paramount": "https://live.viks.tv/021922-paramount-channel.html"
}

def fetch_logo_database():
    """Fetch channel logos from the open-source iptv-org API."""
    print("[*] Fetching channel metadata & logos from iptv-org database...")
    try:
        response = requests.get("https://iptv-org.github.io/api/channels.json", timeout=10)
        response.raise_for_status()
        channels_data = response.json()
        
        # Build a fast lookup dictionary (lowercase name -> logo URL)
        logo_map = {}
        for ch in channels_data:
            name = ch.get("name", "").strip().lower()
            logo = ch.get("logo")
            if name and logo:
                logo_map[name] = logo
        return logo_map
    except Exception as e:
        print(f"[!] Warning: Could not fetch logos from API ({e}). Proceeding without logos.")
        return {}


def extract_stream_for_channel(context, channel_name: str, page_url: str) -> str:
    captured_stream = None
    
    # Parse numerical channel ID from page URL (e.g. '110' from '110-viasat-explore.html')
    channel_id = page_url.split('/')[-1].split('-')[0]

    # Fresh isolated tab for this channel
    page = context.new_page()

    def handle_request(request):
        nonlocal captured_stream
        req_url = request.url
        
        # Verify .m3u8 extension and ensure it matches the channel ID
        if ".m3u8" in req_url and not captured_stream:
            if f"/{channel_id}/" in req_url or f"id={channel_id}" in req_url or "index.m3u8" in req_url:
                print(f"  [+] Match Verified for {channel_name} (ID {channel_id}): {req_url}")
                captured_stream = req_url

    page.on("request", handle_request)

    try:
        print(f"[*] Navigating to [{channel_name}] -> {page_url}...")
        page.goto(page_url, timeout=25000, wait_until="domcontentloaded")
        time.sleep(3)

        # Trigger playable elements inside sub-frames if needed
        for frame in page.frames:
            try:
                for selector in ["button", ".play", "#player", "video"]:
                    elem = frame.locator(selector).first
                    if elem.is_visible():
                        elem.click(force=True, timeout=1000)
            except Exception:
                pass

        time.sleep(5) # Wait for network packets to register

    except Exception as e:
        print(f"  [!] Error scraping {channel_name}: {e}")
    finally:
        page.close() # Close tab to isolate network traffic

    return captured_stream


def build_multichannel_playlist():
    # Load external logos database
    logo_database = fetch_logo_database()
    
    m3u_entries = ["#EXTM3U\n"]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={"Referer": "https://viks.tv/"}
        )

        # Process channels sequentially
        for channel_name, page_url in CHANNELS.items():
            print(f"\n==========================================")
            print(f" Processing: {channel_name}")
            print(f"==========================================")
            
            # Find logo URL in iptv-org database or default to empty string
            logo_url = logo_database.get(channel_name.strip().lower(), "")
            if logo_url:
                print(f"  [+] Found Logo: {logo_url}")
            else:
                print(f"  [-] No logo match found for '{channel_name}'")

            stream_url = extract_stream_for_channel(context, channel_name, page_url)

            if stream_url:
                formatted_stream = f"{stream_url}|Referer=https://viks.tv/&User-Agent=Mozilla/5.0"
                
                # Formulate M3U entry with optional tvg-logo tag
                logo_tag = f' tvg-logo="{logo_url}"' if logo_url else ""
                
                m3u_entries.append(f'#EXTINF:-1{logo_tag} group-title="Live TV", {channel_name}\n')
                m3u_entries.append(f"{formatted_stream}\n\n")
                print(f"  [SUCCESS] Written {channel_name} to M3U")
            else:
                print(f"  [FAILED] No stream captured for {channel_name}")

        browser.close()

    # Write final output to playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.writelines(m3u_entries)

    print("\n[COMPLETE] Playlist updated with streams and logos -> 'playlist.m3u'")

def push_to_github():
    """Pushes updated playlist.m3u to GitHub via REST API."""
    token = os.getenv("GITHUB_TOKEN")  # Reads GITHUB_TOKEN variable from Render
    repo = "armeanco/STRIP"
    path = "playlist.m3u"
    branch = "main"

    if not token:
        print("[!] GITHUB_TOKEN environment variable not set. Skipping push.")
        return

    # Read updated playlist content
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[!] Could not read {path}: {e}")
        return

    # Base64 encode the content required by GitHub API
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Step A: Get existing file SHA (required to update existing file)
    sha = None
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        sha = res.json().get("sha")

    # Step B: Commit file update via API
    payload = {
        "message": "Auto-update playlist streams [Render Cron]",
        "content": encoded_content,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(url, json=payload, headers=headers)
    if put_res.status_code in [200, 201]:
        print("[+] Successfully updated playlist.m3u on GitHub!")
    else:
        print(f"[!] GitHub API push failed ({put_res.status_code}): {put_res.text}")

if __name__ == "__main__":
    build_multichannel_playlist()
    push_to_github()
