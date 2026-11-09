//go:build windows

// Package win: lo mínimo de la API de Windows que necesitan los ejecutables de NOVA AI
// (solo biblioteca estándar de Go: syscall).
package win

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unicode/utf16"
	"unicode/utf8"
	"unsafe"
)

var (
	user32      = syscall.NewLazyDLL("user32.dll")
	messageBoxW = user32.NewProc("MessageBoxW")
	shell32     = syscall.NewLazyDLL("shell32.dll")
	kernel32    = syscall.NewLazyDLL("kernel32.dll")
	mbToWide    = kernel32.NewProc("MultiByteToWideChar")
	shellExecW  = shell32.NewProc("ShellExecuteW")
)

const (
	MB_OK           = 0x0
	MB_YESNO        = 0x4
	MB_ICONERROR    = 0x10
	MB_ICONQUESTION = 0x20
	MB_ICONWARNING  = 0x30
	MB_ICONINFO     = 0x40
	MB_TOPMOST      = 0x40000
	MB_SETFG        = 0x10000
	IDYES           = 6

	createNoWindow = 0x08000000
)

// Box muestra un cuadro de mensaje de Windows y devuelve el botón pulsado.
func Box(text, title string, flags uintptr) int {
	t, _ := syscall.UTF16PtrFromString(text)
	c, _ := syscall.UTF16PtrFromString(title)
	r, _, _ := messageBoxW.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), flags|MB_TOPMOST|MB_SETFG)
	return int(r)
}

// Open abre un archivo o carpeta con su programa asociado (como un doble clic).
func Open(path string) {
	verb, _ := syscall.UTF16PtrFromString("open")
	p, _ := syscall.UTF16PtrFromString(path)
	shellExecW.Call(0, uintptr(unsafe.Pointer(verb)), uintptr(unsafe.Pointer(p)), 0, 0, 1)
}

// Exists dice si existe un archivo o carpeta.
func Exists(p string) bool { _, err := os.Stat(p); return err == nil }

// ExeDir es la carpeta donde está el propio .exe.
func ExeDir() string {
	exe, err := os.Executable()
	if err != nil {
		return "."
	}
	if r, err := filepath.EvalSymlinks(exe); err == nil {
		exe = r
	}
	return filepath.Dir(exe)
}

// PowerShell devuelve la ruta de Windows PowerShell 5.1 (incluido en Windows 10/11).
func PowerShell() string {
	root := os.Getenv("SystemRoot")
	if root == "" {
		root = `C:\Windows`
	}
	p := filepath.Join(root, `System32\WindowsPowerShell\v1.0\powershell.exe`)
	if Exists(p) {
		return p
	}
	return "powershell.exe"
}

// Hidden prepara un proceso sin ventana de consola (la interfaz WPF se ve igualmente).
func Hidden(cmd *exec.Cmd) *exec.Cmd {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
	return cmd
}

// Tail devuelve las últimas n líneas no vacías de un texto.
func Tail(b []byte, n int) string {
	b = bytes.ReplaceAll(b, []byte("\r"), nil)
	var lines []string
	for _, l := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(l) != "" {
			lines = append(lines, l)
		}
	}
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	s := strings.Join(lines, "\n")
	if len(s) > 1500 {
		s = "…" + s[len(s)-1500:]
	}
	return s
}

// FromConsole convierte la salida de PowerShell a UTF-8: sin consola escribe en la página de
// códigos OEM (850 en España), que se vería como «Excepci¢n».
func FromConsole(b []byte) []byte {
	if len(b) == 0 || utf8.Valid(b) {
		return b
	}
	n, _, _ := mbToWide.Call(1 /* CP_OEMCP */, 0, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)), 0, 0)
	if n == 0 {
		return b
	}
	w := make([]uint16, n)
	mbToWide.Call(1, 0, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)), uintptr(unsafe.Pointer(&w[0])), n)
	return []byte(string(utf16.Decode(w)))
}
