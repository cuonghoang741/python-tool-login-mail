"""Settings tab for performance configuration."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from tool_voices.core.config import ConfigManager
    from tool_voices.services.xtts_gateway import XTTSModelGateway


class SettingsTab(QWidget):
    """Tab for configuring performance settings."""
    
    # Signal emitted when settings are applied and model needs reload
    settings_changed = Signal()
    
    def __init__(
        self,
        config_manager: "ConfigManager",
        gateway: "XTTSModelGateway",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._gateway = gateway
        self._build_ui()
        self._load_settings()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("⚙️ Performance Settings")
        header.setStyleSheet("font-size: 20px; font-weight: 600; margin-bottom: 8px;")
        layout.addWidget(header)
        
        # GPU Settings Group
        gpu_group = self._build_gpu_group()
        layout.addWidget(gpu_group)
        
        # Speed Settings Group
        speed_group = self._build_speed_group()
        layout.addWidget(speed_group)
        
        # Advanced Settings Group
        advanced_group = self._build_advanced_group()
        layout.addWidget(advanced_group)
        
        # Status display
        self._status_group = self._build_status_group()
        layout.addWidget(self._status_group)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self._apply_btn = QPushButton("💾 Lưu & Áp dụng")
        self._apply_btn.clicked.connect(self._apply_settings)
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        
        self._reset_btn = QPushButton("🔄 Reset mặc định")
        self._reset_btn.clicked.connect(self._reset_to_defaults)
        
        action_layout.addWidget(self._apply_btn)
        action_layout.addWidget(self._reset_btn)
        action_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        layout.addLayout(action_layout)
        
        # Spacer at bottom
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
    
    def _build_gpu_group(self) -> QGroupBox:
        group = QGroupBox("🖥️ GPU Configuration")
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        
        # Auto-detect GPU checkbox (Renamed to Use GPU for clarity)
        self._auto_detect_gpu = QCheckBox("Sử dụng GPU (Ưu tiên card rời)")
        self._auto_detect_gpu.setToolTip(
            "Bật chế độ sử dụng GPU để tăng tốc độ tạo audio.\n"
            "Nếu tắt, phần mềm sẽ chạy bằng CPU (chậm hơn nhưng ổn định hơn với máy cấu hình thấp)."
        )
        self._auto_detect_gpu.toggled.connect(self._on_auto_detect_changed)
        form.addRow(self._auto_detect_gpu)
        
        # GPU status label
        self._gpu_status = QLabel("Đang kiểm tra...")
        self._gpu_status.setStyleSheet("color: gray; font-style: italic;")
        form.addRow("Trạng thái GPU:", self._gpu_status)
        
        # Use FP16 checkbox
        self._use_fp16 = QCheckBox("Sử dụng FP16 (Half Precision)")
        self._use_fp16.setToolTip(
            "Sử dụng half precision (FP16) để tăng tốc ~2x trên GPU.\n"
            "Chỉ có hiệu lực khi sử dụng GPU."
        )
        form.addRow(self._use_fp16)
        
        return group
    
    def _build_speed_group(self) -> QGroupBox:
        group = QGroupBox("⚡ Speed Preset")
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        
        # Speed preset dropdown
        self._speed_preset = QComboBox()
        self._speed_preset.addItem("🎯 Quality - Chất lượng cao nhất", "quality")
        self._speed_preset.addItem("⚖️ Balanced - Cân bằng (khuyến nghị)", "balanced")
        self._speed_preset.addItem("🚀 Fast - Tốc độ nhanh nhất", "fast")
        self._speed_preset.setToolTip(
            "Quality: gpt_cond_len=6, max_ref_length=30 (chậm nhất, chất lượng cao)\n"
            "Balanced: gpt_cond_len=4, max_ref_length=20 (cân bằng)\n"
            "Fast: gpt_cond_len=3, max_ref_length=10 (nhanh nhất)"
        )
        form.addRow("Preset:", self._speed_preset)
        
        # Streaming inference checkbox
        self._use_streaming = QCheckBox("Sử dụng Streaming Inference")
        self._use_streaming.setToolTip(
            "Bật streaming để xem progress realtime từ model.\n"
            "Hiển thị số audio đã tạo và tốc độ thực tế (e.g., 2.5x realtime).\n"
            "Có thể hơi chậm hơn batch mode trên một số GPU."
        )
        form.addRow(self._use_streaming)
        
        # Description
        desc = QLabel(
            "💡 Speed preset ảnh hưởng đến độ dài conditioning audio được xử lý.\n"
            "    Preset nhanh hơn sẽ giảm chất lượng voice cloning một chút."
        )
        desc.setStyleSheet("color: gray; font-size: 11px;")
        desc.setWordWrap(True)
        form.addRow(desc)
        
        return group
    
    def _build_advanced_group(self) -> QGroupBox:
        group = QGroupBox("🔧 Advanced Optimizations")
        group.setCheckable(True)
        group.setChecked(False)
        
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        
        # torch.compile checkbox
        self._use_torch_compile = QCheckBox("Sử dụng torch.compile (PyTorch 2.0+)")
        self._use_torch_compile.setToolTip(
            "Kích hoạt torch.compile để tối ưu hóa model.\n"
            "Tăng tốc 10-30% nhưng cần thời gian compile lần đầu.\n"
            "Yêu cầu PyTorch 2.0 trở lên."
        )
        form.addRow(self._use_torch_compile)
        
        # Warning label
        warning = QLabel(
            "⚠️ torch.compile có thể gây lỗi với một số cấu hình.\n"
            "    Nếu gặp vấn đề, hãy tắt tùy chọn này."
        )
        warning.setStyleSheet("color: orange; font-size: 11px;")
        warning.setWordWrap(True)
        form.addRow(warning)
        
        return group
    
    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("📊 Current Status")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        self._status_labels = {}
        
        for key, label in [
            ("gpu", "GPU:"),
            ("fp16", "FP16:"),
            ("compiled", "Compiled:"),
            ("preset", "Speed Preset:"),
            ("warmup", "Warmup:"),
        ]:
            row = QHBoxLayout()
            name_label = QLabel(label)
            name_label.setMinimumWidth(100)
            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold;")
            self._status_labels[key] = value_label
            row.addWidget(name_label)
            row.addWidget(value_label)
            row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            layout.addLayout(row)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Status")
        refresh_btn.setMaximumWidth(150)
        refresh_btn.clicked.connect(self._refresh_status)
        layout.addWidget(refresh_btn)
        
        return group
    
    def _load_settings(self) -> None:
        """Load settings from config manager."""
        config = self._config_manager.config
        
        self._auto_detect_gpu.setChecked(config.auto_detect_gpu)
        self._use_fp16.setChecked(config.use_fp16)
        self._use_torch_compile.setChecked(config.use_torch_compile)
        self._use_streaming.setChecked(config.use_streaming)
        
        # Set speed preset
        preset_index = self._speed_preset.findData(config.speed_preset)
        if preset_index >= 0:
            self._speed_preset.setCurrentIndex(preset_index)
        else:
            self._speed_preset.setCurrentIndex(1)  # Default to balanced
        
        # Update GPU status
        self._update_gpu_status()
        self._refresh_status()
    
    def _update_gpu_status(self) -> None:
        """Update GPU status display."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                self._gpu_status.setText(f"✅ {gpu_name}")
                self._gpu_status.setStyleSheet("color: green; font-weight: bold;")
                self._use_fp16.setEnabled(True)
            else:
                self._gpu_status.setText("❌ Không tìm thấy GPU CUDA")
                self._gpu_status.setStyleSheet("color: red;")
                self._use_fp16.setEnabled(False)
                self._use_fp16.setChecked(False)
        except Exception as e:
            self._gpu_status.setText(f"⚠️ Lỗi: {str(e)}")
            self._gpu_status.setStyleSheet("color: orange;")
    
    def _on_auto_detect_changed(self, checked: bool) -> None:
        """Handle auto-detect GPU checkbox change."""
        if checked:
            self._update_gpu_status()
    
    def _refresh_status(self) -> None:
        """Refresh current model status."""
        try:
            gpu_info = self._gateway.gpu_info
            
            # GPU status
            if gpu_info.get("available"):
                self._status_labels["gpu"].setText(f"✅ {gpu_info.get('name', 'Available')}")
                self._status_labels["gpu"].setStyleSheet("color: green; font-weight: bold;")
            else:
                self._status_labels["gpu"].setText("❌ CPU only")
                self._status_labels["gpu"].setStyleSheet("color: gray; font-weight: bold;")
            
            # FP16 status
            if gpu_info.get("fp16_enabled"):
                self._status_labels["fp16"].setText("✅ Enabled")
                self._status_labels["fp16"].setStyleSheet("color: green; font-weight: bold;")
            else:
                self._status_labels["fp16"].setText("❌ Disabled")
                self._status_labels["fp16"].setStyleSheet("color: gray; font-weight: bold;")
            
            # Compiled status
            if gpu_info.get("compiled"):
                self._status_labels["compiled"].setText("✅ Enabled")
                self._status_labels["compiled"].setStyleSheet("color: green; font-weight: bold;")
            else:
                self._status_labels["compiled"].setText("❌ Disabled")
                self._status_labels["compiled"].setStyleSheet("color: gray; font-weight: bold;")
            
            # Speed preset
            preset = gpu_info.get("speed_preset", "balanced")
            preset_labels = {"quality": "🎯 Quality", "balanced": "⚖️ Balanced", "fast": "🚀 Fast"}
            self._status_labels["preset"].setText(preset_labels.get(preset, preset))
            
            # Warmup status
            if gpu_info.get("warmed_up"):
                self._status_labels["warmup"].setText("✅ Model warmed up")
                self._status_labels["warmup"].setStyleSheet("color: green; font-weight: bold;")
            else:
                self._status_labels["warmup"].setText("⏳ Pending (first inference)")
                self._status_labels["warmup"].setStyleSheet("color: orange; font-weight: bold;")
            
        except Exception as e:
            for key in self._status_labels:
                self._status_labels[key].setText("⚠️ Error")
                self._status_labels[key].setStyleSheet("color: orange;")
    
    def _apply_settings(self) -> None:
        """Apply settings and save to config."""
        config = self._config_manager.config
        
        # Update config values
        config.auto_detect_gpu = self._auto_detect_gpu.isChecked()
        config.use_fp16 = self._use_fp16.isChecked()
        config.use_torch_compile = self._use_torch_compile.isChecked()
        config.speed_preset = self._speed_preset.currentData() or "balanced"
        config.use_streaming = self._use_streaming.isChecked()
        
        # Save config
        self._config_manager.save()
        
        # Reload model with new settings
        try:
            self._gateway.reload_model(
                auto_detect_gpu=config.auto_detect_gpu,
                use_fp16=config.use_fp16,
                use_torch_compile=config.use_torch_compile,
                speed_preset=config.speed_preset,
            )
            
            QMessageBox.information(
                self,
                "Thành công",
                "✅ Cài đặt đã được lưu!\n\n"
                "Model sẽ được reload với settings mới khi bạn generate audio tiếp theo.",
            )
            
            # Emit signal
            self.settings_changed.emit()
            
            # Refresh status
            self._refresh_status()
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cảnh báo",
                f"Đã lưu cài đặt nhưng không thể reload model ngay:\n{str(e)}\n\n"
                "Settings sẽ được áp dụng lần khởi động tiếp theo.",
            )
    
    def _reset_to_defaults(self) -> None:
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Xác nhận",
            "Bạn có chắc muốn reset về cài đặt mặc định?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
            self._auto_detect_gpu.setChecked(True)
            self._use_fp16.setChecked(True)
            self._use_torch_compile.setChecked(False)
            self._speed_preset.setCurrentIndex(1)  # Balanced
            self._use_streaming.setChecked(True)  # Streaming on by default
            
            # Apply immediately
            self._apply_settings()
