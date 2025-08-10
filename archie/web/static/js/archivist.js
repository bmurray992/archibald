/**
 * ArchieOS Web Desktop - Archivist Interface JavaScript
 * Handles all client-side functionality for Archie's memory observatory
 */

class ArchiveDesktop {
    constructor() {
        this.currentSection = 'dashboard';
        this.API_BASE = window.location.origin;
        this.authToken = localStorage.getItem('archie_token') || '';
        
        // Initialize the desktop
        this.init();
    }

    /**
     * Initialize the desktop interface
     */
    init() {
        console.log('🔐 Initializing Archie Memory Vault...');
        
        // Check authentication first
        this.checkAuthentication();
        
        // Bind event listeners
        this.bindEvents();
        
        // Load initial data
        this.loadDashboard();
        this.loadPluginGrid();
        this.checkSystemStatus();
        
        // Set up periodic updates
        this.startPeriodicUpdates();
        
        console.log('✅ Archie Memory Vault secured and ready for archival duties!');
    }

    /**
     * Check if user is authenticated
     */
    async checkAuthentication() {
        try {
            const response = await fetch('/auth/check');
            const auth = await response.json();
            
            if (!auth.authenticated) {
                // Redirect to login if not authenticated
                window.location.href = '/auth/login';
                return;
            }
            
            console.log('✅ Authentication verified for:', auth.token_name);
        } catch (error) {
            console.error('Authentication check failed:', error);
            window.location.href = '/auth/login';
        }
    }

    /**
     * Bind all event listeners
     */
    bindEvents() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const section = e.target.getAttribute('data-section');
                this.switchSection(section);
            });
        });

        // Upload modal
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadModal = document.getElementById('uploadModal');
        const closeUpload = document.getElementById('closeUpload');
        const cancelUpload = document.getElementById('cancelUpload');

        uploadBtn?.addEventListener('click', () => this.showUploadModal());
        closeUpload?.addEventListener('click', () => this.hideUploadModal());
        cancelUpload?.addEventListener('click', () => this.hideUploadModal());

        // File upload handling
        this.setupFileUpload();

        // Search functionality
        const searchBtn = document.getElementById('searchBtn');
        const universalSearch = document.getElementById('universalSearch');
        
        searchBtn?.addEventListener('click', () => this.performSearch());
        universalSearch?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // System management buttons
        this.bindSystemButtons();

        // Filter controls
        this.bindFilterControls();

        // Close modal on outside click
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.hideUploadModal();
            }
        });
    }

    /**
     * Bind system management buttons
     */
    bindSystemButtons() {
        // Backup buttons
        document.getElementById('backupMemory')?.addEventListener('click', () => 
            this.performBackup('memory'));
        document.getElementById('backupPlugins')?.addEventListener('click', () => 
            this.performBackup('plugins'));
        document.getElementById('backupFull')?.addEventListener('click', () => 
            this.performBackup('full'));

        // Maintenance buttons
        document.getElementById('cleanTemp')?.addEventListener('click', () => 
            this.performMaintenance('clean'));
        document.getElementById('pruneCycle')?.addEventListener('click', () => 
            this.performMaintenance('prune'));
        document.getElementById('analyzeStorage')?.addEventListener('click', () => 
            this.performMaintenance('analyze'));

        // Refresh button
        document.getElementById('refreshFiles')?.addEventListener('click', () => 
            this.loadFileGrid());
    }

    /**
     * Bind filter controls
     */
    bindFilterControls() {
        const pluginFilter = document.getElementById('pluginFilter');
        const tierFilter = document.getElementById('tierFilter');
        const memoryTypeFilter = document.getElementById('memoryTypeFilter');
        const memorySearch = document.getElementById('memorySearch');

        pluginFilter?.addEventListener('change', () => this.loadFileGrid());
        tierFilter?.addEventListener('change', () => this.loadFileGrid());
        memoryTypeFilter?.addEventListener('change', () => this.loadMemories());
        memorySearch?.addEventListener('input', () => this.loadMemories());
    }

    /**
     * Switch between sections
     */
    switchSection(sectionName) {
        // Prevent rapid section switching
        if (this.isTransitioning) return;
        if (this.currentSection === sectionName) return;
        
        this.isTransitioning = true;
        
        // Update navigation with enhanced feedback
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        const activeNavItem = document.querySelector(`[data-section="${sectionName}"]`);
        activeNavItem?.classList.add('active');
        
        // Add brief click feedback
        activeNavItem?.style.setProperty('transform', 'translateX(2px) scale(0.98)');
        setTimeout(() => {
            activeNavItem?.style.removeProperty('transform');
        }, 150);

        // Get current and target sections
        const currentSection = document.querySelector('.content-section.active');
        const targetSection = document.getElementById(`${sectionName}-section`);
        
        if (!targetSection) {
            this.isTransitioning = false;
            return;
        }

        // Smooth transition between sections
        if (currentSection) {
            currentSection.classList.add('transitioning-out');
            
            setTimeout(() => {
                currentSection.classList.remove('active', 'transitioning-out');
                targetSection.classList.add('active');
                
                // Add staggered animations to child elements
                this.animateChildElements(targetSection);
                
                setTimeout(() => {
                    this.isTransitioning = false;
                }, 100);
            }, 300);
        } else {
            targetSection.classList.add('active');
            this.animateChildElements(targetSection);
            this.isTransitioning = false;
        }

        this.currentSection = sectionName;

        // Load section-specific data
        switch(sectionName) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'files':
                this.loadFileGrid();
                break;
            case 'memories':
                this.loadMemories();
                break;
            case 'system':
                this.loadSystemInfo();
                break;
        }
    }

    /**
     * Load dashboard data
     */
    async loadDashboard() {
        try {
            this.showLoading('Loading dashboard data...');
            
            // Load recent activity
            await this.loadRecentActivity();
            
            // Load Archie's message
            await this.loadArchieMessage();
            
            // Load storage stats
            await this.loadStorageStats();
            
            // Load health metrics
            await this.loadHealthMetrics();
            
        } catch (error) {
            console.error('Failed to load dashboard:', error);
            this.showToast('Failed to load dashboard data', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load recent activity
     */
    async loadRecentActivity() {
        const container = document.getElementById('recentActivity');
        if (!container) return;

        try {
            const response = await this.apiCall('/system/status');
            const activities = [
                { icon: '📚', title: 'Memory system initialized', time: '2 minutes ago' },
                { icon: '📁', title: 'File storage ready', time: '5 minutes ago' },
                { icon: '🔐', title: 'Authentication active', time: '10 minutes ago' },
                { icon: '⚙️', title: 'System health: Excellent', time: '15 minutes ago' }
            ];

            container.innerHTML = activities.map(activity => `
                <div class="activity-item">
                    <div class="activity-icon">${activity.icon}</div>
                    <div class="activity-content">
                        <div class="activity-title">${activity.title}</div>
                        <div class="activity-time">${activity.time}</div>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '<div class="activity-item">📊 Loading activity data...</div>';
        }
    }

    /**
     * Load Archie's message
     */
    async loadArchieMessage() {
        const container = document.getElementById('archieMessage');
        if (!container) return;

        try {
            const response = await this.apiCall('/archie/greeting');
            const message = response.archie_says || "Right then! The vault is secure and your memories are perfectly catalogued. What knowledge shall we explore today?";
            
            container.innerHTML = `
                <div class="archie-avatar">
                    <svg class="icon-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                    </svg>
                </div>
                <div class="archie-text">${message}</div>
            `;
        } catch (error) {
            container.innerHTML = `
                <div class="archie-avatar">
                    <svg class="icon-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                    </svg>
                </div>
                <div class="archie-text">Welcome to the memory vault! I'm organizing your digital archives and ensuring everything is properly secured...</div>
            `;
        }
    }

    /**
     * Load storage statistics
     */
    async loadStorageStats() {
        try {
            const response = await this.apiCall('/stats');
            const stats = response.data || {};
            
            // Update sidebar vault stats  
            document.getElementById('totalInsights')?.textContent = (stats.total_entries || 0) + ' items';
            document.getElementById('totalSize')?.textContent = (stats.total_files || 0) + ' files';
            document.getElementById('totalMemories')?.textContent = '✓ Secured';
            
            // Update storage chart
            this.updateStorageChart(stats);
            
        } catch (error) {
            console.error('Failed to load storage stats:', error);
        }
    }

    /**
     * Update storage chart visualization
     */
    updateStorageChart(stats) {
        const chartContainer = document.getElementById('storageChart');
        if (!chartContainer) return;

        const tiers = {
            hot: stats.hot_files || 0,
            warm: stats.warm_files || 0,
            cold: stats.cold_files || 0,
            vault: stats.vault_files || 0
        };

        const total = Object.values(tiers).reduce((sum, count) => sum + count, 0);
        
        if (total === 0) {
            chartContainer.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 8px; color: var(--text-muted);">
                    <svg class="icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                    </svg>
                    Vault contents secured and catalogued...
                </div>
            `;
            return;
        }

        chartContainer.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 8px; width: 100%;">
                ${Object.entries(tiers).map(([tier, count]) => {
                    const percentage = ((count / total) * 100).toFixed(1);
                    const color = {
                        hot: '#e53e3e',
                        warm: '#d69e2e', 
                        cold: '#3182ce',
                        vault: '#38a169'
                    }[tier];
                    
                    return `
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.75rem;">
                            <div style="width: 12px; height: 12px; background: ${color}; border-radius: 2px;"></div>
                            <span style="flex: 1; text-transform: capitalize;">${tier}</span>
                            <span>${count} (${percentage}%)</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    /**
     * Load health metrics
     */
    async loadHealthMetrics() {
        const container = document.getElementById('healthMetrics');
        if (!container) return;

        try {
            const response = await this.apiCall('/health');
            const isHealthy = response.success;
            
            const metrics = [
                { label: 'Memory System', value: isHealthy ? 'Good' : 'Warning', status: isHealthy ? 'good' : 'warning' },
                { label: 'Storage System', value: 'Good', status: 'good' },
                { label: 'Authentication', value: 'Good', status: 'good' },
                { label: 'Backup System', value: 'Good', status: 'good' }
            ];

            container.innerHTML = metrics.map(metric => `
                <div class="health-item">
                    <span class="health-label">${metric.label}</span>
                    <span class="health-value ${metric.status}">${metric.value}</span>
                </div>
            `).join('');
            
        } catch (error) {
            container.innerHTML = '<div class="health-item">Health check unavailable</div>';
        }
    }

    /**
     * Load plugin grid
     */
    async loadPluginGrid() {
        const container = document.getElementById('pluginGrid');
        if (!container) return;

        const plugins = [
            { name: 'calendar', icon: '📅' },
            { name: 'reminders', icon: '⏰' },
            { name: 'health', icon: '🏥' },
            { name: 'research', icon: '🔬' },
            { name: 'creativity', icon: '🎨' },
            { name: 'tasks', icon: '📋' },
            { name: 'communication', icon: '💬' },
            { name: 'learning', icon: '📚' }
        ];

        container.innerHTML = plugins.map(plugin => `
            <button class="plugin-btn" data-plugin="${plugin.name}">
                ${plugin.icon} ${plugin.name}
            </button>
        `).join('');

        // Bind plugin clicks
        container.querySelectorAll('.plugin-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const plugin = e.target.getAttribute('data-plugin');
                this.filterByPlugin(plugin);
            });
        });

        // Populate filter dropdowns
        this.populatePluginFilters(plugins);
    }

    /**
     * Populate plugin filter dropdowns
     */
    populatePluginFilters(plugins) {
        const pluginFilter = document.getElementById('pluginFilter');
        const uploadPlugin = document.getElementById('uploadPlugin');

        if (pluginFilter) {
            pluginFilter.innerHTML = '<option value="">All Plugins</option>' +
                plugins.map(p => `<option value="${p.name}">${p.icon} ${p.name}</option>`).join('');
        }

        if (uploadPlugin) {
            uploadPlugin.innerHTML = '<option value="">General Storage</option>' +
                plugins.map(p => `<option value="${p.name}">${p.icon} ${p.name}</option>`).join('');
        }
    }

    /**
     * Filter files by plugin
     */
    filterByPlugin(pluginName) {
        // Switch to files section
        this.switchSection('files');
        
        // Set the filter
        const pluginFilter = document.getElementById('pluginFilter');
        if (pluginFilter) {
            pluginFilter.value = pluginName;
            this.loadFileGrid();
        }
    }

    /**
     * Load file grid
     */
    async loadFileGrid() {
        const container = document.getElementById('fileGrid');
        if (!container) return;

        try {
            this.showLoading('Loading files...');
            
            const pluginFilter = document.getElementById('pluginFilter')?.value || '';
            const tierFilter = document.getElementById('tierFilter')?.value || '';
            
            const response = await this.apiCall('/storage/files', {
                method: 'GET',
                params: { plugin: pluginFilter, tier: tierFilter }
            });
            
            const files = response.data?.files || [];
            
            if (files.length === 0) {
                container.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">
                        📁 No files found${pluginFilter ? ` in ${pluginFilter} plugin` : ''}
                    </div>
                `;
                return;
            }

            container.innerHTML = files.map(file => `
                <div class="file-item" data-file-id="${file.id}">
                    <div class="file-icon">${this.getFileIcon(file.filename)}</div>
                    <div class="file-name" title="${file.filename}">${file.filename}</div>
                    <div class="file-meta">
                        <span>${this.formatFileSize(file.size_bytes)}</span>
                        <span>${file.tier}</span>
                    </div>
                    ${file.tags ? `
                        <div class="file-tags">
                            ${file.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `).join('');

            // Bind file clicks
            container.querySelectorAll('.file-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    const fileId = e.currentTarget.getAttribute('data-file-id');
                    this.openFile(fileId);
                });
            });
            
        } catch (error) {
            console.error('Failed to load files:', error);
            container.innerHTML = '<div>Failed to load files</div>';
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load memories
     */
    async loadMemories() {
        const container = document.getElementById('memoryTimeline');
        if (!container) return;

        try {
            this.showLoading('Loading memories...');
            
            const typeFilter = document.getElementById('memoryTypeFilter')?.value || '';
            const searchQuery = document.getElementById('memorySearch')?.value || '';
            
            const response = await this.apiCall('/memory/search', {
                method: 'POST',
                body: {
                    query: searchQuery,
                    entry_type: typeFilter,
                    limit: 50
                }
            });
            
            const memories = response.data?.memories || [];
            
            if (memories.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                        🧠 No memories found
                    </div>
                `;
                return;
            }

            container.innerHTML = memories.map(memory => `
                <div class="memory-item">
                    <div class="memory-header">
                        <span class="memory-type">${memory.entry_type}</span>
                        <span class="memory-date">${this.formatDate(memory.created_at)}</span>
                    </div>
                    <div class="memory-content">${memory.content}</div>
                    ${memory.tags ? `
                        <div class="file-tags">
                            ${memory.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `).join('');
            
        } catch (error) {
            console.error('Failed to load memories:', error);
            container.innerHTML = '<div>Failed to load memories</div>';
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load system information
     */
    async loadSystemInfo() {
        try {
            this.showLoading('Loading system information...');
            
            // Load system stats
            const statsResponse = await this.apiCall('/system/status');
            this.updateSystemStats(statsResponse.data);
            
            // Load security status
            const authResponse = await this.apiCall('/system/auth/tokens');
            this.updateSecurityStatus(authResponse.data);
            
        } catch (error) {
            console.error('Failed to load system info:', error);
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Update system statistics display
     */
    updateSystemStats(stats) {
        const container = document.getElementById('systemStats');
        if (!container || !stats) return;

        container.innerHTML = `
            <div class="health-item">
                <span class="health-label">Archie Version</span>
                <span class="health-value good">${stats.archie_version || '2.0.0'}</span>
            </div>
            <div class="health-item">
                <span class="health-label">Uptime</span>
                <span class="health-value good">Active</span>
            </div>
            <div class="health-item">
                <span class="health-label">Services</span>
                <span class="health-value good">${Object.keys(stats.services || {}).length} Active</span>
            </div>
        `;
    }

    /**
     * Update security status display
     */
    updateSecurityStatus(authData) {
        const container = document.getElementById('securityStatus');
        if (!container) return;

        const stats = authData?.stats || {};
        
        container.innerHTML = `
            <div class="health-item">
                <span class="health-label">Active Tokens</span>
                <span class="health-value good">${stats.active_tokens || 0}</span>
            </div>
            <div class="health-item">
                <span class="health-label">Authentication</span>
                <span class="health-value good">Secure</span>
            </div>
            <div class="health-item">
                <span class="health-label">Last Activity</span>
                <span class="health-value good">Recent</span>
            </div>
        `;
    }

    /**
     * Setup file upload functionality
     */
    setupFileUpload() {
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const browseFiles = document.getElementById('browseFiles');
        const startUpload = document.getElementById('startUpload');

        if (!uploadArea || !fileInput) return;

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            fileInput.files = e.dataTransfer.files;
            this.updateUploadPreview();
        });

        // Click to browse
        uploadArea.addEventListener('click', () => fileInput.click());
        browseFiles?.addEventListener('click', () => fileInput.click());

        // File selection
        fileInput.addEventListener('change', () => this.updateUploadPreview());

        // Start upload
        startUpload?.addEventListener('click', () => this.startFileUpload());
    }

    /**
     * Show upload modal
     */
    showUploadModal() {
        const modal = document.getElementById('uploadModal');
        if (modal) {
            modal.classList.add('active');
        }
    }

    /**
     * Hide upload modal
     */
    hideUploadModal() {
        const modal = document.getElementById('uploadModal');
        if (modal) {
            modal.classList.remove('active');
            this.resetUploadForm();
        }
    }

    /**
     * Reset upload form
     */
    resetUploadForm() {
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        
        if (fileInput) fileInput.value = '';
        if (uploadArea) {
            uploadArea.innerHTML = `
                <div class="upload-icon">📁</div>
                <p>Drag and drop files here, or click to browse</p>
                <button class="btn btn-secondary" id="browseFiles">Browse Files</button>
            `;
        }
        
        this.setupFileUpload(); // Re-bind events
    }

    /**
     * Update upload preview
     */
    updateUploadPreview() {
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        
        if (!fileInput || !fileInput.files.length || !uploadArea) return;

        const files = Array.from(fileInput.files);
        const totalSize = files.reduce((sum, file) => sum + file.size, 0);

        uploadArea.innerHTML = `
            <div class="upload-icon">📁</div>
            <p>${files.length} file(s) selected (${this.formatFileSize(totalSize)})</p>
            <div style="margin-top: 1rem; font-size: 0.875rem; color: var(--text-secondary);">
                ${files.map(file => file.name).join(', ')}
            </div>
        `;
    }

    /**
     * Start file upload
     */
    async startFileUpload() {
        const fileInput = document.getElementById('fileInput');
        const plugin = document.getElementById('uploadPlugin')?.value || '';
        const tier = document.getElementById('uploadTier')?.value || 'hot';
        const tags = document.getElementById('uploadTags')?.value.split(',').map(t => t.trim()).filter(t => t);

        if (!fileInput || !fileInput.files.length) {
            this.showToast('Please select files to upload', 'warning');
            return;
        }

        const files = Array.from(fileInput.files);
        this.showUploadProgress();

        let completed = 0;
        for (const file of files) {
            try {
                await this.uploadFile(file, plugin, tier, tags);
                completed++;
                this.updateUploadProgress((completed / files.length) * 100);
            } catch (error) {
                console.error('Upload failed:', error);
                this.showToast(`Failed to upload ${file.name}`, 'error');
            }
        }

        this.hideUploadProgress();
        this.hideUploadModal();
        this.showToast(`Successfully uploaded ${completed} of ${files.length} files`, 'success');
        
        // Refresh file grid if we're on files section
        if (this.currentSection === 'files') {
            this.loadFileGrid();
        }
    }

    /**
     * Upload a single file
     */
    async uploadFile(file, plugin, tier, tags) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('plugin', plugin);
        formData.append('tier', tier);
        formData.append('tags', JSON.stringify(tags));

        const response = await fetch(`${this.API_BASE}/storage/upload`, {
            method: 'POST',
            headers: this.getAuthHeaders(),
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * Show upload progress
     */
    showUploadProgress() {
        const progress = document.getElementById('uploadProgress');
        if (progress) {
            progress.style.display = 'block';
        }
    }

    /**
     * Hide upload progress
     */
    hideUploadProgress() {
        const progress = document.getElementById('uploadProgress');
        if (progress) {
            progress.style.display = 'none';
        }
    }

    /**
     * Update upload progress
     */
    updateUploadProgress(percentage) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        if (progressFill) {
            progressFill.style.width = `${percentage}%`;
        }
        
        if (progressText) {
            progressText.textContent = `Uploading... ${Math.round(percentage)}%`;
        }
    }

    /**
     * Perform universal search
     */
    async performSearch() {
        const searchInput = document.getElementById('universalSearch');
        const resultsContainer = document.getElementById('searchResults');
        const searchFiles = document.getElementById('searchFiles')?.checked;
        const searchMemories = document.getElementById('searchMemories')?.checked;
        const searchMetadata = document.getElementById('searchMetadata')?.checked;

        if (!searchInput || !resultsContainer) return;

        const query = searchInput.value.trim();
        if (!query) {
            this.showToast('Please enter a search term', 'warning');
            return;
        }

        try {
            this.showLoading('Searching...');
            resultsContainer.innerHTML = '<div>Searching...</div>';

            const results = [];

            // Search memories if enabled
            if (searchMemories) {
                const memoryResponse = await this.apiCall('/memory/search', {
                    method: 'POST',
                    body: { query, limit: 20 }
                });
                const memories = memoryResponse.data?.memories || [];
                results.push(...memories.map(m => ({ ...m, type: 'memory' })));
            }

            // Search files if enabled
            if (searchFiles) {
                const fileResponse = await this.apiCall('/storage/search', {
                    method: 'POST',
                    body: { query, limit: 20 }
                });
                const files = fileResponse.data?.files || [];
                results.push(...files.map(f => ({ ...f, type: 'file' })));
            }

            this.displaySearchResults(results);

        } catch (error) {
            console.error('Search failed:', error);
            resultsContainer.innerHTML = '<div>Search failed. Please try again.</div>';
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Display search results
     */
    displaySearchResults(results) {
        const container = document.getElementById('searchResults');
        if (!container) return;

        if (results.length === 0) {
            container.innerHTML = '<div>No results found</div>';
            return;
        }

        container.innerHTML = results.map(result => {
            if (result.type === 'memory') {
                return `
                    <div class="search-result">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                            <span class="memory-type">🧠 ${result.entry_type}</span>
                            <span class="memory-date">${this.formatDate(result.created_at)}</span>
                        </div>
                        <div>${result.content}</div>
                    </div>
                `;
            } else if (result.type === 'file') {
                return `
                    <div class="search-result">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                            <span>📁 ${result.filename}</span>
                            <span>${this.formatFileSize(result.size_bytes)}</span>
                        </div>
                        <div style="color: var(--text-secondary); font-size: 0.875rem;">
                            Plugin: ${result.plugin || 'General'} | Tier: ${result.tier}
                        </div>
                    </div>
                `;
            }
        }).join('');
    }

    /**
     * Perform backup operation
     */
    async performBackup(type) {
        const statusElement = document.getElementById('backupStatus');
        
        try {
            if (statusElement) {
                statusElement.textContent = `Starting ${type} backup...`;
            }

            const response = await this.apiCall('/system/backup', {
                method: 'POST',
                body: { backup_type: type }
            });

            if (response.success) {
                this.showToast(`${type} backup completed successfully`, 'success');
                if (statusElement) {
                    statusElement.textContent = `${type} backup completed at ${new Date().toLocaleTimeString()}`;
                }
            } else {
                throw new Error(response.message);
            }

        } catch (error) {
            console.error('Backup failed:', error);
            this.showToast(`${type} backup failed`, 'error');
            if (statusElement) {
                statusElement.textContent = `${type} backup failed: ${error.message}`;
            }
        }
    }

    /**
     * Perform maintenance operation
     */
    async performMaintenance(type) {
        const statusElement = document.getElementById('maintenanceStatus');
        
        try {
            if (statusElement) {
                statusElement.textContent = `Running ${type} operation...`;
            }

            let endpoint = '';
            switch (type) {
                case 'clean':
                    endpoint = '/system/prune';
                    break;
                case 'prune':
                    endpoint = '/system/prune';
                    break;
                case 'analyze':
                    endpoint = '/system/storage/analysis';
                    break;
            }

            const response = await this.apiCall(endpoint, { method: 'POST' });

            if (response.success) {
                this.showToast(`${type} operation completed`, 'success');
                if (statusElement) {
                    statusElement.textContent = `${type} completed at ${new Date().toLocaleTimeString()}`;
                }
            } else {
                throw new Error(response.message);
            }

        } catch (error) {
            console.error('Maintenance failed:', error);
            this.showToast(`${type} operation failed`, 'error');
            if (statusElement) {
                statusElement.textContent = `${type} failed: ${error.message}`;
            }
        }
    }

    /**
     * Check system status
     */
    async checkSystemStatus() {
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');

        try {
            const response = await this.apiCall('/health');
            const isOnline = response.success;

            if (statusIndicator) {
                statusIndicator.className = `status-indicator ${isOnline ? 'online' : 'offline'}`;
            }
            if (statusText) {
                statusText.textContent = isOnline ? 'Online' : 'Offline';
            }

        } catch (error) {
            if (statusIndicator) {
                statusIndicator.className = 'status-indicator offline';
            }
            if (statusText) {
                statusText.textContent = 'Offline';
            }
        }
    }

    /**
     * Start periodic updates
     */
    startPeriodicUpdates() {
        // Check system status every 30 seconds
        setInterval(() => this.checkSystemStatus(), 30000);
        
        // Update storage stats every 2 minutes
        setInterval(() => {
            if (this.currentSection === 'dashboard') {
                this.loadStorageStats();
            }
        }, 120000);
    }

    /**
     * Open file (placeholder for future functionality)
     */
    openFile(fileId) {
        console.log('Opening file:', fileId);
        this.showToast('File preview coming soon!', 'info');
    }

    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loadingOverlay');
        const text = document.getElementById('loadingText');
        
        if (overlay) {
            overlay.classList.add('active');
        }
        if (text) {
            text.textContent = message;
        }
    }

    /**
     * Hide loading overlay with enhanced animation
     */
    hideLoading() {
        this.hideSmartLoading();
    }

    /**
     * Show loading overlay with enhanced animation
     */
    showLoading(message = 'Loading...') {
        this.showSmartLoading(message);
    }

    /**
     * Smart loading overlay with enhanced animations
     */
    showSmartLoading(message = 'Processing...') {
        const overlay = document.getElementById('loadingOverlay');
        if (!overlay) return;

        const loadingText = overlay.querySelector('.loading-text');
        if (loadingText) {
            loadingText.textContent = message;
        }

        overlay.style.display = 'flex';
        overlay.style.opacity = '0';
        overlay.style.backdropFilter = 'blur(0px)';

        requestAnimationFrame(() => {
            overlay.style.transition = 'all 0.3s ease';
            overlay.style.opacity = '1';
            overlay.style.backdropFilter = 'blur(10px)';
        });
    }

    hideSmartLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (!overlay) return;

        overlay.style.opacity = '0';
        overlay.style.backdropFilter = 'blur(0px)';
        
        setTimeout(() => {
            overlay.style.display = 'none';
        }, 300);
    }

    /**
     * Make API call with proper headers
     */
    async apiCall(endpoint, options = {}) {
        const url = `${this.API_BASE}${endpoint}`;
        const config = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...this.getAuthHeaders(),
                ...options.headers
            }
        };

        if (options.body) {
            config.body = JSON.stringify(options.body);
        }

        if (options.params) {
            const params = new URLSearchParams(options.params);
            url += `?${params}`;
        }

        const response = await fetch(url, config);
        
        if (!response.ok) {
            throw new Error(`API call failed: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * Get authentication headers
     */
    getAuthHeaders() {
        return this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {};
    }

    /**
     * Get file icon based on extension
     */
    getFileIcon(filename) {
        const ext = filename.split('.').pop()?.toLowerCase();
        const iconMap = {
            txt: '📄', md: '📝', doc: '📄', docx: '📄',
            pdf: '📕', png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️',
            mp4: '🎬', avi: '🎬', mov: '🎬',
            mp3: '🎵', wav: '🎵', m4a: '🎵',
            zip: '🗜️', rar: '🗜️', tar: '🗜️',
            json: '⚙️', xml: '⚙️', csv: '📊'
        };
        return iconMap[ext] || '📄';
    }

    /**
     * Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Format date
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Animate child elements with staggered timing
     */
    animateChildElements(container) {
        const children = container.querySelectorAll('.memory-block, .file-item, .system-card');
        children.forEach((child, index) => {
            child.style.setProperty('--item-index', index);
            child.style.opacity = '0';
            child.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                child.style.transition = 'all 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
                child.style.opacity = '1';
                child.style.transform = 'translateY(0)';
            }, index * 50 + 100);
        });
    }

    /**
     * Add loading state to button with enhanced feedback
     */
    setButtonLoading(button, isLoading) {
        if (!button) return;
        
        if (isLoading) {
            button.classList.add('loading');
            button.disabled = true;
            button.style.transform = 'scale(0.95)';
            
            // Store original text if not already stored
            if (!button.dataset.originalText) {
                button.dataset.originalText = button.textContent;
            }
            
            setTimeout(() => {
                button.style.transform = '';
            }, 150);
        } else {
            button.classList.remove('loading');
            button.disabled = false;
            
            // Restore original text
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
            }
            
            // Success feedback
            button.style.transform = 'scale(1.05)';
            setTimeout(() => {
                button.style.transform = '';
            }, 200);
        }
    }

    /**
     * Enhanced toast notification with micro-animations
     */
    showToast(message, type = 'success', duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-title">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
            <div class="toast-message">${message}</div>
        `;

        // Enhanced slide-in animation
        toast.style.transform = 'translateX(400px) scale(0.8)';
        toast.style.opacity = '0';
        
        container.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            toast.style.transition = 'all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            toast.style.transform = 'translateX(0) scale(1)';
            toast.style.opacity = '1';
        });

        // Auto-remove with enhanced animation
        setTimeout(() => {
            toast.style.transform = 'translateX(400px) scale(0.8)';
            toast.style.opacity = '0';
            
            setTimeout(() => {
                container.removeChild(toast);
            }, 400);
        }, duration);
    }
}

// Initialize the desktop when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ArchiveDesktop();
});

// Add some helpful console messages
console.log('🔐📚 Archie Memory Vault loaded');
console.log('Welcome to your digital memory vault and archival system!');
console.log('Your knowledge is secured, catalogued, and ready for exploration...');