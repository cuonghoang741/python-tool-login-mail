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
    return bootstrap_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

