#!/usr/bin/env python3
"""Painel local. Só escuta em 127.0.0.1; não tem senha padrão nem rota que execute comandos."""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from lib import canais as canais_mod, db, painel  # noqa: E402

HTML = os.path.join(RAIZ, 'dashboard', 'index.html')


class Painel(BaseHTTPRequestHandler):
    server_version = 'x3'

    def log_message(self, *a):
        pass

    def _json(self, codigo, dados):
        b = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def _host_ok(self):
        return (self.headers.get('Host') or '').split(':')[0] in ('127.0.0.1', 'localhost')

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {'erro': 'host recusado'})
        con = db.connect()
        try:
            canais = canais_mod.carregar()
            if self.path == '/':
                with open(HTML, 'rb') as f:
                    b = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(b)))
                self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(b)
            elif self.path == '/api/estado':
                self._json(200, painel.estado(con, canais))
            else:
                m = re.fullmatch(r'/api/canal/([\w-]+)', self.path)
                if m and m.group(1) in canais:
                    self._json(200, painel.itens_canal(con, m.group(1)))
                else:
                    self._json(404, {'erro': 'não encontrado'})
        finally:
            con.close()

    def do_POST(self):
        # O cabeçalho próprio impede que outra página aberta no navegador acione o painel.
        if not self._host_ok() or self.headers.get('X-X3') != '1':
            return self._json(403, {'erro': 'pedido recusado'})
        con = db.connect()
        try:
            m = re.fullmatch(r'/api/entrega/(\d+)/(pausar|retomar|pular|reenviar|confirmar)', self.path)
            if m:
                ok = db.acao(con, int(m.group(1)), m.group(2))
                return self._json(200 if ok else 409, {'ok': ok})
            m = re.fullmatch(r'/api/destino/([\w-]+)/(youtube|rs)/(ligar|desligar)', self.path)
            if m and m.group(1) in canais_mod.carregar():
                db.definir_ligado(con, m.group(1), m.group(2), m.group(3) == 'ligar')
                return self._json(200, {'ok': True})
            self._json(404, {'erro': 'não encontrado'})
        finally:
            con.close()


def criar(porta):
    return ThreadingHTTPServer(('127.0.0.1', porta), Painel)


if __name__ == '__main__':
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8230
    print(f'painel em http://127.0.0.1:{porta}', flush=True)
    criar(porta).serve_forever()
