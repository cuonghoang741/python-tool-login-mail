import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import imaplib
import email
import threading
from email.header import decode_header
import ssl

class GmailLoginTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Gmail Login Tool")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Biến lưu trữ
        self.mail = None
        self.is_connected = False
        
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
        title_label = ttk.Label(main_frame, text="Gmail Login Tool", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Thông tin đăng nhập
        ttk.Label(main_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Mật khẩu:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(main_frame, width=40, show="*")
        self.password_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Loại mật khẩu
        password_frame = ttk.Frame(main_frame)
        password_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.password_type = tk.StringVar(value="normal")
        ttk.Radiobutton(password_frame, text="Mật khẩu thường", 
                       variable=self.password_type, value="normal").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(password_frame, text="App Password", 
                       variable=self.password_type, value="app").pack(side=tk.LEFT)
        
        # Note
        note_label = ttk.Label(main_frame, 
                              text="Chọn loại mật khẩu phù hợp với tài khoản của bạn",
                              font=("Arial", 8), foreground="blue")
        note_label.grid(row=4, column=0, columnspan=2, pady=(0, 10))
        
        # Nút đăng nhập
        self.login_button = ttk.Button(main_frame, text="Đăng nhập", 
                                      command=self.login_gmail)
        self.login_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Nút đăng xuất
        self.logout_button = ttk.Button(main_frame, text="Đăng xuất", 
                                       command=self.logout_gmail, state="disabled")
        self.logout_button.grid(row=6, column=0, columnspan=2, pady=5)
        
        # Trạng thái kết nối
        self.status_label = ttk.Label(main_frame, text="Chưa kết nối", 
                                     foreground="red")
        self.status_label.grid(row=7, column=0, columnspan=2, pady=5)
        
        # Separator
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=20)
        
        # Frame cho danh sách email
        email_frame = ttk.LabelFrame(main_frame, text="Danh sách Email", padding="5")
        email_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        email_frame.columnconfigure(0, weight=1)
        email_frame.rowconfigure(0, weight=1)
        
        # Treeview để hiển thị email
        columns = ('From', 'Subject', 'Date')
        self.email_tree = ttk.Treeview(email_frame, columns=columns, show='headings', height=10)
        
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
        self.load_button = ttk.Button(main_frame, text="Tải Email", 
                                     command=self.load_emails, state="disabled")
        self.load_button.grid(row=10, column=0, columnspan=2, pady=10)
        
        # Cấu hình grid weights
        main_frame.rowconfigure(9, weight=1)
        
    def login_gmail(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        password_type = self.password_type.get()
        
        if not email or not password:
            messagebox.showerror("Lỗi", "Vui lòng nhập đầy đủ email và mật khẩu!")
            return
            
        if not email.endswith('@gmail.com'):
            messagebox.showerror("Lỗi", "Vui lòng sử dụng tài khoản Gmail!")
            return
        
        # Chạy đăng nhập trong thread riêng để không block UI
        threading.Thread(target=self._login_thread, args=(email, password, password_type), daemon=True).start()
        
    def _login_thread(self, email, password, password_type):
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
                    error_msg = "Sai email hoặc mật khẩu. Thử chuyển sang App Password nếu tài khoản có bật 2FA!"
                else:
                    error_msg = "Sai email hoặc App Password. Vui lòng kiểm tra lại!"
            elif "Application-specific password required" in error_msg:
                error_msg = "Tài khoản yêu cầu App Password. Vui lòng chọn 'App Password' và tạo App Password trong Google Account!"
            else:
                error_msg = f"Lỗi đăng nhập: {error_msg}"
            
            self.root.after(0, lambda: self._login_error(error_msg))
            
        except Exception as e:
            self.root.after(0, lambda: self._login_error(f"Lỗi kết nối: {str(e)}"))
    
    def _login_success(self, password_type):
        self.is_connected = True
        password_text = "mật khẩu thường" if password_type == "normal" else "App Password"
        self.status_label.config(text="Đã kết nối thành công!", foreground="green")
        self.login_button.config(state="disabled")
        self.logout_button.config(state="normal")
        self.load_button.config(state="normal")
        self.email_entry.config(state="disabled")
        self.password_entry.config(state="disabled")
        messagebox.showinfo("Thành công", f"Đăng nhập Gmail thành công với {password_text}!")
    
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
        
        self.is_connected = False
        self.status_label.config(text="Đã đăng xuất", foreground="red")
        self.login_button.config(state="normal")
        self.logout_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.email_entry.config(state="normal")
        self.password_entry.config(state="normal")
        self.password_type.set("normal")  # Reset về mật khẩu thường
        
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

def main():
    root = tk.Tk()
    app = GmailLoginTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
