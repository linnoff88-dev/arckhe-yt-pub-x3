ï»¿# yt-pub-x3

[![yt-pub-x3](guia/assets/banner.jpg)](https://linnoff88-dev.github.io/arckhe-/guia/)

**ê°Å¸â¡Â§ê°Å¸â¡Â· [PortuguêÂªs](README.md) êÂ· ê°Å¸â¡Âºê°Å¸â¡Â¸ [English](README.en.md) êÂ· ê°Å¸â¡Âªê°Å¸â¡Â¸ [EspaêÂ±ol](README.es.md)**

## O que êÂ©

O yt-pub-x3 êÂ© uma fila êÂºnica de publicaêÂ§êÂ£o para quem tem vêÂ¡rios canais. Sua automaêÂ§êÂ£o entrega um vêÂ­deo, uma foto ou um carrossel, e ele publica no YouTube e agenda nas redes pelo Metricool, nos horêÂ¡rios de cada canal. TambêÂ©m corta lives em clipes para o YouTube. Um painel mostra, vêÂ­deo por vêÂ­deo, o que saiu, o que espera e o que precisa de vocêÂª. Se um destino falhar, o outro continua. Roda num computador sempre ligado e pede alguêÂ©m têÂ©cnico ou uma IA de programaêÂ§êÂ£o.

## ê°Å¸ââ Guia de uso

Guia completo: **https://linnoff88-dev.github.io/arckhe-/guia/**

## PeêÂ§a para a sua IA analisar

```text
Leia o projeto yt-pub-x3 em https://github.com/linnoff88-dev/yt-pub-x3 (o README explica tudo, inclusive a instalaêÂ§êÂ£o).
Depois olhe como eu publico hoje e me responda em portuguêÂªs simples:
1. Quais canais e redes eu tenho, e onde uma falha hoje derruba mais de um destino?
2. O que o yt-pub-x3 resolveria para mim, e o que ele nêÂ£o resolve?
3. O que preciso ter pronto (contas, logins, Metricool) e qual canal seria o melhor teste?
NêÂ£o instale, nêÂ£o mude e nêÂ£o publique nada. Mostre o plano, comece em simulaêÂ§êÂ£o e espere eu dizer sim.
```

**Estado:** v0.1.0, em teste. Passa nos testes com publicadores falsos, mas ainda nêÂ£o publicou em canal real. Os canais nascem desligados e, sem `X3_PUBLICAR=1`, tudo êÂ© simulaêÂ§êÂ£o.

**Para quem êÂ©:** quem jêÂ¡ opera canais com automaêÂ§êÂµes e tem alguêÂ©m têÂ©cnico ou uma IA de cêÂ³digo. Foi feito para a operaêÂ§êÂ£o ARCKHÉ e precisa de adaptaêÂ§êÂ£o em outra mêÂ¡quina. Se vocêÂª agenda posts êÂ  mêÂ£o no Metricool, provavelmente nêÂ£o precisa dele.

---

## InstalaêÂ§êÂ£o têÂ©cnica

Precisa de Linux, Python 3 com `PyYAML` e `cryptography`, `ffmpeg`/`ffprobe`, e `gh` para hospedar mêÂ­dia do Metricool.

```bash
git clone https://github.com/linnoff88-dev/yt-pub-x3 && cd yt-pub-x3
pip install -r requirements.txt
python3 -m unittest tests/test_x3.py
cp canais/_exemplo.yaml canais/meucanal.yaml   # ajuste os dados do canal
python3 hub.py --once                          # simulaêÂ§êÂ£o
python3 dashboard/server.py 8230               # http://127.0.0.1:8230
```

`config_dir` guarda o login do YouTube: `.env` com `CLIENT_ID`, `CLIENT_SECRET` e `API_KEY`, `credentials.enc` e `.encryption_key`. Para criar: `GWS_CONFIG_DIR=<config_dir> scripts/yt-auth`. `importar-canais` sêÂ³ serve para quem jêÂ¡ tem instêÂ¢ncias `yt-pub-livesN`.

**Conector do Metricool.** O publicador êÂ© um programa externo, indicado por `X3_METRICOOL_VIDEO` (padrêÂ£o: `~/projetos/metricool-linnoff88-dev/publicar.sh`). Ele recebe `<video> <legenda.txt> <repo-pêÂºblico>` e as variêÂ¡veis `MARCA` e `REDES`. SaêÂ­das: `0` agendado (imprima `Metricool: <url>`), `2` formato recusado, outra = tentar de novo. Precisa ser idempotente. A mêÂ­dia fica pêÂºblica no repo de `X3_METRICOOL_REPO`, para o Metricool poder baixar: use um repo seu e leve isso em conta em conteêÂºdo inêÂ©dito. Foto e carrossel usam `scripts/metricool-imagens.sh`, que espera a mesma estrutura em `X3_METRICOOL_DIR`.

**Cortes.** `scripts/yt-clip` usa `yt-dlp`, `ffmpeg`, o motor de `scripts/ia.yaml` e `prompt_cortes.txt` no `config_dir`. Usa `fila-vaga` sêÂ³ se ele existir.

**Capa e textos por IA** usam o `yt-pubx` local (`scripts/ia_ytpubx.py`). Sem ele, informe os textos no `post.json` e coloque `capa.jpg` na pasta. Os avisos usam `avisa-v3.sh` na mêÂ¡quina ARCKHÉ; em outra, ficam no log e no painel.

**ServiêÂ§os** de exemplo em `systemd/`. Eles nêÂ£o ligam a publicaêÂ§êÂ£o real.

## O processo, do inêÂ­cio ao fim

| # | Passo | Comando | Quem faz |
|---|---|---|---|
| 1 | Gerar os canais a partir dos sistemas atuais, todos desligados | `./yt-pub-x3 importar-canais` | ê¢Å¡â¢ê¯Â¸Â script |
| 2 | Trazer o histêÂ³rico de lives de quem corta | `./yt-pub-x3 importar-lives lives1` | ê¢Å¡â¢ê¯Â¸Â script |
| 3 | Escolher o canal do piloto e pêÂ´r `ativo: true` no YAML | editar `canais/livesN.yaml` | ê°Å¸Â§Â  sessêÂ£o com o Nei |
| 4 | Subir hub e painel | `python3 hub.py` êÂ· `python3 dashboard/server.py 8230` | ê¢Å¡â¢ê¯Â¸Â serviêÂ§o |
| 5 | Entregar conteêÂºdo | pasta em `entrada/<canal>/` ou `./yt-pub-x3 enviar <pasta> --canal livesN` | ê¢Å¡â¢ê¯Â¸Â produtor |
| 6 | Validar: formato, repetiêÂ§êÂ£o e textos | automêÂ¡tico; `contexto` usa o Codex | ê¢Å¡â¢ê¯Â¸Â hub êÂ· ê°Å¸Â¤â Codex |
| 7 | Cortar lives em clipes, nos canais com cortes ligados | automêÂ¡tico | ê¢Å¡â¢ê¯Â¸Â hub êÂ· ê°Å¸Â¤â IA de `scripts/ia.yaml` |
| 8 | Publicar 1 item por horêÂ¡rio, separado por destino | automêÂ¡tico | ê¢Å¡â¢ê¯Â¸Â hub |
| 9 | Aplicar capa pelo Codex quando permitido | automêÂ¡tico | ê¢Å¡â¢ê¯Â¸Â hub êÂ· ê°Å¸Â¤â Codex |
| 10 | Acompanhar, pausar, pular ou reenviar | `http://127.0.0.1:8230` | ê°Å¸Â§Â  Nei |

## O que colocar na pasta

```
entrada/lives4/2026-11-18-enxame/
  video.mp4      ou foto.jpg, ou 01.jpg, 02.jpg...
  post.json
  capa.jpg       opcional, vêÂ­deo normal
  legenda.srt    opcional, vêÂ­deo
  pronto         arquivo vazio, criado por êÂºltimo
```

```json
{
  "tipo": "video",
  "titulo": "TêÂ­tulo no YouTube",
  "descricao": "DescriêÂ§êÂ£o no YouTube",
  "texto_rs": "Texto das redes",
  "tags": ["ia"],
  "destinos": ["youtube", "rs"],
  "quando": "fila"
}
```

`tipo`: `video`, `foto` ou `carrossel`. `quando`: `fila`, `agora` ou `AAAA-MM-DD HH:MM`. Sem os textos, informe `contexto` e o Codex escreve. Foto e carrossel vêÂ£o sêÂ³ êÂ s redes e nêÂ£o gastam horêÂ¡rio do YouTube.

## O que acontece quando algo falha

| SituaêÂ§êÂ£o | Resultado |
|---|---|
| Login do YouTube caiu | YouTube do canal pausa por 1 h; o vêÂ­deo fica na fila; redes seguem |
| Limite ou cota do YouTube | Igual, com pausa de 6 h |
| Rede temporêÂ¡ria | AtêÂ© 3 tentativas, depois erro |
| Queda durante o upload | Vai para **Conferir**; nunca reenvia sozinho |
| VêÂ­deo 16:9 ou longo demais para as redes | Redes ficam como **Ignorado** |
| Arquivo repetido ou pasta invêÂ¡lida | **Recusado**, com o motivo, em `data/recusados/` |
| Codex nêÂ£o fez a capa | VêÂ­deo sai sem capa e o painel marca pendente |

## Testes

```bash
python3 -m unittest tests/test_x3.py
```

## SeguranêÂ§a

O painel sêÂ³ escuta em `127.0.0.1`, nêÂ£o tem senha padrêÂ£o nem rota que execute comandos, e aêÂ§êÂµes exigem um cabeêÂ§alho prêÂ³prio. Logins, `canais/*.yaml`, `data/` e `entrada/` ficam fora do git.

Conectores: Metricool para vêÂ­deo e imagem. Blotato e Upload-Post ainda nêÂ£o têÂªm conector ativo.

---

Projeto  - ARCKHÉe