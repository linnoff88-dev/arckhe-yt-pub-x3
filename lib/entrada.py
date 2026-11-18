"""Entrada: entrada/<canal>/<pasta>/ com arquivos + post.json + pronto vira item na fila."""
import fcntl
import json
import os
import re
import shutil
import time
from datetime import datetime

from . import config, db, ia, metricool, midia

VIDEO = ('.mp4', '.mov', '.mkv', '.webm')
IMAGEM = ('.jpg', '.jpeg', '.png', '.webp')
RESERVADOS = {'post.json', 'pronto', 'capa.jpg', 'capa.jpeg', 'capa.png', 'legenda.srt', 'legenda-rs.txt'}
MAX_IMAGENS = 20


class Recusa(Exception):
    pass


class Adiar(Exception):
    """A pasta está certa, mas agora não dá para processar: fica na entrada."""


def _quando(v):
    v = str(v or 'fila').strip()
    if v in ('fila', 'agora'):
        return v
    try:
        return datetime.strptime(v, '%Y-%m-%d %H:%M').strftime('%Y-%m-%d %H:%M')
    except ValueError:
        raise Recusa(f'quando inválido: {v}') from None


def _midias(pasta):
    nomes = [n for n in sorted(os.listdir(pasta)) if n.lower() not in RESERVADOS and not n.startswith('.')]
    return ([n for n in nomes if n.lower().endswith(VIDEO)], [n for n in nomes if n.lower().endswith(IMAGEM)])


def ja_no_ytpubx(canal, sha, arquivo):
    """Mesma regra do yt-pubx: sha256; sem sha, compara com o arquivo de origem. Vídeo removido não conta."""
    regs, removidos, cache = [], set(), {}
    try:
        with open(config.historico_ytpubx(), encoding='utf-8') as f:
            for linha in f:
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if d.get('removido'):
                    removidos.add(d['removido'])
                elif d.get('canal') == canal:
                    regs.append(d)
    except OSError:
        return False
    tam = os.path.getsize(arquivo)
    for d in regs:
        if d.get('video_id') in removidos:
            continue
        if d.get('sha256'):
            if d['sha256'] == sha:
                return True
            continue
        o = os.path.expanduser(d.get('origem') or '')
        if o and os.path.isfile(o) and os.path.getsize(o) == tam:
            if o not in cache:
                cache[o] = midia.sha256([o])
            if cache[o] == sha:
                return True
    return False


def _sem_links(pasta):
    if os.path.islink(pasta):
        raise Recusa('a pasta não pode ser um link')
    real = os.path.realpath(pasta)
    for n in os.listdir(pasta):
        p = os.path.join(pasta, n)
        if os.path.islink(p) or not os.path.realpath(p).startswith(real + os.sep):
            raise Recusa(f'link não permitido: {n}')


def criar_entregas(con, item_id, canal, pede):
    """Uma entrega por destino que faz sentido para o tipo do item."""
    it = db.item(con, item_id)
    nome = canal['nome']
    if 'youtube' in pede and it['tipo'] in ('video', 'clip'):
        db.add_entrega(con, item_id, nome, 'youtube')
    if 'rs' in pede:
        rs = canal['rs']
        motivo = 'Canal sem RS' if not rs['provedor'] else (metricool.formato(it, rs) if rs['provedor'] == 'metricool' else '')
        db.add_entrega(con, item_id, nome, 'rs', 'ignorado' if motivo else 'aguardando', motivo)


def capa_inicial(tipo, capa, l, a, d):
    if tipo not in ('video', 'clip') or midia.eh_short(l, a, d):
        return 'nao_leva'
    return 'pronta' if capa else 'a_gerar'


def enfileirar_pasta(con, canal, origem, escrever=None, simular=False):
    """Valida a pasta e cria o item. Levanta Recusa com o motivo. Retorna o id do item."""
    escrever = escrever or ia.escrever_textos
    nome = canal['nome']
    _sem_links(origem)
    try:
        with open(os.path.join(origem, 'post.json'), encoding='utf-8') as f:
            p = json.load(f)
        if not isinstance(p, dict):
            raise ValueError
    except (OSError, ValueError):
        raise Recusa('post.json ausente ou inválido') from None
    tipo = p.get('tipo')
    videos, imagens = _midias(origem)
    if tipo == 'video':
        if len(videos) != 1 or imagens:
            raise Recusa('vídeo precisa de exatamente 1 arquivo de vídeo')
        midias = videos
    elif tipo == 'foto':
        if len(imagens) != 1 or videos:
            raise Recusa('foto precisa de exatamente 1 imagem')
        midias = imagens
    elif tipo == 'carrossel':
        if not 2 <= len(imagens) <= MAX_IMAGENS or videos:
            raise Recusa(f'carrossel precisa de 2 a {MAX_IMAGENS} imagens')
        midias = imagens
    else:
        raise Recusa('tipo deve ser video, foto ou carrossel')
    quando = _quando(p.get('quando'))
    pede = p.get('destinos') or (['youtube', 'rs'] if tipo == 'video' else ['rs'])
    if not isinstance(pede, list) or not pede or any(d not in ('youtube', 'rs') for d in pede):
        raise Recusa('destinos deve ter youtube e/ou rs')
    privacy = p.get('privacy') or canal['youtube']['privacy']
    if privacy not in ('public', 'unlisted', 'private'):
        raise Recusa('privacy inválido')
    if not isinstance(p.get('tags') or [], (list, str)):
        raise Recusa('tags inválidas')
    caminhos = [os.path.join(origem, n) for n in midias]
    if any(not os.path.getsize(c) for c in caminhos):
        raise Recusa('arquivo vazio')
    sha = midia.sha256(caminhos)
    if db.ja_existe(con, nome, sha) or (tipo == 'video' and ja_no_ytpubx(nome, sha, caminhos[0])):
        raise Recusa('arquivo repetido neste canal')
    l, a, d = midia.probe(caminhos[0]) if tipo == 'video' else (0, 0, 0)
    if tipo == 'video' and not (l and a):
        raise Recusa('não consegui ler o vídeo')
    titulo, descricao, texto = [str(p.get(k) or '').strip() for k in ('titulo', 'descricao', 'texto_rs')]
    tags = p.get('tags') or []
    falta = (not (titulo and descricao)) if tipo == 'video' else (not texto)
    if falta:
        contexto = str(p.get('contexto') or '').strip()
        if not contexto:
            raise Recusa('faltam os textos e o contexto para escrevê-los')
        if simular:
            raise Adiar('em simulação a IA não escreve textos')
        marca = os.path.join(origem, '.falha-ia')
        if os.path.exists(marca) and time.time() - os.path.getmtime(marca) < 1800:
            raise Adiar('IA falhou há pouco; tenta de novo em 30 min')
        try:
            g = escrever(nome, tipo, contexto, caminhos[0] if tipo == 'video' else '', titulo, descricao)
        except Exception as e:
            open(marca, 'w').close()
            raise Adiar(f'Codex não escreveu os textos: {e}') from None
        titulo, descricao = titulo or g.get('titulo', ''), descricao or g.get('descricao', '')
        texto, tags = texto or g.get('texto_rs', ''), tags or g.get('tags', [])
    if tipo == 'video' and not (titulo and descricao):
        raise Recusa('título ou descrição vazios')
    if tipo != 'video' and not texto:
        raise Recusa('texto_rs vazio')
    if isinstance(tags, list):
        tags = ','.join(str(t) for t in tags)
    arq_capa = next((n for n in sorted(os.listdir(origem)) if n.lower().startswith('capa.') and n.lower().endswith(IMAGEM)), '')
    base = re.sub(r'[^\w.-]+', '-', os.path.basename(origem.rstrip('/')))[:60]
    destino = os.path.join(config.acervo_dir(), nome, f"{datetime.now():%Y%m%d-%H%M%S}-{sha[:8]}-{base}")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    arquivos = [os.path.join(destino, n) for n in midias]
    capa = os.path.join(destino, arq_capa) if arq_capa else ''
    leg = os.path.join(destino, 'legenda.srt')
    tem_leg = os.path.exists(os.path.join(origem, 'legenda.srt'))
    con.execute('BEGIN IMMEDIATE')
    try:
        item_id = db.add_item(con, canal=nome, tipo=tipo, pasta=destino, arquivos=json.dumps(arquivos), titulo=titulo,
                              descricao=descricao, texto_rs=texto, tags=str(tags), privacy=privacy, capa=capa,
                              capa_status=capa_inicial(tipo, capa, l, a, d), legenda=leg if tem_leg else '',
                              sha256=sha, origem=str(p.get('origem') or 'entrada'), quando=quando,
                              largura=l, altura=a, duracao=d)
        criar_entregas(con, item_id, canal, list(dict.fromkeys(pede)))
        shutil.move(origem, destino)
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        if os.path.exists(destino) and not os.path.exists(origem):
            shutil.move(destino, origem)
        raise
    return item_id


def _guardar_recusada(pasta, canal):
    alvo = os.path.join(config.recusados_dir(), canal, f"{datetime.now():%Y%m%d-%H%M%S}-{os.path.basename(pasta)}")
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    shutil.move(pasta, alvo)
    return alvo


def varrer(con, canal, log=print, escrever=None, simular=False):
    raiz = os.path.join(config.entrada_dir(), canal['nome'])
    if not os.path.isdir(raiz):
        return 0
    trava = open(f"{config.db_path()}.entrada-{canal['nome']}.lock", 'w')
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        trava.close()
        return 0  # outra varredura do canal ainda está rodando
    novos = 0
    try:
        for n in sorted(os.listdir(raiz)):
            pasta = os.path.join(raiz, n)
            if n.startswith(('.', '_')) or not os.path.lexists(os.path.join(pasta, 'pronto')):
                continue
            try:
                item_id = enfileirar_pasta(con, canal, pasta, escrever, simular)
                novos += 1
                log(f"[{canal['nome']}] na fila: item {item_id} ({n})")
            except Adiar as e:
                log(f"[{canal['nome']}] adiado {n}: {e}")
            except Exception as e:
                motivo = str(e) if isinstance(e, Recusa) else f'pasta inválida: {type(e).__name__}: {e}'
                alvo = _guardar_recusada(pasta, canal['nome'])
                db.add_recusado(con, canal['nome'], alvo, motivo)
                log(f"[{canal['nome']}] recusado {n}: {motivo}")
    finally:
        trava.close()
    return novos
