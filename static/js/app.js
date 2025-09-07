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

            const response = await this.apiClient.submitQuery(
                formData.phone,
                formData.question,
                formData.budgetCents
            );

            if (response.success && response.data?.query_id) {
                this.currentQuery = response.data;
                this.showProgressSection();
                this.startStatusTracking(response.data.query_id);
            } else {
                throw new Error(response.error || 'Failed to submit query');
            }

        } catch (error) {
            this.showError(error.getUserMessage ? error.getUserMessage() : error.message);
        } finally {
            this.setSubmitLoading(false);
        }
    }

    /**
     * Get form data
     */
    getFormData() {
        return {
            question: document.getElementById('question').value.trim(),
            phone: document.getElementById('phone').value.trim(),
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
     * Start status tracking
     */
    startStatusTracking(queryId) {
        this.statusTracker = new QueryStatusTracker(
            this.apiClient,
            queryId,
            (status) => this.handleStatusUpdate(status),
            (status) => this.handleQueryComplete(status),
            (error) => this.handleTrackingError(error)
        );
        
        this.statusTracker.start();
    }

    /**
     * Handle status updates
     */
    handleStatusUpdate(status) {
        const progress = this.getProgressFromStatus(status);
        
        document.getElementById('progressBar').style.width = `${progress.percent}%`;
        document.getElementById('progressPercent').textContent = `${progress.percent}%`;
        document.getElementById('progressStatus').textContent = progress.message;
        document.getElementById('statusMessage').textContent = progress.description;
        document.getElementById('timeEstimate').textContent = progress.timeEstimate;

        // Update query details if available
        if (status.experts_contacted !== undefined) {
            document.getElementById('queryDetails').classList.remove('hidden');
            document.getElementById('queryId').textContent = status.query_id || 'N/A';
            document.getElementById('expertsContacted').textContent = status.experts_contacted || 0;
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