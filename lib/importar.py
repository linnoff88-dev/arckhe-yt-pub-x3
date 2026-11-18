"""Cria canais/*.yaml a partir dos sistemas atuais, só lendo. Todos nascem com ativo: false."""
import glob
import json
import os
import re
import sqlite3

import yaml

from . import canais, config

M = {
    'FTD': (7908265, ['tiktok', 'instagram'], 'inema.tech', 'inema.tech'),
    'inema.tds': (7797870, ['tiktok', 'instagram'], 'inema.tds', 'inema.tds'),
    'VIBE': (8026101, ['tiktok'], '', 'inema.prompts'),
    'eventosextremos': (7800440, ['tiktok', 'instagram'], 'eventos.extremos', 'eventos.extremos'),
    'Radar': (7999284, ['tiktok', 'instagram'], 'inema.club24', 'inema.club24'),
    'inemafuturos': (7577386, ['tiktok', 'instagram'], 'inemafuturos', 'inemafuturos'),
}
MARCA = {'lives2': 'Radar', 'lives3': 'FTD', 'lives4': 'inema.tds', 'lives7': 'VIBE', 'lives8': 'VIBE', 'lives10': 'eventosextremos',
         'lives11': 'inemafuturos', 'lives12': 'inema.tds', 'lives24': 'Radar', 'lives31': 'FTD'}
RS_LIGADO = {'lives3', 'lives4', 'lives7', 'lives8', 'lives12', 'lives31'}
NOTAS = {'lives1': 'Saiu do Metricool em 17/11/2026.', 'lives2': 'O Radar Viral tem fluxo próprio.', 'lives24': 'O Radar Viral tem fluxo próprio.',
         'lives10': 'O clima tem fluxo próprio.', 'lives11': 'Outra conta do Metricool (metricool-pub2).'}


def _ytpubx():
    try:
        with open(os.path.join(config.HOME, '.config', 'yt-pubx', 'config.json'), encoding='utf-8') as f:
            return json.load(f).get('canais', {})
    except OSError:
        return {}


def montar(pasta, yp):
    nome = re.search(r'yt-pub-(lives\d+)$', pasta).group(1)
    con = sqlite3.connect(f"file:{os.path.join(pasta, 'data', 'lives.db')}?mode=ro", uri=True)
    g = dict(con.execute('SELECT chave, valor FROM config').fetchall())
    con.close()
    y2 = {}
    p2 = os.path.join(config.legado_dir(), 'yt-pub-livesx2', 'canais', nome + '.yaml')
    if os.path.exists(p2):
        with open(p2, encoding='utf-8') as f:
            y2 = yaml.safe_load(f) or {}
    v = yp.get(nome, {})
    marca = MARCA.get(nome, '')
    blog, redes, ig, tt = M.get(marca, ('', [], '', ''))
    return canais.normaliza(nome, {
        'destino_id': y2.get('destino_id', ''), 'destino_nome': y2.get('destino_nome') or v.get('nome', ''), 'url': v.get('url', ''),
        'origem_id': g.get('canal_origem_id') or y2.get('origem_id', ''),
        'config_dir': os.path.join(pasta, 'config'), 'lives_dir': os.path.join(pasta, 'lives'), 'ativo': False,
        'youtube': {'ligado': g.get('pipeline_imports_paused') != 'true', 'horarios': g.get('import_pub_horarios', ''),
                    'privacy': g.get('import_privacy') or 'public'},
        'rs': {'provedor': 'metricool' if marca else '', 'ligado': nome in RS_LIGADO, 'marca': marca, 'blog_id': blog,
               'redes': redes, 'instagram': ig, 'tiktok': tt, 'nota': NOTAS.get(nome, '')},
        # Só o lives1 corta hoje: é o único com o corte automático em uso.
        'cortes': {'ligado': nome == 'lives1', 'horarios': g.get('corte_horarios', ''),
                   'max_por_dia': int(g.get('corte_max_por_dia') or 1), 'ai_modo': g.get('ai_mode') or 'claude-api'},
    })


def importar(sobrescrever=False):
    yp = _ytpubx()
    feitos, pulados = [], []
    for db_ in sorted(glob.glob(os.path.join(config.legado_dir(), 'yt-pub-lives[0-9]*', 'data', 'lives.db'))):
        c = montar(os.path.dirname(os.path.dirname(db_)), yp)
        (feitos if canais.salvar(c, sobrescrever=sobrescrever) else pulados).append(c['nome'])
    return feitos, pulados
