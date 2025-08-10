#!/bin/bash
# ArchieOS External Drive Setup Script for ExFAT
# Configures external drive named "Archie" with ExFAT filesystem for ArchieOS storage

set -e

echo "🧠💾 ArchieOS External Drive Setup (ExFAT)"
echo "========================================="
echo ""

# Configuration
DRIVE_LABEL="Archie"
MOUNT_POINT="/mnt/archie"
ARCHIE_USER="pi"  # Change if using different user
FILESYSTEM="exfat"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run this script with sudo${NC}"
    exit 1
fi

# Install ExFAT support if not already installed
echo "📦 Installing ExFAT support..."
apt update
apt install -y exfat-fuse exfat-utils

echo "⚠️  WARNING: This script will prepare an external drive for ArchieOS"
echo "⚠️  Looking for drive labeled 'Archie' or will help you set it up"
echo ""

# Look for existing "Archie" drive
ARCHIE_DEVICE=""
echo "🔍 Searching for existing 'Archie' drive..."
for device in $(lsblk -rno NAME,LABEL | awk '$2=="Archie" {print "/dev/"$1}'); do
    if [ -e "$device" ]; then
        ARCHIE_DEVICE="$device"
        echo "✅ Found existing 'Archie' drive at: $ARCHIE_DEVICE"
        break
    fi
done

if [ -z "$ARCHIE_DEVICE" ]; then
    # List available drives
    echo "📁 Available drives:"
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE
    echo ""

    # Get drive selection
    read -p "Enter the device name (e.g., sda1, sdb1): /dev/" DEVICE_NAME
    ARCHIE_DEVICE="/dev/$DEVICE_NAME"

    # Confirm drive selection
    echo ""
    echo "Selected device: $ARCHIE_DEVICE"
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL | grep -E "^$DEVICE_NAME|NAME"
    echo ""
    echo -e "${YELLOW}⚠️  WARNING: This will format $ARCHIE_DEVICE as ExFAT and label it 'Archie'!${NC}"
    read -p "Are you absolutely sure? Type 'YES' to continue: " CONFIRM

    if [ "$CONFIRM" != "YES" ]; then
        echo "Cancelled. No changes made."
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 1: Formatting drive as ExFAT..."
    # Format as ExFAT with label "Archie"
    mkfs.exfat -n "$DRIVE_LABEL" "$ARCHIE_DEVICE"
    
else
    echo "📋 Using existing 'Archie' drive, skipping format..."
fi


echo ""
echo "📁 Step 2: Creating mount point..."
mkdir -p "$MOUNT_POINT"

echo ""
echo "🔌 Step 3: Mounting drive..."
mount "$ARCHIE_DEVICE" "$MOUNT_POINT"

echo ""
echo "👤 Step 4: Setting permissions..."
chown -R $ARCHIE_USER:$ARCHIE_USER "$MOUNT_POINT"
chmod 755 "$MOUNT_POINT"

echo ""
echo "📝 Step 5: Configuring auto-mount..."
# Get UUID of the drive
UUID=$(blkid -s UUID -o value "$ARCHIE_DEVICE")

# Backup fstab
cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)

# Add to fstab if not already present
if ! grep -q "$UUID" /etc/fstab; then
    echo "UUID=$UUID $MOUNT_POINT exfat defaults,uid=$ARCHIE_USER,gid=$ARCHIE_USER,nofail,x-systemd.device-timeout=5 0 0" >> /etc/fstab
    echo "Added to /etc/fstab"
else
    echo "Drive already in /etc/fstab"
fi

echo ""
echo "🏗️ Step 6: Creating ArchieOS directory structure..."
# Create ArchieOS storage structure
sudo -u $ARCHIE_USER mkdir -p "$MOUNT_POINT/storage"/{uploads,media,memory,plugins,vault,exports,tmp,cold,backups}
sudo -u $ARCHIE_USER mkdir -p "$MOUNT_POINT/storage/plugins"/{calendar,reminders,health,finance,media,journal,research,tasks}
sudo -u $ARCHIE_USER mkdir -p "$MOUNT_POINT/storage/cold/compressed"

# Create subdirectories for each plugin
for plugin in calendar reminders health finance media journal research tasks; do
    sudo -u $ARCHIE_USER mkdir -p "$MOUNT_POINT/storage/plugins/$plugin"/{data,exports,backups,temp}
done

echo ""
echo "🔐 Step 7: Setting up vault directory..."
# Create vault directory (ExFAT doesn't support chmod, so we'll create a note)
sudo -u $ARCHIE_USER mkdir -p "$MOUNT_POINT/storage/vault"
echo "# This directory contains sensitive encrypted files - access restricted" > "$MOUNT_POINT/storage/vault/README.md"

echo ""
echo "📄 Step 8: Creating info file..."
# Create drive info file
cat > "$MOUNT_POINT/ARCHIE_DRIVE_INFO.txt" << EOF
ArchieOS External Storage Drive (ExFAT)
========================================
Created: $(date)
Drive UUID: $UUID
Mount Point: $MOUNT_POINT
Total Size: $(df -h "$MOUNT_POINT" | awk 'NR==2 {print $2}')
Label: $DRIVE_LABEL
Filesystem: ExFAT

Directory Structure:
- storage/uploads/   : Uploaded files
- storage/media/     : General media files
- storage/memory/    : Memory backups
- storage/plugins/   : Plugin-specific storage
- storage/vault/     : Encrypted sensitive files
- storage/exports/   : Export files
- storage/tmp/       : Temporary files
- storage/cold/      : Cold storage archive
- storage/backups/   : System backups

This drive is managed by ArchieOS
EOF

echo ""
echo "🧪 Step 9: Testing mount..."
# Test the mount
if mountpoint -q "$MOUNT_POINT"; then
    echo -e "${GREEN}✅ Drive mounted successfully${NC}"
    df -h "$MOUNT_POINT"
else
    echo -e "${RED}❌ Drive mount failed${NC}"
    exit 1
fi

echo ""
echo "📝 Step 10: Creating ArchieOS configuration..."
# Create config file for ArchieOS
CONFIG_FILE="/home/$ARCHIE_USER/archie/config/external_drive.json"
sudo -u $ARCHIE_USER mkdir -p "/home/$ARCHIE_USER/archie/config"

cat > "$CONFIG_FILE" << EOF
{
  "external_drive": {
    "enabled": true,
    "mount_point": "$MOUNT_POINT",
    "storage_path": "$MOUNT_POINT/storage",
    "drive_uuid": "$UUID",
    "drive_label": "$DRIVE_LABEL",
    "created_at": "$(date -Iseconds)",
    "features": {
      "auto_backup": true,
      "cold_storage": true,
      "compression": true,
      "encryption_ready": true
    }
  }
}
EOF

chown $ARCHIE_USER:$ARCHIE_USER "$CONFIG_FILE"

echo ""
echo "🔄 Step 11: Creating systemd mount monitor..."
# Create systemd service to monitor drive
cat > /etc/systemd/system/archie-drive-monitor.service << EOF
[Unit]
Description=ArchieOS External Drive Monitor
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/bash -c 'while true; do if ! mountpoint -q $MOUNT_POINT; then logger "ArchieOS: External drive not mounted"; fi; sleep 60; done'
Restart=always
User=$ARCHIE_USER

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable archie-drive-monitor.service
systemctl start archie-drive-monitor.service

echo ""
echo -e "${GREEN}✅ ArchieOS External Drive Setup Complete!${NC}"
echo ""
echo "📊 Drive Information:"
echo "   Mount Point: $MOUNT_POINT"
echo "   Storage Path: $MOUNT_POINT/storage"
echo "   Drive UUID: $UUID"
echo "   Total Space: $(df -h "$MOUNT_POINT" | awk 'NR==2 {print $2}')"
echo "   Available: $(df -h "$MOUNT_POINT" | awk 'NR==2 {print $4}')"
echo ""
echo "🚀 Next Steps:"
echo "1. Update ArchieOS configuration to use: $MOUNT_POINT/storage"
echo "2. Restart ArchieOS to use the new storage location"
echo "3. The drive will automatically mount on system boot"
echo ""
echo "💡 To verify the setup:"
echo "   sudo mount -a  # Test fstab entry"
echo "   ls -la $MOUNT_POINT/storage/  # Check directories"
echo ""
echo "🧠💾 ArchieOS is ready for 2TB of memories!"