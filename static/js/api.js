/**
 * API Client for GroupChat Query Submission
 */

class APIClient {
    constructor() {
        this.baseURL = window.location.origin;
        this.apiVersion = 'v1';
    }

    /**
     * Make HTTP request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}/api/${this.apiVersion}/${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
                    response.status,
                    errorData
                );
            }

            return await response.json();
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            
            // Network or parsing error
            throw new APIError(
                'Network error: Unable to connect to the server. Please check your internet connection.',
                0,
                { originalError: error.message }
            );
        }
    }

    /**
     * Submit a new query
     */
    async submitQuery(userPhone, questionText, maxSpendCents, liveMode = false) {
        return this.request('queries/', {
            method: 'POST',
            body: JSON.stringify({
                user_phone: userPhone,
                question_text: questionText,
                max_spend_cents: maxSpendCents,
                timeout_minutes: 30,
                live_mode: liveMode
            })
        });
    }

    /**
     * Get query status
     */
    async getQueryStatus(queryId) {
        return this.request(`queries/${queryId}/status`, {
            method: 'GET'
        });
    }

    /**
     * Health check
     */
    async healthCheck() {
        return this.request('agent/health', {
            method: 'GET'
        });
    }

    /**
     * Generic GET request
     */
    async get(endpoint) {
        return this.wrapResponse(this.request(endpoint, { method: 'GET' }));
    }

    /**
     * Generic POST request
     */
    async post(endpoint, data) {
        return this.wrapResponse(this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        }));
    }

    /**
     * Wrap response in success/error format
     */
    async wrapResponse(promise) {
        try {
            const data = await promise;
            return { success: true, data };
        } catch (error) {
            return { success: false, error: error.message, details: error };
        }
    }

    /**
     * Get compiled answer for a query
     */
    async getQueryAnswer(queryId) {
        return this.wrapResponse(this.request(`queries/${queryId}/answer`, {
            method: 'GET'
        }));
    }

    /**
     * Get contributions for a query
     */
    async getQueryContributions(queryId) {
        return this.wrapResponse(this.request(`queries/${queryId}/contributions`, {
            method: 'GET'
        }));
    }

    /**
     * Get query details
     */
    async getQueryDetails(queryId) {
        return this.wrapResponse(this.request(`queries/${queryId}`, {
            method: 'GET'
        }));
    }

    /**
     * Get query status (direct endpoint)
     */
    async getQueryStatusDirect(queryId) {
        return this.wrapResponse(this.request(`queries/${queryId}/status`, {
            method: 'GET'
        }));
    }
}

/**
 * Custom API Error class
 */
class APIError extends Error {
    constructor(message, status = 0, data = {}) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }

    /**
     * Get user-friendly error message
     */
    getUserMessage() {
        if (this.status === 0) {
            return 'Unable to connect to the server. Please check your internet connection and try again.';
        }
        
        if (this.status >= 500) {
            return 'Server error occurred. Please try again in a few moments.';
        }
        
        if (this.status === 429) {
            return 'Too many requests. Please wait a moment before trying again.';
        }
        
        if (this.status >= 400) {
            return this.message || 'Invalid request. Please check your input and try again.';
        }
        
        return this.message || 'An unexpected error occurred. Please try again.';
    }
}

/**
 * Query Status Tracker
 */
class QueryStatusTracker {
    constructor(apiClient, queryId, onUpdate, onComplete, onError, pollInterval = 2000) {
        this.apiClient = apiClient;
        this.queryId = queryId;
        this.onUpdate = onUpdate;
        this.onComplete = onComplete;
        this.onError = onError;
        this.pollIntervalMs = pollInterval;
        this.polling = false;
        this.pollTimeout = null;
        this.maxRetries = 3;
        this.retryCount = 0;
    }

    /**
     * Start polling for status updates
     */
    start() {
        if (this.polling) return;
        
        this.polling = true;
        this.poll();
    }

    /**
     * Stop polling
     */
    stop() {
        this.polling = false;
        if (this.pollTimeout) {
            clearTimeout(this.pollTimeout);
            this.pollTimeout = null;
        }
    }

    /**
     * Poll for status updates
     */
    async poll() {
        if (!this.polling) return;

        try {
            const response = await this.apiClient.getQueryStatus(this.queryId);
            
            if (response.success && response.data) {
                const status = response.data;
                this.retryCount = 0; // Reset retry count on successful response
                
                this.onUpdate(status);
                
                // Check if query is complete
                if (this.isQueryComplete(status)) {
                    this.stop();
                    this.onComplete(status);
                    return;
                }
            }
            
            // Continue polling
            this.scheduleNextPoll();
            
        } catch (error) {
            this.retryCount++;
            
            if (this.retryCount >= this.maxRetries) {
                this.stop();
                this.onError(error);
                return;
            }
            
            // Retry with exponential backoff
            const delay = Math.min(2000 * Math.pow(2, this.retryCount), 10000);
            setTimeout(() => this.poll(), delay);
        }
    }

    /**
     * Schedule next poll
     */
    scheduleNextPoll() {
        if (this.polling) {
            this.pollTimeout = setTimeout(() => this.poll(), this.pollIntervalMs);
        }
    }

    /**
     * Check if query is complete
     */
    isQueryComplete(status) {
        const terminalStatuses = ['completed', 'failed', 'cancelled'];
        return terminalStatuses.includes(status.status?.toLowerCase());
    }
}

// Export for use in app.js
window.APIClient = APIClient;
window.APIError = APIError;
window.QueryStatusTracker = QueryStatusTracker;