from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
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
        advanced_params: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._synthesis_service = synthesis_service
        self._text = text
        self._voice = voice
        self._emotion = emotion
        self._intensity = intensity
        self._max_workers = max_workers
        self._advanced_params = advanced_params or {}
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
            
            output = self._synthesis_service.synthesize(
                text=self._text,
                voice_name=self._voice,
                emotion=self._emotion,
                intensity=self._intensity,
                max_workers=self._max_workers,
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
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        header = QLabel("Synthesize Speech")
        header.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(header)

        layout.addWidget(self._build_form_section())
        layout.addWidget(self._build_action_bar())
        layout.addWidget(self._build_log_section())
        layout.addWidget(self._build_outputs_list())
        layout.addStretch()

    def _build_form_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self._voice_combo = QComboBox(container)
        self._emotion_combo = QComboBox(container)

        self._intensity_slider = QSlider(Qt.Horizontal, container)
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(50)
        self._intensity_slider.setTickPosition(QSlider.TicksBelow)
        self._intensity_slider.setTickInterval(10)

        self._intensity_label = QLabel("Intensity: 0.50", container)
        intensity_info = QLabel("(Ảnh hưởng: temperature, top_p, speed range)", container)
        intensity_info.setStyleSheet("color: gray; font-size: 10px;")
        intensity_info.setToolTip(
            "Cường độ điều chỉnh độ mạnh của các thay đổi:\n"
            "- Cao (1.0): temperature thấp hơn, top_p thấp hơn, speed range lớn hơn\n"
            "- Thấp (0.0): temperature cao hơn, top_p cao hơn, speed range nhỏ hơn"
        )
        self._intensity_slider.valueChanged.connect(self._update_intensity_label)

        intensity_wrapper = QVBoxLayout()
        intensity_wrapper.setSpacing(4)
        intensity_wrapper.addWidget(self._intensity_slider)
        intensity_wrapper.addWidget(self._intensity_label)
        intensity_wrapper.addWidget(intensity_info)

        intensity_widget = QWidget(container)
        intensity_widget.setLayout(intensity_wrapper)

        self._text_input = QTextEdit(container)
        self._text_input.setPlaceholderText(
            "Nhập nội dung cần đọc. Có thể là đoạn script dài."
        )
        self._text_input.setMinimumHeight(180)

        # Parallel workers input
        self._workers_spin = QSpinBox(container)
        self._workers_spin.setRange(1, 8)
        self._workers_spin.setValue(2)
        self._workers_spin.setToolTip("Số lượng chunks xử lý đồng thời (1-8). Nhiều hơn = nhanh hơn nhưng tốn RAM hơn.")
        workers_label = QLabel("Workers (song song):", container)
        workers_layout = QHBoxLayout()
        workers_layout.addWidget(workers_label)
        workers_layout.addWidget(self._workers_spin)
        workers_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        workers_widget = QWidget(container)
        workers_widget.setLayout(workers_layout)

        form.addRow("Giọng đã clone", self._voice_combo)
        
        # Emotion selection with info
        emotion_label = QLabel("Cảm xúc:", container)
        emotion_info = QLabel("(Ảnh hưởng: tốc độ, temperature, top_p)", container)
        emotion_info.setStyleSheet("color: gray; font-size: 10px;")
        emotion_info.setToolTip(
            "Lưu ý: Emotion chính được capture từ reference audio khi clone voice.\n"
            "Lựa chọn này điều chỉnh các parameters để làm nổi bật emotion hơn:\n"
            "- Excited (angry/happy/surprised): nhanh hơn, focused hơn\n"
            "- Subdued (sad/afraid): chậm hơn, varied hơn\n"
            "- Neutral: cân bằng"
        )
        emotion_layout = QVBoxLayout()
        emotion_layout.setSpacing(2)
        emotion_layout.addWidget(self._emotion_combo)
        emotion_layout.addWidget(emotion_info)
        emotion_widget = QWidget(container)
        emotion_widget.setLayout(emotion_layout)
        form.addRow(emotion_label, emotion_widget)
        
        form.addRow("Cường độ cảm xúc", intensity_widget)
        form.addRow("Workers", workers_widget)
        form.addRow("Văn bản", self._text_input)
        
        # Advanced settings section
        advanced_group = self._build_advanced_settings(container)
        form.addRow(advanced_group)
        
        return container

    def _build_advanced_settings(self, parent: QWidget) -> QWidget:
        """Build advanced settings group with collapsible parameters in grid layout."""
        group = QGroupBox("Cài đặt nâng cao (Advanced)", parent)
        group.setCheckable(True)
        group.setChecked(False)  # Collapsed by default
        group.setToolTip("Click để mở/đóng cài đặt nâng cao")
        
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.setColumnStretch(0, 0)  # Label column
        layout.setColumnStretch(1, 1)  # Control column
        layout.setColumnStretch(2, 0)  # Label column
        layout.setColumnStretch(3, 1)  # Control column
        layout.setColumnStretch(4, 0)  # Label column
        layout.setColumnStretch(5, 1)  # Control column
        
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
        
        # Progress bar for processing state
        self._progress_bar = QProgressBar(container)
        self._progress_bar.setRange(0, 0)  # Indeterminate progress
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        return container

    def _build_log_section(self) -> QWidget:
        """Build log display section."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header with clear button
        header_layout = QHBoxLayout()
        title = QLabel("📋 Log tiến trình", container)
        title.setStyleSheet("font-size: 16px; font-weight: 500;")
        header_layout.addWidget(title)
        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self._clear_log_button = QPushButton("Xóa log", container)
        self._clear_log_button.setMaximumWidth(100)
        self._clear_log_button.clicked.connect(self._clear_log)
        header_layout.addWidget(self._clear_log_button)
        
        layout.addLayout(header_layout)

        # Log text area
        self._log_text = QTextEdit(container)
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(200)
        self._log_text.setPlaceholderText("Log tiến trình sẽ hiển thị ở đây...")
        self._log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._log_text)

        return container

    def _build_outputs_list(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Lịch sử xuất audio", container)
        title.setStyleSheet("font-size: 16px; font-weight: 500;")
        layout.addWidget(title)

        self._outputs_list = QListWidget(container)
        self._outputs_list.itemActivated.connect(self._open_output_file)
        layout.addWidget(self._outputs_list)

        return container

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

    def _handle_generate_audio(self) -> None:
        text = self._text_input.toPlainText().strip()
        if not text:
            self._status_label.setText("Vui lòng nhập văn bản cần đọc.")
            return

        voice = self._voice_combo.currentText()
        emotion_data = self._emotion_combo.currentData()
        emotion_key = emotion_data.key if emotion_data else "neutral"
        intensity = self._intensity_slider.value() / 100
        max_workers = self._workers_spin.value()
        
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
        
        # Create and start worker thread
        self._worker = SynthesisWorker(
            self._controller._synthesis_service,
            text,
            voice,
            emotion_key,
            intensity,
            max_workers,
            advanced_params,
            self,
        )
        self._worker.finished.connect(self._on_synthesis_finished)
        self._worker.error.connect(self._on_synthesis_error)
        self._worker.progress.connect(self._append_log)
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
        self._append_output_item(output)

    def _on_synthesis_error(self, error_msg: str) -> None:
        """Handle synthesis error."""
        self._set_processing_state(False)
        self._status_label.setText("✗ Tạo audio thất bại")
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
        path = item.data(Qt.UserRole)
        if isinstance(path, Path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    
    def _append_log(self, message: str) -> None:
        """Append log message to the log text area."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self._log_text.append(formatted_message)
        # Auto-scroll to bottom
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _clear_log(self) -> None:
        """Clear the log text area."""
        self._log_text.clear()

