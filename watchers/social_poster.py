import requests
import time
import subprocess
from pathlib import Path

VAULT = Path('/mnt/c/Users/dell/Documents/AI_employee_vault')
LOG_FILE = VAULT / 'Logs' / 'social.log'

# Facebook/Instagram — get from Meta Developer Portal
FB_PAGE_ACCESS_TOKEN = "YOUR_FB_PAGE_ACCESS_TOKEN"
FB_PAGE_ID = "YOUR_FB_PAGE_ID"
IG_USER_ID = "YOUR_IG_USER_ID"

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)
    print(entry.strip())

def git_commit(message):
    subprocess.run(['git', '-C', str(VAULT), 'add', '-A'])
    subprocess.run(['git', '-C', str(VAULT), 'commit', '-m', message])
    subprocess.run(['git', '-C', str(VAULT), 'push'])

def post_facebook(message):
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    payload = {"message": message, "access_token": FB_PAGE_ACCESS_TOKEN}
    r = requests.post(url, data=payload)
    if r.status_code == 200:
        log(f"FACEBOOK POST SUCCESS: {message[:60]}")
        return True
    log(f"FACEBOOK FAILED: {r.text}")
    return False

def post_instagram(caption):
    # Step 1: Create media container
    url1 = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    payload1 = {
        "caption": caption,
        "media_type": "REELS",
        "access_token": FB_PAGE_ACCESS_TOKEN
    }
    r1 = requests.post(url1, data=payload1)
    if r1.status_code != 200:
        log(f"INSTAGRAM CONTAINER FAILED: {r1.text}")
        return False
    creation_id = r1.json().get("id")
    # Step 2: Publish
    url2 = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    payload2 = {"creation_id": creation_id, "access_token": FB_PAGE_ACCESS_TOKEN}
    r2 = requests.post(url2, data=payload2)
    if r2.status_code == 200:
        log(f"INSTAGRAM POST SUCCESS: {caption[:60]}")
        return True
    log(f"INSTAGRAM PUBLISH FAILED: {r2.text}")
    return False

def watch_approved_for_social():
    log("=== Social Poster Started (Facebook + Instagram) ===")
    approved = VAULT / 'Approved'
    done = VAULT / 'Done'
    processed = set()

    while True:
        try:
            for filepath in approved.iterdir():
                if filepath.name in processed or filepath.name == '.gitkeep':
                    continue
                content = filepath.read_text(encoding='utf-8')
                if 'type: social' in content.lower():
                    lines = content.splitlines()
                    post_text = ""
                    for i, line in enumerate(lines):
                        if "## Post Content" in line:
                            post_text = "\n".join(lines[i+1:i+10]).strip()
                            break
                    if post_text:
                        post_facebook(post_text)
                        post_instagram(post_text)
                        filepath.rename(done / filepath.name)
                        git_commit(f"social: fb+ig posted {filepath.name}")
                processed.add(filepath.name)
            time.sleep(30)
        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(30)

if __name__ == '__main__':
    watch_approved_for_social()
