#!/usr/bin/env python3
"""Ponte para as funções de texto e capa do yt-pubx. Só lê o yt-pubx; recebe JSON no stdin."""
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
from types import SimpleNamespace

ARQ = os.path.expanduser('~/projetos/yt-pubx/yt-pubx')
sys.path.insert(0, os.path.dirname(ARQ))
sys.dont_write_bytecode = True
carregador = importlib.machinery.SourceFileLoader('ytpubx_x3', ARQ)
spec = importlib.util.spec_from_loader('ytpubx_x3', carregador)
yp = importlib.util.module_from_spec(spec)
carregador.exec_module(yp)

p = json.load(sys.stdin)
cfg = yp.load_config()
nome, c = yp.canal(cfg, p['canal'])
modelo = cfg.get('codex_modelo', '')
pasta = p.get('pasta') or os.getcwd()

if p['acao'] == 'capa':
    assunto = f"{p['titulo']}. {p.get('descricao', '')[:400]}"
    frase = ' '.join(re.sub(r'[^\w\s]', ' ', p['titulo']).split()[:4]).upper()
    arte = yp.arte_codex(f'Cena sobre o assunto, com o sujeito principal à direita e espaço escuro à esquerda: {assunto}', pasta, modelo)
    saida = os.path.join(pasta, 'capa-codex.jpg')
    yp.compor_thumb(arte, frase, c.get('thumb', {}), saida)
    print(json.dumps({'capa': saida}))
elif p['tipo'] in ('foto', 'carrossel'):
    txt = yp.codex('Escreva o post de rede social em português do Brasil. Responda SOMENTE JSON com "titulo" (até 90 '
                   'caracteres) e "texto_rs" (até 900 caracteres, sem links, termina com 3 a 5 hashtags).\n\nContexto:\n'
                   + p['contexto'], pasta, modelo)
    print(json.dumps(json.loads(re.search(r'\{.*\}', txt, re.S).group(0)), ensure_ascii=False))
else:
    a = SimpleNamespace(contexto=p['contexto'], contexto_arquivo=None, legenda=None, title=p.get('titulo') or None,
                        description=p.get('descricao') or None, idioma='pt')
    d = yp.gerar_metadados(a, c, p['video'], yp.duracao(p['video']), pasta, modelo)
    print(json.dumps({'titulo': d['titulo'], 'descricao': d['descricao'], 'tags': d.get('tags', [])}, ensure_ascii=False))
