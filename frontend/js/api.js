/**
 * API Service for Audio Material Management System
 * Handles all HTTP requests to the backend API
 */

class AudioAPI {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
        this.defaultHeaders = {
            'Accept': 'application/json',
        };
    }

    /**
     * Generic request method with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const config = {
            headers: { ...this.defaultHeaders },
            ...options
        };

        // Don't add Content-Type for FormData (let browser set it)
        if (!(options.body instanceof FormData)) {
            config.headers['Content-Type'] = 'application/json';
        }

        try {
            console.log(`[API] ${config.method || 'GET'} ${url}`);
            
            const response = await fetch(url, config);
            
            // Handle different response types
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                const error = new Error(data.detail || data || `HTTP ${response.status}`);
                error.status = response.status;
                error.response = data;
                throw error;
            }

            console.log(`[API] Success:`, data);
            return data;
            
        } catch (error) {
            console.error(`[API] Error:`, error);
            
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('无法连接到服务器，请检查服务器是否运行');
            }
            
            throw error;
        }
    }

    // Health and Info endpoints
    async getHealth() {
        return this.request('/health');
    }

    async getInfo() {
        return this.request('/');
    }

    // Audio Material CRUD operations
    
    /**
     * Upload a new audio file
     */
    async uploadAudio(formData, onProgress = null) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Progress tracking
            if (onProgress) {
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable) {
                        const percentComplete = (event.loaded / event.total) * 100;
                        onProgress(percentComplete);
                    }
                });
            }
            
            xhr.addEventListener('load', () => {
                try {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        const response = JSON.parse(xhr.responseText);
                        console.log('[API] Upload success:', response);
                        resolve(response);
                    } else {
                        const error = JSON.parse(xhr.responseText);
                        reject(new Error(error.detail || `HTTP ${xhr.status}`));
                    }
                } catch (e) {
                    reject(new Error('Invalid server response'));
                }
            });
            
            xhr.addEventListener('error', () => {
                reject(new Error('Upload failed'));
            });
            
            xhr.addEventListener('abort', () => {
                reject(new Error('Upload cancelled'));
            });
            
            xhr.open('POST', `${this.baseURL}/audio`);
            xhr.send(formData);
        });
    }

    /**
     * Get all audio materials
     */
    async getAudios() {
        return this.request('/audio');
    }

    /**
     * Get audio material by ID
     */
    async getAudio(id) {
        return this.request(`/audio/${id}`);
    }

    /**
     * Update audio material
     */
    async updateAudio(id, updateData) {
        return this.request(`/audio/${id}`, {
            method: 'PUT',
            body: JSON.stringify(updateData)
        });
    }

    /**
     * Delete audio material
     */
    async deleteAudio(id) {
        return this.request(`/audio/${id}`, {
            method: 'DELETE'
        });
    }

    // Search and filter operations

    /**
     * Search audio materials using hybrid search
     */
    async searchAudios(searchParams) {
        return this.request('/audio/search', {
            method: 'POST',
            body: JSON.stringify(searchParams)
        });
    }

    /**
     * Get collection statistics
     */
    async getStats() {
        return this.request('/audio/stats');
    }

    /**
     * Get available audio types
     */
    async getAudioTypes() {
        return this.request('/audio/types');
    }

    // Utility methods for filtering

    /**
     * Filter audios by type and/or tags (client-side filtering)
     */
    filterAudios(audios, filters) {
        let filtered = [...audios];

        // Filter by type
        if (filters.type && filters.type !== '') {
            filtered = filtered.filter(audio => 
                audio.type.toLowerCase() === filters.type.toLowerCase()
            );
        }

        // Filter by tag (partial match)
        if (filters.tag && filters.tag.trim() !== '') {
            const tagQuery = filters.tag.toLowerCase().trim();
            filtered = filtered.filter(audio => {
                if (!audio.tags || audio.tags.length === 0) return false;
                return audio.tags.some(tag => 
                    tag.toLowerCase().includes(tagQuery)
                );
            });
        }

        // Filter by description (partial match)
        if (filters.description && filters.description.trim() !== '') {
            const descQuery = filters.description.toLowerCase().trim();
            filtered = filtered.filter(audio => 
                audio.description && audio.description.toLowerCase().includes(descQuery)
            );
        }

        // Filter by duration range
        if (filters.minDuration && filters.minDuration > 0) {
            filtered = filtered.filter(audio => 
                audio.duration >= filters.minDuration
            );
        }

        if (filters.maxDuration && filters.maxDuration > 0) {
            filtered = filtered.filter(audio => 
                audio.duration <= filters.maxDuration
            );
        }

        return filtered;
    }

    /**
     * Sort audios by different criteria
     */
    sortAudios(audios, sortBy = 'id', sortOrder = 'asc') {
        const sorted = [...audios];
        
        sorted.sort((a, b) => {
            let valueA, valueB;
            
            switch (sortBy) {
                case 'name':
                    valueA = a.description || a.path || '';
                    valueB = b.description || b.path || '';
                    break;
                case 'type':
                    valueA = a.type || '';
                    valueB = b.type || '';
                    break;
                case 'duration':
                    valueA = a.duration || 0;
                    valueB = b.duration || 0;
                    break;
                case 'id':
                default:
                    valueA = a.id || 0;
                    valueB = b.id || 0;
                    break;
            }
            
            if (typeof valueA === 'string') {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }
            
            if (sortOrder === 'desc') {
                return valueA < valueB ? 1 : valueA > valueB ? -1 : 0;
            } else {
                return valueA > valueB ? 1 : valueA < valueB ? -1 : 0;
            }
        });
        
        return sorted;
    }

    /**
     * Get audio file URL for playback
     * Note: This assumes the backend serves static files
     */
    getAudioFileURL(audioPath) {
        // If it's already a full URL, return as-is
        if (audioPath.startsWith('http')) {
            return audioPath;
        }
        
        // For local file paths, we need to serve them through the backend
        // This might need adjustment based on how the backend serves files
        return `${this.baseURL}/static/${audioPath}`;
    }

    /**
     * Format duration from seconds to human-readable format
     */
    formatDuration(seconds) {
        if (!seconds || seconds < 0) return '0:00';
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    /**
     * Get display name from file path
     */
    getDisplayName(path, description = null) {
        if (description && description.trim()) {
            return description.trim();
        }
        
        if (!path) return 'Unknown Audio';
        
        // Extract filename from path
        const filename = path.split('/').pop() || path;
        
        // Remove timestamp prefix if present (e.g., "1703123456_music.mp3" -> "music.mp3")
        const cleanName = filename.replace(/^\d+_/, '');
        
        // Remove extension and replace underscores/hyphens with spaces
        return cleanName
            .replace(/\.[^/.]+$/, '') // Remove extension
            .replace(/[_-]/g, ' ')     // Replace _ and - with spaces
            .replace(/\s+/g, ' ')      // Normalize multiple spaces
            .trim();
    }

    /**
     * Validate audio file before upload
     */
    validateAudioFile(file) {
        const validTypes = [
            'audio/mpeg', 'audio/mp3', 
            'audio/wav', 'audio/wave',
            'audio/ogg', 'audio/flac',
            'audio/m4a', 'audio/aac',
            'audio/x-ms-wma'
        ];

        const validExtensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'];

        // Check file type
        if (file.type && !validTypes.some(type => 
            file.type.toLowerCase().includes(type.split('/')[1])
        )) {
            const extension = file.name.toLowerCase().split('.').pop();
            if (!validExtensions.includes(`.${extension}`)) {
                throw new Error(`不支持的音频格式。支持的格式：${validExtensions.join(', ')}`);
            }
        }

        // Check file size (limit to 100MB)
        const maxSize = 100 * 1024 * 1024; // 100MB in bytes
        if (file.size > maxSize) {
            throw new Error('文件太大，请选择小于100MB的音频文件');
        }

        return true;
    }
}

// Create and export a global API instance
window.audioAPI = new AudioAPI();

// Also export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioAPI;
}
