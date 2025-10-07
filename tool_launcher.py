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
    import flow_browser_tool as flow
    flow.main()


def _launch_gmail():
    # Import and delegate after closing the launcher root
    import gmail_browser_login as gmail
    gmail.main()


def _launch_whisk():
    # Import and delegate after closing the launcher root
    import whisk_browser_tool as whisk
    whisk.main()


_selected_launcher = None


def _spawn_tool(entry: str) -> None:
    """Spawn a new detached process of this program with an entry selector.

    - On frozen/EXE builds: re-run `sys.executable` (the same .exe) with `--entry` arg
    - On dev mode: re-run the current script with the same interpreter
    """
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller executable
            cmd = [sys.executable, f"--entry={entry}"]
        else:
            # Running as script: prefer project venv interpreter if present
            script_path = os.path.abspath(__file__)
            project_root = os.path.dirname(script_path)
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

        creationflags = 0
        start_new_session = False
        try:
            # Windows: fully detach the child GUI process
            creationflags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        except Exception:
            creationflags = 0
        # POSIX: start new session to detach
        start_new_session = os.name != 'nt'

        subprocess.Popen(
            cmd,
            close_fds=True,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
    except Exception:
        # Fallback: run inline if spawn fails to avoid dead-end UX
        if entry == 'flow':
            _launch_flow()
        elif entry == 'gmail':
            _launch_gmail()
        elif entry == 'whisk':
            _launch_whisk()


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
    """Spawn selected tool in a fresh process, then quit the launcher UI."""
    try:
        _spawn_tool(entry)
    finally:
        try:
            root.after(10, root.quit)
        except Exception:
            try:
                root.quit()
            except Exception:
                pass


def main() -> None:
    # Prefer ttkbootstrap if available for a nicer UI
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

