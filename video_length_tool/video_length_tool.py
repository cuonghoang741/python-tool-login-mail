import math
import os
import subprocess
import sys
import tempfile
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk


def parse_duration_to_seconds(text: str) -> int:
    """
    Parse duration string into total seconds.

    Supported formats:
      - "SS"
      - "MM:SS"
      - "HH:MM:SS"
    """
    text = text.strip()
    if not text:
        raise ValueError("Empty duration")

    parts = text.split(":")
    if len(parts) == 1:
        # seconds
        return int(parts[0])
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)

    raise ValueError("Invalid duration format")


def get_ffmpeg_executable() -> str:
    """
    Try to locate ffmpeg executable.

    Priority:
      1. Bundled / same folder as executable (when frozen with PyInstaller)
      2. Same folder as this script
      3. "ffmpeg" from PATH

    Returns a string to be used as the ffmpeg command.
    """
    candidates: list[str] = []

    # When running as frozen exe (PyInstaller)
    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base_dir, "ffmpeg.exe"))
        candidates.append(os.path.join(base_dir, "ffmpeg"))
        # Also check folder of the exe itself
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "ffmpeg.exe"))
        candidates.append(os.path.join(exe_dir, "ffmpeg"))

    # When running from source
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "ffmpeg.exe"))
    candidates.append(os.path.join(script_dir, "ffmpeg"))
    candidates.append(os.path.join(script_dir, "ffmpeg", "ffmpeg.exe"))
    candidates.append(os.path.join(script_dir, "ffmpeg", "ffmpeg"))

    for path in candidates:
        if os.path.isfile(path):
            return path

    # Fallback: rely on ffmpeg in PATH
    return "ffmpeg"


def get_ffprobe_executable() -> str:
    """
    Try to locate ffprobe executable similar to ffmpeg.
    """
    candidates: list[str] = []

    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base_dir, "ffprobe.exe"))
        candidates.append(os.path.join(base_dir, "ffprobe"))
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "ffprobe.exe"))
        candidates.append(os.path.join(exe_dir, "ffprobe"))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "ffprobe.exe"))
    candidates.append(os.path.join(script_dir, "ffprobe"))
    candidates.append(os.path.join(script_dir, "ffmpeg", "ffprobe.exe"))
    candidates.append(os.path.join(script_dir, "ffmpeg", "ffprobe"))

    for path in candidates:
        if os.path.isfile(path):
            return path

    return "ffprobe"


# Set appearance mode and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class VideoLengthTool(ctk.CTk):
    """
    Modern GUI tool to multiply video length using ffmpeg.

    - Mode 1: multiply length by N times
    - Mode 2: loop until target duration, then cut at that duration

    Requirements:
      - ffmpeg installed, OR ffmpeg.exe placed next to the .exe / script
    """

    # Speed presets: (preset_name, crf_value, display_name)
    SPEED_PRESETS = {
        "balanced": ("medium", 18, "⚖️ Cân bằng (Chất lượng cao)"),
        "fast": ("veryfast", 20, "🚀 Nhanh (Chất lượng cao nhưng output nặng hơn)"),
        "ultrafast": ("ultrafast", 23, "⚡ Siêu nhanh (CL ổn định, hợp Video nhạc)"),
    }

    # Encoder options: (encoder_name, display_name, is_hardware)
    ENCODER_OPTIONS = {
        "libx264": ("libx264", "💻 CPU (libx264)", False),
        "h264_nvenc": ("h264_nvenc", "🎮 NVIDIA GPU (NVENC)", True),
        "h264_qsv": ("h264_qsv", "🔷 Intel GPU (QuickSync)", True),
        "h264_amf": ("h264_amf", "🔴 AMD GPU (AMF)", True),
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("🎬 Video Length Multiplier")
        self.geometry("850x680")
        self.minsize(750, 600)

        # Variables
        self.input_path_var = ctk.StringVar()
        self.output_path_var = ctk.StringVar()

        self.mode_var = ctk.StringVar(value="factor")
        self.factor_var = ctk.StringVar(value="2")
        self.target_duration_var = ctk.StringVar(value="300")

        # Audio playlist (ordered)
        self.audio_files: list[str] = []

        # Video output options
        self.resolution_var = ctk.StringVar(value="")
        self.fps_var = ctk.StringVar()

        # Speed and encoding options
        self.speed_preset_var = ctk.StringVar(value="balanced")
        self.encoder_var = ctk.StringVar(value="libx264")

        self.ffmpeg_executable = get_ffmpeg_executable()

        # Detect available encoders
        self.available_encoders = self._detect_available_encoders()

        # Progress tracking
        self.progress_var = ctk.DoubleVar(value=0)
        self.is_processing = False

        self._build_ui()

    def _detect_available_encoders(self) -> list[str]:
        """
        Detect which hardware encoders are available on this system.
        Returns list of available encoder names.
        """
        available = ["libx264"]  # CPU encoder always available

        # Test each hardware encoder
        hw_encoders = ["h264_nvenc", "h264_qsv", "h264_amf"]

        for encoder in hw_encoders:
            try:
                # Run a quick test to see if encoder is available
                cmd = [
                    self.ffmpeg_executable,
                    "-f", "lavfi",
                    "-i", "color=c=black:s=64x64:d=0.1",
                    "-c:v", encoder,
                    "-f", "null",
                    "-",
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                if result.returncode == 0:
                    available.append(encoder)
            except Exception:
                pass

        return available

    # UI BUILDING
    def _build_ui(self) -> None:
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main scrollable frame
        main_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title (compact)
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            title_frame,
            text="🎬 Video Length Multiplier",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        row_idx = 1

        # ========== FILES (Input + Output combined) ==========
        files_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        files_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        files_frame.grid_columnconfigure(1, weight=1)
        row_idx += 1

        # Input row
        ctk.CTkLabel(files_frame, text="📁 Input:", width=70).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ctk.CTkEntry(
            files_frame, textvariable=self.input_path_var, placeholder_text="Chọn video đầu vào...", height=32
        ).grid(row=0, column=1, sticky="ew", padx=5, pady=8)
        ctk.CTkButton(files_frame, text="Browse", width=70, height=32, command=self.browse_input).grid(
            row=0, column=2, padx=(5, 10), pady=8
        )

        # Output row
        ctk.CTkLabel(files_frame, text="📤 Output:", width=70).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        ctk.CTkEntry(
            files_frame, textvariable=self.output_path_var, placeholder_text="Nơi lưu file...", height=32
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 8))
        ctk.CTkButton(files_frame, text="Browse", width=70, height=32, command=self.browse_output).grid(
            row=1, column=2, padx=(5, 10), pady=(0, 8)
        )

        # ========== AUDIO (collapsible-style, compact) ==========
        audio_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        audio_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        audio_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1

        audio_header = ctk.CTkFrame(audio_frame, fg_color="transparent")
        audio_header.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ctk.CTkLabel(audio_header, text="🎵 Audio (tùy chọn)", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(audio_header, text="➕ Thêm", width=70, height=26, command=self.add_audio_files).pack(side="right", padx=2)
        ctk.CTkButton(
            audio_header, text="➖ Xóa", width=60, height=26, fg_color="#8b0000", hover_color="#a52a2a",
            command=self.remove_selected_audio
        ).pack(side="right", padx=2)

        # Audio listbox (smaller)
        listbox_frame = ctk.CTkFrame(audio_frame, corner_radius=5, height=60)
        listbox_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.audio_listbox = tk.Listbox(
            listbox_frame, height=3, selectmode=tk.MULTIPLE, bg="#2b2b2b", fg="white",
            selectbackground="#1f538d", font=("Segoe UI", 9), borderwidth=0, highlightthickness=0,
        )
        self.audio_listbox.pack(fill="both", expand=True, padx=2, pady=2)

        # ========== MODE (compact, horizontal) ==========
        mode_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        mode_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        row_idx += 1

        mode_inner = ctk.CTkFrame(mode_frame, fg_color="transparent")
        mode_inner.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(mode_inner, text="⚙️ Chế độ:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(mode_inner, text="Nhân x", variable=self.mode_var, value="factor", width=80).pack(side="left")
        ctk.CTkEntry(mode_inner, textvariable=self.factor_var, width=50, height=28, placeholder_text="2").pack(side="left", padx=5)
        ctk.CTkLabel(mode_inner, text="|").pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_inner, text="Lặp đến", variable=self.mode_var, value="target", width=80).pack(side="left")
        ctk.CTkEntry(mode_inner, textvariable=self.target_duration_var, width=80, height=28, placeholder_text="MM:SS").pack(side="left", padx=5)
        ctk.CTkLabel(mode_inner, text="(SS, MM:SS, HH:MM:SS)", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left", padx=5)

        # ========== VIDEO OPTIONS + SPEED (combined, horizontal) ==========
        options_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        options_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        row_idx += 1

        options_inner = ctk.CTkFrame(options_frame, fg_color="transparent")
        options_inner.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(options_inner, text="🎨 Resolution:").pack(side="left")
        resolution_combo = ctk.CTkComboBox(
            options_inner, variable=self.resolution_var,
            values=["", "1080p", "720p", "480p", "360p"], width=100, height=28
        )
        resolution_combo.pack(side="left", padx=5)
        resolution_combo.set("")

        ctk.CTkLabel(options_inner, text="FPS:").pack(side="left", padx=(10, 0))
        ctk.CTkEntry(options_inner, textvariable=self.fps_var, width=50, height=28, placeholder_text="30").pack(side="left", padx=5)

        ctk.CTkLabel(options_inner, text="|").pack(side="left", padx=10)

        ctk.CTkLabel(options_inner, text="⚡ Speed:").pack(side="left")
        speed_values = [self.SPEED_PRESETS[k][2] for k in ["balanced", "fast", "ultrafast"]]
        self.speed_combo = ctk.CTkComboBox(options_inner, values=speed_values, width=180, height=28, command=self._on_speed_change)
        self.speed_combo.set(self.SPEED_PRESETS["balanced"][2])
        self.speed_combo.pack(side="left", padx=5)

        # ========== ENCODER ==========
        encoder_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        encoder_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        row_idx += 1

        encoder_inner = ctk.CTkFrame(encoder_frame, fg_color="transparent")
        encoder_inner.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(encoder_inner, text="🔧 Encoder:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        encoder_values = []
        self._encoder_keys = []
        for key in ["libx264", "h264_nvenc", "h264_qsv", "h264_amf"]:
            if key in self.available_encoders:
                encoder_values.append(self.ENCODER_OPTIONS[key][1])
                self._encoder_keys.append(key)

        self.encoder_combo = ctk.CTkComboBox(encoder_inner, values=encoder_values, width=200, height=28, command=self._on_encoder_change)
        default_encoder_display = self.ENCODER_OPTIONS["libx264"][1]
        for key in ["h264_nvenc", "h264_qsv", "h264_amf"]:
            if key in self.available_encoders:
                default_encoder_display = self.ENCODER_OPTIONS[key][1]
                self.encoder_var.set(key)
                break
        self.encoder_combo.set(default_encoder_display)
        self.encoder_combo.pack(side="left", padx=10)

        gpu_detected = len(self.available_encoders) > 1
        gpu_status = "✅ GPU detected!" if gpu_detected else "⚠️ No GPU"
        gpu_color = "#00aa00" if gpu_detected else "#888888"
        self.gpu_label = ctk.CTkLabel(encoder_inner, text=gpu_status, font=ctk.CTkFont(size=11), text_color=gpu_color)
        self.gpu_label.pack(side="left", padx=10)

        # Encoder tip
        ctk.CTkLabel(
            encoder_frame, text="💡 GPU nhanh hơn 10-20x CPU • 'Siêu nhanh' phù hợp video nhạc",
            font=ctk.CTkFont(size=10), text_color="gray"
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # ========== PROGRESS + BUTTON ==========
        action_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        action_frame.grid(row=row_idx, column=0, sticky="ew", pady=3)
        action_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1

        self.progress_bar = ctk.CTkProgressBar(action_frame, variable=self.progress_var, height=15, corner_radius=8)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(action_frame, text="Sẵn sàng", font=ctk.CTkFont(size=11))
        self.progress_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))

        self.run_button = ctk.CTkButton(
            action_frame, text="🚀 Tạo Video", font=ctk.CTkFont(size=16, weight="bold"),
            height=40, corner_radius=8, command=self.run
        )
        self.run_button.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))

        # ========== LOG ==========
        log_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        log_frame.grid(row=row_idx, column=0, sticky="nsew", pady=3)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(log_frame, text="📋 Log", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 3)
        )
        self.log_text = ctk.CTkTextbox(log_frame, height=120, corner_radius=5, font=ctk.CTkFont(family="Consolas", size=10))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(3, 10))

    # UI CALLBACKS
    def _on_speed_change(self, value: str) -> None:
        """Handle speed combobox selection change."""
        for key, (_, _, display) in self.SPEED_PRESETS.items():
            if display == value:
                self.speed_preset_var.set(key)
                break

    def _on_encoder_change(self, value: str) -> None:
        """Handle encoder combobox selection change."""
        for key, (_, display, _) in self.ENCODER_OPTIONS.items():
            if display == value:
                self.encoder_var.set(key)
                break

    def add_audio_files(self) -> None:
        filetypes = [
            ("Audio files", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Select audio files", filetypes=filetypes)
        if not paths:
            return
        for p in paths:
            if p not in self.audio_files:
                self.audio_files.append(p)
                self.audio_listbox.insert("end", os.path.basename(p))

    def remove_selected_audio(self) -> None:
        selection = list(self.audio_listbox.curselection())
        if not selection:
            return
        # Remove from bottom to top to keep indices valid
        for index in reversed(selection):
            if index < len(self.audio_files):
                self.audio_files.pop(index)
            self.audio_listbox.delete(index)

    def browse_input(self) -> None:
        filetypes = [
            ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select input video", filetypes=filetypes)
        if not path:
            return
        self.input_path_var.set(path)

        # Suggest output path
        base, ext = os.path.splitext(path)
        self.output_path_var.set(f"{base}_multiplied{ext}")

    def browse_output(self) -> None:
        initial = self.output_path_var.get().strip() or self.input_path_var.get().strip()
        initial_dir = os.path.dirname(initial) if initial else os.getcwd()

        filetypes = [
            ("MP4 video", "*.mp4"),
            ("All files", "*.*"),
        ]
        path = filedialog.asksaveasfilename(
            title="Select output video file",
            initialdir=initial_dir,
            defaultextension=".mp4",
            filetypes=filetypes,
        )
        if not path:
            return
        self.output_path_var.set(path)

    def append_log(self, text: str) -> None:
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.update_idletasks()

    def update_progress(self, value: float, text: str = "") -> None:
        """Update progress bar and label."""
        self.progress_var.set(value)
        if text:
            self.progress_label.configure(text=text)
        self.update_idletasks()

    def _parse_resolution_preset(self, preset: str) -> tuple[int | None, int | None]:
        """
        Convert resolution preset string to (width, height) tuple.
        Returns (None, None) if empty or invalid.
        """
        if not preset or preset.strip() == "":
            return (None, None)

        preset_lower = preset.lower().strip()
        # Map common presets to (width, height)
        resolution_map = {
            "2160p (4k)": (3840, 2160),
            "1440p (2k)": (2560, 1440),
            "1080p (full hd)": (1920, 1080),
            "720p (hd)": (1280, 720),
            "480p (sd)": (854, 480),
            "360p": (640, 360),
            "240p": (426, 240),
        }

        return resolution_map.get(preset_lower, (None, None))

    def _get_speed_preset_key(self) -> str:
        """Get speed preset key from UI selection."""
        selected_display = self.speed_combo.get()
        for key, (_, _, display) in self.SPEED_PRESETS.items():
            if display == selected_display:
                return key
        return "balanced"

    def _get_encoder_config(self) -> tuple[str, str, int]:
        """
        Get encoder configuration based on current UI selections.
        Returns: (encoder_name, preset, crf_value)
        """
        encoder = self.encoder_var.get()
        speed_key = self._get_speed_preset_key()
        preset, crf, _ = self.SPEED_PRESETS[speed_key]

        # For hardware encoders, adjust parameters
        if encoder in ["h264_nvenc", "h264_qsv", "h264_amf"]:
            # Hardware encoders use different quality parameters
            # Map CRF to appropriate quality settings
            if speed_key == "balanced":
                return (encoder, "p4", 23)  # NVENC: p1-p7, lower is faster
            elif speed_key == "fast":
                return (encoder, "p2", 25)
            else:  # ultrafast
                return (encoder, "p1", 28)
        else:
            # CPU encoder (libx264)
            return (encoder, preset, crf)

    def _build_encode_args(self, include_audio: bool = True) -> list[str]:
        """
        Build ffmpeg encoding arguments based on current settings.
        Returns list of arguments for video encoding.
        """
        encoder, preset, crf = self._get_encoder_config()
        args: list[str] = ["-threads", "0"]  # Use all CPU cores

        if encoder == "libx264":
            args.extend([
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
            ])
        elif encoder == "h264_nvenc":
            args.extend([
                "-c:v", "h264_nvenc",
                "-preset", preset,
                "-cq", str(crf),
                "-rc", "vbr",
            ])
        elif encoder == "h264_qsv":
            args.extend([
                "-c:v", "h264_qsv",
                "-preset", preset,
                "-global_quality", str(crf),
            ])
        elif encoder == "h264_amf":
            args.extend([
                "-c:v", "h264_amf",
                "-quality", "speed" if preset in ["p1", "p2"] else "balanced",
                "-rc", "vbr_latency",
                "-qp_i", str(crf),
                "-qp_p", str(crf),
            ])

        if include_audio:
            args.extend(["-c:a", "aac", "-b:a", "192k"])

        return args

    # CORE LOGIC
    def run(self) -> None:
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()

        if not input_path:
            messagebox.showerror("Error", "Vui lòng chọn file video đầu vào.")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("Error", "File đầu vào không tồn tại.")
            return
        if not output_path:
            messagebox.showerror("Error", "Vui lòng chọn nơi lưu file output.")
            return

        mode = self.mode_var.get()
        factor = None
        target_seconds = None
        try:
            if mode == "factor":
                factor_text = self.factor_var.get().strip()
                factor = int(factor_text)
                if factor <= 0:
                    raise ValueError
                if factor == 1:
                    # Just copy file
                    self.append_log("Factor is 1, copying input to output...")
                desc = f"Nhân dài video x{factor}"
            else:
                duration_text = self.target_duration_var.get().strip()
                target_seconds = parse_duration_to_seconds(duration_text)
                if target_seconds <= 0:
                    raise ValueError
                desc = f"Lặp đến {target_seconds} giây"
        except ValueError:
            if mode == "factor":
                messagebox.showerror("Error", "Hệ số phải là số nguyên dương.")
            else:
                messagebox.showerror(
                    "Error",
                    "Thời lượng không hợp lệ. Dùng SS, MM:SS hoặc HH:MM:SS (vd: 300, 05:00, 00:05:00).",
                )
            return

        # Parse video options
        resolution_text = self.resolution_var.get().strip()
        fps_text = self.fps_var.get().strip()

        width, height = self._parse_resolution_preset(resolution_text)
        fps = None
        try:
            if fps_text:
                fps = float(fps_text)
                if fps <= 0:
                    raise ValueError
        except ValueError:
            messagebox.showerror(
                "Error",
                "FPS không hợp lệ. FPS phải là số dương.",
            )
            return

        self.append_log(f"📥 Input: {input_path}")
        self.append_log(f"📤 Output: {output_path}")
        self.append_log(f"⚙️ Mode: {desc}")
        if self.audio_files:
            self.append_log(f"🎵 Audio tracks: {len(self.audio_files)} file(s)")
            for idx, path in enumerate(self.audio_files, start=1):
                self.append_log(f"   {idx}. {os.path.basename(path)}")
        if width or height or fps:
            res_str = f"{width}x{height}" if width and height else "giữ nguyên"
            self.append_log(
                f"🎨 Video options - resolution: {res_str}, fps: {fps or 'giữ nguyên'}",
            )
        self.append_log(f"🔧 Using ffmpeg: {self.ffmpeg_executable}")
        # Log encoder and speed settings
        encoder, preset, crf = self._get_encoder_config()
        speed_key = self._get_speed_preset_key()
        self.append_log(f"⚡ Encoder: {encoder} | Preset: {preset} | Quality: {crf} | Speed: {speed_key}")
        self.append_log(f"📊 Available encoders: {self.available_encoders}")
        self.append_log("🚀 Bắt đầu xử lý...")

        # Decide whether to use simple video-only pipeline
        use_advanced = bool(self.audio_files or width or height or fps)

        # Determine target duration (in seconds) for advanced pipeline
        if use_advanced and mode == "factor":
            try:
                base_duration = self._get_media_duration(input_path)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(
                    "Error",
                    f"Không thể lấy thời lượng video (required for factor mode with audio/options): {exc}",
                )
                self.run_button.configure(state="normal")
                return
            target_seconds = int(math.ceil(base_duration * factor))
        elif mode == "target":
            # target_seconds is already set from parsing above
            pass
        else:
            # Simple factor mode without advanced options - no need to calculate target_seconds
            target_seconds = None

        # Run in background thread to keep UI responsive
        self.run_button.configure(state="disabled")
        self.update_progress(0, "Đang xử lý...")
        thread = threading.Thread(
            target=self._run_ffmpeg_worker,
            args=(input_path, output_path, mode, factor, target_seconds, use_advanced, width, height, fps),
            daemon=True,
        )
        thread.start()

    def _run_ffmpeg_worker(
        self,
        input_path: str,
        output_path: str,
        mode: str,
        factor: int | None,
        target_seconds: int | None,
        use_advanced: bool,
        width: int | None,
        height: int | None,
        fps: float | None,
    ) -> None:
        try:
            if not self.ffmpeg_executable:
                raise FileNotFoundError("ffmpeg executable not configured.")

            if use_advanced:
                assert target_seconds is not None
                self._run_advanced_pipeline(
                    input_path=input_path,
                    output_path=output_path,
                    target_seconds=target_seconds,
                    width=width,
                    height=height,
                    fps=fps,
                )
            else:
                if mode == "factor":
                    assert factor is not None
                    self._run_ffmpeg_factor(input_path, output_path, factor)
                else:
                    assert target_seconds is not None
                    self._run_ffmpeg_target(input_path, output_path, target_seconds)
            self.append_log("✅ Hoàn thành!")
            self.update_progress(1.0, "✅ Hoàn thành!")
            messagebox.showinfo("Thành công", "Video đã được tạo thành công!")
        except FileNotFoundError:
            self.append_log("❌ Error: ffmpeg not found. Make sure ffmpeg is available.")
            self.update_progress(0, "❌ Lỗi: Không tìm thấy ffmpeg")
            messagebox.showerror(
                "Error",
                (
                    "ffmpeg not found.\n\n"
                    "Options:\n"
                    "1) Install ffmpeg and add it to PATH, or\n"
                    "2) Download ffmpeg.exe and place it in the same folder as the .exe or this script."
                ),
            )
        except subprocess.CalledProcessError as exc:
            self.append_log("❌ ffmpeg failed with error code: %s" % exc.returncode)
            self.append_log(str(exc))
            self.update_progress(0, "❌ Lỗi ffmpeg")
            messagebox.showerror("Error", "ffmpeg failed. Vui lòng kiểm tra log để biết chi tiết.")
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"❌ Unexpected error: {exc}")
            self.update_progress(0, "❌ Lỗi không xác định")
            messagebox.showerror("Error", f"Unexpected error: {exc}")
        finally:
            self.run_button.configure(state="normal")

    def _run_ffmpeg_factor(self, input_path: str, output_path: str, factor: int) -> None:
        if factor == 1:
            # Simple copy using ffmpeg to keep container consistent
            cmd = [
                self.ffmpeg_executable,
                "-y",
                "-i",
                input_path,
                "-c",
                "copy",
                output_path,
            ]
            self.append_log("🔄 Running ffmpeg (copy only)...")
            self.append_log(" ".join(cmd))
            subprocess.run(cmd, check=True)
            return

        loop_count = factor - 1
        # First try stream_loop with stream copy (fast, no re-encode)
        cmd_copy = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            str(loop_count),
            "-i",
            input_path,
            "-c",
            "copy",
            output_path,
        ]

        self.append_log("🔄 Running ffmpeg (copy mode)...")
        self.append_log(" ".join(cmd_copy))
        try:
            subprocess.run(cmd_copy, check=True)
            return
        except subprocess.CalledProcessError:
            self.append_log("⚠️ Copy mode failed, retrying with re-encode...")

        # Fallback: re-encode to ensure compatibility
        encode_args = self._build_encode_args(include_audio=True)
        cmd_reencode = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            str(loop_count),
            "-i",
            input_path,
            *encode_args,
            output_path,
        ]
        self.append_log("🔄 Running ffmpeg (re-encode mode)...")
        self.append_log(" ".join(cmd_reencode))
        subprocess.run(cmd_reencode, check=True)

    def _run_ffmpeg_target(self, input_path: str, output_path: str, target_seconds: int) -> None:
        # Loop infinitely and cut at target duration
        cmd_copy = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            input_path,
            "-t",
            str(target_seconds),
            "-c",
            "copy",
            output_path,
        ]
        self.append_log("🔄 Running ffmpeg (copy mode, target duration)...")
        self.append_log(" ".join(cmd_copy))
        try:
            subprocess.run(cmd_copy, check=True)
            return
        except subprocess.CalledProcessError:
            self.append_log("⚠️ Copy mode failed, retrying with re-encode...")

        encode_args = self._build_encode_args(include_audio=True)
        cmd_reencode = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            input_path,
            "-t",
            str(target_seconds),
            *encode_args,
            output_path,
        ]
        self.append_log("🔄 Running ffmpeg (re-encode mode, target duration)...")
        self.append_log(" ".join(cmd_reencode))
        subprocess.run(cmd_reencode, check=True)

    # Helpers for durations and advanced pipeline
    def _get_media_duration(self, path: str) -> float:
        """
        Get media duration in seconds using ffprobe.
        """
        ffprobe = get_ffprobe_executable()
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        self.append_log("🔍 Running ffprobe: " + " ".join(cmd))
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=30)
            duration_str = out.decode("utf-8", errors="replace").strip()
            if not duration_str or duration_str.lower() in ("nan", "inf", "-inf"):
                raise ValueError(f"Invalid duration from ffprobe: {duration_str}")
            duration = float(duration_str)
            if duration <= 0:
                raise ValueError(f"Duration must be positive, got: {duration}")
            return duration
        except FileNotFoundError:
            self.append_log(f"❌ Error: ffprobe not found at: {ffprobe}")
            raise FileNotFoundError(
                f"ffprobe not found. Please ensure ffprobe.exe is in the same folder as ffmpeg.exe or in PATH."
            ) from None
        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            self.append_log(f"❌ ffprobe error: {error_msg}")
            raise RuntimeError(f"ffprobe failed: {error_msg}") from exc
        except ValueError as exc:
            raise exc
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"❌ Unexpected error getting duration: {exc}")
            raise RuntimeError(f"Failed to get media duration: {exc}") from exc

    def _run_advanced_pipeline(
        self,
        input_path: str,
        output_path: str,
        target_seconds: int,
        width: int | None,
        height: int | None,
        fps: float | None,
    ) -> None:
        """
        Advanced pipeline:
        - Create video track of desired duration (and resolution/fps if requested)
        - Create audio track by concatenating and looping playlist to target duration
        - Mux video + audio into final output
        """
        # Create temp directory near output
        base_dir = os.path.dirname(output_path) or os.getcwd()
        tmp_dir = tempfile.mkdtemp(prefix="video_length_tool_", dir=base_dir)
        self.append_log(f"📁 Using temporary directory: {tmp_dir}")

        tmp_video = os.path.join(tmp_dir, "tmp_video.mp4")
        tmp_audio = os.path.join(tmp_dir, "tmp_audio.m4a")

        try:
            # 1) Build video track
            self.update_progress(0.2, "🎬 Đang tạo video track...")
            self._build_video_track(
                input_path=input_path,
                tmp_video=tmp_video,
                target_seconds=target_seconds,
                width=width,
                height=height,
                fps=fps,
            )

            # 2) Build audio track (if any audio files)
            if self.audio_files:
                self.update_progress(0.6, "🎵 Đang tạo audio track...")
                self._build_audio_track(
                    audio_files=self.audio_files,
                    tmp_audio=tmp_audio,
                    target_seconds=target_seconds,
                )
                # 3) Mux video + audio
                self.update_progress(0.8, "🔧 Đang ghép video + audio...")
                cmd_mux = [
                    self.ffmpeg_executable,
                    "-y",
                    "-i",
                    tmp_video,
                    "-i",
                    tmp_audio,
                    "-map",
                    "0:v",  # Video from first input (tmp_video)
                    "-map",
                    "1:a",  # Audio from second input (tmp_audio)
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-shortest",
                    output_path,
                ]
            else:
                # No custom audio: just use video track (may contain original audio if kept)
                self.update_progress(0.8, "🔧 Đang hoàn thiện video...")
                cmd_mux = [
                    self.ffmpeg_executable,
                    "-y",
                    "-i",
                    tmp_video,
                    "-c",
                    "copy",
                    output_path,
                ]

            self.append_log("🔧 Muxing final output...")
            self.append_log(" ".join(cmd_mux))
            subprocess.run(cmd_mux, check=True)
        finally:
            # Clean up temp files
            try:
                if os.path.exists(tmp_video):
                    os.remove(tmp_video)
            except Exception:
                pass
            try:
                if os.path.exists(tmp_audio):
                    os.remove(tmp_audio)
            except Exception:
                pass
            try:
                if os.path.isdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except Exception:
                pass

    def _build_video_track(
        self,
        input_path: str,
        tmp_video: str,
        target_seconds: int,
        width: int | None,
        height: int | None,
        fps: float | None,
    ) -> None:
        """
        Create a video-only track of given duration, applying resolution/fps if requested.
        """
        # Build video filter string
        filters: list[str] = []
        if width or height:
            w = width if width else -1
            h = height if height else -1
            filters.append(f"scale={w}:{h}")
        if fps:
            filters.append(f"fps={fps}")

        vf_args: list[str] = []
        if filters:
            vf_args = ["-vf", ",".join(filters)]

        # If no filters, we can try copy mode first for speed
        # But we need to remove audio stream when building video-only track
        if not filters:
            cmd_copy = [
                self.ffmpeg_executable,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                input_path,
                "-t",
                str(target_seconds),
                "-map",
                "0:v",  # Only take video stream, exclude audio
                "-c:v",
                "copy",
                tmp_video,
            ]
            self.append_log("🔄 Building video track (copy mode, video only)...")
            self.append_log(" ".join(cmd_copy))
            try:
                subprocess.run(cmd_copy, check=True)
                return
            except subprocess.CalledProcessError:
                self.append_log("⚠️ Copy mode for video track failed, retrying with re-encode...")

        # Re-encode video
        encode_args = self._build_encode_args(include_audio=False)
        cmd_reencode = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            input_path,
            "-t",
            str(target_seconds),
            *vf_args,
            "-an",
            *encode_args,
            tmp_video,
        ]
        self.append_log("🔄 Building video track (re-encode mode)...")
        self.append_log(" ".join(cmd_reencode))
        subprocess.run(cmd_reencode, check=True)

    def _build_audio_track(
        self,
        audio_files: list[str],
        tmp_audio: str,
        target_seconds: int,
    ) -> None:
        """
        Build a single audio track by concatenating audio_files in order,
        looping playlist until reaching target_seconds, then cutting.
        """
        if not audio_files:
            return

        # Measure total duration of one playlist cycle
        total_cycle = 0.0
        durations: list[float] = []
        for path in audio_files:
            d = self._get_media_duration(path)
            durations.append(d)
            total_cycle += d

        if total_cycle <= 0:
            raise RuntimeError("Invalid audio durations for playlist.")

        # Number of cycles needed to exceed target_seconds
        cycles = max(1, int(math.ceil(target_seconds / total_cycle)))

        base_dir = os.path.dirname(tmp_audio)
        playlist_path = os.path.join(base_dir, "audio_playlist.txt")

        def _escape_path(p: str) -> str:
            # Keep it simple: use absolute path, replace backslashes
            p_abs = os.path.abspath(p)
            return p_abs.replace("\\", "/").replace("'", "'\\''")

        with open(playlist_path, "w", encoding="utf-8") as f:
            for _ in range(cycles):
                for p in audio_files:
                    escaped = _escape_path(p)
                    f.write(f"file '{escaped}'\n")

        cmd = [
            self.ffmpeg_executable,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            playlist_path,
            "-t",
            str(target_seconds),
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            tmp_audio,
        ]
        self.append_log("🎵 Building audio track from playlist...")
        self.append_log(" ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
        finally:
            try:
                if os.path.exists(playlist_path):
                    os.remove(playlist_path)
            except Exception:
                pass


def main() -> None:
    app = VideoLengthTool()
    app.mainloop()


if __name__ == "__main__":
    main()
