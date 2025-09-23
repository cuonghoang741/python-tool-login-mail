#!/usr/bin/env python3
"""
Build script để tạo file .exe từ Google Flow Tool cho Windows
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Build Google Flow Tool thành file .exe cho Windows"""
    
    print("🎬 Building Google Flow Tool executable for Windows...")
    
    # Kiểm tra file chính
    main_file = "flow_browser_tool.py"
    if not os.path.exists(main_file):
        print(f"❌ Không tìm thấy file {main_file}")
        return False
    
    # Tạo thư mục dist nếu chưa có
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Xóa build cũ
    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("🧹 Đã xóa build cũ")
    
    # PyInstaller command cho Windows
    cmd = [
        "pyinstaller",
        "--onedir",                      # Tạo thư mục thay vì 1 file
        "--windowed",                   # Không hiển thị console window
        "--name=GoogleFlowTool",        # Tên file output
        "--add-data=chrome_cache:chrome_cache",  # Include chrome_cache folder
        "--hidden-import=selenium",
        "--hidden-import=webdriver_manager",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.scrolledtext",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=threading",
        "--hidden-import=json",
        "--hidden-import=urllib.request",
        "--hidden-import=pathlib",
        "--hidden-import=os",
        "--hidden-import=re",
        "--hidden-import=time",
        "--hidden-import=random",
        "--collect-all=selenium",       # Collect all selenium modules
        "--collect-all=webdriver_manager",  # Collect all webdriver_manager modules
        main_file
    ]
    
    # Thêm icon nếu có
    if os.path.exists("logo.png"):
        cmd.insert(-1, "--icon=logo.png")
        print("✅ Sử dụng logo.png làm icon")
    else:
        print("⚠️  Không tìm thấy logo.png, bỏ qua icon")
    
    try:
        print("🔨 Đang build...")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("✅ Build thành công!")
        
        # Kiểm tra thư mục output
        app_dir = dist_dir / "GoogleFlowTool"
        exe_path = app_dir / "GoogleFlowTool"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📁 Thư mục app: {app_dir}")
            print(f"📁 File executable: {exe_path}")
            print(f"📊 Kích thước: {size_mb:.1f} MB")
        else:
            print("⚠️  Không tìm thấy file executable")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi build: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        return False

def create_installer_script():
    """Tạo script để tạo installer cho Windows"""
    
    installer_script = """@echo off
chcp 65001 >nul
echo 🎬 Google Flow Tool Installer
echo.

REM Tạo thư mục cài đặt
set INSTALL_DIR=%USERPROFILE%\\GoogleFlowTool
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo 📁 Đang cài đặt vào: %INSTALL_DIR%

REM Copy file exe
if exist "GoogleFlowTool.exe" (
    copy "GoogleFlowTool.exe" "%INSTALL_DIR%\\" >nul
    echo ✅ Đã copy GoogleFlowTool.exe
) else (
    echo ❌ Không tìm thấy GoogleFlowTool.exe
    pause
    exit /b 1
)

REM Copy chrome_cache folder nếu có
if exist "chrome_cache" (
    xcopy "chrome_cache" "%INSTALL_DIR%\\chrome_cache\\" /E /I /Q >nul
    echo ✅ Đã copy chrome_cache
)

REM Tạo shortcut trên Desktop
set DESKTOP=%USERPROFILE%\\Desktop
echo [InternetShortcut] > "%DESKTOP%\\Google Flow Tool.url"
echo URL=file:///%INSTALL_DIR%\\GoogleFlowTool.exe >> "%DESKTOP%\\Google Flow Tool.url"
echo IconFile=%INSTALL_DIR%\\GoogleFlowTool.exe >> "%DESKTOP%\\Google Flow Tool.url"
echo IconIndex=0 >> "%DESKTOP%\\Google Flow Tool.url"

REM Tạo shortcut trong Start Menu
set START_MENU=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs
if not exist "%START_MENU%" mkdir "%START_MENU%"
echo [InternetShortcut] > "%START_MENU%\\Google Flow Tool.url"
echo URL=file:///%INSTALL_DIR%\\GoogleFlowTool.exe >> "%START_MENU%\\Google Flow Tool.url"
echo IconFile=%INSTALL_DIR%\\GoogleFlowTool.exe >> "%START_MENU%\\Google Flow Tool.url"
echo IconIndex=0 >> "%START_MENU%\\Google Flow Tool.url"

echo.
echo ✅ Cài đặt hoàn tất!
echo 📁 Thư mục cài đặt: %INSTALL_DIR%
echo 🖥️  Shortcut đã tạo trên Desktop và Start Menu
echo.
echo 🚀 Bạn có thể chạy tool bằng cách:
echo   1. Double-click shortcut trên Desktop
echo   2. Hoặc chạy trực tiếp: %INSTALL_DIR%\\GoogleFlowTool.exe
echo.
pause
"""
    
    with open("install.bat", "w", encoding="utf-8") as f:
        f.write(installer_script)
    
    print("📝 Đã tạo install.bat")

def create_readme():
    """Tạo file README hướng dẫn"""
    
    readme_content = """# 🎬 Google Flow Tool - Executable

## 📋 Hướng dẫn sử dụng

### 🚀 Cài đặt
1. Copy file `GoogleFlowTool.exe` và `install.bat` vào cùng thư mục
2. Chạy `install.bat` để cài đặt tự động
3. Tool sẽ được cài đặt vào `%USERPROFILE%\\GoogleFlowTool`
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
"""
    
    with open("README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("📝 Đã tạo README.txt")

if __name__ == "__main__":
    print("=" * 60)
    print("🎬 Google Flow Tool - Windows Build Script")
    print("=" * 60)
    
    success = build_exe()
    
    if success:
        create_installer_script()
        create_readme()
        print("\n🎉 Hoàn tất!")
        print("📋 Files được tạo:")
        print("1. 📁 dist/GoogleFlowTool.exe - File executable")
        print("2. 📝 install.bat - Script cài đặt")
        print("3. 📝 README.txt - Hướng dẫn sử dụng")
        print("\n🚀 Hướng dẫn deploy:")
        print("1. Copy 3 files trên đến máy Windows")
        print("2. Chạy install.bat để cài đặt")
        print("3. Tool sẽ tự động chạy hoàn toàn!")
    else:
        print("\n❌ Build thất bại!")
        sys.exit(1)
