#!/bin/bash
# Archie Installation Script for Raspberry Pi with ExFAT Drive Support

set -e

echo "🧠 Installing Archie on Raspberry Pi with ExFAT Drive Support..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies including ExFAT support
echo "🐍 Installing Python, system dependencies, and ExFAT support..."
sudo apt install -y python3 python3-pip python3-venv git sqlite3 nginx exfat-fuse exfat-utils tesseract-ocr tesseract-ocr-eng python3-magic

# Install additional packages for OCR and processing
echo "📚 Installing additional processing libraries..."
sudo apt install -y libmagic1 poppler-utils imagemagick

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
    sudo -u archie tee "$ARCHIE_HOME/.env" > /dev/null <<EOF
# ArchieOS Configuration
ARCHIE_API_PORT=8090
ARCHIE_DATABASE_PATH=database/memory.db
ARCHIE_PERSONALITY_MODE=content
ARCHIE_AUTO_ARCHIVE_DAYS=90
ARCHIE_LOG_LEVEL=INFO
ARCHIE_SECRET_KEY=your-secret-key-here-change-this
ARCHIE_CORS_ORIGINS=*
ARCHIE_DATA_ROOT=/mnt/archie/storage
ARCHIE_EXTERNAL_DRIVE_ENABLED=true
ARCHIE_EXTERNAL_DRIVE_PATH=/mnt/archie
EOF
    echo "📝 Configuration created. Please update the secret key and other settings as needed."
fi

# Create directories
sudo -u archie mkdir -p "$ARCHIE_HOME/logs"
sudo -u archie mkdir -p "$ARCHIE_HOME/backups"

# Set up external drive detection and mounting
echo "💾 Setting up ExFAT drive detection..."
sudo tee /usr/local/bin/archie-mount-drive.sh > /dev/null <<'EOF'
#!/bin/bash
# Auto-mount script for Archie ExFAT drive

MOUNT_POINT="/mnt/archie"
LOG_FILE="/var/log/archie-mount.log"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    mkdir -p "$MOUNT_POINT"
fi

# Look for drive labeled "Archie"
ARCHIE_DEVICE=$(lsblk -rno NAME,LABEL | awk '$2=="Archie" {print "/dev/"$1}' | head -1)

if [ -n "$ARCHIE_DEVICE" ] && [ -e "$ARCHIE_DEVICE" ]; then
    # Check if already mounted
    if ! mountpoint -q "$MOUNT_POINT"; then
        log_message "Mounting Archie drive: $ARCHIE_DEVICE"
        if mount "$ARCHIE_DEVICE" "$MOUNT_POINT"; then
            log_message "Successfully mounted Archie drive"
            chown archie:archie "$MOUNT_POINT"
        else
            log_message "Failed to mount Archie drive"
        fi
    else
        log_message "Archie drive already mounted"
    fi
else
    log_message "Archie drive not found"
fi
EOF

chmod +x /usr/local/bin/archie-mount-drive.sh

# Set up systemd service
echo "🔧 Setting up systemd service..."
sudo tee /etc/systemd/system/archie.service > /dev/null <<EOF
[Unit]
Description=Archie Memory Archivist
After=network.target multi-user.target
Wants=archie-mount.service

[Service]
Type=simple
User=archie
WorkingDirectory=$ARCHIE_HOME
Environment=PATH=$ARCHIE_HOME/.venv/bin
ExecStartPre=/usr/local/bin/archie-mount-drive.sh
ExecStart=$ARCHIE_HOME/.venv/bin/python run_archie.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set up drive mounting service
sudo tee /etc/systemd/system/archie-mount.service > /dev/null <<EOF
[Unit]
Description=Mount Archie ExFAT Drive
DefaultDependencies=false
After=systemd-udev-settle.service
Before=local-fs.target
Wants=systemd-udev-settle.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/archie-mount-drive.sh
RemainAfterExit=true

[Install]
WantedBy=local-fs.target
EOF

# Set up drive monitor service
sudo tee /etc/systemd/system/archie-drive-monitor.service > /dev/null <<EOF
[Unit]
Description=ArchieOS External Drive Monitor
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/bash -c 'while true; do if ! mountpoint -q /mnt/archie; then /usr/local/bin/archie-mount-drive.sh; fi; sleep 30; done'
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable archie-mount.service
sudo systemctl enable archie.service
sudo systemctl enable archie-drive-monitor.service

# Try to mount drive now
echo "💾 Attempting to mount Archie drive..."
/usr/local/bin/archie-mount-drive.sh

# Start services
sudo systemctl start archie-mount.service
sudo systemctl start archie-drive-monitor.service
sudo systemctl start archie.service

# Set up nginx reverse proxy (optional)
echo "🌐 Setting up nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/archie > /dev/null <<EOF
server {
    listen 80;
    server_name archie.local _;

    # Increase client max body size for file uploads
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/archie /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
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

/var/log/archie-mount.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

# Create udev rule for automatic drive mounting
echo "🔌 Setting up udev rule for automatic drive detection..."
sudo tee /etc/udev/rules.d/99-archie-drive.rules > /dev/null <<EOF
# Automatically mount Archie ExFAT drive
SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="Archie", ENV{ID_FS_TYPE}=="exfat", ACTION=="add", RUN+="/usr/local/bin/archie-mount-drive.sh"
EOF

# Reload udev rules
sudo udevadm control --reload-rules

# Final status
echo "✅ Archie installation completed!"
echo ""
echo "🔍 Status check:"
sudo systemctl status archie --no-pager -l || true
echo ""
echo "💾 Drive status:"
if mountpoint -q /mnt/archie; then
    echo "   ✅ Archie drive mounted at /mnt/archie"
    df -h /mnt/archie
else
    echo "   ⚠️  Archie drive not mounted. Connect your ExFAT drive labeled 'Archie'"
fi
echo ""
echo "📡 Archie should be available at:"
echo "   - http://$(hostname -I | awk '{print $1}'):8090"
echo "   - http://archie.local (if nginx is working)"
echo ""
echo "📋 Useful commands:"
echo "   sudo systemctl status archie              # Check status"
echo "   sudo journalctl -u archie -f              # View logs"
echo "   sudo systemctl restart archie             # Restart service"
echo "   /usr/local/bin/archie-mount-drive.sh      # Manual drive mount"
echo "   sudo systemctl status archie-mount        # Check drive mount service"
echo ""
echo "🎉 Archie is ready to serve as your memory archivist with ExFAT support!"
echo "💡 Make sure your external drive is labeled 'Archie' and formatted as ExFAT"