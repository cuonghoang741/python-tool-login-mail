# Tool Voice Cloning & Synthesis

Ứng dụng nhân bản giọng nói và chuyển văn bản thành giọng nói với khả năng kiểm soát cảm xúc, sử dụng model XTTS-v2 từ Coqui.

## Tính năng

- **Nhân bản giọng nói**: Upload file âm thanh và lưu giọng nói (không cần training)
- **Text-to-Speech**: Chuyển văn bản thành giọng nói với giọng đã clone
- **Kiểm soát cảm xúc**: Chọn cảm xúc (Neutral, Happy, Angry, Sad, Surprised, Afraid)
- **Điều chỉnh cường độ**: Slider để điều chỉnh mức độ cảm xúc (0-100%)

## Yêu cầu hệ thống

- **Windows 10/11**
- **Python 3.9 - 3.11** (KHÔNG hỗ trợ Python 3.12+)
- **Visual C++ Build Tools** (để compile TTS)
- **Kết nối internet** (để tải model XTTS-v2 lần đầu)

## Cài đặt

### Bước 1: Cài Python 3.11

Nếu chưa có Python 3.11, cài bằng winget:
```bash
winget install Python.Python.3.11
```

Hoặc tải từ [python.org](https://www.python.org/downloads/)

### Bước 2: Cài Visual C++ Build Tools

Cài đặt để compile TTS:
```bash
winget install Microsoft.VisualStudio.2022.BuildTools
```

**Lưu ý**: Sau khi cài Build Tools, **phải restart máy** trước khi tiếp tục.

### Bước 3: Cài dependencies

Cài đặt toàn cục với Python 3.11:

```bash
# Đảm bảo đang dùng Python 3.11
py -3.11 --version

# Cài dependencies
py -3.11 -m pip install -r requirements_voice.txt
```

**Lưu ý**: 
- Quá trình cài TTS có thể mất 10-15 phút
- Cần restart máy sau khi cài Build Tools
- Nếu có nhiều Python version, đảm bảo dùng đúng Python 3.11

## Chạy ứng dụng

Chạy ứng dụng với Python 3.11:

```bash
py -3.11 -m tool_voices
```

Hoặc nếu Python 3.11 là default:

```bash
python -m tool_voices
```

## Build thành file EXE

Để build ứng dụng thành file .exe độc lập:

```bash
.\build_voice_tool.bat
```

File exe sẽ được tạo tại: `dist\ToolVoiceCloning\ToolVoiceCloning.exe`

## Hướng dẫn sử dụng

### Tab 1: Thêm Giọng Nói

1. **Chọn file âm thanh**: Click "Chọn file âm thanh" và chọn file (wav, mp3, flac)
2. **Đặt tên giọng**: Nhập tên hiển thị cho giọng nói
3. **Chọn ngôn ngữ** (tùy chọn): Chọn ngôn ngữ ưu tiên hoặc để "Tự động"
4. **Lưu giọng**: Click "Lưu Giọng" - giọng sẽ được lưu ngay (không cần training)

### Tab 2: Synthesize Speech

1. **Chọn giọng**: Chọn giọng đã lưu từ dropdown
2. **Chọn cảm xúc**: Chọn cảm xúc muốn thể hiện (Neutral, Happy, Angry, Sad, Surprised, Afraid)
3. **Điều chỉnh cường độ**: Kéo slider để điều chỉnh mức độ cảm xúc (0-100%)
4. **Nhập văn bản**: Nhập hoặc paste văn bản cần đọc
5. **Generate**: Click "Generate" để tạo file audio
6. **Tải file**: File sẽ được lưu trong thư mục `outputs/` và hiển thị trong danh sách

## Cấu trúc thư mục

```
tool/
├── tool_voices/          # Source code
├── voices/               # Thư mục lưu giọng đã clone
├── outputs/              # Thư mục lưu file audio đã generate
├── config/               # Cấu hình ứng dụng
├── logs/                 # Log files
├── requirements_voice.txt # Dependencies
├── tool_voices.spec      # PyInstaller spec file
└── build_voice_tool.bat  # Script build exe
```

## Xử lý lỗi


### Lỗi: "Module 'torch' chưa được cài đặt"

```bash
py -3.11 -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Lỗi: "cannot import name 'BeamSearchScorer'"

**Đây là lỗi phổ biến nhất!** Transformers version mới không tương thích với TTS.

Sửa ngay bằng lệnh:
```bash
# Uninstall version mới
py -3.11 -m pip uninstall transformers -y

# Cài version tương thích
py -3.11 -m pip install transformers==4.36.2
```

Sau đó **restart ứng dụng** và thử lại.

### Lỗi: "Microsoft Visual C++ 14.0 or greater is required"

1. Cài Visual C++ Build Tools (xem Bước 2)
2. **Restart máy**
3. Chạy lại lệnh cài TTS

### Lỗi: "TTS requires python >= 3.9 and < 3.12"

Đảm bảo đang dùng Python 3.11:
```bash
py -3.11 --version
```

Nếu không có, cài Python 3.11 (xem Bước 1).

### Lỗi: "Language 'vi' is not supported"

**Nguyên nhân**: XTTS-v2 không hỗ trợ chính thức tiếng Việt trong danh sách languages.

**Giải pháp tự động**: Hệ thống đã tự động fallback về English ('en') khi phát hiện text tiếng Việt. Text tiếng Việt vẫn có thể được xử lý, nhưng chất lượng có thể không tối ưu.

**Giải pháp tốt hơn** (nếu cần hỗ trợ tiếng Việt chuyên nghiệp):
1. Fine-tune XTTS với dataset tiếng Việt (cần kiến thức ML và tài nguyên)
2. Sử dụng model TTS khác hỗ trợ tiếng Việt tốt hơn
3. Sử dụng Google Cloud TTS, Azure TTS, hoặc các dịch vụ TTS khác có hỗ trợ tiếng Việt

## Model XTTS-v2

Ứng dụng sử dụng model [XTTS-v2](https://huggingface.co/coqui/XTTS-v2) từ Coqui AI.

- Model sẽ được tải tự động lần đầu chạy (cần internet)
- Kích thước model: ~1.7 GB
- Hỗ trợ đa ngôn ngữ: English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese (zh-cn), Hungarian, Korean, Japanese, Hindi

**Lưu ý về tiếng Việt**: 
- XTTS-v2 **không hỗ trợ chính thức** tiếng Việt (language code 'vi')
- Khi phát hiện text tiếng Việt, hệ thống sẽ tự động fallback về English ('en')
- Text tiếng Việt vẫn có thể được xử lý với English model, nhưng chất lượng có thể không tối ưu
- Để có hỗ trợ tiếng Việt tốt hơn, cần fine-tune model với dữ liệu tiếng Việt hoặc sử dụng model khác

## Ghi chú

- Lần đầu chạy có thể chậm do cần tải model XTTS-v2
- File audio mẫu nên có chất lượng tốt, rõ ràng (khuyến nghị tối thiểu 30 giây)
- Quá trình synthesis có thể mất vài giây đến vài phút tùy độ dài văn bản
- File exe build sẽ lớn (~500MB-1GB) do bao gồm model và dependencies

## License

Dự án này sử dụng model XTTS-v2 từ Coqui AI, tuân theo license của Coqui.

