# yt-pub-x3

Publicador único: fila por canal → YouTube + redes sociais, com status por destino, e cortes de lives. Decisões em `docs/ESPECIFICACAO.md`; uso em `README.md`.

- Conta GitHub: `linnoff88-dev`.
- Publicar de verdade só com `X3_PUBLICAR=1` e canal `ativo: true`. Ligar canal novo é decisêo do Nei.
- Nêo alterar yt-pubx, `~/.config/yt-pubx/config.json` nem os agendadores `yt-pub-livesN` sem pedido.
- Falha de login/cota nunca consome vídeo; envio interrompido vai para `conferir`.
- Blotato e Upload-Post só com autorizaçêo expressa do Nei.
- Testes: `python3 -m unittest tests/test_x3.py`, só com publicadores falsos.

## Self-learning

Quando for corrigido ou notar um erro seu, antes de continuar acrescente a liçêo em uma linha no topo de `## Lessons`.

## Lessons

- Histórico importado nêo pode contar no limite diário de cortes: importar sem data de atualizaçêo. (18/11/2026)
