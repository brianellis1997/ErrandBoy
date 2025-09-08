/**
 * Enhanced Expert Interface with Real-time Notifications
 * Integrates with all Expert Notification APIs from Issue #21
 */

class ExpertInterface {
    constructor() {
        this.currentExpertId = '82634ced-df8c-4968-b97f-4b50e0a23422';
        this.websocket = null;
        this.quillEditor = null;
        this.currentDraft = null;
        this.autoSaveTimer = null;
        this.queueData = { items: [], total_items: 0 };
        
        this.init();
    }
    
    async init() {
        this.setupEventListeners();
        this.initializeQuillEditor();
        await this.loadExpertData();
        this.connectWebSocket();
        this.startAutoRefresh();
    }
    
    setupEventListeners() {
        // Expert selection
        document.getElementById('expertSelect').addEventListener('change', async (e) => {
            this.currentExpertId = e.target.value;
            await this.loadExpertData();
            this.reconnectWebSocket();
        });
        
        // Availability toggle
        document.getElementById('toggleAvailability').addEventListener('click', () => {
            this.toggleAvailability();
        });
        
        // Preferences
        document.getElementById('showPreferences').addEventListener('click', () => {
            this.showPreferencesModal();
        });
        
        document.getElementById('closePreferences').addEventListener('click', () => {
            this.hidePreferencesModal();
        });
        
        document.getElementById('savePreferences').addEventListener('click', () => {
            this.savePreferences();
        });
        
        document.getElementById('cancelPreferences').addEventListener('click', () => {
            this.hidePreferencesModal();
        });
        
        // Queue management
        document.getElementById('refreshQueue').addEventListener('click', () => {
            this.loadQueue();
        });
        
        document.getElementById('statusFilter').addEventListener('change', () => {
            this.loadQueue();
        });
        
        // Draft management
        document.getElementById('saveDraft').addEventListener('click', () => {
            this.saveDraft();
        });
        
        document.getElementById('submitResponse').addEventListener('click', () => {
            this.submitResponse();
        });
        
        document.getElementById('loadTemplate').addEventListener('click', () => {
            this.loadResponseTemplate();
        });
        
        // Confidence slider
        document.getElementById('confidenceSlider').addEventListener('input', (e) => {
            document.getElementById('confidenceValue').textContent = e.target.value + '%';
            this.scheduleAutoSave();
        });
    }
    
    initializeQuillEditor() {
        // Initialize Quill rich text editor
        this.quillEditor = new Quill('#editor', {
            theme: 'snow',
            placeholder: 'Write your expert response here...',
            modules: {
                toolbar: [
                    [{ 'header': [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    ['blockquote', 'code-block'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    [{ 'script': 'sub'}, { 'script': 'super' }],
                    [{ 'indent': '-1'}, { 'indent': '+1' }],
                    ['link', 'image'],
                    ['clean']
                ]
            }
        });
        
        // Auto-save on text changes
        this.quillEditor.on('text-change', () => {
            this.scheduleAutoSave();
        });
    }
    
    async loadExpertData() {
        try {
            // Load expert preferences
            await this.loadPreferences();
            
            // Load expert queue
            await this.loadQueue();
            
            // Load expert drafts
            await this.loadDrafts();
            
            this.updateConnectionStatus('connected', 'Connected');
        } catch (error) {
            console.error('Error loading expert data:', error);
            this.updateConnectionStatus('disconnected', 'Error loading data');
        }
    }
    
    async loadPreferences() {
        try {
            const response = await fetch(`/api/v1/expert/${this.currentExpertId}/preferences`);
            if (response.ok) {
                const preferences = await response.json();
                this.populatePreferencesForm(preferences);
            }
        } catch (error) {
            console.error('Error loading preferences:', error);
        }
    }
    
    async loadQueue() {
        try {
            document.getElementById('queueLoading').classList.remove('hidden');
            document.getElementById('queueItems').classList.add('hidden');
            
            const statusFilter = document.getElementById('statusFilter').value;
            const url = new URL(`/api/v1/expert/${this.currentExpertId}/queue`, window.location.origin);
            
            if (statusFilter) {
                url.searchParams.append('status_filter', statusFilter);
            }
            
            const response = await fetch(url);
            if (response.ok) {
                this.queueData = await response.json();
                this.updateQueueDisplay();
                this.updateStats();
            }
        } catch (error) {
            console.error('Error loading queue:', error);
        } finally {
            document.getElementById('queueLoading').classList.add('hidden');
        }
    }
    
    async loadDrafts() {
        try {
            const response = await fetch(`/api/v1/expert/${this.currentExpertId}/drafts`);
            if (response.ok) {
                const drafts = await response.json();
                this.updateDraftsDisplay(drafts);
            }
        } catch (error) {
            console.error('Error loading drafts:', error);
        }
    }
    
    updateQueueDisplay() {
        const container = document.getElementById('queueItems');
        const emptyState = document.getElementById('queueEmpty');
        
        if (this.queueData.items.length === 0) {
            container.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }
        
        container.classList.remove('hidden');
        emptyState.classList.add('hidden');
        
        container.innerHTML = this.queueData.items.map(item => `
            <div class="border-b border-gray-200 p-4 hover:bg-gray-50 cursor-pointer queue-item" 
                 data-query-id="${item.query_id}">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-1 bg-${this.getUrgencyColor(item.urgency)}-100 text-${this.getUrgencyColor(item.urgency)}-800 rounded-full text-xs font-medium">
                            ${item.urgency.toUpperCase()}
                        </span>
                        <span class="px-2 py-1 bg-${this.getStatusColor(item.status)}-100 text-${this.getStatusColor(item.status)}-800 rounded-full text-xs">
                            ${item.status.toUpperCase()}
                        </span>
                    </div>
                    <div class="text-right text-sm">
                        <div class="font-medium text-green-600">$${(item.estimated_payout_cents / 100).toFixed(4)}</div>
                        <div class="text-gray-500">${item.time_remaining_minutes}m left</div>
                    </div>
                </div>
                
                <p class="text-gray-800 mb-2 line-clamp-2">${item.question_text}</p>
                
                <div class="flex justify-between items-center text-xs text-gray-500">
                    <span>From: ${item.user_phone}</span>
                    <span>${new Date(item.received_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');
        
        // Add click handlers for queue items
        container.querySelectorAll('.queue-item').forEach(item => {
            item.addEventListener('click', () => {
                const queryId = item.dataset.queryId;
                this.selectQuestion(queryId);
            });
        });
    }
    
    updateStats() {
        document.getElementById('queueCount').textContent = this.queueData.total_items;
        document.getElementById('pendingCount').textContent = this.queueData.pending_items;
        document.getElementById('todayCount').textContent = this.queueData.completed_today;
        document.getElementById('earningsToday').textContent = `$${(this.queueData.earnings_today_cents / 100).toFixed(2)}`;
    }
    
    async selectQuestion(queryId) {
        const question = this.queueData.items.find(item => item.query_id === queryId);
        if (!question) return;
        
        // Show selected question
        const questionCard = document.getElementById('selectedQuestionCard');
        const editor = document.getElementById('responseEditor');
        
        document.getElementById('questionUrgency').textContent = question.urgency.toUpperCase();
        document.getElementById('questionTimeLeft').textContent = `${question.time_remaining_minutes}m remaining`;
        document.getElementById('questionPayout').textContent = `$${(question.estimated_payout_cents / 100).toFixed(4)} est.`;
        document.getElementById('questionText').textContent = question.question_text;
        document.getElementById('questionUser').textContent = question.user_phone;
        document.getElementById('questionId').textContent = question.query_id.substring(0, 13) + '...';
        
        questionCard.classList.remove('hidden');
        editor.classList.remove('hidden');
        
        // Load existing draft if available
        await this.loadDraftForQuery(queryId);
        
        // Update selected question ID
        this.selectedQueryId = queryId;
    }
    
    async loadDraftForQuery(queryId) {
        try {
            const response = await fetch(`/api/v1/expert/${this.currentExpertId}/drafts?query_id=${queryId}`);
            if (response.ok) {
                const drafts = await response.json();
                if (drafts.length > 0) {
                    const draft = drafts[0];
                    this.quillEditor.setContents([]);
                    this.quillEditor.insertText(0, draft.draft_content);
                    document.getElementById('confidenceSlider').value = Math.round((draft.confidence_score || 0.8) * 100);
                    document.getElementById('confidenceValue').textContent = Math.round((draft.confidence_score || 0.8) * 100) + '%';
                    this.currentDraft = draft;
                }
            }
        } catch (error) {
            console.error('Error loading draft for query:', error);
        }
    }
    
    scheduleAutoSave() {
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
        }
        
        this.autoSaveTimer = setTimeout(() => {
            this.autoSaveDraft();
        }, 2000); // Auto-save after 2 seconds of inactivity
    }
    
    async autoSaveDraft() {
        if (!this.selectedQueryId) return;
        
        const content = this.quillEditor.getText().trim();
        if (!content) return;
        
        const confidence = parseInt(document.getElementById('confidenceSlider').value) / 100;
        
        const draftData = {
            query_id: this.selectedQueryId,
            contact_id: this.currentExpertId,
            draft_content: content,
            confidence_score: confidence,
            content_format: 'plaintext'
        };
        
        try {
            let response;
            if (this.currentDraft) {
                // Update existing draft
                response = await fetch(`/api/v1/expert/${this.currentExpertId}/drafts/${this.currentDraft.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        draft_content: content,
                        confidence_score: confidence
                    })
                });
            } else {
                // Create new draft
                response = await fetch(`/api/v1/expert/${this.currentExpertId}/drafts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(draftData)
                });
            }
            
            if (response.ok) {
                const draft = await response.json();
                this.currentDraft = draft;
                this.showAutoSaveIndicator();
            }
        } catch (error) {
            console.error('Error auto-saving draft:', error);
        }
    }
    
    async saveDraft() {
        await this.autoSaveDraft();
        this.showNotification('Draft saved successfully!', 'success');
    }
    
    async submitResponse() {
        const content = this.quillEditor.getText().trim();
        if (!content) {
            this.showNotification('Please write a response before submitting.', 'error');
            return;
        }
        
        // This would integrate with the actual submission API
        // For now, we'll just show a success message
        this.showNotification('Response submitted successfully!', 'success');
        
        // Clear the editor and hide the interface
        this.quillEditor.setContents([]);
        document.getElementById('selectedQuestionCard').classList.add('hidden');
        document.getElementById('responseEditor').classList.add('hidden');
        this.currentDraft = null;
        this.selectedQueryId = null;
        
        // Refresh the queue
        await this.loadQueue();
    }
    
    loadResponseTemplate() {
        const template = `Based on my experience in this area, I would recommend the following approach:

1. **Key Considerations:**
   - [Point 1]
   - [Point 2]
   - [Point 3]

2. **Recommended Actions:**
   - [Action 1 with rationale]
   - [Action 2 with rationale]

3. **Additional Resources:**
   - [Relevant resources or references]

Please let me know if you need clarification on any of these points.`;

        this.quillEditor.setContents([]);
        this.quillEditor.insertText(0, template);
        this.scheduleAutoSave();
    }
    
    async toggleAvailability() {
        const button = document.getElementById('toggleAvailability');
        const isAvailable = button.classList.contains('bg-green-100');
        
        try {
            const response = await fetch(`/api/v1/expert/${this.currentExpertId}/availability/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `available=${!isAvailable}&reason=Manual toggle`
            });
            
            if (response.ok) {
                if (isAvailable) {
                    button.classList.remove('bg-green-100', 'text-green-800');
                    button.classList.add('bg-red-100', 'text-red-800');
                    button.textContent = 'Unavailable';
                } else {
                    button.classList.remove('bg-red-100', 'text-red-800');
                    button.classList.add('bg-green-100', 'text-green-800');
                    button.textContent = 'Available';
                }
                
                const result = await response.json();
                this.showNotification(result.message, 'success');
            }
        } catch (error) {
            console.error('Error toggling availability:', error);
            this.showNotification('Error updating availability', 'error');
        }
    }
    
    async showPreferencesModal() {
        document.getElementById('preferencesModal').classList.remove('hidden');
        await this.loadPreferences();
    }
    
    hidePreferencesModal() {
        document.getElementById('preferencesModal').classList.add('hidden');
    }
    
    populatePreferencesForm(preferences) {
        document.getElementById('smsEnabled').checked = preferences.sms_enabled;
        document.getElementById('emailEnabled').checked = preferences.email_enabled;
        document.getElementById('pushEnabled').checked = preferences.push_enabled;
        document.getElementById('notificationSchedule').value = preferences.notification_schedule;
        document.getElementById('maxPerHour').value = preferences.max_notifications_per_hour;
        document.getElementById('maxPerDay').value = preferences.max_notifications_per_day;
        document.getElementById('urgencyFilter').value = preferences.urgency_filter;
        document.getElementById('quietHoursEnabled').checked = preferences.quiet_hours_enabled;
        document.getElementById('quietStart').value = preferences.quiet_hours_start;
        document.getElementById('quietEnd').value = preferences.quiet_hours_end;
    }
    
    async savePreferences() {
        const preferences = {
            sms_enabled: document.getElementById('smsEnabled').checked,
            email_enabled: document.getElementById('emailEnabled').checked,
            push_enabled: document.getElementById('pushEnabled').checked,
            notification_schedule: document.getElementById('notificationSchedule').value,
            max_notifications_per_hour: parseInt(document.getElementById('maxPerHour').value),
            max_notifications_per_day: parseInt(document.getElementById('maxPerDay').value),
            urgency_filter: document.getElementById('urgencyFilter').value,
            quiet_hours_enabled: document.getElementById('quietHoursEnabled').checked,
            quiet_hours_start: document.getElementById('quietStart').value,
            quiet_hours_end: document.getElementById('quietEnd').value
        };
        
        try {
            const response = await fetch(`/api/v1/expert/${this.currentExpertId}/preferences`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(preferences)
            });
            
            if (response.ok) {
                this.hidePreferencesModal();
                this.showNotification('Preferences saved successfully!', 'success');
            }
        } catch (error) {
            console.error('Error saving preferences:', error);
            this.showNotification('Error saving preferences', 'error');
        }
    }
    
    connectWebSocket() {
        const wsUrl = `ws://${window.location.host}/api/v1/ws/expert/${this.currentExpertId}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('connected', 'Connected');
        };
        
        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus('disconnected', 'Disconnected');
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                this.connectWebSocket();
            }, 5000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('disconnected', 'Connection error');
        };
    }
    
    reconnectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
        }
        setTimeout(() => {
            this.connectWebSocket();
        }, 1000);
    }
    
    handleWebSocketMessage(message) {
        console.log('WebSocket message:', message);
        
        switch (message.type) {
            case 'notification':
                this.handleNotification(message);
                break;
            case 'pong':
                // Heartbeat response
                break;
            default:
                console.log('Unknown WebSocket message type:', message.type);
        }
    }
    
    handleNotification(message) {
        const { notification_type, data } = message;
        
        switch (notification_type) {
            case 'query_invitation':
                this.showNewQueryNotification(data);
                this.loadQueue(); // Refresh queue
                break;
            case 'payment_received':
                this.showPaymentNotification(data);
                break;
            case 'status_update':
                this.showNotification(data.message, 'info');
                break;
        }
    }
    
    showNewQueryNotification(data) {
        // Show notification badge
        document.getElementById('queueNotificationBadge').classList.remove('hidden');
        
        // Show toast notification
        document.getElementById('toastTitle').textContent = 'New Query Available';
        document.getElementById('toastMessage').textContent = `${data.question.substring(0, 100)}...`;
        this.showToast();
        
        // Play notification sound if enabled
        this.playNotificationSound();
    }
    
    showPaymentNotification(data) {
        this.showNotification(`Payment received: $${data.amount_dollars.toFixed(4)}`, 'success');
    }
    
    updateConnectionStatus(status, text) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        statusDot.className = `w-3 h-3 rounded-full websocket-${status}`;
        statusText.textContent = text;
    }
    
    showAutoSaveIndicator() {
        const indicator = document.getElementById('autoSaveStatus');
        indicator.style.opacity = '1';
        setTimeout(() => {
            indicator.style.opacity = '0';
        }, 2000);
    }
    
    showNotification(message, type = 'info') {
        // Simple notification system - could be enhanced with a proper toast library
        const colors = {
            success: 'bg-green-100 border-green-500 text-green-700',
            error: 'bg-red-100 border-red-500 text-red-700',
            info: 'bg-blue-100 border-blue-500 text-blue-700'
        };
        
        const notification = document.createElement('div');
        notification.className = `fixed top-20 right-4 p-4 rounded-lg border-l-4 ${colors[type]} z-50`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
    
    showToast() {
        const toast = document.getElementById('notificationToast');
        toast.classList.remove('hidden');
        
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 5000);
    }
    
    playNotificationSound() {
        // Create and play a subtle notification sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
    }
    
    startAutoRefresh() {
        // Refresh queue every 30 seconds
        setInterval(() => {
            this.loadQueue();
        }, 30000);
        
        // Send WebSocket ping every minute to keep connection alive
        setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                }));
            }
        }, 60000);
    }
    
    getUrgencyColor(urgency) {
        const colors = {
            low: 'gray',
            normal: 'blue',
            high: 'yellow',
            urgent: 'red'
        };
        return colors[urgency] || 'gray';
    }
    
    getStatusColor(status) {
        const colors = {
            pending: 'yellow',
            collecting: 'blue',
            compiling: 'purple',
            completed: 'green',
            failed: 'red'
        };
        return colors[status] || 'gray';
    }
}

// Initialize the expert interface when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ExpertInterface();
});