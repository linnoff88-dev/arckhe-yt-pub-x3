"""Canais = canais/<nome>.yaml. Nenhum segredo aqui: o login fica no config_dir do canal."""
import glob
import os
import re

import yaml

from . import config

BASE = {
    'destino_id': '', 'destino_nome': '', 'url': '', 'origem_id': '', 'config_dir': '', 'lives_dir': '',
    'ativo': False, 'max_tentativas': 3,
}
YOUTUBE = {'ligado': True, 'horarios': [], 'privacy': 'public'}
RS = {'provedor': '', 'ligado': False, 'marca': '', 'blog_id': '', 'redes': [], 'instagram': '', 'tiktok': '',
      'horarios': None, 'nota': ''}
CORTES = {'ligado': False, 'horarios': [], 'max_por_dia': 1, 'ai_modo': 'claude-api'}


def _lista(v):
    if isinstance(v, str):
        v = v.split(',')
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def normaliza(nome, bruto):
    bruto = bruto or {}
    c = {**BASE, **{k: v for k, v in bruto.items() if k in BASE and v is not None}, 'nome': nome}
    c['youtube'] = {**YOUTUBE, **(bruto.get('youtube') or {})}
    c['rs'] = {**RS, **(bruto.get('rs') or {})}
    c['cortes'] = {**CORTES, **(bruto.get('cortes') or {})}
    c['youtube']['horarios'] = _lista(c['youtube']['horarios'])
    c['cortes']['horarios'] = _lista(c['cortes']['horarios'])
    c['rs']['redes'] = _lista(c['rs']['redes'])
    c['rs']['horarios'] = c['youtube']['horarios'] if c['rs']['horarios'] is None else _lista(c['rs']['horarios'])
    c['config_dir'] = os.path.expanduser(str(c['config_dir'] or ''))
    c['lives_dir'] = os.path.expanduser(str(c['lives_dir'] or ''))
    return c


def carregar(dir_=None):
    out = {}
    ordem = lambda x: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', os.path.basename(x))]
    for p in sorted(glob.glob(os.path.join(dir_ or config.canais_dir(), '*.yaml')), key=ordem):
        nome = os.path.splitext(os.path.basename(p))[0]
        if nome.startswith('_'):
            continue
        with open(p, encoding='utf-8') as f:
            out[nome] = normaliza(nome, yaml.safe_load(f))
    return out


def salvar(c, dir_=None, sobrescrever=False):
    dir_ = dir_ or config.canais_dir()
    os.makedirs(dir_, exist_ok=True)
    p = os.path.join(dir_, c['nome'] + '.yaml')
    if os.path.exists(p) and not sobrescrever:
        return None
    dados = {k: v for k, v in c.items() if k != 'nome'}
    if dados['rs']['horarios'] == dados['youtube']['horarios']:
        dados['rs'] = {k: v for k, v in dados['rs'].items() if k != 'horarios'}  # herda do YouTube
    with open(p, 'w', encoding='utf-8') as f:
        yaml.safe_dump(dados, f, allow_unicode=True, sort_keys=False)
    return p
