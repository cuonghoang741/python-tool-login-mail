from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, List, Optional

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from tool_voices.domain import VoiceProfile
from tool_voices.services.voice_clone import VoiceCloneService


class AddVoiceController(QObject):
    training_started = Signal()
    training_finished = Signal(object)
    training_failed = Signal(str)

    def __init__(self, service: VoiceCloneService) -> None:
        super().__init__()
        self._service = service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-clone")
        self._current_job: Optional[Future[VoiceProfile]] = None

    def select_samples(self, parent: QWidget) -> List[Path]:
        dialog = QFileDialog(parent)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.setNameFilters(
            [
                "Audio Files (*.wav *.mp3 *.flac)",
                "All Files (*)",
            ]
        )
        if dialog.exec() == QFileDialog.Accepted:
            return [Path(p) for p in dialog.selectedFiles()]
        return []

    def start_training(
        self,
        voice_name: str,
        sample_paths: Iterable[Path],
        language: str,
    ) -> None:
        if self._current_job and not self._current_job.done():
            self.training_failed.emit("Một tiến trình huấn luyện khác đang chạy.")
            return

        samples_list = [Path(path) for path in sample_paths]
        self.training_started.emit()
        future = self._executor.submit(
            self._service.create_voice_profile,
            voice_name,
            samples_list,
            language,
        )
        self._current_job = future
        future.add_done_callback(self._handle_future_completed)

    def _handle_future_completed(self, future: Future[VoiceProfile]) -> None:
        self._current_job = None
        try:
            profile = future.result()
        except Exception as exc:  # noqa: BLE001
            self.training_failed.emit(str(exc))
        else:
            self.training_finished.emit(profile)


class AddVoiceTab(QWidget):
    """Tab enabling users to upload voice samples and trigger cloning."""

    voice_created = Signal(str)

    def __init__(self, service: VoiceCloneService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = AddVoiceController(service)
        self._selected_samples: List[Path] = []

        self._controller.training_started.connect(self._on_training_started)
        self._controller.training_finished.connect(self._on_training_finished)
        self._controller.training_failed.connect(self._on_training_failed)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        header = QLabel("Thêm Giọng Nói")
        header.setObjectName("h1")
        header.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(header)

        description = QTextBrowser(self)
        description.setOpenExternalLinks(True)
        description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        description.setMaximumHeight(80)
        description.setHtml(
            (
                "<p>Tải lên file âm thanh giọng nói (wav, mp3, flac). "
                "Giọng sẽ được lưu ngay và sẵn sàng sử dụng - không cần huấn luyện.</p>"
            )
        )
        layout.addWidget(description)

        layout.addWidget(self._build_voice_form())
        layout.addLayout(self._build_selection_row())
        layout.addWidget(self._build_samples_list())
        layout.addWidget(self._build_training_controls())
        layout.addWidget(self._build_voices_list())
        layout.addStretch()
        self._update_train_enabled()
        self._refresh_voices_list()

    def _build_voice_form(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self._voice_name_input = QLineEdit(container)
        self._voice_name_input.setPlaceholderText("Nhập tên cho giọng nói")
        self._voice_name_input.textChanged.connect(lambda _: self._update_train_enabled())

        self._language_combo = QComboBox(container)
        languages = [
            ("Tự động", "auto"),
            ("Vietnamese", "vi"),
            ("English", "en"),
            ("Spanish", "es"),
            ("Korean", "ko"),
            ("Japanese", "ja"),
        ]
        for label, code in languages:
            self._language_combo.addItem(label, code)

        form.addRow("Tên giọng", self._voice_name_input)
        form.addRow("Ngôn ngữ ưu tiên", self._language_combo)
        return container

    def _build_selection_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._upload_button = QPushButton("Chọn file âm thanh")
        self._upload_button.clicked.connect(self._handle_choose_samples)

        row.addWidget(self._upload_button)
        row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        return row

    def _build_samples_list(self) -> QWidget:
        self._samples_list = QListWidget(self)
        self._samples_list.setMinimumHeight(180)
        self._samples_list.setObjectName("samplesList")
        return self._samples_list

    def _build_training_controls(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._save_button = QPushButton("Lưu Giọng")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._handle_save_voice)

        self._status_label = QLabel("Chưa chọn file")

        layout.addWidget(self._save_button)
        layout.addWidget(self._status_label)
        return container

    def _build_voices_list(self) -> QWidget:
        """Build UI section for listing and managing existing voices."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Giọng đã lưu", container)
        title.setStyleSheet("font-size: 16px; font-weight: 500;")
        header_row.addWidget(title)
        
        refresh_button = QPushButton("Làm mới", container)
        refresh_button.clicked.connect(self._refresh_voices_list)
        header_row.addWidget(refresh_button)
        header_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        layout.addLayout(header_row)

        self._voices_list = QListWidget(container)
        self._voices_list.setMinimumHeight(200)
        self._voices_list.setMaximumHeight(300)
        layout.addWidget(self._voices_list)

        return container

    def _refresh_voices_list(self) -> None:
        """Refresh the list of saved voices."""
        self._voices_list.clear()
        voices = self._controller._service.list_available_voices()
        
        if not voices:
            item = QListWidgetItem("Chưa có giọng nào được lưu")
            item.setFlags(Qt.NoItemFlags)  # Make it non-selectable
            self._voices_list.addItem(item)
            return

        for voice_name in voices:
            widget = QWidget()
            row_layout = QHBoxLayout(widget)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(12)
            row_layout.setAlignment(Qt.AlignVCenter)

            name_label = QLabel(voice_name, widget)
            name_label.setStyleSheet("font-weight: 500; padding: 4px;")
            row_layout.addWidget(name_label)
            
            row_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            
            delete_button = QPushButton("Xóa", widget)
            delete_button.setText("Xóa")  # Explicitly set text
            delete_button.setMinimumWidth(70)
            delete_button.setMaximumWidth(90)
            delete_button.setMinimumHeight(32)
            delete_button.setMaximumHeight(32)
            delete_button.clicked.connect(lambda checked, name=voice_name: self._handle_delete_voice(name))
            row_layout.addWidget(delete_button)

            # Set size hint before adding to list
            widget.setMinimumHeight(40)
            item = QListWidgetItem()
            item.setSizeHint(widget.minimumSizeHint())
            self._voices_list.addItem(item)
            self._voices_list.setItemWidget(item, widget)

    def _handle_delete_voice(self, voice_name: str) -> None:
        """Handle voice deletion with confirmation."""
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa giọng '{voice_name}'?\n\n"
            "Hành động này không thể hoàn tác.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
            try:
                success = self._controller._service.delete_voice(voice_name)
                if success:
                    self._status_label.setText(f"Đã xóa giọng '{voice_name}'")
                    self._refresh_voices_list()
                    self.voice_created.emit("")  # Emit signal to refresh other tabs
                else:
                    self._show_error("Lỗi xóa giọng", f"Không thể xóa giọng '{voice_name}'")
            except Exception as e:
                self._show_error("Lỗi xóa giọng", str(e))

    def _update_train_enabled(self) -> None:
        voice_name = getattr(self, "_voice_name_input", None)
        button = getattr(self, "_save_button", None)
        if voice_name is None or button is None:
            return
        has_name = bool(voice_name.text().strip())
        button.setEnabled(has_name and bool(self._selected_samples))

    def _handle_choose_samples(self) -> None:
        files = self._controller.select_samples(self)
        if not files:
            return
        self._selected_samples = files
        self._refresh_samples_list(files)
        self._update_train_enabled()
        self._status_label.setText(f"Đã chọn {len(files)} mẫu giọng.")

    def _refresh_samples_list(self, files: Iterable[Path]) -> None:
        self._samples_list.clear()
        for file_path in files:
            item = QListWidgetItem(str(file_path))
            self._samples_list.addItem(item)

    def _handle_save_voice(self) -> None:
        voice_name = self._voice_name_input.text().strip()
        if not voice_name:
            self._show_error("Thiếu tên giọng", "Vui lòng đặt tên cho giọng nói.")
            return
        if not self._selected_samples:
            self._show_error("Chưa chọn file âm thanh", "Vui lòng chọn ít nhất một file âm thanh.")
            return

        language = self._language_combo.currentData() or "auto"
        self._controller.start_training(voice_name, self._selected_samples, language)

    def _on_training_started(self) -> None:
        self._save_button.setEnabled(False)
        self._upload_button.setEnabled(False)
        self._status_label.setText("Đang lưu giọng...")

    def _on_training_finished(self, profile: VoiceProfile) -> None:
        self._status_label.setText(f"Đã lưu giọng '{profile.name}' thành công!")
        self._save_button.setEnabled(True)
        self._upload_button.setEnabled(True)
        self._selected_samples.clear()
        self._samples_list.clear()
        self._voice_name_input.clear()
        self._update_train_enabled()
        self._refresh_voices_list()  # Refresh voices list after adding new voice
        self.voice_created.emit(profile.name)

    def _on_training_failed(self, message: str) -> None:
        self._status_label.setText("Lưu giọng thất bại.")
        self._save_button.setEnabled(True)
        self._upload_button.setEnabled(True)
        self._show_error("Lưu giọng thất bại", message)

    def _show_error(self, title: str, message: str) -> None:
        """Display error message with proper formatting for multi-line text."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()

