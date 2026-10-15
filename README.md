# 视频工作室 · AI 助手技能

在 Claude 桌面版 / Claude Code、OpenClaw、WorkBuddy 等 AI 助手的聊天框里用视频工作室（www.bcv.one/xhs）：

- 生成一条视频（5–15 秒），做完下载到本机；
- 和照片里的人视频聊天（也可以让他按某位名人的身份说话）；
- 把一段故事拍成多段长视频，打开页面就边做边连续播；
- 用一段故事开一局无限游戏，页面开着就一直演下去，聊天里还能插入剧情。

只给视频工作室白名单里的账号用：没有令牌什么都做不了。本仓库是私有的，装的那台机器要能访问它（先 `gh auth login`）。

## 安装

| 用在哪 | 怎么装 |
|---|---|
| Claude Code（桌面版的 Code 也是它） | `/plugin marketplace add hypergraphdev/xhs-skills`，再 `/plugin install xhs-video-studio@xhs-skills` |
| 支持 Agent Skills 的大多数助手 | `npx skills add hypergraphdev/xhs-skills` |
| 手动（OpenClaw、WorkBuddy 等） | `git clone https://github.com/hypergraphdev/xhs-skills`，把里面的 `skills/xhs-video-studio` 放进助手的技能目录（Claude 是 `~/.claude/skills/`，OpenClaw 一般是 `~/.openclaw/skills/`） |

更新：插件方式用 `/plugin marketplace update xhs-skills`；手动方式在克隆的目录里 `git pull`。

## 第一次用

1. 打开视频工作室 <https://www.bcv.one/xhs/h3>，右上角点 **AI 助手** → 生成令牌 → 复制。
2. 在聊天框里把令牌发给助手，它会存好（`~/.config/xhs-video-studio/config.json`，只有本人可读），以后不用再给。
3. 要生成东西时先在网页上**开机**：技能不能开关机，机器没开时它会给出网页链接。

## 它运行什么、发送什么、保存什么

- **运行**：`skills/xhs-video-studio/scripts/studio.py`，只用 Python 自带的库（3.8+），不装任何包。
- **联网**：只访问 `https://www.bcv.one/xhs/api/h3/`（或你用 `--base-url`、`XHS_STUDIO_URL` 指定的站点）。
- **发送**：令牌（在请求头里）、你让它拍的想法和故事、聊天说的话；`avatar` 会上传你指定的那张照片。
- **本机保存**：令牌、站点地址、当前聊天形象存在上面那个配置文件里，`logout` 删掉令牌；视频存到 `~/Downloads/xhs-studio/`（`--out` 可改）。
- **令牌**：在视频工作室网页上生成和作废；它不能开关机，也不能生成、作废令牌。
