# yt-pub-x3

[![yt-pub-x3](guia/assets/banner.jpg)](https://inematds.github.io/yt-pub-x3/guia/)

**ðŸ‡§ðŸ‡· [PortuguÃªs](README.md) Â· ðŸ‡ºðŸ‡¸ [English](README.en.md) Â· ðŸ‡ªðŸ‡¸ [EspaÃ±ol](README.es.md)**

## O que Ã©

O yt-pub-x3 Ã© uma fila Ãºnica de publicaÃ§Ã£o para quem tem vÃ¡rios canais. Sua automaÃ§Ã£o entrega um vÃ­deo, uma foto ou um carrossel, e ele publica no YouTube e agenda nas redes pelo Metricool, nos horÃ¡rios de cada canal. TambÃ©m corta lives em clipes para o YouTube. Um painel mostra, vÃ­deo por vÃ­deo, o que saiu, o que espera e o que precisa de vocÃª. Se um destino falhar, o outro continua. Roda num computador sempre ligado e pede alguÃ©m tÃ©cnico ou uma IA de programaÃ§Ã£o.

## ðŸ“– Guia de uso

Guia completo: **https://inematds.github.io/yt-pub-x3/guia/**

## PeÃ§a para a sua IA analisar

```text
Leia o projeto yt-pub-x3 em https://github.com/inematds/yt-pub-x3 (o README explica tudo, inclusive a instalaÃ§Ã£o).
Depois olhe como eu publico hoje e me responda em portuguÃªs simples:
1. Quais canais e redes eu tenho, e onde uma falha hoje derruba mais de um destino?
2. O que o yt-pub-x3 resolveria para mim, e o que ele nÃ£o resolve?
3. O que preciso ter pronto (contas, logins, Metricool) e qual canal seria o melhor teste?
NÃ£o instale, nÃ£o mude e nÃ£o publique nada. Mostre o plano, comece em simulaÃ§Ã£o e espere eu dizer sim.
```

**Estado:** v0.1.0, em teste. Passa nos testes com publicadores falsos, mas ainda nÃ£o publicou em canal real. Os canais nascem desligados e, sem `X3_PUBLICAR=1`, tudo Ã© simulaÃ§Ã£o.

**Para quem Ã©:** quem jÃ¡ opera canais com automaÃ§Ãµes e tem alguÃ©m tÃ©cnico ou uma IA de cÃ³digo. Foi feito para a operaÃ§Ã£o INEMA e precisa de adaptaÃ§Ã£o em outra mÃ¡quina. Se vocÃª agenda posts Ã  mÃ£o no Metricool, provavelmente nÃ£o precisa dele.

---

## InstalaÃ§Ã£o tÃ©cnica

Precisa de Linux, Python 3 com `PyYAML` e `cryptography`, `ffmpeg`/`ffprobe`, e `gh` para hospedar mÃ­dia do Metricool.

```bash
git clone https://github.com/inematds/yt-pub-x3 && cd yt-pub-x3
pip install -r requirements.txt
python3 -m unittest tests/test_x3.py
cp canais/_exemplo.yaml canais/meucanal.yaml   # ajuste os dados do canal
python3 hub.py --once                          # simulaÃ§Ã£o
python3 dashboard/server.py 8230               # http://127.0.0.1:8230
```

`config_dir` guarda o login do YouTube: `.env` com `CLIENT_ID`, `CLIENT_SECRET` e `API_KEY`, `credentials.enc` e `.encryption_key`. Para criar: `GWS_CONFIG_DIR=<config_dir> scripts/yt-auth`. `importar-canais` sÃ³ serve para quem jÃ¡ tem instÃ¢ncias `yt-pub-livesN`.

**Conector do Metricool.** O publicador Ã© um programa externo, indicado por `X3_METRICOOL_VIDEO` (padrÃ£o: `~/projetos/metricool-inematds/publicar.sh`). Ele recebe `<video> <legenda.txt> <repo-pÃºblico>` e as variÃ¡veis `MARCA` e `REDES`. SaÃ­das: `0` agendado (imprima `Metricool: <url>`), `2` formato recusado, outra = tentar de novo. Precisa ser idempotente. A mÃ­dia fica pÃºblica no repo de `X3_METRICOOL_REPO`, para o Metricool poder baixar: use um repo seu e leve isso em conta em conteÃºdo inÃ©dito. Foto e carrossel usam `scripts/metricool-imagens.sh`, que espera a mesma estrutura em `X3_METRICOOL_DIR`.

**Cortes.** `scripts/yt-clip` usa `yt-dlp`, `ffmpeg`, o motor de `scripts/ia.yaml` e `prompt_cortes.txt` no `config_dir`. Usa `fila-vaga` sÃ³ se ele existir.

**Capa e textos por IA** usam o `yt-pubx` local (`scripts/ia_ytpubx.py`). Sem ele, informe os textos no `post.json` e coloque `capa.jpg` na pasta. Os avisos usam `avisa-v3.sh` na mÃ¡quina INEMA; em outra, ficam no log e no painel.

**ServiÃ§os** de exemplo em `systemd/`. Eles nÃ£o ligam a publicaÃ§Ã£o real.

## O processo, do inÃ­cio ao fim

| # | Passo | Comando | Quem faz |
|---|---|---|---|
| 1 | Gerar os canais a partir dos sistemas atuais, todos desligados | `./yt-pub-x3 importar-canais` | âš™ï¸ script |
| 2 | Trazer o histÃ³rico de lives de quem corta | `./yt-pub-x3 importar-lives lives1` | âš™ï¸ script |
| 3 | Escolher o canal do piloto e pÃ´r `ativo: true` no YAML | editar `canais/livesN.yaml` | ðŸ§  sessÃ£o com o Nei |
| 4 | Subir hub e painel | `python3 hub.py` Â· `python3 dashboard/server.py 8230` | âš™ï¸ serviÃ§o |
| 5 | Entregar conteÃºdo | pasta em `entrada/<canal>/` ou `./yt-pub-x3 enviar <pasta> --canal livesN` | âš™ï¸ produtor |
| 6 | Validar: formato, repetiÃ§Ã£o e textos | automÃ¡tico; `contexto` usa o Codex | âš™ï¸ hub Â· ðŸ¤– Codex |
| 7 | Cortar lives em clipes, nos canais com cortes ligados | automÃ¡tico | âš™ï¸ hub Â· ðŸ¤– IA de `scripts/ia.yaml` |
| 8 | Publicar 1 item por horÃ¡rio, separado por destino | automÃ¡tico | âš™ï¸ hub |
| 9 | Aplicar capa pelo Codex quando permitido | automÃ¡tico | âš™ï¸ hub Â· ðŸ¤– Codex |
| 10 | Acompanhar, pausar, pular ou reenviar | `http://127.0.0.1:8230` | ðŸ§  Nei |

## O que colocar na pasta

```
entrada/lives4/2026-11-18-enxame/
  video.mp4      ou foto.jpg, ou 01.jpg, 02.jpg...
  post.json
  capa.jpg       opcional, vÃ­deo normal
  legenda.srt    opcional, vÃ­deo
  pronto         arquivo vazio, criado por Ãºltimo
```

```json
{
  "tipo": "video",
  "titulo": "TÃ­tulo no YouTube",
  "descricao": "DescriÃ§Ã£o no YouTube",
  "texto_rs": "Texto das redes",
  "tags": ["ia"],
  "destinos": ["youtube", "rs"],
  "quando": "fila"
}
```

`tipo`: `video`, `foto` ou `carrossel`. `quando`: `fila`, `agora` ou `AAAA-MM-DD HH:MM`. Sem os textos, informe `contexto` e o Codex escreve. Foto e carrossel vÃ£o sÃ³ Ã s redes e nÃ£o gastam horÃ¡rio do YouTube.

## O que acontece quando algo falha

| SituaÃ§Ã£o | Resultado |
|---|---|
| Login do YouTube caiu | YouTube do canal pausa por 1 h; o vÃ­deo fica na fila; redes seguem |
| Limite ou cota do YouTube | Igual, com pausa de 6 h |
| Rede temporÃ¡ria | AtÃ© 3 tentativas, depois erro |
| Queda durante o upload | Vai para **Conferir**; nunca reenvia sozinho |
| VÃ­deo 16:9 ou longo demais para as redes | Redes ficam como **Ignorado** |
| Arquivo repetido ou pasta invÃ¡lida | **Recusado**, com o motivo, em `data/recusados/` |
| Codex nÃ£o fez a capa | VÃ­deo sai sem capa e o painel marca pendente |

## Testes

```bash
python3 -m unittest tests/test_x3.py
```

## SeguranÃ§a

O painel sÃ³ escuta em `127.0.0.1`, nÃ£o tem senha padrÃ£o nem rota que execute comandos, e aÃ§Ãµes exigem um cabeÃ§alho prÃ³prio. Logins, `canais/*.yaml`, `data/` e `entrada/` ficam fora do git.

Conectores: Metricool para vÃ­deo e imagem. Blotato e Upload-Post ainda nÃ£o tÃªm conector ativo.

---

Projeto adaptado da comunidade INEMA TDS - Marca Arckhe