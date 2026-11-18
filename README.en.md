# yt-pub-x3

[![yt-pub-x3](guia/assets/banner-en.jpg)](https://inematds.github.io/yt-pub-x3/guia/en/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## What it is

yt-pub-x3 is a single publishing queue for people with multiple channels. Your automation delivers a video, photo, or carousel, and it publishes to YouTube and schedules posts on social networks through Metricool, at each channel’s scheduled times. It also cuts livestreams into YouTube clips. A dashboard shows, video by video, what has been published, what is waiting, and what needs your attention. If one destination fails, the other keeps going. It runs on a computer that stays on and requires a technical person or a coding AI.

## 📖 User guide

Complete guide: **https://inematds.github.io/yt-pub-x3/guia/en/**

## Ask your AI to analyze it

```text
Read the yt-pub-x3 project at https://github.com/inematds/yt-pub-x3 (the README explains everything, including installation).
Then look at how I publish content today and answer in plain English:
1. Which channels and social networks do I have, and where would a failure today take down more than one destination?
2. What would yt-pub-x3 solve for me, and what would it not solve?
3. What do I need to have ready (accounts, logins, Metricool), and which channel would be the best test?
Do not install, change, or publish anything. Show me the plan, start with a simulation, and wait for me to say yes.
```

**Status:** v0.1.0, in testing. It passes tests with fake publishers, but has not published to a real channel yet. Channels start disabled, and without `X3_PUBLICAR=1`, everything is simulated.

**Who it’s for:** people who already operate channels with automations and have a technical person or coding AI. It was built for INEMA’s operations and needs adapting for another computer. If you schedule posts manually in Metricool, you probably don’t need it.

---

## Technical installation

Requires Linux, Python 3 with `PyYAML` and `cryptography`, `ffmpeg`/`ffprobe`, and `gh` to host Metricool media.

```bash
git clone https://github.com/inematds/yt-pub-x3 && cd yt-pub-x3
pip install -r requirements.txt
python3 -m unittest tests/test_x3.py
cp canais/_exemplo.yaml canais/meucanal.yaml   # adjust the channel details
python3 hub.py --once                          # simulation
python3 dashboard/server.py 8230               # http://127.0.0.1:8230
```

`config_dir` stores the YouTube login: `.env` with `CLIENT_ID`, `CLIENT_SECRET` and `API_KEY`, `credentials.enc` and `.encryption_key`. To create it: `GWS_CONFIG_DIR=<config_dir> scripts/yt-auth`. `importar-canais` is only for people who already have `yt-pub-livesN` instances.

**Metricool connector.** The publisher is an external program specified by `X3_METRICOOL_VIDEO` (default: `~/projetos/metricool-inematds/publicar.sh`). It receives `<video> <legenda.txt> <repo-público>` and the `MARCA` and `REDES` variables. Outputs: `0` scheduled (print `Metricool: <url>`), `2` format rejected, anything else = retry. It must be idempotent. Media is stored publicly in the `X3_METRICOOL_REPO` repo so Metricool can download it: use your own repo and keep this in mind for unreleased content. Photos and carousels use `scripts/metricool-imagens.sh`, which expects the same structure in `X3_METRICOOL_DIR`.

**Clips.** `scripts/yt-clip` uses `yt-dlp`, `ffmpeg`, the engine in `scripts/ia.yaml`, and `prompt_cortes.txt` in `config_dir`. It uses `fila-vaga` only if it exists.

**AI-generated cover images and text** use the local `yt-pubx` (`scripts/ia_ytpubx.py`). Without it, provide the text in `post.json` and put `capa.jpg` in the folder. Notifications use `avisa-v3.sh` on the INEMA computer; on another computer, they appear in the log and dashboard.

**Example services** are in `systemd/`. They do not enable real publishing.

## The process, from start to finish

| # | Step | Command | Who does it |
|---|---|---|---|
| 1 | Generate channels from the current systems, all disabled | `./yt-pub-x3 importar-canais` | ⚙️ script |
| 2 | Import the livestream history for channels that make clips | `./yt-pub-x3 importar-lives lives1` | ⚙️ script |
| 3 | Choose the pilot channel and set `ativo: true` in the YAML | edit `canais/livesN.yaml` | 🧠 session with Nei |
| 4 | Start the hub and dashboard | `python3 hub.py` · `python3 dashboard/server.py 8230` | ⚙️ service |
| 5 | Deliver content | folder in `entrada/<canal>/` or `./yt-pub-x3 enviar <pasta> --canal livesN` | ⚙️ producer |
| 6 | Validate: format, duplicates, and text | automatic; `contexto` uses Codex | ⚙️ hub · 🤖 Codex |
| 7 | Cut livestreams into clips for channels with clips enabled | automatic | ⚙️ hub · 🤖 AI in `scripts/ia.yaml` |
| 8 | Publish 1 item per scheduled time, separately for each destination | automatic | ⚙️ hub |
| 9 | Add a cover image with Codex when allowed | automatic | ⚙️ hub · 🤖 Codex |
| 10 | Monitor, pause, skip, or resend | `http://127.0.0.1:8230` | 🧠 Nei |

## What to put in the folder

```
entrada/lives4/2026-11-18-enxame/
  video.mp4      or foto.jpg, or 01.jpg, 02.jpg...
  post.json
  capa.jpg       optional, regular video
  legenda.srt    optional, video
  pronto         empty file, created last
```

```json
{
  "tipo": "video",
  "titulo": "Title on YouTube",
  "descricao": "Description on YouTube",
  "texto_rs": "Social media text",
  "tags": ["ia"],
  "destinos": ["youtube", "rs"],
  "quando": "fila"
}
```

`tipo`: `video`, `foto`, or `carrossel`. `quando`: `fila`, `agora`, or `AAAA-MM-DD HH:MM`. If the text is missing, provide `contexto` and Codex will write it. Photos and carousels go only to social networks and do not use a YouTube time slot.

## What happens when something fails

| Situation | Result |
|---|---|
| YouTube login expires | The channel’s YouTube publishing pauses for 1 h; the video stays in the queue; social networks continue |
| YouTube limit or quota | Same, with a 6 h pause |
| Temporary social network failure | Up to 3 attempts, then an error |
| Failure during upload | Goes to **Review**; never resends automatically |
| Video is 16:9 or too long for social networks | Social networks are marked **Skipped** |
| Duplicate file or invalid folder | **Rejected**, with the reason, in `data/recusados/` |
| Codex did not create the cover image | Video goes out without a cover image, and the dashboard marks it as pending |

## Tests

```bash
python3 -m unittest tests/test_x3.py
```

## Security

The dashboard listens only on `127.0.0.1`, has no default password or route that executes commands, and actions require a dedicated header. Logins, `canais/*.yaml`, `data/` and `entrada/` stay out of git.

Connectors: Metricool for video and images. Blotato and Upload-Post do not have active connectors yet.
