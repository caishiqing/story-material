"""
Async Audio material management system using Milvus database
"""

import os
from loguru import logger
import asyncio
from typing import List, Dict, Optional, Any, Union
from pymilvus import AsyncMilvusClient, CollectionSchema, FieldSchema, DataType, Function, FunctionType
from pymilvus.milvus_client.index import IndexParams
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
        db_name: str = "story",
        collection_name: str = "audio",
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
        self.db_name = db_name
        self.collection_name = collection_name
        self.uri = f"http://{milvus_host}:{milvus_port}"
        self.client = None
        self.embedding_service = embedding_service or EmbeddingService()

    async def connect(self):
        """Connect to Milvus server and initialize collection"""
        dbs = await AsyncMilvusClient(self.uri).list_databases()

        if self.db_name not in dbs:
            await AsyncMilvusClient(self.uri).create_database(self.db_name)

        self.client = AsyncMilvusClient(uri=self.uri, db_name=self.db_name)

        collections = await self.client.list_collections()
        if self.collection_name not in collections:
            await self._create_collection()

    async def _create_collection(self):
        """Create the audio collection with defined schema"""
        schema = AsyncMilvusClient.create_schema()

        schema.add_field(field_name="id",
                         datatype=DataType.VARCHAR,
                         max_length=1000,
                         is_primary=True,
                         auto_id=False)

        schema.add_field(field_name="path",
                         datatype=DataType.VARCHAR,
                         max_length=512)

        schema.add_field(field_name="vector",
                         datatype=DataType.FLOAT_VECTOR,
                         dim=self.embedding_service.dimensions)

        schema.add_field(field_name="type",
                         datatype=DataType.VARCHAR,
                         max_length=128)

        schema.add_field(field_name="duration",
                         datatype=DataType.INT64)

        schema.add_field(field_name="tag",
                         datatype=DataType.ARRAY,
                         element_type=DataType.VARCHAR,
                         max_capacity=50,
                         max_length=64,
                         nullable=True)

        schema.add_field(field_name="description",
                         datatype=DataType.VARCHAR,
                         max_length=2048)

        # Create index for dense vector field
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            index_name="vector_index",
            metric_type="L2",
            params={"nlist": 64, "nprobe": 10}
        )

        # Create index for type field
        index_params.add_index(
            field_name="type",
            index_type="INVERTED",
            index_name="type_index",
        )

        # Create collection using async client
        await self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params
        )

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
        # Convert dict to AudioMaterialCreate if needed (duration auto-detected in model)
        if isinstance(audio_data, dict):
            audio_data = AudioMaterialCreate(**audio_data)

        # Generate vector embedding from description
        vector = self.embedding_service.encode(audio_data.description)

        # Prepare data for Milvus insertion
        data = [{
            "id": audio_data.id,  # Use the ID from audio_data (either user-specified or auto-generated)
            "path": audio_data.path,
            "description": audio_data.description,
            "vector": vector.tolist(),
            "type": audio_data.type,
            "tag": audio_data.tags,
            "duration": audio_data.duration
        }]

        result = await self.client.insert(self.collection_name, data=data)

        # Return the actual ID that was inserted
        inserted_id = audio_data.id
        logger.info(f"Successfully added audio material: {audio_data.path} (ID: {inserted_id})")

        return str(inserted_id)

    async def delete(self, audio_id: Union[str, int]) -> bool:
        """
        Delete an audio material by ID

        Args:
            audio_id: ID of the audio to delete

        Returns:
            True if deletion was successful
        """
        # Keep audio_id as-is (can be string or int)

        # Delete by primary key
        result = await self.client.delete(
            collection_name=self.collection_name,
            ids=audio_id
        )

        if result['delete_count'] > 0:
            logger.info(f"Successfully deleted audio material with ID: {audio_id}")
            return True
        else:
            logger.warning(f"No audio material found with ID: {audio_id}")
            return False

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
        # Validate and convert input data
        if isinstance(update_data, AudioMaterialUpdate):
            update_data = update_data.model_dump()

        update_data["id"] = audio_id

        existing_record = await self.client.query(
            collection_name=self.collection_name,
            ids=audio_id,
            output_fields=["description", "vector"]
        )

        if not existing_record:
            logger.warning(f"No audio material found with ID: {audio_id}")
            return False
        else:
            existing_record = existing_record[0]

        # Generate new vector if description changed
        if update_data.get("description") is not None and update_data["description"] != existing_record["description"]:
            vector = self.embedding_service.encode(update_data.description).tolist()
            update_data["vector"] = vector

        result = await self.client.upsert(
            collection_name=self.collection_name,
            data=update_data
        )

        if result['upsert_count'] > 0:
            logger.info(f"Successfully updated audio material with ID: {audio_id}")
            return True
        else:
            logger.warning(f"No audio material found with ID: {audio_id}")
            return False

    async def get(self, audio_id: Union[str, int]) -> Optional[AudioMaterialResponse]:
        """
        Get audio material by ID

        Args:
            audio_id: ID of the audio to retrieve

        Returns:
            AudioMaterialResponse instance or None if not found
        """
        # Keep audio_id as-is (can be string or int)

        records = await self.client.query(
            collection_name=self.collection_name,
            ids=audio_id,
            output_fields=["id", "path", "description", "type", "tag", "duration"]
        )

        if records:
            return AudioMaterialResponse.from_milvus_result(records[0])
        else:
            logger.warning(f"No audio material found with ID: {audio_id}")
            return None

    async def list(self) -> List[AudioMaterialResponse]:
        """
        List all audio materials

        Returns:
            List of AudioMaterialResponse instances
        """
        records = await self.client.query(
            collection_name=self.collection_name,
            output_fields=["id", "path", "description", "type", "tag", "duration"],
            limit=1000
        )

        return [AudioMaterialResponse.from_milvus_result(record) for record in records]

    async def check(self) -> CollectionStats:
        """
        Check collection statistics

        Returns:
            CollectionStats instance
        """
        # Get collection info
        collection_info = await self.client.describe_collection(
            collection_name=self.collection_name
        )

        # Build schema info
        schema_info = {}
        for field in collection_info['fields']:
            schema_info[field['name']] = {
                "type": field['type'],
                "description": field.get('description', '')
            }

        # Get type counts - use the same query for both total count and type counts
        all_records = await self.client.query(
            collection_name=self.collection_name,
            output_fields=["type"],
            limit=10000
        )
        total_entities = len(all_records)

        # Count by type and get actual total count
        type_counts = {}
        for record in all_records:
            audio_type = record.get('type', 'unknown')
            type_counts[audio_type] = type_counts.get(audio_type, 0) + 1

        return CollectionStats(
            collection_name=self.collection_name,
            total_count=total_entities,
            type_counts=type_counts,
            schema=schema_info
        )

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
        # Validate and convert input data
        if isinstance(search_params, dict):
            search_params = AudioSearchParams(**search_params)

        # Build filter expression
        filter_expr = self._build_filter_expression(search_params)
        logger.info(f"Filter expression: {filter_expr}")

        # Generate dense vector for semantic search
        task_description = "Given a query, find the most relevant audio from the database, pay attention to the subject, object, gender, emotion and action."
        query = f"Instruct: {task_description}\nQuery: {search_params.query}"
        query_vector = self.embedding_service.encode(query)

        # Perform hybrid search using AsyncMilvusClient
        search_results = await self.client.search(
            collection_name=self.collection_name,
            data=[query_vector.tolist()],
            anns_field="vector",
            limit=search_params.limit,
            filter=filter_expr,  # Apply filtering
            output_fields=["id", "path", "description", "type", "tag", "duration"],
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

    def _build_filter_expression(self, search_params: AudioSearchParams) -> str:
        """
        Build filter expression for Milvus search

        Args:
            search_params: Search parameters

        Returns:
            Filter expression string
        """
        conditions = []

        # Type filter
        if search_params.type:
            conditions.append(f'type == "{search_params.type.value}"')

        # Tag filter (optional) - single tag or multiple tags
        if search_params.tag:
            if isinstance(search_params.tag, str):
                # Single tag matching
                conditions.append(f'ARRAY_CONTAINS(tag, "{search_params.tag}")')
            elif isinstance(search_params.tag, list):
                # Multiple tags matching - all tags must be present (AND logic)
                tag_conditions = []
                for tag in search_params.tag:
                    tag_conditions.append(f'ARRAY_CONTAINS(tag, "{tag}")')
                if tag_conditions:
                    conditions.append(f'({" AND ".join(tag_conditions)})')

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
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Milvus")
