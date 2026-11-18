"""Banco único. Um item é a publicação; cada destino dele é uma entrega independente."""
import os
import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, canal TEXT NOT NULL, tipo TEXT NOT NULL,
  pasta TEXT NOT NULL DEFAULT '', arquivos TEXT NOT NULL DEFAULT '[]',
  titulo TEXT NOT NULL DEFAULT '', descricao TEXT NOT NULL DEFAULT '', texto_rs TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '', privacy TEXT NOT NULL DEFAULT 'public',
  capa TEXT NOT NULL DEFAULT '', capa_status TEXT NOT NULL DEFAULT 'nao_leva', capa_motivo TEXT NOT NULL DEFAULT '',
  legenda TEXT NOT NULL DEFAULT '', sha256 TEXT NOT NULL, origem TEXT NOT NULL DEFAULT 'entrada',
  quando TEXT NOT NULL DEFAULT 'fila', largura INTEGER NOT NULL DEFAULT 0, altura INTEGER NOT NULL DEFAULT 0,
  duracao REAL NOT NULL DEFAULT 0, criado_em TEXT NOT NULL, UNIQUE(canal, sha256));
CREATE TABLE IF NOT EXISTS entregas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL REFERENCES itens(id), canal TEXT NOT NULL,
  destino TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'aguardando', motivo TEXT NOT NULL DEFAULT '',
  tentativas INTEGER NOT NULL DEFAULT 0, ref TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  atualizado_em TEXT NOT NULL, concluido_em TEXT NOT NULL DEFAULT '', UNIQUE(item_id, destino));
CREATE INDEX IF NOT EXISTS idx_entregas ON entregas(canal, destino, status);
CREATE TABLE IF NOT EXISTS canal_destino (
  canal TEXT NOT NULL, destino TEXT NOT NULL, ligado INTEGER, pausa_motivo TEXT NOT NULL DEFAULT '',
  retomar_em TEXT NOT NULL DEFAULT '', PRIMARY KEY(canal, destino));
CREATE TABLE IF NOT EXISTS recusados (
  id INTEGER PRIMARY KEY AUTOINCREMENT, canal TEXT NOT NULL, pasta TEXT NOT NULL, motivo TEXT NOT NULL, criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lives (
  canal TEXT NOT NULL, video_id TEXT NOT NULL, titulo TEXT NOT NULL DEFAULT '', data_live TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pendente', qtd_clips INTEGER NOT NULL DEFAULT 0, erro TEXT NOT NULL DEFAULT '',
  atualizado_em TEXT NOT NULL DEFAULT '', PRIMARY KEY(canal, video_id));
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE, canal TEXT NOT NULL, tipo TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}', run_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pendente',
  resultado TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL, inicio_em TEXT NOT NULL DEFAULT '', fim_em TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_jobs ON jobs(status, run_at);
"""

ACOES = {
    'pausar': (('aguardando',), 'pausado'),
    'retomar': (('pausado',), 'aguardando'),
    'pular': (('aguardando', 'pausado', 'erro', 'conferir'), 'ignorado'),
    'reenviar': (('erro', 'conferir', 'ignorado'), 'aguardando'),
    'confirmar': (('conferir',), 'feito'),
}


def agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect(path=None):
    path = path or config.db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=30000')
    con.executescript(SCHEMA)
    return con


def add_item(con, **f):
    f.setdefault('criado_em', agora())
    return con.execute(f"INSERT INTO itens({','.join(f)}) VALUES({','.join('?' * len(f))})",
                       tuple(f.values())).lastrowid


def item(con, item_id):
    return con.execute('SELECT * FROM itens WHERE id=?', (item_id,)).fetchone()


def ja_existe(con, canal, sha):
    return con.execute('SELECT id FROM itens WHERE canal=? AND sha256=?', (canal, sha)).fetchone()


def add_entrega(con, item_id, canal, destino, status='aguardando', motivo=''):
    return con.execute('INSERT INTO entregas(item_id,canal,destino,status,motivo,atualizado_em) VALUES(?,?,?,?,?,?)',
                       (item_id, canal, destino, status, motivo, agora())).lastrowid


def entrega(con, eid):
    return con.execute('SELECT * FROM entregas WHERE id=?', (eid,)).fetchone()


def proxima(con, canal, destino):
    """Próxima da fila normal. Com data ou 'agora', a entrega sai por vencidas()."""
    return con.execute("""SELECT e.* FROM entregas e JOIN itens i ON i.id=e.item_id
        WHERE e.canal=? AND e.destino=? AND e.status='aguardando' AND i.quando='fila'
        ORDER BY e.id LIMIT 1""", (canal, destino)).fetchone()


def vencidas(con, canal):
    return con.execute("""SELECT e.* FROM entregas e JOIN itens i ON i.id=e.item_id
        WHERE e.canal=? AND e.status='aguardando' AND i.quando!='fila'
        AND (i.quando='agora' OR i.quando<=?) ORDER BY e.id""", (canal, agora()[:16])).fetchall()


def reivindicar(con, eid):
    cur = con.execute("UPDATE entregas SET status='enviando', tentativas=tentativas+1, atualizado_em=? "
                      "WHERE id=? AND status='aguardando'", (agora(), eid))
    return cur.rowcount == 1


def concluir(con, eid, status, motivo='', ref='', url='', devolver=False):
    fim = agora() if status == 'feito' else ''
    con.execute(f"""UPDATE entregas SET status=?, motivo=?, ref=?, url=?, atualizado_em=?, concluido_em=?
        {', tentativas=MAX(tentativas-1,0)' if devolver else ''} WHERE id=?""",
                (status, (motivo or '')[:500], ref, url, agora(), fim, eid))


def acao(con, eid, nome):
    """Ação manual sobre uma entrega. Retorna True se mudou."""
    if nome not in ACOES:
        raise ValueError(f'ação desconhecida: {nome}')
    origem, destino = ACOES[nome]
    marcas = ','.join('?' * len(origem))
    motivo = {'pular': 'Pulado por você', 'confirmar': 'Confirmado por você'}.get(nome, '')
    extra = ', tentativas=0' if nome == 'reenviar' else ''
    cur = con.execute(f"UPDATE entregas SET status=?, motivo=?, atualizado_em=?{extra} "
                      f"WHERE id=? AND status IN ({marcas})", (destino, motivo, agora(), eid, *origem))
    return cur.rowcount == 1


def estado_destino(con, canal, destino):
    r = con.execute('SELECT * FROM canal_destino WHERE canal=? AND destino=?', (canal, destino)).fetchone()
    return dict(r) if r else {'canal': canal, 'destino': destino, 'ligado': None, 'pausa_motivo': '', 'retomar_em': ''}


def _garante(con, canal, destino):
    con.execute('INSERT OR IGNORE INTO canal_destino(canal,destino) VALUES(?,?)', (canal, destino))


def pausar_destino(con, canal, destino, motivo, retomar_em):
    _garante(con, canal, destino)
    con.execute('UPDATE canal_destino SET pausa_motivo=?, retomar_em=? WHERE canal=? AND destino=?',
                (motivo[:300], retomar_em, canal, destino))


def limpar_pausa(con, canal, destino):
    con.execute("UPDATE canal_destino SET pausa_motivo='', retomar_em='' WHERE canal=? AND destino=?", (canal, destino))


def definir_ligado(con, canal, destino, ligado):
    _garante(con, canal, destino)
    con.execute('UPDATE canal_destino SET ligado=? WHERE canal=? AND destino=?', (1 if ligado else 0, canal, destino))


def add_recusado(con, canal, pasta, motivo):
    con.execute('INSERT INTO recusados(canal,pasta,motivo,criado_em) VALUES(?,?,?,?)', (canal, pasta, motivo[:500], agora()))


def add_job(con, canal, tipo, run_at, payload='{}', chave=None):
    cur = con.execute('INSERT OR IGNORE INTO jobs(chave,canal,tipo,payload,run_at,criado_em) VALUES(?,?,?,?,?,?)',
                      (chave, canal, tipo, payload, run_at, agora()))
    return cur.lastrowid if cur.rowcount else None


def jobs_vencidos(con, limite=50):
    return con.execute("SELECT * FROM jobs WHERE status='pendente' AND run_at<=? ORDER BY tipo='entrada' DESC, run_at, id LIMIT ?",
                       (agora(), limite)).fetchall()


def reivindicar_job(con, job_id):
    cur = con.execute("UPDATE jobs SET status='rodando', inicio_em=? WHERE id=? AND status='pendente'", (agora(), job_id))
    return cur.rowcount == 1


def apagar_job(con, job_id):
    con.execute('DELETE FROM jobs WHERE id=?', (job_id,))


def expirar_atrasados(con, limite_h=1):
    """Hub que ficou parado não solta de uma vez os horários que perdeu."""
    return con.execute("""UPDATE jobs SET status='erro', resultado='horário perdido', fim_em=?
        WHERE status='pendente' AND tipo IN ('publicar','cortar')
        AND run_at < datetime('now','localtime',?)""", (agora(), f'-{int(limite_h)} hours')).rowcount


def fim_job(con, job_id, ok, texto=''):
    con.execute('UPDATE jobs SET status=?, resultado=?, fim_em=? WHERE id=?',
                ('ok' if ok else 'erro', str(texto)[:500], agora(), job_id))


def recuperar_interrompidos(con):
    """Na partida do hub nada pode estar rodando: envio interrompido nunca é repetido sozinho."""
    n = con.execute("UPDATE entregas SET status='conferir', motivo='Envio interrompido: confira antes de reenviar', "
                    "atualizado_em=? WHERE status='enviando'", (agora(),)).rowcount
    con.execute("UPDATE jobs SET status='erro', resultado='interrompido', fim_em=? WHERE status='rodando'", (agora(),))
    con.execute("UPDATE lives SET status='erro', erro='Corte interrompido', atualizado_em=? WHERE status='cortando'", (agora(),))
    return n
