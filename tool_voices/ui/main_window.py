from __future__ import annotations
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QMessageBox,
    QMenu,
    QToolButton,
)

from tool_voices.core.container import ServiceContainer
from tool_voices.tabs.add_voice import AddVoiceTab
from tool_voices.tabs.execute import ExecuteTab
from tool_voices.tabs.help import HelpTab
from tool_voices.tabs.settings_tab import SettingsTab


def find_logo_path() -> Path | None:
    """Tìm đường dẫn đến file logo."""
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        possible_paths = [
            exe_dir / 'logo.ico',
            exe_dir / 'logo.png',
        ]
    else:
        script_dir = Path(__file__).parent.parent.parent
        possible_paths = [
            script_dir / 'logo.ico',
            script_dir / 'logo.png',
        ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


class VoiceMainWindow(QMainWindow):
    """Primary window hosting the Voice Cloning & Synthesis workflow."""

    def __init__(self, services: ServiceContainer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self.setWindowTitle("Tool Voice Cloning & Synthesis")
        self.resize(1024, 768)
        
        # Set icon cho window
        logo_path = find_logo_path()
        if logo_path:
            self.setWindowIcon(QIcon(str(logo_path)))

        self._tab_widget = QTabWidget(self)
        self.setCentralWidget(self._tab_widget)

        self._initialize_tabs()
        self._initialize_menu_bar()

    @property
    def services(self) -> ServiceContainer:
        return self._services

    def _initialize_tabs(self) -> None:
        add_voice_tab = AddVoiceTab(self._services.voice_clone_service, self)
        execute_tab = ExecuteTab(
            self._services.voice_clone_service,
            self._services.voice_synthesis_service,
            self,
        )
        settings_tab = SettingsTab(
            self._services.config_manager,
            self._services.xtts_gateway,
            self,
        )
        help_tab = HelpTab(self)

        add_voice_tab.voice_created.connect(lambda _: execute_tab.refresh_voices())

        self._tab_widget.addTab(add_voice_tab, "Upload & Train")
        self._tab_widget.addTab(execute_tab, "Synthesize")
        self._tab_widget.addTab(settings_tab, "⚙️ Settings")
        self._tab_widget.addTab(help_tab, "Help")

    def _initialize_menu_bar(self) -> None:
        """Tạo menu bar với nút Tài khoản nằm bên tay phải."""
        menubar = self.menuBar()

        # Tạo menu tài khoản
        account_menu = QMenu("Tài khoản", self)

        logout_action = QAction("🚪 Đăng xuất", self)
        logout_action.setStatusTip("Đăng xuất tài khoản hiện tại")
        logout_action.triggered.connect(self._handle_logout)
        account_menu.addAction(logout_action)

        # Dùng corner widget để đưa nút tài khoản sang góc phải
        account_button = QToolButton(self)
        account_button.setText("Tài khoản")
        account_button.setPopupMode(QToolButton.InstantPopup)
        account_button.setMenu(account_menu)
        account_button.setToolButtonStyle(Qt.ToolButtonTextOnly)

        menubar.setCornerWidget(account_button, Qt.TopRightCorner)

    def _handle_logout(self) -> None:
        """Gọi logout dùng chung với tool_launcher rồi đóng ứng dụng."""
        try:
            import tool_launcher  # type: ignore
        except Exception as e:
            QMessageBox.warning(
                self,
                "Không thể đăng xuất",
                f"Không tìm thấy module đăng nhập chung (tool_launcher).\n\nChi tiết: {e}",
            )
            return

        # Xác nhận trước khi đăng xuất
        reply = QMessageBox.question(
            self,
            "Xác nhận đăng xuất",
            "Bạn có chắc chắn muốn đăng xuất không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            logout_fn = getattr(tool_launcher, "logout", None)
            if callable(logout_fn):
                # Không hiện messagebox bên Tk (đã có message Qt ở đây)
                logout_fn(show_message=False)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Lỗi khi đăng xuất",
                f"Không thể đăng xuất tài khoản.\n\nChi tiết: {e}",
            )
            return

        # Đóng cửa sổ chính → thoát app
        self.close()

