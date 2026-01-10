import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import json
import time
import threading
import random
import re
from typing import List, Dict, Any

import requests
from openpyxl import Workbook

try:
    import google.generativeai as _genai_sdk
    _GENAI_IMPORT_ERROR = None
except Exception as exc:  # capture grpc/cygrpc errors too
    _genai_sdk = None
    _GENAI_IMPORT_ERROR = exc


class _RestResponse:
    def __init__(self, text: str):
        self.text = text


class _GeminiRestClient:
    """Fallback client that talks to Gemini REST API directly."""

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.session = requests.Session()

    def generate_content(self, prompt: str):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        resp = self.session.post(url, params={"key": self.api_key}, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text_chunks = []
        for candidate in data.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                if "text" in part:
                    text_chunks.append(part["text"])
            if text_chunks:
                break
        text = "\n".join(text_chunks).strip()
        return _RestResponse(text)


class StoryPromptGenerator:
    def __init__(self, parent_frame, ui_callbacks=None):
        self.parent_frame = parent_frame
        self.ui_callbacks = ui_callbacks or {}
        
        # Gemini API configuration: list of keys, random pick per chat
        self.gemini_api_keys = [
            'AIzaSyD4pXfYEUNqWYOkAdpw7vNqsmoDdASwewk',
            'AIzaSyCmY11OuoBc9C92PHssIp5wx_7pid-kgUg',
            'AIzaSyDQzovP1l0_j9NEVapDz7TrMKfiVKpab1Q',
            'AIzaSyAhdS1h96roE3GnvJOfGPF50t8sLnyyXB8',
            'AIzaSyAH1dXX0demoy6o1CNzP6Ojf5u6yac-Ndo'
        ]
        self.gemini_api_key = None
        self.model = None
        self.model_backend = None  # 'sdk' or 'rest'
        self.last_setup_error = None
        self._setup_gemini()
        
        # UI state
        self.is_generating = False
        self.api_key_mode = tk.StringVar(value="default")  # 'default' or 'custom'
        self.custom_api_key_var = tk.StringVar(value="")

        # Load cached settings (nếu có) trước khi build UI
        self._load_settings()

        # Tự động lưu lại khi người dùng thay đổi mode hoặc key
        try:
            self.api_key_mode.trace_add("write", lambda *args: self._save_settings())
            self.custom_api_key_var.trace_add("write", lambda *args: self._save_settings())
        except Exception:
            # Nếu trace_add không khả dụng trên version Tk, vẫn an toàn bỏ qua
            pass

        self._build_ui()
    
    # ===== Settings (cache) helpers =====
    def _get_ui_settings_path(self) -> str:
        """Trả về đường dẫn file ui_settings.json ở thư mục gốc project."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_dir, "ui_settings.json")
        except Exception:
            # Fallback: dùng current working directory
            return os.path.join(os.getcwd(), "ui_settings.json")

    def _load_settings(self):
        """Load cache cho lựa chọn API key (mode + custom key) từ ui_settings.json nếu có."""
        try:
            settings_path = self._get_ui_settings_path()
            if not os.path.exists(settings_path):
                return
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            mode = data.get("flow_story_api_key_mode")
            if mode in ("default", "custom"):
                self.api_key_mode.set(mode)
            custom_key = data.get("flow_story_custom_api_key")
            if isinstance(custom_key, str):
                self.custom_api_key_var.set(custom_key)
        except Exception as e:
            print(f"Failed to load flow story settings: {e}")

    def _save_settings(self):
        """Lưu cache lựa chọn API key (mode + custom key) vào ui_settings.json."""
        try:
            settings_path = self._get_ui_settings_path()
            data = {}
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    # Nếu file hỏng, ghi đè bằng dict mới
                    data = {}

            data["flow_story_api_key_mode"] = self.api_key_mode.get()
            data["flow_story_custom_api_key"] = self.custom_api_key_var.get()

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save flow story settings: {e}")

    def _setup_gemini(self, api_key: str = None):
        """Initialize Gemini API.
        
        - Nếu api_key được truyền vào: dùng đúng key đó (chế độ custom).
        - Nếu không: lấy random từ danh sách self.gemini_api_keys (chế độ default).
        """
        try:
            if api_key:
                self.gemini_api_key = api_key
            else:
                if not self.gemini_api_keys:
                    raise ValueError("No Gemini API keys configured")
                self.gemini_api_key = random.choice(self.gemini_api_keys)

            if _genai_sdk is not None:
                _genai_sdk.configure(api_key=self.gemini_api_key)
                self.model = _genai_sdk.GenerativeModel('gemini-2.5-pro')
                self.model_backend = "sdk"
            else:
                # Fallback to REST client if SDK is unavailable (e.g., missing cygrpc)
                self.model = _GeminiRestClient(self.gemini_api_key, 'gemini-2.5-pro')
                self.model_backend = "rest"
            self.last_setup_error = None
        except Exception as e:
            print(f"Failed to setup Gemini API: {e}")
            self.model = None
            self.model_backend = None
            self.last_setup_error = e
    
    def _build_ui(self):
        """Build the story prompt generation UI"""
        # Main container
        main_frame = ttk.Frame(self.parent_frame, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        self.parent_frame.columnconfigure(0, weight=1)
        self.parent_frame.rowconfigure(0, weight=1)
        
        # Title
        title = ttk.Label(main_frame, text="📚 All Story Prompts Generator", 
                         font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=tk.W)

        # Two-column layout: left (inputs & actions), right (results)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E), padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=(10, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        # Story input section (left)
        story_frame = ttk.LabelFrame(left_frame, text="📖 Nhập câu chuyện", padding="15")
        story_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        story_frame.configure(style='Card.TLabelframe')
        story_frame.columnconfigure(0, weight=1)
        
        ttk.Label(story_frame, text="Mô tả câu chuyện:", 
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        
        self.story_text = scrolledtext.ScrolledText(story_frame, height=8, wrap=tk.WORD,
                                                   bg='#1B222C', fg='#EAECEF', 
                                                   insertbackground='#EAECEF',
                                                   highlightthickness=1, 
                                                   highlightbackground='#2A2F3A')
        self.story_text.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        
        # Example story
        example_story = """Một câu chuyện về một chú mèo tên Whiskers sống trong một ngôi nhà nhỏ bên bờ biển. 
Whiskers thích đi dạo trên bãi biển vào buổi sáng và ngắm mặt trời mọc. 
Một ngày nọ, chú phát hiện ra một chiếc thuyền cũ bị mắc kẹt trên đá và quyết định khám phá nó. 
Trong chiếc thuyền, chú tìm thấy một bản đồ kho báu và bắt đầu cuộc phiêu lưu tìm kiếm kho báu cùng với những người bạn động vật khác."""
        
        self.story_text.insert("1.0", example_story)
        
        # Configuration section (left)
        config_frame = ttk.LabelFrame(left_frame, text="⚙️ Cấu hình", padding="15")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        config_frame.configure(style='Card.TLabelframe')
        
        # Number of prompts
        ttk.Label(config_frame, text="Số lượng prompt muốn tạo:", 
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        
        self.num_prompts = tk.StringVar(value="10")
        prompts_spinbox = ttk.Spinbox(config_frame, from_=1, to=100, textvariable=self.num_prompts, width=10)
        prompts_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 8))
        
        # Story style
        ttk.Label(config_frame, text="Phong cách câu chuyện:", 
                 font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        
        self.story_style = ttk.Combobox(config_frame, values=[
            "Hành động phiêu lưu",
            "Tình cảm lãng mạn", 
            "Khoa học viễn tưởng",
            "Kinh dị bí ẩn",
            "Hài hước vui nhộn",
            "Cổ tích thần thoại",
            "Tự nhiên hoang dã",
            "Thể thao năng động"
        ], state="readonly", width=20)
        self.story_style.set("Hành động phiêu lưu")
        self.story_style.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(8, 0))

        # Video style
        ttk.Label(config_frame, text="Loại video (Style):", 
                 font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        
        self.video_style = ttk.Combobox(config_frame, values=[
            "Hoạt hình 2D",
            "Hoạt hình 3D", 
            "Stop motion",
            "Live-action (phim người thật)",
            "Motion graphics",
            "Video kỹ xảo (VFX)"
        ], state="readonly", width=25)
        self.video_style.set("Hoạt hình 3D")
        self.video_style.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=(8, 0))

        # API key mode (default vs custom)
        ttk.Label(config_frame, text="Gemini API key:", 
                 font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=(8, 0))

        api_key_mode_frame = ttk.Frame(config_frame)
        api_key_mode_frame.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=(8, 0))

        self.api_key_default_rb = ttk.Radiobutton(
            api_key_mode_frame,
            text="Dùng key mặc định",
            value="default",
            variable=self.api_key_mode,
            command=self._on_api_key_mode_change
        )
        self.api_key_default_rb.grid(row=0, column=0, sticky=tk.W)

        self.api_key_custom_rb = ttk.Radiobutton(
            api_key_mode_frame,
            text="Tự nhập key",
            value="custom",
            variable=self.api_key_mode,
            command=self._on_api_key_mode_change
        )
        self.api_key_custom_rb.grid(row=1, column=0, sticky=tk.W, pady=(2, 0))

        self.custom_api_key_entry = ttk.Entry(api_key_mode_frame, textvariable=self.custom_api_key_var, width=35)
        self.custom_api_key_entry.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        # Áp trạng thái enable/disable theo mode đã load
        self._on_api_key_mode_change()
        
        # Action buttons (left)
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        # two columns layout for buttons
        try:
            button_frame.columnconfigure(0, weight=1)
            button_frame.columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.generate_btn = ttk.Button(button_frame, text="🎬 Tạo Story Prompts", 
                                     command=self._generate_story_prompts, 
                                     style='Accent.TButton')
        self.generate_btn.grid(row=0, column=0, padx=(0, 10), sticky=(tk.W, tk.E))
        
        
        self.export_btn = ttk.Button(button_frame, text="📥 Export Excel", 
                                   command=self._export_to_excel, 
                                   style='Secondary.TButton')
        self.export_btn.grid(row=0, column=1, padx=(0, 0), sticky=(tk.W, tk.E))
        
        self.clear_btn = ttk.Button(button_frame, text="🗑️ Xóa tất cả", 
                                   command=self._clear_all, 
                                   style='Secondary.TButton')
        self.clear_btn.grid(row=1, column=0, padx=(0, 10), pady=(8, 0), sticky=(tk.W, tk.E))
        
        # Execute button to transfer to execute tab
        self.execute_btn = ttk.Button(button_frame, text="🚀 Execute", 
                                     command=self._execute_story_prompts, 
                                     style='Accent.TButton',
                                     state='disabled')
        self.execute_btn.grid(row=1, column=1, padx=(0, 0), pady=(8, 0), sticky=(tk.W, tk.E))
        
        # Status (below left panel)
        self.status_label = ttk.Label(left_frame, text="✅ Sẵn sàng tạo story prompts", 
                                    style='Success.TLabel')
        self.status_label.grid(row=3, column=0, sticky=tk.W)
        
        # Character prompts edit section (right, below results)
        character_frame = ttk.LabelFrame(right_frame, text="👤 Nhân Vật (Có thể chỉnh sửa)", padding="10")
        character_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        character_frame.configure(style='Card.TLabelframe')
        character_frame.columnconfigure(0, weight=1)
        character_frame.rowconfigure(1, weight=1)
        
        ttk.Label(character_frame, text="Mô tả các nhân vật:", 
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        
        self.character_text = scrolledtext.ScrolledText(character_frame, height=4, wrap=tk.WORD,
                                                       bg='#1B222C', fg='#EAECEF', 
                                                       insertbackground='#EAECEF',
                                                       highlightthickness=1, 
                                                       highlightbackground='#2A2F3A')
        self.character_text.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        
        # Results display (right)
        results_frame = ttk.LabelFrame(right_frame, text="📋 Kết quả Story Prompts", padding="10")
        results_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        results_frame.configure(style='Card.TLabelframe')
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=8, wrap=tk.WORD,
                                                    state='disabled', bg='#10141B', fg='#EAECEF',
                                                    insertbackground='#EAECEF',
                                                    highlightthickness=1, 
                                                    highlightbackground='#2A2F3A')
        self.results_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        
        # Make results area expandable
        # left_frame grows vertically with its content implicitly; right_frame is configured above
        
        # Bind character text changes to update character prompts
        self.character_text.bind('<KeyRelease>', self._on_character_text_change)
        
        # Store generated prompts
        self.generated_prompts = []
        self.character_prompts = []
    
    def _generate_story_prompts(self):
        """Generate story prompts using Gemini AI"""
        if self.is_generating:
            return
            
        # Thiết lập API key theo lựa chọn: mặc định hoặc custom
        if self.api_key_mode.get() == "custom":
            custom_key = self.custom_api_key_var.get().strip()
            if not custom_key:
                messagebox.showerror("Lỗi", "Vui lòng nhập Gemini API key của bạn hoặc chọn dùng key mặc định.")
                return
            self._setup_gemini(api_key=custom_key)
        else:
            # Randomize API key per chat from default list
            self._setup_gemini()

        story_text = self.story_text.get("1.0", tk.END).strip()
        if not story_text:
            messagebox.showerror("Lỗi", "Vui lòng nhập mô tả câu chuyện!")
            return
            
        try:
            num_prompts = int(self.num_prompts.get())
            if num_prompts < 1 or num_prompts > 100:
                messagebox.showerror("Lỗi", "Số lượng prompt phải từ 1 đến 100!")
                return
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng prompt không hợp lệ!")
            return
            
        if not self.model:
            detail = "Gemini API chưa được cấu hình đúng! Vui lòng kiểm tra API key hoặc kết nối mạng."
            if self.last_setup_error:
                detail += f"\nChi tiết: {self.last_setup_error}"
            elif _GENAI_IMPORT_ERROR:
                detail += f"\nChi tiết: {_GENAI_IMPORT_ERROR}"
            messagebox.showerror("Lỗi", detail)
            return
            
        # Start generation in background thread
        threading.Thread(target=self._generate_prompts_thread, 
                        args=(story_text, num_prompts), daemon=True).start()
    
    def _generate_prompts_thread(self, story_text: str, num_prompts: int):
        """Background thread for generating prompts"""
        try:
            self.is_generating = True
            self._update_status("🔄 Đang tạo mô tả nhân vật...", "orange")
            self.generate_btn.config(state="disabled")
            
            # Generate character descriptions
            self._update_status("🔄 Đang tạo mô tả nhân vật...", "orange")
            character_prompt = f"""
Bạn là một chuyên gia tạo mô tả nhân vật cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo 4-6 mô tả CỰC KỲ CHI TIẾT về các nhân vật khác nhau trong câu chuyện.

YÊU CẦU MÔ TẢ CỰC KỲ CHI TIẾT (40-60 từ mỗi nhân vật):
- HÌNH DÁNG: Chiều cao chính xác, vóc dáng cụ thể (gầy gò, mập mạp, cao lênh khênh, thấp lùn, v.v.)
- KÍCH THƯỚC: So sánh cụ thể (to như gấu, nhỏ như chuột, trung bình như người bình thường)
- MÀU SẮC: Màu tóc chính xác (vàng óng, nâu sẫm, đen nhánh), màu da (trắng hồng, nâu vàng, đen bóng), màu mắt (xanh dương, nâu đậm, xanh lá), màu quần áo (đỏ thẫm, xanh navy, trắng tinh)
- MẮT: Màu mắt cụ thể, hình dáng mắt (to tròn, nhỏ híp, dài xếch), biểu cảm (tinh nghịch, buồn bã, kiên định, sợ hãi)
- QUẦN ÁO: Loại trang phục chi tiết (áo sơ mi trắng, váy dài xanh, quần jean xanh, áo khoác da đen), màu sắc cụ thể, phong cách (thanh lịch, bụi bặm, sang trọng, giản dị)
- ĐẶC ĐIỂM NỔI BẬT: Râu (râu dài bạc, ria mép đen), tóc (tóc dài xoăn, tóc ngắn thẳng), phụ kiện (kính mắt, nhẫn vàng, vòng cổ bạc), vết sẹo, nốt ruồi, v.v.
- TUỔI TÁC: Trẻ (20-30), già (60-80), trung niên (40-50), thiếu niên (13-18), trẻ em (5-12)
- TÍNH CÁCH: Thể hiện qua ngoại hình (kiên định, nhút nhát, mạnh mẽ, dịu dàng)
- Ghi rõ ai là nhân vật chính
- TẠO RA NHIỀU NHÂN VẬT KHÁC NHAU (nhân vật chính, nhân vật phụ, động vật, v.v.)
- Mỗi mô tả phải dài 40-60 từ để CỰC KỲ CHI TIẾT, gồm cả dáng di chuyển
- Sử dụng từ ngữ sinh động, có tính hình ảnh, cụ thể
- Phù hợp với phong cách câu chuyện: {self.story_style.get()}
- Mỗi nhân vật phải có đặc điểm riêng biệt và dễ phân biệt
- Bao gồm cả nhân vật chính và nhân vật phụ nếu câu chuyện có

Câu chuyện gốc:
{story_text}

Hãy trả về danh sách các mô tả nhân vật CỰC KỲ CHI TIẾT khác nhau.
ĐỊNH DẠNG BẮT BUỘC: Mỗi dòng bắt đầu bằng "**Tên Nhân Vật**: Mô tả..." (Hãy đặt tên nhân vật trong dấu sao đôi và có dấu hai chấm).
Tuyệt đối chỉ trả về danh sách nhân vật, không có lời dẫn.
"""
            
            # Generate character descriptions
            character_response = self.model.generate_content(character_prompt)
            character_text = character_response.text.strip()
            
            # Parse character prompts
            character_prompts = []
            character_names = []
            
            for line in character_text.split('\n'):
                line = line.strip()
                if line and not line.isdigit():
                    character_prompts.append(line)
                    # Extract name
                    # Match **Name**: or Name:
                    m = re.match(r'\*\*?(.*?)\*\*?:', line)
                    if m:
                        character_names.append(m.group(1).strip())
                    else:
                        # Try split by colon
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            character_names.append(parts[0].strip().replace('*', ''))
            
            self.character_prompts = character_prompts
            available_names_str = ", ".join(character_names) if character_names else "các nhân vật đã tạo"
            
            # Update character text area
            self._update_character_text_area()
            
            self._update_status("🔄 Đang tạo story prompts...", "orange")

            # Now generate story prompts in batches of 10, chaining previous outputs
            style = self.story_style.get()
            prompts = []
            base_instruction = f"""
Bạn là một chuyên gia tạo prompt cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo prompt ngắn gọn và hấp dẫn cho việc tạo video.

Danh sách nhân vật hiện có: {available_names_str}

Yêu cầu:
- Bắt đầu bằng: "Chỉ sử dụng nhân vật: [Tên 1, Tên 2], " sau đó mới là nội dung.
- QUAN TRỌNG: Phải dùng CHÍNH XÁC tên trong danh sách nhân vật trên (copy y nguyên). Nếu nhiều nhân vật thì cách nhau dấu phẩy trong ngoặc vuông.
- Nếu không có nhân vật nào cụ thể trong cảnh, dùng "Chỉ sử dụng nhân vật: [Khung cảnh], "
- Mỗi prompt phải là một câu mô tả câu chuyện, hoặc lời thoại nếu có
- Tập trung vào phong cách: {style}
- Mỗi prompt phải mô tả một cảnh/quãng khác nhau của câu chuyện, theo thứ tự tiến triển tự nhiên
- Sử dụng từ ngữ sinh động, có tính hình ảnh
- Tránh lặp lại nội dung giữa các prompt
- Phù hợp để tạo video ngắn (10 giây mỗi prompt)
- Mô tả chi tiết và đầy đủ mỗi cảnh khoảng 50 words

Tuyệt đối đừng nói bất kỳ từ thừa thãi nào không liên quan đến yêu cầu.

Câu chuyện gốc:
{story_text}
"""

            while len(prompts) < num_prompts:
                batch_size = min(10, num_prompts - len(prompts))
                if prompts:
                    # Send previous instruction and accumulated prompts to continue
                    continuation_instruction = f"""
Tin nhắn trước đó (giữ nguyên yêu cầu):
{base_instruction}

Các prompt đã tạo trước đó (giữ nguyên thứ tự từ Scene 1 đến Scene {len(prompts)}):
{chr(10).join(prompts)}

Hãy tạo thêm {batch_size} prompt MỚI tiếp nối mạch truyện (Scene {len(prompts) + 1} đến Scene {len(prompts) + batch_size}), không trùng lặp, mỗi prompt trên một dòng, không đánh số.
"""
                    prompt_text = continuation_instruction
                else:
                    first_batch_instruction = f"""
{base_instruction}

Hãy trả về danh sách {batch_size} prompt đầu tiên (từ Scene 1 đến Scene {batch_size}), mỗi prompt trên một dòng.
"""
                    prompt_text = first_batch_instruction

                # Request this batch
                batch_response = self.model.generate_content(prompt_text)
                batch_text = (batch_response.text or "").strip()

                # Parse and append up to batch_size
                new_items = []
                for line in batch_text.split('\n'):
                    line = line.strip()
                    if line and not line.isdigit():
                        new_items.append(line)
                    if len(new_items) >= batch_size:
                        break

                # Fallback: if the model returned fewer than requested, still proceed
                if new_items:
                    # Programmatically add [Scene N]: prefix
                    start_idx = len(prompts)
                    for idx, item in enumerate(new_items):
                        scene_num = start_idx + idx + 1
                        # Avoid double prefix if AI hallucinated it (check potential old and new format)
                        if not re.match(r'^\[Scene(?:_)?\d+(?:_)?\]:', item, re.IGNORECASE):
                            new_items[idx] = f"[Scene_{scene_num}_]: {item}"
                        else:
                             # Normalize hallucinated prefix numbers
                             item = re.sub(r'^\[Scene(?:_)?\d+(?:_)?\]:\s*', '', item, flags=re.IGNORECASE)
                             new_items[idx] = f"[Scene_{scene_num}_]: {item}"
                    
                    prompts.extend(new_items)
                else:
                    # Break to avoid infinite loop if nothing returned
                    break

                # Update status to show progress
                self._update_status(f"🔄 Đang tạo story prompts... ({len(prompts)}/{num_prompts})", "orange")
            
            # Always combine character prompts with story prompts
            story_prompts = prompts[:num_prompts]
            combined_prompts = []
            
            for story_prompt in story_prompts:
                # Filter character descriptions based on the prompt content
                selected_descriptions = []
                
                # Check for [Name1, Name2] format in "Chỉ sử dụng nhân vật: [...]"
                # Regex matches anything inside brackets after the intro phrase
                match = re.search(r"chỉ sử dụng nhân vật:.*?\[(.*?)\].*?", story_prompt, re.IGNORECASE)
                
                if match:
                    names_str = match.group(1)
                    # Split by comma
                    names_found = [n.strip() for n in names_str.split(',') if n.strip()]
                    
                    if names_found and self.character_prompts:
                        for desc in self.character_prompts:
                            # Try to match the name extracted with the description
                            # Description format expected: "**Name**: Desc" or "Name: Desc"
                            # We check if the 'name found' is contained in the 'description' (start of it)
                            # Or if the parsed name from description matches
                            
                            desc_lower = desc.lower()
                            for name in names_found:
                                name_lower = name.lower()
                                # Check if description starts with name (approx) or contains name followed by colon
                                if name_lower in desc_lower.split(':')[0]:
                                    selected_descriptions.append(desc)
                                    break
                
                # Fallback handled: if selected_descriptions is empty, we MIGHT want to include all, 
                # OR if it's "Khung cảnh" (Scene), maybe we include none?
                # User logic: "Nếu không tìm thấy, fallback về all" (from previous code implicit logic).
                # But if prompt says "Khung cảnh", maybe we don't want characters.
                # Let's keep strict "if names found but no match in descriptions, usage might be empty or wrong".
                # To be safe and follow user "unify" request, let's just stick to the mapping.
                
                # If we parsed [Name] but found no description, maybe it's a hallucination or exact match failed.
                # Try partial match? We already did (name in desc_lower.split(':')[0]).
                
                if not selected_descriptions:
                    # If regex failed completely (no [...] pattern), fallback to ALL characters (safe)
                    if not match:
                        selected_descriptions = self.character_prompts
                
                # Extract Scene prefix
                scene_prefix = ""
                # story_prompt format is "[Scene N]: Content". We want to extract "[Scene N]:"
                # Extract Scene prefix (handling both [Scene N]: and [Scene_N_]: just in case)
                scene_prefix = ""
                # Support both old "[Scene N]:" and new "[Scene_N_]:"
                match_scene = re.match(r'^(\[Scene(?:_)?\d+(?:_)?\]:)\s*(.*)', story_prompt, re.DOTALL | re.IGNORECASE)
                if match_scene:
                    scene_prefix = match_scene.group(1)
                    actual_content = match_scene.group(2)
                else:
                    actual_content = story_prompt

                character_part = ", ".join(selected_descriptions) + ", " if selected_descriptions else ""

                # Add video style prefix
                vid_style = self.video_style.get()
                style_prefix = f"Create video {vid_style}." if vid_style else ""
                
                # Construct combined prompt: [Scene N]: Create [Style]. CharDesc, \n\n Content
                parts = []
                if style_prefix:
                    parts.append(style_prefix)
                if character_part:
                    parts.append(character_part)
                
                middle_part = " ".join(parts)
                
                if middle_part:
                    combined_prompt = f"{scene_prefix} {middle_part}\n\n{actual_content}"
                else:
                    combined_prompt = f"{scene_prefix} {actual_content}"
                
                combined_prompts.append(combined_prompt)
            
            self.generated_prompts = combined_prompts
            print(f"DEBUG: Final generated prompts: {self.generated_prompts}")
            
            # Update UI
            self._display_results()
            self._update_status(f"✅ Đã tạo thành công {len(self.character_prompts)} nhân vật đa dạng và {len(self.generated_prompts)} story prompts!", "green")
            
            # Enable execute button if we have prompts
            if self.generated_prompts:
                self.execute_btn.config(state='normal')
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg and "models" in error_msg:
                self._update_status("❌ Lỗi: Model Gemini không tồn tại hoặc không được hỗ trợ", "red")
                messagebox.showerror("Lỗi", "Model Gemini không tồn tại hoặc không được hỗ trợ. Vui lòng kiểm tra API key hoặc thử lại sau.")
            elif "API key" in error_msg or "authentication" in error_msg.lower():
                self._update_status(f"❌ Lỗi: API key không hợp lệ {error_msg}", "red")
                messagebox.showerror("Lỗi", "API key không hợp lệ. Vui lòng kiểm tra lại API key.")
            else:
                self._update_status(f"❌ Lỗi khi tạo prompts: {error_msg}", "red")
                messagebox.showerror("Lỗi", f"Không thể tạo story prompts: {error_msg}")
        finally:
            self.is_generating = False
            self.generate_btn.config(state="normal")
    
    
    def _display_results(self):
        """Display generated prompts in the results area"""
        self.results_text.configure(state='normal')
        self.results_text.delete('1.0', tk.END)
        
        # Display character prompts if available
        if self.character_prompts:
            self.results_text.insert(tk.END, "👥 CÁC NHÂN VẬT TRONG CÂU CHUYỆN (SẼ ĐƯỢC THÊM VÀO TẤT CẢ STORY PROMPTS):\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n")
            for i, prompt in enumerate(self.character_prompts, 1):
                self.results_text.insert(tk.END, f"{i:2d}. {prompt}\n")
            self.results_text.insert(tk.END, "\n")
        
        # Display story prompts if available
        if self.generated_prompts:
            self.results_text.insert(tk.END, "🎬 STORY PROMPTS (ĐÃ KẾT HỢP VỚI NHÂN VẬT):\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n")
            for i, prompt in enumerate(self.generated_prompts, 1):
                self.results_text.insert(tk.END, f"{i:2d}. {prompt}\n")
        
        if not self.character_prompts and not self.generated_prompts:
            self.results_text.insert(tk.END, "Chưa có prompt nào được tạo.")
        
        self.results_text.configure(state='disabled')
        self.results_text.see(tk.END)
    

    def _export_to_excel(self):
        """Export generated prompts to Excel file"""
        if not self.generated_prompts:
            messagebox.showwarning("Cảnh báo", "Chưa có prompt nào để export!")
            return
            
        try:
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=f"story_prompts_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                title="Lưu file Excel"
            )
            
            if not file_path:
                return
                
            # Create workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Tasks"
            
            # Add headers (matching execute tab format) + story_only
            ws.append(["workflow", "prompt", "media", "aspect_ratio", "outputs_per_prompt", "model", "story_only"])
            
            # Add data rows
            for prompt in self.generated_prompts:
                story_only = self._extract_story_only(prompt)
                ws.append(["text_to_video", prompt, "", "16:9", "1", "Veo 3.1 - Fast", story_only])
            
            # Save file
            wb.save(file_path)
            
            self._update_status(f"✅ Đã export thành công {len(self.generated_prompts)} prompts!", "green")
            messagebox.showinfo("Thành công", f"Đã lưu file Excel:\n{file_path}")
            
        except Exception as e:
            self._update_status(f"❌ Lỗi khi export: {str(e)}", "red")
            messagebox.showerror("Lỗi", f"Không thể export file Excel: {str(e)}")

    def _extract_story_only(self, prompt_text: str) -> str:
        """Extract only the story part without the character list prefix.
        Prefer splitting on the two newlines we insert between character block and story line.
        Fallback heuristics: detect prefix patterns and strip them; otherwise return trimmed text.
        """
        try:
            text = prompt_text.strip()
            # Primary: split on the separator we add between character block and story
            sep = "\n\n"
            if sep in text:
                parts = text.split(sep, 1)
                return parts[1].strip()
            # Secondary: if current character prefix exists, strip it
            if self.character_prompts:
                prefix = ", ".join(self.character_prompts) + ", "
                if text.startswith(prefix):
                    return text[len(prefix):].lstrip(" \n\t:-")
            # Legacy pattern: "Chỉ sử dụng nhân vật: [...], <story>"
            close_idx = text.find('],')
            if close_idx != -1:
                return text[close_idx + 2:].strip(" :,-\u2014\u2013\u00a0\t")
            # Fallback: if there's a colon after the lead phrase, split on first comma after colon
            lead = "Chỉ sử dụng nhân vật"
            if text.lower().startswith(lead.lower()):
                first_comma = text.find(',')
                if first_comma != -1:
                    return text[first_comma + 1:].strip()
            return text
        except Exception:
            return prompt_text
    
    def _clear_all(self):
        """Clear all generated prompts and reset UI"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa tất cả prompts đã tạo?"):
            self.generated_prompts = []
            self.character_prompts = []
            self.character_text.delete('1.0', tk.END)
            self._display_results()
            self._update_status("✅ Đã xóa tất cả prompts", "green")
            # Disable execute button
            self.execute_btn.config(state='disabled')
    
    def _execute_story_prompts(self):
        """Transfer generated prompts to execute tab and switch to execute tab"""
        if not self.generated_prompts:
            messagebox.showwarning("Cảnh báo", "Chưa có prompt nào để execute! Vui lòng tạo story prompts trước.")
            return
            
        try:
            # Check if we have access to the main application callbacks
            if not self.ui_callbacks:
                messagebox.showerror("Lỗi", "Không thể kết nối với execute tab!")
                return
                
            # Create Excel file with generated prompts
            import tempfile
            import os
            from openpyxl import Workbook
            
            # Create temporary Excel file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_file.close()
            
            # Create workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Tasks"
            
            # Add headers (matching execute tab format)
            ws.append(["workflow", "prompt", "media", "aspect_ratio", "outputs_per_prompt", "model"])
            
            # Add data rows with generated prompts
            for prompt in self.generated_prompts:
                ws.append(["text_to_video", prompt, "", "16:9", "2", "Veo 3.1 - Fast"])
            
            # Save file
            wb.save(temp_file.name)
            
            # Use the callback to import the Excel file and switch to execute tab
            if 'import_excel_and_switch' in self.ui_callbacks:
                self.ui_callbacks['import_excel_and_switch'](temp_file.name)
                self._update_status("✅ Đã chuyển prompts sang execute tab!", "green")
            else:
                # Fallback: just show success message
                self._update_status("✅ Đã tạo file Excel với prompts!", "green")
                messagebox.showinfo("Thành công", f"Đã tạo file Excel với {len(self.generated_prompts)} prompts:\n{temp_file.name}\n\nVui lòng import file này vào execute tab.")
            
        except Exception as e:
            self._update_status(f"❌ Lỗi khi execute: {str(e)}", "red")
            messagebox.showerror("Lỗi", f"Không thể execute story prompts: {str(e)}")
    
    def _update_character_text_area(self):
        """Update character text area with current character prompts"""
        self.character_text.delete('1.0', tk.END)
        if self.character_prompts:
            character_text = '\n'.join(self.character_prompts)
            self.character_text.insert('1.0', character_text)
    
    def _on_character_text_change(self, event=None):
        """Handle character text changes"""
        try:
            # Get text from character text area
            character_text = self.character_text.get('1.0', tk.END).strip()
            
            # Parse character prompts from text
            if character_text:
                character_prompts = []
                for line in character_text.split('\n'):
                    line = line.strip()
                    if line:
                        character_prompts.append(line)
                self.character_prompts = character_prompts
            else:
                self.character_prompts = []
            
            # Regenerate story prompts if we have them
            if self.generated_prompts:
                self._regenerate_story_prompts()
                
        except Exception as e:
            print(f"Error updating character prompts: {e}")
    
    def _regenerate_story_prompts(self):
        """Regenerate story prompts with updated character prompts"""
        try:
            # Get original story prompts (without character descriptions)
            story_text = self.story_text.get("1.0", tk.END).strip()
            if not story_text:
                return
                
            # Generate new story prompts
            style = self.story_style.get()
            num_prompts = len(self.generated_prompts) if self.generated_prompts else 10
            
            # Extract names for instruction
            character_names = []
            for line in self.character_prompts:
                m = re.match(r'\*\*?(.*?)\*\*?:', line)
                if m:
                    character_names.append(m.group(1).strip())
                else:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        character_names.append(parts[0].strip().replace('*', ''))
            available_names_str = ", ".join(character_names) if character_names else "các nhân vật đã tạo"

            system_prompt = f"""
Bạn là một chuyên gia tạo prompt cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo {num_prompts} prompt ngắn gọn và hấp dẫn cho việc tạo video.

Danh sách nhân vật hiện có: {available_names_str}

Yêu cầu:
- Bắt đầu bằng: "Chỉ sử dụng nhân vật: [Tên 1, Tên 2], " sau đó mới là nội dung.
- QUAN TRỌNG: Phải dùng CHÍNH XÁC tên trong danh sách nhân vật trên (copy y nguyên). Nếu nhiều nhân vật thì cách nhau dấu phẩy trong ngoặc vuông.
- Nếu không có nhân vật nào cụ thể trong cảnh, dùng "Chỉ sử dụng nhân vật: [Khung cảnh], "
- Mỗi prompt phải là một câu hoặc cụm từ ngắn gọn (dưới 30 từ)
- Tập trung vào phong cách: {style}
- Mỗi prompt phải mô tả một cảnh/quãng khác nhau của câu chuyện
- Sử dụng từ ngữ sinh động, có tính hình ảnh
- Tránh lặp lại nội dung giữa các prompt
- Phù hợp để tạo video ngắn (5-10 giây mỗi prompt)
- Chỉ sử dụng các nhân vật có trong câu chuyện, không tự tạo nhân vật mới

Câu chuyện gốc:
{story_text}

Hãy trả về danh sách {num_prompts} prompt, mỗi prompt trên một dòng, không đánh số thứ tự.
"""
            
            # Generate with Gemini
            response = self.model.generate_content(system_prompt)
            generated_text = response.text.strip()
            
            # Parse the response into individual prompts
            prompts = []
            for line in generated_text.split('\n'):
                line = line.strip()
                line = line.strip()
                if line and not line.isdigit():
                    # Add [Scene_N_] prefix programmatically
                    scene_num = len(prompts) + 1
                    # Avoid double prefix
                    if not re.match(r'^\[Scene(?:_)?\d+(?:_)?\]:', line, re.IGNORECASE):
                        line = f"[Scene_{scene_num}_]: {line}"
                    else:
                        line = re.sub(r'^\[Scene(?:_)?\d+(?:_)?\]:\s*', '', line, flags=re.IGNORECASE)
                        line = f"[Scene_{scene_num}_]: {line}"
                    prompts.append(line)
            
            # Combine with character prompts
            combined_prompts = []
            
            for story_prompt in prompts:
                # Filter character descriptions based on the prompt content
                selected_descriptions = []
                
                # Check for [Name1, Name2] format in "Chỉ sử dụng nhân vật: [...]"
                match = re.search(r"chỉ sử dụng nhân vật:.*?\[(.*?)\].*?", story_prompt, re.IGNORECASE)
                
                if match:
                    names_str = match.group(1)
                    names_found = [n.strip() for n in names_str.split(',') if n.strip()]
                    
                    if names_found and self.character_prompts:
                        for desc in self.character_prompts:
                            desc_lower = desc.lower()
                            for name in names_found:
                                name_lower = name.lower()
                                if name_lower in desc_lower.split(':')[0]:
                                    selected_descriptions.append(desc)
                                    break
                
                if not selected_descriptions:
                    if not match:
                        selected_descriptions = self.character_prompts

                # Extract Scene prefix
                scene_prefix = ""
                # story_prompt format is "[Scene N]: Content". We want to extract "[Scene N]:"
                # Extract Scene prefix
                scene_prefix = ""
                match_scene = re.match(r'^(\[Scene(?:_)?\d+(?:_)?\]:)\s*(.*)', story_prompt, re.DOTALL | re.IGNORECASE)
                if match_scene:
                    scene_prefix = match_scene.group(1)
                    actual_content = match_scene.group(2)
                else:
                    actual_content = story_prompt

                character_part = ", ".join(selected_descriptions) + ", " if selected_descriptions else ""

                # Add video style prefix
                vid_style = self.video_style.get()
                style_prefix = f"Create video {vid_style}." if vid_style else ""
                
                # Construct combined prompt: [Scene N]: Create [Style]. CharDesc, \n\n Content
                parts = []
                if style_prefix:
                    parts.append(style_prefix)
                if character_part:
                    parts.append(character_part)
                
                middle_part = " ".join(parts)
                
                if middle_part:
                    combined_prompt = f"{scene_prefix} {middle_part}\n\n{actual_content}"
                else:
                    combined_prompt = f"{scene_prefix} {actual_content}"
                
                combined_prompts.append(combined_prompt)
            
            self.generated_prompts = combined_prompts
            
            # Update display
            self._display_results()
            
        except Exception as e:
            print(f"Error regenerating story prompts: {e}")

    def _update_status(self, text: str, color: str):
        """Update status label"""
        try:
            style_map = {
                'blue': 'Info.TLabel',
                'green': 'Success.TLabel', 
                'red': 'Error.TLabel',
                'orange': 'Warning.TLabel'
            }
            style = style_map.get(color, 'Info.TLabel')
            self.status_label.config(text=text, style=style)
        except Exception:
            pass

    def _on_api_key_mode_change(self):
        """Bật/tắt ô nhập API key khi người dùng chọn chế độ default/custom."""
        try:
            mode = self.api_key_mode.get()
            if mode == "custom":
                self.custom_api_key_entry.configure(state="normal")
            else:
                self.custom_api_key_entry.configure(state="disabled")
        except Exception:
            # Không để lỗi nhỏ làm vỡ UI
            pass