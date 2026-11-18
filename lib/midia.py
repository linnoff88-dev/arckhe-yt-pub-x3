"""Leitura de arquivos de mídia."""
import hashlib
import json
import subprocess


def probe(arquivo):
    """Retorna (largura, altura, duração em segundos). (0, 0, 0) se não conseguir ler."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                            'stream=width,height:format=duration', '-of', 'json', arquivo],
                           capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        s = d['streams'][0]
        return int(s['width']), int(s['height']), float(d.get('format', {}).get('duration') or 0)
    except Exception:
        return 0, 0, 0.0


def sha256(arquivos):
    h = hashlib.sha256()
    for a in arquivos:
        with open(a, 'rb') as f:
            for bloco in iter(lambda: f.read(1024 * 1024), b''):
                h.update(bloco)
    return h.hexdigest()


def eh_short(largura, altura, duracao):
    return largura < altura and duracao <= 180
