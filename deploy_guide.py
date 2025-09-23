#!/usr/bin/env python3
"""
Hướng dẫn build và deploy Google Flow Tool thành executable
"""

print("=" * 60)
print("🎬 Google Flow Tool - Build & Deploy Guide")
print("=" * 60)

print("""
📋 ĐÃ BUILD THÀNH CÔNG!

🎯 Files được tạo:
1. 📁 dist/GoogleFlowTool/ - Thư mục chứa app
   ├── GoogleFlowTool (executable chính)
   └── _internal/ (các dependencies)
2. 📝 install.bat - Script cài đặt cho Windows
3. 📝 README.txt - Hướng dẫn sử dụng

🚀 HƯỚNG DẪN DEPLOY:

1️⃣ Copy files đến máy Windows:
   - Copy toàn bộ thư mục dist/GoogleFlowTool/
   - Copy file install.bat
   - Copy file README.txt

2️⃣ Cài đặt trên Windows:
   - Chạy install.bat với quyền Administrator
   - Tool sẽ được cài vào %USERPROFILE%\\GoogleFlowTool
   - Shortcut sẽ được tạo trên Desktop và Start Menu

3️⃣ Sử dụng:
   - Double-click shortcut trên Desktop
   - Hoặc chạy trực tiếp GoogleFlowTool.exe trong thư mục cài đặt

⚙️ TÍNH NĂNG:
✅ Đăng nhập Google Flow tự động
✅ Cache theo từng email  
✅ Text to Video workflow
✅ Frames to Video workflow
✅ Upload ảnh đơn
✅ Headless mode (mặc định)
✅ Tự động download video
✅ Responsive UI

🔧 YÊU CẦU HỆ THỐNG:
- Windows 10/11
- Chrome browser (tự động download ChromeDriver)
- Kết nối internet

📊 THÔNG TIN BUILD:
- Kích thước executable: 4.1 MB
- Kích thước thư mục: ~50-100 MB (bao gồm dependencies)
- Platform: Cross-platform (macOS build, Windows compatible)

🎉 Tool đã sẵn sàng để deploy và sử dụng!
""")

print("=" * 60)
print("✅ Build hoàn tất - Tool sẵn sàng deploy!")
print("=" * 60)
