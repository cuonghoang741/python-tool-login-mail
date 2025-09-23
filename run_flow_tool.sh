#!/bin/bash

echo "========================================"
echo "   Google Flow Tool - Starting..."
echo "========================================"
echo

cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
  echo "ERROR: Python chưa được cài đặt!"
  echo "Vui lòng cài đặt Python từ: https://www.python.org/downloads/"
  exit 1
fi

if [ ! -f "flow_browser_tool.py" ]; then
  echo "ERROR: Không tìm thấy flow_browser_tool.py"
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "Tạo virtual environment..."
  python3 -m venv venv
fi

echo "Kích hoạt môi trường và cài đặt thư viện..."
source venv/bin/activate
pip install --quiet selenium webdriver-manager

echo
echo "Khởi động ứng dụng Google Flow Tool..."
python flow_browser_tool.py

status=$?
if [ $status -ne 0 ]; then
  echo "Ứng dụng lỗi với mã $status"
  exit $status
fi

echo "Hoàn tất."


