#!/usr/bin/env python3
"""
Build script để tạo file .exe từ Google Flow Tool
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Build Google Flow Tool thành file .exe"""
    
    print("🎬 Building Google Flow Tool executable...")
    
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
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",                    # Tạo 1 file .exe duy nhất
        "--windowed",                   # Không hiển thị console window
        "--name=GoogleFlowTool",        # Tên file output
        "--icon=logo.png",              # Icon (nếu có)
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
        main_file
    ]
    
    # Loại bỏ icon nếu không có file logo.png
    if not os.path.exists("logo.png"):
        cmd = [c for c in cmd if not c.startswith("--icon")]
        print("⚠️  Không tìm thấy logo.png, bỏ qua icon")
    
    try:
        print("🔨 Đang build...")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("✅ Build thành công!")
        print(f"📁 File .exe được tạo tại: {dist_dir / 'GoogleFlowTool.exe'}")
        
        # Kiểm tra kích thước file
        exe_path = dist_dir / "GoogleFlowTool.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📊 Kích thước file: {size_mb:.1f} MB")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi build: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        return False

def create_installer_script():
    """Tạo script để tạo installer"""
    
    installer_script = """@echo off
echo 🎬 Google Flow Tool Installer
echo.

REM Tạo thư mục cài đặt
set INSTALL_DIR=%USERPROFILE%\\GoogleFlowTool
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Copy file exe
copy "GoogleFlowTool.exe" "%INSTALL_DIR%\\"

REM Copy chrome_cache folder nếu có
if exist "chrome_cache" (
    xcopy "chrome_cache" "%INSTALL_DIR%\\chrome_cache\\" /E /I
)

REM Tạo shortcut
set DESKTOP=%USERPROFILE%\\Desktop
echo [InternetShortcut] > "%DESKTOP%\\Google Flow Tool.url"
echo URL=file:///%INSTALL_DIR%\\GoogleFlowTool.exe >> "%DESKTOP%\\Google Flow Tool.url"
echo IconFile=%INSTALL_DIR%\\GoogleFlowTool.exe >> "%DESKTOP%\\Google Flow Tool.url"
echo IconIndex=0 >> "%DESKTOP%\\Google Flow Tool.url"

echo ✅ Cài đặt hoàn tất!
echo 📁 Thư mục cài đặt: %INSTALL_DIR%
echo 🖥️  Shortcut đã tạo trên Desktop
echo.
pause
"""
    
    with open("install.bat", "w", encoding="utf-8") as f:
        f.write(installer_script)
    
    print("📝 Đã tạo install.bat")

if __name__ == "__main__":
    print("=" * 50)
    print("🎬 Google Flow Tool - Build Script")
    print("=" * 50)
    
    success = build_exe()
    
    if success:
        create_installer_script()
        print("\n🎉 Hoàn tất!")
        print("📋 Hướng dẫn:")
        print("1. File .exe: dist/GoogleFlowTool.exe")
        print("2. Installer: install.bat")
        print("3. Copy cả 2 file này đến máy Windows")
        print("4. Chạy install.bat để cài đặt")
    else:
        print("\n❌ Build thất bại!")
        sys.exit(1)
