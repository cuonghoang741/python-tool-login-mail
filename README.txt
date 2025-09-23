# 🎬 Google Flow Tool - Executable

## 📋 Hướng dẫn sử dụng

### 🚀 Cài đặt
1. Copy file `GoogleFlowTool.exe` và `install.bat` vào cùng thư mục
2. Chạy `install.bat` để cài đặt tự động
3. Tool sẽ được cài đặt vào `%USERPROFILE%\GoogleFlowTool`
4. Shortcut sẽ được tạo trên Desktop và Start Menu

### 🎯 Sử dụng
1. **Đăng nhập**: Nhập email và mật khẩu Google
2. **Execute Media**: Chọn workflow và upload ảnh
3. **Headless Mode**: Mặc định bật để chạy ẩn browser

### ⚙️ Tính năng
- ✅ Đăng nhập Google Flow tự động
- ✅ Cache theo từng email
- ✅ Text to Video workflow
- ✅ Frames to Video workflow
- ✅ Upload ảnh đơn
- ✅ Headless mode
- ✅ Tự động download video

### 🔧 Yêu cầu hệ thống
- Windows 10/11
- Chrome browser (sẽ tự động download ChromeDriver)
- Kết nối internet

### 📁 Cấu trúc thư mục
```
GoogleFlowTool/
├── GoogleFlowTool.exe    # File chính
├── chrome_cache/         # Cache browser
└── downloads/            # Video đã tải
```

### 🆘 Xử lý lỗi
- **Lỗi đăng nhập**: Kiểm tra email/mật khẩu
- **Lỗi upload**: Kiểm tra file ảnh hợp lệ
- **Lỗi browser**: Tắt headless mode để debug

### 📞 Hỗ trợ
Nếu gặp vấn đề, hãy kiểm tra:
1. Chrome browser đã cài đặt
2. Kết nối internet ổn định
3. File ảnh đúng định dạng (jpg, png, webp, etc.)
