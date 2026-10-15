#!/usr/bin/env python3
"""视频工作室（xhs）的命令行：让 AI 助手在聊天框里生成视频、视频聊天、拍长视频和无限游戏。

只用 Python 自带的库（3.8+）。`python3 studio.py --help` 看全部命令。

设置从哪来（先找到的算）：
  令牌      --token、环境变量 XHS_STUDIO_TOKEN、用户配置文件（login 写的）
  站点地址  --base-url、环境变量 XHS_STUDIO_URL、用户配置文件、本技能自带的 config.json
用户配置文件：~/.config/xhs-video-studio/config.json（Windows 在 %APPDATA%），只有本人可读；
里面还记着聊天用的当前形象。开机、关机只能在网页上点，这里只查机器状态。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SKILL = "xhs-video-studio"
VERSION = "1.0.0"
PREFIX = "xhs_pat_"
SKILL_DIR = Path(__file__).resolve().parent.parent
OUT = Path.home() / "Downloads" / "xhs-studio"
FIRST_FRAMES, FRAME_GRID, FPS = 124, 17, 24          # 单条视频只有这些长度：124 + 17k 帧，k = 0..14
STATES = {"planning": "在写剧本", "running": "在生成", "done": "做完了", "stopped": "已停止", "failed": "出错了"}


class StudioError(Exception):
    pass


# ---------------------------------------------------------------- 设置


def config_path() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / SKILL / "config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / SKILL / "config.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with os.fdopen(os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def remember(**changes: Any) -> None:
    save_config({**read_json(config_path()), **changes})


def base_url(args: argparse.Namespace) -> str:
    found = (args.base_url or os.environ.get("XHS_STUDIO_URL") or read_json(config_path()).get("base_url")
             or read_json(SKILL_DIR / "config.json").get("base_url") or "")
    if not found:
        raise StudioError("没有站点地址：用 --base-url 指定，例如 https://www.bcv.one/xhs")
    return found.rstrip("/")


def token_of(args: argparse.Namespace) -> str:
    found = args.token or os.environ.get("XHS_STUDIO_TOKEN") or read_json(config_path()).get("token") or ""
    if not found:
        raise StudioError("还没有令牌：请用户在视频工作室页面右上角点“AI 助手”生成一个，再运行 login <令牌>")
    return found


def page(args: argparse.Namespace, tab: str) -> str:
    """视频工作室的页面（用户浏览器里登录过就能直接看）。"""
    return f"{base_url(args)}/h3?tab={tab}"


# ---------------------------------------------------------------- 请求


def request(args: argparse.Namespace, path: str, body: Any = None, timeout: int = 60, token: str = "") -> Any:
    """调视频工作室的接口，回 JSON；出错时把服务器说的原因带出来。"""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{base_url(args)}/api/h3{path}", data=data, method="GET" if body is None else "POST",
                                 headers={"Authorization": f"Bearer {token or token_of(args)}",
                                          "Content-Type": "application/json", "User-Agent": f"{SKILL}/{VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as reply:
            return json.loads(reply.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise StudioError(f"{exc.code} {said(exc.read())}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise StudioError(f"连不上视频工作室（{getattr(exc, 'reason', exc)}）") from None


def said(raw: bytes) -> str:
    try:
        reply = json.loads(raw)
        return str(reply.get("error") or reply.get("detail") or reply)
    except ValueError:
        return raw[:200].decode("utf-8", "replace")


def download(args: argparse.Namespace, path: str, name: str) -> Path:
    """把一个视频文件存到本机（--out，默认 ~/Downloads/xhs-studio），回本机路径。"""
    folder = Path(args.out).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    req = urllib.request.Request(f"{base_url(args)}/api/h3{path}", headers={
        "Authorization": f"Bearer {token_of(args)}", "User-Agent": f"{SKILL}/{VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as reply, open(target, "wb") as fh:
            while chunk := reply.read(1 << 16):
                fh.write(chunk)
    except urllib.error.HTTPError as exc:
        raise StudioError(f"{exc.code} {said(exc.read())}") from None
    return target


def online(args: argparse.Namespace) -> dict[str, Any]:
    """机器开着才往下走；没开就说清楚去哪里开（这里不能开）。"""
    machine = request(args, "/video/api/machine")
    if not machine.get("online"):
        raise StudioError(f"GPU 机器没开。请用户到 {page(args, 'video')} 右上角点“开机”（技能不能开关机），开好后再来。")
    return machine


def show(args: argparse.Namespace, text: str, raw: Any = None) -> None:
    print(json.dumps(raw, ensure_ascii=False, indent=2) if args.json and raw is not None else text)


def wait_note(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- 账号与机器


def cmd_login(args: argparse.Namespace) -> None:
    token = args.value.strip()
    if not token.startswith(PREFIX):
        raise StudioError(f"这不是视频工作室的令牌（应以 {PREFIX} 开头）")
    me = request(args, "/access", token=token)
    remember(token=token, **({"base_url": args.base_url.rstrip("/")} if args.base_url else {}))
    show(args, f"已连上视频工作室，账号 {me['username']}。令牌已存到 {config_path()}（只有本人可读）。", me)


def cmd_logout(args: argparse.Namespace) -> None:
    kept = read_json(config_path())
    kept.pop("token", None)
    save_config(kept)
    show(args, "已删掉本机存的令牌。")


def cmd_whoami(args: argparse.Namespace) -> None:
    me = request(args, "/access")
    show(args, f"账号 {me['username']}，站点 {base_url(args)}", me)


def cmd_machine(args: argparse.Namespace) -> None:
    machine = request(args, "/video/api/machine")
    words = "开着" if machine.get("online") else f"没开（到 {page(args, 'video')} 右上角点“开机”）"
    show(args, f"GPU 机器：{words}；计算单元余额 {machine.get('balance')}，每小时 {machine.get('rate') or 0}", machine)


# ---------------------------------------------------------------- 1. 单条视频


def snapped(seconds: float) -> float:
    """最接近的、模型训练过的长度（约 5.2–15.1 秒）。"""
    grid = min(14, max(0, round((seconds * FPS - FIRST_FRAMES) / FRAME_GRID)))
    return (FIRST_FRAMES + FRAME_GRID * grid) / FPS


def cmd_video(args: argparse.Namespace) -> None:
    online(args)
    seconds, none = snapped(args.seconds), {"first_frame": "", "last_frame": ""}
    prompt = args.idea
    if not args.as_prompt:
        wait_note("请模型把想法写成视频提示词（约 20 秒）…")
        prompt = request(args, "/video/api/expand", {"idea": args.idea, "seconds": seconds, **none}, timeout=180)["prompt"]
    form = {"prompt": prompt, "idea": args.idea, "seconds": seconds, "gear": args.gear, "steps": args.steps,
            "seed": args.seed, "aspect": args.aspect, **none}
    run = request(args, "/video/api/run", form, timeout=120)["job"]["run"]
    wait_note(f"开始生成 {run}（{seconds:.1f} 秒）…")
    finish_video(args, run)


def run_state(args: argparse.Namespace, run: str) -> dict[str, Any]:
    found = next((item for item in request(args, "/video/api/history")["runs"] if item.get("run") == run), None)
    if not found:
        raise StudioError(f"没有这条视频：{run}")
    return found


def finish_video(args: argparse.Namespace, run: str) -> None:
    """等它做完（最多 --wait 分钟）再取回本机；没等到就说怎么接着取。"""
    deadline = time.time() + args.wait * 60
    while True:
        item = run_state(args, run)
        if item["state"] == "done":
            path = download(args, f"/video/runs/{run}/video.mp4", f"{run}.mp4")
            show(args, f"视频做好了：{path}\n页面上也能看：{page(args, 'video')}", {**item, "file": str(path)})
            return
        if item["state"] == "failed":
            raise StudioError(f"这条视频没做成（{run}），到 {page(args, 'video')} 看原因")
        if time.time() > deadline:
            show(args, f"还在生成（{run}）。稍后运行：video-status {run}", item)
            return
        time.sleep(10)


def cmd_video_status(args: argparse.Namespace) -> None:
    args.wait = 0 if args.wait is None else args.wait
    finish_video(args, args.run)


# ---------------------------------------------------------------- 2. 视频聊天


def current_avatar() -> dict[str, Any]:
    kept = read_json(config_path())
    if not kept.get("avatar"):
        raise StudioError("还没有聊天形象：先运行 avatar <照片> 或 use <以前的形象>")
    return kept


def keep_avatar(args: argparse.Namespace, avatar: dict[str, Any]) -> dict[str, Any]:
    """记下当前形象和它的人设（人设跟着服务器上这张图的记录走）。"""
    record = request(args, "/live/api/talk", {"name": avatar["name"]})
    remember(avatar=avatar, persona=record.get("persona") or "")
    return record


def described(avatar: dict[str, Any], persona: str) -> str:
    who = f"认出是 {avatar['who']}，按这个人的身份说话" if avatar.get("who") else "普通人，按性别配声音"
    return f"形象就绪：{avatar.get('subject')}；{who}（{avatar.get('voice')}）" + (f"\n人设：{persona[:120]}" if persona else "")


def cmd_avatar(args: argparse.Namespace) -> None:
    picture = Path(args.image).expanduser()
    if not picture.is_file():
        raise StudioError(f"找不到这张图片：{picture}")
    online(args)
    wait_note("上传形象、看图、做待机动画（第一次约半分钟到一分钟）…")
    image = "data:image/*;base64," + base64.b64encode(picture.read_bytes()).decode()
    avatar = request(args, "/live/api/avatar", {"image": image}, timeout=600)
    if args.who:
        avatar = request(args, "/live/api/who", {"avatar": avatar, "who": args.who}, timeout=180)["avatar"]
    record = keep_avatar(args, avatar)
    show(args, described(avatar, record.get("persona") or ""), avatar)


def cmd_who(args: argparse.Namespace) -> None:
    made = request(args, "/live/api/who", {"avatar": current_avatar()["avatar"], "who": args.name}, timeout=180)
    record = keep_avatar(args, made["avatar"])
    show(args, described(made["avatar"], record.get("persona") or ""), made)


def cmd_talks(args: argparse.Namespace) -> None:
    talks = request(args, "/live/api/talks", {})["talks"]
    lines = [f"{t['name']}  {t.get('subject', '')}  聊过 {t.get('turns', 0)} 句" for t in talks]
    show(args, "\n".join(lines) or "还没有聊过的形象", talks)


def cmd_use(args: argparse.Namespace) -> None:
    record = request(args, "/live/api/talk", {"name": args.name})
    remember(avatar=record["avatar"], persona=record.get("persona") or "")
    show(args, described(record["avatar"], record.get("persona") or ""), record)


def cmd_chat(args: argparse.Namespace) -> None:
    kept = current_avatar()
    form = {"avatar": kept["avatar"], "text": args.text, "persona": kept.get("persona") or "", "steps": args.steps}
    if args.act:
        form["mode"] = "act"
    turn = request(args, "/live/api/say", form, timeout=330)
    files = [download(args, f"/live/{turn['clip']}", Path(turn["clip"]).name)]
    while turn.get("more"):
        turn = request(args, "/live/api/more", {"token": turn["more"]}, timeout=330)
        files.append(download(args, f"/live/{turn['clip']}", Path(turn["clip"]).name))
    listed = "\n".join(f"  第 {n} 段：{path}" for n, path in enumerate(files, 1))
    show(args, f"回答：{turn['reply']}\n说话的视频（按顺序播）：\n{listed}",
         {"reply": turn["reply"], "files": [str(path) for path in files]})


# ---------------------------------------------------------------- 3、5. 长视频与无限游戏


def cmd_story(args: argparse.Namespace) -> None:
    online(args)
    form = {"idea": args.text, "kind": args.kind, "seconds": args.seconds, "size": args.size, "steps": args.steps,
            "shape": args.shape, "narrate": args.narrate, "speech": args.speech or ""}
    if args.kind == "long" and args.faithful:
        form["faithful"] = args.faithful
    story = request(args, "/long/api/start", form, timeout=180)["story"]
    tab = "game" if args.kind == "game" else "long"
    after = ("页面开着，它就一直往下演；关掉页面 25 秒后暂停，30 分钟没人看就停。" if args.kind == "game"
             else "边做边播；做完后可以 download 取整片。")
    show(args, f"开始了（{story['id']}）。打开 {page(args, tab)} 就自动连续播放。{after}", story)


def current(args: argparse.Namespace) -> dict[str, Any]:
    query = urllib.parse.urlencode({"kind": args.kind})
    story = request(args, f"/long/api/state?{query}").get("story")
    if not story:
        raise StudioError("还没有在做的片子")
    return story


def cmd_status(args: argparse.Namespace) -> None:
    story = current(args)
    segments = story.get("segments") or []
    ready = sum(segment.get("state") == "ready" for segment in segments) + story.get("first", 0)
    flags = [word for key, word in (("paused", "没人看，暂停中"), ("review", "等用户在页面上确认形象"),
                                    ("choose", "等用户在页面上选要画的人物")) if story.get(key)]
    text = (f"{story.get('title') or story['id']}：{STATES.get(story['state'], story['state'])}，"
            f"已做好 {ready} 段（每段约 5 秒）" + (f"；{'，'.join(flags)}" if flags else ""))
    show(args, text + f"\n页面：{page(args, 'game' if args.kind == 'game' else 'long')}", story)


def cmd_insert(args: argparse.Namespace) -> None:
    request(args, "/long/api/insert", {"text": args.text})
    show(args, "剧情已插进去，大约半分钟后演到（页面要开着，无限游戏才会往下演）。")


def cmd_stop(args: argparse.Namespace) -> None:
    request(args, "/long/api/stop", {"kind": args.kind})
    show(args, "做完正在生成的这一段就停。")


def cmd_stories(args: argparse.Namespace) -> None:
    query = urllib.parse.urlencode({"kind": args.kind})
    stories = request(args, f"/long/api/history?{query}")["stories"]
    lines = [f"{s['id']}  {s.get('title') or s.get('idea', '')[:30]}  {STATES.get(s.get('state'), s.get('state'))}  "
             f"{s.get('count', 0)} 段" for s in stories[:20]]
    show(args, "\n".join(lines) or "还没有片子", stories)


def cmd_download(args: argparse.Namespace) -> None:
    story_id = args.id or current(args)["id"]
    wait_note("合并已做好的各段…")
    path = download(args, f"/long/clips/{story_id}/full.mp4", f"{story_id}.mp4")
    show(args, f"整片（已做好的部分）：{path}", {"id": story_id, "file": str(path)})


# ---------------------------------------------------------------- 命令行


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="studio.py", description="视频工作室（xhs）：生成视频、视频聊天、长视频、无限游戏")
    top.add_argument("--base-url", help="站点地址，例如 https://www.bcv.one/xhs")
    top.add_argument("--token", help="访问令牌（一般用 login 存好，不用每次给）")
    top.add_argument("--out", default=str(OUT), help=f"视频存到哪里（默认 {OUT}）")
    top.add_argument("--json", action="store_true", help="输出服务器原样的回复")
    sub = top.add_subparsers(dest="command", required=True)

    def add(name: str, run, text: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name, help=text, description=text)
        command.set_defaults(run=run)
        return command

    add("login", cmd_login, "存好令牌（用户在视频工作室页面点“AI 助手”生成）").add_argument("value")
    add("logout", cmd_logout, "删掉本机存的令牌")
    add("whoami", cmd_whoami, "看连的是哪个账号")
    add("machine", cmd_machine, "看 GPU 机器开没开（开关机只能在网页上点）")

    video = add("video", cmd_video, "1. 生成一条视频（约 5–15 秒），做完下载到本机")
    video.add_argument("idea", help="想拍什么，一句话就行")
    video.add_argument("--seconds", type=float, default=5.2, help="长度，取最接近的 5.2–15.1 秒（默认 5.2）")
    video.add_argument("--gear", default="0.4", choices=["0.2", "0.3", "0.4", "0.5", "1.0"], help="清晰度档（默认 0.4）")
    video.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"])
    video.add_argument("--steps", type=int, default=6, choices=range(4, 9), metavar="4-8")
    video.add_argument("--seed", type=int, default=42)
    video.add_argument("--as-prompt", action="store_true", help="给的就是写好的提示词，不再让模型扩写")
    video.add_argument("--wait", type=float, default=8, help="最多等几分钟（默认 8；等不到就用 video-status 接着取）")
    status = add("video-status", cmd_video_status, "看一条视频做好没有，做好就下载")
    status.add_argument("run")
    status.add_argument("--wait", type=float, help="最多再等几分钟（默认不等）")

    avatar = add("avatar", cmd_avatar, "2. 换聊天形象：一张人物照片")
    avatar.add_argument("image")
    avatar.add_argument("--who", help="按某位名人的身份和人设来聊，例如“马斯克”")
    add("who", cmd_who, "让当前形象按某位名人说话；给空字符串回到普通人").add_argument("name")
    add("talks", cmd_talks, "以前聊过的形象")
    add("use", cmd_use, "换回以前聊过的形象（talks 里的名字）").add_argument("name")
    chat = add("chat", cmd_chat, "跟当前形象说一句话，回答是几段说话的视频")
    chat.add_argument("text")
    chat.add_argument("--act", action="store_true", help="说话时带动作")
    chat.add_argument("--steps", type=int, default=3, choices=range(2, 7), metavar="2-6")

    for kind, text in (("long", "3. 用一段故事拍多段长视频"), ("game", "5. 用一段故事开一局无限游戏")):
        story = add("story" if kind == "long" else "game", cmd_story, text)
        story.set_defaults(kind=kind)
        story.add_argument("text", help="故事或开局")
        story.add_argument("--seconds", type=int, default=0, choices=[0, 30, 60, 120],
                           help="大约多长；0 = 按内容定（默认）" if kind == "long" else argparse.SUPPRESS)
        story.add_argument("--size", default="448x256",
                           choices=["448x256", "640x352", "736x416", "864x480", "960x544", "1344x768"])
        story.add_argument("--steps", type=int, default=4, choices=[3, 4, 6])
        story.add_argument("--shape", default="16:9", choices=["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"])
        story.add_argument("--narrate", action="store_true", help="加旁白")
        story.add_argument("--speech", choices=["zh", "en"], help="台词用什么语言（默认跟故事）")
        if kind == "long":
            story.add_argument("--faithful", choices=["text", "fuller", "full"],
                               help="照原文拍：text 不加戏、fuller 略作展开、full 正常展开（默认把故事当点子自由发挥）")

    for name, run, text in (("status", cmd_status, "看正在做的长视频 / 无限游戏到哪了"),
                            ("stop", cmd_stop, "停下正在做的长视频 / 无限游戏"),
                            ("stories", cmd_stories, "以前做过的长视频 / 无限游戏"),
                            ("download", cmd_download, "把一部长视频已做好的部分合成整片下载到本机")):
        command = add(name, run, text)
        command.add_argument("--kind", default="long", choices=["long", "game"])
        if name == "download":
            command.add_argument("id", nargs="?", help="片子的编号（默认正在做的那部）")
    add("insert", cmd_insert, "给正在玩的无限游戏插一段剧情").add_argument("text")
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.run(args)
    except StudioError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
