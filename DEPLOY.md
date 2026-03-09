# 孩子课外课程表助手 - GitHub 部署指南

## 📋 目录

1. [创建 GitHub 仓库](#1-创建-github-仓库)
2. [推送代码到 GitHub](#2-推送代码到-github)
3. [服务器部署](#3-服务器部署)
4. [自动化部署（可选）](#4-自动化部署可选)
5. [常见问题](#5-常见问题)

---

## 1. 创建 GitHub 仓库

### 方法一：通过 GitHub 网站创建

1. 登录 [GitHub](https://github.com)
2. 点击右上角 **+** 号 → **New repository**
3. 填写仓库信息：
   - **Repository name**: `child-schedule-assistant`（或你喜欢的名称）
   - **Description**: 孩子课外课程表助手 - 智能管理孩子的课外课程
   - **Visibility**: 选择 Public（公开）或 Private（私有）
   - **Initialize this repository with**: 不要勾选（已有本地仓库）
4. 点击 **Create repository**

### 方法二：通过 GitHub CLI 创建

```bash
# 安装 GitHub CLI（如果未安装）
# macOS
brew install gh

# 登录 GitHub
gh auth login

# 创建仓库
gh repo create child-schedule-assistant --public --description "孩子课外课程表助手 - 智能管理孩子的课外课程"
```

---

## 2. 推送代码到 GitHub

### 初始化并推送

```bash
# 进入项目目录
cd /Users/qxd/Desktop/TRAE/kechengbiao

# 初始化 Git 仓库（如果尚未初始化）
git init

# 添加所有文件
git add -A

# 提交更改
git commit -m "Initial commit: 孩子课外课程表助手"

# 添加远程仓库（替换 YOUR_USERNAME 为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/child-schedule-assistant.git

# 推送到 GitHub
git push -u origin master
```

### 使用 SSH 推送（推荐）

```bash
# 生成 SSH 密钥（如果尚未生成）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 添加 SSH 密钥到 ssh-agent
ssh-add ~/.ssh/id_ed25519

# 复制公钥到 GitHub
cat ~/.ssh/id_ed25519.pub
# 然后到 GitHub Settings → SSH and GPG keys → New SSH key

# 使用 SSH 地址添加远程仓库
git remote add origin git@github.com:YOUR_USERNAME/child-schedule-assistant.git

# 推送
git push -u origin master
```

---

## 3. 服务器部署

### 3.1 准备服务器

确保服务器满足以下要求：

- **操作系统**: Linux (Ubuntu 20.04+ / CentOS 8+ / Alibaba Cloud Linux 3+)
- **Python**: 3.8 或更高版本
- **内存**: 至少 1GB RAM
- **端口**: 8501（Streamlit 默认端口）

### 3.2 服务器环境配置

#### Ubuntu/Debian

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和依赖
sudo apt install -y python3 python3-pip python3-venv python3-dev

# 安装构建工具
sudo apt install -y build-essential gcc g++

# 安装 Git
sudo apt install -y git
```

#### CentOS/RHEL/Alibaba Cloud Linux

```bash
# 更新系统
sudo yum update -y

# 安装 Python 和依赖
sudo yum install -y python3 python3-pip python3-devel

# 安装构建工具
sudo yum install -y gcc gcc-c++ make

# 安装 Git
sudo yum install -y git
```

### 3.3 从 GitHub 克隆并部署

```bash
# 进入你想要部署的目录
cd /opt

# 克隆仓库（替换 YOUR_USERNAME）
sudo git clone https://github.com/YOUR_USERNAME/child-schedule-assistant.git

# 进入项目目录
cd child-schedule-assistant

# 创建虚拟环境
sudo python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 初始化数据库
python database.py
```

### 3.4 使用 Systemd 管理服务

创建 Streamlit 服务文件：

```bash
sudo tee /etc/systemd/system/schedule-assistant.service > /dev/null <<EOF
[Unit]
Description=Child Schedule Assistant Streamlit App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/child-schedule-assistant
Environment=PATH=/opt/child-schedule-assistant/venv/bin
ExecStart=/opt/child-schedule-assistant/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

创建调度器服务文件：

```bash
sudo tee /etc/systemd/system/schedule-assistant-scheduler.service > /dev/null <<EOF
[Unit]
Description=Child Schedule Assistant Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/child-schedule-assistant
Environment=PATH=/opt/child-schedule-assistant/venv/bin
ExecStart=/opt/child-schedule-assistant/venv/bin/python scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

启动服务：

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable schedule-assistant.service
sudo systemctl enable schedule-assistant-scheduler.service

# 启动服务
sudo systemctl start schedule-assistant.service
sudo systemctl start schedule-assistant-scheduler.service

# 查看状态
sudo systemctl status schedule-assistant.service
sudo systemctl status schedule-assistant-scheduler.service
```

### 3.5 配置 Nginx 反向代理（推荐）

安装 Nginx：

```bash
# Ubuntu/Debian
sudo apt install -y nginx

# CentOS/RHEL
sudo yum install -y nginx
```

创建 Nginx 配置文件：

```bash
sudo tee /etc/nginx/conf.d/schedule-assistant.conf > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或服务器 IP

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF
```

测试并重启 Nginx：

```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 4. 自动化部署（可选）

### 使用 GitHub Actions 自动部署

创建 `.github/workflows/deploy.yml` 文件：

```yaml
name: Deploy to Server

on:
  push:
    branches: [ master, main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        password: ${{ secrets.SERVER_PASSWORD }}
        script: |
          cd /opt/child-schedule-assistant
          git pull origin master
          source venv/bin/activate
          pip install -r requirements.txt
          sudo systemctl restart schedule-assistant
          sudo systemctl restart schedule-assistant-scheduler
```

在 GitHub 仓库设置中添加 Secrets：

1. 进入仓库 → Settings → Secrets and variables → Actions
2. 添加以下 secrets：
   - `SERVER_HOST`: 你的服务器 IP 或域名
   - `SERVER_USER`: 服务器用户名（如 root）
   - `SERVER_PASSWORD`: 服务器密码

---

## 5. 常见问题

### Q1: Python 版本过低怎么办？

如果服务器 Python 版本低于 3.8，可以安装新版本：

```bash
# Ubuntu 20.04+
sudo apt install -y python3.8 python3.8-venv python3.8-dev

# 或者使用 pyenv 安装任意版本
curl https://pyenv.run | bash
pyenv install 3.10.0
pyenv global 3.10.0
```

### Q2: 端口被占用怎么办？

修改 Streamlit 端口：

```bash
# 修改服务文件中的端口
ExecStart=/opt/child-schedule-assistant/venv/bin/streamlit run app.py --server.port 8502 --server.address 0.0.0.0

# 然后重启服务
sudo systemctl daemon-reload
sudo systemctl restart schedule-assistant
```

### Q3: 如何更新代码？

```bash
cd /opt/child-schedule-assistant
sudo git pull origin master
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart schedule-assistant schedule-assistant-scheduler
```

### Q4: 如何查看日志？

```bash
# 查看 Streamlit 日志
sudo journalctl -u schedule-assistant -f

# 查看调度器日志
sudo journalctl -u schedule-assistant-scheduler -f

# 查看所有日志
sudo journalctl -u schedule-assistant* -f
```

### Q5: 如何备份数据？

数据库文件位于项目目录下的 `schedule.db`：

```bash
# 备份
cp /opt/child-schedule-assistant/schedule.db /backup/schedule.db.$(date +%Y%m%d)

# 恢复
cp /backup/schedule.db.20240308 /opt/child-schedule-assistant/schedule.db
sudo systemctl restart schedule-assistant
```

---

## 📚 相关链接

- [Streamlit 文档](https://docs.streamlit.io/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Systemd 文档](https://systemd.io/)

---

## 🆘 获取帮助

如果在部署过程中遇到问题：

1. 查看应用日志：`sudo journalctl -u schedule-assistant -n 50`
2. 检查端口占用：`netstat -tlnp | grep 8501`
3. 测试应用直接运行：`cd /opt/child-schedule-assistant && source venv/bin/activate && streamlit run app.py`
