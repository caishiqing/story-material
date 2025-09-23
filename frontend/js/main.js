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
        
        // Pagination state
        this.pagination = {
            currentPage: 1,
            itemsPerPage: 20,
            totalItems: 0,
            totalPages: 0
        };
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
        const minDurationFilter = document.getElementById('minDurationFilter');
        const maxDurationFilter = document.getElementById('maxDurationFilter');
        const searchBtn = document.getElementById('searchBtn');
        const clearFiltersBtn = document.getElementById('clearFiltersBtn');

        if (typeFilter) typeFilter.addEventListener('change', () => this.applyFilters());
        if (tagFilter) tagFilter.addEventListener('input', 
            components.debounce(() => this.applyFilters(), 500));
        if (searchQuery) {
            // Support Enter key for semantic search
            searchQuery.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault(); // Prevent form submission
                    e.stopPropagation(); // Stop event bubbling
                    console.log('[Search] Enter key pressed - triggering semantic search');
                    this.performSearch();
                }
            });
        }
        if (minDurationFilter) minDurationFilter.addEventListener('input', 
            components.debounce(() => this.applyFilters(), 500));
        if (maxDurationFilter) maxDurationFilter.addEventListener('input', 
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

        // Audio type change for voice fields visibility
        const audioType = document.getElementById('audioType');
        if (audioType) audioType.addEventListener('change', (e) => this.toggleVoiceFields(e));
        
        // Edit audio type change for voice fields visibility
        const editAudioType = document.getElementById('editAudioType');
        if (editAudioType) editAudioType.addEventListener('change', (e) => this.toggleEditVoiceFields(e));
        
        // Voice gender and age change for auto-updating tags
        const voiceGender = document.getElementById('voiceGender');
        const voiceAge = document.getElementById('voiceAge');
        if (voiceGender) voiceGender.addEventListener('change', () => this.updateVoiceTags());
        if (voiceAge) voiceAge.addEventListener('change', () => this.updateVoiceTags());
        
        // Edit voice gender and age change for auto-updating tags
        const editVoiceGender = document.getElementById('editVoiceGender');
        const editVoiceAge = document.getElementById('editVoiceAge');
        if (editVoiceGender) editVoiceGender.addEventListener('change', () => this.updateEditVoiceTags());
        if (editVoiceAge) editVoiceAge.addEventListener('change', () => this.updateEditVoiceTags());

        // Pagination controls
        const firstPageBtn = document.getElementById('firstPageBtn');
        const prevPageBtn = document.getElementById('prevPageBtn');
        const nextPageBtn = document.getElementById('nextPageBtn');
        const lastPageBtn = document.getElementById('lastPageBtn');
        const pageSizeSelect = document.getElementById('pageSizeSelect');

        if (firstPageBtn) firstPageBtn.addEventListener('click', () => this.goToPage(1));
        if (prevPageBtn) prevPageBtn.addEventListener('click', () => this.goToPage(this.pagination.currentPage - 1));
        if (nextPageBtn) nextPageBtn.addEventListener('click', () => this.goToPage(this.pagination.currentPage + 1));
        if (lastPageBtn) lastPageBtn.addEventListener('click', () => this.goToPage(this.pagination.totalPages));
        if (pageSizeSelect) pageSizeSelect.addEventListener('change', (e) => this.changePageSize(parseInt(e.target.value)));
    }

    /**
     * Load all audio materials
     */
    async loadAudios() {
        try {
            console.log('Loading audios...');
            this.audios = await audioAPI.getAudios();
            this.filteredAudios = [...this.audios];
            
            // Debug: Log loaded audios
            console.log('=== Loaded audios ===');
            this.audios.forEach((audio, index) => {
                console.log(`${index + 1}. ID: ${audio.id}, Path: ${audio.path}`);
            });
            console.log('=====================');
            
            // Initialize pagination and render
            this.updatePagination();
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
            
            // Adjust pagination after data refresh
            this.adjustPaginationAfterDataChange();
            
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
     * Adjust pagination after data changes (add/edit/delete)
     */
    adjustPaginationAfterDataChange() {
        // Re-apply current filters to update filteredAudios
        this.filteredAudios = audioAPI.filterAudios(this.audios, this.currentFilters);
        
        // Update pagination calculations
        this.updatePagination();
        
        // If current page is beyond available pages, go to last page
        if (this.pagination.currentPage > this.pagination.totalPages && this.pagination.totalPages > 0) {
            this.pagination.currentPage = this.pagination.totalPages;
        }
        
        // If no pages available, go to page 1
        if (this.pagination.totalPages === 0) {
            this.pagination.currentPage = 1;
        }
    }

    /**
     * Render audio list with pagination
     */
    renderAudios() {
        const container = document.getElementById('audioContainer');
        if (!container) return;

        // Update view mode class
        container.className = `audio-container ${this.currentViewMode}-view`;
        
        // Clear container
        container.innerHTML = '';
        
        if (this.filteredAudios.length === 0) {
            this.hidePagination();
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

        // Update pagination info
        this.updatePagination();

        // Calculate pagination
        const startIndex = (this.pagination.currentPage - 1) * this.pagination.itemsPerPage;
        const endIndex = Math.min(startIndex + this.pagination.itemsPerPage, this.filteredAudios.length);
        const currentPageAudios = this.filteredAudios.slice(startIndex, endIndex);

        // Show pagination if needed
        if (this.filteredAudios.length > this.pagination.itemsPerPage) {
            this.showPagination();
        } else {
            this.hidePagination();
        }

        // Render current page audio items
        currentPageAudios.forEach((audio, index) => {
            const audioItem = components.createAudioItem(audio, this.currentViewMode);
            
            // Add stagger animation
            setTimeout(() => {
                container.appendChild(audioItem);
            }, index * 50);
        });
    }

    /**
     * Apply filters (excluding search query - only for type, tag, and duration filters)
     */
    applyFilters() {
        // Update filter values (exclude search query for real-time filtering)
        this.currentFilters.type = document.getElementById('typeFilter')?.value || '';
        this.currentFilters.tag = document.getElementById('tagFilter')?.value || '';
        // Don't include description in real-time filtering - only semantic search
        this.currentFilters.description = '';
        
        // Duration filters
        const minDurationValue = document.getElementById('minDurationFilter')?.value;
        const maxDurationValue = document.getElementById('maxDurationFilter')?.value;
        
        this.currentFilters.minDuration = minDurationValue ? parseInt(minDurationValue, 10) : null;
        this.currentFilters.maxDuration = maxDurationValue ? parseInt(maxDurationValue, 10) : null;

        // Apply filters
        this.filteredAudios = audioAPI.filterAudios(this.audios, this.currentFilters);
        
        // Reset to first page when filtering
        this.pagination.currentPage = 1;
        this.updatePagination();
        
        // Re-render
        this.renderAudios();
        
        console.log(`Applied filters: ${this.audios.length} audios filtered to ${this.filteredAudios.length}`);
    }

    /**
     * Perform semantic search
     */
    async performSearch() {
        console.log('[Search] performSearch() method called');
        const query = document.getElementById('searchQuery')?.value?.trim();
        console.log('[Search] Query:', query);
        
        if (!query) {
            console.log('[Search] Empty query - falling back to applyFilters');
            this.applyFilters();
            return;
        }
        
        console.log('[Search] Starting semantic search with query:', query);

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
                min_duration: this.currentFilters.minDuration || undefined,
                max_duration: this.currentFilters.maxDuration || undefined,
                limit: 50
            };

            console.log('[Search] Calling backend API with params:', searchParams);
            const results = await audioAPI.searchAudios(searchParams);
            console.log('[Search] Backend search results:', results.length, 'items');
            
            this.filteredAudios = results;
            this.pagination.currentPage = 1; // Reset to first page for search results
            this.renderAudios();

            components.showToast(`搜索完成：找到 ${results.length} 个相关音效`, 'success', 3000);

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
        const minDurationFilter = document.getElementById('minDurationFilter');
        const maxDurationFilter = document.getElementById('maxDurationFilter');

        if (typeFilter) typeFilter.value = '';
        if (tagFilter) tagFilter.value = '';
        if (searchQuery) searchQuery.value = '';
        if (minDurationFilter) minDurationFilter.value = '';
        if (maxDurationFilter) maxDurationFilter.value = '';

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
        this.pagination.currentPage = 1; // Reset to first page
        this.renderAudios();

        components.showToast('已清除所有筛选条件', 'info', 2000);
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
     * Toggle voice fields visibility based on audio type selection
     */
    toggleVoiceFields(event) {
        const selectedType = event.target.value;
        const audioIdGroup = document.getElementById('audioIdGroup');
        const voiceGenderGroup = document.getElementById('voiceGenderGroup');
        const voiceAgeGroup = document.getElementById('voiceAgeGroup');
        const audioTagsGroup = document.getElementById('audioTagsGroup');
        
        if (selectedType === 'voice') {
            // Show voice-specific fields
            if (audioIdGroup) audioIdGroup.style.display = 'block';
            if (voiceGenderGroup) voiceGenderGroup.style.display = 'block';
            if (voiceAgeGroup) voiceAgeGroup.style.display = 'block';
            // Hide regular tags field for voice
            if (audioTagsGroup) audioTagsGroup.style.display = 'none';
        } else {
            // Hide voice-specific fields
            if (audioIdGroup) audioIdGroup.style.display = 'none';
            if (voiceGenderGroup) voiceGenderGroup.style.display = 'none';
            if (voiceAgeGroup) voiceAgeGroup.style.display = 'none';
            // Show regular tags field for non-voice
            if (audioTagsGroup) audioTagsGroup.style.display = 'block';
            
            // Clear voice fields when hiding
            const audioIdInput = document.getElementById('audioId');
            const voiceGenderSelect = document.getElementById('voiceGender');
            const voiceAgeSelect = document.getElementById('voiceAge');
            if (audioIdInput) audioIdInput.value = '';
            if (voiceGenderSelect) voiceGenderSelect.value = '';
            if (voiceAgeSelect) voiceAgeSelect.value = '';
        }
    }

    /**
     * Toggle edit voice fields visibility based on audio type selection
     */
    toggleEditVoiceFields(event) {
        const selectedType = event.target.value;
        const editVoiceGenderGroup = document.getElementById('editVoiceGenderGroup');
        const editVoiceAgeGroup = document.getElementById('editVoiceAgeGroup');
        const editAudioTagsGroup = document.getElementById('editAudioTagsGroup');
        
        if (selectedType === 'voice') {
            // Show voice-specific fields
            if (editVoiceGenderGroup) editVoiceGenderGroup.style.display = 'block';
            if (editVoiceAgeGroup) editVoiceAgeGroup.style.display = 'block';
            // Hide regular tags field for voice
            if (editAudioTagsGroup) editAudioTagsGroup.style.display = 'none';
        } else {
            // Hide voice-specific fields
            if (editVoiceGenderGroup) editVoiceGenderGroup.style.display = 'none';
            if (editVoiceAgeGroup) editVoiceAgeGroup.style.display = 'none';
            // Show regular tags field for non-voice
            if (editAudioTagsGroup) editAudioTagsGroup.style.display = 'block';
            
            // Clear voice fields when hiding
            const editVoiceGenderSelect = document.getElementById('editVoiceGender');
            const editVoiceAgeSelect = document.getElementById('editVoiceAge');
            if (editVoiceGenderSelect) editVoiceGenderSelect.value = '';
            if (editVoiceAgeSelect) editVoiceAgeSelect.value = '';
        }
    }

    /**
     * Update voice tags based on gender and age selection
     */
    updateVoiceTags() {
        const gender = document.getElementById('voiceGender').value;
        const age = document.getElementById('voiceAge').value;
        const tagsInput = document.getElementById('audioTags');
        
        const tags = [];
        if (gender) tags.push(gender);
        if (age) tags.push(age);
        
        if (tagsInput) {
            tagsInput.value = tags.join(', ');
        }
    }

    /**
     * Update edit voice tags based on gender and age selection
     */
    updateEditVoiceTags() {
        const gender = document.getElementById('editVoiceGender').value;
        const age = document.getElementById('editVoiceAge').value;
        const tagsInput = document.getElementById('editAudioTags');
        
        const tags = [];
        if (gender) tags.push(gender);
        if (age) tags.push(age);
        
        if (tagsInput) {
            tagsInput.value = tags.join(', ');
        }
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
        
        // Prepare validation rules
        const validationRules = {
            audioFile: { 
                required: true, 
                label: '音频文件',
                validate: (value, field) => {
                    if (field.files.length === 0) throw new Error('请选择音频文件');
                    audioAPI.validateAudioFile(field.files[0]);
                }
            },
            audioType: { required: true, label: '音效类型' }
        };
        
        // Add voice-specific validation if voice type is selected
        const audioTypeValue = document.getElementById('audioType').value;
        if (audioTypeValue === 'voice') {
            validationRules.voiceGender = { required: true, label: '性别' };
            validationRules.voiceAge = { required: true, label: '年龄' };
        }
        
        // Validate form
        const isValid = components.validateForm('uploadForm', validationRules);
        
        if (!isValid) return;

        try {
            components.setButtonLoading(submitBtn, true);
            
            // Prepare form data
            const formData = new FormData();
            formData.append('file', document.getElementById('audioFile').files[0]);
            formData.append('audio_type', document.getElementById('audioType').value);
            
            // Add audio ID if provided and type is voice
            const audioType = document.getElementById('audioType').value;
            const audioId = document.getElementById('audioId').value.trim();
            if (audioType === 'voice' && audioId) {
                formData.append('audio_id', audioId);
            }
            
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
            
            // Refresh data and stay on appropriate page
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
            // Debug: Log the input audioId and available audios
            console.log(`Input audioId: ${audioId} (type: ${typeof audioId})`);
            console.log('Available audios:', this.audios.map(a => ({ id: a.id, path: a.path })));
            
            const audio = this.audios.find(a => String(a.id) === String(audioId));
            if (!audio) {
                components.showToast('音效不存在', 'error');
                console.log(`Audio with ID ${audioId} not found!`);
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
            
            // Debug: Log audio information
            console.log(`Playing audio ID: ${audioId}, Path: ${audio.path}, URL: ${audioURL}`);
            
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
            const audio = this.audios.find(a => String(a.id) === String(audioId));
            if (!audio) {
                components.showToast('音效不存在', 'error');
                return;
            }

            this.currentEditingAudio = audio;
            
            // Populate form
            document.getElementById('editAudioId').value = audio.id;
            document.getElementById('editAudioType').value = audio.type;
            document.getElementById('editAudioDescription').value = audio.description || '';
            
            // Handle voice-specific fields
            if (audio.type === 'voice' && audio.tags && audio.tags.length > 0) {
                // Extract gender and age from tags for voice type
                const genderOptions = ['male', 'female'];
                const ageOptions = ['童年', '少年', '青年', '成年', '老年'];
                
                const gender = audio.tags.find(tag => genderOptions.includes(tag));
                const age = audio.tags.find(tag => ageOptions.includes(tag));
                
                if (gender) document.getElementById('editVoiceGender').value = gender;
                if (age) document.getElementById('editVoiceAge').value = age;
                
                // Clear tags input for voice type
                document.getElementById('editAudioTags').value = '';
            } else {
                // Handle regular tags for non-voice types
                const tagsString = audio.tags && audio.tags.length > 0 
                    ? audio.tags.join(', ') : '';
                document.getElementById('editAudioTags').value = tagsString;
                
                // Clear voice fields
                document.getElementById('editVoiceGender').value = '';
                document.getElementById('editVoiceAge').value = '';
            }

            // Show modal
            openEditModal();
            
            // Trigger voice field toggle after modal is shown
            setTimeout(() => {
                this.toggleEditVoiceFields({ target: { value: audio.type } });
            }, 50);

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
        
        // Prepare validation rules
        const editValidationRules = {
            editAudioType: { required: true, label: '音效类型' },
            editAudioDescription: { required: true, label: '描述' }
        };
        
        // Add voice-specific validation if voice type is selected
        const editAudioTypeValue = document.getElementById('editAudioType').value;
        if (editAudioTypeValue === 'voice') {
            editValidationRules.editVoiceGender = { required: true, label: '性别' };
            editValidationRules.editVoiceAge = { required: true, label: '年龄' };
        }
        
        // Validate form
        const isValid = components.validateForm('editForm', editValidationRules);
        
        if (!isValid) return;

        try {
            components.setButtonLoading(submitBtn, true);
            
            const audioId = document.getElementById('editAudioId').value;
            const type = document.getElementById('editAudioType').value;
            const description = document.getElementById('editAudioDescription').value.trim();
            
            let tags = [];
            
            if (type === 'voice') {
                // For voice type, use gender and age as tags
                const gender = document.getElementById('editVoiceGender').value;
                const age = document.getElementById('editVoiceAge').value;
                
                if (gender) tags.push(gender);
                if (age) tags.push(age);
            } else {
                // For non-voice types, use regular tags input
                const tagsInput = document.getElementById('editAudioTags').value.trim();
                if (tagsInput) {
                    tags = tagsInput.split(',').map(tag => tag.trim()).filter(tag => tag);
                }
            }

            const updateData = {
                type,
                description,
                tags: tags.length > 0 ? tags : null
            };

            await audioAPI.updateAudio(audioId, updateData);
            
            components.showToast('音效更新成功', 'success');
            closeEditModal();
            
            // Refresh data and maintain pagination
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
            const audio = this.audios.find(a => String(a.id) === String(audioId));
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
            
            // Refresh data and adjust pagination
            await this.refreshData();

        } catch (error) {
            console.error('Delete failed:', error);
            components.showToast(`删除失败: ${error.message}`, 'error');
        } finally {
            components.setButtonLoading(confirmBtn, false);
            this.currentDeletingAudio = null;
        }
    }

    /**
     * Update pagination state and UI
     */
    updatePagination() {
        this.pagination.totalItems = this.filteredAudios.length;
        this.pagination.totalPages = Math.ceil(this.pagination.totalItems / this.pagination.itemsPerPage);
        
        // Ensure current page is valid
        if (this.pagination.currentPage > this.pagination.totalPages) {
            this.pagination.currentPage = Math.max(1, this.pagination.totalPages);
        }
        
        this.updatePaginationUI();
    }

    /**
     * Update pagination UI elements
     */
    updatePaginationUI() {
        // Update pagination info
        const startItem = (this.pagination.currentPage - 1) * this.pagination.itemsPerPage + 1;
        const endItem = Math.min(startItem + this.pagination.itemsPerPage - 1, this.pagination.totalItems);
        
        const paginationInfo = document.getElementById('paginationInfo');
        if (paginationInfo) {
            if (this.pagination.totalItems === 0) {
                paginationInfo.textContent = '共 0 项';
            } else {
                paginationInfo.textContent = `显示第 ${startItem}-${endItem} 项，共 ${this.pagination.totalItems} 项`;
            }
        }

        // Update button states
        const firstPageBtn = document.getElementById('firstPageBtn');
        const prevPageBtn = document.getElementById('prevPageBtn');
        const nextPageBtn = document.getElementById('nextPageBtn');
        const lastPageBtn = document.getElementById('lastPageBtn');

        const isFirstPage = this.pagination.currentPage === 1;
        const isLastPage = this.pagination.currentPage === this.pagination.totalPages || this.pagination.totalPages === 0;

        if (firstPageBtn) firstPageBtn.disabled = isFirstPage;
        if (prevPageBtn) prevPageBtn.disabled = isFirstPage;
        if (nextPageBtn) nextPageBtn.disabled = isLastPage;
        if (lastPageBtn) lastPageBtn.disabled = isLastPage;

        // Generate page numbers
        this.generatePageNumbers();
    }

    /**
     * Generate page number buttons
     */
    generatePageNumbers() {
        const pageNumbers = document.getElementById('pageNumbers');
        if (!pageNumbers) return;

        pageNumbers.innerHTML = '';

        const totalPages = this.pagination.totalPages;
        const currentPage = this.pagination.currentPage;

        if (totalPages <= 1) return;

        // Calculate which pages to show
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);

        // Adjust if we're near the beginning or end
        if (currentPage <= 3) {
            endPage = Math.min(totalPages, 5);
        }
        if (currentPage > totalPages - 3) {
            startPage = Math.max(1, totalPages - 4);
        }

        // Add first page and ellipsis if needed
        if (startPage > 1) {
            const firstPageNum = this.createPageButton(1);
            pageNumbers.appendChild(firstPageNum);
            
            if (startPage > 2) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'page-ellipsis';
                ellipsis.textContent = '...';
                pageNumbers.appendChild(ellipsis);
            }
        }

        // Add page numbers
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = this.createPageButton(i);
            pageNumbers.appendChild(pageBtn);
        }

        // Add last page and ellipsis if needed
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'page-ellipsis';
                ellipsis.textContent = '...';
                pageNumbers.appendChild(ellipsis);
            }
            
            const lastPageNum = this.createPageButton(totalPages);
            pageNumbers.appendChild(lastPageNum);
        }
    }

    /**
     * Create page number button
     */
    createPageButton(pageNum) {
        const button = document.createElement('button');
        button.className = 'page-number';
        button.textContent = pageNum;
        button.addEventListener('click', () => this.goToPage(pageNum));
        
        if (pageNum === this.pagination.currentPage) {
            button.classList.add('active');
        }
        
        return button;
    }

    /**
     * Go to specific page
     */
    goToPage(pageNum) {
        if (pageNum < 1 || pageNum > this.pagination.totalPages) return;
        
        this.pagination.currentPage = pageNum;
        this.renderAudios();
        
        // Scroll to top of audio list
        const audioList = document.querySelector('.audio-list');
        if (audioList) {
            audioList.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Change page size
     */
    changePageSize(newSize) {
        this.pagination.itemsPerPage = newSize;
        this.pagination.currentPage = 1; // Reset to first page
        this.renderAudios();
        
        components.showToast(`每页显示已设置为 ${newSize} 项`, 'info', 2000);
    }

    /**
     * Show pagination controls
     */
    showPagination() {
        const paginationContainer = document.getElementById('paginationContainer');
        if (paginationContainer) {
            paginationContainer.style.display = 'flex';
        }
    }

    /**
     * Hide pagination controls
     */
    hidePagination() {
        const paginationContainer = document.getElementById('paginationContainer');
        if (paginationContainer) {
            paginationContainer.style.display = 'none';
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
