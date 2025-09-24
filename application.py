"""
Elastic Beanstalk entry point for the GroupChat FastAPI application.
This file is required by AWS Elastic Beanstalk to properly start the application.
"""

from groupchat.main import app

# Elastic Beanstalk looks for 'application' object
application = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8000)