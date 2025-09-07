"""WebSocket endpoints for real-time admin dashboard updates"""

import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for admin dashboard"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Admin WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Admin WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_to_all(self, message: dict):
        """Send a message to all connected clients"""
        if not self.active_connections:
            return
            
        message_json = json.dumps(message)
        disconnected_connections = []
        
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message_json)
                else:
                    disconnected_connections.append(connection)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected_connections:
            self.disconnect(connection)
    
    async def send_activity_update(self, activity_type: str, message: str, level: str = "info"):
        """Send an activity update to all connected clients"""
        await self.send_to_all({
            "type": "activity",
            "data": {
                "activity_type": activity_type,
                "message": message,
                "level": level,
                "timestamp": "now"  # Will be replaced by client with actual timestamp
            }
        })
    
    async def send_metrics_update(self, metrics: dict):
        """Send updated metrics to all connected clients"""
        await self.send_to_all({
            "type": "metrics",
            "data": metrics
        })
    
    async def send_query_update(self, query_id: str, status: str, details: dict = None):
        """Send a query status update to all connected clients"""
        await self.send_to_all({
            "type": "query_update",
            "data": {
                "query_id": query_id,
                "status": status,
                "details": details or {}
            }
        })


# Global connection manager instance
admin_manager = ConnectionManager()


@router.websocket("/admin/ws")
async def admin_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for admin dashboard real-time updates"""
    await admin_manager.connect(websocket)
    
    try:
        # Send initial connection message
        await websocket.send_text(json.dumps({
            "type": "connection",
            "data": {"status": "connected", "message": "Admin dashboard connected"}
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                # Handle different message types from client
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {"timestamp": message.get("timestamp")}
                    }))
                elif message.get("type") == "request_update":
                    # Client requesting specific data update
                    # This could trigger a refresh of specific dashboard sections
                    pass
                    
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from WebSocket: {data}")
                
    except WebSocketDisconnect:
        admin_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        admin_manager.disconnect(websocket)


# Helper functions to be used by other parts of the application
async def notify_query_created(query_id: str, question: str, user_phone: str):
    """Notify admin dashboard of new query creation"""
    await admin_manager.send_activity_update(
        "Query", 
        f"New query submitted: '{question[:50]}{'...' if len(question) > 50 else ''}'",
        "info"
    )
    await admin_manager.send_query_update(query_id, "created", {
        "question": question,
        "user_phone": user_phone
    })


async def notify_query_status_changed(query_id: str, old_status: str, new_status: str):
    """Notify admin dashboard of query status change"""
    await admin_manager.send_activity_update(
        "Query",
        f"Query {query_id[:8]}... status changed: {old_status} → {new_status}",
        "info"
    )
    await admin_manager.send_query_update(query_id, new_status)


async def notify_expert_response(query_id: str, expert_name: str = None):
    """Notify admin dashboard of new expert response"""
    expert_text = f" from {expert_name}" if expert_name else ""
    await admin_manager.send_activity_update(
        "Expert",
        f"New response received{expert_text}",
        "success"
    )


async def notify_payment_processed(query_id: str, amount_cents: int):
    """Notify admin dashboard of payment processing"""
    amount_dollars = amount_cents / 100
    await admin_manager.send_activity_update(
        "Payment",
        f"Payment processed: ${amount_dollars:.2f} distributed for query",
        "success"
    )


async def notify_system_event(message: str, level: str = "info"):
    """Notify admin dashboard of system events"""
    await admin_manager.send_activity_update("System", message, level)