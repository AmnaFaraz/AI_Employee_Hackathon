import tweepy
import time
import subprocess
from pathlib import Path

VAULT = Path('/mnt/c/Users/dell/Documents/AI_employee_vault')
LOG_FILE = VAULT / 'Logs' / 'twitter.log'

# Get from developer.twitter.com
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
ACCESS_TOKEN_SECRET = "YOUR_ACCESS_TOKEN_SECRET"

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

def post_tweet(text):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    try:
        client.create_tweet(text=text[:280])
        log(f"TWEET POSTED: {text[:60]}")
        return True
    except Exception as e:
        log(f"TWEET FAILED: {e}")
        return False

def watch_approved_for_twitter():
    log("=== Twitter Poster Started ===")
    approved = VAULT / 'Approved'
    done = VAULT / 'Done'
    processed = set()

    while True:
        try:
            for filepath in approved.iterdir():
                if filepath.name in processed or filepath.name == '.gitkeep':
                    continue
                content = filepath.read_text(encoding='utf-8')
                if 'type: twitter' in content.lower():
                    lines = content.splitlines()
                    tweet_text = ""
                    for i, line in enumerate(lines):
                        if "## Post Content" in line:
                            tweet_text = "\n".join(lines[i+1:i+5]).strip()
                            break
                    if tweet_text:
                        post_tweet(tweet_text)
                        filepath.rename(done / filepath.name)
                        git_commit(f"twitter: posted {filepath.name}")
                processed.add(filepath.name)
            time.sleep(30)
        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(30)

if __name__ == '__main__':
    watch_approved_for_twitter()
