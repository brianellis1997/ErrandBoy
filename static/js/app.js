/**
 * Main Application Logic for Query Submission Interface
 */

class QueryApp {
    constructor() {
        this.apiClient = new APIClient();
        this.statusTracker = null;
        this.currentQuery = null;
        
        this.initializeEventListeners();
        this.initializeBudgetSlider();
        this.initializeFormValidation();
        this.checkAuthentication();
    }

    /**
     * Check for authenticated expert and pre-populate phone
     */
    checkAuthentication() {
        // Check if expert is authenticated (stored in sessionStorage)
        const expertData = sessionStorage.getItem('expertData');
        if (expertData) {
            try {
                const expert = JSON.parse(expertData);
                if (expert.phone_number) {
                    // Update phone field
                    document.getElementById('phone').value = expert.phone_number;
                    document.getElementById('phone').disabled = true;
                    
                    // Update navigation to show logged in status
                    this.updateNavigationForLoggedInExpert(expert);
                    
                    // Add info message
                    const phoneContainer = document.getElementById('phone').parentElement;
                    const infoDiv = document.createElement('div');
                    infoDiv.className = 'mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md';
                    infoDiv.innerHTML = `
                        <p class="text-sm text-blue-800">
                            <strong>Logged in as expert:</strong> ${expert.name || expert.phone_number}
                            <button onclick="logoutExpert()" class="ml-2 text-blue-600 underline text-xs">
                                Use different number
                            </button>
                        </p>
                    `;
                    phoneContainer.appendChild(infoDiv);
                }
            } catch (e) {
                // Invalid data, clear it
                sessionStorage.removeItem('expertData');
            }
        }
    }

    /**
     * Update navigation to show logged in expert
     */
    updateNavigationForLoggedInExpert(expert) {
        // Find the navigation buttons container
        const navButtons = document.querySelector('nav .flex.gap-3');
        if (navButtons) {
            navButtons.innerHTML = `
                <span class="text-sm text-gray-600 px-3 py-2">
                    Welcome, <strong>${expert.name || 'Expert'}</strong>
                </span>
                <a href="/expert/dashboard" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition-colors font-medium">
                    Dashboard
                </a>
                <button onclick="logoutExpert()" class="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-md transition-colors">
                    Logout
                </button>
            `;
        }
    }

    /**
     * Logout expert (allow different phone number)
     */
    logoutExpert() {
        // Clear all session and local storage
        sessionStorage.clear();
        localStorage.clear();
        location.reload();
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        const form = document.getElementById('queryForm');
        form.addEventListener('submit', (e) => this.handleFormSubmit(e));

        // Real-time character count
        const questionInput = document.getElementById('question');
        questionInput.addEventListener('input', () => this.updateCharacterCount());

        // Phone number formatting
        const phoneInput = document.getElementById('phone');
        phoneInput.addEventListener('input', () => this.formatPhoneNumber());
    }

    /**
     * Initialize budget slider
     */
    initializeBudgetSlider() {
        const slider = document.getElementById('budget');
        const valueDisplay = document.getElementById('budgetValue');

        slider.addEventListener('input', () => {
            const value = parseInt(slider.value);
            const dollars = (value / 100).toFixed(2);
            valueDisplay.textContent = `$${dollars}`;
        });
    }

    /**
     * Initialize form validation
     */
    initializeFormValidation() {
        const questionInput = document.getElementById('question');
        const phoneInput = document.getElementById('phone');

        questionInput.addEventListener('blur', () => this.validateQuestion());
        phoneInput.addEventListener('blur', () => this.validatePhone());
    }

    /**
     * Handle form submission
     */
    async handleFormSubmit(event) {
        event.preventDefault();

        if (!this.validateForm()) {
            return;
        }

        const formData = this.getFormData();
        
        try {
            this.setSubmitLoading(true);
            this.hideAllSections();

            // Always use live network mode
            const response = await this.apiClient.submitQuery(
                formData.phone,
                formData.question,
                formData.budgetCents,
                true  // Always live mode
            );

            if (response && response.id) {
                this.currentQuery = response;
                this.showProgressSection();
                
                // Always show live mode started
                this.showLiveModeStarted(response);
            } else {
                throw new Error('Failed to submit query - invalid response');
            }

        } catch (error) {
            this.showError(error.getUserMessage ? error.getUserMessage() : error.message);
        } finally {
            this.setSubmitLoading(false);
        }
    }

    /**
     * Normalize phone number to +1XXXXXXXXXX format
     */
    normalizePhoneNumber(phone) {
        const digits = phone.replace(/\D/g, '');

        if (digits.length === 11 && digits.startsWith('1')) {
            return '+' + digits;
        } else if (digits.length === 10) {
            return '+1' + digits;
        } else if (digits.length === 11) {
            return '+' + digits;
        } else {
            return phone.startsWith('+') ? phone : '+' + digits;
        }
    }

    /**
     * Get form data
     */
    getFormData() {
        const rawPhone = document.getElementById('phone').value.trim();
        return {
            question: document.getElementById('question').value.trim(),
            phone: this.normalizePhoneNumber(rawPhone),
            budgetCents: parseInt(document.getElementById('budget').value)
        };
    }

    /**
     * Validate entire form
     */
    validateForm() {
        const isQuestionValid = this.validateQuestion();
        const isPhoneValid = this.validatePhone();
        
        return isQuestionValid && isPhoneValid;
    }

    /**
     * Validate question input
     */
    validateQuestion() {
        const input = document.getElementById('question');
        const error = document.getElementById('questionError');
        const value = input.value.trim();

        if (value.length < 10) {
            this.showFieldError(error, 'Question must be at least 10 characters');
            return false;
        }

        if (value.length > 500) {
            this.showFieldError(error, 'Question must be 500 characters or less');
            return false;
        }

        this.hideFieldError(error);
        return true;
    }

    /**
     * Validate phone input
     */
    validatePhone() {
        const input = document.getElementById('phone');
        const error = document.getElementById('phoneError');
        const value = input.value.trim();

        const phoneRegex = /^\+1[0-9]{10}$/;
        
        if (!phoneRegex.test(value)) {
            this.showFieldError(error, 'Please enter a valid US phone number (+1XXXXXXXXXX)');
            return false;
        }

        this.hideFieldError(error);
        return true;
    }

    /**
     * Show field error
     */
    showFieldError(errorElement, message) {
        errorElement.textContent = message;
        errorElement.classList.remove('hidden');
    }

    /**
     * Hide field error
     */
    hideFieldError(errorElement) {
        errorElement.classList.add('hidden');
    }

    /**
     * Update character count
     */
    updateCharacterCount() {
        const input = document.getElementById('question');
        const counter = document.getElementById('charCount');
        const count = input.value.length;
        
        counter.textContent = `${count}/500`;
        
        if (count > 500) {
            counter.classList.add('text-red-600');
            counter.classList.remove('text-gray-500');
        } else {
            counter.classList.add('text-gray-500');
            counter.classList.remove('text-red-600');
        }
    }

    /**
     * Format phone number input
     */
    formatPhoneNumber() {
        const input = document.getElementById('phone');
        let value = input.value.replace(/\D/g, '');
        
        if (value.length > 0 && !value.startsWith('1')) {
            value = '1' + value;
        }
        
        if (value.length > 11) {
            value = value.slice(0, 11);
        }
        
        if (value.length > 0) {
            input.value = '+' + value;
        }
    }

    /**
     * Set submit button loading state
     */
    setSubmitLoading(loading) {
        const btn = document.getElementById('submitBtn');
        const text = document.getElementById('submitText');
        const spinner = document.getElementById('submitSpinner');

        if (loading) {
            btn.disabled = true;
            text.classList.add('hidden');
            spinner.classList.remove('hidden');
        } else {
            btn.disabled = false;
            text.classList.remove('hidden');
            spinner.classList.add('hidden');
        }
    }

    /**
     * Hide all sections
     */
    hideAllSections() {
        ['progressSection', 'resultsSection', 'errorSection'].forEach(id => {
            document.getElementById(id).classList.add('hidden');
        });
    }

    /**
     * Show progress section
     */
    showProgressSection() {
        this.hideAllSections();
        document.getElementById('progressSection').classList.remove('hidden');
        document.getElementById('queryForm').style.opacity = '0.5';
    }

    /**
     * Show live mode started message
     */
    showLiveModeStarted(responseData) {
        const contributorsMatched = responseData.contributors_matched || 0;
        const contributionsReceived = responseData.contributions_received || 0;

        // Update progress section with live mode info
        document.getElementById('progressBar').style.width = '30%';
        document.getElementById('progressPercent').textContent = '30%';
        document.getElementById('progressStatus').textContent = '🔴 Live Network Active';

        // For MVP, show generic message
        document.getElementById('statusMessage').textContent =
            `Your question has been submitted to the network. We're matching it with knowledgeable contributors.`;

        document.getElementById('timeEstimate').textContent = 'Estimated time: 5-30 minutes (live responses)';

        // Show query details with loading state
        document.getElementById('queryDetails').classList.remove('hidden');
        document.getElementById('queryId').textContent = responseData.id || responseData.query_id;
        document.getElementById('expertsContacted').textContent = contributorsMatched > 0 ? contributorsMatched : '...';
        document.getElementById('responsesReceived').textContent = contributionsReceived;

        // Start tracking immediately for live mode
        this.startStatusTracking(responseData.id || responseData.query_id, true);

        // Do an immediate status check to get latest contributors count
        setTimeout(async () => {
            try {
                const status = await this.apiClient.getQueryStatus(responseData.id || responseData.query_id);
                if (status && status.contributors_matched !== undefined) {
                    document.getElementById('expertsContacted').textContent = status.contributors_matched || 0;
                    document.getElementById('responsesReceived').textContent = status.contributions_received || 0;
                }
            } catch (error) {
                console.error('Failed to get immediate status update:', error);
            }
        }, 2000); // Check after 2 seconds
    }

    /**
     * Start status tracking
     */
    startStatusTracking(queryId, liveMode = false) {
        this.statusTracker = new QueryStatusTracker(
            this.apiClient,
            queryId,
            (status) => this.handleStatusUpdate(status),
            (status) => this.handleQueryComplete(status),
            (error) => this.handleTrackingError(error),
            liveMode ? 10000 : 2000  // 10 second intervals for live mode, 2 seconds for demo
        );
        
        this.statusTracker.start();
    }

    /**
     * Handle status updates
     */
    handleStatusUpdate(status) {
        const progress = this.getProgressFromStatus(status);
        
        // Check if query failed
        if (status.status?.toLowerCase() === 'failed') {
            this.showError(status.error_message || 'Query failed: No experts found who can answer this question. Try inviting more experts to join the network!');
            return;
        }
        
        document.getElementById('progressBar').style.width = `${progress.percent}%`;
        document.getElementById('progressPercent').textContent = `${progress.percent}%`;
        document.getElementById('progressStatus').textContent = progress.message;
        document.getElementById('statusMessage').textContent = progress.description;
        document.getElementById('timeEstimate').textContent = progress.timeEstimate;

        // Update query details if available
        if (status.contributors_matched !== undefined) {
            document.getElementById('queryDetails').classList.remove('hidden');
            document.getElementById('queryId').textContent = status.id || status.query_id || 'N/A';
            document.getElementById('expertsContacted').textContent = status.contributors_matched || 0;
            document.getElementById('responsesReceived').textContent = status.contributions_received || 0;
        }
    }

    /**
     * Handle query completion
     */
    handleQueryComplete(status) {
        if (status.status?.toLowerCase() === 'completed' && status.final_answer) {
            this.showResults(status);
        } else {
            this.showError('Query completed but no answer was generated. This may be due to insufficient expert responses.');
        }
    }

    /**
     * Handle tracking error
     */
    handleTrackingError(error) {
        this.showError('Lost connection while tracking query status. ' + (error.getUserMessage ? error.getUserMessage() : error.message));
    }

    /**
     * Get progress information from status
     */
    getProgressFromStatus(status) {
        const statusLower = status.status?.toLowerCase() || 'pending';
        
        const progressMap = {
            'pending': {
                percent: 10,
                message: 'Analyzing question...',
                description: 'Processing your question and determining the best experts to contact.',
                timeEstimate: 'Estimated time: 3-5 minutes'
            },
            'routing': {
                percent: 25,
                message: 'Finding experts...',
                description: 'Matching your question with experts in our network.',
                timeEstimate: 'Estimated time: 2-4 minutes'
            },
            'collecting': {
                percent: 50,
                message: 'Contacting network...',
                description: 'Reaching out to selected experts and collecting responses.',
                timeEstimate: 'Estimated time: 1-3 minutes'
            },
            'compiling': {
                percent: 80,
                message: 'Synthesizing answer...',
                description: 'Combining expert responses into a comprehensive answer.',
                timeEstimate: 'Estimated time: 30-60 seconds'
            },
            'completed': {
                percent: 100,
                message: 'Complete!',
                description: 'Your answer is ready with expert citations.',
                timeEstimate: 'Done!'
            },
            'failed': {
                percent: 0,
                message: 'Query Failed',
                description: 'No experts found who can answer this question.',
                timeEstimate: 'Try asking a different question or invite more experts!'
            }
        };

        return progressMap[statusLower] || progressMap['pending'];
    }

    /**
     * Show results
     */
    showResults(status) {
        this.hideAllSections();
        
        document.getElementById('resultsSection').classList.remove('hidden');
        document.getElementById('answerContent').innerHTML = this.formatAnswer(status.final_answer);
        document.getElementById('confidenceScore').textContent = Math.round((status.confidence_score || 0) * 100);
        
        if (status.total_payout_cents && status.contributions_received) {
            const payout = (status.total_payout_cents / 100).toFixed(2);
            document.getElementById('totalPayout').textContent = `$${payout}`;
            document.getElementById('contributorCount').textContent = status.contributions_received;
        }
    }

    /**
     * Format answer with basic HTML
     */
    formatAnswer(answer) {
        return answer
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    /**
     * Show error
     */
    showError(message) {
        this.hideAllSections();
        document.getElementById('errorSection').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = message;
        document.getElementById('queryForm').style.opacity = '1';
    }

}

/**
 * Logout expert (allow different phone number)
 */
function logoutExpert() {
    // Clear all session and local storage
    sessionStorage.clear();
    localStorage.clear();
    location.reload();
}

/**
 * Reset form to initial state
 */
function resetForm() {
    document.getElementById('queryForm').reset();
    document.getElementById('queryForm').style.opacity = '1';
    document.getElementById('budgetValue').textContent = '$5.00';
    document.getElementById('charCount').textContent = '0/500';
    
    ['progressSection', 'resultsSection', 'errorSection'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });
    
    // Hide field errors
    ['questionError', 'phoneError'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });

    // Reset query details
    document.getElementById('queryDetails').classList.add('hidden');
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new QueryApp();
});