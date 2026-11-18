"""Executa jobs. Único lugar que chama publicadores e muda o status das entregas."""
import json
import os
import subprocess
from datetime import datetime, timedelta

from . import config, cortes, db, entrada, ia, metricool, youtube
from .falhas import AMBIGUO, AUTH, COTA, DEFINITIVO, FORMATO, Falha

PAUSA = {AUTH: timedelta(hours=1), COTA: timedelta(hours=6)}
FAIXAS = {'publicar': None, 'publicar_entrega': None, 'entrada': 'geral', 'capa': 'geral', 'sync_lives': 'geral', 'cortar': 'cortes'}


def pub_youtube(canal, item, log=print):
    arq = json.loads(item['arquivos'])[0]
    return youtube.publicar(arq, item['titulo'], item['descricao'], canal['config_dir'], item['tags'], item['privacy'], log)


def pub_rs(canal, item, log=print):
    return metricool.PUBLICADORES.get(canal['rs']['provedor'], metricool.sem_conector)(canal, item, log)


PUBLICADORES = {'youtube': pub_youtube, 'rs': pub_rs}
definir_capa = youtube.definir_capa
gerar_capa = ia.gerar_capa
ESCREVER = None
CORTAR = None
LISTAR_LIVES = None


def avisar(msg, log=print):
    log(f'AVISO: {msg}')
    if not config.publicar_de_verdade():
        return
    try:
        subprocess.run([os.path.join(config.PROJETOS, 'wifi', 'scripts', 'avisa-v3.sh'), f'yt-pub-x3: {msg}'],
                       capture_output=True, timeout=60)
    except Exception as e:
        log(f'aviso não enviado: {e}')


def ligado(con, canal, destino):
    est = db.estado_destino(con, canal['nome'], destino)
    if est['ligado'] is not None:
        return bool(est['ligado'])
    return bool(canal['youtube' if destino == 'youtube' else 'rs']['ligado'])


def disponivel(con, canal, destino):
    """(pode publicar?, motivo)."""
    if not canal['ativo']:
        return False, 'canal inativo'
    if not ligado(con, canal, destino):
        return False, 'destino desligado'
    est = db.estado_destino(con, canal['nome'], destino)
    if est['retomar_em'] and est['retomar_em'] > db.agora():
        return False, f"pausado até {est['retomar_em'][:16]}: {est['pausa_motivo']}"
    return True, ''


def publicar_entrega(con, canal, e, simular, log=print):
    pode, motivo = disponivel(con, canal, e['destino'])
    if not pode:
        return motivo
    it = db.item(con, e['item_id'])
    rot = f"[{canal['nome']}/{e['destino']}] item {it['id']}"
    if simular:
        log(f"{rot}: SIMULADO {it['titulo'][:60]}")
        return 'simulado'
    if not db.reivindicar(con, e['id']):
        return 'já em andamento'
    tent = db.entrega(con, e['id'])['tentativas']
    try:
        ref, url = PUBLICADORES[e['destino']](canal, it, log=lambda m: log(f'{rot}: {m}'))
    except Falha as f:
        return _tratar_falha(con, canal, e, f, tent, rot, log)
    except Exception as x:
        db.concluir(con, e['id'], 'conferir', f'Falha inesperada: {type(x).__name__}: {x}')
        log(f'{rot}: inesperado, foi para conferir: {x}')
        return 'conferir'
    db.concluir(con, e['id'], 'feito', ref=str(ref), url=url or '')
    db.limpar_pausa(con, canal['nome'], e['destino'])
    if e['destino'] == 'youtube' and it['capa_status'] in ('pronta', 'a_gerar'):
        db.add_job(con, canal['nome'], 'capa', db.agora(), json.dumps({'item_id': it['id']}), f"capa:{it['id']}")
    log(f'{rot}: feito {url}')
    return str(ref)


def _tratar_falha(con, canal, e, f, tent, rot, log):
    msg = str(f)
    log(f'{rot}: falha {f.tipo}: {msg}')
    if f.tipo in PAUSA:
        retomar = (datetime.now() + PAUSA[f.tipo]).strftime('%Y-%m-%d %H:%M:%S')
        db.concluir(con, e['id'], 'aguardando', 'Destino pausado; o vídeo continua na fila', devolver=True)
        db.pausar_destino(con, canal['nome'], e['destino'], msg, retomar)
        avisar(f"{canal['nome']}: {e['destino']} pausado até {retomar[:16]} ({f.tipo}). A fila foi preservada.", log)
    elif f.tipo == FORMATO:
        db.concluir(con, e['id'], 'ignorado', msg)
    elif f.tipo == AMBIGUO:
        db.concluir(con, e['id'], 'conferir', msg)
        avisar(f"{canal['nome']}: envio {e['id']} precisa de conferência.", log)
    elif f.tipo == DEFINITIVO or tent >= int(canal['max_tentativas']):
        db.concluir(con, e['id'], 'erro', msg)
    else:
        db.concluir(con, e['id'], 'aguardando', msg)
    return f.tipo


def fazer_capa(con, canal, item_id, simular, log=print):
    it = db.item(con, item_id)
    e = con.execute("SELECT * FROM entregas WHERE item_id=? AND destino='youtube' AND status='feito'", (item_id,)).fetchone()
    if not e:
        return 'vídeo ainda não publicado'
    if simular:
        return 'simulado'
    try:
        capa = it['capa'] or gerar_capa(canal['nome'], it['titulo'], it['descricao'], it['pasta'])
        definir_capa(e['ref'], capa, canal['config_dir'])
        con.execute("UPDATE itens SET capa=?, capa_status='aplicada', capa_motivo='' WHERE id=?", (capa, item_id))
        return 'capa aplicada'
    except Exception as x:
        con.execute("UPDATE itens SET capa_status='pendente', capa_motivo=? WHERE id=?", (str(x)[:300], item_id))
        avisar(f"{canal['nome']}: vídeo publicado sem capa ({it['titulo'][:50]}).", log)
        return 'capa pendente'


def faixa(job):
    if job['tipo'] in ('publicar', 'publicar_entrega'):
        return 'youtube' if json.loads(job['payload']).get('destino') == 'youtube' else 'rs'
    return FAIXAS.get(job['tipo'], 'geral')


def executar(con, job, canais, simular, log=print):
    """Roda um job já reivindicado e sempre o encerra."""
    p = json.loads(job['payload'] or '{}')
    canal = canais.get(job['canal'])
    try:
        if not canal:
            raise RuntimeError('canal não existe')
        t = job['tipo']
        if not canal['ativo']:
            if t == 'capa':
                con.execute("UPDATE itens SET capa_status='pendente', capa_motivo='Canal desligado' WHERE id=?", (p['item_id'],))
            if t == 'publicar_entrega':
                db.apagar_job(con, job['id'])
                return 'canal inativo'
            db.fim_job(con, job['id'], True, 'canal inativo')
            return 'canal inativo'
        if t in ('sync_lives', 'cortar') and not canal['cortes']['ligado']:
            db.fim_job(con, job['id'], True, 'cortes desligados')
            return 'cortes desligados'
        if t == 'entrada':
            r = f'{entrada.varrer(con, canal, log, ESCREVER, simular)} novo(s)'
        elif t == 'publicar':
            pode, motivo = disponivel(con, canal, p['destino'])
            e = db.proxima(con, canal['nome'], p['destino']) if pode else None
            r = motivo or ('fila vazia' if not e else publicar_entrega(con, canal, e, simular, log))
        elif t == 'publicar_entrega':
            e = db.entrega(con, p['entrega_id'])
            r = publicar_entrega(con, canal, e, simular, log) if e and e['status'] == 'aguardando' else 'sem efeito'
            agora_e = db.entrega(con, p['entrega_id'])
            if e and agora_e and agora_e['status'] == 'aguardando' and agora_e['atualizado_em'] == e['atualizado_em']:
                db.apagar_job(con, job['id'])  # não tentou de verdade: precisa poder voltar depois
                return r
        elif t == 'capa':
            r = fazer_capa(con, canal, p['item_id'], simular, log)
        elif t == 'sync_lives':
            r = 'simulado' if simular else f'{cortes.sincronizar(con, canal, LISTAR_LIVES)} nova(s)'
        elif t == 'cortar':
            r = 'simulado' if simular else cortes.cortar_proxima(con, canal, CORTAR, log)
        else:
            raise RuntimeError(f'job desconhecido: {t}')
        db.fim_job(con, job['id'], True, r)
        return r
    except Exception as x:
        db.fim_job(con, job['id'], False, f'{type(x).__name__}: {x}')
        log(f"job {job['id']} falhou: {x}")
        return None
