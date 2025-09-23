#!/bin/bash

# Gmail Browser Login Tool - macOS Script
echo "========================================"
echo "   Gmail Browser Login Tool - Starting..."
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python chưa được cài đặt!"
    echo "Vui lòng cài đặt Python từ: https://www.python.org/downloads/"
    echo
    read -p "Nhấn Enter để thoát..."
    exit 1
fi

# Display Python version
echo "Python version:"
python3 --version
echo

# Check if gmail_browser_login.py exists
if [ ! -f "gmail_browser_login.py" ]; then
    echo "ERROR: Không tìm thấy file gmail_browser_login.py!"
    echo "Vui lòng đảm bảo file này có trong cùng thư mục."
    echo
    read -p "Nhấn Enter để thoát..."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Tạo virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "Đang kích hoạt virtual environment và cài đặt thư viện..."
source venv/bin/activate
pip install selenium webdriver-manager --quiet
echo

# Run the application
echo "========================================"
echo "   Đang khởi động Gmail Browser Login..."
echo "========================================"
echo
echo "Tính năng:"
echo "- Mở browser Chrome để đăng nhập thật"
echo "- Hỗ trợ 2FA tự động (OTP, SMS, Authenticator)"
echo "- Chờ tối đa 5 phút để xử lý 2FA"
echo "- Kết nối IMAP sau khi đăng nhập thành công"
echo
echo "LƯU Ý: Cần có Chrome browser trên máy!"
echo
echo "========================================"
echo

# Run the Python application
python gmail_browser_login.py

# Check if there was an error
if [ $? -ne 0 ]; then
    echo
    echo "========================================"
    echo "   Có lỗi xảy ra khi chạy ứng dụng!"
    echo "========================================"
    echo
    echo "Các khả năng:"
    echo "1. Thiếu thư viện Python (selenium, webdriver-manager)"
    echo "2. File gmail_browser_login.py bị lỗi"
    echo "3. Python không được cài đặt đúng"
    echo "4. Chrome browser chưa được cài đặt"
    echo
    echo "Giải pháp:"
    echo "1. Cài đặt Chrome browser"
    echo "2. Chạy: source venv/bin/activate && pip install selenium webdriver-manager"
    echo "3. Kiểm tra kết nối internet"
    echo
fi

echo
echo "Ứng dụng đã đóng. Nhấn Enter để thoát..."
read
