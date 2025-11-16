from __future__ import annotations

import logging
import sys

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


def bootstrap_app(args: list[str]) -> int:
    """Configure and execute the Qt application."""
    app = QApplication(args)
    app.setApplicationDisplayName("Tool Voice Cloning & Synthesis")
    app.setApplicationName("Tool Voice Cloning & Synthesis")
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

