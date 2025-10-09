import sys
import os
import subprocess
import traceback
import ctypes

# Try to import tkinter early; show a native dialog if it's missing
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ModuleNotFoundError:
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Không tìm thấy tkinter. Hãy cài Python đầy đủ (có Tcl/Tk) hoặc dùng bản build mới.",
            "Lỗi môi trường Python",
            0x00000010,
        )
    except Exception:
        pass
    sys.exit(1)

# Optional modern theming with ttkbootstrap
try:
    from ttkbootstrap import Window as TtkbWindow
    from ttkbootstrap import Style as TtkbStyle
    _HAS_TTKBOOTSTRAP = True
except Exception:
    TtkbWindow = None
    TtkbStyle = None
    _HAS_TTKBOOTSTRAP = False


def _launch_flow():
    # Import and delegate after closing the launcher root
    _prepare_tcl_env_for_current_process()
    import flow_browser_tool as flow
    flow.main()


def _launch_gmail():
    # Import and delegate after closing the launcher root
    _prepare_tcl_env_for_current_process()
    import gmail_browser_login as gmail
    gmail.main()


def _launch_whisk():
    # Import and delegate after closing the launcher root
    _prepare_tcl_env_for_current_process()
    import whisk_browser_tool as whisk
    whisk.main()


_selected_launcher = None


def _prepare_tcl_env_for_current_process() -> None:
    """Best-effort: set TCL/TK env for this process (Windows) to avoid init.tcl errors.

    Uses paths relative to the active interpreter (venv-aware via base_prefix) and
    falls back to sys.prefix. Safe to call multiple times.
    """
    if os.name != 'nt':
        return
    try:
        base_python = getattr(sys, 'base_prefix', sys.prefix) or sys.prefix
    except Exception:
        base_python = sys.prefix
    candidates = []
    # Prefer base_prefix (real install), then prefix (venv)
    for root in {base_python, sys.prefix}:
        candidates.append((os.path.join(root, 'tcl', 'tcl8.6'), 'TCL_LIBRARY'))
        candidates.append((os.path.join(root, 'tcl', 'tk8.6'), 'TK_LIBRARY'))
    # In frozen EXE, prefer bundled lib/tcl8.6 and lib/tk8.6
    if getattr(sys, 'frozen', False):
        try:
            bundle_dir = os.path.dirname(sys.executable)
            tcl_bundle = os.path.join(bundle_dir, 'lib', 'tcl8.6')
            tk_bundle = os.path.join(bundle_dir, 'lib', 'tk8.6')
            if os.path.isdir(tcl_bundle):
                os.environ['TCL_LIBRARY'] = tcl_bundle
            if os.path.isdir(tk_bundle):
                os.environ['TK_LIBRARY'] = tk_bundle
            return
        except Exception:
            pass

    # Clear conflicting inherited values when not frozen
    os.environ.pop('TCL_LIBRARY', None)
    os.environ.pop('TK_LIBRARY', None)
    for path, var in candidates:
        if os.path.isdir(path):
            os.environ[var] = path

def _spawn_tool(entry: str) -> None:
    """Spawn a new detached process of this program with an entry selector.

    - On frozen/EXE builds: re-run `sys.executable` (the same .exe) with `--entry` arg
    - On dev mode: re-run the current script with the same interpreter
    """
    try:
        # Resolve paths and preferred interpreter
        script_path = os.path.abspath(__file__)
        project_root = os.path.dirname(script_path)

        # On Windows: if we're in a venv, prefer launching with that Python
        # to mirror the successful `--entry=...` CLI behavior. Otherwise,
        # prefer the packaged EXE if available.
        if os.name == 'nt':
            in_venv = False
            try:
                in_venv = hasattr(sys, 'base_prefix') and sys.prefix != sys.base_prefix
            except Exception:
                in_venv = False
            exe_path = os.path.join(project_root, 'dist', 'GoogleFlowTool.exe')
            if not getattr(sys, 'frozen', False) and in_venv:
                venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
                python_exec = venv_py_win if os.path.exists(venv_py_win) else sys.executable
                cmd = [python_exec, script_path, f"--entry={entry}"]
            elif os.path.exists(exe_path):
                cmd = [exe_path, f"--entry={entry}"]
            elif getattr(sys, 'frozen', False):
                # Current process is already the packaged EXE
                cmd = [sys.executable, f"--entry={entry}"]
            else:
                # Running as script: prefer project venv interpreter if present
                venv_py_posix = os.path.join(project_root, 'venv', 'bin', 'python')
                venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
                python_exec = sys.executable
                try:
                    if os.path.exists(venv_py_win):
                        python_exec = venv_py_win
                except Exception:
                    pass
                cmd = [python_exec, script_path, f"--entry={entry}"]
        elif getattr(sys, 'frozen', False):
            # PyInstaller executable (non-Windows)
            cmd = [sys.executable, f"--entry={entry}"]
        else:
            # Running as script: prefer project venv interpreter if present
            venv_py_posix = os.path.join(project_root, 'venv', 'bin', 'python')
            venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
            python_exec = sys.executable
            try:
                if os.name == 'nt' and os.path.exists(venv_py_win):
                    python_exec = venv_py_win
                elif os.name != 'nt' and os.path.exists(venv_py_posix):
                    python_exec = venv_py_posix
            except Exception:
                pass
            cmd = [python_exec, script_path, f"--entry={entry}"]

        # Detach flags
        creationflags = 0
        try:
            if os.name == 'nt':
                creationflags = (
                    getattr(subprocess, 'DETACHED_PROCESS', 0)
                    | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                )
        except Exception:
            creationflags = 0

        # On POSIX we use start_new_session, on Windows avoid close_fds=True
        start_new_session = os.name != 'nt'
        close_fds = os.name != 'nt'

        # Ensure we launch from project root so relative paths work
        env = os.environ.copy()
        env.setdefault('PYTHONUTF8', '1')
        # Help child Python find Tcl/Tk on Windows to avoid init.tcl errors.
        # IMPORTANT: Use the Tcl/Tk that matches the CHILD python executable,
        # not the launcher's interpreter, to avoid version conflicts.
        if os.name == 'nt' and not getattr(sys, 'frozen', False):
            try:
                # python_exec is defined above when not frozen
                # For venvs, python.exe lives at <venv>\Scripts\python.exe
                # For system installs, at <pyroot>\python.exe
                python_dir = os.path.dirname(python_exec)
                python_root = os.path.dirname(python_dir)
                tcl_dir = os.path.join(python_root, 'tcl', 'tcl8.6')
                tk_dir = os.path.join(python_root, 'tcl', 'tk8.6')
                # Clean any inherited conflicting values
                for var in ('TCL_LIBRARY', 'TK_LIBRARY'):
                    if var in env:
                        env.pop(var, None)
                if os.path.isdir(tcl_dir):
                    env['TCL_LIBRARY'] = tcl_dir
                if os.path.isdir(tk_dir):
                    env['TK_LIBRARY'] = tk_dir
            except Exception:
                # As a last resort, remove possibly wrong values
                env.pop('TCL_LIBRARY', None)
                env.pop('TK_LIBRARY', None)

        # Optional: write child output to a log for debugging crashes
        stdout_target = None
        stderr_target = None
        try:
            log_path = os.path.join(project_root, 'launcher_child.log')
            stdout_target = open(log_path, 'a', encoding='utf-8')
            stderr_target = stdout_target
        except Exception:
            stdout_target = None
            stderr_target = None

        subprocess.Popen(
            cmd,
            cwd=project_root,
            close_fds=close_fds,
            creationflags=creationflags,
            start_new_session=start_new_session,
            env=env,
            stdout=stdout_target,
            stderr=stderr_target,
        )
    except Exception:
        # Bubble up; caller decides whether to quit UI or show error
        raise


def _select_and_quit(root, launcher: callable) -> None:
    global _selected_launcher
    _selected_launcher = launcher
    try:
        root.after(10, root.quit)
    except Exception:
        try:
            root.quit()
        except Exception:
            pass


def _spawn_and_quit(root, entry: str) -> None:
    """Spawn selected tool in a fresh process, then quit the launcher UI.

    If spawning fails, keep the launcher open and show an error dialog.
    """
    try:
        _spawn_tool(entry)
    except Exception as e:
        try:
            messagebox.showerror("Không khởi chạy được", f"Lỗi khi mở công cụ: {e}")
        except Exception:
            pass
        return
    try:
        root.after(10, root.quit)
    except Exception:
        try:
            root.quit()
        except Exception:
            pass


def main() -> None:
    # Prepare Tcl env on Windows before creating any Tk root
    _prepare_tcl_env_for_current_process()
    # Prefer ttkbootstrap if available for a nicer UI
    try:
        if _HAS_TTKBOOTSTRAP and TtkbWindow is not None:
            root = TtkbWindow(themename="superhero")
            style = TtkbStyle(theme="superhero")
        else:
            root = tk.Tk()
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except Exception:
                pass
    except Exception:
        # Retry once after forcing env (in case it was called before)
        _prepare_tcl_env_for_current_process()
        root = tk.Tk()
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

    root.title("🔧 Tool Launcher")
    root.geometry("420x220")
    root.resizable(False, False)

    # Container
    container = ttk.Frame(root, padding="20")
    container.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Title
    title = ttk.Label(container, text="Chọn công cụ", font=("Segoe UI", 16, "bold"))
    title.grid(row=0, column=0, columnspan=2, pady=(0, 16))

    # Buttons
    btn_flow = ttk.Button(
        container,
        text="🎬 Veo3",
        command=lambda: _spawn_and_quit(root, 'flow'),
        width=24
    )
    btn_flow.grid(row=1, column=0, padx=8, pady=8, sticky=(tk.W, tk.E))

    def _coming_soon(name: str):
        try:
            messagebox.showinfo("Coming soon", f"{name} sẽ sớm có mặt!")
        except Exception:
            pass

    btn_whisk = ttk.Button(
        container,
        text="🥣 Whisk",
        command=lambda: _spawn_and_quit(root, 'whisk'),
        width=24
    )
    btn_whisk.grid(row=1, column=1, padx=8, pady=8, sticky=(tk.W, tk.E))

    btn_pokecut = ttk.Button(
        container,
        text="✂️ Pokecut (coming soon)",
        command=lambda: _coming_soon("Pokecut"),
        width=24
    )
    btn_pokecut.grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky=(tk.W, tk.E))

    # Info
    info = ttk.Label(
        container,
        text="Veo3/Whisk đã sẵn sàng. Pokecut đang phát triển.",
        foreground="#9AA4AF"
    )
    info.grid(row=3, column=0, columnspan=2, pady=(12, 0))

    # Expand columns
    for i in range(2):
        container.columnconfigure(i, weight=1)

    root.mainloop()


if __name__ == "__main__":
    # Support CLI entry selection: --entry=flow | --entry=gmail | --entry=whisk
    entry_arg = next((a for a in sys.argv[1:] if a.startswith("--entry=")), None)
    if entry_arg:
        entry = entry_arg.split("=", 1)[1]
        try:
            if entry == 'flow':
                _launch_flow()
            elif entry == 'gmail':
                _launch_gmail()
            elif entry == 'whisk':
                _launch_whisk()
            else:
                main()
        except ModuleNotFoundError as e:
            # Friendly guidance to install dependencies
            msg = (
                "Thiếu thư viện Python: " + str(e) + "\n\n"
                "Hướng dẫn khắc phục:\n"
                "1) Đảm bảo đã tạo venv và cài requirements:\n"
                "   - Windows: venv\\Scripts\\python -m pip install -r requirements.txt\n"
                "   - macOS/Linux: venv/bin/python -m pip install -r requirements.txt\n\n"
                "2) Sau đó chạy lại công cụ."
            )
            try:
                _tmp = tk.Tk()
                _tmp.withdraw()
                messagebox.showerror("Thiếu thư viện", msg)
                _tmp.destroy()
            except Exception:
                print(msg, file=sys.stderr)
        else:
            main()
    else:
        main()

