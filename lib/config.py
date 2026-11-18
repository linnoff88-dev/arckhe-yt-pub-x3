"""Caminhos e chaves de ambiente. Tudo é lido na hora, para os testes usarem pastas temporárias."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser('~')
PROJETOS = os.path.join(HOME, 'projetos')


def _p(env, padrao):
    return os.path.expanduser(os.environ.get(env) or padrao)


def db_path():
    return _p('X3_DB', os.path.join(ROOT, 'data', 'x3.db'))


def entrada_dir():
    return _p('X3_ENTRADA', os.path.join(ROOT, 'entrada'))


def canais_dir():
    return _p('X3_CANAIS', os.path.join(ROOT, 'canais'))


def acervo_dir():
    return _p('X3_ACERVO', os.path.join(ROOT, 'data', 'acervo'))


def recusados_dir():
    return _p('X3_RECUSADOS', os.path.join(ROOT, 'data', 'recusados'))


def historico_ytpubx():
    return _p('X3_HISTORICO_YTPUBX', '~/.local/share/yt-pubx/historico.jsonl')


def legado_dir():
    return _p('X3_LEGADO', PROJETOS)


def publicar_de_verdade():
    """Simulação é o padrão: só X3_PUBLICAR=1 publica, baixa ou gasta IA."""
    return os.environ.get('X3_PUBLICAR') == '1'
