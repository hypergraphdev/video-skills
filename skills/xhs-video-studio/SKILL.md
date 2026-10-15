---
name: xhs-video-studio
description: >-
  Use the user's own AI video studio (视频工作室, on www.bcv.one/xhs) from the chat: generate a short video from an
  idea, video-chat with a talking avatar (a photo, optionally speaking as a well-known person), turn a story into a
  long multi-part video that plays continuously, or start an endless story game that keeps playing. Trigger when the
  user asks to 生成视频 / 做一段视频 / 拍个视频, 视频聊天 / 和头像聊天 / 让照片里的人说话, 把故事拍成视频 / 长视频,
  无限游戏 / 互动剧, or to check, steer (插入剧情) or stop one. Private to the studio owner's account; needs the
  studio's access token.
version: 1.0.0
---

# 视频工作室 · Video studio

The user's own video studio on www.bcv.one/xhs drives one GPU machine. This skill uses it from here.
All commands run the bundled script: `python3 scripts/studio.py <command> …` (path relative to this skill's folder;
Python 3.8+, no packages). Add `--json` before the command for the raw server reply. Videos are saved to
`~/Downloads/xhs-studio/` (change with `--out DIR` before the command).

## First use

1. `python3 scripts/studio.py whoami`. If it says there is no token, or the token was rejected, ask the user:
   「请在视频工作室页面右上角点 **AI 助手** → 生成令牌，复制后发给我。」
2. `python3 scripts/studio.py login <token>`. It checks the token and saves it (readable only by the user).
   **Never repeat the token back in the conversation.**

## The machine

Everything needs the GPU machine to be on. **This skill cannot switch it on or off** (the user decided that; the
server refuses it too). Commands check first and fail with a link when it is off: tell the user to open the link and
click 「开机」 there, and continue when they say it is on. `machine` shows whether it is on and the compute balance.
Do not ask the user to start it just to check something.

There is one GPU: one long video or endless game at a time, and a single video waits for the previous one. When the
server says something is still running, tell the user what and offer to `stop` it — do not stop it on your own.

## What the user wants → command

| The user wants… | Command |
|---|---|
| A short video of something (5–15 s) | `video "<idea>" [--seconds 8] [--aspect 9:16]` |
| Video chat with a person in a photo | `avatar <photo> [--who "马斯克"]` once, then `chat "<what they said>"` for each turn |
| The avatar to speak as a well-known person / as an ordinary person again | `who "<name>"` / `who ""` |
| Go back to an avatar used before | `talks`, then `use <name>` |
| A story filmed as a long video | `story "<story>"` (add `--faithful full` to film a pasted text as written) |
| An endless story game | `game "<opening>"`, steer with `insert "<plot>"` |
| How far it is / stop it | `status [--kind game]` / `stop [--kind game]` |
| The finished long video as a file | `download [id]` |

## How to answer

- **Single video** (`video`): it waits up to 8 minutes and downloads the mp4. Give the user the file path (open or
  attach it if your app can show files) and the studio link. If it is not done in time, it prints a run id: run
  `video-status <run> --wait 5` later. The idea is expanded into a full video prompt by the server unless you pass
  `--as-prompt`.
- **Video chat** (`chat`): returns the reply text and 1–3 short mp4 clips that play in order (the first is ready in a
  few seconds). Show the reply and the clips. The avatar and persona stay set between turns. Pass the user's words as
  they said them; do not add your own reply — the avatar answers.
- **Story / game**: they return at once with a link to the studio page. **Tell the user to open the link**: the page
  plays it continuously while it is being made. An endless game only keeps going while that page is open (it pauses
  25 s after the page is closed and stops after 30 minutes). Pages may ask the user to confirm the characters' looks
  (「形象没问题，开拍」); that is done on the page. Use `status` when asked how it is going.
- Errors are printed in Chinese from the server: relay them plainly. `401` → ask for a new token; `403` → this is
  something only the web page can do (machine on/off, tokens).

## Cost

The machine costs compute units by the hour while it is on, and the studio also calls paid AI models for scripts and
replies. Do not run commands in loops or make videos the user did not ask for.
