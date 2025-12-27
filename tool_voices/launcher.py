"""
Simple launcher that activates venv_voice and runs the main application.
This launcher will be packaged as a small exe that doesn't need TTS bundled.
"""
import os
import sys
import subprocess
from pathlib import Path

def find_system_python():
    """Find Python 3.11 from system PATH."""
    # Try py launcher first (Windows)
    try:
        result = subprocess.run(
            ['py', '-3.11', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # py launcher found, use it
            return ['py', '-3.11']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try python3.11
    try:
        result = subprocess.run(
            ['python3.11', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return ['python3.11']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try python with version check
    try:
        result = subprocess.run(
            ['python', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_output = result.stdout.strip() or result.stderr.strip()
            # Check if it's Python 3.11
            if '3.11' in version_output:
                return ['python']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    return None

def find_venv_voice():
    """Find venv_voice directory relative to the exe location."""
    # When running as exe, sys.executable points to the exe file
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        exe_dir = Path(sys.executable).parent
        # venv_voice should be in the same directory as exe
        possible_paths = [
            exe_dir / 'venv_voice',
            exe_dir.parent / 'venv_voice',
        ]
    else:
        # Running as script
        script_dir = Path(__file__).parent.parent
        possible_paths = [
            script_dir / 'venv_voice',
        ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def main():
    # Get exe directory first
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent.parent
    
    # Find Python from system (not from venv)
    python_cmd = find_system_python()
    
    if not python_cmd:
        import tkinter.messagebox as msgbox
        error_msg = (
            "Không tìm thấy Python 3.11 trên hệ thống!\n\n"
            "Vui lòng:\n"
            "1. Chạy install_python.bat để cài đặt Python 3.11\n"
            "2. Hoặc cài đặt Python 3.11 từ https://www.python.org/downloads/\n"
            "3. Đảm bảo chọn 'Add Python to PATH' khi cài đặt\n"
            "4. Sau đó chạy lại ứng dụng"
        )
        msgbox.showerror("Lỗi - Python không khả dụng", error_msg)
        return 1
    
    # Verify Python is working
    try:
        result = subprocess.run(
            python_cmd + ['--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            raise RuntimeError(f"Python version check failed: {result.stderr}")
    except Exception as e:
        import tkinter.messagebox as msgbox
        error_msg = (
            f"Không thể chạy Python!\n\n"
            f"Lỗi: {str(e)}\n\n"
            f"Vui lòng chạy install_python.bat để cài đặt Python 3.11."
        )
        msgbox.showerror("Lỗi - Python không khả dụng", error_msg)
        return 1
    
    # Find venv_voice directory (contains packages, not Python executable)
    venv_path = find_venv_voice()
    
    if not venv_path:
        import tkinter.messagebox as msgbox
        error_msg = (
            "Không tìm thấy venv_voice!\n\n"
            f"Đã tìm tại:\n"
            f"- {exe_dir / 'venv_voice'}\n"
            f"- {exe_dir.parent / 'venv_voice'}\n\n"
            "Vui lòng đảm bảo thư mục venv_voice nằm cùng với file exe."
        )
        msgbox.showerror("Lỗi", error_msg)
        return 1
    
    # Get the main module path and working directory
    if getattr(sys, 'frozen', False):
        # When running as exe, find tool_voices relative to exe
        exe_dir = Path(sys.executable).parent
        # tool_voices should be in the same directory as exe
        tool_voices_path = exe_dir / 'tool_voices'
        if not tool_voices_path.exists():
            # Try parent directory
            tool_voices_path = exe_dir.parent / 'tool_voices'
        work_dir = exe_dir
    else:
        # Running as script
        tool_voices_path = Path(__file__).parent.parent / 'tool_voices'
        work_dir = tool_voices_path.parent
    
    if not tool_voices_path.exists():
        import tkinter.messagebox as msgbox
        msgbox.showerror(
            "Lỗi",
            f"Không tìm thấy thư mục tool_voices!\n\n"
            f"Đã tìm tại: {tool_voices_path}"
        )
        return 1
    
    # Run the application using system Python with venv packages
    try:
        # Clean environment to avoid conflicts
        env = os.environ.copy()
        
        # Remove any Python-related paths that might interfere
        env.pop('PYTHONHOME', None)
        
        # Set VIRTUAL_ENV to point to venv_voice so Python finds packages
        env['VIRTUAL_ENV'] = str(venv_path)
        
        # Add venv site-packages to PYTHONPATH
        if sys.platform == 'win32':
            site_packages = venv_path / 'Lib' / 'site-packages'
        else:
            site_packages = venv_path / 'lib' / 'python3.11' / 'site-packages'
        
        pythonpath_parts = [str(work_dir)]
        if site_packages.exists():
            pythonpath_parts.insert(0, str(site_packages))
        
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = os.pathsep.join(pythonpath_parts) + os.pathsep + env['PYTHONPATH']
        else:
            env['PYTHONPATH'] = os.pathsep.join(pythonpath_parts)
        
        # Build command using system Python
        cmd = python_cmd + ['-m', 'tool_voices']
        
        # Run with the same environment, but use venv Python
        # Hide console output when running as exe
        if getattr(sys, 'frozen', False):
            # When running as exe, hide all output and console window
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
        else:
            # When running as script, show output for debugging
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                env=env
            )
            return result.returncode
    except Exception as e:
        import tkinter.messagebox as msgbox
        import traceback
        error_msg = (
            f"Không thể khởi động ứng dụng!\n\n"
            f"Lỗi: {str(e)}\n\n"
            f"Python exe: {python_exe}\n"
            f"Work dir: {work_dir}\n"
            f"Tool voices path: {tool_voices_path}"
        )
        msgbox.showerror("Lỗi khi chạy ứng dụng", error_msg)
        return 1

if __name__ == '__main__':
    sys.exit(main())

