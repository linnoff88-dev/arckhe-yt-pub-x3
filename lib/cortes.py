"""Cortes: encontra lives novas, corta com o yt-clip e põe os clipes na fila do canal."""
import json
import os
import sqlite3
import subprocess
from datetime import datetime

from . import config, db, entrada, midia, youtube

TEMPO = 4 * 3600


def importar_historico(con, canal):
    """Traz do agendador antigo o que já foi processado, para nunca cortar de novo."""
    p = os.path.join(config.legado_dir(), f"yt-pub-{canal['nome']}", 'data', 'lives.db')
    if not os.path.exists(p):
        return 0
    v = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    v.row_factory = sqlite3.Row
    mapa = {'concluido': 'cortada', 'sem_topicos': 'sem_topicos', 'erro': 'erro'}
    n = 0
    for r in v.execute("SELECT video_id,titulo,data_live,status_cortes,qtd_clips FROM lives WHERE video_id NOT LIKE 'import_%'"):
        n += con.execute("""INSERT INTO lives(canal,video_id,titulo,data_live,status,qtd_clips,atualizado_em) VALUES(?,?,?,?,?,?,?)
                         ON CONFLICT(canal,video_id) DO UPDATE SET status=excluded.status, qtd_clips=excluded.qtd_clips
                         WHERE lives.status='pendente' AND excluded.status!='pendente'""",
                         (canal['nome'], r['video_id'], r['titulo'], r['data_live'], mapa.get(r['status_cortes'], 'pendente'),
                          int(r['qtd_clips'] or 0), '')).rowcount  # sem data: não conta no limite do dia
    v.close()
    return n


def status_antigo(canal, video_id):
    """Situação da live no agendador antigo, ou ''. Enquanto ele existir, é ele quem sabe se já cortou."""
    p = os.path.join(config.legado_dir(), f"yt-pub-{canal['nome']}", 'data', 'lives.db')
    if not os.path.exists(p):
        return ''
    v = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=10)
    try:
        r = v.execute('SELECT status_cortes FROM lives WHERE video_id=?', (video_id,)).fetchone()
        return (r[0] or '') if r else ''
    finally:
        v.close()


def sincronizar(con, canal, listar=None):
    listar = listar or youtube.listar_lives
    n = 0
    for l in listar(canal['origem_id'], canal['config_dir']):
        n += con.execute("INSERT OR IGNORE INTO lives(canal,video_id,titulo,data_live,status,atualizado_em) VALUES(?,?,?,?,'pendente',?)",
                         (canal['nome'], l['video_id'], l['titulo'], l['data_live'], db.agora())).rowcount
    return n


def executar_yt_clip(canal, video_id, log=print):
    s = os.path.join(config.ROOT, 'scripts')
    cmd = [os.path.join(s, 'yt-clip'), '--ai', canal['cortes']['ai_modo'], '--', video_id]
    vaga = os.path.join(config.PROJETOS, 'wifi', 'scripts', 'fila-vaga')
    if os.path.exists(vaga):  # na máquina INEMA, respeita as vagas de trabalho pesado
        cmd = [vaga, 'render', f"x3-corte-{canal['nome']}", '--', *cmd]
    env = {**os.environ, 'LIVES_DIR': canal['lives_dir'], 'GWS_CONFIG_DIR': canal['config_dir']}
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TEMPO)
    if r.returncode:
        raise RuntimeError((r.stdout + r.stderr).strip()[-300:] or f'yt-clip saiu com {r.returncode}')


def _enfileirar_clipes(con, canal, video_id, manifesto):
    n = 0
    for c in manifesto:
        arq = c.get('file', '')
        if not os.path.isfile(arq):
            continue
        sha = midia.sha256([arq])
        if db.ja_existe(con, canal['nome'], sha):
            continue
        l, a, d = midia.probe(arq)
        pasta = os.path.join(config.acervo_dir(), canal['nome'], f"clip-{video_id}-{c.get('index', n)}")
        tags = c.get('tags') or []
        item_id = db.add_item(con, canal=canal['nome'], tipo='clip', pasta=pasta, arquivos=json.dumps([arq]),
                              titulo=c.get('title', ''), descricao=c.get('description', ''), texto_rs=c.get('description', ''),
                              tags=','.join(tags) if isinstance(tags, list) else str(tags), privacy=canal['youtube']['privacy'],
                              capa_status=entrada.capa_inicial('clip', '', l, a, d), sha256=sha, origem=f'live:{video_id}',
                              largura=l, altura=a, duracao=d or float(c.get('duration') or 0))
        entrada.criar_entregas(con, item_id, canal, ['youtube', 'rs'])
        n += 1
    return n


def cortar_proxima(con, canal, cortar=None, log=print):
    """Corta a live pendente mais antiga, respeitando o limite do dia."""
    cortar = cortar or executar_yt_clip
    nome = canal['nome']
    hoje = datetime.now().strftime('%Y-%m-%d')
    feitas = con.execute("SELECT COUNT(*) FROM lives WHERE canal=? AND status IN ('cortada','cortando') AND atualizado_em LIKE ?",
                         (nome, hoje + '%')).fetchone()[0]
    if feitas >= int(canal['cortes']['max_por_dia']):
        return 'limite do dia'
    l = None
    for c in con.execute("SELECT * FROM lives WHERE canal=? AND status='pendente' ORDER BY data_live, video_id", (nome,)).fetchall():
        antigo = status_antigo(canal, c['video_id'])
        if antigo in ('', 'pendente'):
            l = c
            break
        novo = {'concluido': 'cortada', 'sem_topicos': 'sem_topicos', 'erro': 'erro'}.get(antigo)
        if novo:  # sem atualizado_em: não conta no limite do dia
            con.execute('UPDATE lives SET status=? WHERE canal=? AND video_id=?', (novo, nome, c['video_id']))
    if not l:
        return 'nenhuma live pendente'
    vid = l['video_id']
    con.execute("UPDATE lives SET status='cortando', atualizado_em=? WHERE canal=? AND video_id=?", (db.agora(), nome, vid))
    pasta = os.path.join(canal['lives_dir'], vid)
    try:
        cortar(canal, vid, log)
        try:
            with open(os.path.join(pasta, 'clips_manifest.json'), encoding='utf-8') as f:
                manifesto = json.load(f)
        except OSError:
            manifesto = []
        qtd = _enfileirar_clipes(con, canal, vid, manifesto)
        status = 'cortada' if manifesto else ('sem_topicos' if os.path.exists(os.path.join(pasta, 'topics.json')) else 'erro')
        erro = '' if status != 'erro' else 'yt-clip não gerou clipes'
    except Exception as e:
        status, qtd, erro = 'erro', 0, str(e)
    con.execute('UPDATE lives SET status=?, qtd_clips=?, erro=?, atualizado_em=? WHERE canal=? AND video_id=?',
                (status, qtd, erro[:300], db.agora(), nome, vid))
    return f'{vid}: {status} ({qtd} clipes)'
