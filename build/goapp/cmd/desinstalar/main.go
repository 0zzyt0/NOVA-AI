//go:build windows

// Desinstalar NOVA AI.exe: abre el desinstalador gráfico (ya con permisos de administrador).
package main

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"novaai/win"
)

const title = "Desinstalar NOVA AI"

func main() {
	dir := win.ExeDir()
	if !win.Exists(filepath.Join(dir, "instalador", "desinstalar.ps1")) {
		dir = filepath.Dir(filepath.Dir(dir)) // abierto desde instalador\bin
	}
	ps1 := filepath.Join(dir, "instalador", "desinstalar.ps1")
	if !win.Exists(ps1) {
		win.Box("No encuentro el desinstalador ("+ps1+").\n\nPuedes quitar NOVA AI desde Configuración › Aplicaciones.",
			title, win.MB_OK|win.MB_ICONERROR)
		os.Exit(1)
	}
	args := []string{"-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-WindowStyle", "Hidden", "-File", ps1, "-Root", dir}
	for _, a := range os.Args[1:] {
		if s := strings.ToLower(a); s == "/s" || s == "-silencioso" || s == "/silent" {
			args = append(args, "-Silencioso")
		}
	}
	cmd := win.Hidden(exec.Command(win.PowerShell(), args...))
	cmd.Dir = os.TempDir() // no bloquear la carpeta que se va a borrar
	var out bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &out
	if err := cmd.Start(); err != nil {
		win.Box("No se pudo abrir el desinstalador:\n"+err.Error(), title, win.MB_OK|win.MB_ICONERROR)
		os.Exit(1)
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		if err != nil {
			win.Box("El desinstalador no ha podido abrirse ("+err.Error()+").\n\n"+win.Tail(win.FromConsole(out.Bytes()), 8)+
				"\n\nPuedes quitar NOVA AI desde Configuración › Aplicaciones.", title, win.MB_OK|win.MB_ICONERROR)
			os.Exit(1)
		}
	case <-time.After(15 * time.Second):
	}
}
