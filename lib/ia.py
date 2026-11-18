"""Textos e capas pelo Codex, usando o yt-pubx em processo separado. Sem imagem reserva."""
import json
import os
import subprocess
import sys

from . import config


def _chamar(pedido, tempo=1200):
    script = os.path.join(config.ROOT, 'scripts', 'ia_ytpubx.py')
    r = subprocess.run([sys.executable, '-I', script], input=json.dumps(pedido), text=True,
                       capture_output=True, timeout=tempo)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:] or 'IA falhou')
    return json.loads(r.stdout.strip().splitlines()[-1])


def escrever_textos(canal, tipo, contexto, arquivo='', titulo='', descricao=''):
    return _chamar({'acao': 'texto', 'canal': canal, 'tipo': tipo, 'contexto': contexto, 'video': arquivo,
                    'titulo': titulo, 'descricao': descricao})


def gerar_capa(canal, titulo, descricao, pasta):
    os.makedirs(pasta, exist_ok=True)
    return _chamar({'acao': 'capa', 'canal': canal, 'titulo': titulo, 'descricao': descricao, 'pasta': pasta})['capa']
