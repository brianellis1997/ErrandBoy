/**
 * Demo Control System for GroupChat
 * Handles demo orchestration, multi-screen coordination, and control panel
 */

class DemoController {
    constructor() {
        this.apiClient = new APIClient();
        this.websocket = null;
        this.screenType = 'admin'; // Default screen type
        this.demoStatus = null;
        this.isConnected = false;
        
        this.initializeScreenType();
        this.initializeWebSocket();
        this.bindEventHandlers();
    }
    
    /**
     * Determine screen type from URL or page context
     */
    initializeScreenType() {
        const path = window.location.pathname;
        
        if (path.includes('/expert')) {
            this.screenType = 'expert';
        } else if (path.includes('/admin')) {
            this.screenType = 'admin';
        } else if (path.includes('/answer')) {
            this.screenType = 'user';
        } else if (path === '/' || path.includes('/index')) {
            this.screenType = 'user';
        }
        
        console.log(`Demo screen type: ${this.screenType}`);
    }
    
    /**
     * Initialize WebSocket connection for demo coordination
     */
    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/demo/${this.screenType}`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('Demo WebSocket connected');
                this.isConnected = true;
                this.updateConnectionStatus(true);
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.websocket.onclose = () => {
                console.log('Demo WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                
                // Attempt to reconnect after 3 seconds
                setTimeout(() => this.initializeWebSocket(), 3000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('Demo WebSocket error:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
        }
    }
    
    /**
     * Handle incoming WebSocket messages
     */
    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'connection':
                console.log('Demo connection established:', message.data);
                break;
                
            case 'demo_update':
                this.handleDemoUpdate(message.data);
                break;
                
            case 'pong':
                // Handle ping/pong for connection keep-alive
                break;
                
            default:
                console.log('Unknown WebSocket message type:', message.type);
        }
    }
    
    /**
     * Handle demo progress updates
     */
    handleDemoUpdate(data) {
        this.demoStatus = data;
        
        // Update UI based on screen type
        if (this.screenType === 'admin') {
            this.updateAdminDashboard(data);
        } else if (this.screenType === 'expert') {
            this.updateExpertInterface(data);
        } else if (this.screenType === 'user') {
            this.updateUserInterface(data);
        }
        
        // Handle specific update types
        if (data.action === 'reset') {
            this.handleDemoReset();
        } else if (data.stage) {
            this.updateProgress(data.stage, data.progress);
        }
    }
    
    /**
     * Update admin dashboard with demo status
     */
    updateAdminDashboard(data) {
        const dashboardElements = {
            demoStatus: document.getElementById('demo-status'),
            demoStage: document.getElementById('demo-stage'),
            demoProgress: document.getElementById('demo-progress'),
            expertsContacted: document.getElementById('experts-contacted'),
            contributionsReceived: document.getElementById('contributions-received'),
            elapsedTime: document.getElementById('elapsed-time')
        };
        
        if (dashboardElements.demoStatus) {
            dashboardElements.demoStatus.textContent = data.status || 'idle';
            dashboardElements.demoStatus.className = `status-badge ${data.status}`;
        }
        
        if (dashboardElements.demoStage && data.current_stage) {
            dashboardElements.demoStage.textContent = data.current_stage;
        }
        
        if (dashboardElements.demoProgress && data.progress_percent !== undefined) {
            const progressBar = dashboardElements.demoProgress.querySelector('.progress-bar');
            const progressText = dashboardElements.demoProgress.querySelector('.progress-text');
            
            if (progressBar) {
                progressBar.style.width = `${data.progress_percent}%`;
            }
            if (progressText) {
                progressText.textContent = `${data.progress_percent}%`;
            }
        }
        
        if (dashboardElements.expertsContacted && data.experts_contacted !== undefined) {
            dashboardElements.expertsContacted.textContent = data.experts_contacted;
        }
        
        if (dashboardElements.contributionsReceived && data.contributions_received !== undefined) {
            dashboardElements.contributionsReceived.textContent = data.contributions_received;
        }
        
        if (dashboardElements.elapsedTime && data.elapsed_time !== undefined) {
            const minutes = Math.floor(data.elapsed_time / 60);
            const seconds = Math.floor(data.elapsed_time % 60);
            dashboardElements.elapsedTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
    }
    
    /**
     * Update expert interface based on demo state
     */
    updateExpertInterface(data) {
        if (data.type === 'new_response' && data.data) {
            this.showExpertResponseSimulation(data.data.expert, data.data.preview);
        }
        
        // Update expert status indicators
        const statusElement = document.getElementById('expert-demo-status');
        if (statusElement) {
            statusElement.textContent = `Demo: ${data.current_stage || 'idle'}`;
            statusElement.className = `demo-status ${data.status}`;
        }
    }
    
    /**
     * Update user interface based on demo state
     */
    updateUserInterface(data) {
        // If this is the main query submission page, update progress
        if (document.getElementById('progressSection')) {
            this.updateQueryProgress(data);
        }
        
        // If this is the answer page, update answer content
        if (document.getElementById('answerContent') && data.final_answer) {
            this.updateAnswerDisplay(data.final_answer);
        }
    }
    
    /**
     * Update query progress on user interface
     */
    updateQueryProgress(data) {
        const progressSection = document.getElementById('progressSection');
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const progressStatus = document.getElementById('progressStatus');
        
        if (data.status === 'running' && data.progress_percent !== undefined) {
            if (progressSection) progressSection.classList.remove('hidden');
            if (progressBar) progressBar.style.width = `${data.progress_percent}%`;
            if (progressPercent) progressPercent.textContent = `${data.progress_percent}%`;
            if (progressStatus) progressStatus.textContent = this.getStageDisplayName(data.current_stage);
        }
        
        if (data.final_answer) {
            this.showDemoResults(data.final_answer);
        }
    }
    
    /**
     * Update answer display with demo results
     */
    updateAnswerDisplay(answerData) {
        const answerContent = document.getElementById('answerContent');
        const confidenceScore = document.getElementById('confidenceScore');
        const expertCount = document.getElementById('expertCount');
        const totalCost = document.getElementById('totalCost');
        
        if (answerContent && answerData.content) {
            answerContent.innerHTML = this.parseAnswerWithCitations(answerData.content);
        }
        
        if (confidenceScore && answerData.confidence_score) {
            confidenceScore.textContent = Math.round(answerData.confidence_score * 100);
        }
        
        if (expertCount && answerData.expert_count) {
            expertCount.textContent = answerData.expert_count;
        }
        
        if (totalCost && answerData.total_cost_cents) {
            totalCost.textContent = `$${(answerData.total_cost_cents / 100).toFixed(2)}`;
        }
    }
    
    /**
     * Parse answer text and make citations clickable
     */
    parseAnswerWithCitations(text) {
        return text.replace(/\[@([^\]]+)\]/g, '<span class="citation-link" data-expert="$1">[@$1]</span>');
    }
    
    /**
     * Show demo results
     */
    showDemoResults(answerData) {
        // Hide progress section
        const progressSection = document.getElementById('progressSection');
        if (progressSection) progressSection.classList.add('hidden');
        
        // Show results section
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
            
            const answerContent = document.getElementById('answerContent');
            if (answerContent && answerData.content) {
                answerContent.innerHTML = this.parseAnswerWithCitations(answerData.content);
            }
            
            const confidenceScore = document.getElementById('confidenceScore');
            if (confidenceScore) {
                confidenceScore.textContent = Math.round((answerData.confidence_score || 0.9) * 100);
            }
            
            if (answerData.total_cost_cents) {
                const totalPayout = document.getElementById('totalPayout');
                if (totalPayout) {
                    totalPayout.textContent = `$${(answerData.total_cost_cents / 100).toFixed(2)}`;
                }
            }
            
            if (answerData.expert_count) {
                const contributorCount = document.getElementById('contributorCount');
                if (contributorCount) {
                    contributorCount.textContent = answerData.expert_count;
                }
            }
        }
    }
    
    /**
     * Get display-friendly stage name
     */
    getStageDisplayName(stage) {
        const stageNames = {
            'initializing': 'Initializing demo...',
            'routing': 'Analyzing question...',
            'contacting': 'Finding experts...',
            'collecting': 'Collecting responses...',
            'synthesizing': 'Synthesizing answer...',
            'completed': 'Complete!',
            'error': 'Error occurred'
        };
        
        return stageNames[stage] || stage;
    }
    
    /**
     * Show expert response simulation
     */
    showExpertResponseSimulation(expertName, preview) {
        // This could show a notification or update in the expert interface
        console.log(`Expert response from ${expertName}: ${preview}`);
        
        // If there's a notification area, show it there
        const notificationArea = document.getElementById('expert-notifications');
        if (notificationArea) {
            const notification = document.createElement('div');
            notification.className = 'expert-response-notification';
            notification.innerHTML = `
                <div class="expert-name">${expertName}</div>
                <div class="response-preview">${preview}</div>
            `;
            notificationArea.appendChild(notification);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 5000);
        }
    }
    
    /**
     * Handle demo reset
     */
    handleDemoReset() {
        // Reset all UI elements to initial state
        const progressSection = document.getElementById('progressSection');
        const resultsSection = document.getElementById('resultsSection');
        const errorSection = document.getElementById('errorSection');
        
        if (progressSection) progressSection.classList.add('hidden');
        if (resultsSection) resultsSection.classList.add('hidden');
        if (errorSection) errorSection.classList.add('hidden');
        
        // Reset form if present
        const queryForm = document.getElementById('queryForm');
        if (queryForm) {
            queryForm.style.opacity = '1';
            queryForm.reset();
        }
        
        console.log('Demo reset completed');
    }
    
    /**
     * Update connection status indicator
     */
    updateConnectionStatus(connected) {
        const statusIndicator = document.getElementById('demo-connection-status');
        if (statusIndicator) {
            statusIndicator.textContent = connected ? 'Connected' : 'Disconnected';
            statusIndicator.className = connected ? 'status-connected' : 'status-disconnected';
        }
    }
    
    /**
     * Update progress for any screen
     */
    updateProgress(stage, progress) {
        // Generic progress update that works across screen types
        console.log(`Demo progress: ${stage} - ${progress}%`);
        
        // Emit custom event for other components to listen to
        const event = new CustomEvent('demoProgress', {
            detail: { stage, progress, status: this.demoStatus }
        });
        document.dispatchEvent(event);
    }
    
    /**
     * Bind event handlers for demo controls
     */
    bindEventHandlers() {
        // Demo control buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('demo-control-btn')) {
                const action = e.target.dataset.action;
                if (action) {
                    this.sendDemoControl(action);
                }
            }
        });
        
        // Scenario selection
        document.addEventListener('change', (e) => {
            if (e.target.id === 'demo-scenario-select') {
                this.handleScenarioChange(e.target.value);
            }
        });
        
        // Keep WebSocket connection alive
        setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: Date.now()
                }));
            }
        }, 30000); // Ping every 30 seconds
    }
    
    /**
     * Send demo control command via WebSocket
     */
    sendDemoControl(action) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'demo_control',
                action: action,
                timestamp: Date.now()
            }));
        }
        
        console.log(`Demo control action: ${action}`);
    }
    
    /**
     * Handle scenario selection change
     */
    handleScenarioChange(scenarioId) {
        console.log(`Scenario selected: ${scenarioId}`);
        // This could trigger scenario loading or preview
    }
    
    /**
     * API Methods for Demo Control
     */
    
    async startDemo(scenarioId, mode = 'realistic') {
        try {
            const response = await this.apiClient.post('demo/start', {
                scenario_id: scenarioId,
                mode: mode
            });
            
            if (response.success) {
                console.log('Demo started:', response.data);
                return response.data;
            } else {
                throw new Error(response.error || 'Failed to start demo');
            }
        } catch (error) {
            console.error('Error starting demo:', error);
            throw error;
        }
    }
    
    async controlDemo(action) {
        try {
            const response = await this.apiClient.post('demo/control', {
                action: action
            });
            
            if (response.success) {
                console.log(`Demo ${action} successful:`, response.data);
                return response.data;
            } else {
                throw new Error(response.error || `Failed to ${action} demo`);
            }
        } catch (error) {
            console.error(`Error ${action} demo:`, error);
            throw error;
        }
    }
    
    async getDemoStatus() {
        try {
            const response = await this.apiClient.get('demo/status');
            if (response.success) {
                this.demoStatus = response.data;
                return response.data;
            } else {
                throw new Error(response.error || 'Failed to get demo status');
            }
        } catch (error) {
            console.error('Error getting demo status:', error);
            throw error;
        }
    }
    
    async getScenarios() {
        try {
            const response = await this.apiClient.get('demo/scenarios');
            if (response.success) {
                return response.data;
            } else {
                throw new Error(response.error || 'Failed to get scenarios');
            }
        } catch (error) {
            console.error('Error getting scenarios:', error);
            throw error;
        }
    }
}

// Initialize demo controller when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.demoController = new DemoController();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DemoController;
}