from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# Supported languages with full names
SUPPORTED_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Polish", "pl"),
    ("Turkish", "tr"),
    ("Russian", "ru"),
    ("Dutch", "nl"),
    ("Czech", "cs"),
    ("Arabic", "ar"),
    ("Chinese (Simplified)", "zh-cn"),
    ("Hungarian", "hu"),
    ("Korean", "ko"),
    ("Japanese", "ja"),
    ("Hindi", "hi"),
    ("Vietnamese", "vi"),
]


class HelpTab(QWidget):
    """Help tab with user guide and supported languages information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Scroll area for content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # Title
        title = QLabel("Tool Voice Cloning & Synthesis - User Guide")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        content_layout.addWidget(title)

        # User Guide Section
        guide_section = self._create_guide_section()
        content_layout.addWidget(guide_section)

        # Supported Languages Section
        languages_section = self._create_languages_section()
        content_layout.addWidget(languages_section)

        # System Requirements Section
        requirements_section = self._create_requirements_section()
        content_layout.addWidget(requirements_section)

        # Troubleshooting Section
        troubleshooting_section = self._create_troubleshooting_section()
        content_layout.addWidget(troubleshooting_section)

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

    def _create_guide_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title = QLabel("User Guide")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        guide_text = QTextBrowser()
        guide_text.setReadOnly(True)
        guide_text.setMaximumHeight(300)
        guide_html = """
        <h3>1. Upload & Train Tab</h3>
        <p><b>Step 1:</b> Enter a name for your voice profile</p>
        <p><b>Step 2:</b> Select language preference (or use Auto-detect)</p>
        <p><b>Step 3:</b> Click "Select Audio Files" and choose 1-10 audio files</p>
        <ul>
            <li>Supported formats: WAV, MP3, FLAC</li>
            <li>Recommended: 5-10 seconds per file, clear audio quality</li>
            <li>Total duration: At least 30 seconds recommended</li>
        </ul>
        <p><b>Step 4:</b> Click "Start Training" to create the voice profile</p>
        <p><b>Note:</b> Training may take several minutes depending on your system</p>

        <h3>2. Synthesize Tab</h3>
        <p><b>Step 1:</b> Select a trained voice from the dropdown</p>
        <p><b>Step 2:</b> Enter the text you want to synthesize</p>
        <p><b>Step 3:</b> (Optional) Adjust emotion and intensity</p>
        <p><b>Step 4:</b> Click "Synthesize" to generate audio</p>
        <p><b>Step 5:</b> The output file will be saved in the outputs folder</p>
        """
        guide_text.setHtml(guide_html)
        layout.addWidget(guide_text)

        return widget

    def _create_languages_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title = QLabel("Supported Languages")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        languages_text = QTextBrowser()
        languages_text.setReadOnly(True)
        languages_text.setMaximumHeight(250)
        
        # Build HTML for languages
        languages_html = "<p>The following languages are supported by the XTTS-v2 model:</p><ul>"
        for lang_name, lang_code in SUPPORTED_LANGUAGES:
            languages_html += f"<li><b>{lang_name}</b> ({lang_code})</li>"
        languages_html += "</ul>"
        languages_html += """
        <p><b>Note:</b> You can select a language preference when training a voice, 
        or use "Auto" to let the system detect the language automatically from the text.</p>
        """
        
        languages_text.setHtml(languages_html)
        layout.addWidget(languages_text)

        return widget

    def _create_requirements_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title = QLabel("System Requirements")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        requirements_text = QTextBrowser()
        requirements_text.setReadOnly(True)
        requirements_text.setMaximumHeight(150)
        requirements_html = """
        <ul>
            <li><b>Operating System:</b> Windows 10/11</li>
            <li><b>Python:</b> Not required (included in package)</li>
            <li><b>RAM:</b> Minimum 4GB, recommended 8GB+</li>
            <li><b>Storage:</b> At least 2GB free space for models and outputs</li>
            <li><b>Internet:</b> Required for first-time model download</li>
        </ul>
        """
        requirements_text.setHtml(requirements_html)
        layout.addWidget(requirements_text)

        return widget

    def _create_troubleshooting_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title = QLabel("Troubleshooting")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        troubleshooting_text = QTextBrowser()
        troubleshooting_text.setReadOnly(True)
        troubleshooting_html = """
        <h4>Common Issues:</h4>
        <ul>
            <li><b>Training fails:</b> Ensure audio files are clear and not corrupted. 
            Try with fewer files or shorter clips.</li>
            <li><b>Synthesis is slow:</b> This is normal for the first run. 
            Subsequent runs will be faster as models are cached.</li>
            <li><b>No audio output:</b> Check the outputs folder and ensure 
            your system audio is working.</li>
            <li><b>Model download issues:</b> Ensure you have internet connection 
            and sufficient disk space.</li>
        </ul>
        <p><b>Logs:</b> Check the logs folder for detailed error messages 
        if you encounter issues.</p>
        """
        troubleshooting_text.setHtml(troubleshooting_html)
        layout.addWidget(troubleshooting_text)

        return widget

























