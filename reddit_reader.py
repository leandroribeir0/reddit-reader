"""Read-only Reddit client for searching posts and reading threads from the terminal."""

import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

USERNAME = "alphaspy"
USER_AGENT = f"script:reddit-reader:v1.0 (by /u/{USERNAME})"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_URL = "https://oauth.reddit.com"

# Well below the free tier (100/min): one user, requests only when a question is asked.
MAX_REQUESTS_PER_MINUTE = 10

STATE_FILE = Path.home() / ".cache" / "reddit-reader" / "state.json"


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"requests": [], "token": None, "token_expires": 0}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def wait_for_slot(state):
    """Sliding window shared across runs, so separate invocations can't exceed the cap together."""
    now = time.time()
    state["requests"] = [t for t in state["requests"] if now - t < 60]
    if len(state["requests"]) >= MAX_REQUESTS_PER_MINUTE:
        time.sleep(60 - (now - state["requests"][0]))
        state["requests"].pop(0)
    state["requests"].append(time.time())
    save_state(state)


def get_token(state):
    if state["token"] and time.time() < state["token_expires"] - 60:
        return state["token"]

    client_id = os.environ["REDDIT_CLIENT_ID"]
    client_secret = os.environ["REDDIT_CLIENT_SECRET"]
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "read"}).encode(),
        headers={"Authorization": f"Basic {credentials}", "User-Agent": USER_AGENT},
    )
    wait_for_slot(state)
    with urllib.request.urlopen(request) as response:
        data = json.load(response)

    state["token"] = data["access_token"]
    state["token_expires"] = time.time() + data["expires_in"]
    save_state(state)
    return state["token"]


def api_get(path, params):
    state = load_state()
    token = get_token(state)
    url = f"{API_URL}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"Authorization": f"bearer {token}", "User-Agent": USER_AGENT}
    )
    wait_for_slot(state)
    with urllib.request.urlopen(request) as response:
        # Reddit's own limit headers win over the local cap if they are ever stricter.
        remaining = float(response.headers.get("X-Ratelimit-Remaining", 1))
        if remaining < 1:
            time.sleep(float(response.headers.get("X-Ratelimit-Reset", 60)))
        return json.load(response)


def search(args):
    path = f"/r/{args.subreddit}/search" if args.subreddit else "/search"
    params = {
        "q": args.query,
        "sort": args.sort,
        "t": args.time,
        "limit": args.limit,
        "restrict_sr": bool(args.subreddit),
        "raw_json": 1,
    }
    for child in api_get(path, params)["data"]["children"]:
        post = child["data"]
        print(f"[{post['score']}] r/{post['subreddit']} - {post['title']}")
        print(f"  {post['num_comments']} comments - https://www.reddit.com{post['permalink']}\n")


def thread_id(value):
    """Accepts a full thread URL or a bare post id."""
    parts = urllib.parse.urlparse(value).path.strip("/").split("/")
    return parts[parts.index("comments") + 1] if "comments" in parts else parts[-1]


def print_comments(children, indent=0):
    for child in children:
        if child["kind"] != "t1":
            continue
        comment = child["data"]
        prefix = "  " * indent
        print(f"{prefix}- u/{comment['author']} [{comment['score']}]")
        for line in comment["body"].splitlines():
            print(f"{prefix}  {line}")
        if comment["replies"]:
            print_comments(comment["replies"]["data"]["children"], indent + 1)


def thread(args):
    params = {"limit": args.limit, "depth": args.depth, "sort": "top", "raw_json": 1}
    post_listing, comment_listing = api_get(f"/comments/{thread_id(args.thread)}", params)
    post = post_listing["data"]["children"][0]["data"]
    print(f"r/{post['subreddit']} - {post['title']}")
    print(f"u/{post['author']} [{post['score']}] - https://www.reddit.com{post['permalink']}\n")
    if post["selftext"]:
        print(post["selftext"] + "\n")
    print_comments(comment_listing["data"]["children"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)

    search_parser = commands.add_parser("search", help="search public posts")
    search_parser.add_argument("query")
    search_parser.add_argument("-s", "--subreddit")
    search_parser.add_argument("--sort", default="relevance", choices=["relevance", "top", "new", "comments"])
    search_parser.add_argument("--time", default="all", choices=["hour", "day", "week", "month", "year", "all"])
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.set_defaults(func=search)

    thread_parser = commands.add_parser("thread", help="read a post and its comments")
    thread_parser.add_argument("thread", help="thread URL or post id")
    thread_parser.add_argument("--limit", type=int, default=50, help="max comments")
    thread_parser.add_argument("--depth", type=int, default=3, help="max reply depth")
    thread_parser.set_defaults(func=thread)

    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.func(args)


if __name__ == "__main__":
    main()
