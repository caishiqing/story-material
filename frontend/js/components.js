/**
 * UI Components and Utilities
 * Reusable components for the Audio Material Management System
 */

class UIComponents {
    constructor() {
        this.activeToasts = new Map();
        this.toastCounter = 0;
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 5000) {
        const toastId = ++this.toastCounter;
        const container = document.getElementById('toastContainer');
        
        if (!container) {
            console.warn('Toast container not found');
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.id = `toast-${toastId}`;
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        const titles = {
            success: '成功',
            error: '错误',
            warning: '警告',
            info: '信息'
        };

        toast.innerHTML = `
            <div class="toast-header">
                <div class="toast-title">
                    <i class="${icons[type] || icons.info}"></i>
                    ${titles[type] || titles.info}
                </div>
                <button class="toast-close" onclick="components.closeToast(${toastId})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="toast-body">${message}</div>
        `;

        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Store reference
        this.activeToasts.set(toastId, toast);
        
        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => this.closeToast(toastId), duration);
        }
        
        return toastId;
    }

    /**
     * Close specific toast
     */
    closeToast(toastId) {
        const toast = this.activeToasts.get(toastId);
        if (!toast) return;
        
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            this.activeToasts.delete(toastId);
        }, 300);
    }

    /**
     * Close all toasts
     */
    closeAllToasts() {
        this.activeToasts.forEach((toast, id) => {
            this.closeToast(id);
        });
    }

    /**
     * Show loading state
     */
    showLoading(container = null) {
        const targetContainer = container || document.getElementById('audioContainer');
        if (!targetContainer) return;

        const loadingEl = document.getElementById('loadingState');
        const emptyEl = document.getElementById('emptyState');
        
        if (emptyEl) emptyEl.style.display = 'none';
        if (loadingEl) loadingEl.style.display = 'block';
        
        targetContainer.innerHTML = '';
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        const loadingEl = document.getElementById('loadingState');
        if (loadingEl) loadingEl.style.display = 'none';
    }

    /**
     * Show empty state
     */
    showEmptyState() {
        const emptyEl = document.getElementById('emptyState');
        const loadingEl = document.getElementById('loadingState');
        
        if (loadingEl) loadingEl.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'block';
        
        const container = document.getElementById('audioContainer');
        if (container) container.innerHTML = '';
    }

    /**
     * Hide empty state
     */
    hideEmptyState() {
        const emptyEl = document.getElementById('emptyState');
        if (emptyEl) emptyEl.style.display = 'none';
    }

    /**
     * Create audio item element
     */
    createAudioItem(audio, viewMode = 'list') {
        const item = document.createElement('div');
        item.className = 'audio-item fade-in';
        item.dataset.audioId = audio.id;
        
        // Debug: Log the audio being created
        console.log('Creating audio item for:', { id: audio.id, path: audio.path });
        
        const displayName = audioAPI.getDisplayName(audio.path, audio.description);
        const formattedDuration = audioAPI.formatDuration(audio.duration);
        
        // Create tags HTML
        const tagsHtml = audio.tags && audio.tags.length > 0
            ? audio.tags.map(tag => `<span class="tag">${this.escapeHtml(tag)}</span>`).join('')
            : '<span class="tag">无标签</span>';

        // Create the HTML structure
        const audioHeader = document.createElement('div');
        audioHeader.className = 'audio-header';
        
        const headerInfo = document.createElement('div');
        const audioTitle = document.createElement('div');
        audioTitle.className = 'audio-title';
        audioTitle.textContent = displayName;
        
        headerInfo.appendChild(audioTitle);
        
        const audioActions = document.createElement('div');
        audioActions.className = 'audio-actions';
        
        // Create play button with proper event binding
        const playBtn = document.createElement('button');
        playBtn.className = 'action-btn play';
        playBtn.title = '播放';
        playBtn.innerHTML = '<i class="fas fa-play"></i>';
        playBtn.addEventListener('click', () => {
            console.log('Play button clicked for audio ID:', audio.id);
            app.playAudio(String(audio.id));
        });
        
        // Create edit button
        const editBtn = document.createElement('button');
        editBtn.className = 'action-btn edit';
        editBtn.title = '编辑';
        editBtn.innerHTML = '<i class="fas fa-edit"></i>';
        editBtn.addEventListener('click', () => {
            console.log('Edit button clicked for audio ID:', audio.id);
            app.editAudio(String(audio.id));
        });
        
        // Create delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'action-btn delete';
        deleteBtn.title = '删除';
        deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
        deleteBtn.addEventListener('click', () => {
            console.log('Delete button clicked for audio ID:', audio.id);
            app.deleteAudio(String(audio.id));
        });
        
        audioActions.appendChild(playBtn);
        audioActions.appendChild(editBtn);
        audioActions.appendChild(deleteBtn);
        
        audioHeader.appendChild(headerInfo);
        audioHeader.appendChild(audioActions);
        
        // Create description
        const audioDescription = document.createElement('div');
        audioDescription.className = 'audio-description';
        audioDescription.textContent = audio.description || '无描述';
        
        // Create meta info
        const audioMeta = document.createElement('div');
        audioMeta.className = 'audio-meta';
        
        const typeBadge = document.createElement('span');
        typeBadge.className = `type-badge ${audio.type}`;
        typeBadge.textContent = this.getTypeDisplayName(audio.type);
        
        const duration = document.createElement('span');
        duration.className = 'duration';
        duration.textContent = formattedDuration;
        
        audioMeta.appendChild(typeBadge);
        audioMeta.appendChild(duration);
        
        // Create tags
        const audioTags = document.createElement('div');
        audioTags.className = 'audio-tags';
        audioTags.innerHTML = tagsHtml;
        
        // Assemble the item
        item.appendChild(audioHeader);
        item.appendChild(audioDescription);
        item.appendChild(audioMeta);
        item.appendChild(audioTags);
        
        return item;
    }

    /**
     * Get display name for audio type
     */
    getTypeDisplayName(type) {
        const typeNames = {
            'music': '音乐',
            'ambient': '环境音',
            'mood': '氛围音',
            'action': '动作音',
            'transition': '转场音效'
        };
        return typeNames[type] || type;
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Update statistics display
     */
    updateStats(stats) {
        const totalEl = document.getElementById('totalCount');
        const musicEl = document.getElementById('musicCount');
        const ambientEl = document.getElementById('ambientCount');
        const moodEl = document.getElementById('moodCount');
        const actionEl = document.getElementById('actionCount');
        const transitionEl = document.getElementById('transitionCount');
        
        if (totalEl) totalEl.textContent = stats.total_count || 0;
        if (musicEl) musicEl.textContent = stats.type_counts?.music || 0;
        if (ambientEl) ambientEl.textContent = stats.type_counts?.ambient || 0;
        if (moodEl) moodEl.textContent = stats.type_counts?.mood || 0;
        if (actionEl) actionEl.textContent = stats.type_counts?.action || 0;
        if (transitionEl) transitionEl.textContent = stats.type_counts?.transition || 0;
    }

    /**
     * Populate audio type select options
     */
    populateTypeSelects(types) {
        const selects = ['typeFilter', 'audioType', 'editAudioType'];
        
        selects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (!select) return;
            
            const isFilter = selectId === 'typeFilter';
            const currentValue = select.value;
            
            // Clear existing options (except first option for filter)
            const startIndex = isFilter ? 1 : 0;
            while (select.options.length > startIndex) {
                select.remove(startIndex);
            }
            
            // Add type options
            types.forEach(type => {
                const option = document.createElement('option');
                option.value = type;
                option.textContent = this.getTypeDisplayName(type);
                select.appendChild(option);
            });
            
            // Restore selected value if it still exists
            if (currentValue && Array.from(select.options).some(opt => opt.value === currentValue)) {
                select.value = currentValue;
            }
        });
    }

    /**
     * Show modal
     */
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.add('show');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
        
        // Focus first input if available
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }

    /**
     * Hide modal
     */
    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.remove('show');
        document.body.style.overflow = ''; // Restore scrolling
    }

    /**
     * Reset form
     */
    resetForm(formId) {
        const form = document.getElementById(formId);
        if (!form) return;
        
        form.reset();
        
        // Clear any error states
        const errorElements = form.querySelectorAll('.error');
        errorElements.forEach(el => el.classList.remove('error'));
        
        // Hide progress if present
        const progress = form.querySelector('.upload-progress');
        if (progress) progress.style.display = 'none';
    }

    /**
     * Update upload progress
     */
    updateUploadProgress(percent) {
        const progressContainer = document.getElementById('uploadProgress');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        if (progressContainer) progressContainer.style.display = 'block';
        if (progressFill) progressFill.style.width = `${percent}%`;
        if (progressText) progressText.textContent = `${Math.round(percent)}%`;
    }

    /**
     * Hide upload progress
     */
    hideUploadProgress() {
        const progressContainer = document.getElementById('uploadProgress');
        if (progressContainer) progressContainer.style.display = 'none';
    }

    /**
     * Set button loading state
     */
    setButtonLoading(button, loading = true) {
        if (!button) return;
        
        if (loading) {
            button.disabled = true;
            const originalText = button.innerHTML;
            button.dataset.originalText = originalText;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';
        } else {
            button.disabled = false;
            if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    }

    /**
     * Validate form fields
     */
    validateForm(formId, rules = {}) {
        const form = document.getElementById(formId);
        if (!form) return false;
        
        let isValid = true;
        const errors = [];
        
        Object.entries(rules).forEach(([fieldId, fieldRules]) => {
            const field = document.getElementById(fieldId);
            if (!field) return;
            
            field.classList.remove('error');
            
            // Required validation
            if (fieldRules.required) {
                const value = field.type === 'file' ? field.files.length > 0 : field.value.trim();
                if (!value) {
                    field.classList.add('error');
                    errors.push(`${fieldRules.label || fieldId} 是必填项`);
                    isValid = false;
                    return;
                }
            }
            
            // Custom validation
            if (fieldRules.validate && field.value.trim()) {
                try {
                    fieldRules.validate(field.value, field);
                } catch (error) {
                    field.classList.add('error');
                    errors.push(error.message);
                    isValid = false;
                }
            }
        });
        
        if (!isValid && errors.length > 0) {
            this.showToast(errors[0], 'error');
        }
        
        return isValid;
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
     * Debounce function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Animate element
     */
    animateElement(element, animation = 'fade-in') {
        if (!element) return;
        
        element.classList.remove(animation);
        // Force reflow
        element.offsetHeight;
        element.classList.add(animation);
    }

    /**
     * Copy text to clipboard
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('已复制到剪贴板', 'success', 2000);
            return true;
        } catch (err) {
            console.error('Failed to copy text:', err);
            this.showToast('复制失败', 'error', 2000);
            return false;
        }
    }
}

// Global modal functions (called from HTML onclick attributes)
window.openUploadModal = () => {
    components.showModal('uploadModal');
};

window.closeUploadModal = () => {
    components.hideModal('uploadModal');
    components.resetForm('uploadForm');
    components.hideUploadProgress();
};

window.openEditModal = () => {
    components.showModal('editModal');
};

window.closeEditModal = () => {
    components.hideModal('editModal');
    components.resetForm('editForm');
};

window.openDeleteModal = () => {
    components.showModal('deleteModal');
};

window.closeDeleteModal = () => {
    components.hideModal('deleteModal');
};

window.closePlayerModal = () => {
    components.hideModal('playerModal');
    const audio = document.getElementById('audioPlayer');
    if (audio) {
        audio.pause();
        audio.src = '';
    }
};

// Create and export global components instance
window.components = new UIComponents();

// Close modals when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        const modalId = e.target.id;
        if (modalId) {
            components.hideModal(modalId);
            
            // Reset forms and clean up
            if (modalId === 'uploadModal') {
                components.resetForm('uploadForm');
                components.hideUploadProgress();
            } else if (modalId === 'editModal') {
                components.resetForm('editForm');
            } else if (modalId === 'playerModal') {
                const audio = document.getElementById('audioPlayer');
                if (audio) {
                    audio.pause();
                    audio.src = '';
                }
            }
        }
    }
});

// Close modals with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modalId = openModal.id;
            components.hideModal(modalId);
            
            // Clean up
            if (modalId === 'uploadModal') {
                components.resetForm('uploadForm');
                components.hideUploadProgress();
            } else if (modalId === 'editModal') {
                components.resetForm('editForm');
            } else if (modalId === 'playerModal') {
                const audio = document.getElementById('audioPlayer');
                if (audio) {
                    audio.pause();
                    audio.src = '';
                }
            }
        }
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIComponents;
}
