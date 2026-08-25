"""Advanced model search system for EMUSES model registry.

This module provides advanced search capabilities with support for multiple
search backends including Elasticsearch, Solr, and database-based search.
"""

import json
import time
import uuid
import hashlib
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from collections import OrderedDict

from sqlalchemy.orm import Session
from sqlalchemy import func, text

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from elasticsearch import Elasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    # Create stub class for testing
    class Elasticsearch:
        def __init__(self, *args, **kwargs):
            raise ImportError("Elasticsearch not available")

try:
    import pysolr
    SOLR_AVAILABLE = True
except ImportError:
    SOLR_AVAILABLE = False
    # Create stub module for testing
    class _PysolrStub:
        def Solr(self, *args, **kwargs):
            raise ImportError("pysolr not available")
    pysolr = _PysolrStub()

from emuses.multi_user_service.models import ModelRegistry
from emuses.observability.metrics import get_metrics_registry


class SemanticEmbeddings:
    """Semantic embeddings manager for model search.
    
    Provides functionality to generate and compare semantic embeddings
    for model descriptions and queries using various embedding techniques.
    """
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        """Initialize semantic embeddings.
        
        Parameters
        ----------
        embedding_model : str
            Name of the sentence transformer model to use
        """
        self.embedding_model = embedding_model
        self._transformer = None
        self._tfidf_vectorizer = None
        self._embedding_cache = {}
        
        # Initialize the embedding model
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self):
        """Initialize the embedding model based on available libraries."""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._transformer = SentenceTransformer(self.embedding_model)
            except Exception:
                # Fall back to TF-IDF if sentence transformers fail
                self._transformer = None
        
        if SKLEARN_AVAILABLE and self._transformer is None:
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for given text.
        
        Parameters
        ----------
        text : str
            Input text to embed
            
        Returns
        -------
        np.ndarray
            Text embedding vector
        """
        if not text or not text.strip():
            return np.zeros(384)  # Default embedding size
        
        # Check cache first
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        embedding = None
        
        # Try sentence transformers first
        if self._transformer is not None:
            try:
                embedding = self._transformer.encode(text)
                embedding = np.array(embedding, dtype=np.float32)
            except Exception:
                pass
        
        # Fall back to TF-IDF
        if embedding is None and self._tfidf_vectorizer is not None:
            try:
                # For single text, we need to fit or use pre-fitted vectorizer
                # This is a simplified implementation
                tfidf_matrix = self._tfidf_vectorizer.fit_transform([text])
                embedding = tfidf_matrix.toarray()[0].astype(np.float32)
            except Exception:
                # Final fallback: simple word count vector
                embedding = self._simple_text_embedding(text)
        
        if embedding is None:
            embedding = self._simple_text_embedding(text)
        
        # Cache the embedding
        self._embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _simple_text_embedding(self, text: str) -> np.ndarray:
        """Generate simple text embedding based on word frequencies.
        
        Parameters
        ----------
        text : str
            Input text
            
        Returns
        -------
        np.ndarray
            Simple embedding vector
        """
        # Simple embedding based on keyword presence
        keywords = [
            'neural', 'network', 'deep', 'learning', 'machine', 'classification',
            'regression', 'clustering', 'supervised', 'unsupervised', 'model',
            'prediction', 'algorithm', 'feature', 'training', 'validation',
            'accuracy', 'performance', 'optimization', 'gradient', 'random',
            'forest', 'support', 'vector', 'decision', 'tree', 'ensemble'
        ]
        
        text_lower = text.lower()
        embedding = np.zeros(len(keywords), dtype=np.float32)
        
        for i, keyword in enumerate(keywords):
            if keyword in text_lower:
                # Count occurrences and normalize
                count = text_lower.count(keyword)
                embedding[i] = min(count / 10.0, 1.0)  # Normalize to [0,1]
        
        return embedding.astype(np.float32)
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings.
        
        Parameters
        ----------
        embedding1 : np.ndarray
            First embedding vector
        embedding2 : np.ndarray
            Second embedding vector
            
        Returns
        -------
        float
            Cosine similarity score between 0 and 1
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        # Ensure embeddings are the same size
        if len(embedding1) != len(embedding2):
            min_size = min(len(embedding1), len(embedding2))
            embedding1 = embedding1[:min_size]
            embedding2 = embedding2[:min_size]
        
        if SKLEARN_AVAILABLE:
            try:
                # Reshape for sklearn
                emb1_reshaped = embedding1.reshape(1, -1)
                emb2_reshaped = embedding2.reshape(1, -1)
                similarity = cosine_similarity(emb1_reshaped, emb2_reshaped)[0][0]
                return max(0.0, min(1.0, float(similarity)))  # Clamp to [0,1]
            except Exception:
                pass
        
        # Manual cosine similarity calculation
        try:
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return max(0.0, min(1.0, float(similarity)))  # Clamp to [0,1]
        except Exception:
            return 0.0
    
    def find_similar_embeddings(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[np.ndarray],
        threshold: float = 0.7,
        max_results: int = 10
    ) -> List[tuple]:
        """Find similar embeddings to query embedding.
        
        Parameters
        ----------
        query_embedding : np.ndarray
            Query embedding to match against
        candidate_embeddings : List[np.ndarray]
            List of candidate embeddings to search
        threshold : float
            Minimum similarity threshold
        max_results : int
            Maximum number of results to return
            
        Returns
        -------
        List[tuple]
            List of (index, similarity_score) tuples
        """
        similarities = []
        
        for i, candidate in enumerate(candidate_embeddings):
            similarity = self.calculate_similarity(query_embedding, candidate)
            if similarity >= threshold:
                similarities.append((i, similarity))
        
        # Sort by similarity score (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:max_results]
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding generation statistics.
        
        Returns
        -------
        Dict[str, Any]
            Statistics about embedding generation
        """
        return {
            "embedding_model": self.embedding_model,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
            "sklearn_available": SKLEARN_AVAILABLE,
            "transformer_loaded": self._transformer is not None,
            "tfidf_available": self._tfidf_vectorizer is not None,
            "cache_size": len(self._embedding_cache)
        }


class SearchError(Exception):
    """Exception raised for search system errors."""
    pass


@dataclass
class SearchConfig:
    """Configuration for advanced search system.

    Attributes
    ----------
    backend_type : str
        Type of search backend ('elasticsearch', 'solr', 'database')
    elasticsearch_host : str
        Elasticsearch server hostname
    elasticsearch_port : int
        Elasticsearch server port
    solr_url : str
        Apache Solr server URL
    max_results : int
        Maximum number of search results to return
    default_similarity_threshold : float
        Default similarity threshold for semantic search
    enable_semantic_search : bool
        Whether to enable semantic search capabilities
    enable_personalized_ranking : bool
        Whether to enable personalized search result ranking
    cache_ttl_seconds : int
        Time-to-live for search result caching in seconds
    """
    backend_type: str = "database"
    elasticsearch_host: str = "localhost"
    elasticsearch_port: int = 9200
    elasticsearch_index: str = "models"
    solr_url: str = "http://localhost:8983/solr"
    solr_core: str = "models"
    max_results: int = 100
    default_similarity_threshold: float = 0.7
    enable_semantic_search: bool = False
    enable_personalized_ranking: bool = False
    cache_ttl_seconds: int = 300
    enable_search_analytics: bool = True


class SearchBackend(ABC):
    """Abstract base class for search backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name identifier."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform basic text search."""
        pass

    @abstractmethod
    def semantic_search(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform semantic search with similarity matching."""
        pass

    @abstractmethod
    def get_similar_models(
        self,
        model_id: Union[str, uuid.UUID],
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get models similar to the specified model."""
        pass


class DatabaseBackend(SearchBackend):
    """Database-based search backend using SQLAlchemy queries."""

    def __init__(self, db_session: Session):
        """Initialize database search backend.

        Parameters
        ----------
        db_session : Session
            Database session for search operations
        """
        self.db_session = db_session

    @property
    def name(self) -> str:
        """Backend name identifier."""
        return "database"

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform basic text search using database LIKE queries.

        Parameters
        ----------
        query : str
            Search query text
        filters : Dict[str, Any], optional
            Additional filters to apply
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of search results with relevance scores
        """
        try:
            # Build base query
            db_query = self.db_session.query(ModelRegistry)
            
            # Apply text search filters
            if query.strip():
                search_terms = query.lower().split()
                for term in search_terms:
                    db_query = db_query.filter(
                        func.lower(ModelRegistry.name).contains(term) |
                        func.lower(ModelRegistry.description).contains(term) |
                        func.lower(ModelRegistry.model_type).contains(term)
                    )
            
            # Apply additional filters
            if filters:
                for key, value in filters.items():
                    if hasattr(ModelRegistry, key):
                        db_query = db_query.filter(getattr(ModelRegistry, key) == value)
            
            # Order by relevance (name matches first, then description)
            db_query = db_query.order_by(
                func.lower(ModelRegistry.name).contains(query.lower()).desc(),
                ModelRegistry.created_at.desc()
            )
            
            # Limit results
            models = db_query.limit(max_results).all()
            
            # Convert to search result format
            results = []
            for i, model in enumerate(models):
                # Calculate simple relevance score based on match quality
                score = self._calculate_relevance_score(model, query)
                
                result = {
                    "model_id": str(model.id),
                    "name": model.name,
                    "description": model.description or "",
                    "model_type": model.model_type,
                    "is_public": model.is_public,
                    "created_at": model.created_at.isoformat() if model.created_at else None,
                    "score": score,
                    "rank": i + 1
                }
                results.append(result)
            
            return results

        except Exception as e:
            # Log error and return empty results
            return []

    def semantic_search(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform semantic search (falls back to text search for database backend).

        Parameters
        ----------
        query : str
            Search query for semantic matching
        similarity_threshold : float
            Minimum similarity threshold for results
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of semantically similar search results
        """
        # For database backend, semantic search falls back to enhanced text search
        # with expanded query terms and better ranking
        return self._enhanced_text_search(query, similarity_threshold, max_results)

    def get_similar_models(
        self,
        model_id: Union[str, uuid.UUID],
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get models similar to the specified model.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the reference model
        max_results : int
            Maximum number of similar models to return

        Returns
        -------
        List[Dict[str, Any]]
            List of similar models with similarity scores
        """
        try:
            # Normalize UUID
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            
            # Get the reference model
            reference_model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not reference_model:
                return []
            
            # Find similar models based on type and name similarity
            similar_query = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id != model_id,
                ModelRegistry.model_type == reference_model.model_type
            )
            
            # Add text similarity if description exists
            if reference_model.description:
                desc_terms = reference_model.description.lower().split()
                for term in desc_terms[:3]:  # Use first 3 terms
                    similar_query = similar_query.filter(
                        func.lower(ModelRegistry.description).contains(term)
                    )
            
            similar_models = similar_query.limit(max_results).all()
            
            # Convert to result format with similarity scores
            results = []
            for i, model in enumerate(similar_models):
                similarity_score = self._calculate_similarity_score(reference_model, model)
                
                result = {
                    "model_id": str(model.id),
                    "name": model.name,
                    "description": model.description or "",
                    "model_type": model.model_type,
                    "similarity_score": similarity_score,
                    "rank": i + 1
                }
                results.append(result)
            
            return results

        except Exception as e:
            return []

    def _calculate_relevance_score(self, model: ModelRegistry, query: str) -> float:
        """Calculate relevance score for a model given a query.

        Parameters
        ----------
        model : ModelRegistry
            Model to score
        query : str
            Search query

        Returns
        -------
        float
            Relevance score between 0 and 1
        """
        score = 0.0
        query_lower = query.lower()
        
        # Name match (highest weight)
        if model.name and query_lower in model.name.lower():
            score += 1.0
        
        # Description match (medium weight)
        if model.description and query_lower in model.description.lower():
            score += 0.7
        
        # Type match (lower weight)
        if model.model_type and query_lower in model.model_type.lower():
            score += 0.5
        
        # Normalize score
        return min(score, 1.0)

    def _calculate_similarity_score(self, model1: ModelRegistry, model2: ModelRegistry) -> float:
        """Calculate similarity score between two models.

        Parameters
        ----------
        model1 : ModelRegistry
            First model
        model2 : ModelRegistry
            Second model

        Returns
        -------
        float
            Similarity score between 0 and 1
        """
        score = 0.0
        
        # Same model type
        if model1.model_type == model2.model_type:
            score += 0.6
        
        # Similar names
        if model1.name and model2.name:
            name_similarity = len(set(model1.name.lower().split()) & set(model2.name.lower().split()))
            score += min(name_similarity * 0.2, 0.3)
        
        # Similar descriptions
        if model1.description and model2.description:
            desc_words1 = set(model1.description.lower().split())
            desc_words2 = set(model2.description.lower().split())
            common_words = len(desc_words1 & desc_words2)
            if desc_words1 and desc_words2:
                desc_similarity = common_words / max(len(desc_words1), len(desc_words2))
                score += min(desc_similarity * 0.1, 0.1)
        
        return min(score, 1.0)

    def _enhanced_text_search(
        self,
        query: str,
        similarity_threshold: float,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Enhanced text search with semantic-like features.

        Parameters
        ----------
        query : str
            Search query
        similarity_threshold : float
            Minimum similarity threshold
        max_results : int
            Maximum results to return

        Returns
        -------
        List[Dict[str, Any]]
            Enhanced search results
        """
        # Expand query with related terms (simple implementation)
        expanded_terms = self._expand_query_terms(query)
        
        results = []
        for term in expanded_terms:
            term_results = self.search(term, max_results=max_results//len(expanded_terms))
            results.extend(term_results)
        
        # Deduplicate and re-rank results
        seen_ids = set()
        unique_results = []
        for result in results:
            if result["model_id"] not in seen_ids:
                if result["score"] >= similarity_threshold:
                    unique_results.append(result)
                    seen_ids.add(result["model_id"])
        
        # Sort by score and limit
        unique_results.sort(key=lambda x: x["score"], reverse=True)
        return unique_results[:max_results]

    def _expand_query_terms(self, query: str) -> List[str]:
        """Expand query with related terms.

        Parameters
        ----------
        query : str
            Original query

        Returns
        -------
        List[str]
            Expanded query terms
        """
        # Simple query expansion (could be enhanced with NLP)
        terms = [query]
        query_lower = query.lower()
        
        # Add common related terms
        synonyms = {
            "neural": ["neural", "network", "deep", "learning"],
            "machine": ["machine", "learning", "ml", "algorithm"],
            "classification": ["classification", "classifier", "categorization"],
            "regression": ["regression", "prediction", "forecasting"],
            "clustering": ["clustering", "grouping", "segmentation"]
        }
        
        for key, values in synonyms.items():
            if key in query_lower:
                terms.extend(values)
        
        return list(set(terms))  # Remove duplicates


class ElasticsearchBackend(SearchBackend):
    """Elasticsearch-based search backend."""

    def __init__(self, host: str = "localhost", port: int = 9200, index: str = "models"):
        """Initialize Elasticsearch search backend.

        Parameters
        ----------
        host : str
            Elasticsearch server hostname
        port : int
            Elasticsearch server port
        index : str
            Elasticsearch index name
        """
        if not ELASTICSEARCH_AVAILABLE:
            raise SearchError("Elasticsearch package not available. Install with: pip install elasticsearch")

        try:
            self.es = Elasticsearch([{"host": host, "port": port}])
            self.index = index
            # Test connection
            self.es.ping()
        except Exception as e:
            raise SearchError(f"Failed to connect to Elasticsearch: {str(e)}")

    @property
    def name(self) -> str:
        """Backend name identifier."""
        return "elasticsearch"

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform Elasticsearch text search.

        Parameters
        ----------
        query : str
            Search query text
        filters : Dict[str, Any], optional
            Additional filters to apply
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of search results with relevance scores
        """
        try:
            # Build Elasticsearch query
            es_query = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["name^3", "description^2", "model_type"],
                        "type": "best_fields"
                    }
                },
                "size": max_results
            }
            
            # Add filters if provided
            if filters:
                filter_clauses = []
                for key, value in filters.items():
                    filter_clauses.append({"term": {key: value}})
                
                es_query["query"] = {
                    "bool": {
                        "must": es_query["query"],
                        "filter": filter_clauses
                    }
                }
            
            # Execute search
            response = self.es.search(index=self.index, body=es_query)
            
            # Convert to standard format
            results = []
            for i, hit in enumerate(response["hits"]["hits"]):
                result = {
                    "model_id": hit["_id"],
                    "score": hit["_score"],
                    "rank": i + 1
                }
                result.update(hit["_source"])
                results.append(result)
            
            return results

        except Exception as e:
            return []

    def semantic_search(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform Elasticsearch semantic search using vector similarity.

        Parameters
        ----------
        query : str
            Search query for semantic matching
        similarity_threshold : float
            Minimum similarity threshold for results
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of semantically similar search results
        """
        try:
            # Use Elasticsearch's more_like_this query for semantic search
            es_query = {
                "query": {
                    "more_like_this": {
                        "fields": ["name", "description"],
                        "like": query,
                        "min_term_freq": 1,
                        "min_doc_freq": 1,
                        "max_query_terms": 12,
                        "min_should_match": "70%"
                    }
                },
                "min_score": similarity_threshold,
                "size": max_results
            }
            
            response = self.es.search(index=self.index, body=es_query)
            
            # Convert to standard format
            results = []
            for i, hit in enumerate(response["hits"]["hits"]):
                result = {
                    "model_id": hit["_id"],
                    "score": hit["_score"],
                    "rank": i + 1
                }
                result.update(hit["_source"])
                results.append(result)
            
            return results

        except Exception as e:
            return []

    def get_similar_models(
        self,
        model_id: Union[str, uuid.UUID],
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get models similar to the specified model using Elasticsearch.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the reference model
        max_results : int
            Maximum number of similar models to return

        Returns
        -------
        List[Dict[str, Any]]
            List of similar models with similarity scores
        """
        try:
            # Normalize UUID
            if isinstance(model_id, uuid.UUID):
                model_id = str(model_id)
            
            # Use more_like_this query with the specific document
            es_query = {
                "query": {
                    "more_like_this": {
                        "fields": ["name", "description", "model_type"],
                        "like": [{"_index": self.index, "_id": model_id}],
                        "min_term_freq": 1,
                        "min_doc_freq": 1,
                        "max_query_terms": 10
                    }
                },
                "size": max_results
            }
            
            response = self.es.search(index=self.index, body=es_query)
            
            # Convert to standard format
            results = []
            for i, hit in enumerate(response["hits"]["hits"]):
                result = {
                    "model_id": hit["_id"],
                    "similarity_score": hit["_score"],
                    "rank": i + 1
                }
                result.update(hit["_source"])
                results.append(result)
            
            return results

        except Exception as e:
            return []


class SolrBackend(SearchBackend):
    """Apache Solr-based search backend."""

    def __init__(self, url: str = "http://localhost:8983/solr", core: str = "models"):
        """Initialize Solr search backend.

        Parameters
        ----------
        url : str
            Solr server URL
        core : str
            Solr core name
        """
        if not SOLR_AVAILABLE:
            raise SearchError("PySOLR package not available. Install with: pip install pysolr")

        try:
            full_url = f"{url}/{core}"
            self.solr = pysolr.Solr(full_url)
            # Test connection
            self.solr.ping()
        except Exception as e:
            raise SearchError(f"Failed to connect to Solr: {str(e)}")

    @property
    def name(self) -> str:
        """Backend name identifier."""
        return "solr"

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform Solr text search.

        Parameters
        ----------
        query : str
            Search query text
        filters : Dict[str, Any], optional
            Additional filters to apply
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of search results with relevance scores
        """
        try:
            # Build Solr query
            solr_query = f'name:"{query}"^3 OR description:"{query}"^2 OR model_type:"{query}"'
            
            # Add filters
            if filters:
                filter_clauses = [f'{key}:"{value}"' for key, value in filters.items()]
                solr_query += f' AND {" AND ".join(filter_clauses)}'
            
            # Execute search
            response = self.solr.search(solr_query, rows=max_results)
            
            # Convert to standard format
            results = []
            for i, doc in enumerate(response.docs):
                result = {
                    "model_id": doc.get("id"),
                    "name": doc.get("name", ""),
                    "description": doc.get("description", ""),
                    "model_type": doc.get("model_type", ""),
                    "score": doc.get("score", 0.0),
                    "rank": i + 1
                }
                results.append(result)
            
            return results

        except Exception as e:
            return []

    def semantic_search(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform Solr semantic search (falls back to fuzzy search).

        Parameters
        ----------
        query : str
            Search query for semantic matching
        similarity_threshold : float
            Minimum similarity threshold for results
        max_results : int
            Maximum number of results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of semantically similar search results
        """
        # Solr semantic search using fuzzy matching and synonyms
        try:
            # Build fuzzy query
            query_terms = query.split()
            fuzzy_terms = [f"{term}~0.7" for term in query_terms]  # 0.7 similarity
            solr_query = " OR ".join(fuzzy_terms)
            
            response = self.solr.search(solr_query, rows=max_results)
            
            # Filter by similarity threshold
            results = []
            for i, doc in enumerate(response.docs):
                score = doc.get("score", 0.0)
                if score >= similarity_threshold:
                    result = {
                        "model_id": doc.get("id"),
                        "name": doc.get("name", ""),
                        "description": doc.get("description", ""),
                        "score": score,
                        "rank": i + 1
                    }
                    results.append(result)
            
            return results

        except Exception as e:
            return []

    def get_similar_models(
        self,
        model_id: Union[str, uuid.UUID],
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get models similar to the specified model using Solr.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the reference model
        max_results : int
            Maximum number of similar models to return

        Returns
        -------
        List[Dict[str, Any]]
            List of similar models with similarity scores
        """
        try:
            # Normalize UUID
            if isinstance(model_id, uuid.UUID):
                model_id = str(model_id)
            
            # Get reference model first
            ref_response = self.solr.search(f'id:"{model_id}"', rows=1)
            if not ref_response.docs:
                return []
            
            ref_model = ref_response.docs[0]
            
            # Build similarity query based on model type and description
            similarity_query = f'model_type:"{ref_model.get("model_type")}" AND NOT id:"{model_id}"'
            
            response = self.solr.search(similarity_query, rows=max_results)
            
            # Convert to standard format with similarity scores
            results = []
            for i, doc in enumerate(response.docs):
                similarity_score = self._calculate_solr_similarity(ref_model, doc)
                result = {
                    "model_id": doc.get("id"),
                    "name": doc.get("name", ""),
                    "description": doc.get("description", ""),
                    "similarity_score": similarity_score,
                    "rank": i + 1
                }
                results.append(result)
            
            # Sort by similarity score
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            return results

        except Exception as e:
            return []

    def _calculate_solr_similarity(self, ref_model: Dict, candidate_model: Dict) -> float:
        """Calculate similarity between two Solr documents.

        Parameters
        ----------
        ref_model : Dict
            Reference model document
        candidate_model : Dict
            Candidate model document

        Returns
        -------
        float
            Similarity score between 0 and 1
        """
        score = 0.0
        
        # Same model type
        if ref_model.get("model_type") == candidate_model.get("model_type"):
            score += 0.6
        
        # Similar names
        ref_name = ref_model.get("name", "").lower().split()
        cand_name = candidate_model.get("name", "").lower().split()
        if ref_name and cand_name:
            common_name_words = len(set(ref_name) & set(cand_name))
            score += min(common_name_words * 0.2, 0.3)
        
        # Similar descriptions
        ref_desc = ref_model.get("description", "").lower().split()
        cand_desc = candidate_model.get("description", "").lower().split()
        if ref_desc and cand_desc:
            common_desc_words = len(set(ref_desc) & set(cand_desc))
            desc_similarity = common_desc_words / max(len(ref_desc), len(cand_desc))
            score += min(desc_similarity * 0.1, 0.1)
        
        return min(score, 1.0)


class AdvancedModelSearch:
    """Advanced model search system with multiple backends and intelligent features.

    Provides comprehensive search capabilities including semantic search,
    personalized ranking, result caching, and multi-backend support.

    Parameters
    ----------
    db_session : Session
        Database session for search operations
    config : SearchConfig, optional
        Search configuration settings

    Attributes
    ----------
    db_session : Session
        Database session reference
    config : SearchConfig
        Search configuration
    backend : SearchBackend
        Search backend instance

    Examples
    --------
    >>> search = AdvancedModelSearch(db_session)
    >>> results = search.search("neural network classification")
    >>> similar = search.get_similar_models(model_id)
    >>> semantic_results = search.semantic_search("machine learning")
    """

    def __init__(self, db_session: Optional[Session] = None, config: Optional[SearchConfig] = None):
        if db_session is None:
            raise SearchError("Database session is required")

        self.db_session = db_session
        self.config = config or SearchConfig()
        self.metrics_registry = get_metrics_registry()

        # Initialize search backend
        self.backend = self._create_backend()

        # Initialize semantic embeddings if enabled
        self.semantic_embeddings = None
        if self.config.enable_semantic_search:
            self.semantic_embeddings = SemanticEmbeddings()

        # Initialize personalized ranker if enabled
        self.personalized_ranker = None
        if self.config.enable_personalized_ranking:
            from emuses.extras.personalized_ranking import PersonalizedRanker
            self.personalized_ranker = PersonalizedRanker()

        # Search statistics and caching
        self._search_cache: OrderedDict = OrderedDict()
        self._search_stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_response_time": 0.0,
            "semantic_searches": 0
        }
        self._start_time = time.time()

    def _create_backend(self) -> SearchBackend:
        """Create appropriate search backend based on configuration."""
        if self.config.backend_type == "elasticsearch":
            return ElasticsearchBackend(
                host=self.config.elasticsearch_host,
                port=self.config.elasticsearch_port,
                index=self.config.elasticsearch_index
            )
        elif self.config.backend_type == "solr":
            return SolrBackend(
                url=self.config.solr_url,
                core=self.config.solr_core
            )
        elif self.config.backend_type == "database":
            return DatabaseBackend(db_session=self.db_session)
        else:
            raise SearchError(f"Unsupported search backend: {self.config.backend_type}")

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        user_context: Optional[Dict[str, Any]] = None,
        enable_caching: bool = False
    ) -> List[Dict[str, Any]]:
        """Perform advanced model search with optional personalization.

        Parameters
        ----------
        query : str
            Search query text
        filters : Dict[str, Any], optional
            Additional filters to apply to search results
        max_results : int, optional
            Maximum number of results to return (uses config default if not specified)
        user_context : Dict[str, Any], optional
            User context for personalized ranking
        enable_caching : bool, optional
            Whether to cache search results

        Returns
        -------
        List[Dict[str, Any]]
            List of search results with relevance scores and rankings
        """
        start_time = time.time()
        
        try:
            # Use config default if max_results not specified
            if max_results is None:
                max_results = self.config.max_results
            
            # Check cache first if enabled
            cache_key = None
            if enable_caching:
                cache_key = self._generate_cache_key(query, filters, max_results)
                cached_result = self._get_cached_result(cache_key)
                if cached_result is not None:
                    self._search_stats["cache_hits"] += 1
                    return cached_result
                else:
                    self._search_stats["cache_misses"] += 1

            # Perform search using backend
            results = self.backend.search(query, filters, max_results)
            
            # Apply personalized ranking if enabled and user context provided
            if (self.config.enable_personalized_ranking and 
                user_context is not None and 
                results):
                results = self._apply_personalized_ranking(results, user_context)
            
            # Cache results if enabled
            if enable_caching and cache_key:
                self._cache_result(cache_key, results)
            
            # Update statistics
            self._search_stats["total_searches"] += 1
            response_time = time.time() - start_time
            self._search_stats["total_response_time"] += response_time
            
            # Update metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="search",
                    status="success"
                ).inc()
            except ImportError:
                pass
            
            return results

        except Exception as e:
            # Update error metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="search",
                    status="error"
                ).inc()
            except ImportError:
                pass
            return []

    def semantic_search(
        self,
        query: str,
        similarity_threshold: Optional[float] = None,
        max_results: Optional[int] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic search with similarity matching using embeddings.

        Parameters
        ----------
        query : str
            Search query for semantic matching
        similarity_threshold : float, optional
            Minimum similarity threshold (uses config default if not specified)
        max_results : int, optional
            Maximum number of results to return
        user_context : Dict[str, Any], optional
            User context for personalized ranking

        Returns
        -------
        List[Dict[str, Any]]
            List of semantically similar search results
        """
        try:
            # Use config defaults if not specified
            if similarity_threshold is None:
                similarity_threshold = self.config.default_similarity_threshold
            if max_results is None:
                max_results = self.config.max_results

            # Check if semantic search is enabled and embeddings are available
            if self.config.enable_semantic_search and self.semantic_embeddings:
                results = self._perform_embedding_based_search(
                    query, similarity_threshold, max_results
                )
                self._search_stats["semantic_searches"] += 1
            else:
                # Fall back to backend semantic search or regular search
                if hasattr(self.backend, 'semantic_search'):
                    results = self.backend.semantic_search(query, similarity_threshold, max_results)
                else:
                    results = self.backend.search(query, max_results=max_results)
                    # Filter by similarity threshold (using score as approximation)
                    results = [r for r in results if r.get("score", 0) >= similarity_threshold]
            
            # Apply personalized ranking if enabled
            if (self.config.enable_personalized_ranking and 
                user_context is not None and 
                results):
                results = self._apply_personalized_ranking(results, user_context)
            
            return results

        except Exception as e:
            return []

    def _perform_embedding_based_search(
        self,
        query: str,
        similarity_threshold: float,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Perform embedding-based semantic search.

        Parameters
        ----------
        query : str
            Search query
        similarity_threshold : float
            Minimum similarity threshold
        max_results : int
            Maximum results to return

        Returns
        -------
        List[Dict[str, Any]]
            Search results with semantic similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.semantic_embeddings.generate_embedding(query)
            
            # Get all models from database for embedding comparison
            all_models = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.is_public == True
            ).all()
            
            if not all_models:
                return []
            
            # Generate embeddings for all model descriptions
            model_embeddings = []
            model_texts = []
            
            for model in all_models:
                # Combine name and description for richer semantic representation
                text = f"{model.name} {model.description or ''} {model.model_type}"
                model_texts.append(text)
                embedding = self.semantic_embeddings.generate_embedding(text)
                model_embeddings.append(embedding)
            
            # Find similar embeddings
            similar_indices = self.semantic_embeddings.find_similar_embeddings(
                query_embedding,
                model_embeddings,
                threshold=similarity_threshold,
                max_results=max_results
            )
            
            # Convert to search result format
            results = []
            for rank, (model_index, similarity_score) in enumerate(similar_indices):
                model = all_models[model_index]
                
                result = {
                    "model_id": str(model.id),
                    "name": model.name,
                    "description": model.description or "",
                    "model_type": model.model_type,
                    "is_public": model.is_public,
                    "created_at": model.created_at.isoformat() if model.created_at else None,
                    "score": similarity_score,
                    "semantic_score": similarity_score,
                    "rank": rank + 1,
                    "search_type": "embedding_based"
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            # Fall back to regular search if embedding search fails
            return self.backend.search(query, max_results=max_results)

    def get_similar_models(
        self,
        model_id: Union[str, uuid.UUID],
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get models similar to the specified model.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the reference model
        max_results : int
            Maximum number of similar models to return

        Returns
        -------
        List[Dict[str, Any]]
            List of similar models with similarity scores
        """
        try:
            return self.backend.get_similar_models(model_id, max_results)
        except Exception as e:
            return []

    def batch_search(
        self,
        queries: List[str],
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 10
    ) -> List[List[Dict[str, Any]]]:
        """Perform batch search for multiple queries.

        Parameters
        ----------
        queries : List[str]
            List of search queries
        filters : Dict[str, Any], optional
            Common filters to apply to all searches
        max_results : int
            Maximum results per query

        Returns
        -------
        List[List[Dict[str, Any]]]
            List of search results for each query
        """
        results = []
        for query in queries:
            query_results = self.search(query, filters=filters, max_results=max_results)
            results.append(query_results)
        return results

    def get_search_suggestions(self, partial_query: str, max_suggestions: int = 5) -> List[str]:
        """Get search suggestions for partial query.

        Parameters
        ----------
        partial_query : str
            Partial search query
        max_suggestions : int
            Maximum number of suggestions to return

        Returns
        -------
        List[str]
            List of suggested search terms
        """
        try:
            return self._generate_suggestions(partial_query, max_suggestions)
        except Exception as e:
            return []

    def multi_backend_search(
        self,
        query: str,
        backends: List[str],
        merge_strategy: str = "score"
    ) -> List[Dict[str, Any]]:
        """Search across multiple backends and merge results.

        Parameters
        ----------
        query : str
            Search query
        backends : List[str]
            List of backend names to search
        merge_strategy : str
            Strategy for merging results ('score', 'rank', 'round_robin')

        Returns
        -------
        List[Dict[str, Any]]
            Merged search results from multiple backends
        """
        all_results = []
        
        # For now, just use current backend (can be extended to support multiple backends)
        if self.backend.name in backends:
            results = self.backend.search(query)
            for result in results:
                result["backend"] = self.backend.name
            all_results.extend(results)
        
        # Sort by score (simple merge strategy)
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results

    def clear_cache(self) -> None:
        """Clear search result cache."""
        self._search_cache.clear()

    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing search statistics
        """
        uptime_seconds = time.time() - self._start_time
        total_searches = self._search_stats["total_searches"]
        
        stats = {
            "total_searches": total_searches,
            "cache_hits": self._search_stats["cache_hits"],
            "cache_misses": self._search_stats["cache_misses"],
            "semantic_searches": self._search_stats.get("semantic_searches", 0),
            "cache_hit_rate": (
                self._search_stats["cache_hits"] / max(total_searches, 1)
            ),
            "semantic_search_rate": (
                self._search_stats.get("semantic_searches", 0) / max(total_searches, 1)
            ),
            "average_response_time": (
                self._search_stats["total_response_time"] / max(total_searches, 1)
            ),
            "backend_type": self.backend.name,
            "semantic_search_enabled": self.config.enable_semantic_search,
            "personalized_ranking_enabled": self.config.enable_personalized_ranking,
            "uptime_seconds": int(uptime_seconds)
        }
        
        # Add embedding statistics if available
        if self.semantic_embeddings:
            embedding_stats = self.semantic_embeddings.get_embedding_stats()
            stats["embedding_stats"] = embedding_stats
        
        return stats

    def _apply_personalized_ranking(
        self,
        results: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply personalized ranking to search results.

        Parameters
        ----------
        results : List[Dict[str, Any]]
            Original search results
        user_context : Dict[str, Any]
            User context for personalization

        Returns
        -------
        List[Dict[str, Any]]
            Re-ranked search results
        """
        if not self.personalized_ranker:
            return results
        
        try:
            # Use the PersonalizedRanker for sophisticated ranking
            user_id = user_context.get("user_id")
            
            if user_id:
                # Update user profile if preferences are provided
                preferences = user_context.get("preferences")
                expertise_level = user_context.get("expertise_level")
                
                if preferences or expertise_level:
                    self.personalized_ranker.update_user_profile(
                        user_id=user_id,
                        preferences=preferences,
                        expertise_level=expertise_level
                    )
                
                # Rank using stored user profile
                return self.personalized_ranker.rank_models(results, user_id)
            else:
                # Rank using context directly
                return self.personalized_ranker.rank_models_with_context(results, user_context)
                
        except Exception as e:
            # Fall back to simple personalization if PersonalizedRanker fails
            return self._simple_personalized_ranking(results, user_context)
    
    def _simple_personalized_ranking(
        self,
        results: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Simple fallback personalized ranking.

        Parameters
        ----------
        results : List[Dict[str, Any]]
            Original search results
        user_context : Dict[str, Any]
            User context for personalization

        Returns
        -------
        List[Dict[str, Any]]
            Re-ranked search results
        """
        # Simple personalization based on user preferences
        user_preferences = user_context.get("preferences", {})
        
        for result in results:
            personalization_boost = 0.0
            
            # Boost based on model type preferences
            model_type = result.get("model_type", "").lower()
            preferred_type = user_preferences.get("model_type", "").lower()
            if preferred_type and preferred_type in model_type:
                personalization_boost += 0.15
            
            # Boost based on other preferences
            for pref_key, pref_value in user_preferences.items():
                if pref_key != "model_type" and isinstance(pref_value, str):
                    if pref_value.lower() in result.get("name", "").lower():
                        personalization_boost += 0.05
            
            # Apply personalization boost to score
            original_score = result.get("score", 0.0)
            result["personalized_score"] = original_score + personalization_boost
            result["personalization_boost"] = personalization_boost
        
        # Re-sort by personalized score
        results.sort(key=lambda x: x.get("personalized_score", 0), reverse=True)
        
        # Update ranks
        for i, result in enumerate(results):
            result["rank"] = i + 1
        
        return results

    def _generate_cache_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        max_results: int
    ) -> str:
        """Generate cache key for search parameters.

        Parameters
        ----------
        query : str
            Search query
        filters : Dict[str, Any], optional
            Search filters
        max_results : int
            Maximum results

        Returns
        -------
        str
            Cache key
        """
        key_data = {
            "query": query,
            "filters": filters or {},
            "max_results": max_results,
            "backend": self.backend.name
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached search result.

        Parameters
        ----------
        cache_key : str
            Cache key

        Returns
        -------
        List[Dict[str, Any]] or None
            Cached result if found and not expired
        """
        if cache_key in self._search_cache:
            cached_data = self._search_cache[cache_key]
            
            # Check if cache entry is expired
            if time.time() - cached_data["timestamp"] < self.config.cache_ttl_seconds:
                # Move to end (LRU)
                self._search_cache.move_to_end(cache_key)
                return cached_data["results"]
            else:
                # Remove expired entry
                del self._search_cache[cache_key]
        
        return None

    def _cache_result(self, cache_key: str, results: List[Dict[str, Any]]) -> None:
        """Cache search results.

        Parameters
        ----------
        cache_key : str
            Cache key
        results : List[Dict[str, Any]]
            Search results to cache
        """
        # Limit cache size (LRU eviction)
        max_cache_size = 1000
        while len(self._search_cache) >= max_cache_size:
            self._search_cache.popitem(last=False)
        
        self._search_cache[cache_key] = {
            "results": results,
            "timestamp": time.time()
        }

    def _generate_suggestions(self, partial_query: str, max_suggestions: int) -> List[str]:
        """Generate search suggestions for partial query.

        Parameters
        ----------
        partial_query : str
            Partial query text
        max_suggestions : int
            Maximum suggestions to return

        Returns
        -------
        List[str]
            List of suggested terms
        """
        # Simple suggestion generation (could be enhanced with ML)
        suggestions = []
        partial_lower = partial_query.lower()
        
        # Common model-related terms
        common_terms = [
            "neural network", "neural classification", "neural regression",
            "machine learning", "machine classification", "machine regression",
            "deep learning", "deep neural", "deep classification",
            "random forest", "random forest classifier",
            "support vector", "support vector machine",
            "gradient boosting", "gradient descent",
            "convolutional neural", "recurrent neural",
            "transformer model", "transformer classification"
        ]
        
        # Find matching terms
        for term in common_terms:
            if partial_lower in term.lower():
                suggestions.append(term)
                if len(suggestions) >= max_suggestions:
                    break
        
        return suggestions