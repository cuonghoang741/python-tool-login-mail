import tkinter as tk
from tkinter import ttk, messagebox
import sys
import traceback

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


_selected_launcher = None


def _select_and_quit(root: tk.Tk, launcher: callable) -> None:
    global _selected_launcher
    _selected_launcher = launcher
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
        command=lambda: _select_and_quit(root, _launch_flow),
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
        text="🥣 Whisk (coming soon)",
        command=lambda: _coming_soon("Whisk"),
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
        text="Veo3 đã sẵn sàng. Whisk/Pokecut đang phát triển.",
        foreground="#9AA4AF"
    )
    info.grid(row=3, column=0, columnspan=2, pady=(12, 0))

    # Expand columns
    for i in range(2):
        container.columnconfigure(i, weight=1)

    root.mainloop()

    # After the launcher window is closed, run the selected tool
    global _selected_launcher
    if _selected_launcher is not None:
        try:
            _selected_launcher()
        except Exception as e:
            # Try to show a minimal error dialog so the user isn't left with a black screen
            try:
                _tmp = tk.Tk()
                _tmp.withdraw()
                messagebox.showerror(
                    "Tool error",
                    f"Đã xảy ra lỗi khi chạy tool:\n{e}\n\n" +
                    ("\n".join(traceback.format_exc().splitlines()[-6:]))
                )
                _tmp.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    main()


