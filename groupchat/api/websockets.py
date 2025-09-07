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


# Demo-specific connection manager
class DemoConnectionManager(ConnectionManager):
    """Manages WebSocket connections specifically for demo coordination"""
    
    def __init__(self):
        super().__init__()
        self.demo_connections: dict[str, List[WebSocket]] = {
            "user": [],
            "expert": [],
            "admin": []
        }
    
    async def connect_demo_screen(self, websocket: WebSocket, screen_type: str):
        """Connect a demo screen (user, expert, admin)"""
        await websocket.accept()
        
        if screen_type not in self.demo_connections:
            screen_type = "admin"  # Default fallback
        
        self.demo_connections[screen_type].append(websocket)
        logger.info(f"Demo {screen_type} screen connected. Total: {len(self.demo_connections[screen_type])}")
    
    def disconnect_demo_screen(self, websocket: WebSocket, screen_type: str):
        """Disconnect a demo screen"""
        if screen_type in self.demo_connections and websocket in self.demo_connections[screen_type]:
            self.demo_connections[screen_type].remove(websocket)
        logger.info(f"Demo {screen_type} screen disconnected.")
    
    async def broadcast_demo_update(self, update: dict):
        """Broadcast demo update to all connected demo screens"""
        message_json = json.dumps({
            "type": "demo_update",
            "data": update
        })
        
        for screen_type, connections in self.demo_connections.items():
            disconnected = []
            
            for connection in connections:
                try:
                    if connection.client_state == WebSocketState.CONNECTED:
                        await connection.send_text(message_json)
                    else:
                        disconnected.append(connection)
                except Exception as e:
                    logger.error(f"Error sending demo update to {screen_type}: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect_demo_screen(connection, screen_type)
    
    async def send_to_screen_type(self, screen_type: str, message: dict):
        """Send message to specific demo screen type"""
        if screen_type not in self.demo_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.demo_connections[screen_type]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message_json)
                else:
                    disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error sending to {screen_type} screen: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect_demo_screen(connection, screen_type)


# Global demo connection manager
demo_manager = DemoConnectionManager()


@router.websocket("/demo/{screen_type}")
async def demo_websocket_endpoint(websocket: WebSocket, screen_type: str):
    """WebSocket endpoint for demo screen coordination"""
    await demo_manager.connect_demo_screen(websocket, screen_type)
    
    try:
        # Send initial connection message
        await websocket.send_text(json.dumps({
            "type": "connection",
            "data": {
                "status": "connected",
                "screen_type": screen_type,
                "message": f"Demo {screen_type} screen connected"
            }
        }))
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {"timestamp": message.get("timestamp")}
                    }))
                elif message.get("type") == "demo_control":
                    # Forward demo control messages to other screens
                    await demo_manager.broadcast_demo_update({
                        "control_action": message.get("action"),
                        "from_screen": screen_type,
                        "timestamp": message.get("timestamp")
                    })
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from demo WebSocket: {data}")
                
    except WebSocketDisconnect:
        demo_manager.disconnect_demo_screen(websocket, screen_type)
    except Exception as e:
        logger.error(f"Demo WebSocket error: {e}")
        demo_manager.disconnect_demo_screen(websocket, screen_type)


# Helper functions for demo notifications
async def notify_demo_progress(progress_data: dict):
    """Notify all demo screens of progress update"""
    await demo_manager.broadcast_demo_update(progress_data)

async def notify_demo_stage_change(stage: str, progress: int):
    """Notify demo screens of stage change"""
    await demo_manager.broadcast_demo_update({
        "stage": stage,
        "progress": progress,
        "timestamp": "now"
    })

async def notify_demo_expert_response(expert_name: str, response_preview: str):
    """Notify demo screens of new expert response"""
    await demo_manager.send_to_screen_type("expert", {
        "type": "new_response",
        "data": {
            "expert": expert_name,
            "preview": response_preview[:100] + "..." if len(response_preview) > 100 else response_preview
        }
    })

async def notify_demo_reset():
    """Notify all demo screens that demo was reset"""
    await demo_manager.broadcast_demo_update({
        "action": "reset",
        "timestamp": "now"
    })