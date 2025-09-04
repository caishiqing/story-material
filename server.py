"""
FastAPI application for audio material management
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import os
from typing import List, Optional

from backend.models import (
    AudioType,
    AudioSearchParams,
    AudioMaterialCreate,
    AudioMaterialUpdate,
    AudioMaterialResponse,
    CollectionStats
)
from backend.audio_manager import AsyncAudioMaterialManager, create_audio_manager
from backend.embedding import EmbeddingService

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sink=lambda msg: print(msg, end=''),  # Console output
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Global audio manager instance
audio_manager: Optional[AsyncAudioMaterialManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    global audio_manager

    # Startup
    logger.info("Starting up audio material management API...")
    try:
        # Create embedding service with configuration
        embedding_device = os.getenv("EMBEDDING_DEVICE", "auto")
        embedding_service = EmbeddingService(
            model_path=os.getenv("EMBEDDING_MODEL_PATH", "multilingual-e5-large-instruct"),
            device=None if embedding_device == "auto" else embedding_device
        )

        # Create and initialize audio manager
        audio_manager = await create_audio_manager(
            milvus_host=os.getenv("MILVUS_HOST", "localhost"),
            milvus_port=int(os.getenv("MILVUS_PORT", "19530")),
            collection_name=os.getenv("MILVUS_COLLECTION", "story-audio"),
            embedding_service=embedding_service
        )
        logger.info("Audio manager initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize audio manager: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down audio material management API...")
        if audio_manager:
            await audio_manager.disconnect()
            logger.info("Audio manager disconnected")


# Create FastAPI application
app = FastAPI(
    title="Audio Material Management API",
    description="API for managing audio materials with semantic search and metadata",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get audio manager
async def get_audio_manager() -> AsyncAudioMaterialManager:
    """Get the global audio manager instance"""
    if audio_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio manager not initialized"
        )
    return audio_manager


# Error handling
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions"""
    logger.error(f"ValueError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid input", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "audio-material-management"}


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Audio Material Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# Audio material endpoints
@app.post(
    "/audio",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    tags=["Audio Materials"],
    summary="Add new audio material"
)
async def add_audio(
    audio_data: AudioMaterialCreate,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """
    Add a new audio material to the collection.

    - **path**: Audio file path (required)
    - **description**: Audio description (auto-generated from filename if not provided)
    - **type**: Audio effect type (required, must be one of: music, ambient, mood, action, transition)
    - **tags**: List of tags (optional)
    - **duration**: Duration in seconds (auto-detected from file if not provided)

    The system will automatically:
    - Generate description from filename if not provided
    - Detect audio duration from file if not provided
    - Validate duration based on audio type rules
    """
    try:
        audio_id = await manager.add(audio_data)
        return {
            "message": "Audio material added successfully",
            "id": audio_id,
            "path": audio_data.path
        }
    except Exception as e:
        logger.error(f"Failed to add audio material: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get(
    "/audio/{audio_id}",
    response_model=AudioMaterialResponse,
    tags=["Audio Materials"],
    summary="Get audio material by ID"
)
async def get_audio(
    audio_id: int,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """Get a specific audio material by its ID"""
    try:
        audio = await manager.get(audio_id)
        if audio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio material with ID {audio_id} not found"
            )
        return audio
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get audio material {audio_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audio material"
        )


@app.put(
    "/audio/{audio_id}",
    response_model=dict,
    tags=["Audio Materials"],
    summary="Update audio material"
)
async def update_audio(
    audio_id: int,
    update_data: AudioMaterialUpdate,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """
    Update an existing audio material.

    All fields are optional - only provided fields will be updated.
    """
    try:
        success = await manager.update(audio_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio material with ID {audio_id} not found"
            )
        return {
            "message": "Audio material updated successfully",
            "id": audio_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update audio material {audio_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.delete(
    "/audio/{audio_id}",
    response_model=dict,
    tags=["Audio Materials"],
    summary="Delete audio material"
)
async def delete_audio(
    audio_id: int,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """Delete an audio material by its ID"""
    try:
        success = await manager.delete(audio_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio material with ID {audio_id} not found"
            )
        return {
            "message": "Audio material deleted successfully",
            "id": audio_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete audio material {audio_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete audio material"
        )


@app.get(
    "/audio",
    response_model=List[AudioMaterialResponse],
    tags=["Audio Materials"],
    summary="List all audio materials"
)
async def list_audios(
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """List all audio materials in the collection"""
    try:
        audios = await manager.list()
        return audios
    except Exception as e:
        logger.error(f"Failed to list audio materials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list audio materials"
        )


@app.post(
    "/audio/search",
    response_model=List[AudioMaterialResponse],
    tags=["Search"],
    summary="Hybrid search for audio materials"
)
async def search_audios(
    search_params: AudioSearchParams,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """
    Perform hybrid search combining BM25 text search and semantic vector search.

    - **query**: Search query text (required)
    - **type**: Audio effect type filter (required)
    - **tag**: Tag filter for partial matching (optional)
    - **min_duration**: Minimum duration in seconds (optional)
    - **max_duration**: Maximum duration in seconds (optional)
    - **limit**: Maximum number of results (1-100, default: 10)

    Results are ranked by hybrid relevance combining text similarity and semantic similarity.
    """
    try:
        results = await manager.search(search_params)
        return results
    except Exception as e:
        logger.error(f"Failed to search audio materials: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get(
    "/audio/stats",
    response_model=CollectionStats,
    tags=["Statistics"],
    summary="Get collection statistics"
)
async def get_stats(
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """Get statistics about the audio materials collection"""
    try:
        stats = await manager.check()
        return stats
    except Exception as e:
        logger.error(f"Failed to get collection statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get collection statistics"
        )


# Audio types endpoint for reference
@app.get(
    "/audio/types",
    response_model=List[str],
    tags=["Reference"],
    summary="Get available audio types"
)
async def get_audio_types():
    """Get list of available audio types"""
    return [audio_type.value for audio_type in AudioType]


if __name__ == "__main__":
    import uvicorn
    import sys
    import argparse
    from dotenv import load_dotenv

    # Load environment variables as fallback
    load_dotenv()

    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Audio Material Management API Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # API server arguments
    parser.add_argument(
        "--host", "-H",
        default=os.getenv("API_HOST", "0.0.0.0"),
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.getenv("API_PORT", "8000")),
        help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload", "-r",
        action="store_true",
        default=os.getenv("API_RELOAD", "false").lower() == "true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default=os.getenv("LOG_LEVEL", "info").lower(),
        help="Log level for the server"
    )

    # Milvus configuration arguments
    parser.add_argument(
        "--milvus-host",
        default=os.getenv("MILVUS_HOST", "localhost"),
        help="Milvus server host"
    )
    parser.add_argument(
        "--milvus-port",
        type=int,
        default=int(os.getenv("MILVUS_PORT", "19530")),
        help="Milvus server port"
    )
    parser.add_argument(
        "--milvus-collection",
        default=os.getenv("MILVUS_COLLECTION", "story-audio"),
        help="Milvus collection name"
    )

    # Embedding model configuration arguments
    parser.add_argument(
        "--embedding-model-path",
        default=os.getenv("EMBEDDING_MODEL_PATH", "models/multilingual-e5-large-instruct"),
        help="Path to the sentence-transformer model (local path or model name)"
    )
    parser.add_argument(
        "--embedding-device",
        choices=["auto", "cpu", "cuda", "mps"],
        default=os.getenv("EMBEDDING_DEVICE", "auto"),
        help="Device to run the embedding model on"
    )

    # Additional options
    parser.add_argument(
        "--no-access-log",
        action="store_true",
        help="Disable access logging"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes"
    )

    # Parse arguments
    args = parser.parse_args()

    # Update environment variables with parsed arguments
    os.environ["MILVUS_HOST"] = args.milvus_host
    os.environ["MILVUS_PORT"] = str(args.milvus_port)
    os.environ["MILVUS_COLLECTION"] = args.milvus_collection
    os.environ["EMBEDDING_MODEL_PATH"] = args.embedding_model_path
    os.environ["EMBEDDING_DEVICE"] = args.embedding_device

    # Log startup information
    logger.info("Starting Audio Material Management API...")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Reload: {args.reload}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Access Log: {not args.no_access_log}")
    logger.info(f"Milvus: {args.milvus_host}:{args.milvus_port}")
    logger.info(f"Collection: {args.milvus_collection}")
    logger.info(f"Embedding Model Path: {args.embedding_model_path}")
    logger.info(f"Embedding Device: {args.embedding_device}")

    try:
        # Run the application
        uvicorn.run(
            "server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            access_log=not args.no_access_log,
            workers=args.workers if not args.reload else 1  # Workers incompatible with reload
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
