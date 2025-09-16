"""
Data models for audio material management system
Redesigned with inheritance to eliminate redundancy
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import numpy as np
from loguru import logger
import re
import os


class AudioType(str, Enum):
    """Enumeration of audio effect types"""
    MUSIC = "music"
    AMBIENT = "ambient"
    MOOD = "mood"
    ACTION = "action"
    TRANSITION = "transition"


class AudioSearchParams(BaseModel):
    """Search parameters for hybrid audio search"""

    query: str = Field(..., min_length=1, description="Query text for search (required)")
    type: AudioType = Field(..., description="Audio effect type filter (required)")
    tag: Optional[str] = Field(None, min_length=1, description="Tag filter - partial match")
    min_duration: Optional[int] = Field(None, gt=0, description="Minimum duration in seconds")
    max_duration: Optional[int] = Field(None, gt=0, description="Maximum duration in seconds")
    limit: int = Field(10, gt=0, le=100, description="Maximum number of results to return")

    @field_validator('tag')
    def validate_tag(cls, v):
        """Validate and clean tag filter"""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode='after')
    def validate_duration_range(self):
        """Validate duration range"""
        if (self.min_duration is not None and
            self.max_duration is not None and
                self.min_duration > self.max_duration):
            raise ValueError("min_duration cannot be greater than max_duration")
        return self


class AudioMaterialBase(BaseModel):
    """Base class for all audio material models with common fields and validators"""

    # Common fields (inherited by all subclasses)
    path: Optional[str] = Field(None, min_length=1, max_length=512, description="Audio file path")
    description: Optional[str] = Field(None, min_length=1, max_length=2048, description="Audio description")
    type: Optional[str] = Field(None, min_length=1, max_length=128, description="Audio effect type")
    tags: Optional[List[str]] = Field(None, description="Audio effect tags")
    duration: Optional[int] = Field(None, gt=0, description="Audio duration in seconds")

    # Common validators (defined once and inherited by all subclasses)
    @field_validator('tags')
    def validate_tags(cls, v):
        """Validate tags field"""
        if v is not None:
            # Remove empty strings and duplicates
            v = list(set([tag.strip() for tag in v if tag.strip()]))
            # Limit tag count
            if len(v) > 50:
                raise ValueError("Maximum 50 tags allowed")
            # Limit tag length
            for tag in v:
                if len(tag) > 64:
                    raise ValueError("Tag length cannot exceed 64 characters")
        return v

    @field_validator('path')
    def validate_path(cls, v):
        """Validate path field"""
        if v is not None and not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip() if v else v

    @field_validator('description')
    def validate_description(cls, v):
        """Validate description field"""
        if v is not None and not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip() if v else v

    @field_validator('type')
    def validate_type(cls, v):
        """Validate type field"""
        if v is not None and not v.strip():
            raise ValueError("Type cannot be empty")
        return v.strip() if v else v

    class Config:
        """Common Pydantic config for all audio models"""
        json_encoders = {
            np.ndarray: lambda v: v.tolist() if isinstance(v, np.ndarray) else v
        }
        arbitrary_types_allowed = True


class AudioMaterialCreate(AudioMaterialBase):
    """Audio material creation model - only user-provided fields (no auto-generated)"""

    # Override required fields (make them required)
    path: str = Field(..., min_length=1, max_length=512, description="Audio file path")
    description: Optional[str] = Field(None, min_length=1, max_length=2048,
                                       description="Audio description (auto-generated from filename if not provided)")
    type: str = Field(..., min_length=1, max_length=128, description="Audio effect type")
    # tags and duration inherit from base class (optional)

    @model_validator(mode='after')
    def auto_initialize_fields(self):
        """Auto-initialize description and duration if not provided"""
        # Using global loguru logger

        # Auto-generate description from filename if not provided
        if self.description is None:
            logger.info(f"Auto-generating description from filename: {self.path}")
            self.description = self._generate_description_from_filename(self.path)
            logger.info(f"Generated description: {self.description}")

        # Auto-detect duration if not provided
        if self.duration is None:
            logger.info(f"Auto-detecting duration for: {self.path}")

            # Import here to avoid potential circular imports
            from .audio_utils import get_audio_duration

            duration = get_audio_duration(self.path)
            if duration is None:
                raise ValueError(f"Unable to parse audio file duration: {self.path}")

            logger.info(f"Detected duration: {duration} seconds")
            self.duration = duration

        return self

    @model_validator(mode='after')
    def validate_duration_by_type(self):
        """Validate duration based on audio effect type"""
        if self.duration is None or self.type is None:
            return self  # Skip validation if duration or type is not set

        duration = self.duration
        audio_type = self.type.lower()

        # Define duration requirements for each audio type
        duration_rules = {
            'action': {
                'min': 1,
                'max': 10,
                'description': 'Action sound effects must be between 1-10 seconds'
            },
            'transition': {
                'min': 1,
                'max': 10,
                'description': 'Transition sound effects must be between 1-10 seconds'
            },
            'ambient': {
                'min': 60,
                'max': None,
                'description': 'Ambient sound effects must be longer than 60 seconds'
            },
            'music': {
                'min': 60,
                'max': None,
                'description': 'Music must be longer than 60 seconds'
            },
            'mood': {
                'min': 30,
                'max': None,
                'description': 'Mood sound effects must be longer than 30 seconds'
            }
        }

        if audio_type in duration_rules:
            rules = duration_rules[audio_type]

            # Check minimum duration
            if duration <= rules['min']:
                raise ValueError(f"{rules['description']}, got {duration} seconds")

            # Check maximum duration if specified
            if rules['max'] is not None and duration >= rules['max']:
                raise ValueError(f"{rules['description']}, got {duration} seconds")

        return self

    def _generate_description_from_filename(self, file_path: str) -> str:
        """
        Generate description from audio filename

        Rules:
        1. Extract filename without extension
        2. Convert English to lowercase (keep Chinese unchanged)
        3. Replace punctuation with spaces
        4. Remove numbers
        5. Clean up extra spaces

        Args:
            file_path: Path to the audio file

        Returns:
            Generated description string
        """
        # Extract filename without extension
        filename = os.path.splitext(os.path.basename(file_path))[0]

        # Convert English letters to lowercase while preserving Chinese characters
        description = filename.lower()

        # Remove numbers first
        description = re.sub(r'\d+', '', description)

        # Replace punctuation and special characters with spaces
        # Keep Chinese characters (\u4e00-\u9fff), English letters (a-z), and spaces
        # Replace everything else with spaces
        description = re.sub(r'[^\u4e00-\u9fffa-z\s]', ' ', description)

        # Clean up multiple spaces and strip
        description = re.sub(r'\s+', ' ', description).strip()

        # Ensure we have a valid description
        if not description:
            description = "audio material"

        return description.strip().lower()


class AudioMaterialUpdate(AudioMaterialBase):
    """Audio material update model - all fields optional for partial updates"""

    # All fields are inherited from base class as optional - perfect for updates!
    pass


class AudioMaterial(AudioMaterialBase):
    """Complete audio material model including all fields (internal use)"""

    # Additional fields specific to this model
    id: Optional[int] = Field(None, description="Audio material ID (auto-generated)")
    vector: Optional[List[float]] = Field(None, description="Vector embedding (auto-generated)")

    # Override required fields
    path: str = Field(..., min_length=1, max_length=512, description="Audio file path")
    description: str = Field(..., min_length=1, max_length=2048, description="Audio description")
    type: str = Field(..., min_length=1, max_length=128, description="Audio effect type")
    duration: int = Field(..., gt=0, description="Audio duration in seconds")
    # tags inherit from base class (optional)

    @classmethod
    def from_create_data(
        cls,
        create_data: AudioMaterialCreate,
        vector: Optional[List[float]] = None,
        audio_id: Optional[int] = None
    ) -> 'AudioMaterial':
        """Create AudioMaterial from AudioMaterialCreate data"""
        return cls(
            id=audio_id,
            path=create_data.path,
            description=create_data.description,
            type=create_data.type,
            tags=create_data.tags,
            duration=create_data.duration,
            vector=vector
        )


class AudioMaterialResponse(AudioMaterialBase):
    """Audio material response model - for API responses (no vector field)"""

    # Additional field specific to response
    id: int = Field(..., description="Audio material ID")

    # Override required fields
    path: str = Field(..., min_length=1, max_length=512, description="Audio file path")
    description: str = Field(..., min_length=1, max_length=2048, description="Audio description")
    type: str = Field(..., min_length=1, max_length=128, description="Audio effect type")
    duration: int = Field(..., gt=0, description="Audio duration in seconds")
    # tags inherit from base class (optional)

    @classmethod
    def from_milvus_result(cls, result: Dict[str, Any]) -> 'AudioMaterialResponse':
        """Create AudioMaterialResponse from Milvus query result"""
        return cls(
            id=result.get('id'),
            path=result.get('path'),
            description=result.get('description'),
            type=result.get('type'),
            tags=result.get('tag'),  # Milvus uses 'tag' as field name
            duration=result.get('duration')
        )

    @classmethod
    def from_audio_material(cls, audio: AudioMaterial) -> 'AudioMaterialResponse':
        """Create AudioMaterialResponse from AudioMaterial"""
        return cls(
            id=audio.id,
            path=audio.path,
            description=audio.description,
            type=audio.type,
            tags=audio.tags,
            duration=audio.duration
        )


class CollectionStats(BaseModel):
    """Collection statistics model"""

    collection_name: str = Field(..., description="Collection name")
    total_count: int = Field(..., description="Total number of entities")
    type_counts: Dict[str, int] = Field(..., description="Count by audio type")
    schema: Dict[str, Dict[str, Any]] = Field(..., description="Schema information")


# Utility functions for model conversion
def merge_update_data(
    existing: AudioMaterialResponse,
    update_data: AudioMaterialUpdate
) -> AudioMaterial:
    """Merge update data with existing audio material data"""
    return AudioMaterial(
        id=existing.id,
        path=update_data.path if update_data.path is not None else existing.path,
        description=update_data.description if update_data.description is not None else existing.description,
        type=update_data.type if update_data.type is not None else existing.type,
        tags=update_data.tags if update_data.tags is not None else existing.tags,
        duration=update_data.duration if update_data.duration is not None else existing.duration,
        vector=None  # Will be regenerated if description changed
    )


# Export all models for easy importing
__all__ = [
    'AudioType',
    'AudioSearchParams',
    'AudioMaterialBase',
    'AudioMaterialCreate',
    'AudioMaterialUpdate',
    'AudioMaterial',
    'AudioMaterialResponse',
    'CollectionStats',
    'merge_update_data'
]
