#!/usr/bin/env python3
"""
Enhanced seed data script for comprehensive GroupChat demo
Creates realistic expert profiles, queries, and complete workflows
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import random
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groupchat.db.database import AsyncSessionLocal, engine
from groupchat.db.models import (
    Contact, ExpertiseTag, ContactExpertise, Query, Contribution,
    CompiledAnswer, Citation, ContactStatus, QueryStatus, Ledger,
    LedgerEntryType, TransactionType, PayoutSplit
)

# Comprehensive Expertise Tags
EXPERTISE_TAGS = [
    # Technology
    {"name": "Python", "category": "Programming", "description": "Python programming language and ecosystem"},
    {"name": "JavaScript", "category": "Programming", "description": "JavaScript and modern web development"},
    {"name": "React", "category": "Frontend", "description": "React.js library and ecosystem"},
    {"name": "Node.js", "category": "Backend", "description": "Node.js runtime and server-side JavaScript"},
    {"name": "FastAPI", "category": "Backend", "description": "Modern Python web framework"},
    {"name": "PostgreSQL", "category": "Database", "description": "Advanced relational database"},
    {"name": "Machine Learning", "category": "AI/ML", "description": "Machine learning algorithms and applications"},
    {"name": "Data Science", "category": "Analytics", "description": "Data analysis and statistical modeling"},
    {"name": "AWS", "category": "Cloud", "description": "Amazon Web Services cloud platform"},
    {"name": "Docker", "category": "DevOps", "description": "Containerization and deployment"},
    {"name": "Kubernetes", "category": "DevOps", "description": "Container orchestration"},
    {"name": "System Design", "category": "Architecture", "description": "Large-scale system architecture"},
    {"name": "Security", "category": "Infrastructure", "description": "Cybersecurity and best practices"},
    
    # Business & Strategy
    {"name": "Product Management", "category": "Business", "description": "Product strategy and development"},
    {"name": "Marketing", "category": "Business", "description": "Digital marketing and growth"},
    {"name": "Sales", "category": "Business", "description": "Sales strategy and execution"},
    {"name": "Startup Strategy", "category": "Business", "description": "Startup operations and scaling"},
    {"name": "Fundraising", "category": "Business", "description": "Venture capital and investment"},
    {"name": "Operations", "category": "Business", "description": "Business operations and processes"},
    
    # Creative & Design
    {"name": "UX Design", "category": "Design", "description": "User experience design"},
    {"name": "UI Design", "category": "Design", "description": "User interface design"},
    {"name": "Brand Strategy", "category": "Marketing", "description": "Brand development and positioning"},
    {"name": "Content Writing", "category": "Content", "description": "Content strategy and copywriting"},
    {"name": "Social Media", "category": "Marketing", "description": "Social media marketing"},
    
    # Professional Services
    {"name": "Consulting", "category": "Professional", "description": "Management consulting"},
    {"name": "Legal", "category": "Professional", "description": "Legal advice and compliance"},
    {"name": "Finance", "category": "Professional", "description": "Financial planning and analysis"},
    {"name": "HR", "category": "Professional", "description": "Human resources and talent"},
    {"name": "Project Management", "category": "Professional", "description": "Project planning and execution"},
]

# Realistic Expert Profiles
EXPERT_PROFILES = [
    {
        "name": "Dr. Sarah Chen",
        "phone_number": "+15551001001",
        "email": "sarah.chen@stanford.edu",
        "bio": "PhD in Computer Science from Stanford University with 8+ years of experience in machine learning research at Google AI. Published 40+ papers in top-tier conferences including NeurIPS and ICML. Specialized in natural language processing, neural architecture search, and large language models. Currently leading a team of 12 researchers working on next-generation AI systems.",
        "expertise_summary": "Machine Learning, Data Science, Python, Research, AI/ML Strategy",
        "trust_score": 0.95,
        "response_rate": 0.92,
        "avg_response_time_minutes": 25.5,
        "total_contributions": 127,
        "total_earnings_cents": 3850,
        "tags": ["Machine Learning", "Data Science", "Python", "System Design"],
        "handle": "dr_sarah_chen"
    },
    {
        "name": "Mike Rodriguez",
        "phone_number": "+15551001002", 
        "email": "mike.r@netflix.com",
        "bio": "Senior DevOps Engineer at Netflix with 10+ years scaling distributed systems to billions of users. Expert in Kubernetes, AWS, and infrastructure automation. Led the migration of 200+ microservices to cloud-native architecture, reducing costs by 40% while improving reliability. Holds AWS Solutions Architect certification and speaks regularly at DevOps conferences.",
        "expertise_summary": "DevOps, Kubernetes, AWS, Infrastructure, System Design",
        "trust_score": 0.91,
        "response_rate": 0.88,
        "avg_response_time_minutes": 18.3,
        "total_contributions": 95,
        "total_earnings_cents": 2875,
        "tags": ["AWS", "Docker", "Kubernetes", "System Design", "Security"],
        "handle": "devops_mike"
    },
    {
        "name": "Emily Watson",
        "phone_number": "+15551001003",
        "email": "emily@stripe.com", 
        "bio": "Principal Product Manager at Stripe, leading payments infrastructure used by millions of businesses worldwide. 7 years of experience building fintech products from 0 to 1. Previously at Square where she launched their small business lending platform. MBA from Wharton, BS in Computer Science from MIT. Expert in product strategy, user research, and growth metrics.",
        "expertise_summary": "Product Management, Fintech, Strategy, Growth, User Research",
        "trust_score": 0.93,
        "response_rate": 0.85,
        "avg_response_time_minutes": 32.1,
        "total_contributions": 78,
        "total_earnings_cents": 2340,
        "tags": ["Product Management", "Startup Strategy", "Finance", "Operations"],
        "handle": "emily_pm"
    },
    {
        "name": "Alex Kim",
        "phone_number": "+15551001004",
        "email": "alex@alexkimdesign.com",
        "bio": "Award-winning UX Designer with 9 years creating intuitive digital experiences for companies like Airbnb, Uber, and Figma. Led design for products used by 100M+ users. Expert in design systems, user research, and conversion optimization. Recognized in Forbes 30 Under 30 for Design. Mentors designers at IDEO and teaches at General Assembly.",
        "expertise_summary": "UX Design, UI Design, Design Systems, User Research, Product Design",
        "trust_score": 0.89,
        "response_rate": 0.91,
        "avg_response_time_minutes": 22.7,
        "total_contributions": 112,
        "total_earnings_cents": 3360,
        "tags": ["UX Design", "UI Design", "Brand Strategy", "Product Management"],
        "handle": "alex_ux"
    },
    {
        "name": "David Park",
        "phone_number": "+15551001005",
        "email": "david@techcrunch.com",
        "bio": "Senior Reporter at TechCrunch covering enterprise software and emerging technologies. Former startup founder (acquired by Microsoft in 2019). 12+ years in tech journalism with exclusive coverage of major acquisitions and funding rounds. Deep network in Silicon Valley VC community. Regular contributor to CNBC and Bloomberg on tech trends.",
        "expertise_summary": "Tech Journalism, Startup Strategy, Fundraising, Market Analysis",
        "trust_score": 0.87,
        "response_rate": 0.79,
        "avg_response_time_minutes": 45.2,
        "total_contributions": 63,
        "total_earnings_cents": 1890,
        "tags": ["Content Writing", "Startup Strategy", "Marketing", "Fundraising"],
        "handle": "david_tech"
    },
    {
        "name": "Lisa Thompson",
        "phone_number": "+15551001006",
        "email": "lisa@cybersec.consulting",
        "bio": "CISSP-certified cybersecurity consultant with 15+ years protecting Fortune 500 companies from advanced threats. Former NSA analyst and CISO at three unicorn startups. Expert in zero-trust architecture, incident response, and compliance frameworks (SOC2, ISO 27001). Regularly testifies before Congress on cybersecurity legislation.",
        "expertise_summary": "Cybersecurity, Compliance, Risk Management, Security Architecture", 
        "trust_score": 0.96,
        "response_rate": 0.84,
        "avg_response_time_minutes": 28.9,
        "total_contributions": 89,
        "total_earnings_cents": 2670,
        "tags": ["Security", "System Design", "Consulting", "Legal"],
        "handle": "lisa_sec"
    },
    {
        "name": "Carlos Silva",
        "phone_number": "+15551001007",
        "email": "carlos@shopify.com",
        "bio": "Director of Growth at Shopify, scaling merchant acquisition from 100K to 2M+ stores. 8 years of growth hacking experience across B2B and B2C. Built growth teams at Slack and Zoom during their hypergrowth phases. Expert in viral mechanics, retention optimization, and performance marketing. Frequent speaker at GrowthHackers and SaaStr conferences.",
        "expertise_summary": "Growth Marketing, B2B Sales, Performance Marketing, Analytics",
        "trust_score": 0.90,
        "response_rate": 0.86,
        "avg_response_time_minutes": 35.4,
        "total_contributions": 104,
        "total_earnings_cents": 3120,
        "tags": ["Marketing", "Sales", "Operations", "Data Science"],
        "handle": "carlos_growth"
    },
    {
        "name": "Rachel Green",
        "phone_number": "+15551001008",
        "email": "rachel@a16z.com",
        "bio": "Partner at Andreessen Horowitz focusing on enterprise software and developer tools. Led investments in 15+ startups with 3 unicorn exits. Former VP of Product at GitHub where she launched GitHub Actions and Copilot. MS in Computer Science from Carnegie Mellon. Board member at 8 portfolio companies.",
        "expertise_summary": "Venture Capital, Enterprise Software, Developer Tools, Board Advisory",
        "trust_score": 0.94,
        "response_rate": 0.71,
        "avg_response_time_minutes": 67.8,
        "total_contributions": 42,
        "total_earnings_cents": 1260,
        "tags": ["Fundraising", "Startup Strategy", "Product Management", "Consulting"],
        "handle": "rachel_vc"
    },
    {
        "name": "James Wilson",
        "phone_number": "+15551001009",
        "email": "james@fullstack.dev",
        "bio": "Full-stack architect with 12+ years building scalable web applications. Created the architecture for 3 startups that scaled to 10M+ users. Expert in React, Node.js, PostgreSQL, and AWS. Open source contributor with 50K+ GitHub stars across projects. Technical advisor to YCombinator startups and mentor at Lambda School.",
        "expertise_summary": "Full-Stack Development, System Architecture, Open Source, Mentoring",
        "trust_score": 0.88,
        "response_rate": 0.93,
        "avg_response_time_minutes": 15.2,
        "total_contributions": 156,
        "total_earnings_cents": 4680,
        "tags": ["JavaScript", "React", "Node.js", "PostgreSQL", "AWS", "System Design"],
        "handle": "james_fullstack"
    },
    {
        "name": "Maya Patel",
        "phone_number": "+15551001010",
        "email": "maya@consulting.mckinsey.com",
        "bio": "Senior Partner at McKinsey & Company with 14 years advising Fortune 100 CEOs on digital transformation and operational excellence. Led 50+ engagements across technology, healthcare, and financial services. Expert in change management, process optimization, and organizational design. MBA from Harvard Business School, named to Fortune's 40 Under 40.",
        "expertise_summary": "Management Consulting, Digital Transformation, Strategy, Operations",
        "trust_score": 0.97,
        "response_rate": 0.76,
        "avg_response_time_minutes": 52.3,
        "total_contributions": 67,
        "total_earnings_cents": 2010,
        "tags": ["Consulting", "Operations", "Project Management", "Startup Strategy"],
        "handle": "maya_mckinsey"
    },
    {
        "name": "Tom Chang",
        "phone_number": "+15551001011",
        "email": "tom@datarobot.com",
        "bio": "VP of Data Science at DataRobot, building automated machine learning platforms used by Fortune 500 companies. PhD in Statistics from UC Berkeley. 10+ years applying ML to real-world problems in healthcare, finance, and retail. Published researcher in automated feature engineering and model interpretability. Kaggle Grandmaster with 5 competition wins.",
        "expertise_summary": "Data Science, Machine Learning, Statistics, AutoML, Analytics",
        "trust_score": 0.92,
        "response_rate": 0.87,
        "avg_response_time_minutes": 29.6,
        "total_contributions": 98,
        "total_earnings_cents": 2940,
        "tags": ["Data Science", "Machine Learning", "Python", "Statistics"],
        "handle": "tom_datascience"
    },
    {
        "name": "Sophie Martin",
        "phone_number": "+15551001012",
        "email": "sophie@creativeco.agency",
        "bio": "Creative Director at award-winning digital agency, leading brand campaigns for Nike, Apple, and Tesla. 11 years in creative strategy with 20+ industry awards including Cannes Lions and D&AD pencils. Expert in brand positioning, campaign development, and multi-channel storytelling. Adjunct professor at Art Center College of Design.",
        "expertise_summary": "Creative Direction, Brand Strategy, Campaign Development, Visual Design",
        "trust_score": 0.86,
        "response_rate": 0.82,
        "avg_response_time_minutes": 41.7,
        "total_contributions": 73,
        "total_earnings_cents": 2190,
        "tags": ["Brand Strategy", "Marketing", "UX Design", "Content Writing"],
        "handle": "sophie_creative"
    },
    {
        "name": "Kevin O'Brien",
        "phone_number": "+15551001013",
        "email": "kevin@saleforce.com",
        "bio": "Enterprise Sales Leader at Salesforce with $50M+ in annual revenue responsibility. 13 years in B2B sales across SaaS, cloud infrastructure, and enterprise software. Built and led sales teams of 50+ reps. Expert in complex deal structures, enterprise procurement, and customer success. Former sales trainer at Sales Development Institute.",
        "expertise_summary": "Enterprise Sales, B2B Strategy, Team Leadership, Customer Success",
        "trust_score": 0.89,
        "response_rate": 0.89,
        "avg_response_time_minutes": 24.8,
        "total_contributions": 115,
        "total_earnings_cents": 3450,
        "tags": ["Sales", "Operations", "Project Management", "Consulting"],
        "handle": "kevin_sales"
    },
    {
        "name": "Anna Rodriguez",
        "phone_number": "+15551001014",
        "email": "anna@legaltech.law",
        "bio": "Technology Attorney specializing in AI/ML regulations, data privacy, and startup law. JD from Stanford Law School, former associate at Wilson Sonsini. 9 years helping tech companies navigate complex regulatory landscapes. Expert in GDPR, CCPA, and emerging AI governance frameworks. Regular contributor to TechCrunch on legal tech topics.",
        "expertise_summary": "Technology Law, AI Regulations, Data Privacy, Startup Legal",
        "trust_score": 0.95,
        "response_rate": 0.73,
        "avg_response_time_minutes": 58.9,
        "total_contributions": 51,
        "total_earnings_cents": 1530,
        "tags": ["Legal", "Security", "Consulting", "Startup Strategy"],
        "handle": "anna_techlaw"
    },
    {
        "name": "Marcus Johnson",
        "phone_number": "+15551001015",
        "email": "marcus@hr.innovate.com",
        "bio": "Chief People Officer at high-growth startups, scaling teams from 10 to 1000+ employees. 12 years in talent acquisition, performance management, and organizational culture. Led HR through 3 successful IPOs. Expert in remote work policies, diversity & inclusion, and executive coaching. Certified executive coach and frequent speaker at HR conferences.",
        "expertise_summary": "Human Resources, Talent Strategy, Organizational Culture, Leadership",
        "trust_score": 0.91,
        "response_rate": 0.81,
        "avg_response_time_minutes": 38.2,
        "total_contributions": 84,
        "total_earnings_cents": 2520,
        "tags": ["HR", "Operations", "Consulting", "Project Management"],
        "handle": "marcus_hr"
    },
    {
        "name": "Dr. Jennifer Liu",
        "phone_number": "+15551001016",
        "email": "jennifer@research.mit.edu",
        "bio": "Professor of Computer Science at MIT focusing on distributed systems and blockchain technology. PhD from CMU, 15+ years in academia and industry. Co-founded 2 blockchain startups (one acquired by Coinbase). Published 60+ papers on consensus algorithms and cryptographic protocols. Technical advisor to multiple crypto projects and DeFi protocols.",
        "expertise_summary": "Blockchain, Distributed Systems, Cryptography, Academic Research",
        "trust_score": 0.98,
        "response_rate": 0.69,
        "avg_response_time_minutes": 72.4,
        "total_contributions": 38,
        "total_earnings_cents": 1140,
        "tags": ["System Design", "Security", "Python", "Machine Learning"],
        "handle": "dr_jen_blockchain"
    },
    {
        "name": "Ryan Cooper",
        "phone_number": "+15551001017",
        "email": "ryan@socialmedia.guru",
        "bio": "Social Media Strategist managing 50M+ follower accounts for Fortune 500 brands. 8 years creating viral campaigns and community growth strategies. Former Head of Social at BuzzFeed and Spotify. Expert in TikTok, Instagram, YouTube, and emerging platforms. Built organic audiences of 10M+ followers across multiple brands.",
        "expertise_summary": "Social Media Marketing, Content Strategy, Community Building, Viral Growth",
        "trust_score": 0.84,
        "response_rate": 0.94,
        "avg_response_time_minutes": 12.8,
        "total_contributions": 142,
        "total_earnings_cents": 4260,
        "tags": ["Social Media", "Marketing", "Content Writing", "Brand Strategy"],
        "handle": "ryan_social"
    },
    {
        "name": "Dr. Priya Sharma", 
        "phone_number": "+15551001018",
        "email": "priya@fintech.goldman.com",
        "bio": "Managing Director at Goldman Sachs leading quantitative research for algorithmic trading. PhD in Financial Engineering from Stanford. 11 years developing systematic trading strategies managing $2B+ in assets. Expert in quantitative modeling, risk management, and financial derivatives. Published researcher in market microstructure and high-frequency trading.",
        "expertise_summary": "Quantitative Finance, Algorithmic Trading, Risk Management, Financial Modeling",
        "trust_score": 0.96,
        "response_rate": 0.67,
        "avg_response_time_minutes": 89.3,
        "total_contributions": 29,
        "total_earnings_cents": 870,
        "tags": ["Finance", "Data Science", "Python", "Consulting"],
        "handle": "dr_priya_quant"
    },
    {
        "name": "Chris Anderson",
        "phone_number": "+15551001019", 
        "email": "chris@pmconsulting.co",
        "bio": "Senior Project Manager with PMP certification and 10+ years delivering complex technology projects. Managed $100M+ in software development initiatives across healthcare, fintech, and e-commerce. Expert in Agile methodologies, stakeholder management, and risk mitigation. Led digital transformation projects for Fortune 500 companies with 99% on-time delivery rate.",
        "expertise_summary": "Project Management, Agile Methodologies, Digital Transformation, Team Leadership",
        "trust_score": 0.93,
        "response_rate": 0.91,
        "avg_response_time_minutes": 21.5,
        "total_contributions": 108,
        "total_earnings_cents": 3240,
        "tags": ["Project Management", "Operations", "Consulting", "Startup Strategy"],
        "handle": "chris_pm"
    },
    {
        "name": "Zoe Williams",
        "phone_number": "+15551001020",
        "email": "zoe@contentcreator.co",
        "bio": "Content strategist and copywriter with 7 years creating high-converting content for SaaS companies. Grew organic traffic from 0 to 1M monthly visitors for 5 different startups. Expert in SEO, email marketing, and conversion copywriting. Former content lead at HubSpot and Mailchimp. Built content teams and processes that scaled to 100+ pieces per month.",
        "expertise_summary": "Content Marketing, SEO, Copywriting, Email Marketing, Growth",
        "trust_score": 0.88,
        "response_rate": 0.96,
        "avg_response_time_minutes": 16.7,
        "total_contributions": 134,
        "total_earnings_cents": 4020,
        "tags": ["Content Writing", "Marketing", "Social Media", "Sales"],
        "handle": "zoe_content"
    }
]

# Complex Query Scenarios with Multiple Expert Perspectives
SAMPLE_QUERY_SCENARIOS = [
    {
        "user_phone": "+15559876543",
        "question_text": "I'm a startup founder building an AI-powered fintech app. How should I approach regulatory compliance for AI/ML models in financial services, and what's the best technical architecture for handling sensitive financial data at scale?",
        "status": QueryStatus.COMPLETED,
        "max_spend_cents": 800,
        "expert_responses": [
            {
                "expert": "anna_techlaw",
                "response": "For AI/ML in fintech, you'll need to navigate several regulatory frameworks: 1) Model Risk Management (SR 11-7) requires comprehensive model validation and ongoing monitoring. 2) Fair Credit Reporting Act (FCRA) if using AI for credit decisions. 3) Equal Credit Opportunity Act (ECOA) requires bias testing and adverse action notices. 4) Emerging AI regulations like the EU AI Act will impact global operations. I recommend implementing explainable AI from day one, maintaining detailed model documentation, and establishing a Model Risk Management framework. Consider partnering with RegTech providers for automated compliance monitoring. Budget 20-30% of development time for compliance features.",
                "confidence_score": 0.95,
                "was_used": True,
                "payout_cents": 150
            },
            {
                "expert": "dr_priya_quant",
                "response": "From a technical architecture perspective for financial AI: 1) Use microservices architecture with dedicated model serving infrastructure (MLflow, Kubeflow). 2) Implement real-time feature stores for consistent model inputs. 3) Zero-trust security with end-to-end encryption and HSMs for key management. 4) Event-driven architecture for audit trails and regulatory reporting. 5) A/B testing infrastructure for model performance monitoring. For data handling: use database-level encryption, implement data lineage tracking, and consider federated learning for privacy. AWS Financial Services or Google Cloud for Financial Services provide compliant infrastructure. Plan for 99.99% uptime requirements and sub-100ms latency for real-time decisions.",
                "confidence_score": 0.92,
                "was_used": True,
                "payout_cents": 140
            },
            {
                "expert": "lisa_sec",
                "response": "Security architecture is critical for fintech AI. Implement: 1) Zero-trust network with micro-segmentation. 2) Runtime application self-protection (RASP) for AI models. 3) Confidential computing for sensitive ML workloads. 4) Comprehensive logging and SIEM integration. 5) Regular penetration testing and red team exercises. For data protection: use homomorphic encryption for privacy-preserving ML, implement differential privacy, and consider secure multi-party computation for sensitive operations. Ensure SOC 2 Type II compliance from day one. Budget $200K+ annually for security tooling and compliance audits.",
                "confidence_score": 0.88,
                "was_used": True,
                "payout_cents": 120
            }
        ],
        "compiled_answer": "Building an AI-powered fintech app requires careful attention to both regulatory compliance and technical architecture:\n\n## Regulatory Compliance Strategy\n\n**Key Frameworks to Address:**\n- **Model Risk Management (SR 11-7)**: Implement comprehensive model validation and ongoing monitoring [@anna_techlaw]\n- **Fair Credit Reporting Act & Equal Credit Opportunity Act**: Ensure bias testing and adverse action notices for credit decisions [@anna_techlaw] \n- **Emerging AI Regulations**: Prepare for EU AI Act and similar frameworks impacting global operations [@anna_techlaw]\n\n**Implementation Approach:**\n- Build explainable AI capabilities from day one [@anna_techlaw]\n- Maintain detailed model documentation and establish Model Risk Management framework [@anna_techlaw]\n- Budget 20-30% of development time for compliance features [@anna_techlaw]\n- Consider RegTech partnerships for automated compliance monitoring [@anna_techlaw]\n\n## Technical Architecture Recommendations\n\n**Core Infrastructure:**\n- **Microservices Architecture**: Use dedicated model serving infrastructure with MLflow or Kubeflow [@dr_priya_quant]\n- **Real-time Feature Stores**: Ensure consistent model inputs and data lineage [@dr_priya_quant]\n- **Event-driven Architecture**: Enable comprehensive audit trails and regulatory reporting [@dr_priya_quant]\n- **A/B Testing Infrastructure**: Monitor model performance and implement gradual rollouts [@dr_priya_quant]\n\n**Security & Data Protection:**\n- **Zero-trust Network**: Implement micro-segmentation and end-to-end encryption [@lisa_sec] [@dr_priya_quant]\n- **Advanced Security Measures**: Deploy Runtime Application Self-Protection (RASP) for AI models [@lisa_sec]\n- **Privacy-Preserving Technologies**: Use homomorphic encryption and differential privacy for sensitive ML workloads [@lisa_sec]\n- **Compliance Infrastructure**: Ensure SOC 2 Type II compliance with comprehensive logging and SIEM integration [@lisa_sec]\n\n**Performance & Reliability:**\n- Plan for 99.99% uptime and sub-100ms latency for real-time decisions [@dr_priya_quant]\n- Use cloud financial services platforms (AWS Financial Services or Google Cloud) for compliant infrastructure [@dr_priya_quant]\n- Budget $200K+ annually for security tooling and compliance audits [@lisa_sec]\n\nThis approach balances regulatory requirements with scalable technical architecture, ensuring your fintech AI platform can grow while maintaining compliance and security.",
        "confidence_score": 0.91
    },
    {
        "user_phone": "+15559876544", 
        "question_text": "Our B2B SaaS product has great product-market fit but growth has plateaued at $2M ARR. What are the most effective strategies to break through to $10M ARR, and how should we structure our go-to-market team?",
        "status": QueryStatus.COMPLETED,
        "max_spend_cents": 600,
        "expert_responses": [
            {
                "expert": "carlos_growth",
                "response": "Moving from $2M to $10M ARR requires systematic growth strategy: 1) Customer segmentation analysis - identify highest LTV segments and double-down. 2) Expand within existing accounts (upsell/cross-sell) - should be 30-40% of growth. 3) Implement product-led growth motions - freemium or free trial to reduce CAC. 4) Content marketing engine - aim for 10x organic traffic growth. 5) Partner channel development - can contribute 20-30% of revenue. 6) International expansion if product is ready. Focus on improving retention first (95%+ net revenue retention), then scale acquisition. Benchmark: $2M to $10M typically takes 18-24 months with proper execution.",
                "confidence_score": 0.93,
                "was_used": True,
                "payout_cents": 140
            },
            {
                "expert": "kevin_sales",
                "response": "At $2M ARR, you need enterprise sales motion to reach $10M. Team structure: 1) VP of Sales (if not already hired) 2) 3-4 Account Executives focused on new business 3) 2-3 Customer Success Managers for expansion 4) 2 SDRs for qualified lead generation 5) Sales Operations person for process/tooling. Key metrics: $200K+ quota per AE, 3-4x pipeline coverage, 15-20% close rate. Implement account-based marketing for enterprise prospects. Average deal size should increase from $10K to $25K+ annually. Sales cycle will extend to 3-4 months but higher ACV justifies it. Invest in sales enablement and training - proper sales methodology (MEDDIC or Challenger) is crucial at this stage.",
                "confidence_score": 0.89,
                "was_used": True,
                "payout_cents": 125
            },
            {
                "expert": "emily_pm",
                "response": "Product strategy is crucial for this growth phase: 1) Analyze usage data to identify expansion opportunities within product. 2) Build enterprise features (SSO, admin controls, API integrations) to move upmarket. 3) Create multiple pricing tiers - many companies leave money on table with single pricing. 4) Implement usage-based pricing components where possible. 5) Focus on 'aha moments' that drive activation and reduce churn. 6) Build integrations with tools your customers already use. From product-market fit perspective, ensure you have clear ICP definition and can articulate value prop in 30 seconds. Consider adding enterprise sales team but maintain product-led growth for smaller segments. NRR above 110% is essential for sustainable growth to $10M.",
                "confidence_score": 0.87,
                "was_used": True,
                "payout_cents": 115
            }
        ],
        "compiled_answer": "Breaking through from $2M to $10M ARR requires a multi-faceted approach combining growth strategy, team scaling, and product evolution:\n\n## Growth Strategy Framework\n\n**Customer Expansion (30-40% of growth):** [@carlos_growth]\n- Conduct deep customer segmentation analysis to identify highest LTV segments [@carlos_growth]\n- Focus on expanding within existing accounts through upsell/cross-sell [@carlos_growth]\n- Target 95%+ net revenue retention - essential foundation for sustainable growth [@carlos_growth]\n\n**Product-Led Growth Optimization:**\n- Implement freemium or free trial motions to reduce customer acquisition cost [@carlos_growth]\n- Build enterprise features (SSO, admin controls, API integrations) to move upmarket [@emily_pm]\n- Create multiple pricing tiers and consider usage-based pricing components [@emily_pm]\n- Focus on improving 'aha moments' that drive activation and reduce churn [@emily_pm]\n\n**Market Expansion:**\n- Build content marketing engine targeting 10x organic traffic growth [@carlos_growth]\n- Develop partner channel strategy (20-30% revenue contribution potential) [@carlos_growth]\n- Consider international expansion if product is ready [@carlos_growth]\n\n## Go-to-Market Team Structure\n\n**Enterprise Sales Motion:** [@kevin_sales]\n- **VP of Sales** (if not already hired)\n- **3-4 Account Executives** for new business ($200K+ annual quota each)\n- **2-3 Customer Success Managers** focused on expansion\n- **2 SDRs** for qualified lead generation\n- **Sales Operations** person for process optimization and tooling\n\n**Key Performance Metrics:**\n- 3-4x pipeline coverage with 15-20% close rate [@kevin_sales]\n- Average deal size increase from $10K to $25K+ annually [@kevin_sales]\n- Sales cycle extension to 3-4 months (justified by higher ACV) [@kevin_sales]\n\n## Product & Pricing Strategy\n\n**Enterprise Readiness:**\n- Build integrations with tools customers already use [@emily_pm]\n- Ensure clear ICP definition and 30-second value proposition [@emily_pm]\n- Implement account-based marketing for enterprise prospects [@kevin_sales]\n\n**Revenue Optimization:**\n- Target net revenue retention above 110% [@emily_pm]\n- Analyze usage data to identify expansion opportunities [@emily_pm]\n- Maintain product-led growth for smaller segments while building enterprise sales [@emily_pm]\n\n**Implementation Timeline:**\nTypically takes 18-24 months to scale from $2M to $10M ARR with proper execution [@carlos_growth]. Focus on improving retention first, then scale acquisition systematically.\n\n**Critical Success Factor:** Invest heavily in sales enablement and training - implement proven sales methodologies like MEDDIC or Challenger [@kevin_sales].",
        "confidence_score": 0.89
    },
    {
        "user_phone": "+15559876545",
        "question_text": "We're redesigning our mobile app's onboarding flow. Current completion rate is only 45%. What are the latest UX best practices for mobile onboarding, and how can we A/B test improvements effectively?",
        "status": QueryStatus.COMPLETED,
        "max_spend_cents": 500,
        "expert_responses": [
            {
                "expert": "alex_ux", 
                "response": "45% completion rate indicates major friction points. Modern onboarding best practices: 1) Progressive disclosure - show value before asking for information. 2) Minimize form fields - only ask what's absolutely necessary upfront. 3) Social proof and testimonials early in flow. 4) Interactive tutorials vs passive walkthroughs. 5) Clear progress indicators. 6) Allow 'skip' options for non-critical steps. 7) Contextual help and tooltips. 8) Single-purpose screens to reduce cognitive load. Key principle: demonstrate value within 30 seconds. Use tools like Hotjar for heatmaps and session recordings to identify drop-off points. A/B testing should focus on one element at a time - copy, visuals, or flow structure.",
                "confidence_score": 0.91,
                "was_used": True,
                "payout_cents": 135
            },
            {
                "expert": "tom_datascience",
                "response": "For effective A/B testing of onboarding: 1) Statistical significance - need minimum 1000 users per variant for reliable results. 2) Test duration should account for weekly patterns (run full weeks). 3) Segment users by acquisition channel - different sources have different behaviors. 4) Track micro-conversions, not just completion rate (step-by-step funnel analysis). 5) Use sequential testing to avoid peeking problem. 6) Consider holdout groups to measure long-term impact. 7) Mobile-specific considerations: test on different screen sizes and OS versions. Tools: Use Amplitude or Mixpanel for detailed funnel analysis, Optimizely for testing infrastructure. Statistical significance threshold should be 95% confidence with 5% minimum effect size.",
                "confidence_score": 0.88,
                "was_used": True,
                "payout_cents": 125
            },
            {
                "expert": "james_fullstack",
                "response": "Technical implementation for onboarding optimization: 1) Implement event tracking for every micro-interaction (button clicks, form focuses, time spent per screen). 2) Use feature flags for gradual rollouts and instant rollbacks. 3) Lazy load non-critical content to improve performance. 4) Implement error handling and offline support - network issues kill onboarding. 5) Progressive web app features for better mobile experience. 6) Use analytics SDKs that support real-time data (Segment, Firebase). 7) Consider personalization based on user attributes or referral source. Performance is crucial - each 100ms delay reduces conversion by 1%. Implement proper loading states and skeleton screens. Use React Native or Flutter for consistent cross-platform experience if supporting both iOS and Android.",
                "confidence_score": 0.85,
                "was_used": True,
                "payout_cents": 115
            }
        ],
        "compiled_answer": "Improving your mobile onboarding from 45% completion requires both UX optimization and rigorous testing methodology:\n\n## Modern Mobile Onboarding Best Practices\n\n**Core UX Principles:**\n- **Value-First Approach**: Demonstrate value within 30 seconds before asking for user information [@alex_ux]\n- **Progressive Disclosure**: Show value before collecting data, minimize upfront form fields [@alex_ux]\n- **Cognitive Load Reduction**: Use single-purpose screens and clear progress indicators [@alex_ux]\n- **Social Proof Integration**: Include testimonials and social proof early in the flow [@alex_ux]\n\n**Interactive Design Elements:**\n- **Interactive Tutorials**: Replace passive walkthroughs with hands-on experiences [@alex_ux]\n- **Flexible Navigation**: Allow 'skip' options for non-critical steps [@alex_ux]\n- **Contextual Help**: Provide tooltips and contextual assistance [@alex_ux]\n- **Loading States**: Implement skeleton screens and proper loading indicators to maintain engagement [@james_fullstack]\n\n## A/B Testing Strategy\n\n**Testing Framework:**\n- **Sample Size**: Minimum 1000 users per variant for statistical reliability [@tom_datascience]\n- **Test Duration**: Run complete weekly cycles to account for behavioral patterns [@tom_datascience]\n- **Statistical Rigor**: Use 95% confidence threshold with 5% minimum effect size [@tom_datascience]\n\n**Advanced Testing Approaches:**\n- **Segmented Analysis**: Test by acquisition channel - different sources show different behaviors [@tom_datascience]\n- **Micro-Conversion Tracking**: Monitor step-by-step funnel metrics beyond completion rate [@tom_datascience]\n- **Sequential Testing**: Avoid peeking problems and implement holdout groups for long-term impact [@tom_datascience]\n- **Cross-Platform Testing**: Account for different screen sizes and OS versions [@tom_datascience]\n\n## Technical Implementation\n\n**Analytics Infrastructure:**\n- **Comprehensive Event Tracking**: Monitor every micro-interaction including button clicks, form focuses, and time per screen [@james_fullstack]\n- **Real-time Analytics**: Use tools like Amplitude, Mixpanel for funnel analysis and Segment/Firebase for real-time data [@tom_datascience] [@james_fullstack]\n- **Session Analysis**: Implement Hotjar for heatmaps and session recordings to identify friction points [@alex_ux]\n\n**Performance Optimization:**\n- **Speed Matters**: Each 100ms delay reduces conversion by 1% [@james_fullstack]\n- **Technical Excellence**: Implement lazy loading, error handling, offline support, and progressive web app features [@james_fullstack]\n- **Feature Flags**: Use for gradual rollouts and instant rollbacks [@james_fullstack]\n\n**Personalization:**\n- Consider dynamic onboarding based on user attributes or referral source [@james_fullstack]\n- Use consistent cross-platform experience with React Native or Flutter [@james_fullstack]\n\n## Recommended Testing Tools\n- **A/B Testing**: Optimizely for testing infrastructure [@tom_datascience]\n- **Analytics**: Amplitude or Mixpanel for detailed funnel analysis [@tom_datascience]\n- **User Behavior**: Hotjar for qualitative insights [@alex_ux]\n- **Development**: Feature flag systems for gradual rollouts [@james_fullstack]\n\nFocus on testing one element at a time (copy, visuals, or flow structure) and ensure statistical significance before making decisions [@alex_ux].",
        "confidence_score": 0.88
    }
]


async def create_enhanced_seed_data():
    """Create comprehensive demo data with realistic expert profiles and scenarios"""
    async with AsyncSessionLocal() as session:
        try:
            print("🌱 Starting enhanced database seeding...")
            
            # Clear existing data
            print("Clearing existing demo data...")
            # await session.execute(text("TRUNCATE TABLE citations, compiled_answers, contributions, queries, contact_expertise, contacts, expertise_tags CASCADE"))
            
            # Create or get existing expertise tags
            print("Creating comprehensive expertise tags...")
            from sqlalchemy import select
            tags_map = {}
            for tag_data in EXPERTISE_TAGS:
                # Check if tag already exists
                result = await session.execute(select(ExpertiseTag).where(ExpertiseTag.name == tag_data["name"]))
                existing_tag = result.scalar_one_or_none()
                
                if existing_tag:
                    tags_map[tag_data["name"]] = existing_tag
                else:
                    tag = ExpertiseTag(
                        id=uuid.uuid4(),
                        name=tag_data["name"],
                        category=tag_data["category"],
                        description=tag_data.get("description", "")
                    )
                    session.add(tag)
                    tags_map[tag_data["name"]] = tag
            
            await session.flush()
            
            # Create realistic expert profiles
            print("Creating expert profiles with realistic backgrounds...")
            contacts_map = {}
            for profile in EXPERT_PROFILES:
                # Check if contact already exists by phone number
                result = await session.execute(select(Contact).where(Contact.phone_number == profile["phone_number"]))
                existing_contact = result.scalar_one_or_none()
                
                if existing_contact:
                    contacts_map[profile["handle"]] = existing_contact
                else:
                    contact = Contact(
                        id=uuid.uuid4(),
                        name=profile["name"],
                        phone_number=profile["phone_number"],
                        email=profile["email"],
                        bio=profile["bio"],
                        expertise_summary=profile["expertise_summary"],
                        trust_score=profile["trust_score"],
                        response_rate=profile["response_rate"],
                        avg_response_time_minutes=profile["avg_response_time_minutes"],
                        total_contributions=profile["total_contributions"],
                        total_earnings_cents=profile["total_earnings_cents"],
                        status=ContactStatus.ACTIVE,
                        is_available=True,
                        max_queries_per_day=random.randint(5, 15),
                        extra_metadata={"handle": profile["handle"], "specialization": profile["expertise_summary"]}
                    )
                    session.add(contact)
                    contacts_map[profile["handle"]] = contact
                
                # Add expertise tags (only for new contacts)
                if not existing_contact:
                    for tag_name in profile["tags"]:
                        if tag_name in tags_map:
                            contact_expertise = ContactExpertise(
                                contact_id=contact.id,
                                tag_id=tags_map[tag_name].id,
                                confidence_score=random.uniform(0.8, 1.0)
                            )
                            session.add(contact_expertise)
            
            await session.flush()
            
            # Create complex query scenarios
            print("Creating realistic query scenarios with expert responses...")
            for i, scenario in enumerate(SAMPLE_QUERY_SCENARIOS):
                query = Query(
                    id=uuid.uuid4(),
                    user_phone=scenario["user_phone"],
                    question_text=scenario["question_text"],
                    status=scenario["status"],
                    max_experts=len(scenario["expert_responses"]),
                    min_experts=2,
                    timeout_minutes=45,
                    total_cost_cents=scenario["max_spend_cents"],
                    platform_fee_cents=int(scenario["max_spend_cents"] * 0.2),
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
                )
                session.add(query)
                await session.flush()
                
                # Create expert contributions
                contribution_ids = []
                total_payout = 0
                for response in scenario["expert_responses"]:
                    expert = contacts_map.get(response["expert"])
                    if expert:
                        contribution = Contribution(
                            id=uuid.uuid4(),
                            query_id=query.id,
                            contact_id=expert.id,
                            response_text=response["response"],
                            confidence_score=response["confidence_score"],
                            was_used=response["was_used"],
                            requested_at=query.created_at + timedelta(minutes=5),
                            responded_at=query.created_at + timedelta(minutes=random.randint(15, 120)),
                            response_time_minutes=random.randint(15, 120),
                            payout_amount_cents=response["payout_cents"],
                            extra_metadata={"handle": response["expert"], "expertise": expert.expertise_summary}
                        )
                        session.add(contribution)
                        contribution_ids.append(contribution.id)
                        total_payout += response["payout_cents"]
                
                await session.flush()
                
                # Create compiled answer with proper citations
                if scenario.get("compiled_answer"):
                    compiled_answer = CompiledAnswer(
                        id=uuid.uuid4(),
                        query_id=query.id,
                        final_answer=scenario["compiled_answer"],
                        summary=f"AI-synthesized answer combining insights from {len(scenario['expert_responses'])} experts",
                        confidence_score=scenario["confidence_score"],
                        compilation_method="gpt-4-turbo",
                        compilation_tokens_used=random.randint(800, 1500),
                        quality_score=random.uniform(0.85, 0.98),
                        extra_metadata={
                            "expert_handles": [r["expert"] for r in scenario["expert_responses"]],
                            "synthesis_approach": "multi-expert_consensus"
                        }
                    )
                    session.add(compiled_answer)
                    await session.flush()
                    
                    # Create realistic citations
                    citation_count = 0
                    for j, contrib_id in enumerate(contribution_ids):
                        # Create 2-4 citations per contribution
                        num_citations = random.randint(2, 4)
                        for k in range(num_citations):
                            citation = Citation(
                                id=uuid.uuid4(),
                                compiled_answer_id=compiled_answer.id,
                                contribution_id=contrib_id,
                                claim_text=f"Expert insight {j+1}.{k+1}",
                                source_excerpt=scenario["expert_responses"][j]["response"][:200] + "...",
                                position_in_answer=citation_count,
                                confidence=random.uniform(0.85, 0.98)
                            )
                            session.add(citation)
                            citation_count += 1
                
                # Create ledger entries for financial tracking
                transaction_id = uuid.uuid4()
                
                # User payment (debit to user, credit to platform)
                user_payment_entry = Ledger(
                    id=uuid.uuid4(),
                    transaction_id=transaction_id,
                    transaction_type=TransactionType.QUERY_PAYMENT,
                    account_type="user",
                    account_id=scenario["user_phone"],
                    entry_type=LedgerEntryType.DEBIT,
                    amount_cents=scenario["max_spend_cents"],
                    query_id=query.id,
                    description=f"Payment for query: {scenario['question_text'][:100]}..."
                )
                session.add(user_payment_entry)
                
                # Platform fee
                platform_fee = int(scenario["max_spend_cents"] * 0.2)
                platform_entry = Ledger(
                    id=uuid.uuid4(),
                    transaction_id=transaction_id,
                    transaction_type=TransactionType.PLATFORM_FEE,
                    account_type="platform",
                    account_id="platform_revenue",
                    entry_type=LedgerEntryType.CREDIT,
                    amount_cents=platform_fee,
                    query_id=query.id,
                    description=f"Platform fee (20%) for query {query.id}"
                )
                session.add(platform_entry)
                
                # Expert payouts
                for response in scenario["expert_responses"]:
                    expert = contacts_map.get(response["expert"])
                    if expert:
                        payout_entry = Ledger(
                            id=uuid.uuid4(),
                            transaction_id=transaction_id,
                            transaction_type=TransactionType.CONTRIBUTION_PAYOUT,
                            account_type="expert",
                            account_id=str(expert.id),
                            entry_type=LedgerEntryType.CREDIT,
                            amount_cents=response["payout_cents"],
                            query_id=query.id,
                            contact_id=expert.id,
                            description=f"Payout to {expert.name} for query contribution"
                        )
                        session.add(payout_entry)
                
                # Create payout split record
                payout_split = PayoutSplit(
                    id=uuid.uuid4(),
                    query_id=query.id,
                    total_amount_cents=scenario["max_spend_cents"],
                    contributor_pool_cents=total_payout,
                    platform_fee_cents=platform_fee,
                    distribution=[{
                        "expert_handle": r["expert"],
                        "amount_cents": r["payout_cents"],
                        "contribution_quality": r["confidence_score"]
                    } for r in scenario["expert_responses"]],
                    is_processed=True,
                    processed_at=query.created_at + timedelta(minutes=150)
                )
                session.add(payout_split)
            
            await session.commit()
            
            # Print comprehensive summary
            print("\n✅ Enhanced database seeding complete!")
            print("\n📊 Demo data summary:")
            print(f"  - {len(EXPERTISE_TAGS)} expertise tags across {len(set(tag['category'] for tag in EXPERTISE_TAGS))} categories")
            print(f"  - {len(EXPERT_PROFILES)} expert profiles with realistic backgrounds")
            print(f"  - {len(SAMPLE_QUERY_SCENARIOS)} complex query scenarios")
            print(f"  - {sum(len(s['expert_responses']) for s in SAMPLE_QUERY_SCENARIOS)} expert contributions")
            print(f"  - Complete financial records and payment distributions")
            print(f"  - Realistic citation mappings and answer synthesis")
            print("\n🎯 Demo capabilities:")
            print("  ✅ Multi-expert query responses")
            print("  ✅ Interactive citations and source attribution") 
            print("  ✅ Complete financial transaction tracking")
            print("  ✅ Expert reputation and trust scoring")
            print("  ✅ Diverse expertise across technology, business, and creative domains")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating enhanced seed data: {e}")
            raise


async def main():
    """Main entry point"""
    await create_enhanced_seed_data()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())