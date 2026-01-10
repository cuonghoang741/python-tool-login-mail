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
    Modern GUI tool for video processing with ffmpeg.

    Features:
    - Video Length Multiplier: multiply video length or loop to target duration
    - Merge Clips: combine multiple videos into one with drag-drop reordering

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
        self.title("🎬 Video Tool Pro")
        self.geometry("900x750")
        self.minsize(800, 700)

        # Variables for Video Length tab
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

        # Variables for Merge Clips tab
        self.merge_video_files: list[str] = []
        self.merge_output_path_var = ctk.StringVar()
        self.merge_progress_var = ctk.DoubleVar(value=0)
        self.merge_encoder_var = ctk.StringVar(value="libx264")
        self.merge_speed_preset_var = ctk.StringVar(value="balanced")
        self.merge_trim_var = ctk.BooleanVar(value=True)  # Trim 1s from start/end, default ON
        self.merge_trim_var = ctk.BooleanVar(value=True)  # Trim 1s from start/end, default ON
        self.merge_mute_var = ctk.BooleanVar(value=True)
        self.merge_image_duration_var = ctk.StringVar(value="5")
        
        # Merge Clips - Music List
        self.merge_music_files: list[str] = []
        # Merge Clips - Voice List
        self.merge_voice_files: list[str] = []
        
        # Transitions
        self.merge_transition_var = ctk.StringVar(value="None")
        self.merge_transition_duration_var = ctk.StringVar(value="0.5")
        
        self.TRANSITIONS = ["None", "Random", "Fade Black", "Fade White", "Crossfade", "Wipe Left", "Wipe Right", "Slide Left", "Slide Right"]

        # Drag-and-drop state
        self._drag_start_index: int | None = None

        self._build_ui()

    def _detect_available_encoders(self) -> list[str]:
        """
        Detect which hardware encoders are available on this system.
        Returns list of available encoder names.
        
        Refined logic:
        1. For NVIDIA (h264_nvenc): Check hardware presence (torch/nvidia-smi) AND ffmpeg support.
           This mimics 'tool_voices' robustness.
        2. For others (QSV, AMF): Use functional test.
        """
        available = ["libx264"]  # CPU encoder always available

        # --- NVIDIA Detection (Robust) ---
        has_nvidia_hardware = False
        
        # 1. Try torch (like tool_voices)
        try:
            import torch
            if torch.cuda.is_available():
                has_nvidia_hardware = True
        except ImportError:
            pass
            
        # 2. Try nvidia-smi if torch failed or not installed
        if not has_nvidia_hardware:
            try:
                # Check if nvidia-smi is in PATH and runs
                subprocess.check_call(
                    ["nvidia-smi"], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                has_nvidia_hardware = True
            except (FileNotFoundError, subprocess.CalledProcessError, Exception):
                pass

        if has_nvidia_hardware:
            # Check if ffmpeg binary supports h264_nvenc
            try:
                cmd = [self.ffmpeg_executable, "-v", "error", "-h", "encoder=h264_nvenc"]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode == 0:
                    available.append("h264_nvenc")
            except Exception:
                # If checking binary fails, fall back to functional test
                pass

        # --- Other Hardware Encoders (QSV, AMF) or NVENC fallback ---
        # If NVENC was not added by the robust check (e.g. no hardware found but maybe we missed it?), 
        # run the functional test just in case, plus check QSV/AMF.
        
        hw_encoders = []
        if "h264_nvenc" not in available:
            hw_encoders.append("h264_nvenc")
        
        # Add others
        hw_encoders.extend(["h264_qsv", "h264_amf"])

        for encoder in hw_encoders:
            try:
                # Run a quick test to see if encoder is available
                # Using nullsrc is sometimes safer than color
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
                    timeout=5, # Reduced timeout for faster startup
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

        # Create Tabview
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Add tabs
        self.tabview.add("📹 Video Length")
        self.tabview.add("🎞️ Merge Clips")

        # Build each tab's content
        self._build_video_length_tab()
        self._build_merge_clips_tab()

    def _build_video_length_tab(self) -> None:
        """Build the Video Length Multiplier tab UI."""
        tab = self.tabview.tab("📹 Video Length")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)  # Make row 0 (main_frame) expandable

        # Main scrollable frame
        main_frame = ctk.CTkScrollableFrame(tab, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title (compact)
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            title_frame,
            text="🎬 Video Length Multiplier",
            font=ctk.CTkFont(size=20, weight="bold"),
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

    def _build_merge_clips_tab(self) -> None:
        """Build the Merge Clips tab UI with drag-and-drop reordering."""
        tab = self.tabview.tab("🎞️ Merge Clips")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)  # Make video list expandable

        # Main scrollable frame
        main_frame = ctk.CTkFrame(tab, corner_radius=0, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)

        # Title
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            title_frame,
            text="🎞️ Merge Clips - Ghép nhiều video thành 1",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        # ========== VIDEO LIST WITH CONTROLS ==========
        video_list_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        video_list_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        video_list_frame.grid_columnconfigure(0, weight=1)
        video_list_frame.grid_rowconfigure(1, weight=1)

        # Header with buttons
        header_frame = ctk.CTkFrame(video_list_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ctk.CTkLabel(
            header_frame,
            text="📁 Danh sách video (kéo thả để thay đổi thứ tự)",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            header_frame, text="🗑️ Xóa hết", width=80, height=28,
            fg_color="#8b0000", hover_color="#a52a2a",
            command=self._merge_clear_all
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header_frame, text="➖ Xóa chọn", width=90, height=28,
            fg_color="#555555", hover_color="#666666",
            command=self._merge_remove_selected
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header_frame, text="⬇️ Xuống", width=70, height=28,
            command=self._merge_move_down
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header_frame, text="⬆️ Lên", width=70, height=28,
            command=self._merge_move_up
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header_frame, text="➕ Thêm video", width=100, height=28,
            fg_color="#1f7a1f", hover_color="#2a9a2a",
            command=self._merge_add_videos
        ).pack(side="right", padx=2)

        # Video listbox with drag-drop support
        listbox_container = ctk.CTkFrame(video_list_frame, corner_radius=5)
        listbox_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        listbox_container.grid_columnconfigure(0, weight=1)
        listbox_container.grid_rowconfigure(0, weight=1)

        self.merge_listbox = tk.Listbox(
            listbox_container,
            height=10,
            selectmode=tk.SINGLE,
            bg="#2b2b2b",
            fg="white",
            selectbackground="#1f538d",
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
            activestyle='none',
        )
        self.merge_listbox.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Scrollbar for listbox
        merge_scrollbar = ctk.CTkScrollbar(listbox_container, command=self.merge_listbox.yview)
        merge_scrollbar.grid(row=0, column=1, sticky="ns")
        self.merge_listbox.configure(yscrollcommand=merge_scrollbar.set)

        # Bind drag-and-drop events
        self.merge_listbox.bind('<Button-1>', self._on_drag_start)
        self.merge_listbox.bind('<B1-Motion>', self._on_drag_motion)
        self.merge_listbox.bind('<ButtonRelease-1>', self._on_drag_end)

        # Tip label
        ctk.CTkLabel(
            video_list_frame,
            text="💡 Kéo thả để sắp xếp • Video sẽ được ghép theo thứ tự từ trên xuống dưới",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))

        # ========== OUTPUT AND OPTIONS ==========
        options_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        options_frame.grid(row=2, column=0, sticky="ew", pady=5)
        options_frame.grid_columnconfigure(1, weight=1)

        # Output path
        ctk.CTkLabel(options_frame, text="📤 Output:", width=70).grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        ctk.CTkEntry(
            options_frame,
            textvariable=self.merge_output_path_var,
            placeholder_text="Chọn nơi lưu file merged...",
            height=32
        ).grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ctk.CTkButton(
            options_frame, text="Browse", width=70, height=32,
            command=self._merge_browse_output
        ).grid(row=0, column=2, padx=(5, 10), pady=10)

        # Encoder and speed options
        encoder_options_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        encoder_options_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(encoder_options_frame, text="🔧 Encoder:").pack(side="left")

        # Build encoder combo for merge tab
        encoder_values = []
        for key in ["libx264", "h264_nvenc", "h264_qsv", "h264_amf"]:
            if key in self.available_encoders:
                encoder_values.append(self.ENCODER_OPTIONS[key][1])

        self.merge_encoder_combo = ctk.CTkComboBox(
            encoder_options_frame,
            values=encoder_values,
            width=180, height=28,
            command=self._on_merge_encoder_change
        )
        default_encoder_display = self.ENCODER_OPTIONS["libx264"][1]
        for key in ["h264_nvenc", "h264_qsv", "h264_amf"]:
            if key in self.available_encoders:
                default_encoder_display = self.ENCODER_OPTIONS[key][1]
                self.merge_encoder_var.set(key)
                break
        self.merge_encoder_combo.set(default_encoder_display)
        self.merge_encoder_combo.pack(side="left", padx=10)

        ctk.CTkLabel(encoder_options_frame, text="⚡ Speed:").pack(side="left", padx=(10, 0))

        speed_values = [self.SPEED_PRESETS[k][2] for k in ["balanced", "fast", "ultrafast"]]
        self.merge_speed_combo = ctk.CTkComboBox(
            encoder_options_frame,
            values=speed_values,
            width=180, height=28,
            command=self._on_merge_speed_change
        )
        self.merge_speed_combo.set(self.SPEED_PRESETS["balanced"][2])
        self.merge_speed_combo.pack(side="left", padx=10)

        # Trim option row
        trim_options_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        trim_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))

        self.merge_trim_checkbox = ctk.CTkCheckBox(
            trim_options_frame,
            text="✂️ Cắt đầu, cuối (bỏ 1s đầu và 1s cuối mỗi video)",
            variable=self.merge_trim_var,
            font=ctk.CTkFont(size=12),
        )
        self.merge_trim_checkbox.pack(side="left")

        # Mute Source
        ctk.CTkCheckBox(
            trim_options_frame, text="🔇 Tắt toàn bộ sound (source)", variable=self.merge_mute_var, font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=15)

        # Image Duration
        ctk.CTkLabel(trim_options_frame, text="⏱️ Ảnh (giây):").pack(side="left", padx=(15, 5))
        ctk.CTkEntry(
            trim_options_frame, textvariable=self.merge_image_duration_var, width=50
        ).pack(side="left")

        # Audio Container (Music + Voice Side-by-Side)
        audio_container = ctk.CTkFrame(options_frame, fg_color="transparent")
        audio_container.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 5))
        audio_container.grid_columnconfigure(0, weight=1)
        audio_container.grid_columnconfigure(1, weight=1)

        # --- Music Section (Left) ---
        music_frame = ctk.CTkFrame(audio_container, fg_color="#404040", corner_radius=6)
        music_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=0)
        
        music_header = ctk.CTkFrame(music_frame, fg_color="transparent")
        music_header.pack(fill="x", pady=2, padx=5)
        
        ctk.CTkLabel(music_header, text="🎵 Nhạc nền", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        
        # Compact buttons
        ctk.CTkButton(music_header, text="Del", width=40, height=22, fg_color="#8b0000", command=self._merge_remove_music).pack(side="right", padx=1)
        ctk.CTkButton(music_header, text="Add", width=40, height=22, fg_color="#1f7a1f", command=self._merge_add_music).pack(side="right", padx=1)
        ctk.CTkButton(music_header, text="⬇", width=25, height=22, command=self._merge_music_move_down).pack(side="right", padx=1)
        ctk.CTkButton(music_header, text="⬆", width=25, height=22, command=self._merge_music_move_up).pack(side="right", padx=1)

        self.merge_music_listbox = tk.Listbox(
            music_frame, height=3, selectmode=tk.SINGLE, bg="#2b2b2b", fg="white",
            selectbackground="#1f538d", font=("Segoe UI", 9), borderwidth=0, highlightthickness=0
        )
        self.merge_music_listbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # --- Voice Section (Right) ---
        voice_frame = ctk.CTkFrame(audio_container, fg_color="#404040", corner_radius=6)
        voice_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        
        voice_header = ctk.CTkFrame(voice_frame, fg_color="transparent")
        voice_header.pack(fill="x", pady=2, padx=5)
        
        ctk.CTkLabel(voice_header, text="🗣️ Voice", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        
        ctk.CTkButton(voice_header, text="Del", width=40, height=22, fg_color="#8b0000", command=self._merge_remove_voice).pack(side="right", padx=1)
        ctk.CTkButton(voice_header, text="Add", width=40, height=22, fg_color="#1f7a1f", command=self._merge_add_voice).pack(side="right", padx=1)
        ctk.CTkButton(voice_header, text="⬇", width=25, height=22, command=self._merge_voice_move_down).pack(side="right", padx=1)
        ctk.CTkButton(voice_header, text="⬆", width=25, height=22, command=self._merge_voice_move_up).pack(side="right", padx=1)

        self.merge_voice_listbox = tk.Listbox(
            voice_frame, height=3, selectmode=tk.SINGLE, bg="#2b2b2b", fg="white",
            selectbackground="#1f538d", font=("Segoe UI", 9), borderwidth=0, highlightthickness=0
        )
        self.merge_voice_listbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # --- Transition & Effects Row ---
        effects_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        effects_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(effects_frame, text="✨ Hiệu ứng:").pack(side="left")
        ctk.CTkComboBox(
            effects_frame, values=self.TRANSITIONS, variable=self.merge_transition_var, width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(effects_frame, text="⏱️ Thời lượng (s):").pack(side="left", padx=(10, 5))
        ctk.CTkEntry(
            effects_frame, textvariable=self.merge_transition_duration_var, width=50
        ).pack(side="left")

        # ========== PROGRESS AND RUN ==========
        action_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        action_frame.grid(row=5, column=0, sticky="ew", pady=5)
        action_frame.grid_columnconfigure(0, weight=1)

        self.merge_progress_bar = ctk.CTkProgressBar(
            action_frame, variable=self.merge_progress_var, height=15, corner_radius=8
        )
        self.merge_progress_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.merge_progress_bar.set(0)

        self.merge_progress_label = ctk.CTkLabel(
            action_frame, text="Sẵn sàng", font=ctk.CTkFont(size=11)
        )
        self.merge_progress_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))

        self.merge_run_button = ctk.CTkButton(
            action_frame,
            text="🎬 Merge Videos",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40, corner_radius=8,
            fg_color="#1f7a1f",
            hover_color="#2a9a2a",
            command=self._merge_run
        )
        self.merge_run_button.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))

        # ========== LOG ==========
        merge_log_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        merge_log_frame.grid(row=6, column=0, sticky="nsew", pady=5)
        merge_log_frame.grid_columnconfigure(0, weight=1)
        merge_log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            merge_log_frame, text="📋 Log", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 3))

        self.merge_log_text = ctk.CTkTextbox(
            merge_log_frame, height=100, corner_radius=5,
            font=ctk.CTkFont(family="Consolas", size=10)
        )
        self.merge_log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(3, 10))

    # ========== MERGE CLIPS CALLBACKS ==========
    def _merge_add_videos(self) -> None:
        """Add videos to merge list."""
        filetypes = [
            ("Media files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv *.flv *.jpg *.jpeg *.png"),
            ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv *.flv"),
            ("Image files", "*.jpg *.jpeg *.png"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Chọn video để ghép", filetypes=filetypes)
        if not paths:
            return

        # Check if this is the first batch of videos (to auto-suggest output)
        was_empty = len(self.merge_video_files) == 0

        for p in paths:
            if p not in self.merge_video_files:
                self.merge_video_files.append(p)

        self._update_merge_listbox()

        # Auto-suggest output path if this was the first addition
        if was_empty and self.merge_video_files:
            first_video = self.merge_video_files[0]
            dir_path = os.path.dirname(first_video)
            # Suggest output name based on first video
            first_name = os.path.splitext(os.path.basename(first_video))[0]
            suggested_output = os.path.join(dir_path, f"{first_name}_merged.mp4")
            self.merge_output_path_var.set(suggested_output)

    def _update_merge_listbox(self) -> None:
        """Refresh the merge listbox display."""
        self.merge_listbox.delete(0, "end")
        for idx, path in enumerate(self.merge_video_files, start=1):
            filename = os.path.basename(path)
            self.merge_listbox.insert("end", f"{idx}. {filename}")

    def _merge_remove_selected(self) -> None:
        """Remove selected video from list."""
        selection = self.merge_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self.merge_video_files):
            self.merge_video_files.pop(index)
            self._update_merge_listbox()

    def _merge_clear_all(self) -> None:
        """Clear all videos from list."""
        self.merge_video_files.clear()
        self._update_merge_listbox()

    def _merge_move_up(self) -> None:
        """Move selected video up in the list."""
        selection = self.merge_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index > 0:
            # Swap with previous
            self.merge_video_files[index], self.merge_video_files[index - 1] = \
                self.merge_video_files[index - 1], self.merge_video_files[index]
            self._update_merge_listbox()
            self.merge_listbox.selection_set(index - 1)

    def _merge_move_down(self) -> None:
        """Move selected video down in the list."""
        selection = self.merge_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index < len(self.merge_video_files) - 1:
            # Swap with next
            self.merge_video_files[index], self.merge_video_files[index + 1] = \
                self.merge_video_files[index + 1], self.merge_video_files[index]
            self._update_merge_listbox()
            self.merge_listbox.selection_set(index + 1)

    def _on_drag_start(self, event) -> None:
        """Handle drag start for reordering."""
        index = self.merge_listbox.nearest(event.y)
        if 0 <= index < len(self.merge_video_files):
            self._drag_start_index = index
            self.merge_listbox.selection_clear(0, "end")
            self.merge_listbox.selection_set(index)

    def _on_drag_motion(self, event) -> None:
        """Handle drag motion for visual feedback."""
        if self._drag_start_index is None:
            return
        current_index = self.merge_listbox.nearest(event.y)
        if current_index != self._drag_start_index and 0 <= current_index < len(self.merge_video_files):
            # Move item
            item = self.merge_video_files.pop(self._drag_start_index)
            self.merge_video_files.insert(current_index, item)
            self._drag_start_index = current_index
            self._update_merge_listbox()
            self.merge_listbox.selection_set(current_index)

    def _on_drag_end(self, event) -> None:
        """Handle drag end."""
        self._drag_start_index = None

    def _merge_browse_output(self) -> None:
        """Browse for merge output file."""
        initial_dir = os.getcwd()
        if self.merge_video_files:
            initial_dir = os.path.dirname(self.merge_video_files[0])

        filetypes = [
            ("MP4 video", "*.mp4"),
            ("All files", "*.*"),
        ]
        path = filedialog.asksaveasfilename(
            title="Chọn nơi lưu video ghép",
            initialdir=initial_dir,
            defaultextension=".mp4",
            filetypes=filetypes,
        )
        if path:
            self.merge_output_path_var.set(path)

    def _merge_add_music(self) -> None:
        """Add music files to merge playlist."""
        filetypes = [
            ("Audio files", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Chọn nhạc nền", filetypes=filetypes)
        if not paths:
            return
        
        for p in paths:
            if p not in self.merge_music_files:
                self.merge_music_files.append(p)
                self.merge_music_listbox.insert("end", os.path.basename(p))

    def _merge_remove_music(self) -> None:
        """Remove selected music."""
        selection = self.merge_music_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if 0 <= idx < len(self.merge_music_files):
            self.merge_music_files.pop(idx)
            self.merge_music_listbox.delete(idx)

    def _merge_music_move_up(self) -> None:
        selection = self.merge_music_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if idx > 0:
            self.merge_music_files[idx], self.merge_music_files[idx-1] = self.merge_music_files[idx-1], self.merge_music_files[idx]
            self.merge_music_listbox.delete(idx-1)
            self.merge_music_listbox.insert(idx-1, os.path.basename(self.merge_music_files[idx-1]))
            self.merge_music_listbox.delete(idx+1)
            self.merge_music_listbox.insert(idx, os.path.basename(self.merge_music_files[idx]))
            self.merge_music_listbox.selection_set(idx-1)

    def _merge_music_move_down(self) -> None:
        selection = self.merge_music_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if idx < len(self.merge_music_files) - 1:
            self.merge_music_files[idx], self.merge_music_files[idx+1] = self.merge_music_files[idx+1], self.merge_music_files[idx]
            self.merge_music_listbox.delete(idx)
            self.merge_music_listbox.insert(idx, os.path.basename(self.merge_music_files[idx])) # Re-insert current at lower pos logic is tricky with delete.
            # Simpler update whole list
            self.merge_music_listbox.delete(0, "end")
            for p in self.merge_music_files:
                self.merge_music_listbox.insert("end", os.path.basename(p))
            self.merge_music_listbox.selection_set(idx+1)

    # --- Voice List Callbacks ---
    def _merge_add_voice(self) -> None:
        """Add voice files to merge playlist."""
        filetypes = [
            ("Audio files", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Chọn file giọng đọc", filetypes=filetypes)
        if not paths: return
        for p in paths:
            if p not in self.merge_voice_files:
                self.merge_voice_files.append(p)
                self.merge_voice_listbox.insert("end", os.path.basename(p))

    def _merge_remove_voice(self) -> None:
        selection = self.merge_voice_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if 0 <= idx < len(self.merge_voice_files):
            self.merge_voice_files.pop(idx)
            self.merge_voice_listbox.delete(idx)

    def _merge_voice_move_up(self) -> None:
        selection = self.merge_voice_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if idx > 0:
            self.merge_voice_files[idx], self.merge_voice_files[idx-1] = self.merge_voice_files[idx-1], self.merge_voice_files[idx]
            self.merge_voice_listbox.delete(idx-1)
            self.merge_voice_listbox.insert(idx-1, os.path.basename(self.merge_voice_files[idx-1]))
            self.merge_voice_listbox.delete(idx+1)
            self.merge_voice_listbox.insert(idx, os.path.basename(self.merge_voice_files[idx]))
            self.merge_voice_listbox.selection_set(idx-1)

    def _merge_voice_move_down(self) -> None:
        selection = self.merge_voice_listbox.curselection()
        if not selection: return
        idx = selection[0]
        if idx < len(self.merge_voice_files) - 1:
            self.merge_voice_files[idx], self.merge_voice_files[idx+1] = self.merge_voice_files[idx+1], self.merge_voice_files[idx]
            self.merge_voice_listbox.delete(0, "end")
            for p in self.merge_voice_files:
                self.merge_voice_listbox.insert("end", os.path.basename(p))
            self.merge_voice_listbox.selection_set(idx+1)

    def _on_merge_encoder_change(self, value: str) -> None:
        """Handle merge encoder selection change."""
        for key, (_, display, _) in self.ENCODER_OPTIONS.items():
            if display == value:
                self.merge_encoder_var.set(key)
                break

    def _on_merge_speed_change(self, value: str) -> None:
        """Handle merge speed preset selection change."""
        for key, (_, _, display) in self.SPEED_PRESETS.items():
            if display == value:
                self.merge_speed_preset_var.set(key)
                break

    def _merge_append_log(self, text: str) -> None:
        """Append text to merge log."""
        self.merge_log_text.insert("end", text + "\n")
        self.merge_log_text.see("end")
        self.update_idletasks()

    def _merge_update_progress(self, value: float, text: str = "") -> None:
        """Update merge progress bar and label."""
        self.merge_progress_var.set(value)
        if text:
            self.merge_progress_label.configure(text=text)
        self.update_idletasks()

    def _get_merge_encoder_config(self) -> tuple[str, str, int]:
        """Get encoder configuration for merge based on UI selections."""
        encoder = self.merge_encoder_var.get()
        speed_key = self.merge_speed_preset_var.get()

        if speed_key not in self.SPEED_PRESETS:
            speed_key = "balanced"

        preset, crf, _ = self.SPEED_PRESETS[speed_key]

        if encoder in ["h264_nvenc", "h264_qsv", "h264_amf"]:
            if speed_key == "balanced":
                return (encoder, "p4", 23)
            elif speed_key == "fast":
                return (encoder, "p2", 25)
            else:
                return (encoder, "p1", 28)
        else:
            return (encoder, preset, crf)

    def _merge_run(self) -> None:
        """Run the merge operation."""
        if not self.merge_video_files:
            messagebox.showerror("Error", "Vui lòng thêm video/ảnh để ghép.")
            return

        if len(self.merge_video_files) < 2:
            # Allow 1 file if loop/convert? But strictly 'merge' implies >= 2.
            # But maybe user wants to convert 1 image to video + music. Allow >= 1?
            # Existing logic was < 2. Let's keep it but maybe loose for images?
            # User said "Merge clip".
            if len(self.merge_video_files) < 2:
                messagebox.showerror("Error", "Cần ít nhất 2 file để ghép (hoặc dùng Video Length tab cho 1 file).")
                return

        output_path = self.merge_output_path_var.get().strip()
        if not output_path:
            messagebox.showerror("Error", "Vui lòng chọn nơi lưu file output.")
            return

        # Validate all input files exist
        for path in self.merge_video_files:
            if not os.path.isfile(path):
                messagebox.showerror("Error", f"File không tồn tại: {path}")
                return

        # Start processing
        self.merge_run_button.configure(state="disabled")
        self._merge_update_progress(0, "Đang xử lý...")

        # Gather main parameters
        trim_enabled = self.merge_trim_var.get()
        mute_source = self.merge_mute_var.get()
        music_files = self.merge_music_files.copy()
        voice_files = self.merge_voice_files.copy()
        
        mute_source = self.merge_mute_var.get()
        music_files = self.merge_music_files.copy()
        voice_files = self.merge_voice_files.copy()
        
        # Transition params
        transition_type = self.merge_transition_var.get()
        try:
            transition_dur = float(self.merge_transition_duration_var.get())
            if transition_dur < 0: raise ValueError
        except ValueError:
            transition_dur = 0.5
        
        try:
            image_duration = float(self.merge_image_duration_var.get())
            if image_duration <= 0: raise ValueError
        except ValueError:
            image_duration = 5.0

        thread = threading.Thread(
            target=self._merge_worker,
            args=(self.merge_video_files.copy(), output_path, trim_enabled, mute_source, 
                  music_files, voice_files, image_duration, transition_type, transition_dur),
            daemon=True,
        )
        thread.start()

    def _merge_worker(self, video_files: list[str], output_path: str, 
                      trim_enabled: bool, mute_source: bool, 
                      music_files: list[str], voice_files: list[str], 
                      image_duration: float, transition_type: str, transition_dur: float) -> None:
        """Worker thread for merging videos/images."""
        tmp_dir = None
        processed_files: list[str] = []

        try:
            self._merge_append_log("🎬 Bắt đầu ghép media...")
            self._merge_append_log(f"📁 Số lượng file: {len(video_files)}")
            
            # Resolve Random Transition
            actual_transition = transition_type
            if transition_type == "Random":
                import random
                choices = [t for t in self.TRANSITIONS if t not in ["None", "Random"]]
                actual_transition = random.choice(choices)
                self._merge_append_log(f"🎲 Random selected: {actual_transition}")
            
            self._merge_append_log(f"✨ Hiệu ứng: {actual_transition} ({transition_dur}s)")
            self._merge_append_log(f"✂️ Cut 1s đầu/cuối: {'BẬT' if trim_enabled else 'TẮT'}")
            
            # ... Log music/voice ...
            
            encoder, preset, crf = self._get_merge_encoder_config()
            self._merge_append_log(f"🔧 Encoder: {encoder} | Preset: {preset} | Quality: {crf}")

            # 1. Analyze inputs to determine target resolution/fps
            self._merge_update_progress(0.05, "Đang phân tích media...")
            target_width, target_height = 1920, 1080
            target_fps = 30.0
            
            # Find first video to reference
            ref_video = None
            for f in video_files:
                ext = os.path.splitext(f)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png']:
                    ref_video = f
                    break
            
            if ref_video:
                # Probe it
                try:
                    ffprobe = get_ffprobe_executable()
                    cmd = [
                        ffprobe, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate",
                        "-of", "csv=p=0", ref_video
                    ]
                    out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0).decode().strip()
                    parts = out.split(',')
                    if len(parts) >= 3:
                        target_width = int(parts[0])
                        target_height = int(parts[1])
                        fps_parts = parts[2].split('/')
                        if len(fps_parts) == 2:
                            target_fps = float(fps_parts[0]) / float(fps_parts[1])
                        else:
                            target_fps = float(parts[2])
                except Exception as e:
                    self._merge_append_log(f"⚠️ Không thể probe video {os.path.basename(ref_video)}, dùng default 1080p.")
            
            self._merge_append_log(f"🎯 Target Format: {target_width}x{target_height} @ {target_fps:.2f}fps")

            # Create temp directory
            base_dir = os.path.dirname(output_path) or os.getcwd()
            tmp_dir = tempfile.mkdtemp(prefix="merge_clips_", dir=base_dir)
            concat_file = os.path.join(tmp_dir, "concat_list.txt")

            # 2. Process segments (Trim, Loop Images, Normalize)
            self._merge_update_progress(0.1, "Đang xử lý từng segment...")
            
            for idx, path in enumerate(video_files):
                filename = os.path.basename(path)
                seg_out = os.path.join(tmp_dir, f"seg_{idx:03d}.mp4")
                
                # Check if image
                ext = os.path.splitext(path)[1].lower()
                is_image = ext in ['.jpg', '.jpeg', '.png']
                
                msg = f"Processing {idx+1}/{len(video_files)}: {filename}" + (" (Image)" if is_image else "")
                self._merge_append_log(msg)
                self._merge_update_progress(0.1 + (0.4 * idx / len(video_files)), msg)

                self._process_segment(
                    input_path=path,
                    output_path=seg_out,
                    is_image=is_image,
                    trim_enabled=trim_enabled,
                    mute_source=mute_source,
                    image_duration=image_duration,
                    width=target_width,
                    height=target_height,
                    fps=target_fps,
                    encoder_config=(encoder, preset, crf),
                    transition_type=actual_transition,
                    transition_dur=transition_dur
                )
                processed_files.append(seg_out)

            # 3. Concatenate (or Xfade)
            self._merge_update_progress(0.6, "Đang ghép (concatenation)...")
            
            # Decide: Fast Concat (Dip/None) or Xfade
            is_xfade = actual_transition not in ["None", "Fade Black", "Fade White"]
            
            concat_out = os.path.join(tmp_dir, "concat_result.mp4")
            
            if is_xfade:
                self._merge_append_log(f"🔄 Using Xfade: {actual_transition}")
                try:
                    self._merge_with_xfade(
                        processed_files, concat_out, actual_transition, transition_dur, 
                        target_width, target_height, target_fps, (encoder, preset, crf)
                    )
                except Exception as e:
                    self._merge_append_log(f"⚠️ Xfade failed completely: {e}")
                    self._merge_append_log("🔄 Falling back to standard concat (no transitions)...")
                    if os.path.exists(concat_out):
                        os.remove(concat_out)
                    is_xfade = False # Flag to fall through to else block

            if not is_xfade:
                # Standard Concat (Fast)
                # Create list file
                with open(concat_file, "w", encoding="utf-8") as f:
                    for p in processed_files:
                        escaped = os.path.abspath(p).replace("\\", "/").replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")

                cmd_concat = [
                    self.ffmpeg_executable, "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_file, "-c", "copy", concat_out
                ]
                subprocess.run(cmd_concat, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

            # 4. Add Music / Finalize
            self._merge_update_progress(0.8, "Đang finalize âm thanh...")
            
            final_inputs = ["-i", concat_out]
            # Track stream mapping
            # 0:v - Video
            # 0:a - Source Audio (if not muted)
            # Music might be next
            # Voice might be next
            
            stream_indices = {
                "source": 0,
                "music": -1,
                "voice": -1
            }
            next_input_idx = 1
            
            # --- Prepare Music ---
            if music_files:
                music_list_file = os.path.join(tmp_dir, "music_list.txt")
                with open(music_list_file, "w", encoding="utf-8") as f:
                    for m in music_files:
                        escaped = os.path.abspath(m).replace("\\", "/").replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                
                combined_music = os.path.join(tmp_dir, "combined_music.m4a")
                cmd_music = [
                    self.ffmpeg_executable, "-y", "-f", "concat", "-safe", "0",
                    "-i", music_list_file, "-c:a", "aac", "-b:a", "192k", "-vn", combined_music
                ]
                subprocess.run(cmd_music, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                
                # No Loop: Just add input
                final_inputs.extend(["-i", combined_music])
                stream_indices["music"] = next_input_idx
                next_input_idx += 1
                
            # --- Prepare Voice ---
            if voice_files:
                voice_list_file = os.path.join(tmp_dir, "voice_list.txt")
                with open(voice_list_file, "w", encoding="utf-8") as f:
                    for v in voice_files:
                        escaped = os.path.abspath(v).replace("\\", "/").replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                
                combined_voice = os.path.join(tmp_dir, "combined_voice.m4a")
                cmd_voice = [
                    self.ffmpeg_executable, "-y", "-f", "concat", "-safe", "0",
                    "-i", voice_list_file, "-c:a", "aac", "-b:a", "192k", "-vn", combined_voice
                ]
                subprocess.run(cmd_voice, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                
                # No Loop
                final_inputs.extend(["-i", combined_voice])
                stream_indices["voice"] = next_input_idx
                next_input_idx += 1
            
            # --- Mixing ---
            audio_streams_to_mix = []
            
            if not mute_source:
                 audio_streams_to_mix.append(f"{stream_indices['source']}:a")
            
            if stream_indices["music"] != -1:
                audio_streams_to_mix.append(f"{stream_indices['music']}:a")
                
            if stream_indices["voice"] != -1:
                audio_streams_to_mix.append(f"{stream_indices['voice']}:a")
                
            maps = ["-map", "0:v"] # Always map video
            filter_complex = []
            
            if not audio_streams_to_mix:
                 # No audio at all (muted, no music, no voice)
                 pass
            elif len(audio_streams_to_mix) == 1:
                # Just one stream, map it directly
                maps.extend(["-map", audio_streams_to_mix[0], "-shortest"])
            else:
                # Mix multiple streams
                mix_inputs = "".join([f"[{s}]" for s in audio_streams_to_mix])
                filter_complex.append(f"{mix_inputs}amix=inputs={len(audio_streams_to_mix)}:duration=first[aout]")
                maps.extend(["-map", "[aout]"])

            cmd_final = [
                self.ffmpeg_executable, "-y",
                *final_inputs
            ]
            
            if filter_complex:
                cmd_final.extend(["-filter_complex", "".join(filter_complex)])
            
            cmd_final.extend(maps)
            cmd_final.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])
            cmd_final.append(output_path)
            
            self._merge_append_log("💾 Saving final output...")
            subprocess.run(cmd_final, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

            self._merge_append_log("✅ Hoàn thành!")
            self._merge_update_progress(1.0, "✅ Hoàn thành!")
            messagebox.showinfo("Thành công", "Video đã được ghép thành công!")

        except Exception as exc:
            self._merge_append_log(f"❌ Lỗi: {exc}")
            import traceback
            traceback.print_exc()
            self._merge_update_progress(0, "❌ Lỗi")
            messagebox.showerror("Error", f"Lỗi khi ghép video: {exc}")
        finally:
            self.merge_run_button.configure(state="normal")
            # Cleanup
            try:
                if tmp_dir and os.path.exists(tmp_dir):
                    import shutil
                    shutil.rmtree(tmp_dir)
            except Exception:
                pass

    def _process_segment(self, input_path: str, output_path: str, is_image: bool,
                         trim_enabled: bool, mute_source: bool, image_duration: float,
                         width: int, height: int, fps: float, encoder_config: tuple,
                         transition_type: str, transition_dur: float) -> None:
        """Video processing unit with fallback for HW failures."""
        
        # Inner function to build command (keeps things DRY for retry)
        def build_cmd(curr_config):
            enc, pre, q = curr_config
            vf_filters = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                f"fps={fps}",
                "format=yuv420p"
            ]
            
            # Handle Fade Black/White
            segment_duration = image_duration
            if not is_image:
                 input_d = self._get_media_duration(input_path)
                 if trim_enabled and input_d > 2.0:
                     segment_duration = input_d - 2.0
                 else:
                     segment_duration = input_d
            
            if transition_type in ["Fade Black", "Fade White"]:
                color = "white" if "White" in transition_type else "black"
                # Fade In Start
                vf_filters.append(f"fade=t=in:st=0:d={transition_dur}:color={color}")
                # Fade Out End
                if segment_duration > transition_dur:
                     start_fade_out = segment_duration - transition_dur
                     vf_filters.append(f"fade=t=out:st={start_fade_out}:d={transition_dur}:color={color}")
            
            cmd = [self.ffmpeg_executable, "-y"]
            
            if is_image:
                cmd.extend(["-loop", "1", "-i", input_path])
                cmd.extend(["-t", str(image_duration)])
            else:
                start_offset = 0.0
                duration = None
                if trim_enabled:
                    input_dur = self._get_media_duration(input_path)
                    if input_dur > 2.0:
                        start_offset = 1.0
                        duration = input_dur - 2.0
                    else:
                        self._merge_append_log(f"⚠️ Clip too short to trim: {os.path.basename(input_path)}")
                
                if start_offset > 0:
                    cmd.extend(["-ss", str(start_offset)])
                
                cmd.extend(["-i", input_path])
                
                if duration is not None:
                    cmd.extend(["-t", str(duration)])

            # Encoder args
            if enc == "libx264":
                cmd.extend(["-c:v", "libx264", "-preset", pre, "-crf", str(q)])
            elif enc == "h264_nvenc":
                cmd.extend(["-c:v", "h264_nvenc", "-preset", pre, "-cq", str(q), "-rc", "vbr"])
            elif enc == "h264_qsv":
                cmd.extend(["-c:v", "h264_qsv", "-preset", pre, "-global_quality", str(q)])
            elif enc == "h264_amf":
                 cmd.extend(["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_latency"])

            cmd.extend(["-vf", ",".join(vf_filters)])

            if mute_source:
                 cmd.append("-an")
            else:
                if is_image:
                    pass 
                else:
                    cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            if is_image and not mute_source:
                 cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest"])
                 cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            cmd.extend(["-threads", "0"])
            cmd.append(output_path)
            return cmd

        # Try 1: Use requested encoder
        try:
            cmd = build_cmd(encoder_config)
            # self._merge_append_log(f"Running segment: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except subprocess.CalledProcessError as e:
            # ... (Retry logic, no change needed here actually but context check)
            enc_name = encoder_config[0]
            if enc_name != "libx264":
                self._merge_append_log(f"⚠️ Retrying with CPU...")
                fallback_config = ("libx264", "veryfast", 23) 
                cmd_fallback = build_cmd(fallback_config)
                subprocess.run(cmd_fallback, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            else:
                self._merge_append_log(f"❌ FFmpeg error: {e}")
                raise e

    def _merge_with_xfade(self, inputs: list[str], output_path: str, transition_type: str, 
                          duration: float, width: int, height: int, fps: float, 
                          encoder_config: tuple) -> None:
        """Merge videos using complex xfade filter."""
        # Need exact duration of each input to calculate offsets
        offsets = []
        cum_duration = 0.0
        
        # Map transition name to ffmpeg xfade transition
        # "Crossfade" -> "fade"? "distance"? 'fade' is technically mix. 'dissolve' is common.
        # xfade supports: fade, wipeleft, wiperight, slideleft, slideright, etc.
        t_map = {
            "Crossfade": "fade",
            "Wipe Left": "wipeleft",
            "Wipe Right": "wiperight",
            "Slide Left": "slideleft",
            "Slide Right": "slideright"
        }
        xfade_trans = t_map.get(transition_type, "fade")
        
        # Probe durations
        real_inputs = []
        for inp in inputs:
            try:
                d = self._get_media_duration(inp)
                real_inputs.append((inp, d))
            except Exception:
                continue
                
        if not real_inputs: raise ValueError("No inputs for xfade")
        
        # Calculate offsets
        # offset 0 = 0 (implicitly)
        # offset 1 = dur 0 - trans_dur
        # offset 2 = offset 1 + dur 1 - trans_dur
        
        curr_offset = 0.0
        for i in range(len(real_inputs) - 1): # Last clip doesn't have an offset calculation for next
             dur = real_inputs[i][1]
             # Next clip starts at:
             next_start = curr_offset + dur - duration
             offsets.append(next_start)
             curr_offset = next_start
        
        # Build Filter Graph
        # [0][1]xfade=...[v1];[v1][2]xfade...[v2]...
        fg = []
        
        # Inputs
        cmd = [self.ffmpeg_executable, "-y"]
        for inp, _ in real_inputs:
            cmd.extend(["-i", inp])
            
        last_v_label = "0:v"
        # Since inputs are normalized, we assume audio matches.
        # Xfade only affects video. Audio needs 'acrossfade' for crossfade.
        # Or simple mix. 'acrossfade' is better but complex graph.
        # For simplicity, let's use amix (already done in main flow? No, that's music).
        # We need to mix the audio of clips.
        # For simple 'fade' transition, we want audio crossfade.
        # Let's try simple audio concat first? No, gaps.
        # We will use 'acrossfade' for audio parallel to xfade.
        
        last_a_label = "0:a"
        
        for i in range(1, len(real_inputs)):
            # Video Xfade
            next_v_label = f"v{i}"
            fg.append(f"[{last_v_label}][{i}:v]xfade=transition={xfade_trans}:duration={duration}:offset={offsets[i-1]}[{next_v_label}]")
            last_v_label = next_v_label
            
            # Audio Crossfade
            next_a_label = f"a{i}"
            fg.append(f"[{last_a_label}][{i}:a]acrossfade=d={duration}[{next_a_label}]")
            last_a_label = next_a_label
            
        # FORCE PIXEL FORMAT TO YUV420P AFTER XFADE
        # This fixes 4294967274 crashes where complex filters output incompatible formats
        fg.append(f"[{last_v_label}]format=yuv420p[vout]")
        last_v_label = "vout"
            
        cmd.extend(["-filter_complex", ";".join(fg)])
        cmd.extend(["-map", f"[{last_v_label}]", "-map", f"[{last_a_label}]"])
        
        # Encoder args
        # Reuse logic... simplify for now, always re-encode
        # Since Xfade is failing, let's be VERY conservative:
        # 1. Use libx264 (CPU)
        # 2. Use 1 thread
        
        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])
        
        # Audio
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        cmd.extend(["-threads", "1"]) # Thread limit for stability
        cmd.append(output_path)
        
        # self._merge_append_log(f"Running Xfade: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except subprocess.CalledProcessError as e:
             # Retry logic is redundant if we're already being conservative, 
             # but let's keep it simple: if this fails, we just propagate up 
             # and let _merge_worker catch it to fallback to Concat.
             self._merge_append_log(f"❌ Xfade Error: {e}")
             raise e

    def _check_can_fast_concat(self, video_files: list[str]) -> bool:
        """Check if videos can be concatenated without re-encoding."""
        try:
            ffprobe = get_ffprobe_executable()
            first_info = None

            for path in video_files:
                cmd = [
                    ffprobe, "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height",
                    "-of", "csv=p=0",
                    path
                ]
                result = subprocess.run(
                    cmd, capture_output=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                info = result.stdout.decode().strip()

                if first_info is None:
                    first_info = info
                elif info != first_info:
                    return False

            return True
        except Exception:
            return False

    def _merge_fast_concat(self, video_files: list[str], output_path: str, concat_file: str) -> None:
        """Fast concatenation using stream copy."""
        self._merge_update_progress(0.3, "Đang ghép (fast mode)...")

        # Create concat file
        with open(concat_file, "w", encoding="utf-8") as f:
            for path in video_files:
                escaped = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            self.ffmpeg_executable,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]

        self._merge_append_log("🔄 Running: " + " ".join(cmd))
        subprocess.run(cmd, check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    def _merge_reencode(self, video_files: list[str], output_path: str, concat_file: str,
                        encoder: str, preset: str, crf: int) -> None:
        """Concatenation with re-encoding for incompatible videos."""
        self._merge_update_progress(0.2, "Đang ghép (re-encode)...")

        # Create concat file
        with open(concat_file, "w", encoding="utf-8") as f:
            for path in video_files:
                escaped = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        # Build encoding args
        encode_args = ["-threads", "0"]

        if encoder == "libx264":
            encode_args.extend(["-c:v", "libx264", "-preset", preset, "-crf", str(crf)])
        elif encoder == "h264_nvenc":
            encode_args.extend(["-c:v", "h264_nvenc", "-preset", preset, "-cq", str(crf), "-rc", "vbr"])
        elif encoder == "h264_qsv":
            encode_args.extend(["-c:v", "h264_qsv", "-preset", preset, "-global_quality", str(crf)])
        elif encoder == "h264_amf":
            quality = "speed" if preset in ["p1", "p2"] else "balanced"
            encode_args.extend(["-c:v", "h264_amf", "-quality", quality, "-rc", "vbr_latency",
                               "-qp_i", str(crf), "-qp_p", str(crf)])

        encode_args.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd = [
            self.ffmpeg_executable,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            *encode_args,
            output_path
        ]

        self._merge_append_log("🔄 Running: " + " ".join(cmd))
        subprocess.run(cmd, check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            subprocess.run(cmd, check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
            subprocess.run(cmd_copy, check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
        subprocess.run(cmd_reencode, check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            subprocess.run(cmd_copy, check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
        subprocess.run(cmd_reencode, check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=30,
                                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
            subprocess.run(cmd_mux, check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
                subprocess.run(cmd_copy, check=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
        subprocess.run(cmd_reencode, check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

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
            subprocess.run(cmd, check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
