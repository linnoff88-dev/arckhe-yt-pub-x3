"""Conector do Metricool: usa os publicadores da conta, que já têm trava por marca, 1 h e recibo."""
import json
import os
import re
import subprocess

from . import config
from .falhas import DEFINITIVO, FORMATO, TEMPORARIO, Falha



def repo_midia():
    """Repo público que hospeda a mídia: o Metricool precisa de URL pública."""
    return os.environ.get('X3_METRICOOL_REPO') or 'inematds/yt-pubx'


TEMPO = 5400  # espera da trava da marca + agente


def publicador_video():
    return os.environ.get('X3_METRICOOL_VIDEO') or os.path.join(config.PROJETOS, 'metricool-inematds', 'publicar.sh')


def publicador_imagens():
    return os.environ.get('X3_METRICOOL_IMAGENS') or os.path.join(config.ROOT, 'scripts', 'metricool-imagens.sh')


def formato(item, rs):
    """Motivo pelo qual o item não serve para as redes, ou ''."""
    if item['tipo'] in ('foto', 'carrossel'):
        return ''
    if item['largura'] >= item['altura']:
        return 'Formato 16:9 não vai para Reels e TikTok'
    limite = 180 if 'instagram' in rs['redes'] else 600
    if item['duracao'] > limite:
        return f'Passa de {limite} s'
    return ''


def legenda(item):
    """Sempre o mesmo arquivo: o recibo do publicador depende deste texto."""
    os.makedirs(item['pasta'], exist_ok=True)
    p = os.path.join(item['pasta'], 'legenda-rs.txt')
    if not os.path.exists(p):
        with open(p, 'w', encoding='utf-8') as f:
            f.write(f"{item['titulo']}\n\n{item['texto_rs'] or item['descricao']}\n")
    return p


def publicar(canal, item, log=print):
    rs = canal['rs']
    motivo = formato(item, rs)
    if motivo:
        raise Falha(motivo, FORMATO)
    arquivos = json.loads(item['arquivos'])
    env = {**os.environ, 'MARCA': rs['marca'], 'REDES': ','.join(rs['redes'])}
    if item['tipo'] in ('foto', 'carrossel'):
        cmd = ['bash', publicador_imagens(), legenda(item), repo_midia(), *arquivos]
    else:
        cmd = ['bash', publicador_video(), arquivos[0], legenda(item), repo_midia()]
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TEMPO)
    except subprocess.TimeoutExpired:
        raise Falha('Metricool demorou demais', TEMPORARIO) from None
    saida = (r.stdout or '') + (r.stderr or '')
    if r.returncode == 0:
        m = re.search(r'Metricool: (https://\S+)', saida)
        url = m.group(1) if m else f"https://app.metricool.com/planner/calendar?blogId={rs['blog_id']}"
        return rs['marca'], url
    fim = saida.strip()[-300:]
    if r.returncode == 2:
        raise Falha(fim or 'Formato recusado', FORMATO)
    raise Falha(fim or f'publicador saiu com {r.returncode}', TEMPORARIO)


PUBLICADORES = {'metricool': publicar}


def sem_conector(canal, item, log=print):
    raise Falha(f"RS sem conector ativo: {canal['rs'].get('provedor') or 'nenhum'}", DEFINITIVO)
