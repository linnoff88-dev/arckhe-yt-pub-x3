# yt-pub-x3

[![yt-pub-x3](guia/assets/banner-es.jpg)](https://inematds.github.io/yt-pub-x3/guia/es/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## Qué es

yt-pub-x3 es una única cola de publicación para quienes tienen varios canales. Su automatización entrega un video, una foto o un carrusel, y lo publica en YouTube y programa su publicación en las redes mediante Metricool, en los horarios de cada canal. También recorta transmisiones en vivo para crear clips para YouTube. Un panel muestra, video por video, qué se publicó, qué está en espera y qué requiere tu atención. Si falla un destino, el otro continúa. Funciona en una computadora siempre encendida y requiere a una persona técnica o una IA de programación.

## 📖 Guía de uso

Guía completa: **https://inematds.github.io/yt-pub-x3/guia/es/**

## Pídele a tu IA que lo analice

```text
Lee el proyecto yt-pub-x3 en https://github.com/inematds/yt-pub-x3 (el README explica todo, incluida la instalación).
Después, revisa cómo publico actualmente y respóndeme en portugués sencillo:
1. ¿Qué canales y redes tengo, y dónde una falla hace que hoy se caiga más de un destino?
2. ¿Qué resolvería yt-pub-x3 para mí y qué no resolvería?
3. ¿Qué necesito tener listo (cuentas, inicios de sesión, Metricool) y cuál canal sería la mejor prueba?
No instales, no cambies ni publiques nada. Muéstrame el plan, empieza con una simulación y espera a que te diga que sí.
```

**Estado:** v0.1.0, en pruebas. Supera las pruebas con publicadores simulados, pero todavía no ha publicado en un canal real. Los canales se crean desactivados y, sin `X3_PUBLICAR=1`, todo es una simulación.

**Para quién es:** para quienes ya operan canales con automatizaciones y cuentan con alguien técnico o una IA de código. Se creó para la operación de INEMA y requiere adaptación para otra computadora. Si programas publicaciones manualmente en Metricool, probablemente no lo necesitas.

---

## Instalación técnica

Requiere Linux, Python 3 con `PyYAML` y `cryptography`, `ffmpeg`/`ffprobe` y `gh` para alojar medios de Metricool.

```bash
git clone https://github.com/inematds/yt-pub-x3 && cd yt-pub-x3
pip install -r requirements.txt
python3 -m unittest tests/test_x3.py
cp canais/_exemplo.yaml canais/meucanal.yaml   # ajuste os dados do canal
python3 hub.py --once                          # simulação
python3 dashboard/server.py 8230               # http://127.0.0.1:8230
```

`config_dir` guarda el inicio de sesión de YouTube: `.env` con `CLIENT_ID`, `CLIENT_SECRET` y `API_KEY`, `credentials.enc` y `.encryption_key`. Para crearlo: `GWS_CONFIG_DIR=<config_dir> scripts/yt-auth`. `importar-canais` solo sirve para quienes ya tienen instancias `yt-pub-livesN`.

**Conector de Metricool.** El publicador es un programa externo, indicado por `X3_METRICOOL_VIDEO` (valor predeterminado: `~/projetos/metricool-inematds/publicar.sh`). Recibe `<video> <legenda.txt> <repo-público>` y las variables `MARCA` y `REDES`. Resultados: `0` programado (imprime `Metricool: <url>`), `2` formato rechazado, otro valor = volver a intentar. Debe ser idempotente. El medio queda público en el repo de `X3_METRICOOL_REPO`, para que Metricool pueda descargarlo: usa un repo propio y tenlo en cuenta para contenido inédito. Las fotos y los carruseles usan `scripts/metricool-imagens.sh`, que espera la misma estructura en `X3_METRICOOL_DIR`.

**Recortes.** `scripts/yt-clip` usa `yt-dlp`, `ffmpeg`, el motor de `scripts/ia.yaml` y `prompt_cortes.txt` en `config_dir`. Usa `fila-vaga` solo si existe.

**Las portadas y los textos con IA** usan el `yt-pubx` local (`scripts/ia_ytpubx.py`). Si no está disponible, indica los textos en `post.json` y coloca `capa.jpg` en la carpeta. Las notificaciones usan `avisa-v3.sh` en la computadora de INEMA; en otra, aparecen en el registro y el panel.

**Servicios** de ejemplo en `systemd/`. No activan la publicación real.

## El proceso, de principio a fin

| # | Paso | Comando | Quién lo hace |
|---|---|---|---|
| 1 | Generar los canales a partir de los sistemas actuales, todos desactivados | `./yt-pub-x3 importar-canais` | ⚙️ script |
| 2 | Importar el historial de transmisiones en vivo de quienes hacen recortes | `./yt-pub-x3 importar-lives lives1` | ⚙️ script |
| 3 | Elegir el canal piloto y poner `ativo: true` en el YAML | editar `canais/livesN.yaml` | 🧠 sesión con Nei |
| 4 | Iniciar el hub y el panel | `python3 hub.py` · `python3 dashboard/server.py 8230` | ⚙️ servicio |
| 5 | Entregar contenido | carpeta en `entrada/<canal>/` o `./yt-pub-x3 enviar <pasta> --canal livesN` | ⚙️ productor |
| 6 | Validar: formato, repetición y textos | automático; `contexto` usa Codex | ⚙️ hub · 🤖 Codex |
| 7 | Recortar transmisiones en vivo para crear clips, en los canales con recortes activados | automático | ⚙️ hub · 🤖 IA de `scripts/ia.yaml` |
| 8 | Publicar 1 elemento por horario, por separado para cada destino | automático | ⚙️ hub |
| 9 | Aplicar la portada con Codex cuando esté permitido | automático | ⚙️ hub · 🤖 Codex |
| 10 | Revisar, pausar, omitir o volver a enviar | `http://127.0.0.1:8230` | 🧠 Nei |

## Qué colocar en la carpeta

```
entrada/lives4/2026-11-18-enxame/
  video.mp4      ou foto.jpg, ou 01.jpg, 02.jpg...
  post.json
  capa.jpg       opcional, vídeo normal
  legenda.srt    opcional, vídeo
  pronto         arquivo vazio, criado por último
```

```json
{
  "tipo": "video",
  "titulo": "Título no YouTube",
  "descricao": "Descrição no YouTube",
  "texto_rs": "Texto das redes",
  "tags": ["ia"],
  "destinos": ["youtube", "rs"],
  "quando": "fila"
}
```

`tipo`: `video`, `foto` o `carrossel`. `quando`: `fila`, `agora` o `AAAA-MM-DD HH:MM`. Si faltan los textos, indica `contexto` y Codex los redactará. Las fotos y los carruseles van solo a las redes y no consumen un horario de YouTube.

## Qué ocurre cuando algo falla

| Situación | Resultado |
|---|---|
| Se pierde el inicio de sesión de YouTube | YouTube del canal se pausa durante 1 h; el video permanece en la cola; las redes continúan |
| Límite o cuota de YouTube | Igual, con una pausa de 6 h |
| Falla temporal de una red | Hasta 3 intentos; después, error |
| Interrupción durante la carga | Pasa a **Revisar**; nunca se vuelve a enviar automáticamente |
| Video 16:9 o demasiado largo para las redes | Las redes quedan como **Omitido** |
| Archivo repetido o carpeta no válida | **Rechazado**, con el motivo, en `data/recusados/` |
| Codex no creó la portada | El video se publica sin portada y el panel la marca como pendiente |

## Pruebas

```bash
python3 -m unittest tests/test_x3.py
```

## Seguridad

El panel solo escucha en `127.0.0.1`, no tiene una contraseña predeterminada ni una ruta para ejecutar comandos, y las acciones requieren un encabezado propio. Los inicios de sesión, `canais/*.yaml`, `data/` y `entrada/` quedan fuera de git.

Conectores: Metricool para video e imágenes. Blotato y Upload-Post todavía no tienen un conector activo.
