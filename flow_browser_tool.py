import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import re
import json
import time
import random
import threading
import urllib.request
from pathlib import Path

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


class FlowBrowserTool:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎬 Google Flow Tool")
        self.root.geometry("1000x750")
        self.root.resizable(True, True)
        
        # Configure modern style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors and fonts
        self.style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'), foreground='#2E86AB')
        self.style.configure('Subtitle.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#34495E')
        self.style.configure('Success.TLabel', foreground='#27AE60', font=('Segoe UI', 10))
        self.style.configure('Error.TLabel', foreground='#E74C3C', font=('Segoe UI', 10))
        self.style.configure('Info.TLabel', foreground='#3498DB', font=('Segoe UI', 10))
        self.style.configure('Warning.TLabel', foreground='#F39C12', font=('Segoe UI', 10))
        
        # Configure button styles
        self.style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=(15, 8))
        self.style.configure('Secondary.TButton', font=('Segoe UI', 9), padding=(10, 6))
        self.style.configure('Accent.TButton', font=('Segoe UI', 11, 'bold'), padding=(20, 10))
        
        # Configure frame styles
        self.style.configure('Card.TFrame', relief='raised', borderwidth=1)
        self.style.configure('Card.TLabelFrame', relief='raised', borderwidth=1)
        
        # Configure notebook style
        self.style.configure('TNotebook.Tab', padding=[20, 12], font=('Segoe UI', 11, 'bold'))
        self.style.configure('TNotebook', tabmargins=[2, 5, 2, 0])
        
        # Set background color
        self.root.configure(bg='#F8F9FA')

        # Runtime state
        self.driver = None
        self.current_email = None
        self.current_cache_dir = None
        self.current_user_agent = None
        self.login_success = False

        # Profiles (cache per email)
        self.flow_profiles_path = os.path.join(os.getcwd(), "chrome_cache", "flow_profiles.json")
        self.flow_profiles = {}
        self._load_profiles()

        # User agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]

        self._build_ui()

    # ===================== UI =====================
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Bind resize event để responsive
        self.root.bind('<Configure>', self._on_window_resize)

        # Tabs
        login_tab = ttk.Frame(notebook)
        exec_tab = ttk.Frame(notebook)
        notebook.add(login_tab, text="🔐 Đăng nhập & Tài khoản")
        notebook.add(exec_tab, text="🎥 Execute Media")
        # Mặc định chọn tab Execute Media
        notebook.select(1)

        # ===== Login Tab =====
        frame = ttk.Frame(login_tab, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        login_tab.columnconfigure(0, weight=1)
        login_tab.rowconfigure(0, weight=1)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        frame.rowconfigure(6, weight=1)  # Profiles section expandable

        self.title = ttk.Label(frame, text="🎬 Google Flow Login", style='Title.TLabel')
        self.title.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        method_group = ttk.LabelFrame(frame, text="🔑 Phương thức đăng nhập", padding="15")
        method_group.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.login_method = tk.StringVar(value="password")
        # Chỉ giữ password login, ẩn nhóm chọn phương thức
        try:
            method_group.grid_remove()
        except Exception:
            pass

        creds = ttk.LabelFrame(frame, text="📝 Thông tin tài khoản", padding="15")
        creds.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        creds.columnconfigure(1, weight=1)

        ttk.Label(creds, text="📧 Email:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.email_entry = ttk.Entry(creds)
        self.email_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 8), padx=(10, 0))

        self.password_label = ttk.Label(creds, text="🔒 Mật khẩu:", style='Subtitle.TLabel')
        self.password_entry = ttk.Entry(creds, show="*")
        # Luôn hiển thị trường mật khẩu
        self.password_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 8))
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 8), padx=(10, 0))

        self.note_label = ttk.Label(creds, text="💡 Đăng nhập bằng mật khẩu Google (có thể cần 2FA)", style='Info.TLabel')
        self.note_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        self.login_btn = ttk.Button(frame, text="🚀 Đăng nhập Google Flow", command=self._login_flow, style='Accent.TButton')
        self.login_btn.grid(row=3, column=0, columnspan=2, pady=(15, 0))

        self.status_label = ttk.Label(frame, text="⏳ Chưa đăng nhập", style='Warning.TLabel')
        self.status_label.grid(row=4, column=0, columnspan=2, pady=(10, 0))

        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        profiles_group = ttk.LabelFrame(frame, text="👥 Tài khoản đã đăng nhập (cache)", padding="15")
        profiles_group.grid(row=6, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.W, tk.E))
        profiles_group.columnconfigure(0, weight=1)
        profiles_group.rowconfigure(0, weight=1)

        self.profiles_list = tk.Listbox(profiles_group, height=6, selectmode=tk.SINGLE)
        self.profiles_list.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        sb = ttk.Scrollbar(profiles_group, orient=tk.VERTICAL, command=self.profiles_list.yview)
        sb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.profiles_list.configure(yscrollcommand=sb.set)

        actions = ttk.Frame(profiles_group)
        actions.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        ttk.Button(actions, text="👁️ Mở profile", command=self._open_selected_profile, style='Secondary.TButton').pack(side=tk.LEFT)
        ttk.Button(actions, text="🗑️ Xóa cache", command=self._delete_selected_profile, style='Secondary.TButton').pack(side=tk.LEFT, padx=8)

        self._refresh_profiles_list()

        # ===== Execute Tab =====
        ex = ttk.Frame(exec_tab, padding="20")
        ex.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        exec_tab.columnconfigure(0, weight=1)
        exec_tab.rowconfigure(0, weight=1)
        for i in range(3):
            ex.columnconfigure(i, weight=1)
        ex.rowconfigure(2, weight=1)  # Prompt text area expandable

        exec_title = ttk.Label(ex, text="🎥 Execute Media Workflow", style='Title.TLabel')
        exec_title.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Email selection
        email_frame = ttk.LabelFrame(ex, text="👤 Chọn tài khoản", padding="15")
        email_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        email_frame.columnconfigure(1, weight=1)

        ttk.Label(email_frame, text="📧 Email:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.exec_email = tk.StringVar()
        self.exec_email_combo = ttk.Combobox(email_frame, textvariable=self.exec_email, state="readonly")
        self.exec_email_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 8), pady=(0, 8))
        ttk.Button(email_frame, text="🔄 Làm mới", command=self._refresh_exec_emails, style='Secondary.TButton').grid(row=0, column=2, pady=(0, 8))

        # Workflow selection
        workflow_frame = ttk.LabelFrame(ex, text="⚙️ Loại Workflow", padding="15")
        workflow_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        workflow_frame.columnconfigure(0, weight=1)
        workflow_frame.columnconfigure(1, weight=1)

        ttk.Label(workflow_frame, text="Workflow:", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.workflow = tk.StringVar(value="frames_to_video")
        ttk.Radiobutton(workflow_frame, text="📝 Text to Video", variable=self.workflow, value="text_to_video").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Radiobutton(workflow_frame, text="🖼️ Frames to Video", variable=self.workflow, value="frames_to_video").grid(row=1, column=1, sticky=tk.W, pady=5)

        # Prompt section
        prompt_frame = ttk.LabelFrame(ex, text="💬 Prompt (Text to Video)", padding="15")
        prompt_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        prompt_frame.columnconfigure(0, weight=1)

        ttk.Label(prompt_frame, text="Prompt (Text to Video):", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.NW, pady=(0, 8))
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=6, wrap=tk.WORD)
        self.prompt_text.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))

        # Media upload section
        media_frame = ttk.LabelFrame(ex, text="📁 Upload Media (Frames to Video)", padding="15")
        media_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))

        ttk.Label(media_frame, text="Upload media (chỉ 1 file ảnh):", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        media_input_frame = ttk.Frame(media_frame)
        media_input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        media_input_frame.columnconfigure(0, weight=1)
        
        self.media_paths = tk.StringVar()
        self.media_entry = ttk.Entry(media_input_frame, textvariable=self.media_paths)
        self.media_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 8))
        ttk.Button(media_input_frame, text="🖼️ Chọn ảnh", command=self._choose_image_file, style='Secondary.TButton').grid(row=0, column=1)

        # Configuration section
        cfg = ttk.LabelFrame(ex, text="⚙️ Cấu hình", padding="15")
        cfg.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        for i in range(6):
            cfg.columnconfigure(i, weight=1)

        # Browser options
        ttk.Label(cfg, text="Browser mode", style='Subtitle.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.headless_mode = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Headless (ẩn browser)", variable=self.headless_mode).grid(row=0, column=1, sticky=tk.W, pady=(0, 8))

        # Settings (popover) - Aspect ratio, Outputs per prompt, Model
        ttk.Label(cfg, text="Aspect ratio", style='Subtitle.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.aspect_ratio = ttk.Combobox(cfg, values=["16:9", "9:16", "1:1"], state="readonly")
        self.aspect_ratio.set("16:9")
        self.aspect_ratio.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(8, 0))

        ttk.Label(cfg, text="Outputs per prompt", style='Subtitle.TLabel').grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        self.outputs_per_prompt = ttk.Combobox(cfg, values=["1", "2", "3", "4"], state="readonly")
        self.outputs_per_prompt.set("4")
        self.outputs_per_prompt.grid(row=1, column=3, sticky=(tk.W, tk.E), pady=(8, 0))

        ttk.Label(cfg, text="Model", style='Subtitle.TLabel').grid(row=1, column=4, sticky=tk.W, pady=(8, 0))
        self.model_choice = ttk.Combobox(
            cfg,
            values=[
                "Veo 3 - Fast",
                "Veo 3 - Quality",
                "Veo 2 - Fast",
                "Veo 2 - Quality",
            ],
            state="readonly"
        )
        self.model_choice.set("Veo 3 - Fast")
        self.model_choice.grid(row=1, column=5, sticky=(tk.W, tk.E), pady=(8, 0))

        # Action buttons
        action_frame = ttk.Frame(ex)
        action_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Button(action_frame, text="▶️ Execute", command=self._execute_workflow, style='Accent.TButton').pack(side=tk.LEFT)

        self.exec_status = ttk.Label(ex, text="✅ Sẵn sàng", style='Success.TLabel')
        self.exec_status.grid(row=7, column=0, columnspan=3, sticky=tk.W)

        self._refresh_exec_emails()

    # ===================== Responsive Helpers =====================
    def _on_window_resize(self, event):
        """Handle window resize for responsive design"""
        if event.widget == self.root:
            # Update window size info for responsive adjustments
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            # Adjust font sizes based on window size
            if width < 800 or height < 600:
                # Small window - reduce font sizes
                self._adjust_font_sizes("small")
            elif width > 1200 and height > 800:
                # Large window - increase font sizes
                self._adjust_font_sizes("large")
            else:
                # Normal window - default font sizes
                self._adjust_font_sizes("normal")
    
    def _adjust_font_sizes(self, size_mode):
        """Adjust font sizes based on window size"""
        try:
            if size_mode == "small":
                font_size = 9
                title_size = 14
            elif size_mode == "large":
                font_size = 11
                title_size = 18
            else:  # normal
                font_size = 10
                title_size = 16
            
            # Update title font
            if hasattr(self, 'title'):
                self.title.config(font=("Arial", title_size, "bold"))
            
            # Update entry fonts
            if hasattr(self, 'email_entry'):
                self.email_entry.config(font=("Arial", font_size))
            if hasattr(self, 'password_entry'):
                self.password_entry.config(font=("Arial", font_size))
            if hasattr(self, 'media_entry'):
                self.media_entry.config(font=("Arial", font_size))
            if hasattr(self, 'exec_email_combo'):
                self.exec_email_combo.config(font=("Arial", font_size))
            
            # Update text area font
            if hasattr(self, 'prompt_text'):
                self.prompt_text.config(font=("Arial", font_size))
                
        except Exception:
            pass  # Ignore font adjustment errors

    # ===================== Helpers =====================
    def _on_method_change(self) -> None:
        method = self.login_method.get()
        if method == "browser":
            try:
                self.password_label.grid_remove()
                self.password_entry.grid_remove()
                self.note_label.config(text="Browser Login sẽ mở Chrome để đăng nhập Google Flow, hỗ trợ 2FA")
            except Exception:
                pass
        else:
            row = 1
            try:
                self.password_label.grid(row=row, column=0, sticky=tk.W, pady=5)
                self.password_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
                self.note_label.config(text="Nhập mật khẩu Google của bạn (có thể cần 2FA)")
            except Exception:
                pass

    def _load_profiles(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.flow_profiles_path), exist_ok=True)
            if os.path.exists(self.flow_profiles_path):
                with open(self.flow_profiles_path, 'r', encoding='utf-8') as f:
                    self.flow_profiles = json.load(f)
            else:
                self.flow_profiles = {}
        except Exception:
            self.flow_profiles = {}

    def _save_profiles(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.flow_profiles_path), exist_ok=True)
            with open(self.flow_profiles_path, 'w', encoding='utf-8') as f:
                json.dump(self.flow_profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_profiles_list(self) -> None:
        try:
            self.profiles_list.delete(0, tk.END)
            items = sorted(self.flow_profiles.items(), key=lambda kv: kv[1].get("last_login", 0), reverse=True)
            for email_addr, meta in items:
                ts = meta.get("last_login")
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else ""
                self.profiles_list.insert(tk.END, f"{email_addr}  |  {time_str}")
        except Exception:
            pass

    def _refresh_exec_emails(self) -> None:
        try:
            emails = list(self.flow_profiles.keys())
            self.exec_email_combo['values'] = emails
            if emails and not self.exec_email.get():
                self.exec_email.set(emails[0])
        except Exception:
            pass

    # ===================== Login Flow =====================
    def _login_flow(self) -> None:
        email = (self.email_entry.get() or "").strip()
        if not email:
            messagebox.showerror("Lỗi", "Vui lòng nhập email!")
            return
        self.current_email = email
        password = (self.password_entry.get() or "").strip()
        if not password:
            messagebox.showerror("Lỗi", "Vui lòng nhập mật khẩu!")
            return
        threading.Thread(target=self._login_flow_password_thread, args=(email, password), daemon=True).start()

    def _build_chrome(self, cache_key: str, existing_cache_dir: str = None) -> webdriver.Chrome:
        chrome_options = Options()
        # Ưu tiên dùng cache cũ nếu có
        cache_dir = None
        if existing_cache_dir and os.path.isdir(existing_cache_dir):
            cache_dir = existing_cache_dir
        else:
            safe_key = re.sub(r'[^a-zA-Z0-9_.-]', '_', cache_key) or "default"
            cache_dir = os.path.join(os.getcwd(), "chrome_cache", f"flow_{safe_key}")
            os.makedirs(cache_dir, exist_ok=True)
        self.current_cache_dir = cache_dir
        # Nếu profile đang bị một Chrome khác giữ, báo lỗi rõ ràng
        try:
            lock_file = os.path.join(cache_dir, "SingletonLock")
            if os.path.exists(lock_file):
                raise Exception("Profile cache đang được sử dụng bởi một phiên Chrome khác. Hãy đóng trình duyệt đang mở bằng cache này rồi thử lại.")
        except Exception as _:
            # Nếu raise ở trên thì sẽ bị catch ở try/catch phía trên caller
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
        
        # Headless mode nếu được chọn
        if self.headless_mode.get():
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

        # Bật performance logging để đọc Network logs
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
        # Bật Network domain để có thể lấy response body qua CDP
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass
        return driver

    def _login_flow_browser_thread(self, email_addr: str) -> None:
        try:
            self._set_status("Đang mở trình duyệt...", "orange")
            self.login_btn.config(state="disabled")
            meta = self.flow_profiles.get(email_addr)
            exist_dir = meta.get("cache_dir") if meta else None
            self.driver = self._build_chrome(email_addr, existing_cache_dir=exist_dir)

            # Go to Flow
            self.driver.get("https://labs.google/fx/tools/flow")
            self._human_delay(2, 4)

            # If not signed in, go through Google sign-in
            if self._flow_requires_login(self.driver):
                self._set_status("Yêu cầu đăng nhập Google - đang chuyển hướng...", "orange")
                self._trigger_flow_login(self.driver)
                self._human_delay(2, 4)
                self._handle_google_login(self.driver, email_addr)

            # Wait for Flow home after sign-in
            ok = self._wait_until(lambda: "labs.google" in self.driver.current_url, timeout=120)
            if not ok:
                raise Exception("Hết thời gian chờ vào Google Flow")

            self._remember_profile(email_addr, self.current_cache_dir, self.current_user_agent)
            self.login_success = True
            self._set_status("Đăng nhập thành công Google Flow", "green")
            messagebox.showinfo("Thành công", "Đăng nhập Google Flow thành công!")
        except Exception as ex:
            self.login_success = False
            self._set_status("Đăng nhập thất bại", "red")
            messagebox.showerror("Lỗi", f"Lỗi đăng nhập: {ex}")
        finally:
            self.login_btn.config(state="normal")

    def _login_flow_password_thread(self, email_addr: str, password: str) -> None:
        try:
            # Password flow still uses browser to complete 2FA if needed
            self._set_status("Đang mở trình duyệt...", "orange")
            self.login_btn.config(state="disabled")
            meta = self.flow_profiles.get(email_addr)
            exist_dir = meta.get("cache_dir") if meta else None
            self.driver = self._build_chrome(email_addr, existing_cache_dir=exist_dir)
            self.driver.get("https://accounts.google.com/signin")
            self._human_delay(2, 4)
            self._google_type_email_then_password(self.driver, email_addr, password)

            ok = self._wait_signin_success(self.driver, timeout=180)
            if not ok:
                raise Exception("Không thể đăng nhập tài khoản Google")

            # After Google is signed in, open Flow
            self.driver.get("https://labs.google/fx/tools/flow")
            self._wait_until(lambda: "labs.google" in self.driver.current_url, timeout=120)

            self._remember_profile(email_addr, self.current_cache_dir, self.current_user_agent)
            self.login_success = True
            self._set_status("Đăng nhập thành công Google Flow", "green")
            messagebox.showinfo("Thành công", "Đăng nhập Google Flow thành công!")
        except Exception as ex:
            self.login_success = False
            self._set_status("Đăng nhập thất bại", "red")
            messagebox.showerror("Lỗi", f"Lỗi đăng nhập: {ex}")
        finally:
            self.login_btn.config(state="normal")

    # ===================== Execute Media =====================
    def _open_flow_for_exec(self) -> None:
        email_addr = self.exec_email.get()
        if not email_addr:
            messagebox.showerror("Lỗi", "Vui lòng chọn email đã có cache!")
            return
        meta = self.flow_profiles.get(email_addr)
        if not meta:
            messagebox.showerror("Lỗi", "Không tìm thấy cache cho email đã chọn!")
            return
        threading.Thread(target=self._open_profile_thread, args=(email_addr, meta, True), daemon=True).start()

    def _open_profile_thread(self, email_addr: str, meta: dict, go_flow: bool) -> None:
        try:
            drv = self._open_profile_driver(meta)
            if go_flow:
                drv.get("https://labs.google/fx/vi/tools/flow")
                self._wait_until(lambda: "labs.google" in drv.current_url, timeout=120)
            self._set_exec_status(f"Đã mở Flow cho {email_addr}", "green")
        except Exception as ex:
            self._set_exec_status(f"Lỗi mở Flow: {ex}", "red")

    def _execute_workflow(self) -> None:
        email_addr = self.exec_email.get()
        if not email_addr:
            messagebox.showerror("Lỗi", "Vui lòng chọn email!")
            return
        meta = self.flow_profiles.get(email_addr)
        if not meta:
            messagebox.showerror("Lỗi", "Không tìm thấy cache cho email đã chọn!")
            return
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        media = (self.media_paths.get() or "").strip()
        wf = self.workflow.get()

        threading.Thread(target=self._execute_thread, args=(email_addr, meta, wf, prompt, media), daemon=True).start()

    def _execute_thread(self, email_addr: str, meta: dict, wf: str, prompt: str, media: str) -> None:
        try:
            self._log_exec("Opening Flow page...")
            drv = self._open_profile_driver(meta)
            wait = WebDriverWait(drv, 30)
            drv.get("https://labs.google/fx/vi/tools/flow")
            loaded = self._wait_until(lambda: "labs.google" in drv.current_url, timeout=120)
            if not loaded:
                self._log_exec("Failed to load Flow page", error=True)
                return
            time.sleep(2)

            # Choose workflow
            self._log_exec("Click New project (if visible)...")
            # Mở/nhấn nút tạo dự án mới trước khi chọn workflow
            try:
                old_url = drv.current_url
                self._click_new_project(drv)
                # Theo yêu cầu: đợi 5s sau khi nhấn và đợi trang mới load xong
                self._log_exec("Waiting 5s for project page to open...")
                time.sleep(5)
                self._log_exec("Waiting for workspace to load...")
                # Đợi URL thay đổi hoặc các phần tử chính của workspace xuất hiện
                def page_ready():
                    try:
                        if drv.current_url != old_url:
                            return True
                        if drv.find_elements(By.ID, "PINHOLE_TEXT_AREA_ELEMENT_ID"):
                            return True
                        if drv.find_elements(By.CSS_SELECTOR, "button[role='combobox']"):
                            return True
                    except Exception:
                        pass
                    return False
                ready = self._wait_until(page_ready, timeout=30, interval=0.5)
                if not ready:
                    self._log_exec("Workspace not detected after New project. Continuing best-effort...", error=False)
            except Exception:
                self._log_exec("New project button not found - continue")

            self._log_exec("Typing prompt into textarea...")
            # Gõ prompt vào textarea id=PINHOLE_TEXT_AREA_ELEMENT_ID
            try:
                area = drv.find_element(By.ID, "PINHOLE_TEXT_AREA_ELEMENT_ID")
                self._human_click_el(drv, area)
                try:
                    area.clear()
                except Exception:
                    pass
                if prompt:
                    self._human_type_el(area, prompt)
                    self._log_exec("Prompt typed successfully.")
                else:
                    self._log_exec("No prompt provided, skipping typing.")
            except Exception:
                # Fallback: bất kỳ textarea nào nếu id không có
                self._log_exec("PINHOLE_TEXT_AREA_ELEMENT_ID not found, trying fallback textarea...")
                self._type_into_any(drv, [
                    (By.ID, "PINHOLE_TEXT_AREA_ELEMENT_ID"),
                    (By.CSS_SELECTOR, "textarea#PINHOLE_TEXT_AREA_ELEMENT_ID"),
                    (By.CSS_SELECTOR, "textarea")
                ], prompt)

            # Mở combobox chọn workflow và chọn theo wf
            try:
                self._log_exec("Opening workflow combobox and selecting option...")
                self._select_workflow_via_combobox(drv, wf)
                self._log_exec("Workflow selected.")
            except Exception:
                self._log_exec("Failed to select workflow via combobox", error=True)

            # Áp dụng các setting trong popover (Aspect ratio, Outputs per prompt, Model)
            try:
                self._log_exec("Opening settings popover and applying options...")
                self._open_settings_and_apply(drv, self.aspect_ratio.get(), self.outputs_per_prompt.get(), self.model_choice.get())
                self._log_exec("Settings applied.")
            except Exception as ex:
                self._log_exec(f"Failed to apply settings: {ex}", error=True)

            # Apply config if UI exposes inputs (best-effort)
            # (Removed) basic config for resolution/duration/fps per user request

            # Upload media: chỉ áp dụng cho frames_to_video
            if wf == "frames_to_video" and media:
                try:
                    self._log_exec("Waiting 3s after workflow selection before opening add panel...")
                    time.sleep(3)
                    self._log_exec("Opening frames upload panel...")
                    self._open_frames_upload_panel(drv)
                except Exception:
                    self._log_exec("Could not open frames upload panel (will still try upload)")
                self._log_exec("Uploading media (frames)...")
                self._upload_media_any(drv, media)
                self._log_exec("Upload step finished (best-effort).")
                # Nhấn "Cắt và lưu" và đợi đến khi xuất hiện khung hình đầu tiên
                try:
                    self._log_exec("Clicking 'Cắt và lưu' and waiting for first frame...")
                    self._confirm_crop_and_wait_first_frame(drv)
                    self._log_exec("First frame detected.")
                    # Sau khi có khung hình đầu tiên, nhấn nút Tạo (Create)
                    self._log_exec("Clicking 'Tạo' (Create) button...")
                    self._click_create_button(drv)
                    self._log_exec("Clicked 'Tạo' successfully.")
                    # Chờ 10s rồi theo dõi tiến trình và tải kết quả
                    self._log_exec("Waiting 10s before monitoring processing...")
                    time.sleep(10)
                    self._log_exec("Monitoring processing and then reading API logs...")
                    self._monitor_and_fetch_api(drv)
                except Exception:
                    self._log_exec("Could not confirm crop/save or detect first frame", error=True)

            # Execute/Run
            self._log_exec("Submitting job...")
            self._try_click_any(drv, [
                "//button[contains(., 'Run')]",
                "//button[contains(., 'Generate')]",
                "//button[contains(., 'Create')]",
                "//*[contains(text(), 'Run')]",
                "//*[contains(text(), 'Generate')]",
            ])

            self._log_exec("Request submitted. Check results in Flow.", success=True)
        except Exception as ex:
            self._log_exec(f"Execute error: {ex}", error=True)

    # ===================== Selenium Utils =====================
    def _flow_requires_login(self, driver: webdriver.Chrome) -> bool:
        try:
            # If any sign-in indicator or redirect present
            texts = ["Sign in", "Đăng nhập", "Log in"]
            for xp in [f"//*[contains(text(), '{t}')]" for t in texts]:
                if driver.find_elements(By.XPATH, xp):
                    return True
            # Or Google accounts domain
            url = driver.current_url or ""
            if "accounts.google.com" in url:
                return True
        except Exception:
            pass
        return False

    def _click_new_project(self, driver: webdriver.Chrome) -> None:
        """Nhấn nút tạo dự án mới trên trang Flow (EN/VI)."""
        candidates = [
            "//button[normalize-space()='New project']",
            "//button[contains(., 'New project')]",
            "//a[normalize-space()='New project']",
            "//a[contains(., 'New project')]",
            "//button[normalize-space()='Dự án mới']",
            "//button[contains(., 'Dự án mới')]",
            "//a[normalize-space()='Dự án mới']",
            "//a[contains(., 'Dự án mới')]",
        ]
        for xp in candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                return
            except Exception:
                continue

    def _select_workflow_via_combobox(self, driver: webdriver.Chrome, wf: str) -> None:
        """Mở combobox (button[role="combobox"]) và chọn mục theo wf.
        wf == 'text_to_video' -> chọn mục đầu tiên; 'frames_to_video' -> mục thứ 2.
        Đồng thời hỗ trợ text tiếng Việt trong dropdown Radix.
        """
        # Click trigger combobox
        trigger = driver.find_element(By.CSS_SELECTOR, "button[role='combobox']")
        self._human_click_el(driver, trigger)
        time.sleep(0.3)

        # Đợi content xuất hiện (role=listbox)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[@role='listbox']"))
            )
        except Exception:
            pass

        # Ưu tiên chọn theo vị trí
        option_index = 1 if wf == "text_to_video" else 2
        try:
            options = driver.find_elements(By.XPATH, "//*[@role='listbox']//*[@role='option']")
            if options and len(options) >= option_index:
                self._human_click_el(driver, options[option_index - 1])
                return
        except Exception:
            pass

        # Fallback: chọn theo text tiếng Việt/Anh
        if wf == "text_to_video":
            texts = [
                "Từ văn bản sang video",
                "Text to Video",
            ]
        else:
            texts = [
                "Tạo video từ các khung hình",
                "Frames to Video",
            ]
        for t in texts:
            try:
                el = driver.find_element(By.XPATH, f"//*[@role='listbox']//*[contains(., '{t}')]")
                self._human_click_el(driver, el)
                return
            except Exception:
                continue

    def _trigger_flow_login(self, driver: webdriver.Chrome) -> None:
        # Try clicking login button on Flow if available
        self._try_click_any(driver, [
            "//button[contains(., 'Sign in')]",
            "//a[contains(., 'Sign in')]",
            "//*[contains(text(), 'Sign in')]",
        ])

    def _handle_google_login(self, driver: webdriver.Chrome, email_addr: str) -> None:
        try:
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.NAME, "identifier")))
            email_input = driver.find_element(By.NAME, "identifier")
            self._human_click_el(driver, email_input)
            email_input.clear()
            self._human_type_el(email_input, email_addr)
            driver.find_element(By.ID, "identifierNext").click()
            self._human_delay(2, 4)
            # Let user finish password/2FA manually
            messagebox.showinfo("Hướng dẫn", "Vui lòng hoàn tất nhập mật khẩu và xác thực 2FA (nếu có) trong trình duyệt mở.")
            # Thử đóng hộp thoại Passkey nếu xuất hiện
            try:
                self._dismiss_passkey_prompt(driver)
            except Exception:
                pass
            self._wait_signin_success(driver, timeout=300)
        except Exception:
            pass

    def _google_type_email_then_password(self, driver: webdriver.Chrome, email_addr: str, password: str) -> None:
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.NAME, "identifier")))
        email_input = driver.find_element(By.NAME, "identifier")
        self._human_click_el(driver, email_input)
        email_input.clear()
        self._human_type_el(email_input, email_addr)
        driver.find_element(By.ID, "identifierNext").click()
        self._human_delay(2, 4)
        try:
            wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            pw_input = driver.find_element(By.NAME, "Passwd")
        except TimeoutException:
            pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        self._human_click_el(driver, pw_input)
        pw_input.clear()
        self._human_type_el(pw_input, password)
        self._human_delay(0.5, 1.5)
        try:
            driver.find_element(By.ID, "passwordNext").click()
        except Exception:
            pw_input.send_keys(Keys.ENTER)
        # Sau khi submit mật khẩu, cố gắng đóng Passkey prompt nếu có
        try:
            self._human_delay(1, 2)
            self._dismiss_passkey_prompt(driver)
        except Exception:
            pass

    def _wait_signin_success(self, driver: webdriver.Chrome, timeout: int = 180) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                # Thử đóng Passkey prompt nếu xuất hiện trong lúc chờ
                try:
                    self._dismiss_passkey_prompt(driver)
                except Exception:
                    pass
                if self._is_google_signed_in(driver):
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def _dismiss_passkey_prompt(self, driver: webdriver.Chrome) -> None:
        """Đóng hộp thoại gợi ý thêm Passkey bằng cách bấm Not now/No thanks/Bỏ qua."""
        try:
            candidates = [
                "//button[normalize-space()='Not now']",
                "//button[contains(., 'Not now')]",
                "//div[@role='dialog']//button[normalize-space()='Not now']",
                "//span[normalize-space()='Not now']/parent::button",
                "//button[normalize-space()='No thanks']",
                "//button[contains(., 'No thanks')]",
                "//span[normalize-space()='No thanks']/parent::button",
                "//button[normalize-space()='Skip']",
                "//button[contains(., 'Skip')]",
                "//span[normalize-space()='Skip']/parent::button",
                # Vietnamese fallbacks
                "//button[contains(., 'Không phải bây giờ')]",
                "//button[contains(., 'Bỏ qua')]",
            ]
            for xp in candidates:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    self._human_click_el(driver, el)
                    time.sleep(0.5)
                    return
                except Exception:
                    continue
        except Exception:
            pass

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

    def _remember_profile(self, email_addr: str, cache_dir: str, user_agent: str) -> None:
        if not email_addr:
            return
        self.flow_profiles[email_addr] = {
            "cache_dir": cache_dir,
            "user_agent": user_agent,
            "last_login": int(time.time()),
        }
        self._save_profiles()
        self._refresh_profiles_list()
        self._refresh_exec_emails()

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
        
        # Headless mode nếu được chọn
        if self.headless_mode.get():
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
        # Bật performance logging để đọc Network logs
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

    def _open_selected_profile(self) -> None:
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.flow_profiles.get(email_addr)
            if not meta:
                messagebox.showerror("Lỗi", "Không tìm thấy cache!")
                return
            threading.Thread(target=self._open_profile_thread, args=(email_addr, meta, False), daemon=True).start()
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể mở profile: {ex}")

    def _delete_selected_profile(self) -> None:
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.flow_profiles.get(email_addr)
            if not meta:
                return
            cache_dir = meta.get("cache_dir")
            try:
                if cache_dir and os.path.isdir(cache_dir):
                    import shutil
                    shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception:
                pass
            self.flow_profiles.pop(email_addr, None)
            self._save_profiles()
            self._refresh_profiles_list()
            self._refresh_exec_emails()
            self._set_status(f"Đã xóa cache của {email_addr}", "green")
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể xóa cache: {ex}")

    # ===================== Generic Actions =====================
    def _choose_image_file(self) -> None:
        """Choose single image file for upload"""
        try:
            file = filedialog.askopenfilename(
                title="Chọn file ảnh",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff *.webp"),
                    ("JPEG files", "*.jpg *.jpeg"),
                    ("PNG files", "*.png"),
                    ("All files", "*.*")
                ]
            )
            if file:
                self.media_paths.set(file)
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể chọn file ảnh: {ex}")

    def _apply_basic_config(self, driver: webdriver.Chrome, resolution: str, duration: str, fps: str) -> None:
        # Best-effort: try to locate simple inputs/selects
        try:
            # Resolution dropdown/select
            for xp in [
                "//select[contains(@name, 'resolution')]",
                "//select[contains(@id, 'resolution')]",
                "//label[contains(., 'Resolution')]/following::select[1]",
            ]:
                els = driver.find_elements(By.XPATH, xp)
                if els:
                    try:
                        els[0].click()
                        time.sleep(0.2)
                        opt = driver.find_elements(By.XPATH, f"//option[contains(., '{resolution}')]")
                        if opt:
                            opt[0].click()
                    except Exception:
                        pass

            # Duration
            self._type_into_any(driver, [
                (By.XPATH, "//input[@type='number' and contains(@name, 'duration')]"),
                (By.XPATH, "//input[contains(@placeholder, 'Duration')]")
            ], duration)

            # FPS
            self._type_into_any(driver, [
                (By.XPATH, "//input[@type='number' and contains(@name, 'fps')]"),
                (By.XPATH, "//input[contains(@placeholder, 'FPS')]")
            ], fps)
        except Exception:
            pass

    def _upload_media_any(self, driver: webdriver.Chrome, media: str) -> None:
        # Chỉ upload 1 file ảnh duy nhất
        if not media or not os.path.isfile(media):
            self._log_exec("No valid image file provided", error=True)
            return
            
        # Kiểm tra đuôi file có phải ảnh không
        image_extensions = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"]
        if not any(media.lower().endswith(ext) for ext in image_extensions):
            self._log_exec("File must be an image (png, jpg, jpeg, webp, bmp, gif, tiff)", error=True)
            return
            
        self._log_exec(f"Uploading single image: {os.path.basename(media)}")
        
        # Try visible inputs first
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            try:
                inputs[0].send_keys(media)
                self._log_exec("File uploaded successfully via file input")
                return
            except Exception as ex:
                self._log_exec(f"Failed to upload via file input: {ex}", error=True)
                pass

        # Try clicking upload buttons then re-scan inputs
        self._try_click_any(driver, [
            "//button[contains(., 'Upload')]",
            "//button[contains(., 'Add')]",
            "//div[contains(., 'Upload')]",
            "//*[contains(@class, 'upload')]",
        ])
        time.sleep(0.5)
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if inputs:
            try:
                if len(files) == 1:
                    inputs[0].send_keys(files[0])
                else:
                    for f in files:
                        inputs[0].send_keys(f)
                return
            except Exception:
                pass

    def _type_into_any(self, driver: webdriver.Chrome, locators, text: str) -> None:
        if not text:
            return
        for by, sel in locators:
            try:
                el = driver.find_element(by, sel)
                self._human_click_el(driver, el)
                try:
                    el.clear()
                except Exception:
                    pass
                self._human_type_el(el, text)
                break
            except Exception:
                continue

    def _try_click_any(self, driver: webdriver.Chrome, xpaths) -> None:
        for xp in xpaths:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                time.sleep(0.3)
                return
            except Exception:
                continue

    def _log_exec(self, message: str, success: bool = False, error: bool = False) -> None:
        """Log ra console và cập nhật nhãn trạng thái trên tab Execute."""
        prefix = "[EXEC]"
        print(f"{prefix} {message}")
        if error:
            self._set_exec_status(message, "red")
        elif success:
            self._set_exec_status(message, "green")
        else:
            self._set_exec_status(message, "orange")

    def _open_frames_upload_panel(self, driver: webdriver.Chrome) -> None:
        """Mở panel thêm media cho workflow Frames to Video theo mô tả UI.
        1) Click nút có icon 'add' (có thể là button với overlay)
        2) Click nút 'Tải lên' (icon 'upload') để bắt đầu upload ảnh
        """
        # Bước 1: Nút add
        add_candidates = [
            "//button[.//i[contains(text(),'add')]]",
            "//button[contains(@class,'sc-d6df593a') and .//i[contains(text(),'add')]]",
            "//i[text()='add']/ancestor::button[1]",
            "//button[contains(., 'Add') or contains(., 'Thêm')]",
        ]
        for xp in add_candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                time.sleep(0.5)
                break
            except Exception:
                continue

        # Bước 2: Nút "Tải lên" (VN) hoặc tương đương với icon 'upload'
        upload_candidates = [
            "//button[.//div[contains(., 'Tải lên')]]",
            "//button[contains(., 'Tải lên')]",
            "//button[.//i[normalize-space(text())='upload']]",
            "//i[normalize-space(text())='upload']/ancestor::button[1]",
            "//button[contains(., 'Upload')]",
        ]
        for xp in upload_candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                time.sleep(0.5)
                return
            except Exception:
                continue

    def _confirm_crop_and_wait_first_frame(self, driver: webdriver.Chrome) -> None:
        """Nhấn nút 'Cắt và lưu' và đợi đến khi phần tử 'Khung hình đầu tiên' xuất hiện (đã có ảnh)."""
        # Click nút Cắt và lưu (VI) hoặc 'Crop and save' (EN fallback)
        crop_candidates = [
            "//button[.//i[normalize-space(text())='crop'] and contains(., 'Cắt và lưu')]",
            "//button[contains(., 'Cắt và lưu')]",
            "//button[.//i[normalize-space(text())='crop'] and contains(., 'Crop')]",
            "//button[contains(., 'Crop and save')]",
        ]
        for xp in crop_candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                time.sleep(0.5)
                break
            except Exception:
                continue

        # Đợi xuất hiện nút chứa nội dung 'Khung hình đầu tiên'
        def first_frame_ready():
            try:
                return len(driver.find_elements(By.XPATH, "//button[.//span[normalize-space(text())='Khung hình đầu tiên']]") ) > 0
            except Exception:
                return False
        ok = self._wait_until(first_frame_ready, timeout=60, interval=0.5)
        if not ok:
            raise Exception("First frame not detected after crop/save")

    def _click_create_button(self, driver: webdriver.Chrome) -> None:
        """Nhấn nút 'Tạo' (Create) với icon arrow_forward. Đợi nút enabled trước khi click."""
        # Chờ nút xuất hiện và enabled
        def get_button():
            candidates = [
                "//button[.//span[normalize-space(text())='Tạo']]",
                "//button[.//i[normalize-space(text())='arrow_forward']]",
                "//button[contains(., 'Tạo') or contains(., 'Create')]",
            ]
            for xp in candidates:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    return el
                except Exception:
                    continue
            return None

        start = time.time()
        btn = None
        while time.time() - start < 30:
            btn = get_button()
            if btn is not None:
                try:
                    disabled = btn.get_attribute('disabled')
                    aria_disabled = btn.get_attribute('aria-disabled')
                    if not disabled and (aria_disabled in (None, '', 'false')):
                        break
                except Exception:
                    break
            time.sleep(0.5)

        if btn is None:
            raise Exception("Create button not found")
        try:
            self._human_click_el(driver, btn)
            time.sleep(0.3)
        except Exception:
            # Fallback: try executing click via JS
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.3)
            except Exception as ex:
                raise Exception(f"Failed to click Create button: {ex}")

    def _monitor_and_fetch_api(self, driver: webdriver.Chrome) -> None:
        """Theo dõi xử lý đến khi có video, sau đó reload trang và đọc API project.searchProjectWorkflows
        để lấy danh sách fifeUri, sau đó tải về máy."""
        # Chờ đến khi xuất hiện ít nhất 1 video (hoàn tất)
        def any_video_ready():
            try:
                return len(driver.find_elements(By.TAG_NAME, 'video')) > 0
            except Exception:
                return False

        # Poll tối đa 5 phút
        start = time.time()
        while time.time() - start < 300:
            # Log phần trăm nếu tìm thấy
            try:
                percents = driver.find_elements(By.XPATH, "//*[contains(text(), '%')]")
                if percents:
                    txt = percents[0].text.strip()
                    if txt.endswith('%'):
                        self._log_exec(f"Processing... {txt}")
            except Exception:
                pass

            if any_video_ready():
                break
            time.sleep(3)

        # Thu thập các card chứa video
        videos = driver.find_elements(By.TAG_NAME, 'video')
        if not videos:
            self._log_exec("No videos detected after processing window", error=True)
            return

        self._log_exec(f"Found {len(videos)} video(s). Reading Network logs for API JSON...")
        try:
            logs = driver.get_log('performance')
        except Exception:
            logs = []

        # Tìm response của API project.searchProjectWorkflows từ performance logs
        target_fragment = '/fx/api/trpc/project.searchProjectWorkflows'
        request_ids = []
        for item in logs:
            try:
                msg = json.loads(item.get('message', '{}')).get('message', {})
                method = msg.get('method')
                params = msg.get('params', {})
                if method == 'Network.responseReceived':
                    response = params.get('response', {})
                    url = response.get('url', '')
                    if target_fragment in url and response.get('mimeType', '').startswith('application/json'):
                        request_ids.append(params.get('requestId'))
            except Exception:
                continue

        # Lấy response body qua CDP cho từng request id tìm thấy
        all_urls = []
        for rid in request_ids:
            try:
                body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': rid})
                text = body.get('body', '')
                try:
                    data = json.loads(text)
                except Exception:
                    data = text
                urls = self._extract_fife_uris_from_api_json(data)
                all_urls.extend(urls)
            except Exception:
                continue

        if all_urls:
            self._log_exec(f"Found {len(all_urls)} media URL(s) in Network logs. Downloading...")
            self._download_files(all_urls)
        else:
            self._log_exec("No API JSON found in Network logs or no media URLs extracted", error=True)

    def _extract_fife_uris_from_api_json(self, payload):
        urls = []
        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
        except Exception:
            return urls
        try:
            result = payload.get('result', {})
            d2 = result.get('data', {})
            j = d2.get('json', {})
            res = j.get('result', {})
            workflows = res.get('workflows', [])
            for wf in workflows:
                for st in wf.get('workflowSteps', []):
                    for g in st.get('mediaGenerations', []):
                        try:
                            vd = g.get('mediaData', {}).get('videoData', {})
                            fife = vd.get('fifeUri')
                            if fife:
                                urls.append(fife)
                        except Exception:
                            continue
        except Exception:
            return urls
        return urls

    def _download_files(self, urls):
        try:
            out_dir = Path(os.getcwd()) / "downloads" / time.strftime("%Y%m%d_%H%M%S")
            out_dir.mkdir(parents=True, exist_ok=True)
            for i, url in enumerate(urls, 1):
                try:
                    ext = ".mp4"
                    if 'image' in url:
                        ext = ".png"
                    filename = f"media_{i}{ext}"
                    dest = out_dir / filename
                    self._log_exec(f"Downloading {filename}...")
                    urllib.request.urlretrieve(url, dest.as_posix())
                    self._log_exec(f"Downloaded {filename}", success=True)
                except Exception as ex:
                    self._log_exec(f"Failed to download #{i}: {ex}", error=True)
            messagebox.showinfo("Hoàn tất", f"Đã tải {len(urls)} file về: {out_dir}")
        except Exception as ex:
            self._log_exec(f"Download error: {ex}", error=True)

    def _open_settings_and_apply(self, driver: webdriver.Chrome, aspect: str, outputs: str, model: str) -> None:
        """Mở popover Cài đặt (tune) và đặt: Tỷ lệ khung hình, Outputs per prompt, Model."""
        # Mở popover Cài đặt
        settings_btn_xp = [
            "//button[.//i[normalize-space(text())='tune']]",
            "//button[.//span[normalize-space(text())='Cài đặt']]",
            "//button[contains(., 'Cài đặt') or contains(., 'Settings')]",
        ]
        clicked = False
        for xp in settings_btn_xp:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            raise Exception("Settings button not found")

        # Đợi popover role=dialog mở
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//*[@role='dialog']")))
        except Exception:
            pass

        # Helper chọn từ combobox theo nhãn
        def select_from_combobox(label_texts, option_texts):
            # Tìm combobox có label tương ứng
            for label_text in label_texts:
                try:
                    combo = driver.find_element(By.XPATH, f"//button[@role='combobox'][.//span[normalize-space(text())='{label_text}']]")
                    self._log_exec(f"Opening combobox: {label_text}...")
                    self._human_click_el(driver, combo)
                    # Đợi popover listbox mở
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//*[@role='listbox' and @data-state='open' or @data-state='checked' or @data-state='unchecked' or @id]"))
                        )
                    except Exception:
                        pass
                    # mở listbox và chọn option theo text (ưu tiên match chính xác span)
                    for opt_text in option_texts:
                        # Thử match exact trong span
                        for xp in [
                            f"//*[@role='listbox']//span[normalize-space(text())='{opt_text}']",
                            f"//*[@role='listbox']//*[contains(., '{opt_text}')]",
                        ]:
                            try:
                                el = driver.find_element(By.XPATH, xp)
                                self._human_click_el(driver, el)
                                time.sleep(0.2)
                                return True
                            except Exception:
                                continue
                    # Nếu chưa tìm thấy, thử scroll viewport của listbox rồi tìm lại
                    try:
                        viewport = driver.find_element(By.CSS_SELECTOR, "[data-radix-select-viewport]")
                        driver.execute_script("arguments[0].scrollTop = 0;", viewport)
                        time.sleep(0.1)
                        for opt_text in option_texts:
                            try:
                                el = driver.find_element(By.XPATH, f"//*[@role='listbox']//span[normalize-space(text())='{opt_text}']")
                                self._human_click_el(driver, el)
                                time.sleep(0.2)
                                return True
                            except Exception:
                                continue
                    except Exception:
                        pass
                except Exception:
                    continue
            return False

        # 1) Aspect ratio
        aspect_map = {
            "16:9": ["Khổ ngang (16:9)", "Landscape (16:9)"],
            "9:16": ["Khổ dọc (9:16)", "Portrait (9:16)"],
            "1:1": ["Vuông (1:1)", "Square (1:1)"],
        }
        select_from_combobox(["Tỷ lệ khung hình", "Aspect ratio"], aspect_map.get(aspect, [aspect]))

        # 2) Outputs per prompt
        select_from_combobox(["Câu trả lời đầu ra cho mỗi câu lệnh", "Outputs per prompt"], [outputs])

        # 3) Model
        select_from_combobox(["Mô hình", "Model"], [model])

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

    # ===================== Human-like helpers =====================
    def _human_delay(self, min_seconds: float = 1.0, max_seconds: float = 2.5) -> None:
        time.sleep(random.uniform(min_seconds, max_seconds))

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

    # ===================== Status =====================
    def _set_status(self, text: str, color: str) -> None:
        try:
            # Map colors to styles
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

    def _set_exec_status(self, text: str, color: str) -> None:
        try:
            # Map colors to styles
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


def main() -> None:
    root = tk.Tk()
    app = FlowBrowserTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()


