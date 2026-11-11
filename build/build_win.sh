#!/bin/bash
# Compila los ejecutables de NOVA AI (Windows, amd64) y el instalador todo en uno.
# Requisitos: Go 1.24+ y Python 3 (con Pillow solo si regeneras los iconos). Funciona en Linux, macOS o Windows (Git Bash).
#
# Uso:  build/build_win.sh
# Resultado en dist/:
#   NOVA AI Setup.exe   instalador todo en uno (lleva el programa dentro)
#   Nova/               carpeta lista para comprimir (con el instalador ligero dentro)
#
# Por fases (para firmar con SignPath en GitHub Actions; ver .github/workflows/compilar.yml):
#   NOVA_STAGE=exes  build/build_win.sh   solo NOVA AI.exe, Desinstalar NOVA AI.exe y el instalador ligero
#   (firmarlos)
#   NOVA_STAGE=pack  build/build_win.sh   empaqueta con esos .exe ya firmados el instalador todo en uno y dist/Nova
#
# Claves de fábrica: si existe recursos/llave_claves.bin (no está en el repositorio), el instalador
# la incluye y el programa trae claves de IA de serie. Sin ella, cada usuario pone las suyas.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
B=$ROOT/build; R=$ROOT/recursos; DIST=$ROOT/dist
command -v go >/dev/null || { echo "Falta Go (https://go.dev/dl/)"; exit 1; }
PY=$(command -v python3 || command -v python)

echo "· Recursos de Windows (icono, manifiesto y versión)"
$PY $B/winres.py $B/goapp/cmd/setup/rsrc_windows_amd64.syso $R/nova_instalar.ico $B/res/manifest_requireAdministrator.xml $B/res/version_setup.json
$PY $B/winres.py $B/goapp/cmd/lanzador/rsrc_windows_amd64.syso $R/nova.ico $B/res/manifest_asInvoker.xml $B/res/version_lanzador.json
$PY $B/winres.py $B/goapp/cmd/desinstalar/rsrc_windows_amd64.syso $R/nova_desinstalar.ico $B/res/manifest_requireAdministrator.xml $B/res/version_desinstalar.json

export GOOS=windows GOARCH=amd64 CGO_ENABLED=0
GOFLAGS_LD="-H windowsgui -s -w"
STAGE=${NOVA_STAGE:-all}
cd $B/goapp
mkdir -p $ROOT/instalador/bin
if [ "$STAGE" != "pack" ]; then
echo "· NOVA AI.exe y Desinstalar NOVA AI.exe"
go build -trimpath -ldflags "$GOFLAGS_LD" -o "$ROOT/instalador/bin/NOVA AI.exe" ./cmd/lanzador
go build -trimpath -ldflags "$GOFLAGS_LD" -o "$ROOT/instalador/bin/Desinstalar NOVA AI.exe" ./cmd/desinstalar

echo "· Instalador ligero (usa la carpeta en la que está)"
: > cmd/setup/payload.zip
go build -trimpath -ldflags "$GOFLAGS_LD" -o "$ROOT/NOVA AI Setup.exe" ./cmd/setup
fi
if [ "$STAGE" = "exes" ]; then echo "Listo (fase exes): instalador/bin/*.exe y NOVA AI Setup.exe"; exit 0; fi
for f in "$ROOT/instalador/bin/NOVA AI.exe" "$ROOT/instalador/bin/Desinstalar NOVA AI.exe" "$ROOT/NOVA AI Setup.exe"; do
  [ -s "$f" ] || { echo "Falta $f (compila antes la fase exes)"; exit 1; }
done

echo "· Instalador todo en uno"
cd $ROOT
find . -name __pycache__ -type d -prune -exec rm -rf {} +
TMPZIP=$(mktemp -d)/payload.zip
$PY - "$TMPZIP" <<'PYEOF'
import sys, zipfile, os
out = sys.argv[1]
import glob
items = ["core", "gui", "recursos", "instalador", "nova.py", "requirements.txt", "LEEME.md", "LICENSE", "LICENCIA.txt", "INICIAR.bat",
         "DEPURAR.bat", "DESINSTALAR.bat", "INSTALAR_CONSOLA.bat"] + sorted(glob.glob("NORMAS_Y_PRIVACIDAD*.md")) \
        + sorted(glob.glob("datos/comandos*.json"))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for it in items:
        if os.path.isfile(it):
            z.write(it, it)
            continue
        for d, _, files in os.walk(it):
            for f in files:
                if f.endswith(".pyc"):
                    continue
                p = os.path.join(d, f)
                z.write(p, p.replace(os.sep, "/"))
print("  payload:", round(os.path.getsize(out) / 1e6, 1), "MB")
PYEOF
cp "$TMPZIP" $B/goapp/cmd/setup/payload.zip
mkdir -p "$DIST"
cd $B/goapp && go build -trimpath -ldflags "$GOFLAGS_LD" -o "$DIST/NOVA AI Setup.exe" ./cmd/setup
: > cmd/setup/payload.zip

echo "· Carpeta Nova para el .zip"
rm -rf "$DIST/Nova"; mkdir -p "$DIST/Nova/datos"
cd $ROOT
cp -r core gui recursos instalador nova.py requirements.txt LEEME.md NORMAS_Y_PRIVACIDAD*.md LICENSE LICENCIA.txt *.bat "NOVA AI Setup.exe" "$DIST/Nova/"
cp datos/comandos*.json "$DIST/Nova/datos/"
[ -f recursos/llave_claves.bin ] && echo "  (con claves de fábrica)" || echo "  (sin claves de fábrica: cada usuario pondrá las suyas)"
echo "Listo: $DIST"
