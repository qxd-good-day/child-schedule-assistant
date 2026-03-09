#!/bin/bash

# 孩子课外课程表助手 - 部署脚本
# 用法: ./deploy.sh

set -e

echo "🚀 开始部署课程表助手..."

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python3${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python3 已安装${NC}"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 初始化数据库
echo "初始化数据库..."
python database.py

echo -e "${GREEN}✓ 数据库初始化完成${NC}"

# 创建 systemd 服务文件（可选）
if command -v systemctl &> /dev/null; then
    echo "创建系统服务..."
    
    # 获取当前目录
    CURRENT_DIR=$(pwd)
    USER=$(whoami)
    
    # 创建 streamlit 服务
    cat > /tmp/schedule-assistant-streamlit.service << EOF
[Unit]
Description=Schedule Assistant Streamlit App
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # 创建 scheduler 服务
    cat > /tmp/schedule-assistant-scheduler.service << EOF
[Unit]
Description=Schedule Assistant Scheduler
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo -e "${YELLOW}系统服务文件已创建:${NC}"
    echo "  - /tmp/schedule-assistant-streamlit.service"
    echo "  - /tmp/schedule-assistant-scheduler.service"
    echo ""
    echo "要安装服务，请运行:"
    echo "  sudo cp /tmp/schedule-assistant-*.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable schedule-assistant