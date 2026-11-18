# FALHAS — yt-pub-x3

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-11-18 | lives importadas contavam como cortadas hoje e bloqueavam o corte do dia | importar com data vazia | prompt |
| 2026-11-18 | horário rodava antes da varredura da entrada no mesmo ciclo e perdia o vídeo novo | varredura primeiro na ordem dos jobs | prompt |
| 2026-11-18 | revisão achou limite do YouTube em HTTP 400 consumindo fila, reenvio em 5xx, recorte de live já feita e rajada após queda | classificar pelo motivo, 5xx pós-envio vai para conferir, consultar o sistema antigo, expirar horários vencidos | prompt |
