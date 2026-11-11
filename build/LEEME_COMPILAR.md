# Compilar NOVA AI

`build/build_win.sh` genera en `dist/`:

- `NOVA AI Setup.exe`: instalador todo en uno, con el programa completo dentro.
- `Nova/`: la carpeta para el `.zip`, con el instalador ligero dentro.

## Requisitos

- Go 1.24 o superior: <https://go.dev/dl/>.
- Python 3 (solo con biblioteca estándar; Pillow solo si regeneras los iconos).

## Piezas

| Archivo | Qué es |
|---|---|
| `goapp/cmd/setup` | Instalador: descomprime el programa en TEMP y abre `instalador/instalador.ps1` ya con permisos de administrador. Si la ventana gráfica no se abre, lo reintenta y explica el motivo. |
| `goapp/cmd/lanzador` | `NOVA AI.exe`: abre `nova.py` con el Python de `.venv`, sin consola. |
| `goapp/cmd/desinstalar` | `Desinstalar NOVA AI.exe`. |
| `winres.py` | Genera el `.syso` (COFF `.rsrc`) con el icono, el manifiesto y la versión que Go enlaza. |
| `pe_res.py` | Comprueba los recursos de un `.exe` ya compilado. |
| `iconos/` | Genera `nova.ico`, `nova_instalar.ico` y `nova_desinstalar.ico`. |
| `res/` | Manifiestos (administrador o usuario) y datos de versión. |

## Claves de fábrica

```bash
python build/cifrar_claves.py claves.json   # crea recursos/claves_iniciales.enc (+ llave_claves.bin si no existe)
```

`recursos/llave_claves.bin` **no se sube nunca** (está en `.gitignore`). Sin ella, el instalador funciona igual, pero sin claves de serie.

## Compilar y firmar en GitHub (SignPath)

`.github/workflows/compilar.yml` compila NOVA AI en GitHub Actions y, si está configurado, firma los ejecutables con
la firma gratuita de [SignPath Foundation](https://signpath.org) (para que Control inteligente de aplicaciones y
SmartScreen no los bloqueen). Se lanza en **Actions › Compilar y firmar › Run workflow** o al subir una etiqueta `v*`.

1. **Fase exes** (`NOVA_STAGE=exes build/build_win.sh`): `NOVA AI.exe`, `Desinstalar NOVA AI.exe` y el instalador
   ligero. Se firman (configuración de artefacto `exes` en SignPath).
2. **Fase pack** (`NOVA_STAGE=pack build/build_win.sh`): el instalador todo en uno, con los ejecutables ya firmados
   dentro, y la carpeta `dist/Nova`. Se firma el instalador (configuración `setup`).
3. El artefacto **NOVA-AI-version** trae `NOVA.AI.Setup.<versión>.exe`, `NOVA_AI_<versión>_portable.zip` y
   `SHA256SUMS.txt`, listos para adjuntar a la Release.

Para activar la firma (cuando SignPath Foundation acepte el proyecto), en el repositorio:

- **Settings › Secrets and variables › Actions › Secrets:** `SIGNPATH_API_TOKEN` (token de un usuario con permiso
  de envío en el proyecto).
- **… › Variables:** `SIGNPATH_ORGANIZATION_ID`.
- En SignPath: proyecto con slug `NOVA-AI`, política de firma `release-signing` (con aprobación manual), GitHub
  como sistema de compilación de confianza y dos configuraciones de artefacto:
  - `exes`: un ZIP con tres archivos PE (`NOVA AI.exe`, `Desinstalar NOVA AI.exe`, `NOVA AI Setup.exe`).
  - `setup`: un ZIP con `NOVA AI Setup.exe`.
  En ambas, que el nombre de producto sea `NOVA AI` y la versión la misma en todos (vienen de `build/res/version_*.json`).

Sin esos datos el flujo compila igual, sin firmar.
