"""Auditoria: mapeia cada blueprint registrado ao módulo Python que o define,
e cruza com os arquivos *_views.py do topo e do pacote views/ para achar módulos
que NÃO contribuem nenhum blueprint vivo (candidatos a morto)."""
import glob
import os
import sys

# Permite rodar de qualquer cwd: insere a raiz do repo (pai de scripts/) no path.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import app as app_module

app = app_module.app

registrados = {}
for name, bp in app.blueprints.items():
    mod = getattr(bp, "import_name", "?")
    registrados[name] = mod

print("# Blueprints registrados (", len(registrados), ")")
for name, mod in sorted(registrados.items()):
    print(f"- {name}  <-  {mod}")

modulos_vivos = {m.split(".")[0] if "." in m else m for m in registrados.values()}
bases_vivas = {m.split(".")[-1] for m in registrados.values()}

candidatos = sorted(
    [os.path.splitext(os.path.basename(p))[0] for p in glob.glob("*_views.py")]
    + [
        "views." + os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob("views/*.py")
        if not p.endswith("__init__.py")
    ]
)
print("\n# Módulos *_views candidatos vs vivos")
for c in candidatos:
    base = c.split(".")[-1]
    vivo = base in bases_vivas or c in modulos_vivos
    print(f"- {c}: {'VIVO' if vivo else 'INCERTO/sem blueprint registrado'}")
