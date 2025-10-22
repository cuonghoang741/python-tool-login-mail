import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import json
import time
import threading
import random
from openpyxl import Workbook
import google.generativeai as genai
from typing import List, Dict, Any


class StoryPromptGenerator:
    def __init__(self, parent_frame, ui_callbacks=None):
        self.parent_frame = parent_frame
        self.ui_callbacks = ui_callbacks or {}
        
        # Gemini API configuration
        self.gemini_api_key = "AIzaSyDg7cgmRziMGKfbBzRASl1F4Uc4gsmkyDw"
        self.model = None
        self._setup_gemini()
        
        # UI state
        self.is_generating = False
        
        self._build_ui()
    
    def _setup_gemini(self):
        """Initialize Gemini API"""
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        except Exception as e:
            print(f"Failed to setup Gemini API: {e}")
            self.model = None
    
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
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Story input section
        story_frame = ttk.LabelFrame(main_frame, text="📖 Nhập câu chuyện", padding="15")
        story_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
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
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ Cấu hình", padding="15")
        config_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
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
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.generate_btn = ttk.Button(button_frame, text="🎬 Tạo Story + Nhân Vật", 
                                     command=self._generate_story_prompts, 
                                     style='Accent.TButton')
        self.generate_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.character_btn = ttk.Button(button_frame, text="👤 Tạo Nhân Vật", 
                                      command=self._generate_character_prompts, 
                                      style='Secondary.TButton')
        self.character_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.template_btn = ttk.Button(button_frame, text="⬇️ Tải Template", 
                                     command=self._download_excel_template, 
                                     style='Secondary.TButton')
        self.template_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.export_btn = ttk.Button(button_frame, text="📥 Export Excel", 
                                   command=self._export_to_excel, 
                                   style='Secondary.TButton')
        self.export_btn.grid(row=0, column=3, padx=(0, 10))
        
        self.clear_btn = ttk.Button(button_frame, text="🗑️ Xóa tất cả", 
                                   command=self._clear_all, 
                                   style='Secondary.TButton')
        self.clear_btn.grid(row=0, column=4)
        
        # Status
        self.status_label = ttk.Label(main_frame, text="✅ Sẵn sàng tạo story prompts với nhân vật", 
                                    style='Success.TLabel')
        self.status_label.grid(row=4, column=0, columnspan=2, sticky=tk.W)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="📋 Kết quả Story Prompts", padding="10")
        results_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.W, tk.E), pady=(10, 0))
        results_frame.configure(style='Card.TLabelframe')
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=12, wrap=tk.WORD,
                                                    state='disabled', bg='#10141B', fg='#EAECEF',
                                                    insertbackground='#EAECEF',
                                                    highlightthickness=1, 
                                                    highlightbackground='#2A2F3A')
        self.results_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        
        # Make results area expandable
        main_frame.rowconfigure(5, weight=1)
        
        # Store generated prompts
        self.generated_prompts = []
        self.character_prompts = []
    
    def _generate_story_prompts(self):
        """Generate story prompts using Gemini AI"""
        if self.is_generating:
            return
            
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
            messagebox.showerror("Lỗi", "Gemini API chưa được cấu hình đúng! Vui lòng kiểm tra API key hoặc kết nối mạng.")
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
            
            # First, generate character descriptions if not already available
            if not self.character_prompts:
                self._update_status("🔄 Đang tạo mô tả nhân vật...", "orange")
                character_prompt = f"""
Bạn là một chuyên gia tạo mô tả nhân vật cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo 3-5 mô tả chi tiết về ngoại hình nhân vật chính.

Yêu cầu:
- Mỗi mô tả phải ngắn gọn (dưới 15 từ)
- Tập trung vào ngoại hình: màu tóc, màu mắt, trang phục, đặc điểm nổi bật
- Sử dụng từ ngữ sinh động, có tính hình ảnh
- Phù hợp với phong cách câu chuyện: {self.story_style.get()}
- Mỗi mô tả phải khác nhau về góc nhìn hoặc đặc điểm

Câu chuyện gốc:
{story_text}

Hãy trả về danh sách 3-5 mô tả nhân vật, mỗi mô tả trên một dòng, không đánh số thứ tự.
"""
                
                # Generate character descriptions
                character_response = self.model.generate_content(character_prompt)
                character_text = character_response.text.strip()
                
                # Parse character prompts
                character_prompts = []
                for line in character_text.split('\n'):
                    line = line.strip()
                    if line and not line.isdigit():
                        character_prompts.append(line)
                
                self.character_prompts = character_prompts
                self._update_status("🔄 Đang tạo story prompts...", "orange")
            
            # Now generate story prompts
            style = self.story_style.get()
            system_prompt = f"""
Bạn là một chuyên gia tạo prompt cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo {num_prompts} prompt ngắn gọn và hấp dẫn cho việc tạo video.

Yêu cầu:
- Mỗi prompt phải là một câu hoặc cụm từ ngắn gọn (dưới 20 từ)
- Tập trung vào phong cách: {style}
- Mỗi prompt phải mô tả một cảnh/quãng khác nhau của câu chuyện
- Sử dụng từ ngữ sinh động, có tính hình ảnh
- Tránh lặp lại nội dung giữa các prompt
- Phù hợp để tạo video ngắn (5-10 giây mỗi prompt)

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
                if line and not line.isdigit():  # Skip empty lines and numbers
                    prompts.append(line)
            
            # If we got fewer prompts than requested, generate more
            while len(prompts) < num_prompts:
                additional_needed = num_prompts - len(prompts)
                additional_prompt = f"""
Tạo thêm {additional_needed} prompt ngắn gọn cho câu chuyện này, phong cách {style}.
Mỗi prompt trên một dòng, không đánh số.
"""
                try:
                    additional_response = self.model.generate_content(additional_prompt)
                    additional_lines = additional_response.text.strip().split('\n')
                    for line in additional_lines:
                        line = line.strip()
                        if line and not line.isdigit() and len(prompts) < num_prompts:
                            prompts.append(line)
                except Exception:
                    break
            
            # Always combine character prompts with story prompts
            story_prompts = prompts[:num_prompts]
            combined_prompts = []
            print(f"DEBUG: Character prompts available: {len(self.character_prompts)}")
            print(f"DEBUG: Character prompts: {self.character_prompts}")
            print(f"DEBUG: Story prompts: {story_prompts}")
            
            for story_prompt in story_prompts:
                # Combine ALL character prompts with each story prompt
                if self.character_prompts:
                    # Join all character prompts with commas
                    all_characters = ", ".join(self.character_prompts)
                    combined_prompt = f"{all_characters}, {story_prompt}"
                    print(f"DEBUG: Combined prompt with all characters: {combined_prompt}")
                else:
                    combined_prompt = story_prompt
                    print(f"DEBUG: No character prompts, using story only: {combined_prompt}")
                combined_prompts.append(combined_prompt)
            self.generated_prompts = combined_prompts
            print(f"DEBUG: Final generated prompts: {self.generated_prompts}")
            
            # Update UI
            self._display_results()
            self._update_status(f"✅ Đã tạo thành công {len(self.character_prompts)} nhân vật và {len(self.generated_prompts)} story prompts!", "green")
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg and "models" in error_msg:
                self._update_status("❌ Lỗi: Model Gemini không tồn tại hoặc không được hỗ trợ", "red")
                messagebox.showerror("Lỗi", "Model Gemini không tồn tại hoặc không được hỗ trợ. Vui lòng kiểm tra API key hoặc thử lại sau.")
            elif "API key" in error_msg or "authentication" in error_msg.lower():
                self._update_status("❌ Lỗi: API key không hợp lệ", "red")
                messagebox.showerror("Lỗi", "API key không hợp lệ. Vui lòng kiểm tra lại API key.")
            else:
                self._update_status(f"❌ Lỗi khi tạo prompts: {error_msg}", "red")
                messagebox.showerror("Lỗi", f"Không thể tạo story prompts: {error_msg}")
        finally:
            self.is_generating = False
            self.generate_btn.config(state="normal")
    
    def _generate_character_prompts(self):
        """Generate character appearance prompts using Gemini AI"""
        if self.is_generating:
            return
            
        story_text = self.story_text.get("1.0", tk.END).strip()
        if not story_text:
            messagebox.showerror("Lỗi", "Vui lòng nhập mô tả câu chuyện trước khi tạo nhân vật!")
            return
            
        if not self.model:
            messagebox.showerror("Lỗi", "Gemini API chưa được cấu hình đúng! Vui lòng kiểm tra API key hoặc kết nối mạng.")
            return
            
        # Start generation in background thread
        threading.Thread(target=self._generate_character_thread, 
                        args=(story_text,), daemon=True).start()
    
    def _generate_character_thread(self, story_text: str):
        """Background thread for generating character prompts"""
        try:
            self.is_generating = True
            self._update_status("🔄 Đang tạo mô tả nhân vật...", "orange")
            self.character_btn.config(state="disabled")
            
            # Prepare prompt for Gemini
            character_prompt = f"""
Bạn là một chuyên gia tạo mô tả nhân vật cho video AI. Dựa trên câu chuyện được mô tả, hãy tạo 3-5 mô tả chi tiết về ngoại hình nhân vật chính.

Yêu cầu:
- Mỗi mô tả phải ngắn gọn (dưới 15 từ)
- Tập trung vào ngoại hình: màu tóc, màu mắt, trang phục, đặc điểm nổi bật
- Sử dụng từ ngữ sinh động, có tính hình ảnh
- Phù hợp với phong cách câu chuyện: {self.story_style.get()}
- Mỗi mô tả phải khác nhau về góc nhìn hoặc đặc điểm

Câu chuyện gốc:
{story_text}

Hãy trả về danh sách 3-5 mô tả nhân vật, mỗi mô tả trên một dòng, không đánh số thứ tự.
"""
            
            # Generate with Gemini
            response = self.model.generate_content(character_prompt)
            generated_text = response.text.strip()
            
            # Parse the response into individual character prompts
            character_prompts = []
            for line in generated_text.split('\n'):
                line = line.strip()
                if line and not line.isdigit():  # Skip empty lines and numbers
                    character_prompts.append(line)
            
            # Store generated character prompts
            self.character_prompts = character_prompts
            
            # Update UI
            self._display_results()
            self._update_status(f"✅ Đã tạo thành công {len(self.character_prompts)} mô tả nhân vật!", "green")
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg and "models" in error_msg:
                self._update_status("❌ Lỗi: Model Gemini không tồn tại hoặc không được hỗ trợ", "red")
                messagebox.showerror("Lỗi", "Model Gemini không tồn tại hoặc không được hỗ trợ. Vui lòng kiểm tra API key hoặc thử lại sau.")
            elif "API key" in error_msg or "authentication" in error_msg.lower():
                self._update_status("❌ Lỗi: API key không hợp lệ", "red")
                messagebox.showerror("Lỗi", "API key không hợp lệ. Vui lòng kiểm tra lại API key.")
            else:
                self._update_status(f"❌ Lỗi khi tạo nhân vật: {error_msg}", "red")
                messagebox.showerror("Lỗi", f"Không thể tạo mô tả nhân vật: {error_msg}")
        finally:
            self.is_generating = False
            self.character_btn.config(state="normal")
    
    def _display_results(self):
        """Display generated prompts in the results area"""
        self.results_text.configure(state='normal')
        self.results_text.delete('1.0', tk.END)
        
        # Display character prompts if available
        if self.character_prompts:
            self.results_text.insert(tk.END, "👤 MÔ TẢ NHÂN VẬT:\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n")
            for i, prompt in enumerate(self.character_prompts, 1):
                self.results_text.insert(tk.END, f"{i:2d}. {prompt}\n")
            self.results_text.insert(tk.END, "\n")
        
        # Display story prompts if available
        if self.generated_prompts:
            self.results_text.insert(tk.END, "🎬 STORY PROMPTS (ĐÃ KẾT HỢP TẤT CẢ NHÂN VẬT):\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n")
            for i, prompt in enumerate(self.generated_prompts, 1):
                self.results_text.insert(tk.END, f"{i:2d}. {prompt}\n")
        
        if not self.character_prompts and not self.generated_prompts:
            self.results_text.insert(tk.END, "Chưa có prompt nào được tạo.")
        
        self.results_text.configure(state='disabled')
        self.results_text.see(tk.END)
    
    def _download_excel_template(self):
        """Download Excel template file similar to execute tab"""
        try:
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile="story_template.xlsx",
                title="Lưu template Excel"
            )
            
            if not file_path:
                return
                
            # Create workbook and worksheet
            wb = Workbook()
            ws = wb.active
            ws.title = "Tasks"
            
            # Add headers (matching execute tab format)
            ws.append(["workflow", "prompt", "media", "aspect_ratio", "outputs_per_prompt", "model"])
            
            # Add sample rows with story-related prompts
            ws.append(["text_to_video", "A magical forest with glowing fireflies dancing in the moonlight", "", "16:9", "1", "Veo 3.1 - Fast"])
            ws.append(["text_to_video", "A brave knight riding through a mystical mountain pass", "", "9:16", "2", "Veo 3.1 - Fast"])
            ws.append(["text_to_video", "A cozy cottage by the sea with waves gently lapping the shore", "", "16:9", "1", "Veo 3.1 - Fast"])
            
            # Save file
            wb.save(file_path)
            
            self._update_status("✅ Đã tạo template Excel thành công!", "green")
            messagebox.showinfo("Thành công", f"Đã lưu template Excel:\n{file_path}")
            
        except Exception as e:
            self._update_status(f"❌ Lỗi khi tạo template: {str(e)}", "red")
            messagebox.showerror("Lỗi", f"Không thể tạo template Excel: {str(e)}")

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
            
            # Add headers (matching execute tab format)
            ws.append(["workflow", "prompt", "media", "aspect_ratio", "outputs_per_prompt", "model"])
            
            # Add data rows
            for prompt in self.generated_prompts:
                ws.append(["text_to_video", prompt, "", "16:9", "1", "Veo 3.1 - Fast"])
            
            # Save file
            wb.save(file_path)
            
            self._update_status(f"✅ Đã export thành công {len(self.generated_prompts)} prompts!", "green")
            messagebox.showinfo("Thành công", f"Đã lưu file Excel:\n{file_path}")
            
        except Exception as e:
            self._update_status(f"❌ Lỗi khi export: {str(e)}", "red")
            messagebox.showerror("Lỗi", f"Không thể export file Excel: {str(e)}")
    
    def _clear_all(self):
        """Clear all generated prompts and reset UI"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa tất cả prompts đã tạo?"):
            self.generated_prompts = []
            self.character_prompts = []
            self._display_results()
            self._update_status("✅ Đã xóa tất cả prompts", "green")
    
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