# yt-pub-x3 — especificaçêo (18/11/2026)

Status: **projeto criado, código ainda nêo escrito.** Decisões tomadas com o Nei em 17–18/11/2026.
Prévia do painel: https://claude.ai/artifact/NTLsc9fXMWi7hZJt8cE35s (fonte em `docs/previa-painel.dc.html`).

## O que é

Publicador enxuto: **todo conteúdo entra numa fila por canal; um único hub publica no YouTube e nas redes sociais (RS)**, com status separado por destino e controle por canal e por vídeo. Também corta lives em clipes.

Por que existe: em 17/11, 26 Shorts agendados dos lives nêo foram ao Metricool. O gancho do yt-pubx só dispara em upload público imediato e depois do upload, entêo um bloqueio do YouTube também derruba o Metricool.

## Decisões do Nei

- Nome `yt-pub-x3`, projeto novo e enxuto; **um hub para todos os canais**, sem cópia por canal.
- Menu por canal: **Import YT**, **RS** (Metricool, Blotato, Upload-Post…), **Cortes**.
- Se o YouTube falhar (autenticaçêo/limite), as redes saem igual.
- Horário vem da configuraçêo do canal.
- Painel no estilo do Master Dashboard atual: cartêo completo por canal, com links para o canal no YouTube, Metricool, Instagram e TikTok. Tabela: Lives, Clips, Imports, yt-pubx, Metricool. Sem a linha de captaçêo do TikTok.
- O x3 **implementa os cortes de lives em clipes**. Hoje só o lives1 está ativo. A captaçêo de vídeos do TikTok fica de fora (confirmar: postar no TikTok pelo Metricool continua).
- Capa pelo Codex só onde é permitido; Short nêo leva. Codex falhou = publica sem capa, avisa no bot, sem flux.
- Pedido final do Nei: **publicar o projeto no portal e no ARCKHÉ.VIBE**, quando estiver pronto.

## Entrada

`entrada/<canal>/<pasta-da-publicacao>/`: `video.mp4` (ou `foto.jpg`, ou `01.jpg`, `02.jpg`…), `post.json`, `capa.jpg` (opcional, vídeo normal), `legenda.srt` (opcional), e `pronto` (vazio, criado por último). Também `yt-pub-x3 enviar <pasta> --canal livesN`. `yt-pubx publicar` passará a depositar aqui, canal por canal, no piloto.

`post.json`: `tipo` (video|foto|carrossel), `titulo`, `descricao`, `texto_rs`, `tags`, `destinos` (["youtube","rs"]), `quando` (fila|agora|"AAAA-MM-DD HH:MM"), `contexto` (Codex escreve o que faltar).

Mínimo: arquivo + `tipo`; vídeo com `titulo`+`descricao` ou `contexto`; foto/carrossel com `texto_rs` ou `contexto`.

Automático: foto/carrossel só RS, sem gastar horário do YouTube; links saem do texto RS; 16:9 ou longo demais = RS "ignorado"; arquivo repetido recusado (sha256, conferindo também `~/.local/share/yt-pubx/historico.jsonl`); pasta inválida = "Recusado" com motivo.

## Núcleo

Partir de `~/projetos/yt-pub-livesx2` (`hub.py`, `lib/db.py`, `runner.py`, `canais.py`, `creds.py`, `youtube.py`, `entrada.py`), que nunca rodou em produçêo. **Nêo herdar:**

1. Falha de OAuth ou 403 (`uploadLimitExceeded`, `quotaExceeded`) consumindo vídeo. Pausa o YouTube daquele canal com `retomar_em` (auth ~1 h, cota ~6 h); o vídeo fica aguardando, sem contar tentativa.
2. `release_stuck_jobs` recolocando `publicando` na fila (pode duplicar upload). Ao iniciar o hub, `enviando` vira **conferir**, sem reenvio automático.
3. Tick serial. YouTube, RS e cortes rodam em trabalhadores separados; o Metricool pode esperar até 1 h pela trava da marca.

Tabelas: `itens` (canal, tipo, arquivos, textos, sha256, origem, quando; único por canal+sha256), `entregas` (item, destino, status aguardando|pausado|enviando|feito|erro|ignorado|conferir, tentativas, erro, ref, url), `canal_destino` (ligado, pausa, motivo, retomar_em), `lives`, `jobs` (chave única).

Nêo mover o arquivo enquanto algum destino estiver pendente, com erro ou pausado. **Simulaçêo é o padrêo:** publicar de verdade exige `X3_PUBLICAR=1` e canal `ativo: true`.

`canais/livesN.yaml` (fora do git, todos `ativo: false`): `destino_id`, `destino_nome`, `url`, `origem_id`, `config_dir` e `lives_dir` apontando para `yt-pub-livesN`, `youtube{ligado,horarios,privacy}` (usar `import_pub_horarios`, nêo `pub_horarios`), `rs{provedor,ligado,marca,blog_id,redes,perfis}`, `cortes{ligado,horarios,max_por_dia}`. Sêo 19 canais: 1–12, 22–26, 31, 32.

Marcas: lives3/31 FTD 7908265 · lives4/12 ARCKHÉ.tds 7797870 · lives7/8 VIBE 8026101 (só TikTok) · lives10 eventosextremos 7800440 · lives2/24 Radar 7999284 · lives11 ARCKHÉfuturos 7577386 (outra conta, `metricool-pub2`) · lives1 fora do Metricool. Só rs ligado por padrêo onde o publicador atual serve; lives10, lives11 e Radar têm fluxos próprios: decidir no piloto.

## Conectores

- **Metricool, vídeo:** subprocesso de `~/projetos/metricool-linnoff88-dev/publicar.sh <video> <legenda> linnoff88-dev/yt-pubx` com `MARCA`, `REDES` (como `yt-pubx/hooks/metricool.py`). Mantém trava por marca, 1 h, `sem_links`, recibo. Reusar o mesmo arquivo de legenda na repetiçêo (o recibo depende dele). Saída 0 = feito; 2 = formato/ignorado; 1 = tentar de novo. Conferir antes: vertical, ≤180 s com Instagram, ≤600 s só TikTok.
- **Metricool, foto/carrossel:** `publicar.sh` só aceita vídeo. Base: `~/projetos/carrossel-ARCKHÉ/scripts/publicar.sh` (release pública + `createScheduledPost`, `instagramData.type=POST`), mas ele exige `01-capa.png`, publica rascunho sem `AO_VIVO=1` e usa `claude -p`; adaptar sem mudar o original.
- **Blotato e Upload-Post:** só desenho/desligados. **Nêo chamar sem autorizaçêo e chave.**

## Cortes

Copiar de `~/projetos/yt-pub-livesx/scripts` (commit de 15/11): `yt-clip`, `analise_cortes.py`, `ia_motor.py`, `ia.yaml`. Nêo mudar motor nem modelo. `yt-clip --ai <modo> -- <video_id>` com `LIVES_DIR` e `GWS_CONFIG_DIR`; lê `prompt_cortes.txt` do config; gera `<lives_dir>/<id>/clips_manifest.json` (file, title, description, tags, duration) e `topics.json`. Com clipes = cortada; `topics.json` sem tópicos = sem_topicos. Rodar por `~/projetos/wifi/scripts/fila-vaga`. Importar o histórico do lives1 (303 lives cortadas) antes de ligar. lives1: `corte_horarios` 01:35, 02:35, 03:35, 04:35; máximo 1 por dia; `ai_mode` claude-api (conferir no `ia.yaml`). Na migraçêo, só um sistema corta por vez.

## Textos e capas

Reaproveitar a lógica de `gerar_metadados` e `arte_codex`/`gerar_thumb` do `~/projetos/yt-pubx/yt-pubx`, **sem a `arte_reserva`**. Capa roda depois do upload, em job separado; falha = capa pendente + aviso.

## Painel

`dashboard/`, porta própria só em 127.0.0.1, **sem senha padrêo, sem rota de execuçêo ou reinício**. Dados de x3 + leitura somente-leitura de `yt-pub-livesN/data/lives.db`, `historico.jsonl` do yt-pubx e recibos em `metricool-linnoff88-dev/estado`. Ações por entrega: pausar, retomar, pular, reenviar; por canal: ligar/desligar cada destino. POST exige cabeçalho próprio.

## Testes = critério de pronto (só publicadores falsos e pastas temporárias)

YouTube com auth caída: RS sai, vídeo fica na fila, YouTube do canal pausa · 403 de cota: igual · RS falha: YouTube segue · queda no meio do upload: vai para conferir, sem reenvio · pasta sem `pronto`: ignorada · arquivo repetido: recusado · foto/carrossel: nêo gasta horário do YouTube · 16:9: RS ignorado · simulaçêo nêo publica · corte gera clipes na fila e nêo recorta live já importada.

## Limites desta etapa

Nêo mexer em yt-pubx, `~/.config/yt-pubx/config.json`, agendadores antigos, systemd nem na senha do Master. Piloto (lives12, depois lives7, lives31, lives3, lives4) só com OK do Nei. Em aberto: horários dos 5 canais que nêo cabem (lives3 54/28, lives4 52/35, lives11 39/21, lives8 27/14, lives24 26/21); os 27 vídeos fora do Metricool.

## Publicaçêo do projeto (depois de pronto e testado)

Repo `linnoff88-dev/yt-pub-x3`, guia em `guia/` PT/EN/ES (skill `projetos-landing-guia`), portal (skill `atualiza-portal`), tópico no **ARCKHÉ.VIBE** (skill `postar-telegram`). Todo guia leva vídeo depois. Conferir que nada de `canais/*.yaml`, `data/`, `entrada/` nem credencial entra no git. Arquivos da casa: README com "O processo, do início ao fim", CLAUDE.md com Self-learning e Lessons, FALHAS.md, versêo semver.
