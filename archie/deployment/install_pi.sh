#!/bin/bash
# Archie Installation Script for Raspberry Pi

set -e

echo "🧠 Installing Archie on Raspberry Pi..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python and system dependencies..."
sudo apt install -y python3 python3-pip python3-venv git sqlite3 nginx

# Create archie user (optional)
if ! id "archie" &>/dev/null; then
    echo "👤 Creating archie user..."
    sudo useradd -m -s /bin/bash archie
fi

# Set up Archie directory
ARCHIE_HOME="/home/archie/archie"
echo "📁 Setting up Archie directory at $ARCHIE_HOME..."

if [ ! -d "$ARCHIE_HOME" ]; then
    sudo -u archie mkdir -p "$ARCHIE_HOME"
fi

# Clone repository
echo "📥 Cloning Archie repository..."
cd /home/archie
if [ -d "archie/.git" ]; then
    echo "Repository exists, pulling latest changes..."
    sudo -u archie git -C archie pull
else
    echo "Cloning new repository..."
    sudo -u archie git clone https://github.com/yourusername/archie.git
fi

# Set up Python environment
echo "🔧 Setting up Python virtual environment..."
cd "$ARCHIE_HOME"
sudo -u archie python3 -m venv .venv
sudo -u archie .venv/bin/pip install --upgrade pip
sudo -u archie .venv/bin/pip install -r requirements.txt

# Create configuration
echo "⚙️ Setting up configuration..."
if [ ! -f "$ARCHIE_HOME/.env" ]; then
    sudo -u archie cp .env.example .env
    echo "📝 Please edit $ARCHIE_HOME/.env with your settings"
fi

# Create directories
sudo -u archie mkdir -p "$ARCHIE_HOME/logs"
sudo -u archie mkdir -p "$ARCHIE_HOME/backups"

# Set up systemd service
echo "🔧 Setting up systemd service..."
sudo tee /etc/systemd/system/archie.service > /dev/null <<EOF
[Unit]
Description=Archie Memory Archivist
After=network.target

[Service]
Type=simple
User=archie
WorkingDirectory=$ARCHIE_HOME
Environment=PATH=$ARCHIE_HOME/.venv/bin
ExecStart=$ARCHIE_HOME/.venv/bin/python run_archie.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable archie
sudo systemctl start archie

# Set up nginx reverse proxy (optional)
echo "🌐 Setting up nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/archie > /dev/null <<EOF
server {
    listen 80;
    server_name archie.local;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/archie /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Set up log rotation
echo "📝 Setting up log rotation..."
sudo tee /etc/logrotate.d/archie > /dev/null <<EOF
$ARCHIE_HOME/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 archie archie
    postrotate
        systemctl reload archie
    endscript
}
EOF

# Final status
echo "✅ Archie installation completed!"
echo ""
echo "🔍 Status check:"
sudo systemctl status archie --no-pager -l
echo ""
echo "📡 Archie should be available at:"
echo "   - http://$(hostname -I | awk '{print $1}'):8090"
echo "   - http://archie.local (if nginx is working)"
echo ""
echo "📋 Useful commands:"
echo "   sudo systemctl status archie    # Check status"
echo "   sudo systemctl logs archie      # View logs"
echo "   sudo systemctl restart archie   # Restart service"
echo "   tail -f $ARCHIE_HOME/logs/archie.log  # Follow logs"
echo ""
echo "🎉 Archie is ready to serve as your memory archivist!"