from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication) -> None:
    """Apply a modern dark theme, falling back gracefully if extras unavailable."""
    app.setStyle("Fusion")
    try:
        import qdarktheme  # type: ignore
        # Try different API methods for qdarktheme
        if hasattr(qdarktheme, "setup_theme"):
            qdarktheme.setup_theme("dark")
        elif hasattr(qdarktheme, "load_stylesheet"):
            app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
        else:
            # API not available, use fallback
            _apply_fallback_dark_palette(app)
    except (ModuleNotFoundError, AttributeError, Exception):
        # Always use our custom fallback theme which is well-designed
        _apply_fallback_dark_palette(app)


def _apply_fallback_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(24, 24, 27))
    palette.setColor(QPalette.WindowText, QColor(238, 238, 243))
    palette.setColor(QPalette.Base, QColor(18, 18, 20))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 34))
    palette.setColor(QPalette.ToolTipBase, QColor(46, 46, 50))
    palette.setColor(QPalette.ToolTipText, QColor(238, 238, 243))
    palette.setColor(QPalette.Text, QColor(238, 238, 243))
    palette.setColor(QPalette.Button, QColor(39, 39, 43))
    palette.setColor(QPalette.ButtonText, QColor(238, 238, 243))
    palette.setColor(QPalette.BrightText, QColor(255, 92, 92))
    palette.setColor(QPalette.Highlight, QColor(98, 114, 255))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.PlaceholderText, QColor(160, 160, 170))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QWidget {
            background-color: #18181c;
            color: #eeeeef;
            font-size: 14px;
        }
        QTabBar::tab {
            background-color: #26262b;
            color: #b7b7c9;
            padding: 10px 18px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            margin-right: 4px;
        }
        QTabBar::tab:selected {
            background-color: #3a3a42;
            color: #ffffff;
        }
        QLabel#h1 {
            color: #f5f5f7;
        }
        QTextBrowser {
            background-color: #1f1f24;
            border: 1px solid #2f2f36;
            border-radius: 12px;
            padding: 16px;
            color: #d7d7e2;
        }
        QPushButton {
            padding: 10px 24px;
            border-radius: 8px;
            background-color: #6366f1;
            color: #ffffff;
            font-weight: 600;
        }
        QPushButton:disabled {
            background-color: #3c3c3f;
            color: #80808c;
        }
        QListWidget, QTextEdit {
            border: 1px solid #2f2f36;
            border-radius: 10px;
            padding: 12px;
            background-color: #141418;
            selection-background-color: #44445c;
            selection-color: #f0f0f5;
        }
        QComboBox {
            border: 1px solid #2f2f36;
            border-radius: 8px;
            padding: 8px 12px;
            background-color: #141418;
            color: #f5f5f7;
        }
        QComboBox::drop-down {
            border: none;
            background: transparent;
            width: 24px;
        }
        QLineEdit {
            border: 1px solid #2f2f36;
            border-radius: 8px;
            padding: 10px 12px;
            background-color: #141418;
            color: #f5f5f7;
        }
        QProgressBar {
            border-radius: 10px;
            background-color: #202028;
            border: 1px solid #2f2f36;
            text-align: center;
            color: #f5f5f7;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(
                spread:pad,
                x1:0, y1:0,
                x2:1, y2:1,
                stop:0 #22d3ee,
                stop:1 #8b5cf6
            );
            border-radius: 10px;
        }
        QListWidget::item {
            padding: 10px 6px;
        }
        QListWidget::item:selected {
            background-color: #343447;
            border-radius: 6px;
        }
        QSlider::groove:horizontal {
            background: #2f2f36;
            height: 6px;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #6366f1;
            border: none;
            width: 18px;
            height: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }
        QSlider::handle:horizontal:hover {
            background: #818cf8;
        }
        QStatusBar, QLabel {
            color: #d7d7e2;
        }
        """
    )

