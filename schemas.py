"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Core users/products kept for compatibility
class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: Optional[str] = Field(None, description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")
    is_seller: bool = Field(False, description="Whether the user can host shows")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Live Shopping (Whatnot-style) Schemas

class Show(BaseModel):
    """Live show hosted by a seller"""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: str = Field("scheduled", description="scheduled|live|ended")
    start_time: Optional[datetime] = None
    host_id: Optional[str] = Field(None, description="User id of the host")
    cover_image: Optional[str] = None

class Item(BaseModel):
    """Item to be auctioned in a show"""
    show_id: str
    title: str
    description: Optional[str] = None
    start_price: float = Field(..., ge=0)
    image_url: Optional[str] = None
    status: str = Field("ready", description="draft|ready|sold")

class Auction(BaseModel):
    show_id: str
    item_id: str
    status: str = Field("not_started", description="not_started|live|ended")
    starting_price: float = Field(..., ge=0)
    current_price: float = Field(..., ge=0)
    ends_at: Optional[datetime] = None
    highest_bid_id: Optional[str] = None

class Bid(BaseModel):
    show_id: str
    item_id: str
    auction_id: str
    user_id: str
    amount: float = Field(..., gt=0)

class Message(BaseModel):
    show_id: str
    user_id: Optional[str] = None
    text: str
    type: str = Field("text", description="text|system")
