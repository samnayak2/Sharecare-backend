import base64
import json
import os
from fastapi import APIRouter, FastAPI, HTTPException, status, Depends, Header, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
from google.cloud import firestore, storage
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as idtoken, service_account
import uuid
import random
import string
from email_service import email_service
from admin_routes import admin_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ShareCare API",
    description="Backend API for ShareCare mobile application - Food & Clothes Connect",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(admin_router)
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

try:
    # Load credentials from base64 env var
    creds_json = base64.b64decode(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    creds_dict = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(creds_dict)

    # Firestore & Storage with credentials
    db = firestore.Client(credentials=credentials, project=creds_dict["project_id"])
    storage_client = storage.Client(credentials=credentials, project=creds_dict["project_id"])
    bucket = storage_client.bucket("sharecare-466314.appspot.com")

    logger.info("Firestore and Storage clients initialized successfully")

except Exception as e:
    logger.error(f"Failed to initialize clients: {e}")
    db = None
    bucket = None


# Admin email
ADMIN_EMAIL="samruddhi982@gmail.com"

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class CreateUserRequest(BaseModel):
    uid: str
    email: EmailStr
    full_name: str
    email_verified: bool = False
    photo_url: Optional[str] = None
    account_type: str = "individual"
    phoneNumber:str

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

class UpdateItemRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    pickup_times: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None

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
    requested_quantity: int = 1

class UpdateTrackingStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class ReportItemRequest(BaseModel):
    reason: str
    description: str

class MarkNotificationReadRequest(BaseModel):
    notification_ids: List[str]

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

# Helper functions
def generate_tracking_id() -> str:
    """Generate a unique tracking ID"""
    prefix = "SC"  # ShareCare prefix
    timestamp = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{timestamp}{random_part}"

def upload_file_to_storage(file_content: bytes, filename: str, content_type: str) -> str:
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

def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """Verify Firebase ID token using Google Auth API"""
    try:
        auth_req = google_requests.Request()
        token_info = idtoken.verify_firebase_token(id_token, auth_req)

        if not token_info:
            raise ValueError('Invalid token')

        return {
            "uid": token_info.get("sub"),
            "email": token_info.get("email"),
            "email_verified": token_info.get("email_verified", False),
            "name": token_info.get("name", ""),
            "picture": token_info.get("picture")
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Get current user from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    try:
        token = authorization.split(" ")[1] if authorization.startswith("Bearer ") else authorization
        return verify_firebase_token(token)
    except IndexError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

async def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Verify admin user"""
    if current_user["email"] != ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def create_notification(title: str, message: str, notification_type: str,isAdminNotification:bool, target_users: List[str] = None):
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

def create_tracking_record(reservation_id: str, item_id: str, donor_id: str, requester_id: str) -> str:
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

def update_tracking_status(tracking_id: str, new_status: str, notes: str = None, updated_by: str = None):
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
                f"📦 {status_info['title']}",
                f"Tracking ID: {tracking_id} - {status_info['description']}",
                "tracking_update",
                [tracking_data["requester_id"]]
            )
        
        logger.info(f"Tracking status updated: {tracking_id} -> {new_status}")
        
    except Exception as e:
        logger.error(f"Error updating tracking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tracking status"
        )

async def get_current_user_Data_from_database(uid: str):
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

# API Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "ShareCare API is running",
        "status": "healthy",
        "service": "Food & Clothes Connect",
        "version": "1.0.0"
    }

@app.get("/api/v1/health")
async def health_check():
    """Detailed health check"""
    firestore_status = "connected" if db else "disconnected"
    storage_status = "connected" if bucket else "disconnected"
    
    return ApiResponse(
        success=True,
        message="ShareCare API is healthy",
        data={
            "service": "ShareCare API",
            "version": "1.0.0",
            "description": "Food & Clothes Connect Backend",
            "firestore_status": firestore_status,
            "storage_status": storage_status,
        }
    )

# Authentication Routes
@app.post("/api/v1/auth/verify")
async def verify_token(request: VerifyTokenRequest):
    """Verify Firebase ID token"""
    try:
        user_data = verify_firebase_token(request.id_token)
        
        # Send login notification (optional, can be enabled/disabled)
        try:
            # Get IP address from request (you may need to import Request from fastapi)
            ip_address = "Unknown"  # You can get this from request headers
            await email_service.send_login_notification(user_data["email"], user_data.get("name", "User"), ip_address)
        except Exception as e:
            logger.error(f"Failed to send login notification: {e}")

        return ApiResponse(
            success=True,
            message="Token verified successfully",
            data={
                "user": user_data,
                "verified": True,
                "is_admin": user_data["email"] == ADMIN_EMAIL
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/api/v1/auth/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint"""
    try:
        if request.email != ADMIN_EMAIL:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials! Email does not match the expected admin email."
            )
        
        if request.password != "admin123":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials! Password does not match the expected admin password."
            )
        
        return ApiResponse(
            success=True,
            message="Admin login successful",
            data={
                "user": {
                    "id": "1a2b3c4d5e6f",
                    "email": request.email,
                    "phoneNumber": "+",
                    "address": "123 Admin St, Admin City, Admin Country",
                    "bio": "System administrator",
                    "isAdmin": True,
                    "uid": str(uuid.uuid4()),
                    "email_verified": True,
                    "full_name": "Admin User",
                    "account_type": "admin",
                    "is_active": True,
                    "created_at": "2025-07-28T20:32:37.839Z",
                    "updated_at": "2025-07-28T20:35:00.123Z",
                    "photo_url": None
                },
                "token": "admin_token 1234567890abcdef",
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# User Management Routes
@app.post("/api/v1/user/create")
async def create_user(
    request: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create user profile in Firestore"""

    print("Creating user profile",current_user, request)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not available"
        )
    
    try:
        if current_user["uid"] != request.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create profile for another user"
            )
        
        user_ref = db.collection("users").document(request.uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return ApiResponse(
                success=True,
                message="User already exists",
                data=user_doc.to_dict()
            )
        
        user_data = {
            "uid": request.uid,
            "email": request.email,
            "full_name": request.full_name,
            "email_verified": request.email_verified,
            "photo_url": request.photo_url,
            "rating": 0,
            "is_active": True,
            "account_type": request.account_type,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "phoneNumber": request.phoneNumber,
            "address": "not available",
            "bio": "not available",
            "isAdmin": False
        }
        
        user_ref.set(user_data)
        
        create_notification(
            "New User Registered",
            f"New {request.account_type} account registered: {request.full_name} ({request.email})",
            "user_registration",
            [ADMIN_EMAIL]
        )

        # Send welcome email
        try:
            await email_service.send_welcome_email(request.email, request.full_name)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
        
        logger.info(f"User created successfully: {request.uid}")
        
        return ApiResponse(
            success=True,
            message="User created successfully",
            data=user_data
        )
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@app.get("/api/v1/user/profile")
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user profile from Firestore"""
    if not db:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not available"
        )
    
    try:
        user_ref = db.collection("users").document(current_user["uid"])
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return ApiResponse(
                success=True,
                message="Profile retrieved successfully",
                data=user_data
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )

@app.put("/api/v1/user/profile")
async def update_user_profile(
    request: UpdateProfileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile"""
    if not db:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not available"
        )
    
    try:
        user_ref = db.collection("users").document(current_user["uid"])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if request.full_name is not None:
            update_data["full_name"] = request.full_name
        if request.phone_number is not None:
            update_data["phoneNumber"] = request.phone_number
        if request.address is not None:
            update_data["address"] = request.address
        if request.bio is not None:
            update_data["bio"] = request.bio
        
        user_ref.update(update_data)
        
        updated_doc = user_ref.get()
        
        return ApiResponse(
            success=True,
            message="Profile updated successfully",
            data=updated_doc.to_dict()
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@app.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload file to Firebase Storage"""
    try:
        if not bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage not available"
            )
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only images are allowed."
            )
        
        # Read file content
        file_content = await file.read()
        
        # Upload to storage
        file_url = upload_file_to_storage(file_content, file.filename, file.content_type)
        
        return ApiResponse(
            success=True,
            message="File uploaded successfully",
            data={"url": file_url}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

# Items Routes
@app.get("/api/v1/items")
async def get_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sortBy: Optional[str] = Query("created_at"),
    sortOrder: Optional[str] = Query("desc"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get items with pagination and filters"""
    try:
        items_ref = db.collection("items")
        query = items_ref
        
        if category:
            query = query.where("category", "==", category)
        if status:
            query = query.where("status", "==", status)
        
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
        
        reverse = sortOrder == "desc"
        if sortBy == "name":
            items.sort(key=lambda x: x.get("name", "").lower(), reverse=reverse)
        elif sortBy == "expiry_date":
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

@app.post("/api/v1/items")
async def create_item(
    request: CreateItemRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create new item"""
    try:
        user_ref = db.collection("users").document(current_user["uid"])
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        current_user_data= await get_current_user_Data_from_database(current_user["uid"])
        user_data = user_doc.to_dict()
        
        item_data = {
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "food_type": request.food_type,
            "is_bulk_item": request.is_bulk_item,
            "quantity": request.quantity,
            "donor": {
            "id": current_user_data["uid"],
            "name": current_user_data["full_name"],
            "type": current_user_data["account_type"],
            "rating": 0 ,
            "photo_url": current_user_data["photo_url"]
        },
            "donor_id": current_user["uid"],
            "donor_name": user_data.get("full_name", "Unknown"),
            "location": request.location,
            "pickup_times": request.pickup_times,
            "expiry_date": request.expiry_date,
            "is_for_sale": request.is_for_sale,
            "price": request.price,
            "images": [],
            "status": "available",
            "is_verified": False,
            "likes": 0,
            "views": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        doc_ref = db.collection("items").add(item_data)
        item_data["id"] = doc_ref[1].id
        
        create_notification(
            "New Item Donated",
            f"New {request.category} item donated: {request.name} by {user_data.get('full_name', 'Unknown')}",
            "item_donated",
            [ADMIN_EMAIL]
        )

        # Send donation confirmation email
        try:
            await email_service.send_item_donation_confirmation(
                current_user["email"], 
                user_data.get("full_name", "User"), 
                item_data
            )
        except Exception as e:
            logger.error(f"Failed to send donation confirmation email: {e}")
        
        return ApiResponse(
            success=True,
            message="Item created successfully",
            data=item_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item"
        )

@app.get("/api/v1/items/{item_id}")
async def get_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get item by ID"""
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
        
        # Increment view count
        item_ref.update({"views": item_data.get("views", 0) + 1})
        
        return ApiResponse(
            success=True,
            message="Item retrieved successfully",
            data=item_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item"
        )

@app.put("/api/v1/items/{item_id}")
async def update_item(
    item_id: str,
    request: UpdateItemRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        
        # Check if user owns the item
        if item_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this item"
            )
        
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        
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
        if request.status:
            update_data["status"] = request.status
        
        item_ref.update(update_data)
        
        updated_doc = item_ref.get()
        updated_data = updated_doc.to_dict()
        updated_data["id"] = item_id
        
        return ApiResponse(
            success=True,
            message="Item updated successfully",
            data=updated_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update item"
        )

@app.delete("/api/v1/items/{item_id}")
async def delete_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
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
        
        item_data = item_doc.to_dict()
        
        # Check if user owns the item
        if item_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this item"
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

@app.post("/api/v1/items/{item_id}/images")
async def upload_item_images(
    item_id: str,
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload images for an item"""
    try:
        if not bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage not available"
            )
        
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        
        if item_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to upload images for this item"
            )
        
        uploaded_urls = []
        
        for file in files:
            if file.content_type not in ['image/jpeg', 'image/png', 'image/gif', 'image/webp']:
                continue
            
            file_content = await file.read()
            file_url = upload_file_to_storage(file_content, file.filename, file.content_type)
            uploaded_urls.append(file_url)
        
        # Update item with image URLs
        current_images = item_data.get("images", [])
        updated_images = current_images + uploaded_urls
        
        item_ref.update({
            "images": updated_images,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        return ApiResponse(
            success=True,
            message="Images uploaded successfully",
            data={"urls": uploaded_urls}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading item images: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload images"
        )

@app.post("/api/v1/items/{item_id}/like")
async def like_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Like an item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        # Check if user already liked this item
        likes_ref = db.collection("likes").where("item_id", "==", item_id).where("user_id", "==", current_user["uid"])
        existing_likes = list(likes_ref.stream())
        
        if existing_likes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item already liked"
            )
        
        # Add like
        like_data = {
            "item_id": item_id,
            "user_id": current_user["uid"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        db.collection("likes").add(like_data)
        
        # Update item likes count
        item_data = item_doc.to_dict()
        new_likes_count = item_data.get("likes", 0) + 1
        item_ref.update({"likes": new_likes_count})
        
        return ApiResponse(
            success=True,
            message="Item liked successfully",
            data={"likes": new_likes_count}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error liking item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to like item"
        )

@app.delete("/api/v1/items/{item_id}/like")
async def unlike_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Unlike an item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        # Find and remove like
        likes_ref = db.collection("likes").where("item_id", "==", item_id).where("user_id", "==", current_user["uid"])
        existing_likes = list(likes_ref.stream())
        
        if not existing_likes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not liked"
            )
        
        # Remove like
        for like_doc in existing_likes:
            like_doc.reference.delete()
        
        # Update item likes count
        item_data = item_doc.to_dict()
        new_likes_count = max(0, item_data.get("likes", 0) - 1)
        item_ref.update({"likes": new_likes_count})
        
        return ApiResponse(
            success=True,
            message="Item unliked successfully",
            data={"likes": new_likes_count}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error unliking item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlike item"
        )

@app.post("/api/v1/items/{item_id}/reserve")
async def reserve_item(
    item_id: str,
    quantity: int = Form(1),
    message: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reserve an item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        
        if item_data.get("status") != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item is not available for reservation"
            )
        
        if item_data.get("donor_id") == current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reserve your own item"
            )
        
        user_ref = db.collection("users").document(current_user["uid"])
        user_doc = user_ref.get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        reservation_data = {
            "item_id": item_id,
            "item_name": item_data.get("name", "Unknown"),
            "user_id": current_user["uid"],
            "user_name": user_data.get("full_name", "Unknown"),
            "donor_id": item_data.get("donor_id"),
            "message": message,
            "requested_quantity": quantity,
            "status": "pending",
            "location": item_data.get("location", {}),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        doc_ref = db.collection("reservations").add(reservation_data)
        reservation_data["id"] = doc_ref[1].id
        
        create_notification(
            "New Reservation Request",
            f"Someone wants to reserve your item '{item_data.get('name', 'Unknown')}'",
            "reservation_request",
            [item_data.get("donor_id")]
        )
        
        return ApiResponse(
            success=True,
            message="Item reserved successfully",
            data=reservation_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error reserving item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reserve item"
        )

@app.post("/api/v1/items/{item_id}/pickup")
async def mark_item_picked_up(
    item_id: str,
    reservationId: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark item as picked up"""
    try:
        # Verify reservation exists and belongs to user
        reservation_ref = db.collection("reservations").document(reservationId)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )
        
        reservation_data = reservation_doc.to_dict()
        
        if reservation_data.get("user_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to mark this item as picked up"
            )
        
        # Update reservation status
        reservation_ref.update({
            "status": "picked_up",
            "picked_up_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # Update item status
        item_ref = db.collection("items").document(item_id)
        item_ref.update({
            "status": "donated",
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # Update tracking status if exists
        tracking_query = db.collection("tracking").where("reservation_id", "==", reservationId)
        tracking_docs = list(tracking_query.stream())
        
        if tracking_docs:
            tracking_doc = tracking_docs[0]
            tracking_data = tracking_doc.to_dict()
            update_tracking_status(
                tracking_data["tracking_id"], 
                "picked_up", 
                "Item successfully picked up by requester",
                current_user["uid"]
            )
        
        return ApiResponse(
            success=True,
            message="Item marked as picked up successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error marking item as picked up: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark item as picked up"
        )

@app.post("/api/v1/items/{item_id}/report")
async def report_item(
    item_id: str,
    request: ReportItemRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Report an item"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        report_data = {
            "item_id": item_id,
            "reporter_id": current_user["uid"],
            "reason": request.reason,
            "description": request.description,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        db.collection("reports").add(report_data)
        
        # Notify admin
        create_notification(
            "Item Reported",
            f"Item '{item_doc.to_dict().get('name', 'Unknown')}' has been reported for: {request.reason}",
            "item_report",
            [ADMIN_EMAIL]
        )
        
        return ApiResponse(
            success=True,
            message="Item reported successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error reporting item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to report item"
        )

@app.post("/api/v1/items/{item_id}/favorite")
async def add_to_favorites(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add item to favorites"""
    try:
        # Check if already in favorites
        favorites_query = db.collection("favorites").where("item_id", "==", item_id).where("user_id", "==", current_user["uid"])
        existing_favorites = list(favorites_query.stream())
        
        if existing_favorites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item already in favorites"
            )
        
        favorite_data = {
            "item_id": item_id,
            "user_id": current_user["uid"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        db.collection("favorites").add(favorite_data)
        
        return ApiResponse(
            success=True,
            message="Item added to favorites"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error adding to favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to favorites"
        )

@app.delete("/api/v1/items/{item_id}/favorite")
async def remove_from_favorites(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove item from favorites"""
    try:
        favorites_query = db.collection("favorites").where("item_id", "==", item_id).where("user_id", "==", current_user["uid"])
        existing_favorites = list(favorites_query.stream())
        
        if not existing_favorites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not in favorites"
            )
        
        for favorite_doc in existing_favorites:
            favorite_doc.reference.delete()
        
        return ApiResponse(
            success=True,
            message="Item removed from favorites"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error removing from favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from favorites"
        )

@app.get("/api/v1/items/category/{category}")
async def get_items_by_category(
    category: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get items by category"""
    try:
        items_query = db.collection("items").where("category", "==", category).where("status", "==", "available")
        items_docs = items_query.stream()
        
        items = []
        for doc in items_docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            items.append(item_data)
        
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Items retrieved successfully",
            data={"items": items}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving items by category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve items by category"
        )

@app.get("/api/v1/items/search")
async def search_items(
    q: str = Query(...),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    radius: Optional[int] = Query(10),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Search items"""
    try:
        items_ref = db.collection("items")
        query = items_ref.where("status", "==", "available")
        
        if category:
            query = query.where("category", "==", category)
        
        docs = query.stream()
        items = []
        
        search_lower = q.lower()
        
        for doc in docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            
            # Search in name and description
            if (search_lower in item_data.get("name", "").lower() or
                search_lower in item_data.get("description", "").lower()):
                items.append(item_data)
        
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Search completed successfully",
            data={"items": items}
        )
        
    except Exception as e:
        logger.error(f"Error searching items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search items"
        )

@app.get("/api/v1/items/nearby")
async def get_nearby_items(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: int = Query(10),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get nearby items"""
    try:
        # This is a simplified implementation
        # In production, you'd use geospatial queries
        items_query = db.collection("items").where("status", "==", "available")
        items_docs = items_query.stream()
        
        nearby_items = []
        
        for doc in items_docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            
            # Simple distance calculation (you'd use proper geospatial functions in production)
            item_location = item_data.get("location", {})
            if "latitude" in item_location and "longitude" in item_location:
                # Add to nearby items (simplified - should calculate actual distance)
                nearby_items.append(item_data)
        
        nearby_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Nearby items retrieved successfully",
            data={"items": nearby_items}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving nearby items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve nearby items"
        )

@app.get("/api/v1/items/{item_id}/stats")
async def get_item_stats(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get item statistics"""
    try:
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        
        # Get reservations count
        reservations_query = db.collection("reservations").where("item_id", "==", item_id)
        reservations_count = len(list(reservations_query.stream()))
        
        # Get likes count
        likes_count = item_data.get("likes", 0)
        
        # Get views count
        views_count = item_data.get("views", 0)
        
        stats = {
            "views": views_count,
            "likes": likes_count,
            "reservations": reservations_count,
            "status": item_data.get("status", "unknown"),
            "created_at": item_data.get("created_at"),
            "updated_at": item_data.get("updated_at")
        }
        
        return ApiResponse(
            success=True,
            message="Item statistics retrieved successfully",
            data=stats
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving item stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item statistics"
        )

# User-specific item routes
@app.get("/api/v1/user/donations")
async def get_user_donations(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get items donated by current user"""
    try:
        items_query = db.collection("items").where("donor_id", "==", current_user["uid"])
        items_docs = items_query.stream()
        
        items = []
        for doc in items_docs:
            item_data = doc.to_dict()
            item_data["id"] = doc.id
            items.append(item_data)
        
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="User donations retrieved successfully",
            data={"items": items}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user donations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve donations"
        )

@app.get("/api/v1/user/reservations")
async def get_user_reservations(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get reservations made by current user"""
    try:
        reservations_query = db.collection("reservations").where("user_id", "==", current_user["uid"])
        reservations_docs = reservations_query.stream()
        
        reservations = []
        for doc in reservations_docs:
            reservation_data = doc.to_dict()
            reservation_data["id"] = doc.id
            
            # Get item details
            item_ref = db.collection("items").document(reservation_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                reservation_data["item"] = item_doc.to_dict()
            
            reservations.append(reservation_data)
        
        reservations.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="User reservations retrieved successfully",
            data={"reservations": reservations}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user reservations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reservations"
        )

@app.get("/api/v1/user/pickups")
async def get_user_pickups(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get items picked up by current user"""
    try:
        reservations_query = db.collection("reservations").where("user_id", "==", current_user["uid"]).where("status", "==", "picked_up")
        reservations_docs = reservations_query.stream()
        
        pickups = []
        for doc in reservations_docs:
            pickup_data = doc.to_dict()
            pickup_data["id"] = doc.id
            
            # Get item details
            item_ref = db.collection("items").document(pickup_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                pickup_data["item"] = item_doc.to_dict()
            
            pickups.append(pickup_data)
        
        pickups.sort(key=lambda x: x.get("picked_up_at", x.get("created_at", "")), reverse=True)
        
        return ApiResponse(
            success=True,
            message="User pickups retrieved successfully",
            data={"pickups": pickups}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user pickups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pickups"
        )

@app.get("/api/v1/user/favorites")
async def get_favorite_items(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's favorite items"""
    try:
        favorites_query = db.collection("favorites").where("user_id", "==", current_user["uid"])
        favorites_docs = favorites_query.stream()
        
        favorite_items = []
        for doc in favorites_docs:
            favorite_data = doc.to_dict()
            
            # Get item details
            item_ref = db.collection("items").document(favorite_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                item_data = item_doc.to_dict()
                item_data["id"] = item_doc.id
                item_data["favorited_at"] = favorite_data.get("created_at")
                favorite_items.append(item_data)
        
        favorite_items.sort(key=lambda x: x.get("favorited_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Favorite items retrieved successfully",
            data={"items": favorite_items}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving favorite items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve favorite items"
        )

# Reservations Routes
@app.post("/api/v1/reservations")
async def create_reservation(
    request: ReservationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create item reservation"""
    try:
        item_ref = db.collection("items").document(request.item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        
        if item_data.get("status") != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item is not available for reservation"
            )
        
        if item_data.get("donor_id") == current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reserve your own item"
            )
        
        user_ref = db.collection("users").document(current_user["uid"])
        user_doc = user_ref.get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        reservation_data = {
            "item_id": request.item_id,
            "item_name": item_data.get("name", "Unknown"),
            "user_id": current_user["uid"],
            "user_name": user_data.get("full_name", "Unknown"),
            "donor_id": item_data.get("donor_id"),
            "message": request.message,
            "requested_quantity": getattr(request, 'requested_quantity', 1),
            "status": "pending",
            "location": item_data.get("location", {}),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "item":{
                "name": item_data.get("name",""),
                "category": item_data.get("category",""),
                "images": item_data.get("images",[]),
                "pickup_times":item_data.get('pickup_times','')
            }
        }
        
        doc_ref = db.collection("reservations").add(reservation_data)
        reservation_data["id"] = doc_ref[1].id
        
        create_notification(
            "New Reservation Request",
            f"Someone wants to reserve your item '{item_data.get('name', 'Unknown')}'",
            "reservation_request",
            [item_data.get("donor_id")]
        )

        # Send emails to both donor and requester
        try:
            # Email to donor
            await email_service.send_reservation_request_email(
                item_data.get("donor_id"), 
                item_data.get("donor_name", "Donor"), 
                user_data.get("full_name", "User"), 
                item_data, 
                request.message
            )
            
            # Email to requester
            await email_service.send_reservation_confirmation_email(
                current_user["email"], 
                user_data.get("full_name", "User"), 
                item_data.get("donor_name", "Donor"), 
                item_data
            )
        except Exception as e:
            logger.error(f"Failed to send reservation emails: {e}")
        
        return ApiResponse(
            success=True,
            message="Reservation created successfully",
            data=reservation_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create reservation"
        )

@app.delete("/api/v1/reservations/{reservation_id}")
async def cancel_reservation(
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel a reservation"""
    try:
        reservation_ref = db.collection("reservations").document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )
        
        reservation_data = reservation_doc.to_dict()
        
        # Check if user owns the reservation
        if reservation_data.get("user_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this reservation"
            )
        
        # Update reservation status
        reservation_ref.update({
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # Notify donor
        create_notification(
            "Reservation Cancelled",
            f"A reservation for your item '{reservation_data.get('item_name', 'Unknown')}' has been cancelled",
            "reservation_cancelled",
            [reservation_data.get("donor_id")]
        )
        
        return ApiResponse(
            success=True,
            message="Reservation cancelled successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error cancelling reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel reservation"
        )

@app.put("/api/v1/reservations/{reservation_id}/status")
async def update_reservation_status(
    reservation_id: str,
    status: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update reservation status (approve/decline) with automatic rejection logic and tracking"""
    try:
        reservation_ref = db.collection("reservations").document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )
        
        reservation_data = reservation_doc.to_dict()
        
        # Get item details
        item_ref = db.collection("items").document(reservation_data["item_id"])
        item_doc = item_ref.get()
        item_data = item_doc.to_dict()
        
        # Only donor can update reservation status
        if item_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the donor can update reservation status"
            )
        
        # Update reservation status
        reservation_ref.update({
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        if status == "approved":
            # Create tracking record
            tracking_id = create_tracking_record(
                reservation_id,
                reservation_data["item_id"],
                item_data.get("donor_id"),
                reservation_data["user_id"]
            )
            
            # Update reservation with tracking ID
            reservation_ref.update({"tracking_id": tracking_id})
            
            # Handle bulk vs single item logic
            if item_data.get("is_bulk_item") and item_data.get("quantity", 0) > 1:
                # For bulk items, decrease quantity
                new_quantity = item_data.get("quantity", 1) - reservation_data.get("requested_quantity", 1)
                if new_quantity <= 0:
                    # All items taken, reject remaining requests
                    item_ref.update({
                        "status": "donated",
                        "quantity": 0,
                        "updated_at": datetime.utcnow().isoformat()
                    })
                    
                    # Reject all other pending requests
                    await reject_other_requests(reservation_data["item_id"], reservation_id, item_data)
                else:
                    # Update quantity
                    item_ref.update({
                        "quantity": new_quantity,
                        "updated_at": datetime.utcnow().isoformat()
                    })
            else:
                # For single items, mark as reserved and reject other requests
                item_ref.update({
                    "status": "reserved",
                    "updated_at": datetime.utcnow().isoformat()
                })
                
                # Reject all other pending requests
                await reject_other_requests(reservation_data["item_id"], reservation_id, item_data)
            
            # Create chat room for approved reservation
            chat_data = {
                "reservation_id": reservation_id,
                "item_id": reservation_data["item_id"],
                "donor_id": item_data.get("donor_id"),
                "requester_id": reservation_data["user_id"],
                "created_at": datetime.utcnow().isoformat(),
                "last_message_at": datetime.utcnow().isoformat(),
                "is_active": True
            }
            db.collection("chats").add(chat_data)
            
            # Send approval notification with tracking ID
            create_notification(
                "Request Approved! 🎉",
                f"Great news! Your request for '{item_data.get('name', 'item')}' has been approved. Tracking ID: {tracking_id}. You can now track your item and chat with the donor.",
                "reservation_approved",
                [reservation_data["user_id"]]
            )
            
            # Send tracking email
            try:
                requester_ref = db.collection("users").document(reservation_data["user_id"])
                requester_doc = requester_ref.get()
                requester_data = requester_doc.to_dict() if requester_doc.exists else {}
                
                await email_service.send_tracking_email(
                    requester_data.get("email", ""),
                    requester_data.get("full_name", "User"),
                    item_data,
                    tracking_id
                )
            except Exception as e:
                logger.error(f"Failed to send tracking email: {e}")
            
        elif status == "declined":
            # Send decline notification
            create_notification(
                "Request Declined",
                f"Unfortunately, your request for '{item_data.get('name', 'item')}' was declined. Don't worry, there are many other items available!",
                "reservation_declined",
                [reservation_data["user_id"]]
            )
        
        return ApiResponse(
            success=True,
            message=f"Reservation {status} successfully",
            data={"tracking_id": tracking_id if status == "approved" else None}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating reservation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update reservation status"
        )

async def reject_other_requests(item_id: str, approved_reservation_id: str, item_data: dict):
    """Reject all other pending requests for an item"""
    try:
        # Get all pending requests for this item (excluding the approved one)
        requests_query = db.collection("reservations").where("item_id", "==", item_id).where("status", "==", "pending")
        requests_docs = list(requests_query.stream())
        
        rejected_users = []
        
        for request_doc in requests_docs:
            if request_doc.id != approved_reservation_id:
                request_data = request_doc.to_dict()
                
                # Update status to declined
                request_doc.reference.update({
                    "status": "declined",
                    "updated_at": datetime.utcnow().isoformat()
                })
                
                # Add to rejected users list
                rejected_users.append({
                    "user_id": request_data["user_id"],
                    "user_name": request_data["user_name"],
                    "email": request_data.get("email", "")
                })
                
                # Send decline notification
                create_notification(
                    "Request Not Selected",
                    f"Your request for '{item_data.get('name', 'item')}' was not selected. The donor chose another requester. Keep looking - there are many other great items available!",
                    "reservation_declined",
                    [request_data["user_id"]]
                )
        
        logger.info(f"Rejected {len(rejected_users)} other requests for item {item_id}")
        
    except Exception as e:
        logger.error(f"Error rejecting other requests: {e}")

# Tracking Routes
@app.get("/api/v1/tracking/{tracking_id}")
async def get_tracking_info(
    tracking_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get tracking information by tracking ID"""
    try:
        # Find tracking record
        tracking_query = db.collection("tracking").where("tracking_id", "==", tracking_id)
        tracking_docs = list(tracking_query.stream())
        
        if not tracking_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking ID not found"
            )
        
        tracking_doc = tracking_docs[0]
        tracking_data = tracking_doc.to_dict()
        tracking_data["id"] = tracking_doc.id
        
        # Check if user has access to this tracking info
        if (tracking_data.get("requester_id") != current_user["uid"] and 
            tracking_data.get("donor_id") != current_user["uid"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get item details
        item_ref = db.collection("items").document(tracking_data["item_id"])
        item_doc = item_ref.get()
        if item_doc.exists:
            tracking_data["item"] = item_doc.to_dict()
        
        # Get reservation details
        reservation_ref = db.collection("reservations").document(tracking_data["reservation_id"])
        reservation_doc = reservation_ref.get()
        if reservation_doc.exists:
            tracking_data["reservation"] = reservation_doc.to_dict()
        
        # Add status definitions
        tracking_data["status_definitions"] = TRACKING_STATUSES
        
        return ApiResponse(
            success=True,
            message="Tracking information retrieved successfully",
            data=tracking_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tracking info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking information"
        )

@app.put("/api/v1/tracking/{tracking_id}/status")
async def update_tracking_status_endpoint(
    tracking_id: str,
    request: UpdateTrackingStatusRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update tracking status (donor only)"""
    try:
        # Find tracking record
        tracking_query = db.collection("tracking").where("tracking_id", "==", tracking_id)
        tracking_docs = list(tracking_query.stream())
        
        if not tracking_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking ID not found"
            )
        
        tracking_doc = tracking_docs[0]
        tracking_data = tracking_doc.to_dict()
        
        # Only donor can update tracking status
        if tracking_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the donor can update tracking status"
            )
        
        # Validate status
        if request.status not in TRACKING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tracking status"
            )
        
        # Update tracking status
        update_tracking_status(tracking_id, request.status, request.notes, current_user["uid"])
        
        return ApiResponse(
            success=True,
            message="Tracking status updated successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating tracking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tracking status"
        )

@app.get("/api/v1/user/tracking")
async def get_user_tracking(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all tracking records for current user (as requester)"""
    try:
        tracking_query = db.collection("tracking").where("requester_id", "==", current_user["uid"])
        tracking_docs = tracking_query.stream()
        
        tracking_records = []
        for doc in tracking_docs:
            tracking_data = doc.to_dict()
            tracking_data["id"] = doc.id
            
            # Get item details
            item_ref = db.collection("items").document(tracking_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                tracking_data["item"] = item_doc.to_dict()
            
            tracking_records.append(tracking_data)
        
        tracking_records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="User tracking records retrieved successfully",
            data={"tracking_records": tracking_records}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user tracking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking records"
        )

@app.get("/api/v1/donor/tracking")
async def get_donor_tracking(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all tracking records for current user (as donor)"""
    try:
        tracking_query = db.collection("tracking").where("donor_id", "==", current_user["uid"])
        tracking_docs = tracking_query.stream()
        
        tracking_records = []
        for doc in tracking_docs:
            tracking_data = doc.to_dict()
            tracking_data["id"] = doc.id
            
            # Get item details
            item_ref = db.collection("items").document(tracking_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                tracking_data["item"] = item_doc.to_dict()
            
            # Get requester details
            requester_ref = db.collection("users").document(tracking_data["requester_id"])
            requester_doc = requester_ref.get()
            if requester_doc.exists:
                tracking_data["requester"] = requester_doc.to_dict()
            
            tracking_records.append(tracking_data)
        
        tracking_records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Donor tracking records retrieved successfully",
            data={"tracking_records": tracking_records}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving donor tracking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking records"
        )

# Chat endpoints
@app.get("/api/v1/chats")
async def get_user_chats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all chats for current user"""
    try:
        # Get chats where user is either donor or requester
        donor_chats_query = db.collection("chats").where("donor_id", "==", current_user["uid"])
        requester_chats_query = db.collection("chats").where("requester_id", "==", current_user["uid"])
        
        donor_chats = list(donor_chats_query.stream())
        requester_chats = list(requester_chats_query.stream())
        
        all_chats = donor_chats + requester_chats
        
        chats = []
        for chat_doc in all_chats:
            chat_data = chat_doc.to_dict()
            chat_data["id"] = chat_doc.id
            
            # Get item details
            item_ref = db.collection("items").document(chat_data["item_id"])
            item_doc = item_ref.get()
            if item_doc.exists:
                chat_data["item"] = item_doc.to_dict()
            
            # Get other user details
            other_user_id = chat_data["donor_id"] if chat_data["requester_id"] == current_user["uid"] else chat_data["requester_id"]
            user_ref = db.collection("users").document(other_user_id)
            user_doc = user_ref.get()
            if user_doc.exists:
                chat_data["other_user"] = user_doc.to_dict()
            
            chats.append(chat_data)
        
        chats.sort(key=lambda x: x.get("last_message_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Chats retrieved successfully",
            data={"chats": chats}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chats"
        )

@app.get("/api/v1/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get messages for a specific chat"""
    try:
        # Verify user has access to this chat
        chat_ref = db.collection("chats").document(chat_id)
        chat_doc = chat_ref.get()
        
        if not chat_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        chat_data = chat_doc.to_dict()
        if current_user["uid"] not in [chat_data["donor_id"], chat_data["requester_id"]]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get messages
        messages_query = db.collection("messages").where("chat_id", "==", chat_id).order_by("created_at")
        messages_docs = messages_query.stream()
        
        messages = []
        for message_doc in messages_docs:
            message_data = message_doc.to_dict()
            message_data["id"] = message_doc.id
            messages.append(message_data)
        
        return ApiResponse(
            success=True,
            message="Messages retrieved successfully",
            data={"messages": messages}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )

@app.post("/api/v1/chats/{chat_id}/messages")
async def send_message(
    chat_id: str,
    message: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Send a message in a chat"""
    try:
        # Verify user has access to this chat
        chat_ref = db.collection("chats").document(chat_id)
        chat_doc = chat_ref.get()
        
        if not chat_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        chat_data = chat_doc.to_dict()
        if current_user["uid"] not in [chat_data["donor_id"], chat_data["requester_id"]]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Create message
        message_data = {
            "chat_id": chat_id,
            "sender_id": current_user["uid"],
            "message": message,
            "created_at": datetime.utcnow().isoformat(),
            "read": False
        }
        
        doc_ref = db.collection("messages").add(message_data)
        message_data["id"] = doc_ref[1].id
        
        # Update chat last message time
        chat_ref.update({
            "last_message_at": datetime.utcnow().isoformat(),
            "last_message": message
        })
        
        return ApiResponse(
            success=True,
            message="Message sent successfully",
            data=message_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )

# Notifications Routes
@app.get("/api/v1/notifications")
async def get_user_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user notifications"""
    try:
        # Get notifications targeted to this user or general notifications
        notifications_query = db.collection("notifications").where("target_users", "array_contains", current_user["uid"])
        notifications_docs = list(notifications_query.stream())
        
        # Also get general notifications (empty target_users)
        general_notifications_query = db.collection("notifications").where("target_users", "==", [])
        general_notifications_docs = list(general_notifications_query.stream())
        
        all_notifications = notifications_docs + general_notifications_docs
        
        notifications = []
        for doc in all_notifications:
            notification_data = doc.to_dict()
            notification_data["id"] = doc.id
            notification_data["read"] = current_user["uid"] in notification_data.get("read_by", [])
            notifications.append(notification_data)
        
        # Sort by created_at
        notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Paginate
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_notifications = notifications[start_idx:end_idx]
        
        # Count unread notifications
        unread_count = len([n for n in notifications if not n["read"]])
        
        return ApiResponse(
            success=True,
            message="Notifications retrieved successfully",
            data={
                "notifications": paginated_notifications,
                "unread_count": unread_count,
                "total": len(notifications),
                "page": page,
                "limit": limit,
                "total_pages": (len(notifications) + limit - 1) // limit
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )

@app.get("/api/v1/notifications/{notification_id}")
async def get_notification_by_id(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get notification by ID"""
    try:
        notification_ref = db.collection("notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification_data = notification_doc.to_dict()
        notification_data["id"] = notification_doc.id
        
        # Check if user has access to this notification
        target_users = notification_data.get("target_users", [])
        if target_users and current_user["uid"] not in target_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        notification_data["read"] = current_user["uid"] in notification_data.get("read_by", [])
        
        return ApiResponse(
            success=True,
            message="Notification retrieved successfully",
            data=notification_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification"
        )

@app.put("/api/v1/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark notification as read"""
    try:
        notification_ref = db.collection("notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification_data = notification_doc.to_dict()
        read_by = notification_data.get("read_by", [])
        
        if current_user["uid"] not in read_by:
            read_by.append(current_user["uid"])
            notification_ref.update({
                "read_by": read_by,
                "read_at": datetime.utcnow().isoformat()
            })
        
        return ApiResponse(
            success=True,
            message="Notification marked as read"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )

@app.put("/api/v1/notifications/read-all")
async def mark_all_notifications_read(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark all notifications as read for current user"""
    try:
        # Get all notifications for this user
        notifications_query = db.collection("notifications").where("target_users", "array_contains", current_user["uid"])
        notifications_docs = list(notifications_query.stream())
        
        # Also get general notifications
        general_notifications_query = db.collection("notifications").where("target_users", "==", [])
        general_notifications_docs = list(general_notifications_query.stream())
        
        all_notifications = notifications_docs + general_notifications_docs
        
        updated_count = 0
        for doc in all_notifications:
            notification_data = doc.to_dict()
            read_by = notification_data.get("read_by", [])
            
            if current_user["uid"] not in read_by:
                read_by.append(current_user["uid"])
                doc.reference.update({
                    "read_by": read_by,
                    "read_at": datetime.utcnow().isoformat()
                })
                updated_count += 1
        
        return ApiResponse(
            success=True,
            message=f"Marked {updated_count} notifications as read"
        )
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read"
        )

@app.delete("/api/v1/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete notification (admin only or if user is in target_users)"""
    try:
        notification_ref = db.collection("notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification_data = notification_doc.to_dict()
        
        # Check if user has permission to delete
        target_users = notification_data.get("target_users", [])
        if current_user["email"] != ADMIN_EMAIL and current_user["uid"] not in target_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
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

@app.get("/api/v1/notifications/unread-count")
async def get_unread_notifications_count(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get count of unread notifications"""
    try:
        # Get notifications targeted to this user
        notifications_query = db.collection("notifications").where("target_users", "array_contains", current_user["uid"])
        notifications_docs = list(notifications_query.stream())
        
        # Also get general notifications
        general_notifications_query = db.collection("notifications").where("target_users", "==", [])
        general_notifications_docs = list(general_notifications_query.stream())
        
        all_notifications = notifications_docs + general_notifications_docs
        
        unread_count = 0
        for doc in all_notifications:
            notification_data = doc.to_dict()
            if current_user["uid"] not in notification_data.get("read_by", []):
                unread_count += 1
        
        return ApiResponse(
            success=True,
            message="Unread count retrieved successfully",
            data={"count": unread_count}
        )
        
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count"
        )

@app.get("/api/v1/reservations/{reservation_id}")
async def get_reservation_by_id(
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get reservation by ID"""
    try:
        reservation_ref = db.collection("reservations").document(reservation_id)
        reservation_doc = reservation_ref.get()
        
        if not reservation_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )
        
        reservation_data = reservation_doc.to_dict()
        reservation_data["id"] = reservation_doc.id
        
        # Check if user has access to this reservation
        if (reservation_data.get("user_id") != current_user["uid"] and 
            reservation_data.get("donor_id") != current_user["uid"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get item details
        item_ref = db.collection("items").document(reservation_data["item_id"])
        item_doc = item_ref.get()
        if item_doc.exists:
            reservation_data["item"] = item_doc.to_dict()
        
        return ApiResponse(
            success=True,
            message="Reservation retrieved successfully",
            data=reservation_data
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reservation"
        )

@app.get("/api/v1/items/{item_id}/requests")
async def get_item_requests(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all reservation requests for an item"""
    try:
        # Verify user owns the item
        item_ref = db.collection("items").document(item_id)
        item_doc = item_ref.get()
        
        if not item_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        item_data = item_doc.to_dict()
        if item_data.get("donor_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get all requests for this item
        requests_query = db.collection("reservations").where("item_id", "==", item_id)
        requests_docs = requests_query.stream()
        
        requests = []
        for doc in requests_docs:
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Get requester details
            user_ref = db.collection("users").document(request_data["user_id"])
            user_doc = user_ref.get()
            if user_doc.exists:
                request_data["requester"] = user_doc.to_dict()
            
            requests.append(request_data)
        
        requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return ApiResponse(
            success=True,
            message="Item requests retrieved successfully",
            data={"reservations": requests}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving item requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item requests"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
