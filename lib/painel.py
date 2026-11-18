"""Dados do painel: fila do x3 + leitura somente-leitura dos sistemas atuais."""
import collections
import glob
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta

from . import VERSION, config, db, runner

_cache = {'t': 0, 'v': {}}


def _historico_ytpubx(dias):
    h = collections.defaultdict(lambda: {'n': 0, 'ag': 0, 'h24': 0, 'd': collections.Counter()})
    agora = datetime.now().strftime('%Y-%m-%d %H:%M')
    d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
    try:
        f = open(config.historico_ytpubx(), encoding='utf-8')
    except OSError:
        return h
    with f:
        for l in f:
            try:
                r = json.loads(l)
            except ValueError:
                continue
            p = r.get('privacy') or {}
            q = str(p.get('publishAt') or r.get('data') or '')[:16].replace('T', ' ')
            if not r.get('canal') or not q or (p.get('privacyStatus') != 'public' and not p.get('publishAt')):
                continue
            x = h[r['canal']]
            x['n'] += 1
            x['d'][q[:10]] += 1
            x['h24'] += d24 <= q <= agora
            x['ag'] += q > agora
    return h


def _recibos():
    out = collections.Counter()
    d = os.path.join(config.legado_dir(), 'metricool-inematds', 'estado')
    for p in glob.glob(os.path.join(d, '*.recibo.json')):
        try:
            m = re.search(r'blogId=(\d+)', open(p, encoding='utf-8').read())
            if m:
                out[int(m.group(1))] += 1
        except OSError:
            pass
    return out


def _legado(nome, yp, dias):
    z = lambda: [0, 0, 0, 0, 0]
    o = {'imports': z(), 'clips': z(), 'lives': z(), 'ultimo_corte': ''}
    D = collections.Counter(yp['d'])
    p = os.path.join(config.legado_dir(), f'yt-pub-{nome}', 'data', 'lives.db')
    if os.path.exists(p):
        d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
        c = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        L = {r['video_id']: r for r in c.execute('SELECT video_id,titulo,qtd_clips,clips_pendentes,status_cortes,data_corte FROM lives')}
        tipo = lambda v: None if str(v).startswith('import_') and str(L[v]['titulo'] if v in L else '').startswith('TikTok @') else (
            'imports' if str(v).startswith('import_') else 'clips')
        for v, r in L.items():
            k = tipo(v)
            if k:
                o[k][0] += int(r['qtd_clips'] or 0)
                o[k][1] += int(r['clips_pendentes'] or 0)
            if not v.startswith('import_'):
                o['lives'][0] += 1
                s = r['status_cortes']
                o['lives'][1] += s == 'pendente'
                o['lives'][2] += s == 'concluido'
                o['lives'][3] += str(s).startswith('erro')
                dc = r['data_corte'] or ''
                o['lives'][4] += dc >= d24
                o['ultimo_corte'] = max(o['ultimo_corte'], dc)
        for r in c.execute('SELECT clip_video_id v, live_video_id l, data_publicacao d FROM publicados'):
            k, e = tipo(r['l']), r['v'] in ('erro_upload', 'publicando', '')
            if not e:
                D[str(r['d'])[:10]] += 1
            if k:
                o[k][3 if e else 2] += 1
                o[k][4] += (not e) and str(r['d']) >= d24
        c.close()
    o['historico'] = [D[d] for d in dias]
    o['entrada7'] = sum(yp['d'][d] for d in dias[-7:])  # o que chegou pelo yt-pubx e teria de caber na fila
    return o


def legado(canais):
    if time.time() - _cache['t'] > 60:
        ontem = datetime.now().date() - timedelta(days=1)
        dias = [(ontem - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        h = _historico_ytpubx(dias)
        v = {'dias': dias, 'recibos': _recibos(), 'canais': {}}
        for n in canais:
            try:
                v['canais'][n] = {**_legado(n, h[n], dias), 'yt': [h[n]['n'], h[n]['ag'], h[n]['n'], '–', h[n]['h24']]}
            except sqlite3.Error:
                v['canais'][n] = {}
        _cache.update(t=time.time(), v=v)
    return _cache['v']


def _contagem(con, nome, destino):
    r = {x['status']: x['n'] for x in con.execute('SELECT status, COUNT(*) n FROM entregas WHERE canal=? AND destino=? GROUP BY status', (nome, destino))}
    d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    r['h24'] = con.execute("SELECT COUNT(*) FROM entregas WHERE canal=? AND destino=? AND status='feito' AND concluido_em>=?", (nome, destino, d24)).fetchone()[0]
    return r


def estado(con, canais):
    lg = legado(canais)
    out = []
    for n, c in canais.items():
        v = lg['canais'].get(n, {})
        destinos = {}
        for d in ('youtube', 'rs'):
            e = db.estado_destino(con, n, d)
            destinos[d] = {'ligado': runner.ligado(con, c, d), 'pausa': e['pausa_motivo'], 'retomar_em': e['retomar_em'], 'n': _contagem(con, n, d)}
        s = len(c['youtube']['horarios']) * 7
        sem = v.get('entrada7', 0)
        out.append({'nome': n, 'titulo': c['destino_nome'] or 'Sem nome salvo', 'url': c['url'], 'ativo': c['ativo'],
                    'youtube': c['youtube'], 'rs': c['rs'], 'cortes': c['cortes'], 'destinos': destinos, 'legado': v,
                    'vagas': s, 'semana': sem, 'recibos': lg['recibos'].get(c['rs']['blog_id'], 0)})
    return {'versao': VERSION, 'publicando': config.publicar_de_verdade(), 'agora': db.agora(), 'dias': lg['dias'], 'canais': out,
            'recusados': [dict(r) for r in con.execute('SELECT * FROM recusados ORDER BY id DESC LIMIT 30')]}


def itens_canal(con, nome):
    itens = []
    for i in con.execute('SELECT * FROM itens WHERE canal=? ORDER BY id DESC LIMIT 100', (nome,)).fetchall():
        e = [dict(x) for x in con.execute('SELECT id,destino,status,motivo,tentativas,url,atualizado_em FROM entregas WHERE item_id=? ORDER BY destino DESC', (i['id'],))]
        itens.append({'id': i['id'], 'tipo': i['tipo'], 'titulo': i['titulo'], 'origem': i['origem'], 'quando': i['quando'], 'largura': i['largura'],
                      'altura': i['altura'], 'duracao': round(i['duracao']), 'capa': i['capa_status'], 'capa_motivo': i['capa_motivo'], 'entregas': e})
    lives = [dict(r) for r in con.execute('SELECT video_id,titulo,data_live,status,qtd_clips,erro FROM lives WHERE canal=? ORDER BY data_live DESC LIMIT 30', (nome,))]
    return {'itens': itens, 'lives': lives}
