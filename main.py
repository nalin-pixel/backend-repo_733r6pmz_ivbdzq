import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else ("✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set")
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# ----------------------------
# Live Shopping API (MVP)
# ----------------------------
from schemas import Show, Item, Auction, Bid, Message
from bson import ObjectId


def oid(id_str: str):
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


@app.post("/shows")
def create_show(show: Show):
    show_dict = show.model_dump()
    show_id = create_document("show", show_dict)
    return {"id": show_id, **show_dict}


@app.get("/shows")
def list_shows(status: Optional[str] = None, limit: int = 20):
    filt: Dict[str, Any] = {}
    if status:
        filt["status"] = status
    docs = get_documents("show", filt, limit)
    # Convert ObjectId to string
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.post("/items")
def create_item(item: Item):
    item_dict = item.model_dump()
    item_id = create_document("item", item_dict)
    return {"id": item_id, **item_dict}


@app.get("/shows/{show_id}/items")
def list_items(show_id: str, limit: int = 50):
    docs = get_documents("item", {"show_id": show_id}, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


class StartAuctionRequest(BaseModel):
    item_id: str
    starting_price: float
    duration_seconds: int = 60


@app.post("/shows/{show_id}/auctions/start")
def start_auction(show_id: str, payload: StartAuctionRequest):
    # End any existing live auction for this show
    db["auction"].update_many({"show_id": show_id, "status": "live"}, {"$set": {"status": "ended"}})

    ends_at = datetime.now(timezone.utc) + timedelta(seconds=payload.duration_seconds)
    auction = Auction(
        show_id=show_id,
        item_id=payload.item_id,
        status="live",
        starting_price=payload.starting_price,
        current_price=payload.starting_price,
        ends_at=ends_at,
        highest_bid_id=None,
    ).model_dump()

    auction_id = create_document("auction", auction)
    return {"id": auction_id, **auction}


@app.get("/shows/{show_id}/auctions/current")
def current_auction(show_id: str):
    docs = list(db["auction"].find({"show_id": show_id, "status": "live"}).limit(1))
    if not docs:
        return {"auction": None}
    a = docs[0]
    a["id"] = str(a.pop("_id"))
    return {"auction": a}


class PlaceBidRequest(BaseModel):
    user_id: str
    amount: float


@app.post("/auctions/{auction_id}/bids")
def place_bid(auction_id: str, payload: PlaceBidRequest):
    a = db["auction"].find_one({"_id": oid(auction_id)})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("status") != "live":
        raise HTTPException(status_code=400, detail="Auction not live")

    min_required = max(a.get("starting_price", 0), a.get("current_price", 0))
    if payload.amount <= min_required:
        raise HTTPException(status_code=400, detail=f"Bid must be greater than {min_required}")

    bid = Bid(
        show_id=a["show_id"],
        item_id=a["item_id"],
        auction_id=auction_id,
        user_id=payload.user_id,
        amount=payload.amount,
    ).model_dump()
    bid_id = create_document("bid", bid)

    # Update auction
    db["auction"].update_one({"_id": oid(auction_id)}, {"$set": {"current_price": payload.amount, "highest_bid_id": bid_id}})

    # Optional anti-snipe: extend if < 10s remaining
    if a.get("ends_at"):
        now = datetime.now(timezone.utc)
        remaining = a["ends_at"] - now
        if remaining.total_seconds() < 10:
            new_end = now + timedelta(seconds=10)
            db["auction"].update_one({"_id": oid(auction_id)}, {"$set": {"ends_at": new_end}})

    return {"id": bid_id, **bid}


@app.get("/auctions/{auction_id}/bids")
def list_bids(auction_id: str, limit: int = 50):
    docs = get_documents("bid", {"auction_id": auction_id}, limit)
    # Sort highest first
    docs.sort(key=lambda x: x.get("amount", 0), reverse=True)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


class MessageRequest(BaseModel):
    user_id: Optional[str] = None
    text: str


@app.post("/shows/{show_id}/messages")
def post_message(show_id: str, payload: MessageRequest):
    msg = Message(show_id=show_id, user_id=payload.user_id, text=payload.text).model_dump()
    msg_id = create_document("message", msg)
    return {"id": msg_id, **msg}


@app.get("/shows/{show_id}/messages")
def list_messages(show_id: str, limit: int = 50):
    docs = get_documents("message", {"show_id": show_id}, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    # Order newest last
    docs.sort(key=lambda x: x.get("created_at"))
    return docs


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
