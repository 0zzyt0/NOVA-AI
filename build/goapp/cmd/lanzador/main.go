//go:build windows

// NOVA AI.exe: abre el asistente con el Python de su propia carpeta (.venv), sin consolas.
package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"novaai/win"
)

const title = "NOVA AI"

func newest(paths ...string) string {
	best, bt := "", time.Time{}
	for _, p := range paths {
		if st, err := os.Stat(p); err == nil && st.ModTime().After(bt) {
			best, bt = p, st.ModTime()
		}
	}
	return best
}

func main() {
	dir := win.ExeDir()
	// junto al .exe, o dos niveles arriba si se abre desde instalador\bin
	roots := []string{dir, filepath.Dir(filepath.Dir(dir))}
	if pf := os.Getenv("ProgramFiles"); pf != "" {
		roots = append(roots, filepath.Join(pf, "NOVA AI"))
	}
	for _, r := range roots {
		pyw := filepath.Join(r, ".venv", "Scripts", "pythonw.exe")
		script := filepath.Join(r, "nova.py")
		if !win.Exists(pyw) || !win.Exists(script) {
			continue
		}
		cmd := exec.Command(pyw, append([]string{script}, os.Args[1:]...)...)
		cmd.Dir = r
		if err := cmd.Start(); err != nil {
			win.Box("No se pudo abrir NOVA AI:\n"+err.Error(), title, win.MB_OK|win.MB_ICONERROR)
			os.Exit(1)
		}
		done := make(chan error, 1)
		go func() { done <- cmd.Wait() }()
		select {
		case err := <-done:
			// Se cerró enseguida: si fue un error, se cuenta (si no, era otra Nova ya abierta).
			if err != nil {
				logf := newest(filepath.Join(os.Getenv("LOCALAPPDATA"), "NOVA AI", "datos", "fallos.log"),
					filepath.Join(r, "datos", "fallos.log"))
				msg := "NOVA AI se ha cerrado al arrancar (" + err.Error() + ")."
				if logf != "" {
					if b, e := os.ReadFile(logf); e == nil {
						msg += "\n\nÚltimas líneas de " + logf + ":\n" + win.Tail(b, 10)
					}
				}
				msg += "\n\nPrueba a reinstalar con «NOVA AI Setup» o abre DEPURAR.bat para ver más detalles."
				win.Box(msg, title, win.MB_OK|win.MB_ICONERROR)
				os.Exit(1)
			}
		case <-time.After(8 * time.Second):
		}
		return
	}
	win.Box("NOVA AI todavía no está instalada en este equipo (falta su entorno de Python).\n\n"+
		"Ejecuta «NOVA AI Setup.exe» (o INSTALAR.bat) para instalarla.", title, win.MB_OK|win.MB_ICONWARNING)
	os.Exit(1)
}
