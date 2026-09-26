import os
import base64
import requests

def push_to_github():
    """Pushes updated playlist.m3u to GitHub via REST API."""
    token = os.getenv("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")
    repo = "armeanco/STRIP"  # e.g., "johndoe/my-iptv"
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

# Call this at the very end of your main execution flow:
if __name__ == "__main__":
    build_multichannel_playlist()
    push_to_github()
