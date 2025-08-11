from fastapi import APIRouter
from fastapi import APIRouter, FastAPI, HTTPException, status, Depends, Header, Query, File, UploadFile, Form
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
from google.cloud import firestore, storage
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as idtoken, service_account
from collections import defaultdict
import json

from pydantic import BaseModel, EmailStr
from email_service import email_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

cred_info = {
    "type": "service_account",
    "project_id": "sharecare-466314",
    "private_key_id": "8a0a21d654a94031d2bea21d28b2b2d5fd7354ae",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...REDACTED...\n-----END PRIVATE KEY-----\n",
    "client_email": "sharecare-466314@appspot.gserviceaccount.com",
    "client_id": "107970011439146979175",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/sharecare-466314%40appspot.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

try:
    creds = service_account.Credentials.from_service_account_info(cred_info)
    project_id = cred_info["project_id"]

    # Create clients with explicit project & creds
    db = firestore.Client(project=project_id, credentials=creds)
    storage_client = storage.Client(project=project_id, credentials=creds)

    # Use your bucket (or derive from project_id)
    bucket = storage_client.bucket("sharecare-466314.appspot.com")

    logger.info("Firestore and Storage clients initialized successfully")

except Exception as e:
    logger.error(f"Failed to initialize clients: {e}")
    db = None
    bucket = None

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class UserProfile(BaseModel):
    uid: str
    email: EmailStr
    full_name: str
    phone_number: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    email_verified: bool = False
    is_active: bool = True
    account_type: str = "individual"
    created_at: str
    updated_at: str

class CreateUserRequest(BaseModel):
    uid: str
    email: EmailStr
    full_name: str
    email_verified: bool = False
    photo_url: Optional[str] = None
    account_type: str = "individual"

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None

class UpdatePreferencesRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications: Optional[Dict[str, bool]] = None

class VerifyTokenRequest(BaseModel):
    id_token: str

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class CreateItemRequest(BaseModel):
    name: str
    description: str
    category: str
    food_type: Optional[str] = None
    is_bulk_item: bool = False
    quantity: int = 1
    location: Dict[str, Any]
    pickup_times: str
    expiry_date: Optional[str] = None
    is_for_sale: bool = False
    price: float = 0.0

class UpdateUserStatusRequest(BaseModel):
    is_active: bool

class BulkDeleteItemsRequest(BaseModel):
    item_ids: List[str]

class VerifyItemRequest(BaseModel):
    is_verified: bool

class NotificationRequest(BaseModel):
    title: str
    message: str
    type: str
    target_users: Optional[List[str]] = None

class ReservationRequest(BaseModel):
    item_id: str
    message: Optional[str] = None

class UpdateItemRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    pickup_times: Optional[str] = None
    expiry_date: Optional[str] = None

class SystemSettingsRequest(BaseModel):
    section: str
    key: str
    value: Any

def create_notification(title: str, message: str, notification_type: str, target_users: List[str] = None):
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
        
        db.collection("admin-notifications").add(notification_data)
        logger.info(f"Notification created: {title}")
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        
# Admin Profile Routes
@admin_router.get("/profile")
async def get_admin_profile():
    """Get admin profile information"""
    try:
        # Return static admin profile for now
        admin_profile = {
            "id": "admin_001",
            "email": "hdreddy4783@gmail.com",
            "full_name": "Admin User",
            "role": "super_admin",
            "permissions": [
                "manage_users",
                "manage_items", 
                "view_analytics",
                "manage_notifications",
                "system_settings"
            ],
            "last_login": datetime.utcnow().isoformat(),
            "created_at": "2024-01-01T00:00:00.000Z",
            "avatar_url": None,
            "department": "System Administration",
            "phone": "+353 089 952 5505"
        }
        
        return ApiResponse(
            success=True,
            message="Admin profile retrieved successfully",
            data=admin_profile
        )
        
    except Exception as e:
        logger.error(f"Error retrieving admin profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin profile"
        )

@admin_router.put("/profile")
async def update_admin_profile(
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    department: Optional[str] = None
):
    """Update admin profile information"""
    try:
        # In a real implementation, you would update the admin profile in the database
        updated_profile = {
            "id": "admin_001",
            "email": "hdreddy4783@gmail.com",
            "full_name": full_name or "Admin User",
            "role": "super_admin",
            "phone": phone or "+1-234-567-8900",
            "department": department or "System Administration",
            "updated_at": datetime.utcnow().isoformat()
        }
        
        return ApiResponse(
            success=True,
            message="Admin profile updated successfully",
            data=updated_profile
        )
        
    except Exception as e:
        logger.error(f"Error updating admin profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update admin profile"
        )

@admin_router.post("/logout")
async def admin_logout():
    """Admin logout endpoint"""
    try:
        # Log the logout activity
        logger.info("Admin logged out successfully")
        
        return ApiResponse(
            success=True,
            message="Admin logged out successfully"
        )
        
    except Exception as e:
        logger.error(f"Error during admin logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout"
        )

# Admin Routes
@admin_router.get("/users")
async def get_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Get all users with pagination and filters"""
    try:
        users_ref = db.collection("users")
        query = users_ref
        
        if status_filter == "active":
            query = query.where("is_active", "==", True)
        elif status_filter == "inactive":
            query = query.where("is_active", "==", False)
            
        if account_type:
            query = query.where("account_type", "==", account_type)
        
        docs = query.stream()
        users = []
        
        for doc in docs:
            user_data = doc.to_dict()
            user_data["id"] = doc.id
            
            if search:
                search_lower = search.lower()
                if (search_lower not in user_data.get("full_name", "").lower() and
                    search_lower not in user_data.get("email", "").lower()):
                    continue
            
            users.append(user_data)
        
        reverse = sort_order == "desc"
        if sort_by == "name":
            users.sort(key=lambda x: x.get("full_name", "").lower(), reverse=reverse)
        elif sort_by == "email":
            users.sort(key=lambda x: x.get("email", "").lower(), reverse=reverse)
        else:
            users.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)
        
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_users = users[start_idx:end_idx]
        
        return ApiResponse(
            success=True,
            message="Users retrieved successfully",
            data={
                "users": paginated_users,
                "total": len(users),
                "page": page,
                "limit": limit,
                "total_pages": (len(users) + limit - 1) // limit
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )

@admin_router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Update user active status"""
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_ref.update({
            "is_active": request.is_active,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        action = "activated" if request.is_active else "deactivated"
        logger.info(f"User {action}: {user_id}")
        
        return ApiResponse(
            success=True,
            message=f"User {action} successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating user status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )

@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Delete user account"""
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Send account deletion confirmation email
        user_data = user_doc.to_dict()
        try:
            await email_service.send_account_deletion_email(
                user_data.get("email", ""), 
                user_data.get("full_name", "User")
            )
        except Exception as e:
            logger.error(f"Failed to send deletion confirmation email: {e}")
        
        user_ref.delete()
        
        # Delete user items
        items_query = db.collection("items").where("donor_id", "==", user_id)
        items = items_query.stream()
        for item in items:
            item.reference.delete()
        
        # Delete user reservations
        reservations_query = db.collection("reservations").where("user_id", "==", user_id)
        reservations = reservations_query.stream()
        for reservation in reservations:
            reservation.reference.delete()
        
        # Delete user likes
        likes_query = db.collection("likes").where("user_id", "==", user_id)
        likes = likes_query.stream()
        for like in likes:
            like.reference.delete()
        
        logger.info(f"User deleted successfully: {user_id}")
        
        return ApiResponse(
            success=True,
            message="User deleted successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@admin_router.get("/statistics")
async def get_admin_statistics():
    """Get admin dashboard statistics"""
    try:
        # Get user statistics
        users_ref = db.collection("users")
        all_users = list(users_ref.stream())
        
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.to_dict().get("is_active", True)])
        inactive_users = total_users - active_users
        
        individual_accounts = len([u for u in all_users if u.to_dict().get("account_type") == "individual"])
        business_accounts = len([u for u in all_users if u.to_dict().get("account_type") == "business"])
        
        # Get item statistics
        items_ref = db.collection("items")
        all_items = list(items_ref.stream())
        
        total_items = len(all_items)
        available_items = len([i for i in all_items if i.to_dict().get("status") == "available"])
        reserved_items = len([i for i in all_items if i.to_dict().get("status") == "reserved"])
        donated_items = len([i for i in all_items if i.to_dict().get("status") == "donated"])
        
        # Get category breakdown
        category_stats = defaultdict(int)
        for item in all_items:
            category = item.to_dict().get("category", "others")
            category_stats[category] += 1
        
        # Get monthly statistics
        now = datetime.utcnow()
        monthly_stats = []
        
        for i in range(6):
            month_start = now.replace(day=1) - timedelta(days=30 * i)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            
            month_items = [
                item for item in all_items
                if month_start.isoformat() <= item.to_dict().get("created_at", "") <= month_end.isoformat()
            ]
            
            monthly_stats.append({
                "month": month_start.strftime("%B %Y"),
                "items": len(month_items)
            })
        
        monthly_stats.reverse()
        
        # Get most active donors
        donor_stats = defaultdict(int)
        donor_names = {}
        
        for item in all_items:
            item_data = item.to_dict()
            donor_id = item_data.get("donor_id")
            if donor_id:
                donor_stats[donor_id] += 1
                donor_names[donor_id] = item_data.get("donor_name", "Unknown")
        
        most_active_donors = [
            {"id": donor_id, "name": donor_names[donor_id], "items": count}
            for donor_id, count in sorted(donor_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return ApiResponse(
            success=True,
            message="Statistics retrieved successfully",
            data={
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "inactive": inactive_users,
                    "individual": individual_accounts,
                    "business": business_accounts
                },
                "items": {
                    "total": total_items,
                    "available": available_items,
                    "reserved": reserved_items,
                    "donated": donated_items,
                    "by_category": dict(category_stats)
                },
                "monthly_items": monthly_stats,
                "most_active_donors": most_active_donors
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )

@admin_router.get("/items")
async def get_all_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Get all items with pagination and filters"""
    try:
        items_ref = db.collection("items")
        query = items_ref
        
        if category:
            query = query.where("category", "==", category)
        if status:
            query = query.where("status", "==", status)
        if verified is not None:
            query = query.where("is_verified", "==", verified)
        
        docs = query.stream()
        items = []
        
        for doc in docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            
            if search:
                search_lower = search.lower()
                if (search_lower not in item_data.get("name", "").lower() and
                    search_lower not in item_data.get("description", "").lower()):
                    continue
            
            items.append(item_data)
        
        reverse = sort_order == "desc"
        if sort_by == "name":
            items.sort(key=lambda x: x.get("name", "").lower(), reverse=reverse)
        elif sort_by == "expiry_date":
            items.sort(key=lambda x: x.get("expiry_date", ""), reverse=reverse)
        else:
            items.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)
        
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_items = items[start_idx:end_idx]
        
        return ApiResponse(
            success=True,
            message="Items retrieved successfully",
            data={
                "items": paginated_items,
                "total": len(items),
                "page": page,
                "limit": limit,
                "total_pages": (len(items) + limit - 1) // limit
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve items"
        )

@admin_router.get("/items/{item_id}")
async def get_item_details(item_id: str):
    """Get detailed item information"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        item_data["id"] = item_doc.id
        
        # Get reservations for this item
        reservations_query = db.collection("reservations").where("item_id", "==", item_id)
        reservations = []
        for reservation_doc in reservations_query.stream():
            reservation_data = reservation_doc.to_dict()
            reservation_data["id"] = reservation_doc.id
            reservations.append(reservation_data)
        
        item_data["reservations"] = reservations
        
        # Get reports for this item
        reports_query = db.collection("reports").where("item_id", "==", item_id)
        reports = []
        for report_doc in reports_query.stream():
            report_data = report_doc.to_dict()
            report_data["id"] = report_doc.id
            reports.append(report_data)
        
        item_data["reports"] = reports
        
        # Get view count and likes
        item_data["views"] = item_data.get("views", 0)
        item_data["likes"] = item_data.get("likes", 0)
        
        return ApiResponse(
            success=True,
            message="Item details retrieved successfully",
            data=item_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving item details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item details"
        )

@admin_router.put("/items/{item_id}")
async def update_item(item_id: str, request: UpdateItemRequest):
    """Update item information"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        update_data = {}
        if request.name:
            update_data["name"] = request.name
        if request.description:
            update_data["description"] = request.description
        if request.category:
            update_data["category"] = request.category
        if request.pickup_times:
            update_data["pickup_times"] = request.pickup_times
        if request.expiry_date:
            update_data["expiry_date"] = request.expiry_date
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        item_ref.update(update_data)
        
        return ApiResponse(
            success=True,
            message="Item updated successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update item"
        )

@admin_router.put("/items/{item_id}/verify")
async def verify_item(
    item_id: str,
    request: VerifyItemRequest,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Verify item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_ref.update({
            "is_verified": request.is_verified,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        action = "verified" if request.is_verified else "unverified"
        logger.info(f"Item {action}: {item_id}")
        
        return ApiResponse(
            success=True,
            message=f"Item {action} successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error verifying item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify item"
        )

@admin_router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Delete item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        # Delete related reservations
        reservations_query = db.collection("reservations").where("item_id", "==", item_id)
        reservations = reservations_query.stream()
        for reservation in reservations:
            reservation.reference.delete()
        
        # Delete related likes
        likes_query = db.collection("likes").where("item_id", "==", item_id)
        likes = likes_query.stream()
        for like in likes:
            like.reference.delete()
        
        item_ref.delete()
        
        logger.info(f"Item deleted successfully: {item_id}")
        
        return ApiResponse(
            success=True,
            message="Item deleted successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete item"
        )

@admin_router.post("/items/bulk-delete")
async def bulk_delete_items(
    request: BulkDeleteItemsRequest,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Bulk delete items"""
    try:
        deleted_count = 0
        
        for item_id in request.item_ids:
            try:
                item_ref = db.collection("items").document(item_id)
                item_doc = item_ref.get()
                
                if item_doc.exists:
                    # Delete related data
                    reservations_query = db.collection("reservations").where("item_id", "==", item_id)
                    reservations = reservations_query.stream()
                    for reservation in reservations:
                        reservation.reference.delete()
                    
                    likes_query = db.collection("likes").where("item_id", "==", item_id)
                    likes = likes_query.stream()
                    for like in likes:
                        like.reference.delete()
                    
                    item_ref.delete()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting item {item_id}: {e}")
                continue
        
        logger.info(f"Bulk deleted {deleted_count} items")
        
        return ApiResponse(
            success=True,
            message=f"Successfully deleted {deleted_count} items"
        )
        
    except Exception as e:
        logger.error(f"Error bulk deleting items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk delete items"
        )

@admin_router.get("/notifications")
async def get_admin_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Get admin notifications"""
    try:
        notifications_ref = db.collection("admin-notifications")
        query = notifications_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        
        offset = (page - 1) * limit
        docs = query.offset(offset).limit(limit).stream()
        
        notifications = []
        for doc in docs:
            notification_data = doc.to_dict()
            notification_data["id"] = doc.id
            notifications.append(notification_data)
        
        total_docs = list(notifications_ref.stream())
        total = len(total_docs)
        
        return ApiResponse(
            success=True,
            message="Notifications retrieved successfully",
            data={
                "notifications": notifications,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )

@admin_router.get("/notifications/{notification_id}")
async def get_notification_details(notification_id: str):
    """Get detailed notification information"""
    try:
        notification_ref = db.collection("admin-notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification_data = notification_doc.to_dict()
        notification_data["id"] = notification_doc.id
        
        # Add delivery statistics
        target_users = notification_data.get("target_users", [])
        total_sent = len(target_users) if target_users else 1000  # Mock data
        delivered = int(total_sent * 0.95)  # Mock 95% delivery rate
        read = len(notification_data.get("read_by", []))
        failed = total_sent - delivered
        
        notification_data["delivery_stats"] = {
            "total_sent": total_sent,
            "delivered": delivered,
            "read": read,
            "failed": failed
        }
        
        # Mock user responses
        notification_data["user_responses"] = [
            {
                "user_id": "user1",
                "user_name": "John Doe",
                "response_type": "clicked",
                "response_time": datetime.utcnow().isoformat()
            }
        ]
        
        return ApiResponse(
            success=True,
            message="Notification details retrieved successfully",
            data=notification_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving notification details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification details"
        )

@admin_router.post("/notifications")
async def create_admin_notification(
    request: NotificationRequest,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Create admin notification"""
    try:
        create_notification(
            request.title,
            request.message,
            request.type,
            request.target_users
        )
        
        return ApiResponse(
            success=True,
            message="Notification created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification"
        )

@admin_router.post("/notifications/{notification_id}/resend")
async def resend_notification(notification_id: str, data: dict):
    """Resend notification"""
    try:
        notification_ref = db.collection("admin-notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Create a new notification with updated message
        notification_data = notification_doc.to_dict()
        new_message = data.get("message", notification_data.get("message"))
        
        create_notification(
            notification_data.get("title"),
            new_message,
            notification_data.get("type"),
            notification_data.get("target_users")
        )
        
        return ApiResponse(
            success=True,
            message="Notification resent successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error resending notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend notification"
        )

@admin_router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete notification"""
    try:
        notification_ref = db.collection("admin-notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification_ref.delete()
        
        return ApiResponse(
            success=True,
            message="Notification deleted successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )

@admin_router.put("/reports/{report_id}/resolve")
async def resolve_report(report_id: str):
    """Resolve a report"""
    try:
        report_ref = db.collection("reports").document(report_id)
        report_doc = report_ref.get()
        
        if not report_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report_ref.update({
            "status": "resolved",
            "resolved_at": datetime.utcnow().isoformat(),
            "resolved_by": "admin"
        })
        
        return ApiResponse(
            success=True,
            message="Report resolved successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error resolving report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve report"
        )

@admin_router.get("/users/{user_id}/items")
async def get_user_items(
    user_id: str,
    # admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Get all items by specific user"""
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        
        items_query = db.collection("items").where("donor_id", "==", user_id)
        items_docs = items_query.stream()
        
        items = []
        for doc in items_docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            items.append(item_data)
        
        reservations_query = db.collection("reservations").where("user_id", "==", user_id)
        reservations_docs = reservations_query.stream()
        
        reservations = []
        for doc in reservations_docs:
            reservation_data = doc.to_dict()
            reservation_data["id"] = doc.id
            reservations.append(reservation_data)
        
        return ApiResponse(
            success=True,
            message="User items retrieved successfully",
            data={
                "user": user_data,
                "donated_items": items,
                "reserved_items": reservations,
                "total_donated": len(items),
                "total_reserved": len(reservations)
            }
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving user items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user items"
        )

@admin_router.get("/demand-areas")
async def get_demand_areas():
    """Get areas with high demand for Google Maps integration"""
    try:
        reservations_ref = db.collection("reservations")
        reservations = list(reservations_ref.stream())
        
        location_demand = defaultdict(int)
        location_coords = {}
        
        for reservation in reservations:
            reservation_data = reservation.to_dict()
            location = reservation_data.get("location", {})
            
            if location and "latitude" in location and "longitude" in location:
                lat = round(location["latitude"], 3)
                lng = round(location["longitude"], 3)
                location_key = f"{lat},{lng}"
                
                location_demand[location_key] += 1
                location_coords[location_key] = {
                    "latitude": lat,
                    "longitude": lng,
                    "address": location.get("address", "Unknown")
                }
        
        demand_areas = []
        for location_key, demand_count in location_demand.items():
            coords = location_coords[location_key]
            
            if demand_count >= 10:
                demand_level = "high"
                color = "red"
            elif demand_count >= 5:
                demand_level = "medium"
                color = "orange"
            else:
                demand_level = "low"
                color = "yellow"
            
            demand_areas.append({
                "location": coords,
                "demand_count": demand_count,
                "demand_level": demand_level,
                "color": color
            })
        
        demand_areas.sort(key=lambda x: x["demand_count"], reverse=True)
        
        return ApiResponse(
            success=True,
            message="Demand areas retrieved successfully",
            data={
                "demand_areas": demand_areas,
                "total_areas": len(demand_areas)
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving demand areas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve demand areas"
        )
