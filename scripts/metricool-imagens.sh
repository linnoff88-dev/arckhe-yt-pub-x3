#!/usr/bin/env bash
# Publica foto ou carrossel no Metricool da conta inematds, com as travas do publicar.sh de vídeo.
# uso: MARCA=<marca> REDES=tiktok,instagram metricool-imagens.sh <legenda.txt> <repo-público> <imagem>...
# Saída: 0 agendado · 1 tentar de novo · 2 entrada inválida.
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
M="${X3_METRICOOL_DIR:-$HOME/projetos/metricool-inematds}"
[ $# -ge 3 ] || { echo "uso: $0 <legenda> <repo> <imagem>..."; exit 2; }
TXT="$(realpath "$1")"; REPO="$2"; shift 2
MARCA="${MARCA:-inema.tds}"; REDES="${REDES:-tiktok,instagram}"
for f in "$@"; do [ -s "$f" ] || { echo "imagem ausente: $f"; exit 2; }; done

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
python3 "$M/sem_links.py" "$TXT" "$T/texto.txt" || exit 2; TXT="$T/texto.txt"

mkdir -p "$HOME/.local/share/metricool-intervalo" "$M/estado"
CHAVE=$(printf '%s' "inematds_$MARCA" | tr -c 'A-Za-z0-9._-' '_')
exec 9>"$HOME/.local/share/metricool-intervalo/$CHAVE.publicacao.lock"
flock -w 3600 9 || exit 1

HASH=$( { cat "$@" "$TXT"; printf '%s' "$MARCA"; } | sha256sum | cut -c1-24)
RECIBO="$M/estado/$HASH.recibo.json"
[ -s "$RECIBO" ] && { echo "já agendado, recibo $RECIBO"; exit 0; }

ALVO=$(( $(date +%s) + 600 ))
ALVO=$(python3 "$M/intervalo.py" --conector metricool-inematds --marca "$MARCA" --alvo "$ALVO") || { echo "trava de 1 h não leu a agenda"; exit 1; }
QUANDO=$(date -u -d "@$ALVO" +%Y-%m-%dT%H:%M:00)

gh release view social -R "$REPO" >/dev/null 2>&1 || \
  gh release create social -R "$REPO" --title "Vídeos para redes sociais" --notes "Cópias usadas pelo Metricool." >/dev/null
MEDIA=""; n=0
for f in "$@"; do
  n=$((n + 1)); e="${f##*.}"; nome="$(printf '%s-%02d.%s' "$HASH" "$n" "$e")"; cp "$f" "$T/$nome"
  gh release upload social "$T/$nome" -R "$REPO" --clobber || { echo "falhou o envio da imagem"; exit 1; }
  u=$(python3 "$M/auto/resolver_midia.py" "https://github.com/$REPO/releases/download/social/$nome") || exit 1
  MEDIA="$MEDIA\"$u\","
done
MEDIA="${MEDIA%,}"

PEDIDO="Use só as ferramentas do servidor MCP metricool-inematds.
1) getBrandSettings: blogId da marca com label exatamente \"$MARCA\" e quais destas redes estão conectadas: $REDES.
2) getScheduledPosts da marca no dia: se a mesma mídia e o mesmo texto já estiverem agendados, devolva o recibo sem recriar. Senão, createScheduledPost UMA vez, nas redes conectadas:
   date = ${QUANDO}Z ; publicationDate = {dateTime: \"$QUANDO\", timezone: \"UTC\"}
   media = [$MEDIA] (nesta ordem) ; text = conteúdo exato do arquivo $TXT (leia com Read)
   draft = false ; autoPublish = true
   instagramData = {type: \"POST\", isAiGenerated: true}
   tiktokData = {privacyOption: \"PUBLIC_TO_EVERYONE\", title: primeira linha do texto (até 90 caracteres), autoAddMusic: true, photoCoverIndex: 0}
3) Responda APENAS uma linha JSON, sem crase: {\"ok\":true|false,\"redes\":[...],\"faltam\":[...],\"planner\":[...],\"erro\":\"\"}"
OUT=$(printf '%s' "$PEDIDO" | timeout 900 python3 "$M/auto/ia_motor.py" executar metricool_publicacao --pasta "$M/estado" --agente --arquivo "$TXT" \
  --ferramentas "mcp__metricool-inematds__getBrandSettings mcp__metricool-inematds__getScheduledPosts mcp__metricool-inematds__createScheduledPost Read" 2>&1)
J=$(printf '%s' "$OUT" | grep -o '{.*"ok".*}' | tail -1)
printf '%s' "$J" | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("ok") is True else 1)' 2>/dev/null \
  || { echo "Metricool não agendou: $(printf '%s' "$OUT" | tail -c 300)"; exit 1; }
printf '%s\n' "$J" > "$RECIBO"
python3 "$M/intervalo.py" --registrar --marca "$MARCA" --alvo "$ALVO"
PLAN=$(printf '%s' "$J" | python3 -c 'import json,sys; p=json.load(sys.stdin).get("planner") or [""]; print(p[0])')
echo "Metricool: $PLAN"
