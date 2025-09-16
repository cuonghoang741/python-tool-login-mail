import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import imaplib
import email
import threading
from email.header import decode_header
import ssl
import time
import json
import os
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class GmailBrowserLoginTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Gmail Browser Login Tool")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Biến lưu trữ
        self.mail = None
        self.is_connected = False
        self.driver = None
        self.login_success = False
        self.current_email = None
        self.current_cache_dir = None
        self.current_user_agent = None
        self.debug_check_counter = 0
        
        # User agents và human behavior
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
        # Hồ sơ/cache theo email
        self.profiles_path = os.path.join(os.getcwd(), "chrome_cache", "profiles.json")
        self.profiles = {}
        self._load_profiles()

        self.setup_ui()
        
    def setup_ui(self):
        # Frame chính
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Cấu hình grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Tiêu đề
        title_label = ttk.Label(main_frame, text="Gmail Browser Login Tool", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Phương thức đăng nhập
        method_frame = ttk.LabelFrame(main_frame, text="Chọn phương thức đăng nhập", padding="10")
        method_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.login_method = tk.StringVar(value="browser")
        ttk.Radiobutton(method_frame, text="🌐 Browser Login (Khuyến nghị)", 
                       variable=self.login_method, value="browser",
                       command=self.on_method_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(method_frame, text="🔐 Mật khẩu trực tiếp", 
                       variable=self.login_method, value="password",
                       command=self.on_method_change).pack(anchor=tk.W, pady=2)
        
        # Frame thông tin đăng nhập
        self.login_frame = ttk.LabelFrame(main_frame, text="Thông tin đăng nhập", padding="10")
        self.login_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.login_frame.columnconfigure(1, weight=1)
        
        # Email
        ttk.Label(self.login_frame, text="Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(self.login_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Mật khẩu (chỉ hiện khi chọn password method)
        self.password_label = ttk.Label(self.login_frame, text="Mật khẩu:")
        self.password_entry = ttk.Entry(self.login_frame, width=40, show="*")
        
        # Loại mật khẩu (chỉ hiện khi chọn password method)
        self.password_type_frame = ttk.Frame(self.login_frame)
        self.password_type = tk.StringVar(value="normal")
        self.normal_radio = ttk.Radiobutton(self.password_type_frame, text="Mật khẩu thường", 
                                           variable=self.password_type, value="normal")
        self.app_radio = ttk.Radiobutton(self.password_type_frame, text="App Password", 
                                        variable=self.password_type, value="app")
        
        # Note
        self.note_label = ttk.Label(self.login_frame, 
                                   text="Browser Login sẽ mở Chrome để đăng nhập thật, hỗ trợ 2FA tự động",
                                   font=("Arial", 8), foreground="blue")
        self.note_label.grid(row=3, column=0, columnspan=2, pady=(5, 0))
        
        # Nút đăng nhập
        self.login_button = ttk.Button(main_frame, text="🚀 Đăng nhập", 
                                      command=self.login_gmail)
        self.login_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Nút đăng xuất
        self.logout_button = ttk.Button(main_frame, text="Đăng xuất", 
                                       command=self.logout_gmail, state="disabled")
        self.logout_button.grid(row=4, column=0, columnspan=2, pady=5)
        
        # Trạng thái kết nối
        self.status_label = ttk.Label(main_frame, text="Chưa kết nối", 
                                     foreground="red")
        self.status_label.grid(row=5, column=0, columnspan=2, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.progress.grid_remove()
        
        # Separator
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=20)
        
        # Frame tài khoản đã đăng nhập (profiles)
        profiles_frame = ttk.LabelFrame(main_frame, text="Tài khoản đã đăng nhập", padding="5")
        profiles_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        profiles_frame.columnconfigure(0, weight=1)
        profiles_frame.rowconfigure(0, weight=1)
        
        # Listbox hiển thị email đã lưu
        self.profiles_list = tk.Listbox(profiles_frame, height=5)
        self.profiles_list.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        profiles_scroll = ttk.Scrollbar(profiles_frame, orient=tk.VERTICAL, command=self.profiles_list.yview)
        profiles_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.profiles_list.configure(yscrollcommand=profiles_scroll.set)
        
        # Nút thao tác profiles
        profiles_buttons = ttk.Frame(profiles_frame)
        profiles_buttons.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5,0))
        self.open_profile_btn = ttk.Button(profiles_buttons, text="Mở Browser", command=self.open_selected_profile)
        self.open_profile_btn.pack(side=tk.LEFT)
        self.delete_profile_btn = ttk.Button(profiles_buttons, text="Xóa Cache", command=self.delete_selected_profile)
        self.delete_profile_btn.pack(side=tk.LEFT, padx=10)
        
        # Frame cho danh sách email
        email_frame = ttk.LabelFrame(main_frame, text="Danh sách Email", padding="5")
        email_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        email_frame.columnconfigure(0, weight=1)
        email_frame.rowconfigure(0, weight=1)
        
        # Treeview để hiển thị email
        columns = ('From', 'Subject', 'Date')
        self.email_tree = ttk.Treeview(email_frame, columns=columns, show='headings', height=8)
        
        # Cấu hình cột
        self.email_tree.heading('From', text='Người gửi')
        self.email_tree.heading('Subject', text='Tiêu đề')
        self.email_tree.heading('Date', text='Ngày')
        
        self.email_tree.column('From', width=150)
        self.email_tree.column('Subject', width=300)
        self.email_tree.column('Date', width=120)
        
        # Scrollbar cho treeview
        scrollbar = ttk.Scrollbar(email_frame, orient=tk.VERTICAL, command=self.email_tree.yview)
        self.email_tree.configure(yscrollcommand=scrollbar.set)
        
        self.email_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Nút tải email
        self.load_button = ttk.Button(main_frame, text="📧 Tải Email", 
                                     command=self.load_emails, state="disabled")
        self.load_button.grid(row=10, column=0, columnspan=2, pady=10)
        
        # Cấu hình grid weights
        main_frame.rowconfigure(9, weight=1)
        
        # Khởi tạo UI
        self.on_method_change()
        self._refresh_profiles_list()
        
    def on_method_change(self):
        method = self.login_method.get()
        
        if method == "browser":
            # Ẩn password fields
            self.password_label.grid_remove()
            self.password_entry.grid_remove()
            self.password_type_frame.grid_remove()
            self.note_label.config(text="Browser Login sẽ mở Chrome để đăng nhập thật, hỗ trợ 2FA tự động")
        else:
            # Hiện password fields
            self.password_label.grid(row=1, column=0, sticky=tk.W, pady=5)
            self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
            self.password_type_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
            self.normal_radio.pack(side=tk.LEFT, padx=(0, 20))
            self.app_radio.pack(side=tk.LEFT)
            self.note_label.config(text="Sử dụng mật khẩu thường hoặc App Password")
    
    def login_gmail(self):
        email = self.email_entry.get().strip()
        method = self.login_method.get()
        
        if not email:
            messagebox.showerror("Lỗi", "Vui lòng nhập email!")
            return
            
        if not email.endswith('@gmail.com'):
            messagebox.showerror("Lỗi", "Vui lòng sử dụng tài khoản Gmail!")
            return
        
        # Lưu email hiện tại và gợi ý cache
        self.current_email = email

        if method == "password":
            password = self.password_entry.get().strip()
            if not password:
                messagebox.showerror("Lỗi", "Vui lòng nhập mật khẩu!")
                return
            password_type = self.password_type.get()
            threading.Thread(target=self._login_password_thread, 
                           args=(email, password, password_type), daemon=True).start()
        else:
            threading.Thread(target=self._login_browser_thread, 
                           args=(email,), daemon=True).start()
    
    def _login_browser_thread(self, email):
        try:
            # Cập nhật UI
            self.root.after(0, lambda: self.login_button.config(state="disabled"))
            self.root.after(0, lambda: self.status_label.config(text="Đang mở browser...", foreground="orange"))
            self.root.after(0, lambda: self.progress.grid())
            self.root.after(0, lambda: self.progress.start())
            
            # Khởi tạo Chrome driver với human-like behavior
            chrome_options = Options()
            
            # Persistent cache/profile per email để giống người dùng thật
            safe_email = re.sub(r'[^a-zA-Z0-9_.-]', '_', self.current_email or email) or "default"
            cache_dir = os.path.join(os.getcwd(), "chrome_cache", safe_email)
            self.current_cache_dir = cache_dir
            os.makedirs(cache_dir, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={cache_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            
            # Random user agent
            user_agent = random.choice(self.user_agents)
            self.current_user_agent = user_agent
            chrome_options.add_argument(f"--user-agent={user_agent}")
            chrome_options.add_argument("--lang=vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7")
            chrome_options.add_argument("--start-maximized")
            
            # Tối giản flags để trông như người dùng thật hơn
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-client-side-phishing-detection")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--hide-scrollbars")
            chrome_options.add_argument("--mute-audio")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-prompt-on-repost")
            chrome_options.add_argument("--disable-hang-monitor")
            chrome_options.add_argument("--disable-background-timer-throttling")
            
            # Random window size
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            chrome_options.add_argument(f"--window-size={width},{height}")
            
            # Experimental options
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("detach", True)
            
            # Prefs gần với mặc định người dùng
            prefs = {
                "intl.accept_languages": "vi-VN,vi,en-US,en",
                "credentials_enable_service": True,
                "profile.password_manager_enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Tự động tải ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Thêm human-like behavior và anti-detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']})")
            
            # Override các thuộc tính để giống browser thật
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent,
                "acceptLanguage": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "platform": "Win32"
            })
            
            # Thêm random viewport
            self.driver.set_window_size(
                random.randint(1200, 1920), 
                random.randint(800, 1080)
            )
            
            # Random mouse position
            self.driver.execute_script(f"window.moveTo({random.randint(0, 100)}, {random.randint(0, 100)});")
            
            # Human-like delay
            self._human_delay(2, 4)
            
            # Mở Gmail với random delay
            self.root.after(0, lambda: self.status_label.config(text="Đang mở Gmail...", foreground="orange"))
            self.driver.get("https://accounts.google.com/signin")
            
            # Human-like delay
            self._human_delay(3, 6)
            
            # Đợi trang load với timeout dài hơn
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.NAME, "identifier"))
            )
            
            # Human-like behavior: scroll và hover
            self._human_scroll()
            self._human_delay(1, 3)
            
            # Nhập email với human-like typing
            self.root.after(0, lambda: self.status_label.config(text="Đang nhập email...", foreground="orange"))
            email_input = self.driver.find_element(By.NAME, "identifier")
            
            # Human-like click và clear
            self._human_click(email_input)
            self._human_delay(0.5, 1)
            email_input.clear()
            self._human_delay(0.5, 1)
            
            # Human-like typing
            self._human_type(email_input, email)
            self._human_delay(1, 2)
            
            # Click Next với human behavior
            next_button = self.driver.find_element(By.ID, "identifierNext")
            self._human_click(next_button)
            
            # Human-like delay
            self._human_delay(2, 4)
            
            # Đợi trang password load với timeout dài hơn
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
            except TimeoutException:
                # Thử các selector khác
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                    )
                except TimeoutException:
                    pass
            
            # Human-like behavior
            self._human_scroll()
            self._human_delay(1, 3)
            
            # Hiển thị hướng dẫn cho user
            self.root.after(0, lambda: self._show_2fa_instructions())
            
            # Đợi user nhập password và xử lý 2FA
            self.root.after(0, lambda: self.status_label.config(text="Đang đợi bạn nhập mật khẩu và xử lý 2FA...", foreground="blue"))
            
            # Đợi đến khi đăng nhập thành công (có thể mất đến 5 phút)
            success = self._wait_for_login_success()
            
            if success:
                # Đã đăng nhập thành công qua browser. Không cố gắng đăng nhập IMAP (không dùng được session browser).
                self.root.after(0, lambda: self.status_label.config(text="Đăng nhập thành công (browser). Đang đóng trình duyệt...", foreground="green"))

                # Lưu profile thông tin
                try:
                    self._remember_profile(self.current_email or email, self.current_cache_dir, self.current_user_agent)
                except Exception:
                    pass

                # Cập nhật UI thành công
                self.root.after(0, lambda: self._login_success("browser"))

                # Đóng trình duyệt sau khi đã đăng nhập
                try:
                    if self.driver:
                        self.driver.quit()
                        self.driver = None
                except Exception:
                    pass
            else:
                self.root.after(0, lambda: self._login_error("Đăng nhập thất bại hoặc hết thời gian chờ"))
                
        except Exception as e:
            error_text = str(e)
            self.root.after(0, lambda txt=error_text: self._login_error(f"Lỗi browser login: {txt}"))
        finally:
            # Giữ browser mở để người dùng thấy rõ và tương tác
            # Không quit driver tại đây. Chỉ dừng progress UI.
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.progress.grid_remove())
    
    def _wait_for_login_success(self, timeout=300):  # 5 phút
        """Đợi đăng nhập thành công hoặc hết thời gian"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Kiểm tra avatar/account button của Google (mỗi 5 giây)
                if self._is_signed_in():
                    return True
                # Human-like behavior: random mouse movement
                if random.random() < 0.1:  # 10% chance
                    self._random_mouse_movement()
                
                # Human-like behavior: random scroll
                if random.random() < 0.05:  # 5% chance
                    self._human_scroll()
                
                # Kiểm tra xem có đang ở Gmail inbox không
                current_url = self.driver.current_url
                if "mail.google.com" in current_url or "myaccount.google.com" in current_url:
                    return True
                
                # Kiểm tra các URL khác có thể là thành công
                success_urls = [
                    "accounts.google.com/b/0/ManageAccount",
                    "myaccount.google.com",
                    "gmail.com",
                    "mail.google.com"
                ]
                
                for url in success_urls:
                    if url in current_url:
                        return True
                
                # Kiểm tra xem có thông báo lỗi không
                try:
                    error_elements = self.driver.find_elements(By.CSS_SELECTOR, "[role='alert'], .error, .warning, .error-msg")
                    if error_elements:
                        error_text = error_elements[0].text.lower()
                        if any(word in error_text for word in ["incorrect", "wrong", "invalid", "error", "failed"]):
                            return False
                except:
                    pass
                
                # Kiểm tra xem có element "Welcome" hoặc "Inbox" không
                try:
                    welcome_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Welcome') or contains(text(), 'Inbox') or contains(text(), 'Gmail')]")
                    if welcome_elements:
                        return True
                except:
                    pass
                
                # Human-like delay: kiểm tra mỗi ~5s
                self._human_delay(5, 5)
                
            except Exception:
                self._human_delay(5, 5)
        
        return False

    def _is_signed_in(self):
        """Kiểm tra đã đăng nhập bằng cách tìm nút avatar tài khoản Google và log debug."""
        self.debug_check_counter += 1
        check_id = self.debug_check_counter
        try:
            current_url = None
            try:
                current_url = self.driver.current_url
            except Exception:
                current_url = None
            print(f"[LOGIN-CHECK #{check_id}] URL: {current_url}")

            # Redirect tới trang tài khoản = đã đăng nhập
            if current_url and current_url.startswith("https://myaccount.google.com/"):
                print(f"[LOGIN-CHECK #{check_id}] => signed_in=True (myaccount)" )
                return True

            # Tìm avatar/account button theo nhiều selector
            selectors = [
                "a[aria-label^='Google Account:' i]",
                "a[aria-label^='Tài khoản Google:' i]",
                "a[aria-label*='Google Account' i]",
                "a.gb_B.gb_Za.gb_0",
                "img.gb_P.gbii",
            ]
            for sel in selectors:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, sel):
                        print(f"[LOGIN-CHECK #{check_id}] selector '{sel}' FOUND => signed_in=True")
                        return True
                except Exception as ex:
                    print(f"[LOGIN-CHECK #{check_id}] selector '{sel}' error: {ex}")

            print(f"[LOGIN-CHECK #{check_id}] => signed_in=False")
            return False
        except Exception as ex:
            print(f"[LOGIN-CHECK #{check_id}] exception: {ex}")
            return False
    
    def _show_2fa_instructions(self):
        """Hiển thị hướng dẫn 2FA"""
        instructions = """
🌐 BROWSER ĐÃ MỞ - HƯỚNG DẪN ĐĂNG NHẬP:

1. Nhập mật khẩu Gmail của bạn
2. Nếu có 2FA:
   - Nhập mã OTP từ điện thoại
   - Hoặc xác nhận qua Google Authenticator
   - Hoặc xác nhận qua SMS
3. Đợi chuyển đến Gmail inbox
4. Ứng dụng sẽ tự động kết nối

⏰ Thời gian chờ: 5 phút
        """
        messagebox.showinfo("Hướng dẫn đăng nhập", instructions)
    
    # ====== Profiles (per-email cache) ======
    def _load_profiles(self):
        try:
            os.makedirs(os.path.dirname(self.profiles_path), exist_ok=True)
            if os.path.exists(self.profiles_path):
                with open(self.profiles_path, 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
            else:
                self.profiles = {}
        except Exception:
            self.profiles = {}
    
    def _save_profiles(self):
        try:
            os.makedirs(os.path.dirname(self.profiles_path), exist_ok=True)
            with open(self.profiles_path, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def _remember_profile(self, email_addr, cache_dir, user_agent):
        if not email_addr:
            return
        self.profiles[email_addr] = {
            "cache_dir": cache_dir,
            "user_agent": user_agent,
            "last_login": int(time.time())
        }
        self._save_profiles()
        self.root.after(0, self._refresh_profiles_list)

    def _refresh_profiles_list(self):
        try:
            self.profiles_list.delete(0, tk.END)
            # Sắp xếp theo thời gian đăng nhập gần nhất
            items = sorted(self.profiles.items(), key=lambda kv: kv[1].get("last_login", 0), reverse=True)
            for email_addr, meta in items:
                ts = meta.get("last_login")
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else ""
                self.profiles_list.insert(tk.END, f"{email_addr}  |  {time_str}")
        except Exception:
            pass

    def open_selected_profile(self):
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.profiles.get(email_addr)
            if not meta:
                messagebox.showerror("Lỗi", "Không tìm thấy thông tin cache của tài khoản!")
                return

            # Mở browser với profile cache tương ứng
            threading.Thread(target=self._open_profile_browser_thread, args=(email_addr, meta), daemon=True).start()
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể mở browser: {ex}")

    def _open_profile_browser_thread(self, email_addr, meta):
        try:
            self.root.after(0, lambda: self.status_label.config(text=f"Đang mở browser cho {email_addr}...", foreground="orange"))
            chrome_options = Options()
            cache_dir = meta.get("cache_dir")
            if cache_dir and os.path.isdir(cache_dir):
                chrome_options.add_argument(f"--user-data-dir={cache_dir}")
                chrome_options.add_argument("--profile-directory=Default")
            if meta.get("user_agent"):
                chrome_options.add_argument(f"--user-agent={meta['user_agent']}")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--lang=vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7")

            service = Service(ChromeDriverManager().install())
            drv = webdriver.Chrome(service=service, options=chrome_options)
            drv.get("https://myaccount.google.com/")
            self.root.after(0, lambda: self.status_label.config(text=f"Đã mở browser cho {email_addr}", foreground="green"))
        except Exception as ex:
            self.root.after(0, lambda: self._login_error(f"Không thể mở profile browser: {ex}"))

    def delete_selected_profile(self):
        try:
            sel = self.profiles_list.curselection()
            if not sel:
                messagebox.showinfo("Thông báo", "Vui lòng chọn một tài khoản trong danh sách!")
                return
            line = self.profiles_list.get(sel[0])
            email_addr = line.split("  |  ")[0].strip()
            meta = self.profiles.get(email_addr)
            if not meta:
                return
            # Xóa thư mục cache
            cache_dir = meta.get("cache_dir")
            try:
                if cache_dir and os.path.isdir(cache_dir):
                    import shutil
                    shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception:
                pass
            # Xóa trong profiles.json
            self.profiles.pop(email_addr, None)
            self._save_profiles()
            self._refresh_profiles_list()
            self.root.after(0, lambda: self.status_label.config(text=f"Đã xóa cache của {email_addr}", foreground="green"))
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không thể xóa cache: {ex}")
    
    def _login_password_thread(self, email, password, password_type):
        try:
            # Cập nhật UI
            self.root.after(0, lambda: self.login_button.config(state="disabled"))
            self.root.after(0, lambda: self.status_label.config(text="Đang kết nối...", foreground="orange"))
            
            # Kết nối Gmail IMAP
            self.mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            self.mail.login(email, password)
            
            # Cập nhật UI thành công
            self.root.after(0, lambda: self._login_success(password_type))
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if "Invalid credentials" in error_msg:
                if password_type == "normal":
                    error_msg = "Sai email hoặc mật khẩu. Thử chuyển sang Browser Login!"
                else:
                    error_msg = "Sai email hoặc App Password. Vui lòng kiểm tra lại!"
            elif "Application-specific password required" in error_msg:
                error_msg = "Tài khoản yêu cầu App Password. Thử Browser Login để xử lý 2FA tự động!"
            else:
                error_msg = f"Lỗi đăng nhập: {error_msg}"
            
            self.root.after(0, lambda: self._login_error(error_msg))
            
        except Exception as e:
            self.root.after(0, lambda: self._login_error(f"Lỗi kết nối: {str(e)}"))
    
    def _login_success(self, method):
        self.is_connected = True
        method_text = "Browser Login" if method == "browser" else f"mật khẩu {method}"
        self.status_label.config(text="Đã kết nối thành công!", foreground="green")
        self.login_button.config(state="disabled")
        self.logout_button.config(state="normal")
        # Nếu là browser login, không bật tải email vì chưa có IMAP session
        if method == "browser":
            self.load_button.config(state="disabled")
        else:
            self.load_button.config(state="normal")
        self.email_entry.config(state="disabled")
        if self.login_method.get() == "password":
            self.password_entry.config(state="disabled")
        messagebox.showinfo("Thành công", f"Đăng nhập Gmail thành công với {method_text}!")
    
    def _login_error(self, error_msg):
        self.is_connected = False
        self.status_label.config(text="Kết nối thất bại", foreground="red")
        self.login_button.config(state="normal")
        self.logout_button.config(state="disabled")
        self.load_button.config(state="disabled")
        messagebox.showerror("Lỗi", error_msg)
    
    def logout_gmail(self):
        try:
            if self.mail:
                self.mail.logout()
                self.mail = None
        except:
            pass
        
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        self.is_connected = False
        self.status_label.config(text="Đã đăng xuất", foreground="red")
        self.login_button.config(state="normal")
        self.logout_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.email_entry.config(state="normal")
        if self.login_method.get() == "password":
            self.password_entry.config(state="normal")
            self.password_type.set("normal")
        
        # Xóa danh sách email
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)
    
    def load_emails(self):
        if not self.is_connected or not self.mail:
            messagebox.showerror("Lỗi", "Chưa kết nối Gmail!")
            return
        
        # Chạy tải email trong thread riêng
        threading.Thread(target=self._load_emails_thread, daemon=True).start()
    
    def _load_emails_thread(self):
        try:
            self.root.after(0, lambda: self.load_button.config(state="disabled"))
            self.root.after(0, lambda: self.status_label.config(text="Đang tải email...", foreground="orange"))
            
            # Chọn inbox
            self.mail.select('INBOX')
            
            # Tìm email gần đây (10 email cuối)
            status, messages = self.mail.search(None, 'ALL')
            if status != 'OK':
                raise Exception("Không thể tìm email")
            
            email_ids = messages[0].split()
            recent_emails = email_ids[-10:]  # Lấy 10 email gần nhất
            
            # Xóa danh sách cũ
            self.root.after(0, lambda: [self.email_tree.delete(item) for item in self.email_tree.get_children()])
            
            # Lấy thông tin email
            for email_id in reversed(recent_emails):  # Hiển thị email mới nhất trước
                status, msg_data = self.mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # Parse email
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Lấy thông tin
                from_addr = self._decode_header(email_message.get('From', 'Unknown'))
                subject = self._decode_header(email_message.get('Subject', 'No Subject'))
                date = email_message.get('Date', 'Unknown')
                
                # Thêm vào treeview
                self.root.after(0, lambda f=from_addr, s=subject, d=date: 
                               self.email_tree.insert('', 'end', values=(f, s, d)))
            
            self.root.after(0, lambda: self.status_label.config(text="Đã tải email thành công!", foreground="green"))
            self.root.after(0, lambda: self.load_button.config(state="normal"))
            
        except Exception as e:
            self.root.after(0, lambda: self._load_emails_error(str(e)))
    
    def _load_emails_error(self, error_msg):
        self.status_label.config(text="Lỗi tải email", foreground="red")
        self.load_button.config(state="normal")
        messagebox.showerror("Lỗi", f"Không thể tải email: {error_msg}")
    
    def _decode_header(self, header):
        """Decode email header"""
        if header is None:
            return "Unknown"
        
        decoded_parts = decode_header(header)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    try:
                        decoded_string += part.decode(encoding)
                    except:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _human_delay(self, min_seconds=1, max_seconds=3):
        """Random delay để giống human"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _human_type(self, element, text):
        """Typing giống human với random delay giữa các ký tự"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
    
    def _human_click(self, element):
        """Click giống human với hover trước"""
        actions = ActionChains(self.driver)
        actions.move_to_element(element).pause(random.uniform(0.1, 0.3)).click().perform()
    
    def _human_scroll(self):
        """Scroll giống human"""
        scroll_amount = random.randint(100, 300)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        self._human_delay(0.5, 1)
        self.driver.execute_script(f"window.scrollBy(0, -{scroll_amount//2});")
    
    def _random_mouse_movement(self):
        """Di chuyển chuột random"""
        try:
            actions = ActionChains(self.driver)
            # Random movement
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                actions.move_by_offset(x, y).perform()
                time.sleep(random.uniform(0.1, 0.3))
        except:
            pass

def main():
    root = tk.Tk()
    app = GmailBrowserLoginTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
