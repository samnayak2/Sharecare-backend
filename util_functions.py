
import logging
import uuid
import string
import random
from fastapi import HTTPException, status, Header
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def upload_file_to_storage(bucket, file_content: bytes, filename: str, content_type: str) -> str:
    """Upload file to Firebase Storage and return public URL"""
    try:
        # Generate unique filename
        file_extension = filename.split('.')[-1] if '.' in filename else 'jpg'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Upload to storage
        blob = bucket.blob(f"images/{unique_filename}")
        blob.upload_from_string(file_content, content_type=content_type)
        
        # Make blob publicly accessible
        blob.make_public()
        
        return blob.public_url
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

def verify_firebase_token(uid: str) -> Dict[str, Any]:
    try:
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return {
            "uid": uid,
            
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Get UID from Authorization header directly."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

    if authorization.startswith("Bearer "):
        uid = authorization.split(" ", 1)[1]
    else:
        uid = authorization

    return verify_firebase_token(uid)


def create_notification(db,title: str, message: str, notification_type: str,isAdminNotification:bool, target_users: List[str] = None):
    """Create notification in database"""
    try:
        notification_data = {
            "title": title,
            "message": message,
            "type": notification_type,
            "target_users": target_users or [],
            "created_at": datetime.utcnow().isoformat(),
            "read_by": []
        }
        if isAdminNotification:
            db.collection("admin-notifications").add(notification_data)
        else:
            db.collection("notifications").add(notification_data)
        logger.info(f"Notification created: {title}")
    except Exception as e:
        logger.error(f"Error creating notification: {e}")

def generate_tracking_id() -> str:
    """Generate a unique tracking ID"""
    prefix = "SC"  # ShareCare prefix
    timestamp = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{timestamp}{random_part}"

def create_tracking_record(db, reservation_id: str, item_id: str, donor_id: str, requester_id: str) -> str:
    """Create a new tracking record"""
    try:
        tracking_id = generate_tracking_id()
        
        tracking_data = {
            "tracking_id": tracking_id,
            "reservation_id": reservation_id,
            "item_id": item_id,
            "donor_id": donor_id,
            "requester_id": requester_id,
            "current_status": "request_accepted",
            "status_history": [
                {
                    "status": "request_submitted",
                    "timestamp": datetime.utcnow().isoformat(),
                    "notes": "Request submitted to donor",
                    "updated_by": requester_id
                },
                {
                    "status": "request_accepted",
                    "timestamp": datetime.utcnow().isoformat(),
                    "notes": "Request accepted by donor",
                    "updated_by": donor_id
                }
            ],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        db.collection("tracking").add(tracking_data)
        logger.info(f"Tracking record created: {tracking_id}")
        
        return tracking_id
        
    except Exception as e:
        logger.error(f"Error creating tracking record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tracking record"
        )
    
# Tracking status definitions
TRACKING_STATUSES = {
    "request_submitted": {
        "title": "Request Submitted",
        "description": "Your request has been submitted to the donor",
        "icon": "send"
    },
    "request_accepted": {
        "title": "Request Accepted",
        "description": "Great! The donor has accepted your request",
        "icon": "check_circle"
    },
    "preparing_item": {
        "title": "Preparing Item",
        "description": "The donor is preparing your item",
        "icon": "inventory"
    },
    "packing_completed": {
        "title": "Packing Completed",
        "description": "Your item has been packed and is ready",
        "icon": "package"
    },
    "ready_for_pickup": {
        "title": "Ready for Pickup",
        "description": "Your item is ready for pickup! Contact the donor to arrange collection",
        "icon": "local_shipping"
    },
    "picked_up": {
        "title": "Item Picked Up",
        "description": "Item has been successfully picked up",
        "icon": "done_all"
    },
    "completed": {
        "title": "Completed",
        "description": "Transaction completed successfully",
        "icon": "celebration"
    },
    "cancelled": {
        "title": "Cancelled",
        "description": "The request has been cancelled",
        "icon": "cancel"
    }
}

def update_tracking_status( db, tracking_id: str, new_status: str, notes: str = None, updated_by: str = None):
    """Update tracking status"""
    try:
        # Find tracking record
        tracking_query = db.collection("tracking").where("tracking_id", "==", tracking_id)
        tracking_docs = list(tracking_query.stream())
        
        if not tracking_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking record not found"
            )
        
        tracking_doc = tracking_docs[0]
        tracking_data = tracking_doc.to_dict()
        
        # Add new status to history
        new_status_entry = {
            "status": new_status,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes or TRACKING_STATUSES.get(new_status, {}).get("description", ""),
            "updated_by": updated_by
        }
        
        status_history = tracking_data.get("status_history", [])
        status_history.append(new_status_entry)
        
        # Update tracking record
        tracking_doc.reference.update({
            "current_status": new_status,
            "status_history": status_history,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # Send notification to requester
        if new_status in TRACKING_STATUSES:
            status_info = TRACKING_STATUSES[new_status]
            create_notification(
                db=db,
                title=
                 f"📦 {status_info['title']}",
                message=
                f"Tracking ID: {tracking_id} - {status_info['description']}",
                notification_type=
                "tracking_update",
                isAdminNotification=False,
                target_users=
                [tracking_data["requester_id"]]
            )
        
        logger.info(f"Tracking status updated: {tracking_id} -> {new_status}")
        
    except Exception as e:
        logger.error(f"Error updating tracking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tracking status"
        )

async def get_current_user_Data_from_database( db, uid: str):
    """Get user data from database"""
    if not db:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not available"
        )
    try:
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        return user_doc.to_dict()
    except Exception as e:
        logger.error(f"Error getting user data from database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user data from database"
        )