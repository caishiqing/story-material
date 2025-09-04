"""
Embedding service using sentence-transformers library
"""

import os
from loguru import logger
import numpy as np
from typing import List, Union, Optional
from sentence_transformers import SentenceTransformer
import torch


class EmbeddingService:
    """
    Embedding service class that provides text embedding functionality
    using sentence-transformers library
    """

    def __init__(
        self,
        model_path: str = "multilingual-e5-large-instruct",
        device: Optional[str] = None
    ):
        """
        Initialize the embedding service

        Args:
            model_path: Path to the sentence-transformer model (local path or model name)
            device: Device to run the model on ('cpu', 'cuda', 'mps')
        """
        self.model_path = model_path
        self.device = device or self._get_best_device()

        # Setup logging (using loguru global logger)
        # No need to create instance logger, use global logger

        # Initialize model
        self.model = None
        self._load_model()

    def _get_best_device(self) -> str:
        """
        Automatically detect the best available device

        Returns:
            String representing the best device ('cuda', 'mps', or 'cpu')
        """
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def _load_model(self):
        """Load the sentence-transformer model"""
        try:
            logger.info(f"Loading embedding model from: {self.model_path}")
            self.model = SentenceTransformer(
                self.model_path,
                device=self.device
            )
            logger.info(f"Model loaded successfully on device: {self.device}")
        except Exception as e:
            logger.error(f"Failed to load model from {self.model_path}: {str(e)}")
            raise

    def encode(
        self,
        sentences: Union[str, List[str]],
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False
    ) -> np.ndarray:
        """
        Encode sentences into embeddings

        Args:
            sentences: Single sentence or list of sentences to encode
            batch_size: Batch size for processing
            normalize_embeddings: Whether to normalize embeddings to unit vectors
            show_progress_bar: Whether to show progress bar for batch processing

        Returns:
            - If single string input: returns 1D numpy array (single embedding vector)
            - If list input: returns 2D numpy array (array of embedding vectors)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Please initialize the service properly.")

        # Check if input is a single string
        is_single_string = isinstance(sentences, str)

        # Convert single string to list for processing
        if is_single_string:
            sentences = [sentences]

        try:
            embeddings = self.model.encode(
                sentences,
                batch_size=batch_size,
                normalize_embeddings=normalize_embeddings,
                convert_to_numpy=True,
                show_progress_bar=show_progress_bar
            )

            # Ensure the result is always numpy array
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)

            # If input was a single string, return 1D array (single vector)
            if is_single_string:
                embeddings = embeddings[0]

            logger.debug(f"Encoded {len(sentences)} sentences")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to encode sentences: {str(e)}")
            raise

    def compute_similarity(
        self,
        embeddings1: Union[np.ndarray, List[np.ndarray]],
        embeddings2: Union[np.ndarray, List[np.ndarray]]
    ) -> Union[float, np.ndarray]:
        """
        Compute cosine similarity between embeddings

        Args:
            embeddings1: First set of embeddings
            embeddings2: Second set of embeddings

        Returns:
            Cosine similarity score(s)
        """
        try:
            # Convert to numpy arrays if needed
            if isinstance(embeddings1, list):
                embeddings1 = np.array(embeddings1)
            if isinstance(embeddings2, list):
                embeddings2 = np.array(embeddings2)

            # Ensure embeddings are 2D
            if embeddings1.ndim == 1:
                embeddings1 = embeddings1.reshape(1, -1)
            if embeddings2.ndim == 1:
                embeddings2 = embeddings2.reshape(1, -1)

            # Compute cosine similarity
            similarity = np.dot(embeddings1, embeddings2.T)

            # If both inputs were single vectors, return scalar
            if similarity.shape == (1, 1):
                return float(similarity[0, 0])

            return similarity

        except Exception as e:
            logger.error(f"Failed to compute similarity: {str(e)}")
            raise

    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        top_k: int = 5
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Find most similar embeddings to a query

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: Array of candidate embeddings
            top_k: Number of top results to return

        Returns:
            Tuple of (similarities, indices) for top_k most similar embeddings
        """
        try:
            # Compute similarities
            similarities = self.compute_similarity(
                query_embedding.reshape(1, -1),
                candidate_embeddings
            ).flatten()

            # Get top_k indices
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            top_similarities = similarities[top_indices]

            return top_similarities, top_indices

        except Exception as e:
            logger.error(f"Failed to find most similar: {str(e)}")
            raise

    def get_model_info(self) -> dict:
        """
        Get information about the loaded model

        Returns:
            Dictionary containing model information
        """
        if self.model is None:
            return {"status": "Model not loaded"}

        return {
            "model_path": self.model_path,
            "device": self.device,
            "embedding_dimension": self.model.get_sentence_embedding_dimension(),
            "max_seq_length": self.model.max_seq_length
        }

    def __repr__(self) -> str:
        return f"EmbeddingService(model_path='{self.model_path}', device='{self.device}')"


# Convenient factory function
def create_embedding_service(
    model_path: str = "multilingual-e5-large-instruct",
    device: Optional[str] = None
) -> EmbeddingService:
    """
    Factory function to create an embedding service instance

    Args:
        model_path: Path to the sentence-transformer model (local path or model name)
        device: Device to run the model on

    Returns:
        Configured EmbeddingService instance
    """
    return EmbeddingService(
        model_path=model_path,
        device=device
    )


# Example usage and testing
if __name__ == "__main__":
    # Setup logging (loguru is already configured)

    # Create embedding service
    embedding_service = create_embedding_service()

    # Print model info
    print("Model Info:", embedding_service.get_model_info())

    # Test with sample texts
    sample_texts = [
        "Hello world",
        "How are you today?",
        "Machine learning is fascinating",
        "Natural language processing",
        "Deep learning models"
    ]

    print("\nTesting embedding encoding...")
    embeddings = embedding_service.encode(sample_texts)
    print(f"Embeddings shape: {embeddings.shape}")

    # Test similarity computation
    print("\nTesting similarity computation...")
    query_text = "Artificial intelligence"
    query_embedding = embedding_service.encode(query_text)

    similarities, indices = embedding_service.find_most_similar(
        query_embedding, embeddings, top_k=3
    )

    print(f"Query: '{query_text}'")
    print("Most similar texts:")
    for i, (sim, idx) in enumerate(zip(similarities, indices)):
        print(f"{i+1}. '{sample_texts[idx]}' (similarity: {sim:.4f})")
