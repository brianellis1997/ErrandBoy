/**
 * Expert Interface JavaScript
 * Handles expert response functionality and demo features
 */

class ExpertInterface {
    constructor() {
        this.currentExpert = null;
        this.selectedQuestion = null;
        this.questions = [];
        this.responseHistory = [];
        this.refreshInterval = null;
        
        this.expertProfiles = {
            alice_chen: {
                name: "Dr. Alice Chen",
                title: "AI/ML Researcher",
                bio: "PhD in Computer Science, specializing in neural networks and deep learning applications",
                expertise: ["artificial-intelligence", "machine-learning", "data-science", "neural-networks"],
                responseRate: "94%",
                avgRating: "4.8",
                totalResponses: 127
            },
            bob_martinez: {
                name: "Bob Martinez", 
                title: "Full-Stack Developer",
                bio: "10+ years building scalable web applications with React, Node.js, and cloud platforms",
                expertise: ["web-development", "javascript", "react", "node-js", "cloud-computing"],
                responseRate: "91%",
                avgRating: "4.6",
                totalResponses: 203
            },
            sarah_kim: {
                name: "Sarah Kim",
                title: "Product Manager", 
                bio: "Strategic product leader with experience launching consumer and B2B software products",
                expertise: ["product-management", "user-experience", "strategy", "agile"],
                responseRate: "88%",
                avgRating: "4.7",
                totalResponses: 89
            },
            mike_johnson: {
                name: "Mike Johnson",
                title: "Database Architect",
                bio: "Database design expert specializing in PostgreSQL, MongoDB, and distributed systems",
                expertise: ["databases", "postgresql", "mongodb", "distributed-systems", "performance"],
                responseRate: "96%",
                avgRating: "4.9", 
                totalResponses: 156
            },
            lisa_wang: {
                name: "Lisa Wang",
                title: "UX Designer",
                bio: "Human-centered design advocate with expertise in user research and interface design",
                expertise: ["user-experience", "design", "user-research", "prototyping"],
                responseRate: "92%",
                avgRating: "4.8",
                totalResponses: 74
            }
        };

        this.responseTemplates = {
            need_more_info: "I'd be happy to help with this question, but I need some additional context to provide a comprehensive answer. Could you please clarify [specific aspect]? This will help me give you the most accurate and useful response.",
            
            outside_expertise: "While this is an interesting question, it falls outside my primary area of expertise. I'd recommend connecting with someone who specializes in [relevant field] for the most accurate guidance.",
            
            detailed_answer: "Based on my experience with [relevant area], here's a comprehensive breakdown:\n\n1. [Main point]\n2. [Supporting detail]\n3. [Implementation considerations]\n\nKey considerations: [important factors to remember]\n\nWould you like me to elaborate on any of these points?"
        };

        this.sampleQuestions = [
            {
                id: "demo-1",
                question_text: "What are the best practices for scaling PostgreSQL databases in production environments?",
                user_phone: "+1***-***-1234",
                max_spend_cents: 750,
                created_at: new Date(Date.now() - 1200000).toISOString(), // 20 minutes ago
                status: "collecting",
                expertise_tags: ["databases", "postgresql", "performance"],
                responses_received: 0
            },
            {
                id: "demo-2", 
                question_text: "How should I optimize React performance for large datasets with complex filtering?",
                user_phone: "+1***-***-5678",
                max_spend_cents: 500,
                created_at: new Date(Date.now() - 900000).toISOString(), // 15 minutes ago
                status: "collecting", 
                expertise_tags: ["web-development", "react", "javascript"],
                responses_received: 1
            },
            {
                id: "demo-3",
                question_text: "What's the current state of GPT models for automated code generation and review?",
                user_phone: "+1***-***-9012", 
                max_spend_cents: 1000,
                created_at: new Date(Date.now() - 600000).toISOString(), // 10 minutes ago
                status: "collecting",
                expertise_tags: ["artificial-intelligence", "machine-learning", "code-generation"],
                responses_received: 0
            },
            {
                id: "demo-4",
                question_text: "How should I structure a microservices architecture for a growing e-commerce platform?", 
                user_phone: "+1***-***-3456",
                max_spend_cents: 800,
                created_at: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
                status: "collecting",
                expertise_tags: ["architecture", "microservices", "distributed-systems"],
                responses_received: 0
            },
            {
                id: "demo-5",
                question_text: "What are the key UX principles for designing mobile-first financial applications?",
                user_phone: "+1***-***-7890",
                max_spend_cents: 600, 
                created_at: new Date(Date.now() - 180000).toISOString(), // 3 minutes ago
                status: "collecting",
                expertise_tags: ["user-experience", "design", "mobile", "fintech"],
                responses_received: 0
            }
        ];

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadExpertFromStorage();
        this.startAutoRefresh();
        this.loadQuestions();
    }

    setupEventListeners() {
        // Expert selector
        document.getElementById('expertSelect').addEventListener('change', (e) => {
            this.switchExpert(e.target.value);
        });

        // Demo controls
        document.getElementById('loadSampleQueries').addEventListener('click', () => {
            this.loadSampleQuestions();
        });

        document.getElementById('resetDemo').addEventListener('click', () => {
            this.resetDemo();
        });

        // Question management
        document.getElementById('refreshQuestions').addEventListener('click', () => {
            this.loadQuestions();
        });

        document.getElementById('statusFilter').addEventListener('change', () => {
            this.applyFilters();
        });

        document.getElementById('myExpertiseFilter').addEventListener('click', (e) => {
            e.target.classList.toggle('bg-primary');
            e.target.classList.toggle('text-white');
            e.target.classList.toggle('bg-gray-100');
            this.applyFilters();
        });

        // Response form
        document.getElementById('responseText').addEventListener('input', (e) => {
            this.updateCharCount(e.target);
            this.validateResponse();
        });

        document.getElementById('confidenceSlider').addEventListener('input', (e) => {
            document.getElementById('confidenceValue').textContent = e.target.value;
        });

        // Template buttons
        document.querySelectorAll('.template-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const template = e.target.getAttribute('data-template');
                this.applyTemplate(template);
            });
        });

        // Submit buttons
        document.getElementById('submitResponse').addEventListener('click', () => {
            this.submitResponse();
        });

        document.getElementById('cancelResponse').addEventListener('click', () => {
            this.clearResponseForm();
        });

        // Modal close
        document.getElementById('closeSuccessModal').addEventListener('click', () => {
            this.hideSuccessModal();
        });
    }

    loadExpertFromStorage() {
        const savedExpert = localStorage.getItem('selectedExpert') || 'alice_chen';
        document.getElementById('expertSelect').value = savedExpert;
        this.switchExpert(savedExpert);
    }

    switchExpert(expertId) {
        this.currentExpert = this.expertProfiles[expertId];
        localStorage.setItem('selectedExpert', expertId);
        
        // Update expert info display
        document.getElementById('expertBio').textContent = this.currentExpert.bio;
        document.getElementById('responseRate').textContent = this.currentExpert.responseRate;
        document.getElementById('avgRating').textContent = this.currentExpert.avgRating;
        
        // Clear any selected question since expert changed
        this.clearResponseForm();
        this.applyFilters();
    }

    startAutoRefresh() {
        // Refresh questions every 30 seconds
        this.refreshInterval = setInterval(() => {
            if (!document.hidden) {
                this.loadQuestions();
            }
        }, 30000);
    }

    async loadQuestions() {
        try {
            // Try to load real queries from API first
            try {
                const response = await fetch('/api/v1/queries?status=collecting');
                if (response.ok) {
                    const data = await response.json();
                    this.questions = data.queries.map(query => ({
                        id: query.id,
                        question_text: query.question_text,
                        user_phone: query.user_phone.replace(/(\d{3})(\d{3})(\d{4})/, '+1***-***-$3'),
                        max_spend_cents: query.total_cost_cents,
                        created_at: query.created_at,
                        status: query.status,
                        expertise_tags: [], // Would be derived from matching in real app
                        responses_received: 0 // Would be counted from contributions
                    }));
                } else {
                    throw new Error('API call failed');
                }
            } catch (apiError) {
                // Fall back to localStorage if API fails
                console.warn('API call failed, using localStorage:', apiError);
                const savedQuestions = localStorage.getItem('expertDemoQuestions');
                if (savedQuestions) {
                    this.questions = JSON.parse(savedQuestions);
                } else {
                    this.questions = [];
                }
            }
            
            this.updateLastRefreshed();
            this.applyFilters();
        } catch (error) {
            console.error('Error loading questions:', error);
            this.showError('Failed to load questions');
        }
    }

    loadSampleQuestions() {
        this.questions = [...this.sampleQuestions];
        localStorage.setItem('expertDemoQuestions', JSON.stringify(this.questions));
        this.applyFilters();
        this.showNotification('Sample questions loaded successfully');
    }

    resetDemo() {
        this.questions = [];
        this.responseHistory = [];
        this.selectedQuestion = null;
        localStorage.removeItem('expertDemoQuestions');
        localStorage.removeItem('expertResponseHistory');
        
        this.applyFilters();
        this.clearResponseForm();
        this.updateResponseHistory();
        this.showNotification('Demo reset successfully');
    }

    applyFilters() {
        const statusFilter = document.getElementById('statusFilter').value;
        const expertiseFilter = document.getElementById('myExpertiseFilter').classList.contains('bg-primary');
        
        let filteredQuestions = this.questions;
        
        // Filter by status
        if (statusFilter !== 'all') {
            filteredQuestions = filteredQuestions.filter(q => q.status === statusFilter);
        }
        
        // Filter by expertise
        if (expertiseFilter && this.currentExpert) {
            filteredQuestions = filteredQuestions.filter(q => 
                q.expertise_tags.some(tag => 
                    this.currentExpert.expertise.includes(tag)
                )
            );
        }
        
        this.renderQuestionList(filteredQuestions);
    }

    renderQuestionList(questions) {
        const questionList = document.getElementById('questionList');
        
        if (questions.length === 0) {
            questionList.innerHTML = `
                <div class="p-4 text-center text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <p>No questions available</p>
                    <p class="text-sm">Check back soon or load sample questions</p>
                </div>
            `;
            return;
        }
        
        questionList.innerHTML = questions.map(question => `
            <div class="p-4 cursor-pointer hover:bg-gray-50 transition duration-200" onclick="expertInterface.selectQuestion('${question.id}')">
                <div class="mb-2">
                    <h3 class="font-medium text-gray-900 line-clamp-2">${question.question_text}</h3>
                </div>
                
                <div class="flex justify-between items-center text-sm text-gray-600 mb-2">
                    <span>From: ${question.user_phone}</span>
                    <span class="text-green-600 font-medium">$${(question.max_spend_cents / 100).toFixed(2)}</span>
                </div>
                
                <div class="flex justify-between items-center text-xs text-gray-500">
                    <span>${this.timeAgo(question.created_at)}</span>
                    <span>${question.responses_received} responses</span>
                </div>
                
                <div class="mt-2 flex flex-wrap gap-1">
                    ${question.expertise_tags.slice(0, 3).map(tag => 
                        `<span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">${tag}</span>`
                    ).join('')}
                </div>
            </div>
        `).join('');
    }

    selectQuestion(questionId) {
        const question = this.questions.find(q => q.id === questionId);
        if (!question) return;
        
        this.selectedQuestion = question;
        
        // Update selected question display
        document.getElementById('questionText').textContent = question.question_text;
        document.getElementById('requesterInfo').textContent = question.user_phone;
        document.getElementById('paymentAmount').textContent = `$${(question.max_spend_cents / 100).toFixed(2)}`;
        
        // Show response form
        document.getElementById('noQuestionSelected').classList.add('hidden');
        document.getElementById('responseForm').classList.remove('hidden');
        
        // Clear any previous response
        document.getElementById('responseText').value = '';
        document.getElementById('confidenceSlider').value = '5';
        document.getElementById('confidenceValue').textContent = '5';
        document.getElementById('sourcesLinks').value = '';
        this.updateCharCount(document.getElementById('responseText'));
    }

    clearResponseForm() {
        this.selectedQuestion = null;
        document.getElementById('responseForm').classList.add('hidden');
        document.getElementById('noQuestionSelected').classList.remove('hidden');
    }

    applyTemplate(templateId) {
        const template = this.responseTemplates[templateId];
        if (template) {
            document.getElementById('responseText').value = template;
            this.updateCharCount(document.getElementById('responseText'));
            this.validateResponse();
        }
    }

    updateCharCount(textarea) {
        const charCount = textarea.value.length;
        document.getElementById('responseCharCount').textContent = `${charCount}/1000`;
        
        if (charCount > 1000) {
            document.getElementById('responseCharCount').classList.add('text-red-600');
        } else {
            document.getElementById('responseCharCount').classList.remove('text-red-600');
        }
    }

    validateResponse() {
        const responseText = document.getElementById('responseText').value;
        const errorSpan = document.getElementById('responseError');
        const submitBtn = document.getElementById('submitResponse');
        
        let isValid = true;
        let errorMessage = '';
        
        if (responseText.length < 50) {
            isValid = false;
            errorMessage = 'Response must be at least 50 characters';
        } else if (responseText.length > 1000) {
            isValid = false; 
            errorMessage = 'Response must not exceed 1000 characters';
        }
        
        if (errorMessage) {
            errorSpan.textContent = errorMessage;
            errorSpan.classList.remove('hidden');
        } else {
            errorSpan.classList.add('hidden');
        }
        
        submitBtn.disabled = !isValid;
        return isValid;
    }

    async submitResponse() {
        if (!this.selectedQuestion || !this.validateResponse()) {
            return;
        }
        
        const responseText = document.getElementById('responseText').value;
        const confidence = parseInt(document.getElementById('confidenceSlider').value);
        const sources = document.getElementById('sourcesLinks').value;
        
        // Show loading state
        document.getElementById('submitText').classList.add('hidden');
        document.getElementById('submitSpinner').classList.remove('hidden');
        document.getElementById('submitResponse').disabled = true;
        
        try {
            // Try to submit to real API first
            try {
                const apiResponse = await fetch(`/api/v1/queries/${this.selectedQuestion.id}/contributions`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        response_text: responseText,
                        confidence_score: confidence / 10, // Convert to 0.1-1.0 scale
                        source_links: sources,
                        expert_name: this.currentExpert.name
                    })
                });
                
                if (apiResponse.ok) {
                    const contributionData = await apiResponse.json();
                    console.log('Successfully submitted contribution:', contributionData);
                } else {
                    const errorData = await apiResponse.json();
                    throw new Error(errorData.detail || 'Failed to submit contribution');
                }
            } catch (apiError) {
                console.warn('API submission failed, using demo mode:', apiError);
                // Fall back to demo behavior
                await new Promise(resolve => setTimeout(resolve, 1500));
            }
            
            const response = {
                id: `response-${Date.now()}`,
                question_id: this.selectedQuestion.id,
                question_text: this.selectedQuestion.question_text,
                response_text: responseText,
                confidence_score: confidence / 10,
                sources: sources,
                expert_name: this.currentExpert.name,
                submitted_at: new Date().toISOString()
            };
            
            // Add to response history
            this.responseHistory.unshift(response);
            localStorage.setItem('expertResponseHistory', JSON.stringify(this.responseHistory));
            
            // Update question status (mark as having one more response)
            this.selectedQuestion.responses_received += 1;
            localStorage.setItem('expertDemoQuestions', JSON.stringify(this.questions));
            
            this.showSuccessModal();
            this.clearResponseForm();
            this.updateResponseHistory();
            this.applyFilters(); // Refresh question list
            
        } catch (error) {
            console.error('Error submitting response:', error);
            this.showError('Failed to submit response. Please try again.');
        } finally {
            // Reset button state
            document.getElementById('submitText').classList.remove('hidden');
            document.getElementById('submitSpinner').classList.add('hidden');
            document.getElementById('submitResponse').disabled = false;
        }
    }

    updateResponseHistory() {
        // Load from storage
        const savedHistory = localStorage.getItem('expertResponseHistory');
        if (savedHistory) {
            this.responseHistory = JSON.parse(savedHistory);
        }
        
        const historyContainer = document.getElementById('responseHistory');
        
        if (this.responseHistory.length === 0) {
            historyContainer.innerHTML = `
                <div class="p-4 text-center text-gray-500">
                    <p>No responses yet</p>
                    <p class="text-sm">Your submitted responses will appear here</p>
                </div>
            `;
            return;
        }
        
        historyContainer.innerHTML = this.responseHistory.map(response => `
            <div class="p-4">
                <div class="mb-2">
                    <h4 class="font-medium text-gray-900 line-clamp-2">${response.question_text}</h4>
                </div>
                <div class="text-sm text-gray-700 mb-2 line-clamp-3">${response.response_text}</div>
                <div class="flex justify-between items-center text-xs text-gray-500">
                    <span>Confidence: ${Math.round(response.confidence_score * 10)}/10</span>
                    <span>${this.timeAgo(response.submitted_at)}</span>
                </div>
            </div>
        `).join('');
    }

    showSuccessModal() {
        document.getElementById('successModal').classList.remove('hidden');
    }

    hideSuccessModal() {
        document.getElementById('successModal').classList.add('hidden');
    }

    updateLastRefreshed() {
        document.getElementById('lastUpdated').textContent = 'Just updated';
    }

    showNotification(message) {
        // Simple notification - could be enhanced with a proper toast system
        console.log('Notification:', message);
    }

    showError(message) {
        console.error('Error:', message);
        alert(message); // Simple error display - could be enhanced
    }

    timeAgo(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diffInMinutes = Math.floor((now - time) / 60000);
        
        if (diffInMinutes < 1) return 'Just now';
        if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
        if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
        return `${Math.floor(diffInMinutes / 1440)}d ago`;
    }
}

// Initialize the expert interface when the page loads
let expertInterface;
document.addEventListener('DOMContentLoaded', () => {
    expertInterface = new ExpertInterface();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (expertInterface && expertInterface.refreshInterval) {
        clearInterval(expertInterface.refreshInterval);
    }
});