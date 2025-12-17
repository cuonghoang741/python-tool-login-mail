#!/bin/bash
# Tool Voice Cloning - Install and Run Script for Mac/Linux

set -e  # Exit on error

echo "========================================"
echo "   Tool Voice Cloning & Synthesis"
echo "   Install and Run"
echo "========================================"
echo ""

# Lấy đường dẫn thư mục script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Hàm kiểm tra Python version
check_python_version() {
    local python_cmd="$1"
    if command -v "$python_cmd" &> /dev/null; then
        local version=$($python_cmd --version 2>&1 | awk '{print $2}')
        local major=$(echo "$version" | cut -d. -f1)
        local minor=$(echo "$version" | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 9 ] && [ "$minor" -le 11 ]; then
            echo "$python_cmd"
            return 0
        fi
    fi
    return 1
}

# [1/5] Kiểm tra Python
echo "[1/5] Kiểm tra Python..."
echo ""

PYTHON_CMD=""

# Thử các lệnh Python phổ biến
for cmd in python3.11 python3.10 python3.9 python3 python; do
    if check_python_version "$cmd"; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] Không tìm thấy Python 3.9-3.11!"
    echo ""
    echo "Vui lòng cài đặt Python 3.9, 3.10 hoặc 3.11:"
    echo ""
    echo "Trên macOS:"
    echo "  brew install python@3.11"
    echo ""
    echo "Hoặc tải từ: https://www.python.org/downloads/"
    echo ""
    exit 1
fi

echo "[OK] Tìm thấy Python:"
$PYTHON_CMD --version
echo ""

# [2/5] Kiểm tra pip
echo "[2/5] Kiểm tra pip..."
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "[ERROR] pip không hoạt động!"
    echo "Đang cài đặt pip..."
    $PYTHON_CMD -m ensurepip --upgrade
fi
echo "[OK] pip đã sẵn sàng"
echo ""

# [3/5] Tạo virtual environment
echo "[3/5] Thiết lập môi trường ảo..."
if [ ! -d "venv_voice" ]; then
    echo "Đang tạo virtual environment..."
    $PYTHON_CMD -m venv venv_voice
    if [ $? -ne 0 ]; then
        echo "[ERROR] Không thể tạo virtual environment!"
        exit 1
    fi
    echo "[OK] Đã tạo virtual environment"
else
    echo "[OK] Virtual environment đã tồn tại"
fi
echo ""

# [4/5] Kích hoạt virtual environment và cài đặt dependencies
echo "[4/5] Cài đặt dependencies..."
source venv_voice/bin/activate

# Nâng cấp pip
python -m pip install --upgrade pip --quiet

# Cài đặt dependencies
if [ -f "requirements_voice.txt" ]; then
    echo "Đang cài đặt các thư viện cần thiết..."
    echo "(Quá trình này có thể mất vài phút...)"
    echo ""
    python -m pip install -r requirements_voice.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Cài đặt dependencies thất bại!"
        exit 1
    fi
    echo "[OK] Đã cài đặt tất cả dependencies"
else
    echo "[WARNING] Không tìm thấy requirements_voice.txt"
    echo "Đang cài đặt dependencies cơ bản..."
    python -m pip install PySide6 torch torchaudio TTS numpy soundfile transformers==4.36.2
fi
echo ""

# [5/5] Chạy ứng dụng
echo "[5/5] Khởi động ứng dụng..."
echo "========================================"
echo "   Đang mở Tool Voice Cloning..."
echo "========================================"
echo ""

python -m tool_voices

# Xử lý sau khi đóng ứng dụng
EXIT_CODE=$?
echo ""
echo "========================================"
if [ $EXIT_CODE -ne 0 ]; then
    echo "   Có lỗi xảy ra!"
    echo "========================================"
    echo ""
    echo "Các khả năng:"
    echo "1. Thiếu thư viện Python"
    echo "2. Lỗi trong code ứng dụng"
    echo "3. Python không được cài đặt đúng"
    echo ""
else
    echo "   Ứng dụng đã đóng thành công!"
    echo "========================================"
    echo ""
fi

