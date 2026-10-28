# reddit-reader

A small, read-only command-line client for the Reddit Data API. I use it on my own computer to search public posts and read threads when I'm troubleshooting dev and Windows setup issues.

The requests are made on my behalf by my AI coding assistant (Claude Code, by Anthropic): when I ask it something, it runs this script to find relevant threads, and the text it reads is sent to Anthropic's API only to answer my question in that session.

## What it does

- `search`: searches public posts, optionally inside one subreddit.
- `thread`: reads a post and its top comments.

That's all. It never posts, comments, votes, sends messages or touches private data.

## Limits and data use

- OAuth app-only token with the `read` scope, under my account u/alphaspy.
- Capped at 10 requests per minute, shared across runs, and it also backs off if Reddit's rate limit headers ask for it.
- Single user. Requests only happen when I ask a question.
- Nothing is stored, apart from the access token and request timestamps used for the rate limit (`~/.cache/reddit-reader/state.json`).
- Reddit content is not shared, sold, republished or used to train any model.

## Usage

Requires Python 3.9+, no extra packages.

```sh
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...

python reddit_reader.py search "remove line under tab bar" --subreddit WindowsTerminal
python reddit_reader.py thread https://www.reddit.com/r/PowerShell/comments/abc123/some_title/
```
