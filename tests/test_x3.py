"""Testes só com publicadores falsos e pastas temporárias: nada toca canal real."""
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'dashboard'))
import hub  # noqa: E402
import server  # noqa: E402
from lib import canais, cortes, db, entrada, importar, metricool, midia, painel, runner, youtube  # noqa: E402
from lib.falhas import AMBIGUO, AUTH, COTA, DEFINITIVO, TEMPORARIO, Falha  # noqa: E402

VERT = (1080, 1920, 55.0)
DEIT = (1920, 1080, 179.0)


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='x3-teste-')
        self.addCleanup(shutil.rmtree, self.t, True)
        amb = {'X3_DB': f'{self.t}/d/x3.db', 'X3_ENTRADA': f'{self.t}/entrada', 'X3_CANAIS': f'{self.t}/canais', 'X3_ACERVO': f'{self.t}/acervo',
               'X3_RECUSADOS': f'{self.t}/rec', 'X3_HISTORICO_YTPUBX': f'{self.t}/hist.jsonl', 'X3_LEGADO': f'{self.t}/legado', 'X3_PUBLICAR': '1'}
        p = mock.patch.dict(os.environ, amb)
        p.start()
        self.addCleanup(p.stop)
        self.dims = {}
        p = mock.patch.object(midia, 'probe', lambda f: self.dims.get(os.path.basename(f), VERT))
        p.start()
        self.addCleanup(p.stop)
        self.yt, self.rs = [], []
        self.falha_yt, self.falha_rs = None, None
        p = mock.patch.dict(runner.PUBLICADORES, {'youtube': self.pub_yt, 'rs': self.pub_rs})
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(runner, 'avisar', lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)
        self.con = db.connect()
        self.hm = datetime.now().strftime('%H:%M')
        self.canal()
        self.n = 0

    def pub_yt(self, canal, item, log=print):
        if self.falha_yt:
            raise self.falha_yt
        self.yt.append(item['id'])
        return 'vid%d' % item['id'], 'https://youtu.be/%d' % item['id']

    def pub_rs(self, canal, item, log=print):
        if self.falha_rs:
            raise self.falha_rs
        self.rs.append(item['id'])
        return 'FTD', 'https://planner/%d' % item['id']

    def canal(self, nome='lives3', **extra):
        c = {'ativo': True, 'config_dir': f'{self.t}/cfg', 'lives_dir': f'{self.t}/lives', 'origem_id': 'UCx',
             'youtube': {'horarios': [self.hm]}, 'rs': {'provedor': 'metricool', 'ligado': True, 'marca': 'FTD', 'redes': ['tiktok', 'instagram']}}
        c.update(extra)
        canais.salvar(canais.normaliza(nome, c), sobrescrever=True)

    def c(self, nome='lives3'):
        return canais.carregar()[nome]

    def pasta(self, nome=None, tipo='video', arquivos=None, pronto=True, canal='lives3', **post):
        self.n += 1
        nome = nome or f'p{self.n}'
        d = f'{self.t}/entrada/{canal}/{nome}'
        os.makedirs(d)
        for a in arquivos or (['video.mp4'] if tipo == 'video' else ['foto.jpg'] if tipo == 'foto' else ['01.jpg', '02.jpg']):
            with open(f'{d}/{a}', 'w') as f:
                f.write(f'{nome}-{a}')
        p = {'tipo': tipo, **({'titulo': f'T{self.n}', 'descricao': 'D'} if tipo == 'video' else {'titulo': 'T', 'texto_rs': 'Texto'}), **post}
        with open(f'{d}/post.json', 'w') as f:
            json.dump(p, f)
        if pronto:
            open(f'{d}/pronto', 'w').close()
        return d

    def varrer(self):
        return entrada.varrer(self.con, self.c(), log=lambda m: None)

    def rodar(self, destino):
        return runner.executar(self.con, self.job('publicar', {'destino': destino}), canais.carregar(), False, lambda m: None)

    def job(self, tipo, p):
        j = db.add_job(self.con, 'lives3', tipo, db.agora(), json.dumps(p), f'{tipo}:{self.id()}:{os.urandom(4).hex()}')
        db.reivindicar_job(self.con, j)
        return self.con.execute('SELECT * FROM jobs WHERE id=?', (j,)).fetchone()

    def st(self, item=1, destino='youtube'):
        return self.con.execute('SELECT * FROM entregas WHERE item_id=? AND destino=?', (item, destino)).fetchone()


class Falhas(Base):
    def _pausa(self, tipo):
        self.pasta(); self.pasta(); self.varrer()
        self.falha_yt = Falha('caiu', tipo)
        self.assertEqual(self.rodar('youtube'), tipo)
        e = self.st()
        self.assertEqual((e['status'], e['tentativas']), ('aguardando', 0))
        self.assertTrue(db.estado_destino(self.con, 'lives3', 'youtube')['retomar_em'])
        self.rodar('rs')
        self.assertEqual(self.rs, [1])
        self.assertEqual(self.st(1, 'rs')['status'], 'feito')
        self.assertEqual(self.rodar('youtube'), runner.disponivel(self.con, self.c(), 'youtube')[1])
        self.assertEqual(self.st(2)['status'], 'aguardando')
        self.falha_yt = None
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        self.rodar('youtube')
        self.assertEqual(self.yt, [1])

    def test_auth_caida_preserva_fila_e_rs_sai(self):
        self._pausa(AUTH)

    def test_cota_preserva_fila_e_rs_sai(self):
        self._pausa(COTA)

    def test_rs_falha_e_youtube_segue(self):
        self.pasta(); self.varrer()
        self.falha_rs = Falha('x', DEFINITIVO)
        self.rodar('rs'); self.rodar('youtube')
        self.assertEqual(self.st(1, 'rs')['status'], 'erro')
        self.assertEqual(self.st()['status'], 'feito')

    def test_temporaria_para_no_limite(self):
        self.pasta(); self.varrer()
        self.falha_yt = Falha('rede', TEMPORARIO)
        for _ in range(3):
            self.rodar('youtube')
        self.assertEqual((self.st()['status'], self.st()['tentativas']), ('erro', 3))

    def test_ambiguo_vai_para_conferir(self):
        self.pasta(); self.varrer()
        self.falha_yt = Falha('caiu no upload', AMBIGUO)
        self.rodar('youtube')
        self.assertEqual(self.st()['status'], 'conferir')
        self.assertEqual(self.rodar('youtube'), 'fila vazia')

    def test_queda_no_meio_nao_reenvia(self):
        self.pasta(); self.varrer()
        db.reivindicar(self.con, self.st()['id'])
        self.assertEqual(db.recuperar_interrompidos(self.con), 1)
        self.assertEqual(self.st()['status'], 'conferir')
        self.assertEqual(self.rodar('youtube'), 'fila vazia')
        self.assertEqual(self.yt, [])

    def test_classificacao_http(self):
        self.assertEqual(youtube.classifica_http(401, ''), AUTH)
        self.assertEqual(youtube.classifica_http(403, '"reason":"uploadLimitExceeded"'), COTA)
        self.assertEqual(youtube.classifica_http(403, '"reason":"quotaExceeded"'), COTA)
        self.assertEqual(youtube.classifica_http(503, ''), TEMPORARIO)
        self.assertEqual(youtube.classifica_http(400, ''), DEFINITIVO)


class Entrada(Base):
    def test_sem_pronto_ignorada(self):
        d = self.pasta(pronto=False)
        self.assertEqual(self.varrer(), 0)
        self.assertTrue(os.path.isdir(d))

    def test_repetido_recusado(self):
        self.pasta('a'); self.varrer()
        d = self.pasta('b')
        shutil.copy(f"{json.loads(db.item(self.con, 1)['arquivos'])[0]}", f'{d}/video.mp4')
        self.assertEqual(self.varrer(), 0)
        self.assertIn('repetido', self.con.execute('SELECT motivo FROM recusados').fetchone()[0])
        self.assertFalse(os.path.exists(d))

    def test_repetido_no_ytpubx(self):
        d = self.pasta()
        sha = midia.sha256([f'{d}/video.mp4'])
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'sha256': sha}) + '\n')
        self.assertEqual(self.varrer(), 0)

    def test_carrossel_nao_gasta_youtube(self):
        self.pasta(tipo='carrossel'); self.pasta(tipo='foto'); self.pasta(); self.varrer()
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM entregas WHERE destino='youtube'").fetchone()[0], 1)
        self.rodar('youtube')
        self.assertEqual(self.yt, [3])
        self.rodar('rs')
        self.assertEqual(self.rs, [1])

    def test_16_9_ignorado_na_rs(self):
        self.dims['h.mp4'] = DEIT
        self.pasta(arquivos=['h.mp4']); self.varrer()
        self.assertEqual(self.st(1, 'rs')['status'], 'ignorado')
        self.assertEqual(self.st()['status'], 'aguardando')
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'a_gerar')

    def test_short_nao_leva_capa(self):
        self.pasta(); self.varrer()
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'nao_leva')

    def test_contexto_escreve_textos(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'sobre IA'}, open(f'{d}/post.json', 'w'))
        n = entrada.varrer(self.con, self.c(), lambda m: None, lambda *a: {'titulo': 'Novo', 'descricao': 'Desc', 'tags': ['ia']})
        self.assertEqual(n, 1)
        self.assertEqual(db.item(self.con, 1)['titulo'], 'Novo')

    def test_invalidos(self):
        self.pasta(tipo='outro', arquivos=['a.jpg']); self.pasta(tipo='carrossel', arquivos=['1.jpg'])
        self.pasta(quando='amanhã')
        self.assertEqual(self.varrer(), 0)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 3)


class Hub(Base):
    def test_simulacao_nao_publica(self):
        self.pasta()
        with mock.patch.dict(os.environ, {'X3_PUBLICAR': ''}):
            hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual((self.yt, self.rs), ([], []))
        self.assertEqual(self.st()['status'], 'aguardando')

    def test_canal_inativo_nao_roda(self):
        self.canal(ativo=False); self.pasta()
        self.assertEqual(hub.ciclo(self.con), 0)
        self.assertTrue(os.path.isdir(f'{self.t}/entrada/lives3/p1'))

    def test_horario_publica_um_por_destino(self):
        self.pasta(); self.pasta(); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])
        self.assertEqual(self.rs, [1])

    def test_agora_fura_a_fila(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(); self.pasta(quando='agora'); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [2])

    def test_data_futura_espera(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='2099-01-01 10:00'); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [])

    def test_destino_desligado(self):
        db.definir_ligado(self.con, 'lives3', 'youtube', False)
        self.pasta(); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [])
        self.assertEqual(self.rs, [1])

    def test_acoes(self):
        self.pasta(); self.varrer()
        e = self.st()['id']
        self.assertTrue(db.acao(self.con, e, 'pausar'))
        self.assertEqual(self.rodar('youtube'), 'fila vazia')
        self.assertTrue(db.acao(self.con, e, 'retomar'))
        self.assertTrue(db.acao(self.con, e, 'pular'))
        self.assertTrue(db.acao(self.con, e, 'reenviar'))
        self.assertFalse(db.acao(self.con, e, 'confirmar'))


class Capa(Base):
    def _pub(self):
        self.dims['h.mp4'] = DEIT
        self.pasta(arquivos=['h.mp4']); self.varrer(); self.rodar('youtube')

    def test_codex_falha_publica_e_fica_pendente(self):
        self._pub()
        with mock.patch.object(runner, 'gerar_capa', side_effect=RuntimeError('sem codex')):
            self.assertEqual(runner.fazer_capa(self.con, self.c(), 1, False, lambda m: None), 'capa pendente')
        self.assertEqual(self.st()['status'], 'feito')
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'pendente')

    def test_capa_aplicada(self):
        self._pub()
        with mock.patch.object(runner, 'gerar_capa', return_value='c.jpg'), mock.patch.object(runner, 'definir_capa') as d:
            runner.fazer_capa(self.con, self.c(), 1, False, lambda m: None)
        d.assert_called_once()
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'aplicada')


class Cortes(Base):
    def setUp(self):
        super().setUp()
        self.canal(cortes={'ligado': True, 'horarios': [self.hm], 'max_por_dia': 1})

    def _cortar(self, canal, vid, log=print):
        d = f"{canal['lives_dir']}/{vid}"
        os.makedirs(f'{d}/clips')
        m = []
        for i in (1, 2):
            f = f'{d}/clips/c{i}.mp4'
            open(f, 'w').write(f'{vid}{i}')
            m.append({'index': i, 'file': f, 'title': f'C{i}', 'description': 'D', 'tags': ['a'], 'duration': 300})
            self.dims[f'c{i}.mp4'] = (1920, 1080, 300)
        json.dump(m, open(f'{d}/clips_manifest.json', 'w'))

    def test_corte_gera_clipes_na_fila(self):
        self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3','L1','2026-01-01')")
        self.assertIn('2 clipes', cortes.cortar_proxima(self.con, self.c(), self._cortar))
        self.assertEqual(self.con.execute("SELECT tipo,origem FROM itens").fetchone()[:2], ('clip', 'live:L1'))
        self.assertEqual(self.st(1, 'rs')['status'], 'ignorado')
        self.assertEqual(self.st()['status'], 'aguardando')

    def test_limite_por_dia(self):
        for v in ('L1', 'L2'):
            self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3',?,'2026-01-01')", (v,))
        cortes.cortar_proxima(self.con, self.c(), self._cortar)
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), self._cortar), 'limite do dia')

    def test_historico_nao_recorta(self):
        os.makedirs(f'{self.t}/legado/yt-pub-lives3/data')
        v = sqlite3.connect(f'{self.t}/legado/yt-pub-lives3/data/lives.db')
        v.execute('CREATE TABLE lives(video_id,titulo,data_live,status_cortes,qtd_clips)')
        v.execute("INSERT INTO lives VALUES('L1','t','2026-01-01','concluido',3),('import_x','t','','concluido',1)")
        v.commit(); v.close()
        self.assertEqual(cortes.importar_historico(self.con, self.c()), 1)
        cortes.sincronizar(self.con, self.c(), lambda *a: [{'video_id': 'L1', 'titulo': 't', 'data_live': '2026-01-01'}])
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), self._cortar), 'nenhuma live pendente')

    def test_erro_no_corte(self):
        self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3','L1','2026-01-01')")
        def ruim(*a):
            raise RuntimeError('falhou')
        cortes.cortar_proxima(self.con, self.c(), ruim)
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'erro')


class Revisao(Base):
    """Defeitos achados na revisão independente de 18/11/2026."""

    def test_400_com_limite_pausa(self):
        self.assertEqual(youtube.classifica_http(400, '"reason":"uploadLimitExceeded"'), COTA)

    def test_5xx_depois_do_envio_e_ambiguo(self):
        erro = urllib.error.HTTPError('u', 503, 'x', {}, __import__('io').BytesIO(b'{}'))
        with mock.patch('urllib.request.urlopen', side_effect=erro):
            with self.assertRaises(Falha) as c:
                youtube._http(urllib.request.Request('http://x'), apos_envio=True)
        self.assertEqual(c.exception.tipo, AMBIGUO)

    def _legado(self, status):
        os.makedirs(f'{self.t}/legado/yt-pub-lives3/data', exist_ok=True)
        v = sqlite3.connect(f'{self.t}/legado/yt-pub-lives3/data/lives.db')
        v.execute('CREATE TABLE IF NOT EXISTS lives(video_id,titulo,data_live,status_cortes,qtd_clips)')
        v.execute('DELETE FROM lives')
        v.execute("INSERT INTO lives VALUES('L1','t','2026-01-01',?,0)", (status,))
        v.commit(); v.close()

    def test_live_cortada_pelo_antigo_nao_recorta(self):
        self._legado('pendente')
        cortes.importar_historico(self.con, self.c())
        self._legado('concluido')
        chamou = []
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), lambda *a: chamou.append(1)), 'nenhuma live pendente')
        self.assertEqual(chamou, [])
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'cortada')

    def test_reimportar_atualiza_pendente(self):
        self._legado('pendente'); cortes.importar_historico(self.con, self.c())
        self._legado('concluido'); cortes.importar_historico(self.con, self.c())
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'cortada')

    def test_repetido_sem_sha_pelo_arquivo_de_origem(self):
        d = self.pasta()
        o = f'{self.t}/origem.mp4'
        shutil.copy(f'{d}/video.mp4', o)
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'video_id': 'v', 'origem': o}) + '\n')
        self.assertEqual(self.varrer(), 0)

    def test_video_removido_nao_conta_como_repetido(self):
        d = self.pasta()
        sha = midia.sha256([f'{d}/video.mp4'])
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'video_id': 'v', 'sha256': sha}) + '\n' + json.dumps({'removido': 'v'}) + '\n')
        self.assertEqual(self.varrer(), 1)

    def test_hub_parado_nao_solta_horarios(self):
        for _ in range(3):
            self.pasta()
        self.varrer()
        for i in range(3):
            db.add_job(self.con, 'lives3', 'publicar', '2020-01-01 08:00:00', json.dumps({'destino': 'youtube'}), f'velho{i}')
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        hub.ciclo(self.con)
        self.assertEqual(self.yt, [])

    def test_agora_volta_depois_da_pausa(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='agora'); self.varrer()
        db.pausar_destino(self.con, 'lives3', 'youtube', 'x', '2099-01-01 00:00:00')
        e = self.st()
        j = self.job('publicar_entrega', {'entrega_id': e['id'], 'destino': 'youtube'})
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        db.pausar_destino(self.con, 'lives3', 'youtube', 'x', '2099-01-01 00:00:00')
        runner.executar(self.con, j, canais.carregar(), False, lambda m: None)
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])

    def test_simulacao_nao_prende_item_agora(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='agora')
        with mock.patch.dict(os.environ, {'X3_PUBLICAR': ''}):
            hub.ciclo(self.con); hub.ciclo(self.con)
        hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])

    def test_post_malformado_nao_trava_nem_some(self):
        self.pasta(destinos=[['x']]); self.pasta(privacy=['x']); self.pasta()
        self.assertEqual(self.varrer(), 1)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 2)
        self.assertEqual(len(os.listdir(f'{self.t}/acervo/lives3')), 1)

    def test_canal_desligado_nao_corta(self):
        self.canal(ativo=False, cortes={'ligado': True, 'horarios': [self.hm]})
        j = self.job('cortar', {})
        with mock.patch.object(runner, 'CORTAR', side_effect=AssertionError):
            self.assertEqual(runner.executar(self.con, j, canais.carregar(), False, lambda m: None), 'canal inativo')

    def test_simulacao_nao_gasta_ia(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'x'}, open(f'{d}/post.json', 'w'))
        chamou = []
        n = entrada.varrer(self.con, self.c(), lambda m: None, lambda *a: chamou.append(1), True)
        self.assertEqual((n, chamou, os.path.isdir(d)), (0, [], True))

    def test_codex_fora_mantem_pasta(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'x'}, open(f'{d}/post.json', 'w'))
        def ruim(*a):
            raise RuntimeError('sem limite')
        entrada.varrer(self.con, self.c(), lambda m: None, ruim)
        self.assertTrue(os.path.isdir(d))
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 0)

    def test_link_simbolico_recusado(self):
        d = self.pasta(tipo='foto')
        s = f'{self.t}/segredo'
        open(s, 'w').write('x')
        os.remove(f'{d}/foto.jpg'); os.symlink(s, f'{d}/foto.jpg')
        self.assertEqual(self.varrer(), 0)
        self.assertIn('link', self.con.execute('SELECT motivo FROM recusados').fetchone()[0])


class ConectorMetricool(Base):
    def _script(self, codigo, saida=''):
        p = f'{self.t}/pub.sh'
        with open(p, 'w') as f:
            f.write(f'#!/bin/bash\necho "$MARCA|$REDES|$1|$2|$3" > {self.t}/args\necho "{saida}"\nexit {codigo}\n')
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        return p

    def _item(self):
        self.pasta(); self.varrer()
        return db.item(self.con, 1)

    def test_ok_envia_marca_e_redes(self):
        with mock.patch.dict(os.environ, {'X3_METRICOOL_VIDEO': self._script(0, 'Metricool: https://app/x')}):
            ref, url = metricool.publicar(self.c(), self._item())
        self.assertEqual((ref, url), ('FTD', 'https://app/x'))
        self.assertTrue(open(f'{self.t}/args').read().startswith('FTD|tiktok,instagram|'))

    def test_saidas(self):
        it = self._item()
        for cod, tipo in ((2, 'formato'), (1, 'temporario')):
            with mock.patch.dict(os.environ, {'X3_METRICOOL_VIDEO': self._script(cod)}):
                with self.assertRaises(Falha) as c:
                    metricool.publicar(self.c(), it)
            self.assertEqual(c.exception.tipo, tipo)

    def test_legenda_estavel(self):
        it = self._item()
        p = metricool.legenda(it)
        a = open(p).read()
        self.assertEqual(metricool.legenda(it), p)
        self.assertEqual(open(p).read(), a)

    def test_scripts_validos(self):
        self.assertEqual(os.system(f"bash -n {RAIZ}/scripts/metricool-imagens.sh"), 0)


class Painel(Base):
    def setUp(self):
        super().setUp()
        painel._cache.update(t=0, v={})
        self.s = server.criar(0)
        self.base = f'http://127.0.0.1:{self.s.server_address[1]}'
        threading.Thread(target=self.s.serve_forever, daemon=True).start()
        self.addCleanup(self.s.server_close)
        self.addCleanup(self.s.shutdown)

    def req(self, caminho, metodo='GET', cab=None):
        r = urllib.request.Request(self.base + caminho, method=metodo, headers=cab or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as x:
                return x.status, x.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_escuta_so_local(self):
        self.assertEqual(self.s.server_address[0], '127.0.0.1')

    def test_estado_e_acao(self):
        self.pasta(); self.varrer()
        c, b = self.req('/api/estado')
        self.assertEqual(json.loads(b)['canais'][0]['nome'], 'lives3')
        e = self.st()['id']
        self.assertEqual(self.req(f'/api/entrega/{e}/pausar', 'POST')[0], 403)
        self.assertEqual(self.req(f'/api/entrega/{e}/pausar', 'POST', {'X-X3': '1'})[0], 200)
        self.assertEqual(self.st()['status'], 'pausado')
        self.assertEqual(len(json.loads(self.req('/api/canal/lives3')[1])['itens']), 1)

    def test_host_estranho_recusado(self):
        self.assertEqual(self.req('/api/estado', cab={'Host': 'site.mal'})[0], 403)

    def test_pagina(self):
        c, b = self.req('/')
        self.assertEqual(c, 200)
        self.assertIn(b'X3 Master', b)


class Importar(Base):
    def test_cria_inativo_sem_sobrescrever(self):
        d = f'{self.t}/legado/yt-pub-lives1'
        os.makedirs(f'{d}/data')
        v = sqlite3.connect(f'{d}/data/lives.db')
        v.execute('CREATE TABLE config(chave,valor)')
        v.executemany('INSERT INTO config VALUES(?,?)', [('import_pub_horarios', '07:00,10:00'), ('pub_horarios', '01:00'), ('corte_horarios', '01:35'), ('corte_max_por_dia', '1')])
        v.commit(); v.close()
        self.assertEqual(importar.importar()[0], ['lives1'])
        c = self.c('lives1')
        self.assertFalse(c['ativo'])
        self.assertEqual(c['youtube']['horarios'], ['07:00', '10:00'])
        self.assertTrue(c['cortes']['ligado'])
        self.assertEqual(importar.importar()[1], ['lives1'])


if __name__ == '__main__':
    unittest.main()
