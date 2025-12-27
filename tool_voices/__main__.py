from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from tool_voices.core.container import ServiceContainer
from tool_voices.core.logging_config import configure_logging
from tool_voices.ui import VoiceMainWindow
from tool_voices.ui.styles import apply_theme


def create_service_container() -> ServiceContainer:
    """Instantiate the service container. Separated for testability."""
    container = ServiceContainer()
    configure_logging(container.config_manager.logs_dir)
    logging.getLogger(__name__).info("Service container initialized.")
    return container


def find_logo_path() -> Path | None:
    """Tìm đường dẫn đến file logo."""
    # Khi chạy từ exe, tìm logo trong cùng thư mục với exe
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        possible_paths = [
            exe_dir / 'logo.ico',
            exe_dir / 'logo.png',
            exe_dir.parent / 'logo.ico',
            exe_dir.parent / 'logo.png',
        ]
    else:
        # Khi chạy từ script, tìm logo ở thư mục gốc
        script_dir = Path(__file__).parent.parent
        possible_paths = [
            script_dir / 'logo.ico',
            script_dir / 'logo.png',
        ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def ensure_authenticated() -> bool:
    """
    Đảm bảo người dùng đã đăng nhập, dùng chung luồng login với tool_launcher.py.

    - Ưu tiên re-use: tool_launcher.check_existing_auth() và tool_launcher.show_login_form()
    - Trả về True nếu đã đăng nhập / xác thực thành công, False nếu người dùng hủy.
    """
    logger = logging.getLogger(__name__)

    try:
        # tool_launcher.py nằm ở thư mục gốc project, đã được thêm vào PYTHONPATH
        import tool_launcher  # type: ignore
    except Exception as e:  # pragma: no cover - fallback trong môi trường thiếu file
        # Nếu vì lý do nào đó không import được, cho phép vào app để tránh chặn cứng
        logger.error("Không thể import module đăng nhập chung (tool_launcher): %s", e)
        return True

    try:
        # Giữ đúng luồng với main() trong tool_launcher.py:
        # 1) Thử xác thực token hiện có
        check_auth = getattr(tool_launcher, "check_existing_auth", None)
        if callable(check_auth):
            if check_auth(alert_on_failure=True):
                return True

        # 2) Nếu chưa có / token không hợp lệ, hiển thị form đăng nhập Tk
        show_login_form = getattr(tool_launcher, "show_login_form", None)
        if callable(show_login_form):
            return bool(show_login_form())

        # Nếu không có hàm login, cho phép vào app để tránh treo
        logger.warning(
            "tool_launcher không cung cấp đủ hàm đăng nhập (check_existing_auth / show_login_form)."
        )
        return True
    except Exception as e:  # pragma: no cover - bảo vệ an toàn quanh Tk
        logger.error("Lỗi trong luồng đăng nhập dùng chung: %s", e)
        # Nếu luồng login gặp lỗi bất ngờ, cho phép vào app thay vì chặn cứng
        return True


def bootstrap_app(args: list[str]) -> int:
    """Configure and execute the Qt application."""
    app = QApplication(args)
    app.setApplicationDisplayName("Tool Voice Cloning & Synthesis")
    app.setApplicationName("Tool Voice Cloning & Synthesis")
    
    # Set icon cho ứng dụng
    logo_path = find_logo_path()
    if logo_path:
        app.setWindowIcon(QIcon(str(logo_path)))
    
    apply_theme(app)

    services = create_service_container()
    window = VoiceMainWindow(services)
    window.show()
    logging.getLogger(__name__).info("Application UI launched.")

    return app.exec()


def main() -> int:
    # Đảm bảo đăng nhập trước khi khởi chạy UI chính
    if not ensure_authenticated():
        # Người dùng hủy form đăng nhập -> thoát nhẹ nhàng
        return 0

    return bootstrap_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

