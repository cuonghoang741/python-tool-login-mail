import tkinter as tk
from tkinter import ttk, messagebox

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


def _run_and_close(root: tk.Tk, launcher: callable) -> None:
    # Hide launcher to avoid destroying Tk context too early
    try:
        root.withdraw()
    except Exception:
        pass
    # Start selected tool shortly after, then close launcher once it returns
    def _start():
        try:
            launcher()
        finally:
            try:
                root.destroy()
            except Exception:
                pass
    try:
        root.after(50, _start)
    except Exception:
        _start()


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
        command=lambda: _run_and_close(root, _launch_flow),
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


if __name__ == "__main__":
    main()


