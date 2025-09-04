"""
Async Audio material management system using Milvus database
"""

import os
from loguru import logger
import asyncio
from typing import List, Dict, Optional, Any, Union
from pymilvus import AsyncMilvusClient, CollectionSchema, FieldSchema, DataType, Function, FunctionType
import numpy as np
from .embedding import EmbeddingService
from .models import (
    AudioType,
    AudioSearchParams,
    AudioMaterial,
    AudioMaterialCreate,
    AudioMaterialUpdate,
    AudioMaterialResponse,
    CollectionStats,
    merge_update_data
)
from .audio_utils import get_audio_info, suggest_audio_type_from_path
from pydantic import ValidationError


class AsyncAudioMaterialManager:
    """
    Async Audio material management system with Milvus database backend
    """

    def __init__(
        self,
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        collection_name: str = "story-audio",
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize the async audio material manager

        Args:
            milvus_host: Milvus server host
            milvus_port: Milvus server port
            collection_name: Name of the collection to manage
            embedding_service: EmbeddingService instance for vector generation
        """
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.milvus_uri = f"http://{milvus_host}:{milvus_port}"
        self.collection_name = collection_name
        self.embedding_service = embedding_service or EmbeddingService()

        # Setup logging (using loguru global logger)
        # No need to create instance logger, use global logger

        # Initialize async client (will be set in connect())
        self.client: Optional[AsyncMilvusClient] = None
        self._initialized = False

    async def connect(self):
        """Connect to Milvus server and initialize collection"""
        if self._initialized:
            return

        try:
            # Create async client
            self.client = AsyncMilvusClient(uri=self.milvus_uri)
            logger.info(f"Connected to Milvus at {self.milvus_uri}")

            # Initialize collection
            await self._init_collection()
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {str(e)}")
            raise

    async def _init_collection(self):
        """Initialize or load the audio collection"""
        try:
            # Check if collection exists
            if await self.client.has_collection(collection_name=self.collection_name):
                logger.info(f"Collection '{self.collection_name}' already exists")
            else:
                await self._create_collection()
                logger.info(f"Created new collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize collection: {str(e)}")
            raise

    async def _create_collection(self):
        """Create the audio collection with defined schema"""
        try:
            # Define fields
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True
                ),
                FieldSchema(
                    name="path",
                    dtype=DataType.VARCHAR,
                    max_length=512,
                    description="Audio file path"
                ),
                FieldSchema(
                    name="description",
                    dtype=DataType.VARCHAR,
                    max_length=2048,
                    enable_analyzer=True,
                    description="Audio description for BM25 indexing"
                ),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=1024,
                    description="Vector embedding of the audio description"
                ),
                FieldSchema(
                    name="sparse_vector",
                    dtype=DataType.SPARSE_FLOAT_VECTOR,
                    description="Sparse vector for BM25 full-text search"
                ),
                FieldSchema(
                    name="type",
                    dtype=DataType.VARCHAR,
                    max_length=128,
                    description="Audio effect type"
                ),
                FieldSchema(
                    name="tag",
                    dtype=DataType.ARRAY,
                    element_type=DataType.VARCHAR,
                    max_capacity=50,
                    max_length=64,
                    nullable=True,
                    description="Audio effect tags (nullable)"
                ),
                FieldSchema(
                    name="duration",
                    dtype=DataType.INT64,
                    description="Audio duration in seconds"
                )
            ]

            # Define BM25 function for full-text search
            bm25_function = Function(
                name="description_bm25_emb",
                input_field_names=["description"],
                output_field_names=["sparse_vector"],
                function_type=FunctionType.BM25,
            )

            # Create collection schema
            schema = CollectionSchema(
                fields=fields,
                description="Story audio material collection"
            )

            # Add BM25 function to schema
            schema.add_function(bm25_function)

            # Create collection using async client
            await self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema
            )

            # Create index for dense vector field
            dense_index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }

            await self.client.create_index(
                collection_name=self.collection_name,
                field_name="vector",
                index_params=dense_index_params
            )

            # Create index for sparse vector field (BM25)
            sparse_index_params = {
                "metric_type": "BM25",
                "index_type": "SPARSE_INVERTED_INDEX",
                "params": {}
            }

            await self.client.create_index(
                collection_name=self.collection_name,
                field_name="sparse_vector",
                index_params=sparse_index_params
            )

        except Exception as e:
            logger.error(f"Failed to create collection: {str(e)}")
            raise

    async def add(
        self,
        audio_data: Union[AudioMaterialCreate, dict]
    ) -> str:
        """
        Add a new audio material to the collection

        Args:
            audio_data: AudioMaterialCreate instance or dictionary with audio data

        Returns:
            ID of the inserted record
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Convert dict to AudioMaterialCreate if needed (duration auto-detected in model)
            if isinstance(audio_data, dict):
                audio_data = AudioMaterialCreate(**audio_data)

            # Generate vector embedding from description
            vector = self.embedding_service.encode(audio_data.description)

            # Prepare data for Milvus insertion
            data = [{
                "path": audio_data.path,
                "description": audio_data.description,
                "vector": vector.tolist(),
                "type": audio_data.type,
                "tag": audio_data.tags,
                "duration": audio_data.duration
            }]

            # Insert data
            result = await self.client.insert(
                collection_name=self.collection_name,
                data=data
            )

            inserted_id = result['insert_count']  # AsyncMilvusClient returns different format
            logger.info(f"Successfully added audio material: {audio_data.path} (ID: {inserted_id})")

            return str(inserted_id)

        except ValidationError as e:
            logger.error(f"Invalid audio data: {str(e)}")
            raise ValueError(f"Invalid audio data: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to add audio material: {str(e)}")
            raise

    async def delete(self, audio_id: Union[str, int]) -> bool:
        """
        Delete an audio material by ID

        Args:
            audio_id: ID of the audio to delete

        Returns:
            True if deletion was successful
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Convert to int if string
            if isinstance(audio_id, str):
                audio_id = int(audio_id)

            # Delete by primary key
            expr = f"id == {audio_id}"
            result = await self.client.delete(
                collection_name=self.collection_name,
                filter=expr
            )

            if result['delete_count'] > 0:
                logger.info(f"Successfully deleted audio material with ID: {audio_id}")
                return True
            else:
                logger.warning(f"No audio material found with ID: {audio_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete audio material: {str(e)}")
            raise

    async def update(
        self,
        audio_id: Union[str, int],
        update_data: Union[AudioMaterialUpdate, dict]
    ) -> bool:
        """
        Update an existing audio material

        Args:
            audio_id: ID of the audio to update
            update_data: AudioMaterialUpdate instance or dictionary with fields to update

        Returns:
            True if update was successful
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Validate and convert input data
            if isinstance(update_data, dict):
                update_data = AudioMaterialUpdate(**update_data)

            # Convert to int if string
            if isinstance(audio_id, str):
                audio_id = int(audio_id)

            # First, get the existing record
            expr = f"id == {audio_id}"

            existing_records = await self.client.query(
                collection_name=self.collection_name,
                filter=expr,
                output_fields=["id", "path", "description", "type", "tag", "duration"]
            )

            if not existing_records:
                logger.warning(f"No audio material found with ID: {audio_id}")
                return False

            # Convert existing record to response model
            existing_audio = AudioMaterialResponse.from_milvus_result(existing_records[0])

            # Merge update data with existing data using utility function
            merged_audio = merge_update_data(existing_audio, update_data)

            # Generate new vector if description changed
            if update_data.description is not None:
                vector = self.embedding_service.encode(merged_audio.description)
                merged_audio.vector = vector.tolist()
            else:
                # Get existing vector
                vector_records = await self.client.query(
                    collection_name=self.collection_name,
                    filter=expr,
                    output_fields=["vector"]
                )
                merged_audio.vector = vector_records[0]["vector"]

            # Delete old record
            await self.client.delete(
                collection_name=self.collection_name,
                filter=expr
            )

            # Prepare data for insertion
            insert_data = [{
                "path": merged_audio.path,
                "description": merged_audio.description,
                "vector": merged_audio.vector,
                "type": merged_audio.type,
                "tag": merged_audio.tags,
                "duration": merged_audio.duration
            }]

            # Insert updated record
            await self.client.insert(
                collection_name=self.collection_name,
                data=insert_data
            )

            logger.info(f"Successfully updated audio material with ID: {audio_id}")
            return True

        except ValidationError as e:
            logger.error(f"Invalid update data: {str(e)}")
            raise ValueError(f"Invalid update data: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to update audio material: {str(e)}")
            raise

    async def get(self, audio_id: Union[str, int]) -> Optional[AudioMaterialResponse]:
        """
        Get audio material by ID

        Args:
            audio_id: ID of the audio to retrieve

        Returns:
            AudioMaterialResponse instance or None if not found
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Convert to int if string
            if isinstance(audio_id, str):
                audio_id = int(audio_id)

            expr = f"id == {audio_id}"

            records = await self.client.query(
                collection_name=self.collection_name,
                filter=expr,
                output_fields=["id", "path", "description", "type", "tag", "duration"]
            )

            if records:
                return AudioMaterialResponse.from_milvus_result(records[0])
            else:
                logger.warning(f"No audio material found with ID: {audio_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to get audio material: {str(e)}")
            raise

    async def list(self) -> List[AudioMaterialResponse]:
        """
        List all audio materials

        Returns:
            List of AudioMaterialResponse instances
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            records = await self.client.query(
                collection_name=self.collection_name,
                filter="",  # Empty filter to get all records
                output_fields=["id", "path", "description", "type", "tag", "duration"]
            )

            return [AudioMaterialResponse.from_milvus_result(record) for record in records]

        except Exception as e:
            logger.error(f"Failed to list audio materials: {str(e)}")
            raise

    async def check(self) -> CollectionStats:
        """
        Check collection statistics

        Returns:
            CollectionStats instance
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Get collection info
            collection_info = await self.client.describe_collection(
                collection_name=self.collection_name
            )

            # Get entity count
            stats_result = await self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["count(*)"]
            )

            total_entities = len(stats_result) if stats_result else 0

            # Build schema info
            schema_info = {}
            for field in collection_info['fields']:
                schema_info[field['name']] = {
                    "type": field['type'],
                    "description": field.get('description', '')
                }

            return CollectionStats(
                collection_name=self.collection_name,
                total_entities=total_entities,
                schema=schema_info
            )
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            raise

    async def search(
        self,
        search_params: Union[AudioSearchParams, dict]
    ) -> List[AudioMaterialResponse]:
        """
        Perform hybrid search with BM25 and semantic vector search

        Args:
            search_params: AudioSearchParams instance or dictionary with search parameters

        Returns:
            List of AudioMaterialResponse instances ranked by hybrid relevance
        """
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()

            # Validate and convert input data
            if isinstance(search_params, dict):
                search_params = AudioSearchParams(**search_params)

            # Build filter expression
            filter_expr = self._build_filter_expression(search_params)
            logger.info(f"Filter expression: {filter_expr}")

            # Generate dense vector for semantic search
            query_vector = self.embedding_service.encode(search_params.query)

            # Perform hybrid search using AsyncMilvusClient
            search_results = await self.client.search(
                collection_name=self.collection_name,
                data=[search_params.query, query_vector.tolist()],  # Text and vector for hybrid search
                anns_field=["sparse_vector", "vector"],  # Search both fields
                limit=search_params.limit,
                filter=filter_expr,  # Apply filtering
                output_fields=["id", "path", "description", "type", "tag", "duration"],
                search_params={
                    "sparse": {"params": {"drop_ratio_search": 0.2}},
                    "dense": {"params": {"nprobe": 10}}
                }
            )

            # Convert results to AudioMaterialResponse
            responses = []
            if search_results:
                # Process search results
                for result_group in search_results:
                    for hit in result_group:
                        # Extract entity data
                        entity_data = hit.get('entity', {})
                        result_dict = {
                            'id': hit.get('id'),
                            'path': entity_data.get('path'),
                            'description': entity_data.get('description'),
                            'type': entity_data.get('type'),
                            'tag': entity_data.get('tag'),
                            'duration': entity_data.get('duration')
                        }
                        responses.append(AudioMaterialResponse.from_milvus_result(result_dict))

            # Remove duplicates and limit results
            seen_ids = set()
            unique_responses = []
            for response in responses:
                if response.id not in seen_ids:
                    seen_ids.add(response.id)
                    unique_responses.append(response)

            final_responses = unique_responses[:search_params.limit]

            logger.info(f"Hybrid search for '{search_params.query}' returned {len(final_responses)} results")
            return final_responses

        except ValidationError as e:
            logger.error(f"Invalid search parameters: {str(e)}")
            raise ValueError(f"Invalid search parameters: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to perform hybrid search: {str(e)}")
            raise

    def _build_filter_expression(self, search_params: AudioSearchParams) -> str:
        """
        Build filter expression for Milvus search

        Args:
            search_params: Search parameters

        Returns:
            Filter expression string
        """
        conditions = []

        # Type filter (required)
        conditions.append(f'type == "{search_params.type.value}"')

        # Tag filter (optional) - partial match
        if search_params.tag:
            # Use ARRAY_CONTAINS for array field matching
            conditions.append(f'ARRAY_CONTAINS(tag, "{search_params.tag}")')

        # Duration range filters (optional)
        if search_params.min_duration is not None:
            conditions.append(f'duration >= {search_params.min_duration}')

        if search_params.max_duration is not None:
            conditions.append(f'duration <= {search_params.max_duration}')

        # Combine all conditions with AND
        filter_expr = " AND ".join(conditions)

        return filter_expr

    async def disconnect(self):
        """Disconnect from Milvus"""
        try:
            if self.client:
                await self.client.close()
                self.client = None
                self._initialized = False
                logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Failed to disconnect from Milvus: {str(e)}")


# Factory function
async def create_audio_manager(
    milvus_host: str = "localhost",
    milvus_port: int = 19530,
    collection_name: str = "story-audio",
    embedding_service: Optional[EmbeddingService] = None
) -> AsyncAudioMaterialManager:
    """
    Factory function to create and initialize an async audio material manager

    Args:
        milvus_host: Milvus server host
        milvus_port: Milvus server port
        collection_name: Name of the collection
        embedding_service: EmbeddingService instance

    Returns:
        Configured and connected AsyncAudioMaterialManager instance
    """
    manager = AsyncAudioMaterialManager(
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        collection_name=collection_name,
        embedding_service=embedding_service
    )
    # Auto-connect when creating through factory
    await manager.connect()
    return manager
