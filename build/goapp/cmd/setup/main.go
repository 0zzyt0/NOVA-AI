//go:build windows

// NOVA AI Setup: instalador en un solo archivo.
// Lleva dentro el programa completo (payload.zip), lo descomprime en una carpeta temporal y abre
// el instalador gráfico (PowerShell + WPF). El .exe ya arranca como administrador (manifiesto),
// así que no hay segunda ventana de permisos ni consolas que se abren y cierran.
// Si el instalador gráfico no llega a abrirse, lo reintenta de otra forma y, si aun así falla,
// explica el motivo en una ventana en lugar de cerrarse sin decir nada.
package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"novaai/win"
)

//go:embed payload.zip
var payload []byte

const title = "NOVA AI · Instalación"

func extract(dst string) error {
	zr, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return err
	}
	base := filepath.Clean(dst) + string(os.PathSeparator)
	for _, f := range zr.File {
		p := filepath.Join(dst, filepath.FromSlash(f.Name))
		if !strings.HasPrefix(p, base) {
			continue // ruta sospechosa: fuera de la carpeta
		}
		if f.FileInfo().IsDir() {
			os.MkdirAll(p, 0o755)
			continue
		}
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		w, err := os.Create(p)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(w, rc)
		rc.Close()
		w.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

// prepare devuelve la carpeta con el programa que se va a instalar.
func prepare() (string, func(), error) {
	if len(payload) > 22 {
		tmp, err := os.MkdirTemp("", "NOVA_AI_Setup_")
		if err != nil {
			return "", nil, err
		}
		if err := extract(tmp); err != nil {
			os.RemoveAll(tmp)
			return "", nil, fmt.Errorf("no se pudo descomprimir el programa: %v", err)
		}
		return tmp, func() { os.RemoveAll(tmp) }, nil
	}
	// Versión ligera (dentro de Nova.zip): instala la carpeta en la que está el .exe
	dir := win.ExeDir()
	for _, d := range []string{dir, filepath.Dir(dir)} {
		if win.Exists(filepath.Join(d, "instalador", "instalador.ps1")) && win.Exists(filepath.Join(d, "nova.py")) {
			return d, func() {}, nil
		}
	}
	return "", nil, fmt.Errorf("no encuentro los archivos de NOVA AI junto a este instalador.\n\n" +
		"Descomprime el .zip completo antes de ejecutarlo (no lo abras desde dentro del .zip)")
}

func run(mode, ps1, src, ready string) ([]byte, int) {
	args := []string{"-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-WindowStyle", "Hidden"}
	if mode == "archivo" {
		args = append(args, "-File", ps1, "-Origen", src)
	} else {
		// Sin pasar por un archivo .ps1: evita las directivas de ejecución que bloquean scripts.
		args = append(args, "-Command",
			"& ([scriptblock]::Create([IO.File]::ReadAllText($env:NOVA_PS1))) -Origen $env:NOVA_ORIGEN")
	}
	cmd := win.Hidden(exec.Command(win.PowerShell(), args...))
	cmd.Dir = src
	cmd.Env = append(os.Environ(), "NOVA_SETUP_READY="+ready, "NOVA_PS1="+ps1, "NOVA_ORIGEN="+src)
	var out bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &out
	code := 0
	if err := cmd.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			code = ee.ExitCode()
		} else {
			fmt.Fprintf(&out, "\nNo se pudo ejecutar PowerShell: %v\n", err)
			code = -1
		}
	}
	return win.FromConsole(out.Bytes()), code
}

func main() {
	src, cleanup, err := prepare()
	if err != nil {
		win.Box("No se pudo preparar la instalación: "+err.Error(), title, win.MB_OK|win.MB_ICONERROR)
		os.Exit(1)
	}
	defer cleanup()
	ps1 := filepath.Join(src, "instalador", "instalador.ps1")
	ready := filepath.Join(os.TempDir(), fmt.Sprintf("nova_ai_setup_%d.listo", os.Getpid()))
	logPath := filepath.Join(os.TempDir(), "NOVA_AI_Setup.log")
	os.Remove(ready)

	var log bytes.Buffer
	fmt.Fprintf(&log, "NOVA AI Setup · %s\nOrigen: %s\n", time.Now().Format("2006-01-02 15:04:05"), src)
	code := 0
	for _, mode := range []string{"archivo", "bloque"} {
		out, c := run(mode, ps1, src, ready)
		code = c
		fmt.Fprintf(&log, "\n--- modo %s · código %d ---\n%s\n", mode, c, out)
		if win.Exists(ready) || c == 3 {
			break // la ventana llegó a abrirse (o el usuario negó los permisos): no se reintenta
		}
	}
	os.WriteFile(logPath, append([]byte("\xEF\xBB\xBF"), log.Bytes()...), 0o644) // con BOM: el Bloc de notas lo lee bien
	if win.Exists(ready) {
		os.Remove(ready)
		return
	}
	reason := "El instalador gráfico no ha podido abrirse."
	switch code {
	case 2:
		reason = "Este Windows no ha podido cargar la parte gráfica del instalador (WPF / .NET Framework)."
	case 3:
		reason = "Hacen falta permisos de administrador para instalar en «Archivos de programa»."
	}
	msg := fmt.Sprintf("%s\n\nDetalles (código %d):\n%s\n\n¿Quieres abrir el registro completo?\n(%s)\n\n"+
		"Mientras tanto puedes usar INSTALAR_CONSOLA.bat del archivo Nova.zip.",
		reason, code, win.Tail(log.Bytes(), 8), logPath)
	if win.Box(msg, title, win.MB_YESNO|win.MB_ICONERROR) == win.IDYES {
		win.Open(logPath)
	}
	os.Exit(1)
}
