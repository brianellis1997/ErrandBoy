# GroupChat Frontend Interface

This directory contains the web frontend for the GroupChat query submission system. The interface allows users to submit questions, track progress in real-time, and view synthesized answers with expert citations.

## Overview

The frontend is a clean, responsive web interface built with vanilla HTML, CSS, and JavaScript. It provides a complete user experience for submitting queries to the expert network and tracking their progress through the workflow.

## Files Structure

```
static/
├── README.md           # This documentation
├── index.html         # Main query submission interface
├── test.html          # Simple API connectivity test page
├── css/
│   └── styles.css     # Custom CSS styles and enhancements
└── js/
    ├── api.js         # API client utilities and error handling
    └── app.js         # Main application logic and UI interactions
```

## Features

### Core Functionality
- **Query Submission Form**: Clean form with validation for questions, phone numbers, and budget
- **Real-Time Progress Tracking**: Live updates showing query processing stages
- **Response Display**: Formatted answers with confidence scores and payment information
- **Error Handling**: Comprehensive error management with user-friendly messages

### Technical Features
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Form Validation**: Client-side validation with helpful error messages
- **Real-Time Updates**: Polls API every 2 seconds for status updates
- **Loading States**: Visual feedback during API calls and processing
- **Progressive Enhancement**: Basic functionality works without JavaScript

## API Integration

The frontend integrates with the following API endpoints:

### Primary Endpoints
- `POST /api/v1/agent/process-query` - Submit a new query for processing
- `GET /api/v1/agent/tools/queries/{id}/status` - Get real-time query status
- `GET /api/v1/agent/health` - Health check endpoint

### Request Format
```javascript
// Query submission
{
  "user_phone": "+1234567890",
  "question_text": "Your question here",
  "max_spend_cents": 500
}
```

### Response Format
```javascript
// Successful submission
{
  "success": true,
  "data": {
    "query_id": "uuid",
    "final_answer": "synthesized answer",
    "confidence_score": 0.89,
    "experts_contacted": 5,
    "contributions_received": 3,
    "payment_processed": true,
    "total_payout_cents": 350
  }
}
```

## How It Works

### 1. Form Submission
1. User fills out the query form (question, phone, budget)
2. Client-side validation checks input requirements
3. Form data is submitted via POST to `/api/v1/agent/process-query`
4. Progress tracking begins immediately

### 2. Progress Tracking
1. System polls `/api/v1/agent/tools/queries/{id}/status` every 2 seconds
2. Progress bar and status messages update based on workflow stage
3. Query details (experts contacted, responses received) are displayed
4. Polling stops when query reaches terminal state

### 3. Result Display
1. Completed queries show synthesized answer with formatting
2. Confidence score and payment information are displayed
3. Users can submit another query or return to form

### 4. Error Handling
1. Network errors, API failures, and validation errors are caught
2. User-friendly error messages are displayed
3. Users can retry failed submissions

## Query Status Flow

The interface tracks queries through these stages:

1. **Pending** (10%) - "Analyzing question..."
2. **Routing** (25%) - "Finding experts..."
3. **Collecting** (50%) - "Contacting network..."
4. **Compiling** (80%) - "Synthesizing answer..."
5. **Completed** (100%) - "Complete!"

Each stage includes estimated time remaining and descriptive messages.

## Running the Frontend

### Development Setup

1. **Start the Backend Server**:
   ```bash
   # Activate conda environment
   source /Users/bdogellis/miniforge3/etc/profile.d/conda.sh
   conda activate GroupChat
   
   # Start FastAPI server
   python -m uvicorn groupchat.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the Interface**:
   - Main Interface: http://localhost:8000/static/index.html
   - API Test Page: http://localhost:8000/static/test.html
   - API Documentation: http://localhost:8000/docs

### Testing

1. **Basic Connectivity Test**:
   ```bash
   # Test static files
   curl http://localhost:8000/static/index.html
   
   # Test API health
   curl http://localhost:8000/api/v1/agent/health
   ```

2. **Frontend API Test**:
   - Open http://localhost:8000/static/test.html
   - Click "Test API Connection" button
   - Should show green checkmark with health response

3. **Full Flow Test**:
   - Open http://localhost:8000/static/index.html
   - Fill out form with valid data
   - Submit query and verify progress tracking
   - Check for proper error handling with invalid inputs

## Code Architecture

### APIClient Class (`api.js`)
- Handles all HTTP requests to the backend
- Provides error handling and user-friendly error messages
- Manages request/response formatting

### QueryStatusTracker Class (`api.js`)
- Manages real-time polling for query status updates
- Handles retry logic with exponential backoff
- Detects terminal query states

### QueryApp Class (`app.js`)
- Main application controller
- Manages UI state and user interactions
- Coordinates between form, progress tracking, and results display

## Styling and Design

### CSS Framework
- **Tailwind CSS**: Loaded via CDN for rapid styling
- **Custom CSS**: Additional styles in `styles.css` for enhanced interactions

### Design Principles
- **Clean and Minimal**: Focus on usability over decoration
- **Responsive**: Mobile-first design that scales to desktop
- **Accessible**: Proper focus indicators and semantic HTML
- **Professional**: Business-appropriate color scheme and typography

### Key Visual Elements
- Progress bar with smooth animations
- Loading spinners and state indicators
- Color-coded status messages (blue for info, green for success, red for errors)
- Card-based layout with subtle shadows and spacing

## Browser Compatibility

### Supported Browsers
- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

### JavaScript Features Used
- ES6+ syntax (async/await, arrow functions, classes)
- Fetch API for HTTP requests
- Modern DOM manipulation methods

## Error Handling Strategy

### Client-Side Validation
- Phone number format validation (+1XXXXXXXXXX)
- Question length validation (10-500 characters)
- Real-time character counting
- Visual error indicators

### Network Error Handling
- Connection timeout handling
- Retry logic for failed requests
- Graceful degradation when API is unavailable
- Clear error messages for different failure types

### API Error Handling
- HTTP status code interpretation
- Structured error response parsing
- Context-aware error messages
- Recovery options for users

## Performance Considerations

### Optimization Techniques
- Minimal external dependencies (only Tailwind CSS CDN)
- Efficient DOM manipulation
- Debounced input validation
- Smart polling with automatic stop conditions

### Loading Performance
- CSS and JS files are small and cacheable
- No build process required
- Fast initial page load
- Progressive enhancement approach

## Future Enhancement Ideas

### Potential Improvements
1. **WebSocket Integration**: Replace polling with real-time updates
2. **Query History**: Allow users to view previous queries
3. **Export Options**: Download answers in various formats
4. **Advanced Filtering**: Filter experts by criteria
5. **Notification System**: Browser notifications for completed queries

### Accessibility Improvements
1. **Screen Reader Support**: Enhanced ARIA labels
2. **Keyboard Navigation**: Full keyboard accessibility
3. **High Contrast Mode**: Support for accessibility preferences
4. **Voice Input**: Speech-to-text for question input

## Troubleshooting

### Common Issues

1. **Static Files Not Loading**:
   - Verify FastAPI StaticFiles mount is configured
   - Check file permissions on static directory
   - Ensure server is running and accessible

2. **API Connection Failures**:
   - Check backend server is running on correct port
   - Verify CORS configuration allows frontend origin
   - Test API endpoints directly with curl

3. **Form Validation Issues**:
   - Check JavaScript console for errors
   - Verify input formats match expected patterns
   - Test with known good values

4. **Progress Tracking Not Working**:
   - Check query ID is returned from submission
   - Verify status polling endpoint is accessible
   - Look for JavaScript errors in browser console

### Debug Tools

1. **Browser Developer Tools**:
   - Network tab to monitor API calls
   - Console tab for JavaScript errors
   - Elements tab to inspect DOM state

2. **API Testing**:
   - Use curl or Postman to test endpoints directly
   - Check FastAPI docs at /docs for API exploration
   - Monitor server logs for backend issues

## Security Considerations

### Client-Side Security
- Input validation prevents injection attacks
- No sensitive data stored in browser
- HTTPS recommended for production
- CORS properly configured

### Best Practices
- Phone numbers are validated but not stored client-side
- No authentication tokens exposed in frontend code
- Error messages don't leak sensitive information
- Form data is sanitized before API submission

---

This frontend interface provides a complete, professional user experience for the GroupChat system. It's designed to be maintainable, extensible, and user-friendly while integrating seamlessly with the backend API.