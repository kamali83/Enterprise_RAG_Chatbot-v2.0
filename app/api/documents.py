"""
Document management API routes
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
import os
import shutil
from datetime import datetime
from app.api.auth import get_current_user
from app.models.schemas import DocumentResponse, DocumentUploadResponse
from app.models.db_models import User
from app.core.config import settings
from app.core.logging import get_logger
from app.services.rag_service import get_rag_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])

DOCS_DIR = settings.DOCS_DIR


def validate_file(file: UploadFile) -> bool:
    """Validate file type and size."""
    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    
    return True


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
):
    """List all uploaded documents."""
    if not os.path.exists(DOCS_DIR):
        return []
    
    documents = []
    for filename in os.listdir(DOCS_DIR):
        file_path = os.path.join(DOCS_DIR, filename)
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            documents.append({
                "id": hash(filename) % 1000000,  # Temporary ID
                "filename": filename,
                "file_type": ext,
                "file_size": os.path.getsize(file_path),
                "uploaded_by": current_user.id,
                "uploaded_at": datetime.fromtimestamp(os.path.getctime(file_path)),
                "is_indexed": os.path.exists("faiss_index/index.faiss"),
            })
    
    return documents


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a new document."""
    # Validate file
    validate_file(file)
    
    # Create docs directory if it doesn't exist
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    file_path = os.path.join(DOCS_DIR, file.filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="File already exists")
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        file_size = len(content)
        
        # Reindex vector store
        reindex_status = "pending"
        try:
            from app.services.document_service import reindex_documents
            await reindex_documents()
            reindex_status = "indexed"
        except Exception as e:
            logger.error(f"Reindexing failed: {e}")
            reindex_status = "failed"
        
        logger.info(f"Document uploaded: {file.filename} by user {current_user.username}")
        
        return DocumentUploadResponse(
            filename=file.filename,
            file_size=file_size,
            status="uploaded",
            reindex_status=reindex_status,
        )
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")


@router.delete("/{filename}", status_code=200)
async def delete_document(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a document."""
    file_path = os.path.join(DOCS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(file_path)
        
        # Reindex vector store
        reindex_status = "pending"
        try:
            from app.services.document_service import reindex_documents
            await reindex_documents()
            reindex_status = "indexed"
        except Exception as e:
            logger.error(f"Reindexing failed: {e}")
            reindex_status = "failed"
        
        logger.info(f"Document deleted: {filename} by user {current_user.username}")
        
        return {
            "filename": filename,
            "status": "deleted",
            "reindex_status": reindex_status,
        }
    
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


@router.post("/reindex", status_code=200)
async def reindex(
    current_user: User = Depends(get_current_user),
):
    """Manually trigger reindexing of all documents."""
    try:
        from app.services.document_service import reindex_documents
        await reindex_documents()
        
        logger.info(f"Manual reindex triggered by user {current_user.username}")
        
        return {
            "status": "success",
            "message": "Documents reindexed successfully",
        }
    
    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {str(e)}")
