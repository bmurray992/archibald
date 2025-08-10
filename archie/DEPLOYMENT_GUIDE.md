# 🚀 ArchieOS Deployment Guide

Complete guide for deploying ArchieOS on Raspberry Pi with ExFAT external drive support.

## 📋 Prerequisites

### Hardware Requirements
- **Raspberry Pi 4** (recommended) or Raspberry Pi 3B+
- **External drive** labeled "Archie" formatted as ExFAT
- **MicroSD card** (32GB+ recommended)
- **Internet connection** (WiFi or Ethernet)

### Software Requirements
- **Raspberry Pi OS** (Bullseye or newer)
- **Python 3.9+** (included with Pi OS)
- **Internet access** for package installation

## 🔧 Quick Setup

### Option 1: Automatic Installation (Recommended)

```bash
# Download and run the automated installer
curl -fsSL https://raw.githubusercontent.com/yourusername/archie/main/deployment/install_pi_exfat.sh | sudo bash

# Or if you have the repository locally:
cd archie/deployment
sudo ./install_pi_exfat.sh
```

This script will:
- Install all dependencies including ExFAT support
- Set up automatic drive mounting
- Configure systemd services
- Set up nginx reverse proxy
- Configure monitoring and logging

### Option 2: Manual Installation

Follow the [Manual Installation](#manual-installation) section below.

## 💾 External Drive Setup

### Drive Requirements
- **Label**: Must be labeled "Archie" (case sensitive)
- **Filesystem**: ExFAT (for cross-platform compatibility)
- **Size**: 2TB recommended, 1TB minimum

### Format Your Drive

#### On Windows:
1. Open Disk Management
2. Right-click your drive → Format
3. **File system**: ExFAT
4. **Volume label**: Archie
5. Click Start

#### On macOS:
1. Open Disk Utility
2. Select your drive
3. Click Erase
4. **Format**: ExFAT
5. **Name**: Archie
6. Click Erase

#### On Linux:
```bash
# Find your drive (replace sdX1 with your actual device)
lsblk

# Format as ExFAT with label "Archie"
sudo mkfs.exfat -n "Archie" /dev/sdX1
```

### Automatic Drive Setup Script

If your drive needs setup or isn't labeled correctly:

```bash
cd archie/deployment
sudo ./setup_external_drive.sh
```

This will:
- Install ExFAT support
- Find or format your drive as "Archie"
- Create the ArchieOS directory structure
- Configure automatic mounting

## 🏗️ Manual Installation

If you prefer to install manually or need to customize the setup:

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git sqlite3 nginx \
    exfat-fuse exfat-utils tesseract-ocr tesseract-ocr-eng \
    python3-magic libmagic1 poppler-utils imagemagick
```

### Step 2: Create User and Directory

```bash
# Create archie user (optional)
sudo useradd -m -s /bin/bash archie

# Set up directory
sudo -u archie mkdir -p /home/archie/archie
cd /home/archie
sudo -u archie git clone https://github.com/yourusername/archie.git
```

### Step 3: Python Environment

```bash
cd /home/archie/archie
sudo -u archie python3 -m venv .venv
sudo -u archie .venv/bin/pip install --upgrade pip
sudo -u archie .venv/bin/pip install -r requirements.txt
```

### Step 4: Configuration

```bash
# Create environment configuration
sudo -u archie tee .env > /dev/null <<EOF
ARCHIE_API_PORT=8090
ARCHIE_DATABASE_PATH=database/memory.db
ARCHIE_PERSONALITY_MODE=content
ARCHIE_AUTO_ARCHIVE_DAYS=90
ARCHIE_LOG_LEVEL=INFO
ARCHIE_SECRET_KEY=$(openssl rand -base64 32)
ARCHIE_CORS_ORIGINS=*
ARCHIE_DATA_ROOT=/mnt/archie/storage
ARCHIE_EXTERNAL_DRIVE_ENABLED=true
ARCHIE_EXTERNAL_DRIVE_PATH=/mnt/archie
EOF
```

### Step 5: Drive Mounting

Create automatic drive mounting script:

```bash
sudo tee /usr/local/bin/archie-mount-drive.sh > /dev/null <<'EOF'
#!/bin/bash
MOUNT_POINT="/mnt/archie"
mkdir -p "$MOUNT_POINT"
ARCHIE_DEVICE=$(lsblk -rno NAME,LABEL | awk '$2=="Archie" {print "/dev/"$1}' | head -1)
if [ -n "$ARCHIE_DEVICE" ] && [ -e "$ARCHIE_DEVICE" ]; then
    if ! mountpoint -q "$MOUNT_POINT"; then
        mount "$ARCHIE_DEVICE" "$MOUNT_POINT"
        chown archie:archie "$MOUNT_POINT"
    fi
fi
EOF

sudo chmod +x /usr/local/bin/archie-mount-drive.sh
```

### Step 6: Systemd Services

Create the main service:

```bash
sudo tee /etc/systemd/system/archie.service > /dev/null <<EOF
[Unit]
Description=Archie Memory Archivist
After=network.target multi-user.target
Wants=archie-mount.service

[Service]
Type=simple
User=archie
WorkingDirectory=/home/archie/archie
Environment=PATH=/home/archie/archie/.venv/bin
ExecStartPre=/usr/local/bin/archie-mount-drive.sh
ExecStart=/home/archie/archie/.venv/bin/python run_archie.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

Create drive monitoring service:

```bash
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
```

Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable archie.service
sudo systemctl enable archie-drive-monitor.service
sudo systemctl start archie-drive-monitor.service
sudo systemctl start archie.service
```

### Step 7: Nginx Configuration

```bash
sudo tee /etc/nginx/sites-available/archie > /dev/null <<EOF
server {
    listen 80;
    server_name archie.local _;
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
```

## 🔍 Verification and Testing

### Check System Status

```bash
# Check ArchieOS service
sudo systemctl status archie

# Check drive mounting
df -h | grep archie
mountpoint -q /mnt/archie && echo "Drive mounted" || echo "Drive not mounted"

# Check logs
sudo journalctl -u archie -f

# Test API endpoint
curl http://localhost:8090/health
```

### Test Drive Access

```bash
# Check drive contents
ls -la /mnt/archie/storage/

# Test write access
sudo -u archie touch /mnt/archie/test.txt
sudo -u archie rm /mnt/archie/test.txt
```

### Web Interface

Open in browser:
- `http://YOUR_PI_IP:8090` (direct access)
- `http://archie.local` (if mDNS is working)

Default login: `admin` / `admin`

## 🛠️ Troubleshooting

### Common Issues

#### Drive Not Mounting

```bash
# Check if drive is connected
lsblk -o NAME,LABEL,FSTYPE

# Manual mount attempt
sudo /usr/local/bin/archie-mount-drive.sh

# Check mount logs
tail -f /var/log/archie-mount.log
```

#### Service Not Starting

```bash
# Check detailed logs
sudo journalctl -u archie -n 50

# Check Python environment
sudo -u archie /home/archie/archie/.venv/bin/python --version

# Test manual start
sudo -u archie /home/archie/archie/.venv/bin/python /home/archie/archie/run_archie.py
```

#### ExFAT Support Missing

```bash
# Install ExFAT support
sudo apt update
sudo apt install -y exfat-fuse exfat-utils
```

#### Database Issues

```bash
# Check database file
ls -la /home/archie/archie/database/memory.db

# Run migrations
cd /home/archie/archie
sudo -u archie .venv/bin/python -c "from migrations.001_unified_entities import migrate; migrate()"
```

### Log Files

- **Service logs**: `sudo journalctl -u archie`
- **Drive mount logs**: `/var/log/archie-mount.log`
- **Application logs**: `/home/archie/archie/logs/`
- **Nginx logs**: `/var/log/nginx/`

### Reset Installation

If you need to start over:

```bash
# Stop services
sudo systemctl stop archie archie-drive-monitor
sudo systemctl disable archie archie-drive-monitor

# Remove files
sudo rm -f /etc/systemd/system/archie*.service
sudo rm -f /usr/local/bin/archie-mount-drive.sh
sudo rm -rf /home/archie/archie

# Remove user (optional)
sudo userdel -r archie
```

## 🔧 Configuration Options

### Environment Variables

Edit `/home/archie/archie/.env`:

```bash
# API Configuration
ARCHIE_API_PORT=8090                    # Port for API server
ARCHIE_CORS_ORIGINS=*                   # CORS origins

# Storage Configuration  
ARCHIE_DATA_ROOT=/mnt/archie/storage    # Main storage path
ARCHIE_EXTERNAL_DRIVE_ENABLED=true     # Enable external drive
ARCHIE_EXTERNAL_DRIVE_PATH=/mnt/archie  # Drive mount point

# Database
ARCHIE_DATABASE_PATH=database/memory.db # Database file path

# Behavior
ARCHIE_PERSONALITY_MODE=content         # Personality mode
ARCHIE_AUTO_ARCHIVE_DAYS=90            # Auto-archive after days
ARCHIE_LOG_LEVEL=INFO                  # Logging level

# Security
ARCHIE_SECRET_KEY=your-secret-key      # JWT secret key
```

### Council Integration

For multi-AI Council setup, configure:

```bash
# Add to .env
ARCHIE_COUNCIL_ENABLED=true
ARCHIE_COUNCIL_MEMBER_ID=archie
ARCHIE_COUNCIL_ROLE=archivist
ARCHIE_COUNCIL_CAPABILITIES=memory,storage,analysis
```

## 🎯 Performance Optimization

### For Raspberry Pi 4 (4GB+)

```bash
# Increase memory limits in .env
ARCHIE_MAX_MEMORY_MB=1024
ARCHIE_MAX_WORKERS=4
ARCHIE_BATCH_SIZE=100
```

### For Raspberry Pi 3B+

```bash
# Conservative settings
ARCHIE_MAX_MEMORY_MB=512
ARCHIE_MAX_WORKERS=2
ARCHIE_BATCH_SIZE=50
```

### Storage Optimization

```bash
# Enable compression for cold storage
ARCHIE_COMPRESSION_ENABLED=true
ARCHIE_COMPRESSION_LEVEL=6

# Auto-tier storage
ARCHIE_AUTO_TIER_DAYS=30
```

## 🔐 Security Considerations

### Change Default Credentials

1. Access web interface
2. Go to Settings → Security
3. Update admin password
4. Create additional users as needed

### Secure API Access

```bash
# Generate new secret key
openssl rand -base64 32

# Update .env file
ARCHIE_SECRET_KEY=your-new-secret-key
```

### Network Security

```bash
# Configure nginx with SSL (optional)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d archie.local
```

## 📚 Additional Resources

### Service Management

```bash
# Start/stop/restart
sudo systemctl start archie
sudo systemctl stop archie
sudo systemctl restart archie

# Enable/disable autostart
sudo systemctl enable archie
sudo systemctl disable archie

# View status and logs
sudo systemctl status archie
sudo journalctl -u archie -f
```

### Backup and Restore

```bash
# Create backup
curl -X POST http://localhost:8090/backup/create

# List backups
curl http://localhost:8090/backup/list

# Download backup
curl -O http://localhost:8090/backup/download/backup_id
```

### Updates

```bash
# Update code
cd /home/archie/archie
sudo -u archie git pull
sudo -u archie .venv/bin/pip install -r requirements.txt
sudo systemctl restart archie
```

## 🎉 Success!

You now have ArchieOS running on your Raspberry Pi with:

- ✅ ExFAT external drive support
- ✅ Automatic drive mounting and monitoring  
- ✅ Web interface at `http://archie.local`
- ✅ RESTful API at port 8090
- ✅ OCR and enrichment pipelines
- ✅ Council integration ready
- ✅ Automatic backups and archiving
- ✅ Systemd service management

ArchieOS is now ready to serve as your intelligent memory archivist! 🧠💾

## 📞 Support

For issues and questions:
- Check the troubleshooting section above
- Review logs: `sudo journalctl -u archie`
- Test basic functionality: `curl http://localhost:8090/health`
- Verify drive mount: `mountpoint /mnt/archie`

Happy archiving! 📁✨