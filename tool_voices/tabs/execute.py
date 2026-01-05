from __future__ import annotations

from pathlib import Path
import time
import re
from typing import List, Optional

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import os
import subprocess
import platform

from tool_voices.domain import default_emotions
from tool_voices.services.voice_clone import VoiceCloneService
from tool_voices.services.voice_synthesis import VoiceSynthesisService


class SynthesisWorker(QThread):
    """Worker thread for running synthesis without blocking UI."""
    finished = Signal(Path)
    error = Signal(str)
    progress = Signal(str)  # Signal for progress updates
    
    def __init__(
        self,
        synthesis_service: VoiceSynthesisService,
        text: str,
        voice: str,
        emotion: str,
        intensity: float,
        max_workers: int,
        language: Optional[str] = None,
        advanced_params: Optional[dict] = None,
        use_streaming: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._synthesis_service = synthesis_service
        self._text = text
        self._voice = voice
        self._emotion = emotion
        self._intensity = intensity
        self._max_workers = max_workers
        self._language = language
        self._advanced_params = advanced_params or {}
        self._use_streaming = use_streaming
        self._log_callback = None
    
    def set_log_callback(self, callback):
        """Set callback function to receive log messages."""
        self._log_callback = callback
    
    def _log(self, message: str):
        """Emit log message via signal and callback."""
        self.progress.emit(message)
        if self._log_callback:
            self._log_callback(message)
    
    def run(self):
        try:
            # Set up log callback in service
            self._synthesis_service.set_log_callback(self._log)
            
            self._log("🚀 Bắt đầu tạo audio...")
            self._log(f"📝 Text: {len(self._text)} ký tự")
            self._log(f"🎤 Giọng: {self._voice}")
            self._log(f"😊 Cảm xúc: {self._emotion}, Cường độ: {self._intensity:.2f}")
            self._log(f"⚙️ Workers: {self._max_workers}")
            self._log(f"🎵 Streaming: {'Bật' if self._use_streaming else 'Tắt'}")
            if self._language:
                self._log(f"🌐 Ngôn ngữ TTS: {self._language}")
            
            output = self._synthesis_service.synthesize(
                text=self._text,
                voice_name=self._voice,
                emotion=self._emotion,
                intensity=self._intensity,
                language_override=self._language,
                max_workers=self._max_workers,
                use_streaming=self._use_streaming,
            )
            
            self._log(f"✅ Hoàn tất! File: {output.name}")
            self.finished.emit(output)
        except Exception as e:
            error_msg = str(e)
            self._log(f"❌ Lỗi: {error_msg}")
            self.error.emit(error_msg)
        finally:
            # Clear log callback
            self._synthesis_service.set_log_callback(None)


class ExecuteController:
    def __init__(
        self,
        clone_service: VoiceCloneService,
        synthesis_service: VoiceSynthesisService,
    ) -> None:
        self._clone_service = clone_service
        self._synthesis_service = synthesis_service

    def available_voices(self) -> List[str]:
        voices = self._clone_service.list_available_voices()
        return voices or ["Default XTTS Voice"]


class ExecuteTab(QWidget):
    """Tab dedicated to text-to-speech synthesis with emotional control."""

    def __init__(
        self,
        clone_service: VoiceCloneService,
        synthesis_service: VoiceSynthesisService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = ExecuteController(clone_service, synthesis_service)
        self._worker: Optional[SynthesisWorker] = None
        self._synth_start_ts: Optional[float] = None
        self._build_ui()
        self.refresh_voices()
        self.refresh_emotions()
    
    def closeEvent(self, event) -> None:
        """Cleanup worker thread when closing."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QLabel("Synthesize Speech")
        header.setStyleSheet("font-size: 20px; font-weight: 600; margin-bottom: 8px;")
        layout.addWidget(header)

        layout.addWidget(self._build_form_section())
        layout.addWidget(self._build_action_bar())
        layout.addWidget(self._build_log_section())
        layout.addWidget(self._build_outputs_list())

    def _build_form_section(self) -> QWidget:
        container = QWidget(self)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # Voice and emotion group
        voice_group = QGroupBox("Voice Settings", container)
        voice_form = QFormLayout(voice_group)
        voice_form.setContentsMargins(12, 12, 12, 12)
        voice_form.setHorizontalSpacing(12)
        voice_form.setVerticalSpacing(8)

        self._voice_combo = QComboBox(voice_group)
        self._use_default_voice_checkbox = QCheckBox("Use Default Voice (Neutral)", voice_group)
        self._use_default_voice_checkbox.setToolTip(
            "Enable to use neutral/default voice for the selected language.\n"
            "Note: XTTS-v2 requires reference audio, so this uses a neutral speaker embedding.\n"
            "For better results, train a voice using the 'Upload & Train' tab."
        )
        self._default_voice_combo = QComboBox(voice_group)
        self._default_voice_combo.setEnabled(False)
        self._default_voice_combo.setVisible(False)
        
        # Populate default voices (XTTS supported languages)
        # Note: XTTS-v2 doesn't have built-in default voices - it requires reference audio
        # These are language options that will use a neutral/default speaker embedding
        default_voices = [
            ("English (en)", "en"),
            ("Spanish (es)", "es"),
            ("French (fr)", "fr"),
            ("German (de)", "de"),
            ("Italian (it)", "it"),
            ("Portuguese (pt)", "pt"),
            ("Polish (pl)", "pl"),
            ("Turkish (tr)", "tr"),
            ("Russian (ru)", "ru"),
            ("Dutch (nl)", "nl"),
            ("Czech (cs)", "cs"),
            ("Arabic (ar)", "ar"),
            ("Chinese (zh-cn)", "zh-cn"),
            ("Hungarian (hu)", "hu"),
            ("Korean (ko)", "ko"),
            ("Japanese (ja)", "ja"),
            ("Hindi (hi)", "hi"),
            ("Vietnamese (vi)", "vi"),
        ]
        for label, code in default_voices:
            self._default_voice_combo.addItem(label, code)
        
        self._use_default_voice_checkbox.toggled.connect(self._on_default_voice_toggled)
        
        # Language selection (TTS language)
        self._language_combo = QComboBox(voice_group)
        self._language_combo.setToolTip(
            "Chọn ngôn ngữ cho TTS.\n"
            "Auto: để hệ thống tự đoán dựa trên voice/text.\n"
            "Khi dùng Default Voice, lựa chọn này sẽ ưu tiên language cho model XTTS."
        )

        # Populate language options (khớp với danh sách default voices)
        self._language_combo.addItem("Auto (dựa trên voice/text)", None)
        language_options = [
            ("English (en)", "en"),
            ("Spanish (es)", "es"),
            ("French (fr)", "fr"),
            ("German (de)", "de"),
            ("Italian (it)", "it"),
            ("Portuguese (pt)", "pt"),
            ("Polish (pl)", "pl"),
            ("Turkish (tr)", "tr"),
            ("Russian (ru)", "ru"),
            ("Dutch (nl)", "nl"),
            ("Czech (cs)", "cs"),
            ("Arabic (ar)", "ar"),
            ("Chinese (zh-cn)", "zh-cn"),
            ("Hungarian (hu)", "hu"),
            ("Korean (ko)", "ko"),
            ("Japanese (ja)", "ja"),
            ("Hindi (hi)", "hi"),
            ("Vietnamese (vi)", "vi"),
        ]
        for label, code in language_options:
            self._language_combo.addItem(label, code)

        self._emotion_combo = QComboBox(voice_group)

        self._intensity_slider = QSlider(Qt.Horizontal, voice_group)
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(50)
        self._intensity_slider.setTickPosition(QSlider.TicksBelow)
        self._intensity_slider.setTickInterval(10)

        self._intensity_label = QLabel("0.50", voice_group)
        self._intensity_label.setMinimumWidth(50)
        self._intensity_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._intensity_slider.valueChanged.connect(self._update_intensity_label)
        
        # Voice selection with default voice option
        voice_layout = QVBoxLayout()
        voice_layout.setSpacing(6)
        
        # Checkbox for default voice
        voice_layout.addWidget(self._use_default_voice_checkbox)
        
        # Trained voice combo (shown when default is off)
        trained_voice_layout = QHBoxLayout()
        trained_voice_layout.addWidget(QLabel("Trained Voice:", voice_group))
        trained_voice_layout.addWidget(self._voice_combo)
        trained_voice_widget = QWidget(voice_group)
        trained_voice_widget.setLayout(trained_voice_layout)
        voice_layout.addWidget(trained_voice_widget)
        
        # Default voice combo (shown when default is on)
        default_voice_layout = QHBoxLayout()
        default_voice_layout.addWidget(QLabel("Default Voice:", voice_group))
        default_voice_layout.addWidget(self._default_voice_combo)
        default_voice_widget = QWidget(voice_group)
        default_voice_widget.setLayout(default_voice_layout)
        voice_layout.addWidget(default_voice_widget)
        
        voice_widget = QWidget(voice_group)
        voice_widget.setLayout(voice_layout)
        voice_form.addRow("Voice:", voice_widget)

        # Language + Emotion trên cùng một hàng (UI gọn hơn)
        lang_emo_layout = QHBoxLayout()
        lang_emo_layout.setSpacing(8)

        lang_label = QLabel("Language:", voice_group)
        emo_label = QLabel("Emotion:", voice_group)

        lang_emo_layout.addWidget(lang_label)
        lang_emo_layout.addWidget(self._language_combo, stretch=1)
        lang_emo_layout.addSpacing(12)
        lang_emo_layout.addWidget(emo_label)
        lang_emo_layout.addWidget(self._emotion_combo, stretch=1)

        lang_emo_widget = QWidget(voice_group)
        lang_emo_widget.setLayout(lang_emo_layout)
        voice_form.addRow(lang_emo_widget)
        
        # Intensity (một hàng riêng bên dưới)
        intensity_compact = QHBoxLayout()
        intensity_compact.addWidget(self._intensity_slider)
        intensity_compact.addWidget(self._intensity_label)
        intensity_compact_widget = QWidget(voice_group)
        intensity_compact_widget.setLayout(intensity_compact)
        voice_form.addRow("Intensity:", intensity_compact_widget)
        
        main_layout.addWidget(voice_group)
        
        # Text input group
        text_group = QGroupBox("Text Input", container)
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(12, 12, 12, 12)
        text_layout.setSpacing(8)
        
        self._text_input = QTextEdit(text_group)
        self._text_input.setPlaceholderText("Nhập nội dung cần đọc. Có thể là đoạn script dài.")
        self._text_input.setMinimumHeight(120)
        text_layout.addWidget(self._text_input)
        
        # Workers in same group
        self._workers_spin = QSpinBox(text_group)
        self._workers_spin.setRange(1, 4)
        self._workers_spin.setValue(1)
        self._workers_spin.setToolTip("Số lượng chunks xử lý đồng thời (1-4). Đề xuất: 1 để ổn định; 2 nếu chunk rất ngắn.")
        
        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel("Workers:", text_group))
        workers_layout.addWidget(self._workers_spin)
        workers_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        workers_label = QLabel("(Parallel processing)", text_group)
        workers_label.setStyleSheet("color: gray; font-size: 10px;")
        workers_layout.addWidget(workers_label)
        text_layout.addLayout(workers_layout)
        
        main_layout.addWidget(text_group)
        
        # Advanced settings section
        advanced_group = self._build_advanced_settings(container)
        main_layout.addWidget(advanced_group)
        
        return container

    def _build_advanced_settings(self, parent: QWidget) -> QWidget:
        """Build advanced settings group with collapsible parameters in grid layout."""
        group = QGroupBox("Cài đặt nâng cao (Advanced)", parent)
        group.setCheckable(True)
        group.setChecked(False)  # Collapsed by default
        group.setToolTip("Click để mở/đóng cài đặt nâng cao")
        
        # Main layout for group
        main_layout = QVBoxLayout(group)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Container for all advanced controls (hidden by default)
        self._advanced_controls_container = QWidget(group)
        layout = QGridLayout(self._advanced_controls_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setColumnStretch(0, 0)  # Label column
        layout.setColumnStretch(1, 1)  # Control column
        layout.setColumnStretch(2, 0)  # Label column
        layout.setColumnStretch(3, 1)  # Control column
        layout.setColumnStretch(4, 0)  # Label column
        layout.setColumnStretch(5, 1)  # Control column
        
        # Initially hide the container
        self._advanced_controls_container.setVisible(False)
        
        row = 0
        
        # Row 1: Temperature, Top-p, Top-k
        # Temperature: 0.1 - 2.0, default 0.75
        temp_label = QLabel("Temperature:", group)
        self._temperature_spin = QDoubleSpinBox(group)
        self._temperature_spin.setRange(0.1, 2.0)
        self._temperature_spin.setSingleStep(0.05)
        self._temperature_spin.setValue(0.75)
        self._temperature_spin.setDecimals(2)
        self._temperature_spin.setToolTip("Điều chỉnh độ ngẫu nhiên (0.1=deterministic, 2.0=very random). Default: 0.75")
        layout.addWidget(temp_label, row, 0)
        layout.addWidget(self._temperature_spin, row, 1)
        
        # Top-p: 0.1 - 1.0, default 0.85
        top_p_label = QLabel("Top-p:", group)
        self._top_p_spin = QDoubleSpinBox(group)
        self._top_p_spin.setRange(0.1, 1.0)
        self._top_p_spin.setSingleStep(0.05)
        self._top_p_spin.setValue(0.85)
        self._top_p_spin.setDecimals(2)
        self._top_p_spin.setToolTip("Nucleus sampling threshold. Default: 0.85")
        layout.addWidget(top_p_label, row, 2)
        layout.addWidget(self._top_p_spin, row, 3)
        
        # Top-k: 1 - 200, default 50
        top_k_label = QLabel("Top-k:", group)
        self._top_k_spin = QSpinBox(group)
        self._top_k_spin.setRange(1, 200)
        self._top_k_spin.setValue(50)
        self._top_k_spin.setToolTip("Top-k sampling. Default: 50")
        layout.addWidget(top_k_label, row, 4)
        layout.addWidget(self._top_k_spin, row, 5)
        
        row += 1
        
        # Row 2: Repetition Penalty, Length Penalty, Speed
        # Repetition penalty: 1.0 - 20.0, default 10.0
        rep_penalty_label = QLabel("Repetition Penalty:", group)
        self._repetition_penalty_spin = QDoubleSpinBox(group)
        self._repetition_penalty_spin.setRange(1.0, 20.0)
        self._repetition_penalty_spin.setSingleStep(0.5)
        self._repetition_penalty_spin.setValue(10.0)
        self._repetition_penalty_spin.setDecimals(1)
        self._repetition_penalty_spin.setToolTip("Penalty cho việc lặp lại tokens. Default: 10.0")
        layout.addWidget(rep_penalty_label, row, 0)
        layout.addWidget(self._repetition_penalty_spin, row, 1)
        
        # Length penalty: 0.1 - 2.0, default 1.0
        len_penalty_label = QLabel("Length Penalty:", group)
        self._length_penalty_spin = QDoubleSpinBox(group)
        self._length_penalty_spin.setRange(0.1, 2.0)
        self._length_penalty_spin.setSingleStep(0.1)
        self._length_penalty_spin.setValue(1.0)
        self._length_penalty_spin.setDecimals(1)
        self._length_penalty_spin.setToolTip("Penalty cho độ dài output. Default: 1.0")
        layout.addWidget(len_penalty_label, row, 2)
        layout.addWidget(self._length_penalty_spin, row, 3)
        
        # Speed: 0.5 - 2.0, default 1.0
        speed_label = QLabel("Speed:", group)
        self._speed_spin = QDoubleSpinBox(group)
        self._speed_spin.setRange(0.5, 2.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setDecimals(1)
        self._speed_spin.setToolTip("Tốc độ phát âm (0.5=chậm, 2.0=nhanh). Default: 1.0")
        layout.addWidget(speed_label, row, 4)
        layout.addWidget(self._speed_spin, row, 5)
        
        row += 1
        
        # Row 3: Num Beams, Do Sample, Auto-adjust
        # Num beams: 1 - 10, default 1
        num_beams_label = QLabel("Num Beams:", group)
        self._num_beams_spin = QSpinBox(group)
        self._num_beams_spin.setRange(1, 10)
        self._num_beams_spin.setValue(1)
        self._num_beams_spin.setToolTip("Số beams cho beam search (1=no beam search). Default: 1")
        layout.addWidget(num_beams_label, row, 0)
        layout.addWidget(self._num_beams_spin, row, 1)
        
        # Do sample: checkbox, default True
        do_sample_label = QLabel("Do Sample:", group)
        self._do_sample_check = QCheckBox(group)
        self._do_sample_check.setChecked(True)
        self._do_sample_check.setToolTip("Sử dụng sampling (True) hoặc greedy decoding (False). Default: True")
        layout.addWidget(do_sample_label, row, 2)
        layout.addWidget(self._do_sample_check, row, 3)
        
        # Auto-adjust checkbox: if checked, use intensity-based auto-adjustment
        auto_adjust_label = QLabel("Tự động điều chỉnh:", group)
        self._auto_adjust_check = QCheckBox(group)
        self._auto_adjust_check.setChecked(True)
        self._auto_adjust_check.setToolTip("Tự động điều chỉnh temperature/top_p/speed dựa trên intensity. Nếu bỏ chọn, dùng giá trị cố định ở trên.")
        layout.addWidget(auto_adjust_label, row, 4)
        layout.addWidget(self._auto_adjust_check, row, 5)
        
        # Add advanced controls container to main layout
        main_layout.addWidget(self._advanced_controls_container)
        
        # Connect group checkbox to show/hide advanced controls
        def on_advanced_toggled(checked: bool):
            self._advanced_controls_container.setVisible(checked)
        
        group.toggled.connect(on_advanced_toggled)
        on_advanced_toggled(False)  # Initial state (hidden)
        
        # Connect auto-adjust to enable/disable other controls
        def on_auto_adjust_changed(checked: bool):
            enabled = not checked
            self._temperature_spin.setEnabled(enabled)
            self._top_p_spin.setEnabled(enabled)
            self._speed_spin.setEnabled(enabled)
        
        self._auto_adjust_check.toggled.connect(on_auto_adjust_changed)
        on_auto_adjust_changed(True)  # Initial state
        
        return group

    def _build_action_bar(self) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._generate_button = QPushButton("Generate Audio", container)
        self._generate_button.clicked.connect(self._handle_generate_audio)

        self._refresh_button = QPushButton("Refresh Voices", container)
        self._refresh_button.clicked.connect(self.refresh_voices)

        layout.addWidget(self._generate_button)
        layout.addWidget(self._refresh_button)
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._status_label = QLabel("Chưa tạo audio", container)
        layout.addWidget(self._status_label)
        
        # Timing label to show ETA and elapsed explicitly
        self._timing_label = QLabel("ETA: -- | Elapsed: --", container)
        timing_font = self._timing_label.font()
        timing_font.setPointSize(9)
        self._timing_label.setFont(timing_font)
        layout.addWidget(self._timing_label)
        
        # Progress bar for processing state
        self._progress_bar = QProgressBar(container)
        self._progress_bar.setRange(0, 0)  # Indeterminate progress
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        return container

    def _build_log_section(self) -> QWidget:
        """Build log display section."""
        log_group = QGroupBox("Process Log", self)
        log_group.setCheckable(True)
        log_group.setChecked(False)
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.setSpacing(8)

        # Header with clear button
        header_layout = QHBoxLayout()
        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self._clear_log_button = QPushButton("Clear", log_group)
        self._clear_log_button.setMaximumWidth(80)
        self._clear_log_button.clicked.connect(self._clear_log)
        header_layout.addWidget(self._clear_log_button)
        
        log_layout.addLayout(header_layout)

        # Log text area
        self._log_text = QTextEdit(log_group)
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(150)
        self._log_text.setPlaceholderText("Process log will appear here...")
        self._log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        
        # Container to show/hide log content
        self._log_content_widget = QWidget(log_group)
        log_content_layout = QVBoxLayout(self._log_content_widget)
        log_content_layout.setContentsMargins(0, 0, 0, 0)
        log_content_layout.addWidget(self._log_text)
        self._log_content_widget.setVisible(False)
        
        log_layout.addWidget(self._log_content_widget)
        
        # Connect group checkbox to show/hide log
        def on_log_toggled(checked: bool):
            self._log_content_widget.setVisible(checked)
        
        log_group.toggled.connect(on_log_toggled)
        
        return log_group

    def _build_outputs_list(self) -> QWidget:
        outputs_group = QGroupBox("Output History", self)
        outputs_layout = QVBoxLayout(outputs_group)
        outputs_layout.setContentsMargins(12, 12, 12, 12)
        outputs_layout.setSpacing(8)

        self._outputs_list = QListWidget(outputs_group)
        self._outputs_list.setMaximumHeight(150)
        self._outputs_list.itemActivated.connect(self._open_output_file)
        self._outputs_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._outputs_list.customContextMenuRequested.connect(self._show_output_context_menu)
        outputs_layout.addWidget(self._outputs_list)

        return outputs_group

    def refresh_voices(self) -> None:
        voices = self._controller.available_voices()
        self._voice_combo.clear()
        self._voice_combo.addItems(voices)

    def refresh_emotions(self) -> None:
        emotions = default_emotions()
        self._emotion_combo.clear()
        for emotion in emotions:
            self._emotion_combo.addItem(emotion.label, emotion)

    def _update_intensity_label(self, value: int) -> None:
        self._intensity_label.setText(f"Intensity: {value / 100:.2f}")
    
    def _on_default_voice_toggled(self, checked: bool) -> None:
        """Handle toggle of default voice checkbox."""
        self._voice_combo.setEnabled(not checked)
        self._voice_combo.setVisible(not checked)
        self._default_voice_combo.setEnabled(checked)
        self._default_voice_combo.setVisible(checked)

    def _handle_generate_audio(self) -> None:
        text = self._text_input.toPlainText().strip()
        if not text:
            self._status_label.setText("Vui lòng nhập văn bản cần đọc.")
            return

        # Determine which voice to use
        use_default = self._use_default_voice_checkbox.isChecked()
        if use_default:
            default_voice_data = self._default_voice_combo.currentData()
            voice = f"default:{default_voice_data}" if default_voice_data else "default:en"
        else:
            voice = self._voice_combo.currentText()
        
        emotion_data = self._emotion_combo.currentData()
        emotion_key = emotion_data.key if emotion_data else "neutral"
        intensity = self._intensity_slider.value() / 100
        max_workers = self._workers_spin.value()

        # Language override từ dropdown (None = auto)
        language_override = self._language_combo.currentData()
        
        # Collect advanced parameters
        advanced_params = {}
        if not self._auto_adjust_check.isChecked():
            # Use manual values
            advanced_params = {
                "temperature": self._temperature_spin.value(),
                "top_p": self._top_p_spin.value(),
                "top_k": self._top_k_spin.value(),
                "repetition_penalty": self._repetition_penalty_spin.value(),
                "length_penalty": self._length_penalty_spin.value(),
                "speed": self._speed_spin.value(),
                "num_beams": self._num_beams_spin.value(),
                "do_sample": self._do_sample_check.isChecked(),
            }
        else:
            # Still pass manual values for parameters not auto-adjusted
            advanced_params = {
                "top_k": self._top_k_spin.value(),
                "repetition_penalty": self._repetition_penalty_spin.value(),
                "length_penalty": self._length_penalty_spin.value(),
                "num_beams": self._num_beams_spin.value(),
                "do_sample": self._do_sample_check.isChecked(),
            }

        # Show processing state
        self._set_processing_state(True)
        self._status_label.setText("Đang xử lý... Vui lòng đợi...")
        self._synth_start_ts = time.time()
        self._timing_label.setText("ETA: -- | Elapsed: 0.0s")
        
        # Read use_streaming from config (default True)
        try:
            from tool_voices.core.config import ConfigManager
            from pathlib import Path
            config_manager = ConfigManager(Path.cwd())
            use_streaming = config_manager.config.use_streaming
        except Exception:
            use_streaming = True  # Default if config not available
        
        # Create and start worker thread
        self._worker = SynthesisWorker(
            synthesis_service=self._controller._synthesis_service,
            text=text,
            voice=voice,
            emotion=emotion_key,
            intensity=intensity,
            max_workers=max_workers,
            language=language_override,
            advanced_params=advanced_params,
            use_streaming=use_streaming,
            parent=self,
        )
        self._worker.finished.connect(self._on_synthesis_finished)
        self._worker.error.connect(self._on_synthesis_error)
        self._worker.progress.connect(self._append_log)
        self._worker.progress.connect(self._update_status_from_progress)
        self._worker.start()

    def _set_processing_state(self, is_processing: bool) -> None:
        """Update UI to show processing state."""
        self._generate_button.setEnabled(not is_processing)
        self._progress_bar.setVisible(is_processing)
        if not is_processing:
            self._progress_bar.setRange(0, 0)  # Reset to indeterminate

    def _on_synthesis_finished(self, output: Path) -> None:
        """Handle successful synthesis completion."""
        self._set_processing_state(False)
        self._status_label.setText(f"✓ Hoàn tất: {output.name}")
        if self._synth_start_ts:
            total = time.time() - self._synth_start_ts
            self._timing_label.setText(f"ETA: 0s | Elapsed: {total:.2f}s")
            self._synth_start_ts = None
        self._append_output_item(output)

    def _on_synthesis_error(self, error_msg: str) -> None:
        """Handle synthesis error."""
        self._set_processing_state(False)
        self._status_label.setText("✗ Tạo audio thất bại")
        if self._synth_start_ts:
            total = time.time() - self._synth_start_ts
            self._timing_label.setText(f"ETA: -- | Elapsed: {total:.2f}s")
            self._synth_start_ts = None
        # Show detailed error message
        QMessageBox.critical(
            self, 
            "Lỗi tạo audio", 
            f"Không thể tạo audio:\n\n{error_msg}\n\n"
            "Vui lòng thử:\n"
            "- Giảm số workers xuống 1\n"
            "- Chia nhỏ text thành nhiều phần\n"
            "- Kiểm tra lại giọng và text input"
        )

    def _append_output_item(self, output_path: Path) -> None:
        item = QListWidgetItem(str(output_path))
        item.setData(Qt.UserRole, output_path)
        self._outputs_list.addItem(item)
        self._outputs_list.scrollToItem(item)

    def _open_output_file(self, item: QListWidgetItem) -> None:
        """Open the output file (double-click)."""
        path = item.data(Qt.UserRole)
        if isinstance(path, Path) and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    
    def _show_output_context_menu(self, position) -> None:
        """Show context menu for output file with actions."""
        item = self._outputs_list.itemAt(position)
        if not item:
            return
        
        path = item.data(Qt.UserRole)
        if not isinstance(path, Path) or not path.exists():
            return
        
        from PySide6.QtWidgets import QMenu
        
        menu = QMenu(self)
        
        # Open file action
        open_action = menu.addAction("📂 Mở file")
        open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
        
        # Open folder action
        open_folder_action = menu.addAction("📁 Mở folder")
        open_folder_action.triggered.connect(lambda: self._open_output_folder(path))
        
        # Play audio action
        play_action = menu.addAction("▶️ Phát audio")
        play_action.triggered.connect(lambda: self._play_audio(path))
        
        menu.addSeparator()
        
        # Delete action
        delete_action = menu.addAction("🗑️ Xóa file")
        delete_action.triggered.connect(lambda: self._delete_output_file(item, path))
        
        menu.exec_(self._outputs_list.mapToGlobal(position))
    
    def _open_output_folder(self, path: Path) -> None:
        """Open the folder containing the output file."""
        if path.exists():
            folder_path = path.parent
            if platform.system() == 'Windows':
                os.startfile(str(folder_path))
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', str(folder_path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(folder_path)])
    
    def _play_audio(self, path: Path) -> None:
        """Play the audio file using system default player."""
        if not path.exists():
            QMessageBox.warning(self, "Lỗi", f"File không tồn tại: {path}")
            return
        
        try:
            if platform.system() == 'Windows':
                os.startfile(str(path))
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', str(path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(path)])
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể phát audio: {str(e)}")
    
    def _delete_output_file(self, item: QListWidgetItem, path: Path) -> None:
        """Delete the output file after confirmation."""
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa file:\n{path.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if path.exists():
                    path.unlink()
                    # Remove item from list
                    row = self._outputs_list.row(item)
                    self._outputs_list.takeItem(row)
                    QMessageBox.information(self, "Thành công", "Đã xóa file thành công.")
                else:
                    QMessageBox.warning(self, "Lỗi", "File không tồn tại.")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa file: {str(e)}")
    
    def _append_log(self, message: str) -> None:
        """Append log message to the log text area."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self._log_text.append(formatted_message)
        # Auto-scroll to bottom
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _update_status_from_progress(self, message: str) -> None:
        """Mirror progress log to status label so user sees ETA without opening log."""
        # Keep it short to avoid truncation in the action bar
        self._status_label.setText(message)
    
        # Parse ETA and elapsed time from message if present
        eta_match = re.search(r"ước còn ~([0-9]+(?:\.[0-9]+)?)s", message)
        elapsed_match = re.search(r"đã chạy ([0-9]+(?:\.[0-9]+)?)s", message)
        total_match = re.search(r"Tổng thời gian.*?([0-9]+(?:\.[0-9]+)?)s", message)

        eta_text = None
        elapsed_text = None

        if eta_match:
            eta_text = f"{float(eta_match.group(1)):.2f}s"
        if total_match:
            elapsed_text = f"{float(total_match.group(1)):.2f}s"
        elif elapsed_match:
            elapsed_text = f"{float(elapsed_match.group(1)):.2f}s"
        elif self._synth_start_ts:
            # Fallback: compute elapsed so far
            elapsed = time.time() - self._synth_start_ts
            elapsed_text = f"{elapsed:.2f}s"
        
        # Update timing label if we have info
        if eta_text or elapsed_text:
            eta_display = eta_text or "--"
            elapsed_display = elapsed_text or "--"
            self._timing_label.setText(f"ETA: {eta_display} | Elapsed: {elapsed_display}")

    def _clear_log(self) -> None:
        """Clear the log text area."""
        self._log_text.clear()

