from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr

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
    phoneNumber: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None

class UpdatePreferencesRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications: Optional[Dict[str, bool]] = None

class VerifyTokenRequest(BaseModel):
    uid: str

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