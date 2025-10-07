import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import base64
import re
import json
import time
import random
import threading

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Optional modern theming with ttkbootstrap (for a nicer look)
try:
    from ttkbootstrap import Style as TtkbStyle
    from ttkbootstrap import Window as TtkbWindow
    _HAS_TTKBOOTSTRAP = True
except Exception:
    TtkbStyle = None
    TtkbWindow = None
    _HAS_TTKBOOTSTRAP = False


WHISK_URL = "https://labs.google/fx/tools/whisk"
WHISK_PROJECT_URL = "https://labs.google/fx/tools/whisk/project"


class WhiskBrowserTool:
    def __init__(self, root: tk.Tk | None, use_tk_ui: bool = True, ui_callbacks: dict | None = None):
        self.root = root
        self.use_tk_ui = use_tk_ui
        self.ui_callbacks = ui_callbacks or {}

        self.root.title("🧪 Google Whisk Tool")
        self.root.geometry("800x560")
        self.root.resizable(True, True)

        self._apply_theme()

        # Runtime state
        self.driver = None
        self.current_email = None
        self.current_cache_dir = None
        self.current_user_agent = None
        self.login_success = False

        # Execution state & queue (per-account)
        self.stop_exec = False
        self.account_states = {}
        self.exec_drivers = {}
        self.exec_success_count = 0
        self.exec_error_count = 0

        # Profiles (cache per email)
        self.whisk_profiles_path = os.path.join(os.getcwd(), "chrome_cache", "whisk_profiles.json")
        self.whisk_profiles = {}
        self._load_profiles()

        # User agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]

        if self.use_tk_ui:
            self._build_ui()

        # Route error popups to non-blocking log
        try:
            self._orig_showerror = messagebox.showerror
            def _no_alert_showerror(title, msg):
                try:
                    self._append_log(f"[ERROR] {title}: {msg}\n")
                except Exception:
                    pass
            messagebox.showerror = _no_alert_showerror
        except Exception:
            pass

    # ===================== Theming =====================
    def _apply_theme(self) -> None:
        self.colors = {
            'bg': '#0F1115',
            'surface': '#171A21',
            'border': '#2A2F3A',
            'text': '#EAECEF',
            'subtle': '#9AA4AF',
            'accent': '#58A6FF',
            'accent_hover': '#3E7FD8',
            'success': '#2ECC71',
            'warning': '#F1C40F',
            'error': '#E74C3C',
            'info': '#58A6FF',
        }
        if _HAS_TTKBOOTSTRAP and TtkbStyle is not None:
            self.style = TtkbStyle(theme='superhero')
        else:
            self.style = ttk.Style()
            self.style.theme_use('clam')
        self.root.configure(bg=self.colors['bg'])
        for element in ('TFrame', 'TLabelframe', 'TLabelframe.Label'):
            self.style.configure(element, background=self.colors['bg'], foreground=self.colors['text'])
        self.style.configure('Card.TLabelframe', background=self.colors['surface'], bordercolor=self.colors['border'], borderwidth=1, relief='ridge')
        self.style.configure('TLabel', background=self.colors['bg'], foreground=self.colors['text'], font=('Segoe UI', 10))
        self.style.configure('Title.TLabel', background=self.colors['bg'], foreground=self.colors['accent'], font=('Segoe UI Semibold', 18))
        self.style.configure('Subtitle.TLabel', background=self.colors['bg'], foreground=self.colors['subtle'], font=('Segoe UI', 10, 'bold'))
        self.style.configure('Success.TLabel', background=self.colors['bg'], foreground=self.colors['success'], font=('Segoe UI', 10))
        self.style.configure('Error.TLabel', background=self.colors['bg'], foreground=self.colors['error'], font=('Segoe UI', 10))
        self.style.configure('Info.TLabel', background=self.colors['bg'], foreground=self.colors['info'], font=('Segoe UI', 10))
        self.style.configure('Warning.TLabel', background=self.colors['bg'], foreground=self.colors['warning'], font=('Segoe UI', 10))
        self.style.configure('Accent.TButton', padding=(14, 9), background=self.colors['accent'], foreground='#0B0C10', font=('Segoe UI', 10, 'bold'), borderwidth=0)
        self.style.map('Accent.TButton', background=[('active', self.colors['accent_hover'])])
        self.style.configure('Secondary.TButton', padding=(12, 8), background='#1A1F27', foreground=self.colors['text'], font=('Segoe UI', 10), borderwidth=0)

    # ===================== UI =====================
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        login_tab = ttk.Frame(notebook)
        exec_tab = ttk.Frame(notebook)
        notebook.add(login_tab, text="🔐 Đăng nhập Whisk")
        notebook.add(exec_tab, text="🎥 Execute")

        frame = ttk.Frame(login_tab, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        login_tab.columnconfigure(0, weight=1)
        login_tab.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="🧪 Google Whisk Login", style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=(0, 16))

        creds = ttk.LabelFrame(frame, text="📝 Thông tin tài khoản", padding="15", style='Card.TLabelframe')
        creds.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 12))
        creds.columnconfigure(1, weight=1)

        ttk.Label(creds, text="📧 Email:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.email_entry = ttk.Entry(creds)
        self.email_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 8))

        ttk.Label(creds, text="🔒 Mật khẩu:", style='Subtitle.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(0, 8))
        self.password_entry = ttk.Entry(creds, show="*")
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 8))

        self.note_label = ttk.Label(creds, text="💡 Đăng nhập Google (có thể cần 2FA)", style='Info.TLabel')
        self.note_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))

        self.login_btn = ttk.Button(frame, text="🚀 Đăng nhập Whisk", command=self._login_whisk, style='Accent.TButton')
        self.login_btn.grid(row=2, column=0, columnspan=2, pady=(14, 0))

        self.status_label = ttk.Label(frame, text="⏳ Chưa đăng nhập", style='Warning.TLabel')
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        profiles = ttk.LabelFrame(frame, text="👥 Tài khoản đã đăng nhập (cache)", padding="12", style='Card.TLabelframe')
        profiles.grid(row=4, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.W, tk.E), pady=(12, 0))
        profiles.columnconfigure(0, weight=1)
        profiles.rowconfigure(0, weight=1)

        self.profiles_list = tk.Listbox(profiles, height=6, bg=self.colors['surface'], fg=self.colors['text'],
                                        highlightthickness=1, highlightbackground=self.colors['border'],
                                        selectbackground='#253044', selectforeground=self.colors['text'])
        self.profiles_list.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        sb = ttk.Scrollbar(profiles, orient=tk.VERTICAL, command=self.profiles_list.yview)
        sb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.profiles_list.configure(yscrollcommand=sb.set)

        actions = ttk.Frame(profiles)
        actions.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))
        ttk.Button(actions, text="👁️ Mở profile", command=self._open_selected_profile, style='Secondary.TButton').pack(side=tk.LEFT)
        ttk.Button(actions, text="🗑️ Xóa cache", command=self._delete_selected_profile, style='Secondary.TButton').pack(side=tk.LEFT, padx=8)

        log_box = ttk.LabelFrame(frame, text="📜 Log", padding="10", style='Card.TLabelframe')
        log_box.grid(row=5, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.W, tk.E), pady=(12, 0))
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)
        self.log = scrolledtext.ScrolledText(log_box, height=6, wrap=tk.WORD, state='disabled',
                                             bg='#10141B', fg=self.colors['text'])
        self.log.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))

        self._refresh_profiles_list()

        # ===== Execute Tab =====
        exec_tab.columnconfigure(0, weight=1)
        exec_tab.rowconfigure(0, weight=1)
        ex = ttk.Frame(exec_tab, padding="20")
        ex.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        ex.columnconfigure(0, weight=3)
        ex.columnconfigure(1, weight=2)
        ex.rowconfigure(5, weight=1)

        ttk.Label(ex, text="🎥 Execute Whisk", style='Title.TLabel').grid(row=0, column=0, pady=(0, 16), sticky=tk.W)

        # Account selection
        sel = ttk.LabelFrame(ex, text="👤 Chọn tài khoản", padding="12", style='Card.TLabelframe')
        sel.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        sel.columnconfigure(1, weight=1)

        ttk.Label(sel, text="📧 Email:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.exec_email = tk.StringVar()
        self.exec_email_combo = ttk.Combobox(sel, textvariable=self.exec_email, state="readonly")
        self.exec_email_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0))
        ttk.Button(sel, text="🔄 Làm mới", command=self._refresh_exec_emails, style='Secondary.TButton').grid(row=0, column=2, padx=(8, 0))

        # Config: Headless toggle
        cfg = ttk.LabelFrame(ex, text="⚙️ Cấu hình", padding="12", style='Card.TLabelframe')
        cfg.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        self.headless_mode = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Headless (ẩn browser)", variable=self.headless_mode).grid(row=0, column=0, sticky=tk.W)

        # Actions
        actions_ex = ttk.Frame(ex)
        actions_ex.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        actions_ex.columnconfigure(0, weight=1)
        actions_ex.columnconfigure(1, weight=1)
        actions_ex.columnconfigure(2, weight=1)
        ttk.Button(actions_ex, text="📥 Import Excel", command=self._import_excel_whisk, style='Secondary.TButton').grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 6))
        ttk.Button(actions_ex, text="⬇️ Tải Template", command=self._download_excel_template_whisk, style='Secondary.TButton').grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6, 6))

        # Status + Log
        self.exec_status = ttk.Label(ex, text="✅ Sẵn sàng", style='Success.TLabel')
        self.exec_status.grid(row=4, column=0, sticky=tk.W)

        log_frame = ttk.LabelFrame(ex, text="📜 Log tiến trình", padding="10", style='Card.TLabelframe')
        log_frame.grid(row=5, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.exec_log = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD, state='disabled',
                                                  bg='#10141B', fg=self.colors['text'])
        self.exec_log.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))

        # Right side: Progress counters
        side = ttk.LabelFrame(ex, text="📊 Tiến trình", padding="10", style='Card.TLabelframe')
        side.grid(row=0, column=1, rowspan=6, sticky=(tk.N, tk.S, tk.W, tk.E), padx=(12, 0))
        side.columnconfigure(0, weight=1)
        ttk.Label(side, text="In queue:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0,4))
        self.lbl_queue = ttk.Label(side, text="0", style='Info.TLabel')
        self.lbl_queue.grid(row=1, column=0, sticky=tk.W)
        ttk.Separator(side, orient=tk.HORIZONTAL).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(8,8))
        ttk.Label(side, text="Executing:", style='Subtitle.TLabel').grid(row=3, column=0, sticky=tk.W, pady=(0,4))
        self.lbl_exec = ttk.Label(side, text="0", style='Info.TLabel')
        self.lbl_exec.grid(row=4, column=0, sticky=tk.W)
        ttk.Separator(side, orient=tk.HORIZONTAL).grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(8,8))
        ttk.Label(side, text="Success:", style='Subtitle.TLabel').grid(row=6, column=0, sticky=tk.W, pady=(0,4))
        self.lbl_ok = ttk.Label(side, text="0", style='Success.TLabel')
        self.lbl_ok.grid(row=7, column=0, sticky=tk.W)
        ttk.Separator(side, orient=tk.HORIZONTAL).grid(row=8, column=0, sticky=(tk.W, tk.E), pady=(8,8))
        ttk.Label(side, text="Error:", style='Subtitle.TLabel').grid(row=9, column=0, sticky=tk.W, pady=(0,4))
        self.lbl_err = ttk.Label(side, text="0", style='Error.TLabel')
        self.lbl_err.grid(row=10, column=0, sticky=tk.W)
        # Initialize counters
        try:
            self._update_exec_counters()
        except Exception:
            pass

    # ===================== Profiles =====================
    def _load_profiles(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.whisk_profiles_path), exist_ok=True)
            if os.path.exists(self.whisk_profiles_path):
                with open(self.whisk_profiles_path, 'r', encoding='utf-8') as f:
                    self.whisk_profiles = json.load(f)
            else:
                self.whisk_profiles = {}
        except Exception:
            self.whisk_profiles = {}

    def _save_profiles(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.whisk_profiles_path), exist_ok=True)
            with open(self.whisk_profiles_path, 'w', encoding='utf-8') as f:
                json.dump(self.whisk_profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_profiles_list(self) -> None:
        try:
            self.profiles_list.delete(0, tk.END)
            items = sorted(self.whisk_profiles.items(), key=lambda kv: kv[1].get("last_login", 0), reverse=True)
            for email_addr, meta in items:
                ts = meta.get("last_login")
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else ""
                self.profiles_list.insert(tk.END, f"{email_addr}  |  {time_str}")
        except Exception:
            pass

    # ===================== Login =====================
    def _login_whisk(self) -> None:
        email = (self.email_entry.get() or "").strip()
        if not email:
            messagebox.showerror("Lỗi", "Vui lòng nhập email!")
            return
        self.current_email = email
        password = (self.password_entry.get() or "").strip()
        if not password:
            messagebox.showerror("Lỗi", "Vui lòng nhập mật khẩu!")
            return
        threading.Thread(target=self._login_password_thread, args=(email, password), daemon=True).start()

    def _build_chrome(self, cache_key: str, existing_cache_dir: str | None = None) -> webdriver.Chrome:
        chrome_options = Options()
        # Prefer existing cache dir if available
        cache_dir = None
        if existing_cache_dir and os.path.isdir(existing_cache_dir):
            cache_dir = existing_cache_dir
        else:
            safe_key = re.sub(r'[^a-zA-Z0-9_.-]', '_', cache_key) or "default"
            cache_dir = os.path.join(os.getcwd(), "chrome_cache", f"whisk_{safe_key}")
            os.makedirs(cache_dir, exist_ok=True)
        self.current_cache_dir = cache_dir

        # Simple lock detection for single instance of profile
        try:
            lock_file = os.path.join(cache_dir, "SingletonLock")
            if os.path.exists(lock_file):
                raise Exception("Profile cache đang được sử dụng bởi phiên Chrome khác. Hãy đóng trình duyệt rồi thử lại.")
        except Exception:
            pass

        chrome_options.add_argument(f"--user-data-dir={cache_dir}")
        chrome_options.add_argument("--profile-directory=Default")
        ua = random.choice(self.user_agents)
        self.current_user_agent = ua
        chrome_options.add_argument(f"--user-agent={ua}")
        chrome_options.add_argument("--lang=vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("detach", True)
        # Further reduce automation fingerprints
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        try:
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        except Exception:
            pass

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass
        return driver

    def _login_password_thread(self, email_addr: str, password: str) -> None:
        try:
            self._set_status("Đang mở trình duyệt...", "orange")
            self.login_btn.config(state="disabled")
            meta = self.whisk_profiles.get(email_addr)
            exist_dir = meta.get("cache_dir") if meta else None
            self.driver = self._build_chrome(email_addr, existing_cache_dir=exist_dir)

            self.driver.get("https://accounts.google.com/signin")
            self._human_delay(1.5, 3.0)
            self._human_warm_up_page(self.driver)
            self._google_type_email_then_password(self.driver, email_addr, password)

            ok = self._wait_signin_success(self.driver, timeout=240)
            if not ok:
                # Retry via AccountChooser as a fallback for "This browser or app may not be secure"
                try:
                    self._set_status("Thử lại đăng nhập qua AccountChooser...", "orange")
                    self.driver.get("https://accounts.google.com/AccountChooser?continue=https://labs.google/fx/tools/whisk")
                    self._human_delay(1.0, 2.0)
                    self._human_warm_up_page(self.driver)
                    self._google_type_email_then_password(self.driver, email_addr, password)
                    ok = self._wait_signin_success(self.driver, timeout=180)
                except Exception:
                    ok = False
                if not ok:
                    raise Exception("Không thể đăng nhập tài khoản Google")

            # After signed in, open Whisk
            self.driver.get(WHISK_URL)
            self._wait_until(lambda: "labs.google" in (self.driver.current_url or ""), timeout=120)

            # If Whisk has a final "Sign in with Google" gate, click it
            try:
                self._click_whisk_google_signin(self.driver)
            except Exception:
                pass

            self._remember_profile(email_addr, self.current_cache_dir, self.current_user_agent)
            self.login_success = True
            self._set_status("Đăng nhập Whisk thành công", "green")
            messagebox.showinfo("Thành công", "Đăng nhập Google Whisk thành công!")
        except Exception as ex:
            self.login_success = False
            self._set_status("Đăng nhập thất bại", "red")
            messagebox.showerror("Lỗi", f"Lỗi đăng nhập: {ex}")
        finally:
            try:
                if self.driver is not None:
                    self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.login_btn.config(state="normal")

    # ===================== Selenium helpers =====================
    def _click_whisk_google_signin(self, driver: webdriver.Chrome) -> None:
        candidates = [
            "//button[.//span[normalize-space()='Sign in with Google']]",
            "//button[contains(., 'Sign in with Google')]",
            "//button[contains(@class,'sc-') and contains(., 'Sign in with Google')]",
            "//button[.//span[normalize-space()='Đăng nhập bằng Google']]",
            "//button[contains(., 'Đăng nhập bằng Google')]",
        ]
        self._human_delay(0.5, 1.2)
        for xp in candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
                except Exception:
                    pass
                self._human_click_el(driver, el)
                time.sleep(0.4)
                return
            except Exception:
                continue

    def _google_type_email_then_password(self, driver: webdriver.Chrome, email_addr: str, password: str) -> None:
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.NAME, "identifier")))
        email_input = driver.find_element(By.NAME, "identifier")
        self._human_click_el(driver, email_input)
        email_input.clear()
        self._human_type_el(email_input, email_addr)
        driver.find_element(By.ID, "identifierNext").click()
        self._human_delay(1.5, 3.0)
        try:
            wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            pw_input = driver.find_element(By.NAME, "Passwd")
        except TimeoutException:
            pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        self._human_click_el(driver, pw_input)
        pw_input.clear()
        self._human_type_el(pw_input, password)
        self._human_delay(0.4, 1.0)
        try:
            driver.find_element(By.ID, "passwordNext").click()
        except Exception:
            pw_input.send_keys(Keys.ENTER)

    def _wait_signin_success(self, driver: webdriver.Chrome, timeout: int = 180) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                if self._is_google_signed_in(driver):
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def _is_google_signed_in(self, driver: webdriver.Chrome) -> bool:
        try:
            url = driver.current_url or ""
            if url.startswith("https://myaccount.google.com/"):
                return True
            selectors = [
                "a[aria-label^='Google Account:' i]",
                "a[aria-label^='Tài khoản Google:' i]",
                "img.gb_P.gbii",
            ]
            for sel in selectors:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    return True
        except Exception:
            return False
        return False

    def _human_delay(self, min_seconds: float = 1.0, max_seconds: float = 2.0) -> None:
        time.sleep(random.uniform(min_seconds, max_seconds))

    def _human_warm_up_page(self, driver: webdriver.Chrome) -> None:
        try:
            # random scrolls
            for _ in range(random.randint(1, 3)):
                dy = random.randint(100, 400) * (1 if random.random() < 0.5 else -1)
                driver.execute_script("window.scrollBy(0, arguments[0]);", dy)
                time.sleep(random.uniform(0.1, 0.4))
            # slight mouse moves over body if possible
            try:
                body = driver.find_element(By.TAG_NAME, 'body')
                ActionChains(driver).move_to_element_with_offset(body, random.randint(5, 50), random.randint(5, 30)).pause(random.uniform(0.05, 0.2)).perform()
            except Exception:
                pass
        except Exception:
            pass

    def _human_click_el(self, driver: webdriver.Chrome, element) -> None:
        try:
            ActionChains(driver).move_to_element(element).pause(random.uniform(0.05, 0.2)).click().perform()
        except Exception:
            try:
                element.click()
            except Exception:
                pass

    def _human_type_el(self, element, text: str) -> None:
        for ch in text:
            element.send_keys(ch)
            time.sleep(random.uniform(0.02, 0.08))

    def _type_prompt_into_any_textarea(self, driver: webdriver.Chrome, text: str, timeout: int = 15) -> bool:
        """Type text into a visible <textarea> (do not rely on class selectors)."""
        if not text:
            return False
        try:
            # Prefer any visible textarea
            wait = WebDriverWait(driver, timeout)
            # Try a straightforward textarea
            area = None
            try:
                area = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'textarea')))
            except Exception:
                area = None
            # If multiple, pick the first visible and enabled
            if area is None:
                candidates = driver.find_elements(By.TAG_NAME, 'textarea')
            else:
                candidates = [area] + [el for el in driver.find_elements(By.TAG_NAME, 'textarea') if el is not area]
            for el in candidates:
                try:
                    if not el.is_displayed() or not el.is_enabled():
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.2)
                    self._human_click_el(driver, el)
                    try:
                        el.clear()
                        time.sleep(0.05)
                    except Exception:
                        pass
                    self._human_type_el(el, text)
                    return True
                except Exception:
                    continue
        except Exception:
            pass
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy textarea hiển thị để nhập văn bản\n")
        except Exception:
            pass
        return False

    def _click_add_image_button(self, driver: webdriver.Chrome, timeout: int = 5) -> bool:
        """Click the button that contains text 'Thêm hình ảnh' without relying on classes."""
        xpaths = [
            "//button[.//span[normalize-space(text())='Thêm hình ảnh']]",
            "//button[normalize-space(.)='Thêm hình ảnh']",
            "//button[contains(., 'Thêm hình ảnh')]",
            "//*[@role='button'][.//span[normalize-space(text())='Thêm hình ảnh']]",
            "//*[@role='button'][contains(., 'Thêm hình ảnh')]",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.1)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.2)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy nút 'Thêm hình ảnh'\n")
        except Exception:
            pass
        return False

    def _click_button_by_text(self, driver: webdriver.Chrome, text: str, timeout: int = 8) -> bool:
        """Click a button by its visible text without relying on classes."""
        if not text:
            return False
        xpaths = [
            f"//button[normalize-space(.)='{text}']",
            f"//button[.//span[normalize-space(text())='{text}']]",
            f"//button[contains(., '{text}')]",
            f"//*[@role='button' and normalize-space(.)='{text}']",
            f"//*[@role='button'][.//span[normalize-space(text())='{text}']]",
            f"//*[normalize-space(text())='{text}']/ancestor::*[self::button or @role='button'][1]",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.1)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.25)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy nút '{text}'\n")
        except Exception:
            pass
        return False

    def _click_button_by_aria_label(self, driver: webdriver.Chrome, aria_label: str, timeout: int = 6) -> bool:
        """Click a button by its aria-label attribute; fallback to icon text if needed."""
        if not aria_label:
            return False
        xpaths = [
            f"//button[@aria-label='{aria_label}']",
            f"//*[@role='button' and @aria-label='{aria_label}']",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.1)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.2)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy nút aria-label='{aria_label}'\n")
        except Exception:
            pass
        return False

    def _open_aspect_ratio_menu(self, driver: webdriver.Chrome, timeout: int = 6) -> bool:
        """Open the aspect ratio popover by clicking the trigger button with the aspect_ratio icon."""
        xpaths = [
            "//button[@aria-haspopup='dialog' and .//i[normalize-space(text())='aspect_ratio']]",
            "//*[@role='button' and @aria-haspopup='dialog' and .//i[normalize-space(text())='aspect_ratio']]",
            "//button[.//i[normalize-space(text())='aspect_ratio']]",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.1)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.2)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy nút mở chọn Tỷ lệ khung hình\n")
        except Exception:
            pass
        return False

    def _pick_aspect_ratio(self, driver: webdriver.Chrome, size_text: str, timeout: int = 6) -> bool:
        """Pick the aspect ratio option by visible text like '1:1', '9:16', '16:9', '3:4', '4:3'."""
        if not (size_text or '').strip():
            return False
        label = (size_text or '').strip()
        xpaths = [
            f"//div[@role='dialog']//button[.//span[normalize-space(text())='{label}']]",
            f"//div[@role='dialog']//span[normalize-space(text())='{label}']/ancestor::button[1]",
            f"//button[.//span[normalize-space(text())='{label}']]",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.05)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.2)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy tùy chọn size '{label}'\n")
        except Exception:
            pass
        return False

    def _open_tune_menu(self, driver: webdriver.Chrome, timeout: int = 6) -> bool:
        """Open the tune/settings popover by clicking the trigger button with the tune icon."""
        xpaths = [
            "//button[@aria-haspopup='dialog' and .//i[normalize-space(text())='tune']]",
            "//*[@role='button' and @aria-haspopup='dialog' and .//i[normalize-space(text())='tune']]",
            "//button[.//i[normalize-space(text())='tune']]",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for xp in xpaths:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if not el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.1)
                    self._human_click_el(driver, el)
                    return True
                except Exception:
                    continue
            time.sleep(0.2)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy nút mở tune/settings\n")
        except Exception:
            pass
        return False

    def _set_random_seed(self, driver: webdriver.Chrome, timeout: int = 6) -> bool:
        """Set a random 6-digit number into the seed input (id=whisk-seed-input)."""
        try:
            seed_val = str(random.randint(100000, 999999))
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    inp = driver.find_element(By.ID, 'whisk-seed-input')
                    if not inp.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
                        time.sleep(0.05)
                    self._human_click_el(driver, inp)
                    try:
                        inp.clear()
                    except Exception:
                        pass
                    inp.send_keys(seed_val)
                    try:
                        self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đặt seed: {seed_val}\n")
                    except Exception:
                        pass
                    return True
                except Exception:
                    time.sleep(0.2)
        except Exception:
            pass
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy input seed (whisk-seed-input)\n")
        except Exception:
            pass
        return False

    def _click_submit_execute(self, driver: webdriver.Chrome, timeout: int = 10) -> bool:
        """Click the final execute/submit button labeled 'Gửi câu lệnh' when it becomes enabled."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # Prefer aria-label
                candidates = driver.find_elements(By.XPATH,
                    "//button[@type='submit' and (@aria-label='Gửi câu lệnh' or contains(., 'Gửi câu lệnh') or .//i[normalize-space(text())='arrow_forward'])] | "
                    "//*[@role='button' and (@aria-label='Gửi câu lệnh' or contains(., 'Gửi câu lệnh'))] | "
                    "//button[contains(., 'Gửi câu lệnh')]"
                )
                for btn in candidates:
                    try:
                        disabled_attr = btn.get_attribute('disabled')
                        data_state = btn.get_attribute('data-state')
                        is_enabled = (disabled_attr is None) and btn.is_enabled()
                        if not is_enabled:
                            continue
                        if not btn.is_displayed():
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.1)
                        self._human_click_el(driver, btn)
                        try:
                            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã nhấn 'Gửi câu lệnh'\n")
                        except Exception:
                            pass
                        return True
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.25)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không thể nhấn 'Gửi câu lệnh' (có thể đang disabled)\n")
        except Exception:
            pass
        return False

    def _download_result_images(self, driver: webdriver.Chrome, wait_seconds: int = 30, max_images: int = 10) -> int:
        """Wait then find <img src="blob:..."> and download images to local folder. Returns count saved."""
        try:
            time.sleep(max(0, wait_seconds))
            imgs = driver.find_elements(By.CSS_SELECTOR, "img[src^='blob:']")
        except Exception:
            imgs = []
        if not imgs:
            try:
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy ảnh kết quả (blob:)\n")
            except Exception:
                pass
            return 0
        # Ensure output directory
        out_dir = os.path.join(os.getcwd(), 'downloads')
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            pass
        saved = 0
        for i, img in enumerate(imgs):
            if i >= max_images:
                break
            try:
                src = img.get_attribute('src') or ''
                if not src.startswith('blob:'):
                    continue
                data_url = self._fetch_blob_data_url(driver, src)
                if not data_url:
                    continue
                # Parse data URL
                if not data_url.startswith('data:'):
                    continue
                header, b64 = data_url.split(',', 1)
                ext = 'png'
                if 'image/' in header:
                    try:
                        ext = header.split('image/')[1].split(';')[0]
                    except Exception:
                        ext = 'png'
                file_name = f"result_{int(time.time())}_{i}.{ext}"
                file_path = os.path.join(out_dir, file_name)
                with open(file_path, 'wb') as f:
                    f.write(base64.b64decode(b64))
                saved += 1
                try:
                    self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã lưu ảnh: {file_path}\n")
                except Exception:
                    pass
            except Exception:
                continue
        if saved == 0:
            try:
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không thể tải về ảnh blob\n")
            except Exception:
                pass
        return saved

    def _fetch_blob_data_url(self, driver: webdriver.Chrome, blob_url: str, timeout: int = 10) -> str | None:
        """Fetch a blob: URL in page context and return a data URL (base64)."""
        try:
            script = (
                "var url = arguments[0]; var cb = arguments[1];"
                "fetch(url).then(r=>r.blob()).then(b=>{var fr=new FileReader();"
                "fr.onload=function(){cb(fr.result)}; fr.onerror=function(){cb(null)}; fr.readAsDataURL(b);}).catch(()=>cb(null));"
            )
            driver.set_script_timeout(timeout)
            result = driver.execute_async_script(script, blob_url)
            return result
        except Exception:
            return None

    # ===== Containers: Nhập văn bản / Tải hình ảnh lên =====
    def _find_prompt_image_containers(self, driver: webdriver.Chrome) -> list:
        """Return a list of container nodes that include both 'Nhập văn bản' and 'Tải hình ảnh lên'."""
        containers = []
        try:
            nodes = driver.find_elements(By.XPATH, 
                "//*[.//label[normalize-space(text())='Nhập văn bản'] or .//button[.//label[normalize-space(text())='Nhập văn bản']] or .//*[normalize-space(text())='Nhập văn bản']]"
            )
            for node in nodes:
                try:
                    has_upload = len(node.find_elements(By.XPATH, 
                        ".//label[normalize-space(text())='Tải hình ảnh lên'] | .//button[.//label[normalize-space(text())='Tải hình ảnh lên']] | .//*[normalize-space(text())='Tải hình ảnh lên']"
                    )) > 0
                    if has_upload:
                        containers.append(node)
                except Exception:
                    continue
        except Exception:
            pass
        # Deduplicate by element id if any
        result = []
        seen = set()
        for c in containers:
            try:
                key = c.id if hasattr(c, 'id') else c
                if key in seen:
                    continue
                seen.add(key)
                result.append(c)
            except Exception:
                result.append(c)
        if not result:
            try:
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy container có 'Nhập văn bản' và 'Tải hình ảnh lên'\n")
            except Exception:
                pass
        return result

    def _fill_prompt_and_images_at_index(self, driver: webdriver.Chrome, index: int, prompt_text: str | None, image_paths: list[str] | None) -> bool:
        """Find the container at index and fill prompt and upload images using its controls.
        Resilient to hidden inputs; will send paths to descendant input[type='file'] if present.
        """
        try:
            containers = self._find_prompt_image_containers(driver)
            if not containers:
                return False
            if index < 0 or index >= len(containers):
                try:
                    self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Index {index} vượt ngoài số container hiện có ({len(containers)})\n")
                except Exception:
                    pass
                return False
            container = containers[index]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
            time.sleep(0.2)

            # Type prompt
            if prompt_text:
                # Prefer textarea inside container
                area = None
                try:
                    areas = container.find_elements(By.TAG_NAME, 'textarea')
                    areas = [a for a in areas if a.is_displayed() and a.is_enabled()]
                    if areas:
                        area = areas[0]
                except Exception:
                    area = None
                if area is None:
                    # Click the "Nhập văn bản" label/button to reveal input, then wait 1s for modal
                    try:
                        text_btn = None
                        candidates = container.find_elements(By.XPATH, 
                            ".//button[.//label[normalize-space(text())='Nhập văn bản']] | .//*[normalize-space(text())='Nhập văn bản']/ancestor::*[self::button or @role='button'][1] | .//*[normalize-space(text())='Nhập văn bản']"
                        )
                        if candidates:
                            text_btn = candidates[0]
                        if text_btn is not None:
                            self._human_click_el(driver, text_btn)
                            time.sleep(1.0)
                    except Exception:
                        pass
                    try:
                        areas = container.find_elements(By.TAG_NAME, 'textarea')
                        areas = [a for a in areas if a.is_displayed() and a.is_enabled()]
                        if areas:
                            area = areas[0]
                    except Exception:
                        area = None
                if area is not None:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", area)
                        time.sleep(0.1)
                        self._human_click_el(driver, area)
                        try:
                            area.clear()
                        except Exception:
                            pass
                        self._human_type_el(area, prompt_text)
                    except Exception:
                        # Fallback: type into any visible textarea on the page
                        self._type_prompt_into_any_textarea(driver, prompt_text)
                else:
                    # Fallback: type into any visible textarea on the page
                    ok = self._type_prompt_into_any_textarea(driver, prompt_text)
                    if not ok:
                        try:
                            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không tìm thấy textarea trong slot {index}\n")
                        except Exception:
                            pass

            # Upload images AFTER typing prompt
            if image_paths:
                uploaded_any = False
                # Click the upload button by label first to mirror user flow
                try:
                    upload_btn = None
                    candidates = container.find_elements(By.XPATH, 
                        ".//button[.//label[normalize-space(text())='Tải hình ảnh lên']] | .//*[normalize-space(text())='Tải hình ảnh lên']/ancestor::*[self::button or @role='button'][1] | .//*[normalize-space(text())='Tải hình ảnh lên']"
                    )
                    if candidates:
                        upload_btn = candidates[0]
                    if upload_btn is not None:
                        self._human_click_el(driver, upload_btn)
                        time.sleep(0.3)
                except Exception:
                    pass
                # Then try direct file input inside container
                try:
                    file_inputs = container.find_elements(By.CSS_SELECTOR, "input[type='file']")
                except Exception:
                    file_inputs = []
                if file_inputs:
                    for path in image_paths:
                        try:
                            # Ensure the input is interactable
                            try:
                                driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible';", file_inputs[0])
                            except Exception:
                                pass
                            file_inputs[0].send_keys(path)
                            time.sleep(0.3)
                            uploaded_any = True
                        except Exception:
                            pass
                if not uploaded_any:
                    try:
                        self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không thể upload ảnh tại slot {index}\n")
                    except Exception:
                        pass
            return True
        except Exception:
            return False

    def _upload_image_via_toolbar(self, driver: webdriver.Chrome, image_path: str, timeout: int = 8) -> bool:
        """Upload a single image using the top toolbar that has buttons 'Nhập văn bản' and 'Tải hình ảnh lên'."""
        if not (image_path or '').strip():
            return False
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # Find a toolbar container that has both labels
                toolbars = driver.find_elements(By.XPATH,
                    "//div[.//*[normalize-space(text())='Nhập văn bản'] and .//*[normalize-space(text())='Tải hình ảnh lên']]"
                )
                for tb in toolbars:
                    try:
                        # Click the upload button by label first to mirror user action
                        try:
                            candidates = tb.find_elements(By.XPATH,
                                ".//button[.//label[normalize-space(text())='Tải hình ảnh lên']] | .//*[normalize-space(text())='Tải hình ảnh lên']/ancestor::*[self::button or @role='button'][1] | .//*[normalize-space(text())='Tải hình ảnh lên']"
                            )
                            if candidates:
                                self._human_click_el(driver, candidates[0])
                                time.sleep(0.3)
                        except Exception:
                            pass
                        # Find input[type=file] inside toolbar
                        inputs = tb.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if inputs:
                            try:
                                driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible';", inputs[0])
                            except Exception:
                                pass
                            inputs[0].send_keys(image_path)
                            time.sleep(0.4)
                            return True
                        # If no input found, click the upload button by label inside this toolbar
                        candidates = tb.find_elements(By.XPATH,
                            ".//button[.//label[normalize-space(text())='Tải hình ảnh lên']] | .//*[normalize-space(text())='Tải hình ảnh lên']/ancestor::*[self::button or @role='button'][1] | .//*[normalize-space(text())='Tải hình ảnh lên']"
                        )
                        if candidates:
                            self._human_click_el(driver, candidates[0])
                            time.sleep(0.3)
                            inputs = tb.find_elements(By.CSS_SELECTOR, "input[type='file']")
                            if inputs:
                                try:
                                    driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible';", inputs[0])
                                except Exception:
                                    pass
                                inputs[0].send_keys(image_path)
                                time.sleep(0.4)
                                return True
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.25)
        try:
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Không thể upload ảnh qua toolbar (không tìm thấy input hoặc nút)\n")
        except Exception:
            pass
        return False

    def _wait_until(self, predicate, timeout: int = 60, interval: float = 1.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def _remember_profile(self, email_addr: str, cache_dir: str, user_agent: str) -> None:
        if not email_addr:
            return
        self.whisk_profiles[email_addr] = {
            "cache_dir": cache_dir,
            "user_agent": user_agent,
            "last_login": int(time.time()),
        }
        self._save_profiles()
        self._refresh_profiles_list()
        # Also refresh execute email list if exec tab is present
        try:
            self._refresh_exec_emails()
        except Exception:
            pass

    # ===================== Profile actions =====================
    def _open_selected_profile(self) -> None:
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.whisk_profiles.get(email_addr)
            if not meta:
                messagebox.showerror("Lỗi", "Không tìm thấy cache!")
                return
            threading.Thread(target=self._open_profile_thread, args=(email_addr, meta), daemon=True).start()
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể mở profile: {ex}")

    def _open_profile_thread(self, email_addr: str, meta: dict) -> None:
        try:
            drv = self._open_profile_driver(meta)
            # Open the Whisk project page directly as requested
            drv.get(WHISK_PROJECT_URL)
            self._wait_until(lambda: "labs.google" in (drv.current_url or ""), timeout=120)
            self._set_status(f"Đã mở Whisk cho {email_addr}", "green")
            self._set_exec_status(f"Đã mở Whisk cho {email_addr}", "green")
        except Exception as ex:
            self._set_status(f"Lỗi mở Whisk: {ex}", "red")
            self._set_exec_status(f"Lỗi mở Whisk: {ex}", "red")

    def _open_profile_driver(self, meta: dict) -> webdriver.Chrome:
        chrome_options = Options()
        cache_dir = meta.get("cache_dir")
        if cache_dir and os.path.isdir(cache_dir):
            chrome_options.add_argument(f"--user-data-dir={cache_dir}")
            chrome_options.add_argument("--profile-directory=Default")
        if meta.get("user_agent"):
            chrome_options.add_argument(f"--user-agent={meta['user_agent']}")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--lang=vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7")
        # Headless toggle for execute flow
        try:
            if self.headless_mode.get():
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
        except Exception:
            pass
        try:
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        except Exception:
            pass
        service = Service(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=service, options=chrome_options)
        try:
            drv.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass
        return drv

    # ===== Execute actions =====
    def _refresh_exec_emails(self) -> None:
        try:
            emails = list(self.whisk_profiles.keys())
            if hasattr(self, 'exec_email_combo'):
                self.exec_email_combo['values'] = emails
            if emails and hasattr(self, 'exec_email') and not self.exec_email.get():
                self.exec_email.set(emails[0])
        except Exception:
            pass

    def _open_whisk_for_exec(self) -> None:
        email_addr = getattr(self, 'exec_email', tk.StringVar()).get()
        if not email_addr:
            try:
                messagebox.showerror("Lỗi", "Vui lòng chọn email đã có cache!")
            except Exception:
                pass
            return
        meta = self.whisk_profiles.get(email_addr)
        if not meta:
            try:
                messagebox.showerror("Lỗi", "Không tìm thấy cache cho email đã chọn!")
            except Exception:
                pass
            return
        threading.Thread(target=self._open_profile_thread, args=(email_addr, meta), daemon=True).start()

    # ===== Job queue & execution =====
    def _enqueue_or_start_account_job(self, email_addr: str, meta: dict, row: dict) -> None:
        job = {"email": email_addr, "meta": meta, "row": row}
        st = self.account_states.get(email_addr)
        if st is None:
            st = {'queue': [], 'running': False, 'lock': threading.Lock()}
            self.account_states[email_addr] = st
        with st['lock']:
            if st['running']:
                st['queue'].append(job)
                action = "queue"
            else:
                st['running'] = True
                action = "start"
        if action == "queue":
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Queued job for {email_addr}\n")
            try:
                self._update_exec_counters()
            except Exception:
                pass
        else:
            threading.Thread(target=self._execute_row_thread, args=(email_addr, meta, row), daemon=True).start()

    def _execute_row_thread(self, email_addr: str, meta: dict, row: dict) -> None:
        try:
            drv = self._open_profile_driver(meta)
            self.exec_drivers[email_addr] = drv
            self.stop_exec = False
            self._set_exec_status(f"Mở Whisk cho {email_addr}...", 'orange')
            drv.get(WHISK_PROJECT_URL)
            self._wait_until(lambda: "labs.google" in (drv.current_url or ""), timeout=120)
            time.sleep(3)
            # Click "Nhập công cụ" if present before proceeding
            try:
                if self._click_button_by_text(drv, "Nhập công cụ", timeout=6):
                    self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã nhấn 'Nhập công cụ'\n")
            except Exception:
                pass
            # Nhập main promt vào textarea (không dùng class)
            try:
                main_prompt = (row.get('main promt') or '').strip()
                if main_prompt:
                    self._type_prompt_into_any_textarea(drv, main_prompt)
                    self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã nhập main promt vào textarea\n")
                # Chọn size nếu có: mở menu, đợi 1s, rồi chọn option
                size_val = (row.get('size') or '').strip()
                if size_val:
                    if self._open_aspect_ratio_menu(drv):
                        time.sleep(1)
                        self._pick_aspect_ratio(drv, size_val)
            except Exception as _ex:
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Lỗi nhập promt: {_ex}\n")

            # Nếu có ảnh, nhấn nút "Thêm hình ảnh"
            try:
                has_image = any([
                    (row.get('image_1') or '').strip(),
                    (row.get('image_2') or '').strip(),
                    (row.get('kind_image') or '').strip(),
                    (row.get('screen_image') or '').strip(),
                ])
                if has_image:
                    # Ensure the global 'Thêm hình ảnh' entry point is clicked first
                    try:
                        if self._click_add_image_button(drv):
                            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã nhấn 'Thêm hình ảnh'\n")
                            time.sleep(1)
                            # Immediately add a new category section as requested
                            if self._click_button_by_aria_label(drv, "Thêm danh mục mới", timeout=4):
                                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã nhấn 'Thêm danh mục mới'\n")
                                time.sleep(1)
                    except Exception:
                        pass
                    # Không upload sớm qua toolbar; thực hiện upload trong container index 0 sau khi nhập prompt
                    # Fill slots by index with images only (no per-image prompt)
                    field_sets = [
                        ('', [p for p in [row.get('image_1')] if (p or '').strip()]),
                        ('', [p for p in [row.get('image_2')] if (p or '').strip()]),
                        ('', [p for p in [row.get('screen_image')] if (p or '').strip()]),
                        ('', [p for p in [row.get('kind_image')] if (p or '').strip()]),
                    ]
                    for idx, (ptext, imgs) in enumerate(field_sets):
                        # Với index 0: nhập prompt trước rồi upload image_1 trong container
                        imgs_to_use = imgs
                        if ptext or imgs_to_use:
                            filled = self._fill_prompt_and_images_at_index(drv, idx, ptext, imgs_to_use)
                            if filled:
                                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Slot {idx}: đã tải ảnh/nhập văn bản\n")
                            else:
                                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Slot {idx}: không tìm thấy container\n")
                    # After finishing all uploads, click the aspect_ratio button and pick size if provided
                    try:
                        if self._open_aspect_ratio_menu(drv):
                            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã mở menu Tỷ lệ khung hình sau khi upload ảnh\n")
                            time.sleep(1)
                            size_val_after = (row.get('size') or '').strip()
                            if size_val_after:
                                self._pick_aspect_ratio(drv, size_val_after)
                    except Exception:
                        pass
                    # Open tune/settings and set random seed
                    try:
                        if self._open_tune_menu(drv):
                            time.sleep(1)
                            self._set_random_seed(drv)
                    except Exception:
                        pass
                    # Finally click submit/execute
                    try:
                        self._click_submit_execute(drv)
                    except Exception:
                        pass
                    # Wait and download result images (blob: URLs)
                    try:
                        saved_count = self._download_result_images(drv, wait_seconds=30, max_images=10)
                        self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã tải {saved_count} ảnh kết quả\n")
                    except Exception:
                        pass
            except Exception as _ex:
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Lỗi click Thêm hình ảnh: {_ex}\n")

            # For now, just log the row summary
            summary = (
                f"size={row.get('size') or ''} | main='{(row.get('main promt') or '')[:60]}' | "
                f"img1={os.path.basename(row.get('image_1') or '')} | img2={os.path.basename(row.get('kind_image') or row.get('image_2') or '')}"
            )
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Executing: {summary}\n")
            # Placeholder wait to simulate work
            time.sleep(5)
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Done for {email_addr}\n")
            try:
                self.exec_success_count = getattr(self, 'exec_success_count', 0) + 1
                self._update_exec_counters()
            except Exception:
                pass
        except Exception as ex:
            self._set_exec_status(f"Lỗi execute: {ex}", 'red')
            try:
                self.exec_error_count = getattr(self, 'exec_error_count', 0) + 1
                self._update_exec_counters()
            except Exception:
                pass
        finally:
            try:
                local_drv = self.exec_drivers.get(email_addr)
                if local_drv is not None:
                    local_drv.quit()
            except Exception:
                pass
            try:
                if email_addr in self.exec_drivers:
                    del self.exec_drivers[email_addr]
            except Exception:
                pass
            # Auto-run next job if available
            try:
                st = self.account_states.get(email_addr)
                next_job = None
                if st is None:
                    st = {'queue': [], 'running': False, 'lock': threading.Lock()}
                    self.account_states[email_addr] = st
                with st['lock']:
                    if st['queue']:
                        next_job = st['queue'].pop(0)
                    else:
                        st['running'] = False
                if next_job is not None:
                    threading.Thread(target=self._execute_row_thread, args=(next_job['email'], next_job['meta'], next_job['row']), daemon=True).start()
                else:
                    self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | All jobs completed for {email_addr}\n")
                try:
                    self._update_exec_counters()
                except Exception:
                    pass
            except Exception as ex:
                try:
                    st = self.account_states.get(email_addr)
                    if st:
                        with st['lock']:
                            st['running'] = False
                except Exception:
                    pass
                self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Queue scheduling error: {ex}\n")

    def _delete_selected_profile(self) -> None:
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.whisk_profiles.get(email_addr)
            if not meta:
                return
            cache_dir = meta.get("cache_dir")
            try:
                if cache_dir and os.path.isdir(cache_dir):
                    import shutil
                    shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception:
                pass
            self.whisk_profiles.pop(email_addr, None)
            self._save_profiles()
            self._refresh_profiles_list()
            self._set_status(f"Đã xóa cache của {email_addr}", "green")
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể xóa cache: {ex}")

    # ===================== UX helpers =====================
    def _append_log(self, text: str) -> None:
        try:
            if hasattr(self, 'log'):
                self.log.configure(state='normal')
                self.log.insert(tk.END, text)
                self.log.see(tk.END)
                self.log.configure(state='disabled')
        except Exception:
            pass

    # Exec tab helpers (logging/status for execute tab)
    def _append_exec_log(self, text: str) -> None:
        try:
            if hasattr(self, 'exec_log'):
                self.exec_log.configure(state='normal')
                self.exec_log.insert(tk.END, text)
                self.exec_log.see(tk.END)
                self.exec_log.configure(state='disabled')
        except Exception:
            pass

    def _set_exec_status(self, text: str, color: str) -> None:
        try:
            if getattr(self, 'use_tk_ui', True) and hasattr(self, 'exec_status'):
                style_map = {
                    'blue': 'Info.TLabel',
                    'green': 'Success.TLabel',
                    'red': 'Error.TLabel',
                    'orange': 'Warning.TLabel'
                }
                style = style_map.get(color, 'Info.TLabel')
                self.exec_status.config(text=text, style=style)
        except Exception:
            pass

    def _update_exec_counters(self) -> None:
        try:
            # Queued total across accounts
            total_q = 0
            running = 0
            for _, st in self.account_states.items():
                try:
                    with st['lock']:
                        total_q += len(st['queue'])
                        running += 1 if st.get('running') else 0
                except Exception:
                    continue
            if hasattr(self, 'lbl_queue'):
                self.lbl_queue.config(text=str(total_q))
            if hasattr(self, 'lbl_exec'):
                self.lbl_exec.config(text=str(running))
            if hasattr(self, 'lbl_ok'):
                self.lbl_ok.config(text=str(getattr(self, 'exec_success_count', 0)))
            if hasattr(self, 'lbl_err'):
                self.lbl_err.config(text=str(getattr(self, 'exec_error_count', 0)))
        except Exception:
            pass

    # ===== Excel Template + Import =====
    def _download_excel_template_whisk(self) -> None:
        try:
            from tkinter import filedialog
            try:
                from openpyxl import Workbook
            except Exception:
                messagebox.showerror("Thiếu thư viện", "Cần cài openpyxl để tạo template: pip install openpyxl")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="whisk_template.xlsx",
                title="Lưu template Excel"
            )
            if not path:
                return
            wb = Workbook()
            ws = wb.active
            ws.title = "Tasks"
            # Headers per request (keep the exact keys as provided)
            headers = [
                "main promt",
                "image_1",
                "image_2",
                "screen_image",
                "kind_image",
                "size",  # allowed: 1:1, 9:16, 16:9, 3:4, 4:3
            ]
            ws.append(headers)
            # Sample rows
            ws.append(["A hero shot product on clean background", "C:/images/p1.jpg", "C:/images/p2.jpg", "C:/images/screen.jpg", "C:/images/variantA.jpg", "1:1"]) 
            ws.append(["Street fashion look", "C:/images/a.jpg", "C:/images/b.jpg", "", "", "9:16"]) 
            wb.save(path)
            self._append_exec_log(f"[EXEC] {time.strftime('%H:%M:%S')} | Đã lưu template: {path}\n")
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể tạo template: {ex}")

    def _import_excel_whisk(self) -> None:
        try:
            from tkinter import filedialog
            try:
                from openpyxl import load_workbook
            except Exception:
                messagebox.showerror("Thiếu thư viện", "Cần cài openpyxl để import: pip install openpyxl")
                return
            path = filedialog.askopenfilename(title="Chọn file Excel", filetypes=[("Excel", "*.xlsx")])
            if not path:
                return
            wb = load_workbook(filename=path, read_only=True, data_only=True)
            ws = wb.active

            def _cell_to_str(val):
                try:
                    if val is None:
                        return ''
                    return str(val).strip()
                except Exception:
                    return ''

            rows = []
            headers = None
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if row is None:
                    continue
                if i == 0:
                    headers = [(_cell_to_str(c) or '').lower() for c in row]
                    continue
                # Map by header name; tolerate minor case differences and spaces
                def get(col_name: str):
                    try:
                        idx = headers.index(col_name)
                        return _cell_to_str(row[idx])
                    except Exception:
                        return ''
                item = {
                    'main promt': get('main promt'),
                    'image_1': get('image_1'),
                    'image_2': get('image_2'),
                    'screen_image': get('screen_image'),
                    'kind_image': get('kind_image'),
                    'size': get('size'),
                }
                # Basic validation: require at least one of main promt or image_1
                if any(item.values()):
                    rows.append(item)

            if not rows:
                messagebox.showerror("Lỗi", "Không có dữ liệu hợp lệ trong file Excel!")
                return

            # Dispatch jobs round-robin across cached accounts
            emails = list(self.whisk_profiles.keys())
            if not emails:
                messagebox.showerror("Lỗi", "Chưa có account nào trong cache!")
                return
            self._set_exec_status(f"Imported {len(rows)} row(s) - dispatching...", 'orange')
            idx_email = 0
            for r in rows:
                target_email = emails[idx_email % len(emails)]
                idx_email += 1
                meta = self.whisk_profiles.get(target_email)
                if not meta:
                    continue
                self._enqueue_or_start_account_job(target_email, meta, r)
            self._set_exec_status("Jobs enqueued/started.", 'green')
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể import Excel: {ex}")

    def _set_status(self, text: str, color: str) -> None:
        try:
            if hasattr(self, 'ui_callbacks') and self.ui_callbacks.get('on_status'):
                try:
                    self.ui_callbacks['on_status'](text, color)
                except Exception:
                    pass
            if getattr(self, 'use_tk_ui', True) and hasattr(self, 'status_label'):
                style_map = {
                    'blue': 'Info.TLabel',
                    'green': 'Success.TLabel',
                    'red': 'Error.TLabel',
                    'orange': 'Warning.TLabel'
                }
                style = style_map.get(color, 'Info.TLabel')
                self.status_label.config(text=text, style=style)
        except Exception:
            pass


def main() -> None:
    # Use ttkbootstrap Window when available for a nicer UI
    if _HAS_TTKBOOTSTRAP and TtkbWindow is not None:
        root = TtkbWindow(themename='superhero')
    else:
        root = tk.Tk()
    app = WhiskBrowserTool(root, use_tk_ui=True)

    def _on_app_close():
        try:
            try:
                if getattr(app, 'driver', None) is not None:
                    app.driver.quit()
            except Exception:
                pass
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    try:
        root.protocol("WM_DELETE_WINDOW", _on_app_close)
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()


