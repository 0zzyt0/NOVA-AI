"""Cifra las claves de IA de fábrica de NOVA AI.

Uso:  python build/cifrar_claves.py claves.json
      (claves.json: {"gemini": "...", "groq": "...", "openrouter": "...", "deepseek": "..."})

Escribe recursos/claves_iniciales.enc (se puede subir al repositorio) y, si no existe, crea la llave
maestra recursos/llave_claves.bin, que NUNCA debe subirse: está en .gitignore y solo viaja dentro del
instalador oficial. Guarda una copia de la llave en un sitio seguro.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import keyvault  # noqa: E402

keys = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keyvault.save(keys, ROOT / "recursos" / "claves_iniciales.enc", ROOT / "recursos" / "llave_claves.bin")
print("Claves cifradas:", ", ".join(sorted(keys)))
