"""
FastAPI application for audio material management
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import os
import socket
import json
import time
import yaml
import socket
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import quote

from backend.models import (
    AudioType,
    AudioSearchParams,
    AudioMaterialCreate,
    AudioMaterialUpdate,
    AudioMaterialResponse,
    CollectionStats
)
from backend.audio_manager import AsyncAudioMaterialManager
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

# Configuration loading function


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded configuration from {config_path}")
        return config
    else:
        logger.warning(f"Configuration file {config_path} not found, using defaults")
        return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    global audio_manager

    # Startup
    logger.info("Starting up audio material management API...")

    # Load configuration from YAML file
    config = load_config()

    # Get embedding configuration
    embedding_config = config.get("embedding", {})
    embedding_service = EmbeddingService(
        model_path=embedding_config.get("model_path"),
        device=embedding_config.get("device")
    )

    # Get milvus configuration
    milvus_config = config.get("milvus", {})
    audio_manager = AsyncAudioMaterialManager(
        milvus_host=milvus_config.get("host"),
        milvus_port=milvus_config.get("port"),
        db_name=milvus_config.get("database"),
        collection_name=milvus_config.get("collection"),
        embedding_service=embedding_service
    )
    await audio_manager.connect()
    logger.info("Audio manager initialized successfully")

    yield


# Create FastAPI application
app = FastAPI(
    title="Sound Hub API",
    description="API for managing sound audio materials with semantic search and metadata",
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

# Mount static files for audio playback
# Ensure the data directory exists
os.makedirs("data/sound", exist_ok=True)
app.mount("/static/data", StaticFiles(directory="data"), name="static")


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
    file: UploadFile = File(...),
    audio_type: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    audio_id: Optional[str] = Form(None),
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """
    Upload and add a new audio material to the collection.

    - **file**: Audio file to upload (required)
    - **audio_type**: Audio effect type (required, must be one of: music, ambient, mood, action, transition, voice)
    - **description**: Audio description (auto-generated from filename if not provided)
    - **tags**: List of tags as JSON string (optional, e.g., '["tag1", "tag2"]')
    - **audio_id**: Custom ID for audio material (optional, auto-generated if not provided)

    The system will automatically:
    - Save file to data/sound/{type}/ directory
    - Generate description from filename if not provided
    - Detect audio duration from uploaded file
    - Validate duration based on audio type rules
    - Use audio_id as primary key if provided, otherwise auto-generate
    """
    try:
        # Validate audio type
        valid_types = [e.value for e in AudioType]
        if audio_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid audio type. Must be one of: {valid_types}"
            )

        # Validate file type (basic check by extension)
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required"
            )

        file_extension = Path(file.filename).suffix.lower()
        valid_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'}
        if file_extension not in valid_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid audio file format. Supported formats: {', '.join(valid_extensions)}"
            )

        # Create target directory structure
        base_dir = Path("data/sound")
        type_dir = base_dir / audio_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid conflicts
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = type_dir / safe_filename

        # Save uploaded file
        try:
            with open(file_path, "wb") as buffer:
                # Read file in chunks to handle large files
                while chunk := await file.read(8192):  # 8KB chunks
                    buffer.write(chunk)
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )

        # Parse tags if provided
        parsed_tags = None
        if tags:
            try:
                parsed_tags = json.loads(tags) if tags.strip() else None
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated string
                parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Prepare audio material data
        audio_data_dict = {
            "path": str(file_path),
            "type": audio_type,
            "description": description,
            "tags": parsed_tags
        }

        # Use audio_id as primary key if provided
        if audio_id:
            audio_data_dict["id"] = audio_id

        # Create audio material data using the saved file path
        audio_data = AudioMaterialCreate(**audio_data_dict)

        # Add to the collection
        audio_id = await manager.add(audio_data)

        return {
            "message": "Audio material uploaded and added successfully",
            "id": audio_id,
            "filename": file.filename,
            "path": str(file_path),
            "type": audio_type
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to add audio material: {e}")
        # Clean up file if it was saved but processing failed
        if 'file_path' in locals() and file_path.exists():
            try:
                file_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up file after error: {cleanup_error}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Specific routes first (before parameterized routes)
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


@app.get(
    "/audio/types",
    response_model=List[str],
    tags=["Reference"],
    summary="Get available audio types"
)
async def get_audio_types():
    """Get list of available audio types"""
    return [audio_type.value for audio_type in AudioType]


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


# Parameterized routes last
@app.get(
    "/audio/{audio_id}",
    response_model=AudioMaterialResponse,
    tags=["Audio Materials"],
    summary="Get audio material by ID"
)
async def get_audio(
    audio_id: str,
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
    audio_id: str,
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
    audio_id: str,
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
    "/audio/{audio_id}/download-url",
    response_model=dict,
    tags=["Audio Materials"],
    summary="Get audio download URL"
)
async def get_audio_download_url(
    audio_id: str,
    request: Request,
    manager: AsyncAudioMaterialManager = Depends(get_audio_manager)
):
    """
    Generate download URL for audio material.

    Returns a complete HTTP URL that can be used to download or stream the audio file.
    The URL includes proper encoding for Chinese characters and special characters.
    """
    try:
        audio = await manager.get(audio_id)
        if not audio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio material with ID {audio_id} not found"
            )

        # 生成完整的下载URL
        # host = os.getenv("BASE_URL", socket.gethostbyname(socket.gethostname()))
        base_url = f"{request.url.scheme}://{request.url.netloc}"

        # URL编码处理中文路径和特殊字符
        path_parts = audio.path.split('/')
        encoded_parts = [quote(part, safe='') for part in path_parts]
        encoded_path = '/'.join(encoded_parts)

        download_url = f"{base_url}/static/{encoded_path}"

        # 根据文件扩展名确定MIME类型
        file_extension = Path(audio.path).suffix.lower()
        content_type_mapping = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.wma': 'audio/x-ms-wma'
        }
        content_type = content_type_mapping.get(file_extension, 'audio/mpeg')

        return {
            "audio_id": str(audio_id),
            "download_url": download_url,
            "filename": Path(audio.path).name,
            "content_type": content_type,
            "file_size_bytes": None,  # 可以后续添加文件大小检测
            "description": audio.description,
            "duration": audio.duration
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL for audio {audio_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )


if __name__ == "__main__":
    import uvicorn
    import sys
    import argparse
    from dotenv import load_dotenv

    # Load environment variables as fallback (for backwards compatibility)
    load_dotenv()

    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Audio Material Management API Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # API server arguments
    parser.add_argument(
        "--host", "-H",
        default="0.0.0.0",
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload", "-r",
        action="store_true",
        default=False,
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default="info",
        help="Log level for the server"
    )

    # Configuration file argument
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file (for Milvus and embedding settings)"
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

    # Load configuration from file
    config = load_config(args.config)
    milvus_config = config.get("milvus", {})
    embedding_config = config.get("embedding", {})

    # Log startup information
    logger.info("Starting Audio Material Management API...")
    logger.info(f"Configuration file: {args.config}")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Reload: {args.reload}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Access Log: {not args.no_access_log}")
    logger.info(f"Milvus: {milvus_config.get('host')}:{milvus_config.get('port')}")
    logger.info(f"Database: {milvus_config.get('database')}")
    logger.info(f"Collection: {milvus_config.get('collection')}")
    logger.info(f"Embedding Model Path: {embedding_config.get('model_path')}")
    logger.info(f"Embedding Device: {embedding_config.get('device')}")

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
