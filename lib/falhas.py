"""Como um publicador avisa o que deu errado. O tipo decide o destino do vídeo."""

TEMPORARIO = 'temporario'  # tenta de novo até max_tentativas
AUTH = 'auth'              # pausa o destino do canal; o vídeo espera, sem gastar tentativa
COTA = 'cota'              # idem, por mais tempo
DEFINITIVO = 'definitivo'  # erro: só volta com "reenviar"
FORMATO = 'formato'        # ignorado: este arquivo não serve para este destino
AMBIGUO = 'ambiguo'        # pode ter publicado: conferir antes de reenviar


class Falha(Exception):
    def __init__(self, msg, tipo=TEMPORARIO):
        super().__init__(msg)
        self.tipo = tipo
