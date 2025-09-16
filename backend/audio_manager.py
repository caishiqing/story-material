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
        self.client = AsyncMilvusClient(uri=f"http://{milvus_host}:{milvus_port}")
        self.embedding_service = embedding_service or EmbeddingService()

    async def connect(self):
        """Connect to Milvus server and initialize collection"""
        dbs = await self.client.list_databases()
        if self.db_name not in dbs:
            await self.client.create_database(self.db_name)

        self.client.use_database(self.db_name)

        collections = await self.client.list_collections()
        if self.collection_name not in collections:
            await self._create_collection()

    async def _create_collection(self):
        """Create the audio collection with defined schema"""
        schema = AsyncMilvusClient.create_schema()

        schema.add_field(field_name="id",
                         datatype=DataType.INT64,
                         is_primary=True,
                         auto_id=True)

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

        analyzer_params = {"type": "chinese"}

        schema.add_field(field_name="description",
                         datatype=DataType.VARCHAR,
                         max_length=2048,
                         enable_analyzer=True,
                         enable_match=True,
                         analyzer_params=analyzer_params)

        schema.add_field(field_name="sparse_vector",
                         datatype=DataType.SPARSE_FLOAT_VECTOR)

        # Define BM25 function for full-text search
        bm25_function = Function(
            name="description_bm25_emb",
            input_field_names=["description"],
            output_field_names=["sparse_vector"],
            function_type=FunctionType.BM25,
        )
        schema.add_function(bm25_function)

        # Create index for dense vector field
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            index_name="vector_index",
            metric_type="L2",
            params={"nlist": 64, "nprobe": 10}
        )

        # Create index for sparse vector field (BM25)
        index_params.add_index(
            field_name="sparse_vector",
            index_type="SPARSE_INVERTED_INDEX",
            index_name="sparse_vector_index",
            metric_type="BM25",
            params={}
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
            "path": audio_data.path,
            "description": audio_data.description,
            "vector": vector.tolist(),
            "type": audio_data.type,
            "tag": audio_data.tags,
            "duration": audio_data.duration
        }]

        result = await self.client.insert(self.collection_name, data=data)

        inserted_id = result['insert_count']  # AsyncMilvusClient returns different format
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
        # Convert to int if string
        if isinstance(audio_id, str):
            audio_id = int(audio_id)

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
        # Convert to int if string
        if isinstance(audio_id, str):
            audio_id = int(audio_id)

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

        # Get entity count using proper query method
        collection_stats = await self.client.get_collection_stats(
            collection_name=self.collection_name
        )
        total_entities = collection_stats.get('row_count', 0)

        # Build schema info
        schema_info = {}
        for field in collection_info['fields']:
            schema_info[field['name']] = {
                "type": field['type'],
                "description": field.get('description', '')
            }

        # Get type counts
        all_records = await self.client.query(
            collection_name=self.collection_name,
            output_fields=["type"],
            limit=1000
        )

        # Count by type
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
        query_vector = self.embedding_service.encode(search_params.query)

        # Perform hybrid search using AsyncMilvusClient
        search_results = await self.client.search(
            collection_name=self.collection_name,
            data=[search_params.query, query_vector.tolist()],
            anns_field=["sparse_vector", "vector"],
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
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Milvus")
