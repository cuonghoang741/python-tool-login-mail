import sys
import os
import subprocess
import traceback
import ctypes
import json
import threading
import time

# Force UTF-8 for stdio on Windows consoles to avoid cp1252 encode errors
def _force_utf8_stdio() -> None:
    try:
        # Enable UTF-8 mode for this process
        os.environ.setdefault('PYTHONUTF8', '1')
        # Reconfigure stdio if possible (Python 3.7+)
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        if hasattr(sys.stderr, 'reconfigure'):
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
    except Exception:
        pass

# Apply UTF-8 stdio configuration as early as possible
_force_utf8_stdio()

# Try to import tkinter early; show a native dialog if it's missing
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ModuleNotFoundError:
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Không tìm thấy tkinter. Hãy cài Python đầy đủ (có Tcl/Tk) hoặc dùng bản build mới.",
            "Lỗi môi trường Python",
            0x00000010,
        )
    except Exception:
        pass
    sys.exit(1)

# HTTP client
try:
    import requests
except Exception:
    requests = None

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
    _prepare_tcl_env_for_current_process()
    import flow_browser_tool as flow
    flow.main()


def _launch_gmail():
    # Import and delegate after closing the launcher root
    _prepare_tcl_env_for_current_process()
    import gmail_browser_login as gmail
    gmail.main()


def _launch_whisk():
    # Import and delegate after closing the launcher root
    _prepare_tcl_env_for_current_process()
    import whisk_browser_tool as whisk
    whisk.main()


_selected_launcher = None
_is_authenticated = False
_auth_token = None

def _get_app_dir() -> str:
    """Return a stable directory for app runtime files.

    - In frozen/EXE: use the directory of the executable (next to .exe)
    - In dev: use the project root (directory of this source file)
    """
    try:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()

# Authentication configuration
AUTH_CONFIG_FILE = os.path.join(_get_app_dir(), "auth_config.json")
API_BASE_URL = "https://api-animo.airing.network/api"
AUTH_ME_INTERVAL_SECONDS = 300  # 5 minutes

_auth_monitor_thread = None
_auth_monitor_running = False

def load_auth_config():
    """Load authentication configuration from file"""
    try:
        if os.path.exists(AUTH_CONFIG_FILE):
            with open(AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_auth_config(config):
    """Save authentication configuration to file"""
    try:
        with open(AUTH_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _get_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def authenticate_user(username, password):
    """Authenticate user with API /login and return standardized result"""
    if requests is None:
        return {"success": False, "error": "Thiếu thư viện requests. Hãy cài đặt: pip install requests"}

    # Fallback mode for testing (remove this when API is ready)
    if username == "test" and password == "test123":
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "package": "Premium",
            "expiresAt": int(time.time()) + 30 * 24 * 3600  # 30 days from now
        }
        save_auth_config({
            "accessToken": "test_token_123",
            "user": user_data,
            "savedAt": int(time.time())
        })
        return {
            "success": True,
            "token": "test_token_123",
            "user": user_data,
            "expires": None
        }

    try:
        url = f"{API_BASE_URL}/auth/login"
        payload = {"email": username, "password": password}
        print(f"🌐 Making login request to: {url}")
        print(f"📦 Payload: {payload}")
        
        resp = requests.post(url, json=payload, headers={"Accept": "application/json"}, timeout=10)
        print(f"📡 Response status: {resp.status_code}")
        
        if resp.status_code >= 400:
            print(f"❌ Login failed with status: {resp.status_code}")
            try:
                data = resp.json()
                msg = data.get("message") or data.get("error") or resp.text
            except Exception:
                msg = resp.text
            if resp.status_code >= 500:
                msg = "Tài khoản hoặc mật khẩu không chính xác."
            print(f"❌ Error message: {msg}")
            return {"success": False, "error": msg or "Đăng nhập thất bại"}

        data = resp.json() if resp.content else {}
        print(f"📊 Login response data: {data}")
        
        # Parse nested structure: data.result.accessToken
        result_data = data.get("result", {})
        access_token = result_data.get("accessToken") or data.get("accessToken") or data.get("token")
        user = result_data.get("user") or data.get("user")
        
        print(f"🔍 Extracted token: {access_token[:20] if access_token else 'None'}...")
        print(f"🔍 Extracted user: {user}")
        
        if not access_token:
            print("❌ No access token in response")
            return {"success": False, "error": "Phản hồi đăng nhập không hợp lệ: thiếu accessToken"}

        print(f"✅ Got access token: {access_token[:20]}...")

        # Get user info from /me endpoint
        try:
            me_url = f"{API_BASE_URL}/user/me"
            print(f"🌐 Making /me request to: {me_url}")
            me_resp = requests.get(me_url, headers=_get_auth_headers(access_token), timeout=8)
            print(f"📡 /me response status: {me_resp.status_code}")
            
            if me_resp.status_code == 200:
                me_data = me_resp.json()
                print(f"📊 /me response data: {me_data}")
                user = me_data  # Use full user data from /me
            else:
                print(f"⚠️ /me failed with status: {me_resp.status_code}")
        except Exception as e:
            print(f"⚠️ /me failed: {e}")  # Debug info
            pass  # Continue with basic user data if /me fails

        # Ensure the package is still active before completing login
        is_valid_package, exp_msg = _check_package_expiration(user)
        if not is_valid_package:
            print(f"⛔ Package expired or invalid: {exp_msg}")
            return {
                "success": False,
                "error": f"Tài khoản đã hết hạn: {exp_msg or 'Vui lòng gia hạn để tiếp tục sử dụng.'}"
            }

        print(f"💾 Saving auth config for user: {user}")
        # Save immediately
        save_auth_config({
            "accessToken": access_token,
            "user": user,
            "savedAt": int(time.time())
        })

        result = {
            "success": True,
            "token": access_token,
            "user": user or username,
            "expires": None
        }
        print(f"✅ Final auth result: {result}")
        return result
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
        return {"success": False, "error": "Không thể kết nối đến server. Vui lòng kiểm tra kết nối mạng."}
    except requests.exceptions.Timeout:
        print("❌ Timeout error")
        return {"success": False, "error": "Kết nối timeout. Vui lòng thử lại."}
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"success": False, "error": f"Lỗi: {str(e)}"}

def _api_me(token: str):
    if requests is None:
        raise RuntimeError("Thiếu thư viện requests")
    url = f"{API_BASE_URL}/user/me"
    resp = requests.get(url, headers=_get_auth_headers(token), timeout=15)
    if resp.status_code >= 400:
        raise RuntimeError(f"/me lỗi: {resp.status_code}")
    return resp.json() if resp.content else {}

def _check_package_expiration(user_data):
    """Validate user package info from /me response"""
    if not user_data:
        return False, "Không có thông tin tài khoản"
    
    print(f"🔍 Checking package expiration for user data: {user_data}")
    
    exp_time = None
    package_name = "Unknown"
    package_present = False
    
    if isinstance(user_data, dict):
        actual_user_data = user_data
        if 'result' in actual_user_data and isinstance(actual_user_data['result'], dict):
            actual_user_data = actual_user_data['result']
            print(f"🔍 Found nested result structure, using: {actual_user_data}")
        if 'user' in actual_user_data and isinstance(actual_user_data['user'], dict):
            actual_user_data = actual_user_data['user']
            print(f"🔍 Found nested user structure, using: {actual_user_data}")
    else:
        actual_user_data = {}
    
    if not isinstance(actual_user_data, dict):
        return False, "Dữ liệu tài khoản không hợp lệ"
    
    # Check deleted flags
    deleted_fields = ['deletedAt', 'deleted_at']
    for field in deleted_fields:
        deleted_value = actual_user_data.get(field)
        if deleted_value:
            return False, "Tài khoản đã bị khóa hoặc xóa"
    
    # Check package info
    active_pkg = actual_user_data.get('activePackage')
    if isinstance(active_pkg, dict):
        deleted_value = active_pkg.get('deletedAt') or active_pkg.get('deleted_at')
        if deleted_value:
            return False, "Gói dịch vụ đã bị hủy"
        package_present = True
        package_obj = active_pkg.get('package')
        if isinstance(package_obj, dict):
            package_name = package_obj.get('name', package_name)
        else:
            package_name = active_pkg.get('name', package_name)
        exp_time = active_pkg.get('endDate') or active_pkg.get('expiresAt') or active_pkg.get('expires_at')
    else:
        package_candidate = actual_user_data.get('package') or actual_user_data.get('plan')
        if package_candidate:
            package_present = True
            if isinstance(package_candidate, dict):
                package_name = package_candidate.get('name', package_name)
            else:
                package_name = package_candidate
        exp_fields = ['expiresAt', 'expires_at', 'expirationDate', 'expiration_date', 'exp', 'endDate']
        for field in exp_fields:
            field_value = actual_user_data.get(field)
            if field_value:
                exp_time = field_value
                break
    
    if not package_present:
        return False, "Tài khoản chưa có gói dịch vụ hoặc đã hết hạn"
    
    if not exp_time:
        return False, "Không xác định được thời hạn sử dụng gói"
    
    print(f"📅 Expiration time: {exp_time} | Package: {package_name}")
    
    try:
        import datetime
        if isinstance(exp_time, (int, float)):
            exp_timestamp = float(exp_time)
        elif isinstance(exp_time, str):
            try:
                if exp_time.endswith('Z'):
                    exp_timestamp = datetime.datetime.fromisoformat(exp_time.replace('Z', '+00:00')).timestamp()
                else:
                    exp_timestamp = datetime.datetime.fromisoformat(exp_time).timestamp()
            except Exception:
                exp_timestamp = float(exp_time)
        else:
            return False, "Định dạng thời gian hết hạn không hợp lệ"
        
        current_time = time.time()
        if exp_timestamp <= current_time:
            return False, "Gói dịch vụ đã hết hạn"
        
        days_left = int((exp_timestamp - current_time) / (24 * 3600))
        return True, f"Còn {max(days_left, 0)} ngày"
    except Exception as e:
        print(f"❌ Error parsing expiration: {e}")
        return False, f"Lỗi kiểm tra hết hạn: {str(e)}"

def check_existing_auth(alert_on_failure: bool = False):
    """Validate stored token via /me and ensure package is active."""
    global _is_authenticated, _auth_token
    config = load_auth_config()
    token = config.get('accessToken') or config.get('token')
    if not token:
        return False
    try:
        user_data = _api_me(token)
        is_valid, exp_msg = _check_package_expiration(user_data)
        if not is_valid:
            err_msg = exp_msg or "Tài khoản không hợp lệ."
            if alert_on_failure:
                try:
                    messagebox.showerror("Không thể tiếp tục", err_msg)
                except Exception:
                    print(f"[AUTH] {err_msg}")
            else:
                print(f"[AUTH] {err_msg}")
            logout(show_message=False)
            return False
        
        save_auth_config({
            "accessToken": token,
            "user": user_data,
            "savedAt": int(time.time())
        })
        _is_authenticated = True
        _auth_token = token
        return True
    except Exception as e:
        if alert_on_failure:
            try:
                messagebox.showerror("Phiên đăng nhập không hợp lệ", f"Không thể xác thực token: {e}")
            except Exception:
                print(f"[AUTH] Không thể xác thực token: {e}")
        else:
            print(f"[AUTH] Không thể xác thực token: {e}")
        return False

def _start_auth_monitor(root):
    """Start background thread to call /me every 5 minutes. Logout on failure."""
    global _auth_monitor_thread, _auth_monitor_running
    if _auth_monitor_running:
        return
    _auth_monitor_running = True

    def monitor():
        global _auth_monitor_running
        while _auth_monitor_running:
            time.sleep(AUTH_ME_INTERVAL_SECONDS)
            cfg = load_auth_config()
            token = cfg.get('accessToken') or cfg.get('token')
            if not token:
                continue
            try:
                user_data = _api_me(token)
                # Check package expiration
                is_valid, exp_msg = _check_package_expiration(user_data)
                if not is_valid:
                    def do_logout():
                        try:
                            messagebox.showerror("Gói hết hạn", f"Gói của bạn đã hết hạn!\n{exp_msg}\nSẽ đăng xuất.")
                        except Exception:
                            pass
                        try:
                            logout(show_message=False)
                            root.quit()
                            # Restart the application
                            main()
                        except Exception:
                            pass
                    try:
                        root.after(0, do_logout)
                    except Exception:
                        pass
                    break
            except Exception as e:
                def do_logout():
                    try:
                        messagebox.showerror("Phiên đăng nhập hết hạn", "Token không còn hợp lệ. Sẽ đăng xuất.")
                    except Exception:
                        pass
                    try:
                        logout(show_message=False)
                        root.quit()
                        # Restart the application
                        main()
                    except Exception:
                        pass
                try:
                    root.after(0, do_logout)
                except Exception:
                    pass
                break

    _auth_monitor_thread = threading.Thread(target=monitor, daemon=True)
    _auth_monitor_thread.start()


def _prepare_tcl_env_for_current_process() -> None:
    """Best-effort: set TCL/TK env for this process (Windows) to avoid init.tcl errors.

    Uses paths relative to the active interpreter (venv-aware via base_prefix) and
    falls back to sys.prefix. Safe to call multiple times.
    """
    if os.name != 'nt':
        return
    try:
        base_python = getattr(sys, 'base_prefix', sys.prefix) or sys.prefix
    except Exception:
        base_python = sys.prefix
    candidates = []
    # Prefer base_prefix (real install), then prefix (venv)
    for root in {base_python, sys.prefix}:
        candidates.append((os.path.join(root, 'tcl', 'tcl8.6'), 'TCL_LIBRARY'))
        candidates.append((os.path.join(root, 'tcl', 'tk8.6'), 'TK_LIBRARY'))
    # In frozen EXE, prefer bundled lib/tcl8.6 and lib/tk8.6
    if getattr(sys, 'frozen', False):
        try:
            bundle_dir = os.path.dirname(sys.executable)
            tcl_bundle = os.path.join(bundle_dir, 'lib', 'tcl8.6')
            tk_bundle = os.path.join(bundle_dir, 'lib', 'tk8.6')
            if os.path.isdir(tcl_bundle):
                os.environ['TCL_LIBRARY'] = tcl_bundle
            if os.path.isdir(tk_bundle):
                os.environ['TK_LIBRARY'] = tk_bundle
            return
        except Exception:
            pass

    # Clear conflicting inherited values when not frozen
    os.environ.pop('TCL_LIBRARY', None)
    os.environ.pop('TK_LIBRARY', None)
    for path, var in candidates:
        if os.path.isdir(path):
            os.environ[var] = path

def _spawn_tool(entry: str) -> None:
    """Spawn a new detached process of this program with an entry selector.

    - On frozen/EXE builds: re-run `sys.executable` (the same .exe) with `--entry` arg
    - On dev mode: re-run the current script with the same interpreter
    """
    try:
        # Resolve paths and preferred interpreter
        # Determine a stable working directory for the child process
        # Use the executable directory when frozen; otherwise use project root from this file
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
            script_path = os.path.join(project_root, 'tool_launcher.py')
        else:
            script_path = os.path.abspath(__file__)
            project_root = os.path.dirname(script_path)

        # On Windows: if we're in a venv, prefer launching with that Python
        # to mirror the successful `--entry=...` CLI behavior. Otherwise,
        # prefer the packaged EXE if available.
        if os.name == 'nt':
            in_venv = False
            try:
                in_venv = hasattr(sys, 'base_prefix') and sys.prefix != sys.base_prefix
            except Exception:
                in_venv = False
            exe_path = os.path.join(project_root, 'dist', 'GoogleFlowTool', 'GoogleFlowTool.exe')
            if not getattr(sys, 'frozen', False) and in_venv:
                venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
                python_exec = venv_py_win if os.path.exists(venv_py_win) else sys.executable
                cmd = [python_exec, script_path, f"--entry={entry}"]
            elif os.path.exists(exe_path):
                cmd = [exe_path, f"--entry={entry}"]
            elif getattr(sys, 'frozen', False):
                # Current process is already the packaged EXE
                cmd = [sys.executable, f"--entry={entry}"]
            else:
                # Running as script: prefer project venv interpreter if present
                venv_py_posix = os.path.join(project_root, 'venv', 'bin', 'python')
                venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
                python_exec = sys.executable
                try:
                    if os.path.exists(venv_py_win):
                        python_exec = venv_py_win
                except Exception:
                    pass
                cmd = [python_exec, script_path, f"--entry={entry}"]
        elif getattr(sys, 'frozen', False):
            # PyInstaller executable (non-Windows)
            cmd = [sys.executable, f"--entry={entry}"]
        else:
            # Running as script: prefer project venv interpreter if present
            venv_py_posix = os.path.join(project_root, 'venv', 'bin', 'python')
            venv_py_win = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
            python_exec = sys.executable
            try:
                if os.name == 'nt' and os.path.exists(venv_py_win):
                    python_exec = venv_py_win
                elif os.name != 'nt' and os.path.exists(venv_py_posix):
                    python_exec = venv_py_posix
            except Exception:
                pass
            cmd = [python_exec, script_path, f"--entry={entry}"]

        # Detach flags
        creationflags = 0
        try:
            if os.name == 'nt':
                creationflags = (
                    getattr(subprocess, 'DETACHED_PROCESS', 0)
                    | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                )
        except Exception:
            creationflags = 0

        # On POSIX we use start_new_session, on Windows avoid close_fds=True
        start_new_session = os.name != 'nt'
        close_fds = os.name != 'nt'

        # Ensure we launch from project root so relative paths work
        env = os.environ.copy()
        env.setdefault('PYTHONUTF8', '1')
        # Help child Python find Tcl/Tk on Windows to avoid init.tcl errors.
        # IMPORTANT: Use the Tcl/Tk that matches the CHILD python executable,
        # not the launcher's interpreter, to avoid version conflicts.
        if os.name == 'nt' and not getattr(sys, 'frozen', False):
            try:
                # python_exec is defined above when not frozen
                # For venvs, python.exe lives at <venv>\Scripts\python.exe
                # For system installs, at <pyroot>\python.exe
                python_dir = os.path.dirname(python_exec)
                python_root = os.path.dirname(python_dir)
                tcl_dir = os.path.join(python_root, 'tcl', 'tcl8.6')
                tk_dir = os.path.join(python_root, 'tcl', 'tk8.6')
                # Clean any inherited conflicting values
                for var in ('TCL_LIBRARY', 'TK_LIBRARY'):
                    if var in env:
                        env.pop(var, None)
                if os.path.isdir(tcl_dir):
                    env['TCL_LIBRARY'] = tcl_dir
                if os.path.isdir(tk_dir):
                    env['TK_LIBRARY'] = tk_dir
            except Exception:
                # As a last resort, remove possibly wrong values
                env.pop('TCL_LIBRARY', None)
                env.pop('TK_LIBRARY', None)

        # Optional: write child output to a log for debugging crashes
        stdout_target = None
        stderr_target = None
        try:
            log_path = os.path.join(project_root, 'launcher_child.log')
            stdout_target = open(log_path, 'a', encoding='utf-8')
            stderr_target = stdout_target
        except Exception:
            stdout_target = None
            stderr_target = None

        subprocess.Popen(
            cmd,
            cwd=project_root,
            close_fds=close_fds,
            creationflags=creationflags,
            start_new_session=start_new_session,
            env=env,
            stdout=stdout_target,
            stderr=stderr_target,
        )
    except Exception:
        # Bubble up; caller decides whether to quit UI or show error
        raise


def _select_and_quit(root, launcher: callable) -> None:
    global _selected_launcher
    _selected_launcher = launcher
    try:
        root.after(10, root.quit)
    except Exception:
        try:
            root.quit()
        except Exception:
            pass


def _spawn_and_quit(root, entry: str) -> None:
    """Spawn selected tool in a fresh process, then quit the launcher UI.

    If spawning fails, keep the launcher open and show an error dialog.
    """
    try:
        _spawn_tool(entry)
    except Exception as e:
        try:
            messagebox.showerror("Không khởi chạy được", f"Lỗi khi mở công cụ: {e}")
        except Exception:
            pass
        return
    try:
        root.after(10, root.quit)
    except Exception:
        try:
            root.quit()
        except Exception:
            pass

def show_login_form():
    """Show login form window"""
    global _is_authenticated, _auth_token
    
    # Check if already authenticated
    if check_existing_auth(alert_on_failure=True):
        return True
    
    login_root = None
    login_success = False
    auth_result = None
    auth_error = None
    auth_processed = False
    
    def on_login():
        nonlocal login_success, auth_result, auth_error, auth_processed
        print("🔐 Login button clicked")
        username = username_entry.get().strip()
        password = password_entry.get()
        
        print(f"📝 Username: {username}")
        print(f"🔑 Password length: {len(password)}")
        
        if not username:
            print("❌ No username provided")
            messagebox.showerror("Lỗi", "Vui lòng nhập tên đăng nhập")
            return
        
        if not password:
            print("❌ No password provided")
            messagebox.showerror("Lỗi", "Vui lòng nhập mật khẩu")
            return
        
        print("✅ Input validation passed")
        
        # Reset auth state for a new attempt to avoid stale flags causing hangs
        auth_result = None
        auth_error = None
        auth_processed = False

        # Disable login button during authentication
        print("🔄 Disabling login button...")
        login_btn.config(state='disabled', text='Đang đăng nhập...')
        login_root.update()
        print("✅ Login button disabled")
        
        def auth_thread():
            nonlocal login_success, auth_result, auth_error
            print("🧵 Starting auth thread...")
            try:
                print("🌐 Calling authenticate_user...")
                result = authenticate_user(username, password)
                print(f"📊 Auth result: {result}")
                
                # Set result flag instead of calling UI directly
                auth_result = result
                print("✅ Auth result set")
                        
            except Exception as e:
                print(f"❌ Auth thread error: {e}")
                auth_error = str(e)
                print("✅ Auth error set")
        
        print("🚀 Starting auth thread...")
        threading.Thread(target=auth_thread, daemon=True).start()
        print("✅ Auth thread started")
        
        # Poll for auth result in main thread
        def check_auth_result():
            nonlocal login_success, auth_processed
            if auth_processed:
                return  # Already processed, stop polling
            
            if auth_result is not None:
                print("📨 Processing auth result in main thread")
                auth_processed = True
                handle_auth_result(auth_result)
                return
            elif auth_error is not None:
                print("❌ Processing auth error in main thread")
                auth_processed = True
                handle_auth_error(auth_error)
                return
            else:
                # Continue polling
                login_root.after(100, check_auth_result)
        
        # Start polling
        login_root.after(100, check_auth_result)
    
    def handle_auth_result(result):
        nonlocal login_success
        print("📨 handle_auth_result called")
        print(f"📊 Result: {result}")
        login_btn.config(state='normal', text='Đăng nhập')
        print("✅ Login button re-enabled")
        
        if result['success']:
            print("🎉 Login successful!")
            global _auth_token
            _auth_token = result['token']
            _is_authenticated = True
            
            # Save auth config
            save_auth_config({
                'accessToken': result['token'],
                'user': result['user'],
                'savedAt': int(time.time())
            })
            
            # Check package expiration
            user_data = result['user']
            is_valid, exp_msg = _check_package_expiration(user_data)
            
            if not is_valid:
                messagebox.showerror("Gói hết hạn", f"Gói của bạn đã hết hạn!\n{exp_msg}\nVui lòng gia hạn để tiếp tục sử dụng.")
                logout(show_message=False)
                return
            
            # Show success message with package info
            user_name = "User"
            package_name = "Unknown"
            
            if isinstance(user_data, dict):
                # Handle nested structure: user_data.result.activePackage
                actual_user_data = user_data
                if 'result' in user_data:
                    actual_user_data = user_data['result']
                
                # Handle nested structure from /me API
                if 'activePackage' in actual_user_data:
                    active_pkg = actual_user_data['activePackage']
                    if isinstance(active_pkg, dict) and 'package' in active_pkg:
                        package_name = active_pkg['package'].get('name', 'Unknown')
                        package_info = package_name
                    else:
                        package_info = package_name
                else:
                    package_name = actual_user_data.get('package', actual_user_data.get('plan', 'Standard'))
                    package_info = package_name
                
                user_name = actual_user_data.get('name', actual_user_data.get('email', 'User'))
            else:
                package_info = str(user_data)
            
            success_msg = f"Đăng nhập thành công!\n\n👤 Chào mừng: {user_name}\n📦 Gói: {package_info}\n⏰ Trạng thái: {exp_msg}"
            
            if "Còn" in exp_msg and int(exp_msg.split()[1]) <= 7:
                success_msg += "\n\n⚠️ Cảnh báo: Gói sắp hết hạn!"
            
            messagebox.showinfo("Thành công", success_msg)
            login_success = True
            login_root.destroy()
        else:
            print("❌ Login failed")
            messagebox.showerror("Lỗi đăng nhập", result.get('error', 'Đăng nhập thất bại'))
            print("✅ Error dialog shown")
    
    def handle_auth_error(error_msg):
        print(f"❌ handle_auth_error called: {error_msg}")
        login_btn.config(state='normal', text='Đăng nhập')
        print("✅ Login button re-enabled after error")
        messagebox.showerror("Lỗi", f"Lỗi kết nối: {error_msg}")
        print("✅ Error dialog shown")
    
    def on_cancel():
        login_root.destroy()
    
    def on_key_press(event):
        if event.keysym == 'Return':
            on_login()
        elif event.keysym == 'Escape':
            on_cancel()
    
    # Create login window
    login_root = tk.Toplevel()
    login_root.title("🔐 Đăng nhập")
    login_root.geometry("600x420")
    login_root.resizable(False, False)
    login_root.grab_set()  # Modal window
    
    # Center the window
    login_root.update_idletasks()
    x = (login_root.winfo_screenwidth() // 2) - (600 // 2)
    y = (login_root.winfo_screenheight() // 2) - (420 // 2)
    login_root.geometry(f"600x420+{x}+{y}")
    
    # Container
    container = ttk.Frame(login_root, padding="30")
    container.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title = ttk.Label(container, text="🔐 Đăng nhập hệ thống", font=("Segoe UI", 16, "bold"))
    title.pack(pady=(0, 12))

    # Single-device warning
    warning_text = (
        "Lưu ý: Mỗi tài khoản chỉ được đăng nhập trên 1 thiết bị tại 1 thời điểm.\n"
        "Nếu đăng nhập ở thiết bị khác, phiên hiện tại sẽ bị đăng xuất."
    )
    warning_label = ttk.Label(
        container,
        text=warning_text,
        foreground="#B91C1C",  # red-700
        font=("Segoe UI", 10, "bold"),
        justify=tk.CENTER
    )
    warning_label.pack(pady=(0, 16))
    
    # Username frame
    username_frame = ttk.Frame(container)
    username_frame.pack(fill=tk.X, pady=(0, 15))
    
    username_label = ttk.Label(username_frame, text="Tên đăng nhập:", font=("Segoe UI", 10))
    username_label.pack(anchor=tk.W)
    
    username_entry = ttk.Entry(username_frame, font=("Segoe UI", 11), width=30)
    username_entry.pack(fill=tk.X, pady=(5, 0))
    username_entry.focus()
    
    # Password frame
    password_frame = ttk.Frame(container)
    password_frame.pack(fill=tk.X, pady=(0, 20))
    
    password_label = ttk.Label(password_frame, text="Mật khẩu:", font=("Segoe UI", 10))
    password_label.pack(anchor=tk.W)
    
    password_entry = ttk.Entry(password_frame, font=("Segoe UI", 11), width=30, show="*")
    password_entry.pack(fill=tk.X, pady=(5, 0))
    
    # Buttons frame
    buttons_frame = ttk.Frame(container)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))
    
    login_btn = ttk.Button(buttons_frame, text="Đăng nhập", command=on_login, width=15)
    login_btn.pack(side=tk.LEFT, padx=(0, 10))
    
    cancel_btn = ttk.Button(buttons_frame, text="Hủy", command=on_cancel, width=15)
    cancel_btn.pack(side=tk.LEFT)
    
    # Bind keyboard events
    login_root.bind('<KeyPress>', on_key_press)
    username_entry.bind('<KeyPress>', on_key_press)
    password_entry.bind('<KeyPress>', on_key_press)
    
    # Info text
    info_text = ttk.Label(container, text="Nhấn Enter để đăng nhập, Esc để hủy", 
                         font=("Segoe UI", 9), foreground="#666666")
    info_text.pack(pady=(12, 0))

    # Brand & contact
    brand_contact = ttk.Label(container, text="ANIMTECH", 
                              font=("Segoe UI", 9, "bold"), foreground="#4B5563")
    brand_contact.pack(pady=(8, 0))
    
    # Wait for window to close
    login_root.wait_window()
    
    return login_success


def logout(show_message: bool = True):
    """Logout user and clear authentication"""
    global _is_authenticated, _auth_token
    _is_authenticated = False
    _auth_token = None
    
    # Clear saved auth config
    try:
        if os.path.exists(AUTH_CONFIG_FILE):
            os.remove(AUTH_CONFIG_FILE)
    except Exception:
        pass
    
    if show_message:
        messagebox.showinfo("Đăng xuất", "Đã đăng xuất thành công!")

def _show_about():
    try:
        messagebox.showinfo(
            "About ANIMTECH",
            (
                "ANIMTECH\n\n"
                "Công ty công nghệ đồ họa tiên phong phát triển bộ công cụ AI \n"
                "giúp tự động hóa toàn bộ quy trình làm phim: từ tiền kỳ (ý tưởng, kịch bản, \n"
                "storyboard), sản xuất (tạo hình, compositing, motion), đến hậu kỳ \n"
                "(âm thanh, grading, QC).\n\n"
                "Sứ mệnh của chúng tôi là tăng tốc 10x thời gian sản xuất, giảm mạnh chi phí, \n"
                "đồng thời duy trì chất lượng điện ảnh ở chuẩn cao nhất thông qua pipeline \n"
                "thông minh, realtime và bảo mật cấp doanh nghiệp.\n\n"
                "Năng lực cốt lõi: mô hình AI tùy biến theo dự án, tích hợp sâu với DCC \n"
                "(Blender, After Effects, v.v.), render phân tán, theo dõi chất lượng \n"
                "tự động và khả năng mở rộng linh hoạt cho studio mọi quy mô.\n\n"
                "Liên hệ: ANIMTECH"
            )
        )
    except Exception:
        pass

def main() -> None:
    # Check authentication first
    if not show_login_form():
        return  # User cancelled login
    
    # Prepare Tcl env on Windows before creating any Tk root
    _prepare_tcl_env_for_current_process()
    # Prefer ttkbootstrap if available for a nicer UI
    try:
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
    except Exception:
        # Retry once after forcing env (in case it was called before)
        _prepare_tcl_env_for_current_process()
        root = tk.Tk()
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

    root.title("🔧 Tool Launcher")
    root.geometry("500x350")
    root.resizable(False, False)

    # Container
    container = ttk.Frame(root, padding="30")
    container.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Title
    title = ttk.Label(container, text="Chọn công cụ", font=("Segoe UI", 18, "bold"))
    title.grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Buttons
    btn_flow = ttk.Button(
        container,
        text="🎬 Veo3",
        command=lambda: _spawn_and_quit(root, 'flow'),
        width=28
    )
    btn_flow.grid(row=1, column=0, padx=12, pady=12, sticky=(tk.W, tk.E))

    def _coming_soon(name: str):
        try:
            messagebox.showinfo("Coming soon", f"{name} sẽ sớm có mặt!")
        except Exception:
            pass

    btn_whisk = ttk.Button(
        container,
        text="🥣 Whisk",
        command=lambda: _spawn_and_quit(root, 'whisk'),
        width=28
    )
    btn_whisk.grid(row=1, column=1, padx=12, pady=12, sticky=(tk.W, tk.E))

    btn_pokecut = ttk.Button(
        container,
        text="✂️ Pokecut (coming soon)",
        command=lambda: _coming_soon("Pokecut"),
        width=28
    )
    btn_pokecut.grid(row=2, column=0, columnspan=2, padx=12, pady=12, sticky=(tk.W, tk.E))

    # Info
    info = ttk.Label(
        container,
        text="Veo3/Whisk đã sẵn sàng. Pokecut đang phát triển.",
        foreground="#9AA4AF",
        font=("Segoe UI", 11)
    )
    info.grid(row=3, column=0, columnspan=2, pady=(16, 0))

    # Brand & contact
    brand = ttk.Label(
        container,
        text="ANIMTECH",
        foreground="#4B5563",
        font=("Segoe UI", 10, "bold")
    )
    brand.grid(row=4, column=0, columnspan=2, pady=(8, 0))

    # About Us button
    btn_about = ttk.Button(
        container,
        text="ℹ️ About Us",
        command=_show_about,
        width=28
    )
    btn_about.grid(row=5, column=0, columnspan=2, padx=12, pady=(12, 0), sticky=(tk.W, tk.E))
    
    # Logout button
    def logout_and_restart():
        logout()
        root.quit()
        # Restart the application
        main()
    
    logout_btn = ttk.Button(
        container,
        text="🚪 Đăng xuất",
        command=logout_and_restart,
        width=28
    )
    logout_btn.grid(row=6, column=0, columnspan=2, padx=12, pady=(12, 0), sticky=(tk.W, tk.E))

    # Expand columns
    for i in range(2):
        container.columnconfigure(i, weight=1)

    # Start auth monitor
    try:
        _start_auth_monitor(root)
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    # Support CLI entry selection: --entry=flow | --entry=gmail | --entry=whisk
    entry_arg = next((a for a in sys.argv[1:] if a.startswith("--entry=")), None)
    if entry_arg:
        entry = entry_arg.split("=", 1)[1]
        try:
            # Check authentication for CLI mode too
            if not check_existing_auth():
                print("Vui lòng đăng nhập trước khi sử dụng công cụ.")
                # Try to show login form
                try:
                    _prepare_tcl_env_for_current_process()
                    if not show_login_form():
                        sys.exit(1)
                except Exception:
                    print("Không thể hiển thị form đăng nhập. Vui lòng chạy tool_launcher.py để đăng nhập.")
                    sys.exit(1)
            
            if entry == 'flow':
                _launch_flow()
            elif entry == 'gmail':
                _launch_gmail()
            elif entry == 'whisk':
                _launch_whisk()
            else:
                main()
        except ModuleNotFoundError as e:
            # Friendly guidance to install dependencies
            msg = (
                "Thiếu thư viện Python: " + str(e) + "\n\n"
                "Hướng dẫn khắc phục:\n"
                "1) Đảm bảo đã tạo venv và cài requirements:\n"
                "   - Windows: venv\\Scripts\\python -m pip install -r requirements.txt\n"
                "   - macOS/Linux: venv/bin/python -m pip install -r requirements.txt\n\n"
                "2) Sau đó chạy lại công cụ."
            )
            try:
                _tmp = tk.Tk()
                _tmp.withdraw()
                messagebox.showerror("Thiếu thư viện", msg)
                _tmp.destroy()
            except Exception:
                print(msg, file=sys.stderr)
        else:
            main()
    else:
        main()

