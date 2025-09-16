/**
 * Main Application Logic
 * Audio Material Management System Frontend
 */

class AudioApp {
    constructor() {
        this.audios = [];
        this.filteredAudios = [];
        this.currentViewMode = 'list';
        this.currentFilters = {
            type: '',
            tag: '',
            description: '',
            minDuration: null,
            maxDuration: null
        };
        this.audioTypes = [];
        this.currentEditingAudio = null;
        this.currentDeletingAudio = null;
    }

    /**
     * Initialize the application
     */
    async init() {
        try {
            console.log('Initializing Audio Management System...');
            
            // Show initial loading
            components.showLoading();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Load initial data
            await this.loadAudioTypes();
            await this.loadAudios();
            await this.loadStats();
            
            components.showToast('系统加载完成', 'success', 3000);
            
        } catch (error) {
            console.error('Failed to initialize app:', error);
            components.showToast(`初始化失败: ${error.message}`, 'error');
            components.hideLoading();
            components.showEmptyState();
        }
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Header buttons
        const uploadBtn = document.getElementById('uploadBtn');
        const refreshBtn = document.getElementById('refreshBtn');
        
        if (uploadBtn) uploadBtn.addEventListener('click', () => openUploadModal());
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.refreshData());

        // Filter controls
        const typeFilter = document.getElementById('typeFilter');
        const tagFilter = document.getElementById('tagFilter');
        const searchQuery = document.getElementById('searchQuery');
        const searchBtn = document.getElementById('searchBtn');
        const clearFiltersBtn = document.getElementById('clearFiltersBtn');

        if (typeFilter) typeFilter.addEventListener('change', () => this.applyFilters());
        if (tagFilter) tagFilter.addEventListener('input', 
            components.debounce(() => this.applyFilters(), 500));
        if (searchQuery) searchQuery.addEventListener('input', 
            components.debounce(() => this.applyFilters(), 500));
        if (searchBtn) searchBtn.addEventListener('click', () => this.performSearch());
        if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', () => this.clearFilters());

        // View controls
        const gridViewBtn = document.getElementById('gridViewBtn');
        const listViewBtn = document.getElementById('listViewBtn');

        if (gridViewBtn) gridViewBtn.addEventListener('click', () => this.setViewMode('grid'));
        if (listViewBtn) listViewBtn.addEventListener('click', () => this.setViewMode('list'));

        // Form submissions
        const uploadForm = document.getElementById('uploadForm');
        const editForm = document.getElementById('editForm');
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

        if (uploadForm) uploadForm.addEventListener('submit', (e) => this.handleUpload(e));
        if (editForm) editForm.addEventListener('submit', (e) => this.handleEdit(e));
        if (confirmDeleteBtn) confirmDeleteBtn.addEventListener('click', () => this.confirmDelete());

        // File input change for validation
        const audioFile = document.getElementById('audioFile');
        if (audioFile) audioFile.addEventListener('change', (e) => this.validateUploadFile(e));
    }

    /**
     * Load all audio materials
     */
    async loadAudios() {
        try {
            console.log('Loading audios...');
            this.audios = await audioAPI.getAudios();
            this.filteredAudios = [...this.audios];
            this.renderAudios();
            components.hideLoading();
            
            if (this.audios.length === 0) {
                components.showEmptyState();
            } else {
                components.hideEmptyState();
            }
            
        } catch (error) {
            console.error('Failed to load audios:', error);
            components.showToast(`加载音效失败: ${error.message}`, 'error');
            components.hideLoading();
            components.showEmptyState();
        }
    }

    /**
     * Load audio types
     */
    async loadAudioTypes() {
        try {
            this.audioTypes = await audioAPI.getAudioTypes();
            components.populateTypeSelects(this.audioTypes);
        } catch (error) {
            console.error('Failed to load audio types:', error);
            // Use fallback types
            this.audioTypes = ['music', 'ambient', 'mood', 'action', 'transition'];
            components.populateTypeSelects(this.audioTypes);
        }
    }

    /**
     * Load statistics
     */
    async loadStats() {
        try {
            const stats = await audioAPI.getStats();
            components.updateStats(stats);
        } catch (error) {
            console.error('Failed to load stats:', error);
            // Show default stats
            components.updateStats({
                total_count: this.audios.length,
                type_counts: {}
            });
        }
    }

    /**
     * Refresh all data
     */
    async refreshData() {
        const refreshBtn = document.getElementById('refreshBtn');
        const originalIcon = refreshBtn ? refreshBtn.innerHTML : '';
        
        try {
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 刷新';
                refreshBtn.disabled = true;
            }
            
            await Promise.all([
                this.loadAudios(),
                this.loadStats()
            ]);
            
            components.showToast('数据刷新完成', 'success', 2000);
            
        } catch (error) {
            console.error('Failed to refresh data:', error);
            components.showToast(`刷新失败: ${error.message}`, 'error');
        } finally {
            if (refreshBtn) {
                refreshBtn.innerHTML = originalIcon;
                refreshBtn.disabled = false;
            }
        }
    }

    /**
     * Render audio list
     */
    renderAudios() {
        const container = document.getElementById('audioContainer');
        if (!container) return;

        // Update view mode class
        container.className = `audio-container ${this.currentViewMode}-view`;
        
        // Clear container
        container.innerHTML = '';
        
        if (this.filteredAudios.length === 0) {
            if (this.audios.length === 0) {
                components.showEmptyState();
            } else {
                // Show filtered empty state
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-search"></i>
                        <h3>未找到匹配的音效</h3>
                        <p>请调整筛选条件后重试</p>
                        <button class="btn btn-outline" onclick="app.clearFilters()">
                            <i class="fas fa-times"></i> 清除筛选
                        </button>
                    </div>
                `;
            }
            return;
        }

        components.hideEmptyState();

        // Render audio items
        this.filteredAudios.forEach((audio, index) => {
            const audioItem = components.createAudioItem(audio, this.currentViewMode);
            
            // Add stagger animation
            setTimeout(() => {
                container.appendChild(audioItem);
            }, index * 50);
        });
    }

    /**
     * Apply filters
     */
    applyFilters() {
        // Update filter values
        this.currentFilters.type = document.getElementById('typeFilter')?.value || '';
        this.currentFilters.tag = document.getElementById('tagFilter')?.value || '';
        this.currentFilters.description = document.getElementById('searchQuery')?.value || '';

        // Apply filters
        this.filteredAudios = audioAPI.filterAudios(this.audios, this.currentFilters);
        
        // Re-render
        this.renderAudios();
        
        console.log(`Filtered ${this.audios.length} audios to ${this.filteredAudios.length}`);
    }

    /**
     * Perform semantic search
     */
    async performSearch() {
        const query = document.getElementById('searchQuery')?.value?.trim();
        if (!query) {
            this.applyFilters();
            return;
        }

        const searchBtn = document.getElementById('searchBtn');
        const originalContent = searchBtn?.innerHTML;

        try {
            if (searchBtn) {
                searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                searchBtn.disabled = true;
            }

            // Prepare search parameters
            const searchParams = {
                query: query,
                type: this.currentFilters.type || undefined,
                tag: this.currentFilters.tag || undefined,
                limit: 50
            };

            const results = await audioAPI.searchAudios(searchParams);
            this.filteredAudios = results;
            this.renderAudios();

            components.showToast(`找到 ${results.length} 个相关音效`, 'info', 3000);

        } catch (error) {
            console.error('Search failed:', error);
            components.showToast(`搜索失败: ${error.message}`, 'error');
            // Fallback to local filtering
            this.applyFilters();
        } finally {
            if (searchBtn && originalContent) {
                searchBtn.innerHTML = originalContent;
                searchBtn.disabled = false;
            }
        }
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        // Reset filter inputs
        const typeFilter = document.getElementById('typeFilter');
        const tagFilter = document.getElementById('tagFilter');
        const searchQuery = document.getElementById('searchQuery');

        if (typeFilter) typeFilter.value = '';
        if (tagFilter) tagFilter.value = '';
        if (searchQuery) searchQuery.value = '';

        // Reset filter state
        this.currentFilters = {
            type: '',
            tag: '',
            description: '',
            minDuration: null,
            maxDuration: null
        };

        // Show all audios
        this.filteredAudios = [...this.audios];
        this.renderAudios();

        components.showToast('筛选已清除', 'info', 2000);
    }

    /**
     * Set view mode
     */
    setViewMode(mode) {
        this.currentViewMode = mode;
        
        // Update button states
        const gridBtn = document.getElementById('gridViewBtn');
        const listBtn = document.getElementById('listViewBtn');
        
        if (gridBtn) gridBtn.classList.toggle('active', mode === 'grid');
        if (listBtn) listBtn.classList.toggle('active', mode === 'list');
        
        // Re-render with new view mode
        this.renderAudios();
    }

    /**
     * Validate upload file
     */
    validateUploadFile(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            audioAPI.validateAudioFile(file);
            
            // Show file info
            const fileInfo = `文件: ${file.name} (${components.formatFileSize(file.size)})`;
            components.showToast(fileInfo, 'info', 3000);
            
        } catch (error) {
            event.target.value = ''; // Clear the input
            components.showToast(error.message, 'error');
        }
    }

    /**
     * Handle file upload
     */
    async handleUpload(event) {
        event.preventDefault();
        
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Validate form
        const isValid = components.validateForm('uploadForm', {
            audioFile: { 
                required: true, 
                label: '音频文件',
                validate: (value, field) => {
                    if (field.files.length === 0) throw new Error('请选择音频文件');
                    audioAPI.validateAudioFile(field.files[0]);
                }
            },
            audioType: { required: true, label: '音效类型' }
        });
        
        if (!isValid) return;

        try {
            components.setButtonLoading(submitBtn, true);
            
            // Prepare form data
            const formData = new FormData();
            formData.append('file', document.getElementById('audioFile').files[0]);
            formData.append('audio_type', document.getElementById('audioType').value);
            
            const description = document.getElementById('audioDescription').value.trim();
            if (description) {
                formData.append('description', description);
            }
            
            const tags = document.getElementById('audioTags').value.trim();
            if (tags) {
                formData.append('tags', tags);
            }

            // Upload with progress tracking
            const result = await audioAPI.uploadAudio(formData, (progress) => {
                components.updateUploadProgress(progress);
            });

            // Success
            components.hideUploadProgress();
            components.showToast(`音效上传成功: ${result.filename}`, 'success');
            closeUploadModal();
            
            // Refresh data
            await this.refreshData();

        } catch (error) {
            console.error('Upload failed:', error);
            components.showToast(`上传失败: ${error.message}`, 'error');
            components.hideUploadProgress();
        } finally {
            components.setButtonLoading(submitBtn, false);
        }
    }

    /**
     * Play audio
     */
    async playAudio(audioId) {
        try {
            const audio = this.audios.find(a => a.id == audioId);
            if (!audio) {
                components.showToast('音效不存在', 'error');
                return;
            }

            // Open player modal
            components.showModal('playerModal');
            
            // Update player info
            document.getElementById('playerTitle').innerHTML = 
                `<i class="fas fa-play"></i> ${audioAPI.getDisplayName(audio.path, audio.description)}`;
            document.getElementById('playingTitle').textContent = 
                audioAPI.getDisplayName(audio.path, audio.description);
            document.getElementById('playingDescription').textContent = 
                audio.description || '无描述';
            
            const typeBadge = document.getElementById('playingType');
            typeBadge.textContent = components.getTypeDisplayName(audio.type);
            typeBadge.className = `type-badge ${audio.type}`;
            
            document.getElementById('playingDuration').textContent = 
                audioAPI.formatDuration(audio.duration);

            // Update tags
            const tagsContainer = document.getElementById('playingTags');
            if (audio.tags && audio.tags.length > 0) {
                tagsContainer.innerHTML = audio.tags
                    .map(tag => `<span class="tag">${components.escapeHtml(tag)}</span>`)
                    .join('');
            } else {
                tagsContainer.innerHTML = '<span class="tag">无标签</span>';
            }

            // Set up audio player
            const audioPlayer = document.getElementById('audioPlayer');
            const audioURL = audioAPI.getAudioFileURL(audio.path);
            
            audioPlayer.src = audioURL;
            audioPlayer.load();
            
            // Auto play
            try {
                await audioPlayer.play();
            } catch (playError) {
                console.warn('Auto play failed:', playError);
                components.showToast('音频加载完成，请手动点击播放', 'info');
            }

        } catch (error) {
            console.error('Failed to play audio:', error);
            components.showToast(`播放失败: ${error.message}`, 'error');
        }
    }

    /**
     * Edit audio
     */
    async editAudio(audioId) {
        try {
            const audio = this.audios.find(a => a.id == audioId);
            if (!audio) {
                components.showToast('音效不存在', 'error');
                return;
            }

            this.currentEditingAudio = audio;
            
            // Populate form
            document.getElementById('editAudioId').value = audio.id;
            document.getElementById('editAudioType').value = audio.type;
            document.getElementById('editAudioDescription').value = audio.description || '';
            
            // Handle tags
            const tagsString = audio.tags && audio.tags.length > 0 
                ? audio.tags.join(', ') : '';
            document.getElementById('editAudioTags').value = tagsString;

            // Show modal
            openEditModal();

        } catch (error) {
            console.error('Failed to prepare edit:', error);
            components.showToast(`编辑失败: ${error.message}`, 'error');
        }
    }

    /**
     * Handle edit form submission
     */
    async handleEdit(event) {
        event.preventDefault();
        
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Validate form
        const isValid = components.validateForm('editForm', {
            editAudioType: { required: true, label: '音效类型' },
            editAudioDescription: { required: true, label: '描述' }
        });
        
        if (!isValid) return;

        try {
            components.setButtonLoading(submitBtn, true);
            
            const audioId = document.getElementById('editAudioId').value;
            const type = document.getElementById('editAudioType').value;
            const description = document.getElementById('editAudioDescription').value.trim();
            const tagsInput = document.getElementById('editAudioTags').value.trim();
            
            // Parse tags
            let tags = [];
            if (tagsInput) {
                tags = tagsInput.split(',').map(tag => tag.trim()).filter(tag => tag);
            }

            const updateData = {
                type,
                description,
                tags: tags.length > 0 ? tags : null
            };

            await audioAPI.updateAudio(audioId, updateData);
            
            components.showToast('音效更新成功', 'success');
            closeEditModal();
            
            // Refresh data
            await this.refreshData();

        } catch (error) {
            console.error('Update failed:', error);
            components.showToast(`更新失败: ${error.message}`, 'error');
        } finally {
            components.setButtonLoading(submitBtn, false);
        }
    }

    /**
     * Delete audio
     */
    async deleteAudio(audioId) {
        try {
            const audio = this.audios.find(a => a.id == audioId);
            if (!audio) {
                components.showToast('音效不存在', 'error');
                return;
            }

            this.currentDeletingAudio = audio;
            
            // Update modal content
            const fileName = audioAPI.getDisplayName(audio.path, audio.description);
            document.getElementById('deleteFileName').textContent = fileName;
            
            // Show confirmation modal
            openDeleteModal();

        } catch (error) {
            console.error('Failed to prepare delete:', error);
            components.showToast(`删除失败: ${error.message}`, 'error');
        }
    }

    /**
     * Confirm delete
     */
    async confirmDelete() {
        if (!this.currentDeletingAudio) return;

        const confirmBtn = document.getElementById('confirmDeleteBtn');
        
        try {
            components.setButtonLoading(confirmBtn, true);
            
            await audioAPI.deleteAudio(this.currentDeletingAudio.id);
            
            components.showToast('音效删除成功', 'success');
            closeDeleteModal();
            
            // Refresh data
            await this.refreshData();

        } catch (error) {
            console.error('Delete failed:', error);
            components.showToast(`删除失败: ${error.message}`, 'error');
        } finally {
            components.setButtonLoading(confirmBtn, false);
            this.currentDeletingAudio = null;
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new AudioApp();
    app.init();
});

// Global functions for HTML onclick attributes
window.app = window.app || {};

// Handle page visibility change to pause audio when tab is not active
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        const audioPlayer = document.getElementById('audioPlayer');
        if (audioPlayer && !audioPlayer.paused) {
            audioPlayer.pause();
        }
    }
});

// Handle errors globally
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (window.components) {
        components.showToast('发生未知错误，请刷新页面重试', 'error');
    }
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    if (window.components) {
        components.showToast('操作失败，请重试', 'error');
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioApp;
}
