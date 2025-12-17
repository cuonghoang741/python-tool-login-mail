import math
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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


class VideoLengthTool(tk.Tk):
    """
    Simple GUI tool to multiply video length using ffmpeg.

    - Mode 1: multiply length by N times
    - Mode 2: loop until target duration, then cut at that duration

    Requirements:
      - ffmpeg installed, OR ffmpeg.exe placed next to the .exe / script
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Video Length Multiplier")
        self.geometry("800x750")
        self.resizable(False, False)

        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()

        self.mode_var = tk.StringVar(value="factor")
        self.factor_var = tk.StringVar(value="2")
        self.target_duration_var = tk.StringVar(value="300")

        # Audio playlist (ordered)
        self.audio_files: list[str] = []

        # Video output options
        self.resolution_var = tk.StringVar(value="")  # Empty = keep original
        self.fps_var = tk.StringVar()

        self.ffmpeg_executable = get_ffmpeg_executable()

        self._build_ui()

    # UI BUILDING
    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 8}

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Input file
        input_frame = ttk.LabelFrame(main_frame, text="Input video")
        input_frame.pack(fill="x", **padding)

        ttk.Label(input_frame, text="File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        input_entry = ttk.Entry(input_frame, textvariable=self.input_path_var, width=70)
        input_entry.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_input).grid(
            row=0, column=2, padx=5, pady=5
        )
        input_frame.columnconfigure(1, weight=1)

        # Output file
        output_frame = ttk.LabelFrame(main_frame, text="Output video")
        output_frame.pack(fill="x", **padding)

        ttk.Label(output_frame, text="File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var, width=70)
        output_entry.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_output).grid(
            row=0, column=2, padx=5, pady=5
        )
        output_frame.columnconfigure(1, weight=1)

        # Audio playlist
        audio_frame = ttk.LabelFrame(main_frame, text="Audio tracks (optional)")
        audio_frame.pack(fill="both", expand=False, **padding)

        ttk.Label(
            audio_frame,
            text="Audio files will be played in order from top to bottom and looped to fill the video duration.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=3)

        self.audio_listbox = tk.Listbox(audio_frame, height=5, selectmode=tk.MULTIPLE)
        self.audio_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        btn_add_audio = ttk.Button(audio_frame, text="Add audio files...", command=self.add_audio_files)
        btn_add_audio.grid(row=2, column=0, sticky="w", padx=5, pady=5)

        btn_remove_audio = ttk.Button(
            audio_frame,
            text="Remove selected",
            command=self.remove_selected_audio,
        )
        btn_remove_audio.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        audio_frame.columnconfigure(0, weight=1)
        audio_frame.rowconfigure(1, weight=1)

        # Mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Mode")
        mode_frame.pack(fill="x", **padding)

        factor_radio = ttk.Radiobutton(
            mode_frame,
            text="Multiply length by factor (x times)",
            variable=self.mode_var,
            value="factor",
        )
        factor_radio.grid(row=0, column=0, sticky="w", padx=5, pady=3)

        ttk.Label(mode_frame, text="Factor (x):").grid(row=0, column=1, sticky="e", padx=5, pady=3)
        factor_entry = ttk.Entry(mode_frame, textvariable=self.factor_var, width=8)
        factor_entry.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        target_radio = ttk.Radiobutton(
            mode_frame,
            text="Loop until target duration (then cut)",
            variable=self.mode_var,
            value="target",
        )
        target_radio.grid(row=1, column=0, sticky="w", padx=5, pady=3)

        ttk.Label(mode_frame, text="Target duration:").grid(
            row=1, column=1, sticky="e", padx=5, pady=3
        )
        target_entry = ttk.Entry(mode_frame, textvariable=self.target_duration_var, width=12)
        target_entry.grid(row=1, column=2, sticky="w", padx=5, pady=3)

        ttk.Label(
            mode_frame,
            text="Format: SS or MM:SS or HH:MM:SS (e.g. 300, 05:00, 00:05:00)",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=3)

        mode_frame.columnconfigure(0, weight=1)

        # Video options (resolution / fps)
        video_opts_frame = ttk.LabelFrame(main_frame, text="Video options (optional)")
        video_opts_frame.pack(fill="x", **padding)

        ttk.Label(video_opts_frame, text="Resolution:").grid(
            row=0,
            column=0,
            sticky="e",
            padx=5,
            pady=3,
        )
        resolution_combo = ttk.Combobox(
            video_opts_frame,
            textvariable=self.resolution_var,
            width=15,
            state="readonly",
            values=["", "2160p (4K)", "1440p (2K)", "1080p (Full HD)", "720p (HD)", "480p (SD)", "360p", "240p"],
        )
        resolution_combo.grid(row=0, column=1, sticky="w", padx=2, pady=3)

        ttk.Label(
            video_opts_frame,
            text="(select resolution or leave empty to keep original)",
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=5, pady=3)

        ttk.Label(video_opts_frame, text="FPS:").grid(
            row=2,
            column=0,
            sticky="e",
            padx=5,
            pady=3,
        )
        fps_entry = ttk.Entry(video_opts_frame, textvariable=self.fps_var, width=8)
        fps_entry.grid(row=2, column=1, sticky="w", padx=2, pady=3)

        ttk.Label(
            video_opts_frame,
            text="(leave empty to keep original fps)",
        ).grid(row=2, column=2, columnspan=3, sticky="w", padx=5, pady=3)

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", **padding)

        self.run_button = ttk.Button(button_frame, text="Generate output video", command=self.run)
        self.run_button.pack(side="right")

        # Log / status
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(fill="both", expand=True, **padding)

        self.log_text = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    # UI CALLBACKS
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
                self.audio_listbox.insert("end", p)

    def remove_selected_audio(self) -> None:
        selection = list(self.audio_listbox.curselection())
        if not selection:
            return
        # Remove from bottom to top to keep indices valid
        for index in reversed(selection):
            path = self.audio_listbox.get(index)
            if path in self.audio_files:
                self.audio_files.remove(path)
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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
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

    # CORE LOGIC
    def run(self) -> None:
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()

        if not input_path:
            messagebox.showerror("Error", "Please select an input video file.")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("Error", "Input file does not exist.")
            return
        if not output_path:
            messagebox.showerror("Error", "Please select an output video file.")
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
                desc = f"Multiply length by factor x{factor}"
            else:
                duration_text = self.target_duration_var.get().strip()
                target_seconds = parse_duration_to_seconds(duration_text)
                if target_seconds <= 0:
                    raise ValueError
                desc = f"Loop until target duration {target_seconds} seconds"
        except ValueError:
            if mode == "factor":
                messagebox.showerror("Error", "Factor must be a positive integer.")
            else:
                messagebox.showerror(
                    "Error",
                    "Invalid target duration. Use SS, MM:SS or HH:MM:SS (e.g. 300, 05:00, 00:05:00).",
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
                "Invalid fps. FPS must be a positive number.",
            )
            return

        self.append_log(f"Input: {input_path}")
        self.append_log(f"Output: {output_path}")
        self.append_log(f"Mode: {desc}")
        if self.audio_files:
            self.append_log(f"Audio tracks: {len(self.audio_files)} file(s)")
            for idx, path in enumerate(self.audio_files, start=1):
                self.append_log(f"  {idx}. {path}")
        if width or height or fps:
            res_str = f"{width}x{height}" if width and height else "keep"
            self.append_log(
                f"Video options - resolution: {res_str}, fps: {fps or 'keep'}",
            )
        self.append_log(f"Using ffmpeg executable: {self.ffmpeg_executable}")
        self.append_log("Starting ffmpeg job...")

        # Decide whether to use simple video-only pipeline
        use_advanced = bool(self.audio_files or width or height or fps)

        # Determine target duration (in seconds) for advanced pipeline
        if use_advanced and mode == "factor":
            try:
                base_duration = self._get_media_duration(input_path)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(
                    "Error",
                    f"Failed to get input video duration (required for factor mode with audio/options): {exc}",
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
            self.append_log("Done.")
            messagebox.showinfo("Success", "Output video created successfully.")
        except FileNotFoundError:
            self.append_log("Error: ffmpeg not found. Make sure ffmpeg is available.")
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
            self.append_log("ffmpeg failed with error code: %s" % exc.returncode)
            self.append_log(str(exc))
            messagebox.showerror("Error", "ffmpeg failed. Please check the log for details.")
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"Unexpected error: {exc}")
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
            self.append_log("Running ffmpeg (copy only)...")
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

        self.append_log("Running ffmpeg (copy mode)...")
        self.append_log(" ".join(cmd_copy))
        try:
            subprocess.run(cmd_copy, check=True)
            return
        except subprocess.CalledProcessError:
            self.append_log("Copy mode failed, retrying with re-encode...")

        # Fallback: re-encode to ensure compatibility
        cmd_reencode = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            str(loop_count),
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_path,
        ]
        self.append_log("Running ffmpeg (re-encode mode)...")
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
        self.append_log("Running ffmpeg (copy mode, target duration)...")
        self.append_log(" ".join(cmd_copy))
        try:
            subprocess.run(cmd_copy, check=True)
            return
        except subprocess.CalledProcessError:
            self.append_log("Copy mode failed, retrying with re-encode...")

        cmd_reencode = [
            self.ffmpeg_executable,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            input_path,
            "-t",
            str(target_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_path,
        ]
        self.append_log("Running ffmpeg (re-encode mode, target duration)...")
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
        self.append_log("Running ffprobe: " + " ".join(cmd))
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
            self.append_log(f"Error: ffprobe not found at: {ffprobe}")
            raise FileNotFoundError(
                f"ffprobe not found. Please ensure ffprobe.exe is in the same folder as ffmpeg.exe or in PATH."
            ) from None
        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            self.append_log(f"ffprobe error: {error_msg}")
            raise RuntimeError(f"ffprobe failed: {error_msg}") from exc
        except ValueError as exc:
            raise exc
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"Unexpected error getting duration: {exc}")
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
        self.append_log(f"Using temporary directory: {tmp_dir}")

        tmp_video = os.path.join(tmp_dir, "tmp_video.mp4")
        tmp_audio = os.path.join(tmp_dir, "tmp_audio.m4a")

        try:
            # 1) Build video track
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
                self._build_audio_track(
                    audio_files=self.audio_files,
                    tmp_audio=tmp_audio,
                    target_seconds=target_seconds,
                )
                # 3) Mux video + audio
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
                cmd_mux = [
                    self.ffmpeg_executable,
                    "-y",
                    "-i",
                    tmp_video,
                    "-c",
                    "copy",
                    output_path,
                ]

            self.append_log("Muxing final output...")
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
            self.append_log("Building video track (copy mode, video only)...")
            self.append_log(" ".join(cmd_copy))
            try:
                subprocess.run(cmd_copy, check=True)
                return
            except subprocess.CalledProcessError:
                self.append_log("Copy mode for video track failed, retrying with re-encode...")

        # Re-encode video
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
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            tmp_video,
        ]
        self.append_log("Building video track (re-encode mode)...")
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
        self.append_log("Building audio track from playlist...")
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



