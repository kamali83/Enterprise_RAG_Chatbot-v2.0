from fastapi import FastAPI, Depends, HTTPException, Header, Form, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, StreamingResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional, AsyncGenerator
import json
import os
import asyncio
import queue
import threading

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DATABASE_URL
from retriever import get_retriever, get_document_sources
from generator import generate_answer, generate_answer_stream, tokenizer, model
from sqlalchemy import create_engine, Session
from models import Base, User, Conversation, Message

# ---------------- No-cache Middleware for Frontend ----------------
class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/frontend"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

# ---------------- Database Setup ----------------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

# ---------------- FastAPI ----------------
app = FastAPI()
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=False)
retriever = get_retriever()

# ---------------- JWT ----------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------- User Endpoints ----------------
@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Check if user exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = pwd_context.hash(password)
    new_user = User(username=username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"msg": "User created", "user_id": new_user.id}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    is_valid = pwd_context.verify(password, user.hashed_password)

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": username})
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}

# ---------------- Chat API ----------------
def get_current_user(token: str = Header(...), db: Session = Depends(get_db)):
    username = verify_token(token)
    return db.query(User).filter(User.username == username).first()

@app.get("/ask")
def ask_question(query: str, current_user: User = Depends(get_current_user)):
    docs = retriever.invoke(query)
    context = "\n".join([doc.page_content for doc in docs])
    answer = generate_answer(query, context)
    sources = get_document_sources(docs)
    return {"answer": answer, "sources": sources}


# ---------------- Conversation Management ----------------
@app.post("/conversations")
def create_conversation(name: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = Conversation(user_id=current_user.id, name=name)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "name": conv.name, "created_at": str(conv.created_at)}

@app.get("/conversations")
def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.created_at.desc()).all()
    return [{"id": c.id, "name": c.name, "created_at": str(c.created_at)} for c in convs]

@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"msg": "Deleted"}

@app.put("/conversations/{conv_id}")
def rename_conversation(conv_id: int, name: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.name = name
    db.commit()
    return {"id": conv.id, "name": conv.name}

@app.post("/messages")
def add_message(conversation_id: int, sender: str = Form(...), content: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify conversation belongs to user
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = Message(conversation_id=conversation_id, sender=sender, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "sender": msg.sender, "content": msg.content, "timestamp": str(msg.timestamp)}

@app.get("/messages/{conversation_id}")
def get_messages(conversation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.timestamp.asc()).all()
    return [{"id": m.id, "sender": m.sender, "content": m.content, "timestamp": str(m.timestamp)} for m in msgs]


# ---------------- Document Management ----------------
DOCS_DIR = "data/docs"

@app.get("/documents")
def list_documents(current_user: User = Depends(get_current_user)):
    """List all documents in the docs directory."""
    if not os.path.exists(DOCS_DIR):
        return {"documents": []}

    docs = []
    for filename in os.listdir(DOCS_DIR):
        file_path = os.path.join(DOCS_DIR, filename)
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            docs.append({
                "filename": filename,
                "size": os.path.getsize(file_path),
                "type": ext,
                "indexed": os.path.exists("faiss_index/index.faiss")
            })
    return {"documents": docs}

@app.post("/documents")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Upload a new document to the docs directory."""
    allowed_extensions = {".txt", ".pdf", ".docx", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed_extensions}")

    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)

    file_path = os.path.join(DOCS_DIR, file.filename)

    # Check if file already exists
    if os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="File already exists")

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Auto-reindex
    try:
        from ingest import create_vector_store
        create_vector_store()
        reindex_status = "indexed"
    except Exception as e:
        reindex_status = "pending"

    return {
        "filename": file.filename,
        "size": len(content),
        "status": "uploaded",
        "reindex_status": reindex_status
    }

@app.delete("/documents/{filename}")
def delete_document(filename: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a document from the docs directory."""
    file_path = os.path.join(DOCS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(file_path)

    # Auto-reindex after deletion
    try:
        from ingest import create_vector_store
        create_vector_store()
        reindex_status = "indexed"
    except Exception as e:
        reindex_status = "pending"

    return {
        "filename": filename,
        "status": "deleted",
        "reindex_status": reindex_status
    }


async def stream_generator(query: str, context: str) -> AsyncGenerator[str, None]:
    """Generate SSE stream for response tokens."""
    # Use a queue to collect tokens from the streamer
    token_queue = queue.Queue()
    done_event = threading.Event()

    def run_generation():
        try:
            # Create a custom streamer that puts tokens in our queue
            from transformers import TextStreamer

            class QueueStreamer(TextStreamer):
                def put(self, token):
                    if token is not None:
                        token_queue.put_nowait(token)

            streamer = QueueStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

            device = model.device
            prompt = f"""
Answer the question based on the context provided.
Context: {context}
Question: {query}
Answer:"""
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=768).to(device)

            model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=150,
                min_new_tokens=5,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=2.0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                streamer=streamer
            )
        finally:
            done_event.set()

    thread = threading.Thread(target=run_generation)
    thread.start()

    while not done_event.is_set() or not token_queue.empty():
        try:
            token = token_queue.get(timeout=0.5)
            yield f"data: {token}\n\n"
            await asyncio.sleep(0.02)
        except queue.Empty:
            continue

    thread.join()
    yield "data: [DONE]\n\n"


@app.get("/ask_stream")
async def ask_question_stream(query: str, current_user: str = Depends(get_current_user)):
    """Streaming endpoint - returns answer token by token via SSE."""
    docs = retriever.invoke(query)
    context = "\n".join([doc.page_content for doc in docs])

    return StreamingResponse(
        stream_generator(query, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )