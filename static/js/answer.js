/**
 * Answer Display Application
 * Handles interactive citations, expert contributions, and process timeline
 */

class AnswerApp {
    constructor() {
        this.apiClient = new APIClient();
        this.queryId = null;
        this.answerData = null;
        this.contributionsData = null;
        this.currentCitation = null;
        
        this.initializeFromURL();
        this.initializeEventListeners();
    }

    /**
     * Initialize query ID from URL parameters
     */
    initializeFromURL() {
        // Try URL parameters first
        const urlParams = new URLSearchParams(window.location.search);
        this.queryId = urlParams.get('query_id') || urlParams.get('id');
        
        // Try URL path
        if (!this.queryId) {
            const pathParts = window.location.pathname.split('/');
            const answerIndex = pathParts.indexOf('answer');
            if (answerIndex !== -1 && pathParts[answerIndex + 1]) {
                this.queryId = pathParts[answerIndex + 1];
            }
        }

        // Try HTTP headers (from server route)
        if (!this.queryId) {
            const queryIdHeader = document.querySelector('meta[name="query-id"]');
            if (queryIdHeader) {
                this.queryId = queryIdHeader.content;
            }
        }

        if (this.queryId) {
            this.loadAnswerData();
        } else {
            this.showError('No query ID provided. Please check the URL.');
        }
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        document.getElementById('togglePanelBtn').addEventListener('click', () => {
            this.toggleBehindScenesPanel();
        });

        document.getElementById('shareBtn').addEventListener('click', () => {
            this.shareAnswer();
        });

        document.getElementById('closeCitationPopup').addEventListener('click', () => {
            this.hideCitationPopup();
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#citationPopup') && !e.target.closest('.citation-link')) {
                this.hideCitationPopup();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideCitationPopup();
            }
        });
    }

    /**
     * Load answer data from API
     */
    async loadAnswerData() {
        try {
            const [answerResponse, contributionsResponse] = await Promise.all([
                this.apiClient.get(`/api/v1/queries/${this.queryId}/answer`),
                this.apiClient.get(`/api/v1/queries/${this.queryId}/contributions`)
            ]);

            if (answerResponse.success && answerResponse.data) {
                this.answerData = answerResponse.data;
                this.contributionsData = contributionsResponse.success ? contributionsResponse.data : null;
                this.renderAnswer();
                this.showContent();
            } else {
                throw new Error(answerResponse.error || 'Failed to load answer');
            }
        } catch (error) {
            this.showError(error.getUserMessage ? error.getUserMessage() : error.message);
        }
    }

    /**
     * Render the complete answer display
     */
    renderAnswer() {
        this.renderAnswerContent();
        this.renderAnswerMetadata();
        this.renderCitationSummary();
        this.renderBehindScenes();
    }

    /**
     * Render answer content with interactive citations
     */
    renderAnswerContent() {
        const content = document.getElementById('answerContent');
        const answer = this.answerData.final_answer || '';
        
        const processedAnswer = this.processCitations(answer);
        content.innerHTML = processedAnswer;

        this.attachCitationListeners();
    }

    /**
     * Process [@handle] citations in answer text
     */
    processCitations(text) {
        const citationRegex = /@(\w+)/g;
        const citations = this.answerData.citations || [];
        
        return text.replace(citationRegex, (match, handle) => {
            const citation = citations.find(c => 
                c.claim_text.includes(match) || c.source_excerpt.includes(handle)
            );
            
            if (citation) {
                return `<span class="citation-link" data-citation-id="${citation.id}">${match}</span>`;
            }
            return match;
        });
    }

    /**
     * Attach click listeners to citation links
     */
    attachCitationListeners() {
        document.querySelectorAll('.citation-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const citationId = link.dataset.citationId;
                this.showCitationPopup(citationId, link);
            });

            link.addEventListener('mouseenter', () => {
                link.style.backgroundColor = '#dbeafe';
            });

            link.addEventListener('mouseleave', () => {
                link.style.backgroundColor = '';
            });
        });
    }

    /**
     * Show citation popup with contributor details
     */
    showCitationPopup(citationId, triggerElement) {
        const citation = this.answerData.citations?.find(c => c.id === citationId);
        if (!citation) return;

        const contribution = this.contributionsData?.contributions?.find(
            c => c.id === citation.contribution_id
        );

        if (!contribution) return;

        this.currentCitation = { citation, contribution };
        
        const popup = document.getElementById('citationPopup');
        const rect = triggerElement.getBoundingClientRect();

        document.getElementById('contributorName').textContent = `@${contribution.contact_id || 'Expert'}`;
        document.getElementById('contributorExpertise').textContent = contribution.extra_metadata?.expertise || 'Subject Matter Expert';
        document.getElementById('sourceExcerpt').textContent = citation.source_excerpt;
        document.getElementById('citationConfidence').textContent = Math.round(citation.confidence * 100);
        document.getElementById('citationResponseTime').textContent = 
            contribution.response_time_minutes ? `${Math.round(contribution.response_time_minutes)}m` : '--';

        popup.style.left = `${rect.left}px`;
        popup.style.top = `${rect.bottom + 10}px`;
        popup.classList.remove('hidden');
    }

    /**
     * Hide citation popup
     */
    hideCitationPopup() {
        document.getElementById('citationPopup').classList.add('hidden');
    }

    /**
     * Render answer metadata
     */
    renderAnswerMetadata() {
        const confidence = Math.round((this.answerData.confidence_score || 0) * 100);
        document.getElementById('confidenceScore').textContent = `${confidence}%`;

        const responseTime = this.calculateTotalResponseTime();
        document.getElementById('responseTime').textContent = responseTime;

        const expertCount = this.contributionsData?.contributions?.length || 0;
        document.getElementById('expertCount').textContent = expertCount;

        const totalCost = this.calculateTotalCost();
        document.getElementById('totalCost').textContent = totalCost;
    }

    /**
     * Calculate total response time
     */
    calculateTotalResponseTime() {
        if (!this.contributionsData?.contributions) return '--';
        
        const avgResponseTime = this.contributionsData.contributions.reduce(
            (sum, c) => sum + (c.response_time_minutes || 0), 0
        ) / this.contributionsData.contributions.length;
        
        return avgResponseTime > 0 ? `${Math.round(avgResponseTime)}m` : '--';
    }

    /**
     * Calculate total cost
     */
    calculateTotalCost() {
        if (!this.contributionsData?.contributions) return '--';
        
        const totalCents = this.contributionsData.contributions.reduce(
            (sum, c) => sum + (c.payout_amount_cents || 0), 0
        );
        
        return totalCents > 0 ? `$${(totalCents / 100).toFixed(2)}` : '--';
    }

    /**
     * Render citation summary badges
     */
    renderCitationSummary() {
        const container = document.getElementById('citationSummary');
        const citations = this.answerData.citations || [];

        if (citations.length === 0) {
            container.innerHTML = '<span class="text-gray-500 text-sm">No citations available</span>';
            return;
        }

        const citationMap = new Map();
        citations.forEach(citation => {
            const contributionId = citation.contribution_id;
            if (!citationMap.has(contributionId)) {
                citationMap.set(contributionId, { count: 0, citations: [] });
            }
            citationMap.get(contributionId).count++;
            citationMap.get(contributionId).citations.push(citation);
        });

        const badges = Array.from(citationMap.entries()).map(([contributionId, data]) => {
            const contribution = this.contributionsData?.contributions?.find(
                c => c.id === contributionId
            );
            const handle = contribution?.extra_metadata?.handle || 'Expert';
            
            return `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    @${handle}
                    <span class="ml-1 bg-blue-200 text-blue-800 rounded-full px-2 py-0.5">${data.count}</span>
                </span>
            `;
        }).join('');

        container.innerHTML = badges;
    }

    /**
     * Render behind-the-scenes content
     */
    renderBehindScenes() {
        this.renderProcessTimeline();
        this.renderExpertContributions();
        this.renderPaymentDistribution();
    }

    /**
     * Render process timeline
     */
    renderProcessTimeline() {
        const container = document.getElementById('processTimeline');
        const stages = [
            { name: 'Question Analysis', status: 'completed', duration: '30s' },
            { name: 'Expert Matching', status: 'completed', duration: '1m 15s' },
            { name: 'Network Outreach', status: 'completed', duration: '2m 30s' },
            { name: 'Response Collection', status: 'completed', duration: '45s' },
            { name: 'Answer Synthesis', status: 'completed', duration: '20s' }
        ];

        const timelineHTML = stages.map(stage => `
            <div class="timeline-item ${stage.status}">
                <div class="flex-shrink-0">
                    <div class="w-3 h-3 rounded-full ${
                        stage.status === 'completed' ? 'bg-green-400' : 
                        stage.status === 'current' ? 'bg-blue-400' : 'bg-gray-300'
                    }"></div>
                </div>
                <div class="flex-grow">
                    <div class="flex justify-between items-center">
                        <span class="font-medium text-gray-900">${stage.name}</span>
                        <span class="text-sm text-gray-500">${stage.duration}</span>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = timelineHTML;
    }

    /**
     * Render expert contributions
     */
    renderExpertContributions() {
        const container = document.getElementById('expertContributions');
        const contributions = this.contributionsData?.contributions || [];

        if (contributions.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center">No contributions available</p>';
            return;
        }

        const contributionsHTML = contributions.map(contribution => {
            const wasUsed = contribution.was_used;
            const citationCount = this.answerData.citations?.filter(
                c => c.contribution_id === contribution.id
            ).length || 0;

            return `
                <div class="bg-gray-50 rounded-lg p-4 border ${wasUsed ? 'border-green-200' : 'border-gray-200'}">
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <div class="font-medium text-gray-900">
                                @${contribution.extra_metadata?.handle || 'Expert'}
                                ${wasUsed ? '<span class="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Used in Answer</span>' : ''}
                            </div>
                            <div class="text-sm text-gray-600">
                                Confidence: ${Math.round(contribution.confidence_score * 100)}% | 
                                Response Time: ${contribution.response_time_minutes ? Math.round(contribution.response_time_minutes) + 'm' : '--'}
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-medium text-gray-900">
                                $${(contribution.payout_amount_cents / 100).toFixed(2)}
                            </div>
                            ${citationCount > 0 ? `<div class="text-xs text-green-600">${citationCount} citation${citationCount > 1 ? 's' : ''}</div>` : ''}
                        </div>
                    </div>
                    <div class="text-sm text-gray-700 bg-white p-3 rounded border">
                        ${contribution.response_text.length > 200 ? 
                            contribution.response_text.substring(0, 200) + '...' : 
                            contribution.response_text}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = contributionsHTML;
    }

    /**
     * Render payment distribution
     */
    renderPaymentDistribution() {
        const container = document.getElementById('paymentDistribution');
        const contributions = this.contributionsData?.contributions || [];
        
        const totalPayout = contributions.reduce((sum, c) => sum + c.payout_amount_cents, 0);
        const platformFee = Math.round(totalPayout * 0.2);
        const expertPayouts = totalPayout - platformFee;

        const paymentHTML = `
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="text-center">
                    <div class="text-2xl font-bold text-green-600">$${(expertPayouts / 100).toFixed(2)}</div>
                    <div class="text-sm text-gray-600">Expert Payments (80%)</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-blue-600">$${(platformFee / 100).toFixed(2)}</div>
                    <div class="text-sm text-gray-600">Platform Fee (20%)</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-gray-900">$${(totalPayout / 100).toFixed(2)}</div>
                    <div class="text-sm text-gray-600">Total Cost</div>
                </div>
            </div>
            <div class="mt-4 text-xs text-gray-500 text-center">
                Payments distributed automatically to ${contributions.length} expert${contributions.length > 1 ? 's' : ''}
            </div>
        `;

        container.innerHTML = paymentHTML;
    }

    /**
     * Toggle behind the scenes panel
     */
    toggleBehindScenesPanel() {
        const panel = document.getElementById('behindScenesPanel');
        const button = document.getElementById('togglePanelBtn');
        
        if (panel.classList.contains('hidden')) {
            panel.classList.remove('hidden');
            button.textContent = 'Hide Details';
        } else {
            panel.classList.add('hidden');
            button.textContent = 'Behind the Scenes';
        }
    }

    /**
     * Share answer functionality
     */
    shareAnswer() {
        const url = window.location.href;
        
        if (navigator.share) {
            navigator.share({
                title: 'GroupChat Answer',
                text: 'Check out this expert-sourced answer with citations',
                url: url
            });
        } else {
            navigator.clipboard.writeText(url).then(() => {
                this.showTemporaryMessage('Link copied to clipboard!');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
    }

    /**
     * Show temporary message
     */
    showTemporaryMessage(message) {
        const button = document.getElementById('shareBtn');
        const originalText = button.textContent;
        button.textContent = message;
        button.disabled = true;
        
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
        }, 2000);
    }

    /**
     * Show main content and hide loading
     */
    showContent() {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('mainContent').classList.remove('hidden');
    }

    /**
     * Show error state
     */
    showError(message) {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('mainContent').classList.remove('hidden');
        document.getElementById('errorState').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = message;
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AnswerApp();
});