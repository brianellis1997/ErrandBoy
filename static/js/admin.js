/**
 * GroupChat Admin Dashboard JavaScript
 * Handles all dashboard functionality including data loading, charts, and real-time updates
 */

class AdminDashboard {
    constructor() {
        this.demoMode = false;
        this.charts = {};
        this.refreshInterval = null;
        this.websocket = null;
        this.lastUpdate = null;
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.setupTabs();
        await this.loadInitialData();
        this.startAutoRefresh();
        this.connectWebSocket();
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshData();
        });

        // Demo mode toggle
        document.getElementById('demoModeToggle').addEventListener('click', () => {
            this.toggleDemoMode();
        });

        // Search and filter functionality
        const querySearch = document.getElementById('querySearch');
        if (querySearch) {
            querySearch.addEventListener('input', () => this.filterQueries());
        }

        const statusFilter = document.getElementById('statusFilter');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => this.filterQueries());
        }

        const dateFilter = document.getElementById('dateFilter');
        if (dateFilter) {
            dateFilter.addEventListener('change', () => this.filterQueries());
        }
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.dataset.tab;
                
                // Remove active classes
                tabButtons.forEach(btn => {
                    btn.classList.remove('active', 'border-primary', 'text-primary');
                    btn.classList.add('border-transparent', 'text-gray-500');
                });
                tabContents.forEach(content => content.classList.remove('active'));

                // Add active classes
                button.classList.add('active', 'border-primary', 'text-primary');
                button.classList.remove('border-transparent', 'text-gray-500');
                document.getElementById(targetTab).classList.add('active');

                // Load tab-specific data
                this.loadTabData(targetTab);
            });
        });
    }

    async loadInitialData() {
        this.showLoading(true);
        const errors = [];
        
        try {
            // Load data with individual error handling
            const results = await Promise.allSettled([
                this.loadSystemStats().catch(e => { errors.push('System stats: ' + e.message); throw e; }),
                this.loadQueries().catch(e => { errors.push('Queries: ' + e.message); throw e; }),
                this.loadExperts().catch(e => { errors.push('Experts: ' + e.message); throw e; }),
                this.loadPayments().catch(e => { errors.push('Payments: ' + e.message); throw e; })
            ]);
            
            // Check for any failures
            const failedRequests = results.filter(result => result.status === 'rejected');
            if (failedRequests.length > 0) {
                console.warn(`${failedRequests.length} requests failed:`, failedRequests);
                // Continue with partial data rather than failing completely
            }
            
            this.initializeCharts();
            this.updateLastRefreshed();
            
            if (errors.length > 0) {
                this.showError(`Some data failed to load: ${errors.join(', ')}`);
            }
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load dashboard data - check console for details');
            
            // Fall back to demo mode if there's a complete failure
            if (!this.demoMode) {
                console.log('Attempting to enable demo mode as fallback');
                this.toggleDemoMode();
            }
        } finally {
            this.showLoading(false);
        }
    }

    async loadSystemStats() {
        try {
            console.log('Loading system stats...');
            const response = await fetch('/api/v1/admin/stats');
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('System stats API error:', response.status, errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            console.log('System stats loaded successfully:', data);
            
            this.updateSystemMetrics(data);
            this.updateSystemHealth(data);
            
            return data;
        } catch (error) {
            console.error('Error loading system stats:', error);
            throw new Error(`System stats failed: ${error.message}`);
        }
    }

    updateSystemMetrics(data) {
        // Update main metrics with null checks
        const totalQueries = document.getElementById('totalQueries');
        const activeExperts = document.getElementById('activeExperts');
        
        if (totalQueries) totalQueries.textContent = data.queries?.total || '0';
        if (activeExperts) activeExperts.textContent = data.contacts?.active || '0';
        
        // Calculate and display payment total (mock for now)
        const totalPayments = this.demoMode ? '$12,450' : '--';
        const totalPaymentsEl = document.getElementById('totalPayments');
        if (totalPaymentsEl) totalPaymentsEl.textContent = totalPayments;
        
        // Calculate average response time (mock for now)
        const avgResponseTime = this.demoMode ? '2.4h' : '--';
        const avgResponseTimeEl = document.getElementById('avgResponseTime');
        if (avgResponseTimeEl) avgResponseTimeEl.textContent = avgResponseTime;

        // Update change indicators
        const recent24h = data.queries?.recent_24h || 0;
        const queriesChangeEl = document.getElementById('queriesChange');
        if (queriesChangeEl) queriesChangeEl.textContent = `+${recent24h} in last 24h`;
        
        const recentExperts = data.contacts?.recent_24h || 0;
        const expertsChangeEl = document.getElementById('expertsChange');
        if (expertsChangeEl) expertsChangeEl.textContent = `+${recentExperts} new experts`;
        
        const paymentsChangeEl = document.getElementById('paymentsChange');
        if (paymentsChangeEl) paymentsChangeEl.textContent = this.demoMode ? '+$1,250 today' : '--';
        
        const responseTimeChangeEl = document.getElementById('responseTimeChange');
        if (responseTimeChangeEl) responseTimeChangeEl.textContent = this.demoMode ? '15% faster' : '--';

        // Update system status
        const isHealthy = data.database?.status === 'healthy';
        const statusDots = document.querySelectorAll('.status-dot');
        const statusText = document.getElementById('systemStatus');
        
        statusDots.forEach(dot => {
            dot.className = `status-dot ${isHealthy ? 'status-healthy' : 'status-error'}`;
        });
        
        if (statusText) {
            statusText.textContent = isHealthy ? 'System Healthy' : 'System Issues';
        }
    }

    updateSystemHealth(data) {
        const healthContainer = document.getElementById('systemHealth');
        if (!healthContainer) return;

        const healthItems = [
            {
                name: 'Database',
                status: data.database?.status || 'unknown',
                details: `Connection: ${data.database?.status === 'healthy' ? 'Active' : 'Failed'}`
            },
            {
                name: 'Redis Cache',
                status: data.redis?.configured ? 'healthy' : 'not_configured',
                details: data.redis?.configured ? 'Connected' : 'Not configured'
            },
            {
                name: 'Twilio SMS',
                status: data.integrations?.twilio?.configured ? 'healthy' : 'not_configured',
                details: data.integrations?.twilio?.enabled ? 'Enabled' : 'Disabled'
            },
            {
                name: 'OpenAI API',
                status: data.integrations?.openai?.configured ? 'healthy' : 'not_configured',
                details: data.integrations?.openai?.configured ? 'Connected' : 'Not configured'
            }
        ];

        healthContainer.innerHTML = healthItems.map(item => `
            <div class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                <div class="flex items-center">
                    <div class="status-dot status-${this.getStatusClass(item.status)}"></div>
                    <span class="font-medium">${item.name}</span>
                </div>
                <span class="text-sm text-gray-600">${item.details}</span>
            </div>
        `).join('');
    }

    getStatusClass(status) {
        switch (status) {
            case 'healthy': return 'healthy';
            case 'not_configured': return 'warning';
            case 'unhealthy': return 'error';
            default: return 'warning';
        }
    }

    async loadQueries() {
        try {
            const response = await fetch('/api/v1/admin/queries');
            let queries = [];
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    queries = result.data.queries.map(q => ({
                        id: q.id,
                        question: q.question_text,
                        status: q.status,
                        created: q.created_at,
                        budget: q.max_spend_cents,
                        responses: q.response_count,
                        expert_count: q.expert_count
                    }));
                }
            }
            
            // Fallback to mock data in demo mode or on error
            if (queries.length === 0 && this.demoMode) {
                queries = this.getMockQueries();
            }
            
            this.renderQueriesTable(queries);
            return queries;
        } catch (error) {
            console.error('Error loading queries:', error);
            // Show mock data in demo mode on error
            if (this.demoMode) {
                const queries = this.getMockQueries();
                this.renderQueriesTable(queries);
                return queries;
            }
            throw error;
        }
    }

    getMockQueries() {
        return [
            {
                id: 'q-001',
                question: 'What are the latest AI trends in 2024?',
                status: 'completed',
                created: '2024-01-15T10:30:00Z',
                budget: 500,
                responses: 3,
                expert_count: 5
            },
            {
                id: 'q-002', 
                question: 'How to implement microservices architecture?',
                status: 'collecting',
                created: '2024-01-15T14:22:00Z',
                budget: 750,
                responses: 1,
                expert_count: 8
            },
            {
                id: 'q-003',
                question: 'Best practices for React performance optimization',
                status: 'routing',
                created: '2024-01-15T16:45:00Z',
                budget: 300,
                responses: 0,
                expert_count: 12
            }
        ];
    }

    renderQueriesTable(queries) {
        const tableBody = document.getElementById('queriesTable');
        if (!tableBody) return;

        tableBody.innerHTML = queries.map(query => `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${query.id}
                </td>
                <td class="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                    ${query.question}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${this.getStatusBadgeClass(query.status)}">
                        ${query.status}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${new Date(query.created).toLocaleDateString()}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    $${(query.budget / 100).toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button class="text-primary hover:text-blue-900" onclick="window.location.href='/answer/${query.id}'">
                        View
                    </button>
                </td>
            </tr>
        `).join('');
    }

    getStatusBadgeClass(status) {
        const classes = {
            'pending': 'bg-yellow-100 text-yellow-800',
            'routing': 'bg-blue-100 text-blue-800', 
            'collecting': 'bg-purple-100 text-purple-800',
            'completed': 'bg-green-100 text-green-800',
            'failed': 'bg-red-100 text-red-800'
        };
        return classes[status] || 'bg-gray-100 text-gray-800';
    }

    async loadExperts() {
        try {
            const response = await fetch('/api/v1/admin/contacts/summary');
            let experts = [];
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    experts = result.data.experts.map(e => ({
                        id: e.id,
                        name: e.name,
                        expertise: e.expertise_areas,
                        trust_score: e.trust_score,
                        response_rate: e.response_rate,
                        avg_response_time: e.avg_response_time,
                        total_earnings: e.total_earnings,
                        queries_answered: e.queries_answered
                    }));
                }
            }
            
            // Fallback to mock data in demo mode or on error
            if (experts.length === 0 && this.demoMode) {
                experts = this.getMockExperts();
            }
            
            this.renderExpertsGrid(experts);
            this.updateExpertMetrics(experts);
            return experts;
        } catch (error) {
            console.error('Error loading experts:', error);
            // Show mock data in demo mode on error
            if (this.demoMode) {
                const experts = this.getMockExperts();
                this.renderExpertsGrid(experts);
                this.updateExpertMetrics(experts);
                return experts;
            }
            throw error;
        }
    }

    getMockExperts() {
        return [
            {
                id: 'exp-001',
                name: 'Dr. Sarah Chen',
                expertise: ['AI/ML', 'Computer Vision'],
                trust_score: 98,
                response_rate: 95,
                avg_response_time: '2.1h',
                total_earnings: 2450,
                queries_answered: 23
            },
            {
                id: 'exp-002',
                name: 'Marcus Rodriguez',
                expertise: ['Backend Architecture', 'Microservices'],
                trust_score: 94,
                response_rate: 87,
                avg_response_time: '3.2h',
                total_earnings: 1890,
                queries_answered: 18
            },
            {
                id: 'exp-003',
                name: 'Emily Watson',
                expertise: ['React', 'Frontend Performance'],
                trust_score: 92,
                response_rate: 91,
                avg_response_time: '1.8h',
                total_earnings: 1650,
                queries_answered: 15
            }
        ];
    }

    renderExpertsGrid(experts) {
        const grid = document.getElementById('expertsGrid');
        if (!grid) return;

        grid.innerHTML = experts.map(expert => `
            <div class="bg-gray-50 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div class="flex items-center mb-3">
                    <div class="w-10 h-10 bg-primary rounded-full flex items-center justify-center text-white font-bold">
                        ${expert.name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <div class="ml-3">
                        <h4 class="font-medium text-gray-900">${expert.name}</h4>
                        <p class="text-sm text-gray-500">Trust: ${expert.trust_score}%</p>
                    </div>
                </div>
                <div class="space-y-2">
                    <div class="flex flex-wrap gap-1">
                        ${Array.isArray(expert.expertise) 
                            ? expert.expertise.map(skill => `
                                <span class="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">${skill}</span>
                            `).join('')
                            : `<span class="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">${expert.expertise}</span>`
                        }
                    </div>
                    <div class="text-sm text-gray-600">
                        <div>Response Rate: ${expert.response_rate}%</div>
                        <div>Avg Time: ${expert.avg_response_time}</div>
                        <div>Earnings: $${expert.total_earnings}</div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    updateExpertMetrics(experts) {
        if (!experts.length) return;

        const totalExperts = experts.length;
        const avgTrustScore = Math.round(experts.reduce((sum, e) => sum + e.trust_score, 0) / totalExperts);
        const avgResponseRate = Math.round(experts.reduce((sum, e) => sum + e.response_rate, 0) / totalExperts);

        document.getElementById('totalExperts').textContent = totalExperts.toString();
        document.getElementById('avgTrustScore').textContent = `${avgTrustScore}%`;
        document.getElementById('responseRate').textContent = `${avgResponseRate}%`;
    }

    async loadPayments() {
        try {
            const response = await fetch('/api/v1/ledger/stats/platform');
            let data = {};
            
            if (response.ok) {
                const result = await response.json();
                data = result.success ? result.data : {};
            }
            
            this.renderPaymentData(data);
            return data;
        } catch (error) {
            console.error('Error loading payments:', error);
            // Show demo data on error
            if (this.demoMode) {
                this.renderPaymentData(this.getMockPaymentData());
            }
            throw error;
        }
    }

    getMockPaymentData() {
        return {
            summary: {
                total_platform_fees_dollars: 2490.50,
                total_referral_pool_dollars: 1245.25,
                queries_processed: 47
            },
            recent_platform_transactions: [
                {
                    id: 'tx-001',
                    transaction_type: 'platform_fee',
                    amount_cents: 100,
                    timestamp: '2024-01-15T14:30:00Z',
                    status: 'completed'
                },
                {
                    id: 'tx-002', 
                    transaction_type: 'platform_fee',
                    amount_cents: 150,
                    timestamp: '2024-01-15T12:15:00Z',
                    status: 'completed'
                }
            ]
        };
    }

    renderPaymentData(data) {
        // Update transaction table
        const transactionTable = document.getElementById('transactionsTable');
        if (!transactionTable) return;

        const transactions = data.recent_platform_transactions || [];
        transactionTable.innerHTML = transactions.map(tx => `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${tx.id}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${tx.transaction_type.replace('_', ' ')}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    $${(tx.amount_cents / 100).toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${new Date(tx.timestamp).toLocaleDateString()}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                        ${tx.status}
                    </span>
                </td>
            </tr>
        `).join('');
    }

    initializeCharts() {
        try {
            console.log('Initializing charts...');
            this.createQueryVolumeChart();
            this.createQueryStatusChart();
            this.createPaymentDistributionChart();
            this.createRevenueChart();
            console.log('Charts initialized successfully');
        } catch (error) {
            console.error('Error initializing charts:', error);
            // Don't throw error - charts are non-critical
        }
    }

    createQueryVolumeChart() {
        const ctx = document.getElementById('queryVolumeChart');
        if (!ctx) return;

        // Generate mock data for last 30 days
        const labels = Array.from({length: 30}, (_, i) => {
            const date = new Date();
            date.setDate(date.getDate() - (29 - i));
            return date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
        });

        const data = Array.from({length: 30}, () => 
            this.demoMode ? Math.floor(Math.random() * 10) + 1 : 0
        );

        this.charts.queryVolume = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Queries',
                    data,
                    borderColor: '#3B82F6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    createQueryStatusChart() {
        const ctx = document.getElementById('queryStatusChart');
        if (!ctx) return;

        const data = this.demoMode ? [5, 3, 2, 15, 1] : [0, 0, 0, 0, 0];

        this.charts.queryStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Pending', 'Routing', 'Collecting', 'Completed', 'Failed'],
                datasets: [{
                    data,
                    backgroundColor: [
                        '#FCD34D',
                        '#60A5FA',
                        '#A78BFA',
                        '#34D399',
                        '#F87171'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    createPaymentDistributionChart() {
        const ctx = document.getElementById('paymentDistributionChart');
        if (!ctx) return;

        const data = this.demoMode ? [70, 20, 10] : [0, 0, 0];

        this.charts.paymentDistribution = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Contributors (70%)', 'Platform (20%)', 'Referrers (10%)'],
                datasets: [{
                    data,
                    backgroundColor: ['#10B981', '#3B82F6', '#F59E0B']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    createRevenueChart() {
        const ctx = document.getElementById('revenueChart');
        if (!ctx) return;

        const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
        const data = this.demoMode ? [1200, 1900, 2100, 1800, 2400, 2100] : [0, 0, 0, 0, 0, 0];

        this.charts.revenue = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Platform Revenue ($)',
                    data,
                    backgroundColor: '#3B82F6',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value;
                            }
                        }
                    }
                }
            }
        });
    }

    async loadTabData(tab) {
        switch (tab) {
            case 'queries':
                await this.loadQueries();
                break;
            case 'experts':
                await this.loadExperts();
                break;
            case 'payments':
                await this.loadPayments();
                break;
            default:
                break;
        }
    }

    filterQueries() {
        // This would implement client-side filtering
        // For now, just reload the queries
        this.loadQueries();
    }

    toggleDemoMode() {
        this.demoMode = !this.demoMode;
        const button = document.getElementById('demoModeToggle');
        button.textContent = `Demo Mode: ${this.demoMode ? 'ON' : 'OFF'}`;
        button.className = this.demoMode ? 
            'px-3 py-1 text-sm bg-green-100 text-green-800 rounded-full' :
            'px-3 py-1 text-sm bg-yellow-100 text-yellow-800 rounded-full';
        
        // Reload data with demo mode
        this.refreshData();
    }

    async refreshData() {
        try {
            await this.loadInitialData();
            this.addActivityItem('System', 'Dashboard data refreshed', 'info');
        } catch (error) {
            console.error('Error refreshing data:', error);
            this.showError('Failed to refresh data');
        }
    }

    startAutoRefresh() {
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, 30000);
    }

    connectWebSocket() {
        // Connect to real WebSocket endpoint
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/admin/ws`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected to admin dashboard');
                this.addActivityItem('System', 'Real-time updates connected', 'success');
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
                console.log('WebSocket connection closed');
                this.addActivityItem('System', 'Real-time updates disconnected', 'warning');
                
                // Attempt to reconnect after 5 seconds
                setTimeout(() => {
                    if (!this.websocket || this.websocket.readyState === WebSocket.CLOSED) {
                        this.connectWebSocket();
                    }
                }, 5000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.addActivityItem('System', 'WebSocket connection error', 'error');
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            // Fallback to demo mode for activity simulation
            if (this.demoMode) {
                this.simulateActivity();
            }
        }
    }
    
    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'connection':
                console.log('WebSocket connection established:', message.data);
                break;
                
            case 'activity':
                const activity = message.data;
                this.addActivityItem(
                    activity.activity_type,
                    activity.message,
                    activity.level
                );
                break;
                
            case 'metrics':
                // Update dashboard metrics with new data
                this.updateSystemMetrics(message.data);
                break;
                
            case 'query_update':
                // Handle query status updates
                this.handleQueryUpdate(message.data);
                break;
                
            case 'pong':
                // Handle ping/pong for connection keep-alive
                break;
                
            default:
                console.log('Unknown WebSocket message type:', message.type);
        }
    }
    
    handleQueryUpdate(data) {
        // Update query table if visible
        const currentTab = document.querySelector('.tab-content.active')?.id;
        if (currentTab === 'queries') {
            this.loadQueries(); // Refresh query data
        }
        
        // Add activity item for query updates
        if (data.status) {
            this.addActivityItem(
                'Query',
                `Query ${data.query_id?.substring(0, 8)}... status: ${data.status}`,
                'info'
            );
        }
    }

    simulateActivity() {
        const activities = [
            { type: 'Query', message: 'New query submitted: "AI best practices"', level: 'info' },
            { type: 'Expert', message: 'Expert response received from Dr. Chen', level: 'success' },
            { type: 'Payment', message: 'Payment processed: $3.50 to contributor', level: 'success' },
            { type: 'System', message: 'Background synthesis completed', level: 'info' }
        ];

        setInterval(() => {
            if (this.demoMode) {
                const activity = activities[Math.floor(Math.random() * activities.length)];
                this.addActivityItem(activity.type, activity.message, activity.level);
            }
        }, 5000);
    }

    addActivityItem(type, message, level = 'info') {
        const feed = document.getElementById('activityFeed');
        if (!feed) return;

        const timestamp = new Date().toLocaleTimeString();
        const item = document.createElement('div');
        item.className = 'activity-item p-4 hover:bg-gray-50';
        item.innerHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0">
                    <div class="status-dot status-${level === 'success' ? 'healthy' : level === 'error' ? 'error' : 'warning'}"></div>
                </div>
                <div class="ml-3 flex-1">
                    <p class="text-sm font-medium text-gray-900">${type}</p>
                    <p class="text-sm text-gray-600">${message}</p>
                    <p class="text-xs text-gray-500 mt-1">${timestamp}</p>
                </div>
            </div>
        `;

        feed.insertBefore(item, feed.firstChild);

        // Keep only last 20 items
        while (feed.children.length > 20) {
            feed.removeChild(feed.lastChild);
        }
    }

    updateLastRefreshed() {
        this.lastUpdate = new Date();
        const element = document.getElementById('lastUpdated');
        if (element) {
            element.textContent = `Last updated: ${this.lastUpdate.toLocaleTimeString()}`;
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.style.display = show ? 'flex' : 'none';
        }
    }

    showError(message) {
        // Enhanced error notification with console logging
        console.error('Dashboard Error:', message);
        
        // Create a toast-style notification instead of alert
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded shadow-lg z-50';
        notification.innerHTML = `
            <div class="flex items-center">
                <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                </svg>
                <span>${message}</span>
                <button class="ml-4 text-red-700 hover:text-red-900" onclick="this.parentElement.parentElement.remove()">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    destroy() {
        // Clean up intervals and websockets
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        if (this.websocket) {
            this.websocket.close();
        }
        
        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing admin dashboard...');
    try {
        window.adminDashboard = new AdminDashboard();
        console.log('Admin dashboard initialized successfully');
    } catch (error) {
        console.error('Failed to initialize admin dashboard:', error);
        
        // Show error on screen
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #fee; border: 2px solid #f88; padding: 20px; border-radius: 8px; z-index: 1000; max-width: 500px;';
        errorDiv.innerHTML = `
            <h3 style="margin: 0 0 10px 0; color: #c53030;">Dashboard Initialization Error</h3>
            <p style="margin: 0 0 10px 0;">Failed to initialize admin dashboard: ${error.message}</p>
            <button onclick="this.parentElement.remove()" style="background: #c53030; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Close</button>
            <button onclick="location.reload()" style="background: #3182ce; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; margin-left: 10px;">Retry</button>
        `;
        document.body.appendChild(errorDiv);
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.adminDashboard) {
        window.adminDashboard.destroy();
    }
});