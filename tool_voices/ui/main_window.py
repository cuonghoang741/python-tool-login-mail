from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from tool_voices.core.container import ServiceContainer
from tool_voices.tabs.add_voice import AddVoiceTab
from tool_voices.tabs.execute import ExecuteTab


class VoiceMainWindow(QMainWindow):
    """Primary window hosting the Voice Cloning & Synthesis workflow."""

    def __init__(self, services: ServiceContainer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self.setWindowTitle("Tool Voice Cloning & Synthesis")
        self.resize(1024, 768)

        self._tab_widget = QTabWidget(self)
        self.setCentralWidget(self._tab_widget)

        self._initialize_tabs()

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

        add_voice_tab.voice_created.connect(lambda _: execute_tab.refresh_voices())

        self._tab_widget.addTab(add_voice_tab, "Upload & Train")
        self._tab_widget.addTab(execute_tab, "Synthesize")

