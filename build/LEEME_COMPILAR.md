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
