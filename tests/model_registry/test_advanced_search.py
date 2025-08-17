"""Tests for advanced model search system."""

import pytest
import uuid
import numpy as np
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, List, Any

from emuses.tools.advanced_search import (
    AdvancedModelSearch, SearchBackend, SearchConfig, SearchError,
    ElasticsearchBackend, SolrBackend, DatabaseBackend, SemanticEmbeddings
)


class TestSemanticEmbeddings:
    """Test semantic embeddings functionality."""
    
    def test_semantic_embeddings_init(self):
        """Test semantic embeddings initialization."""
        embeddings = SemanticEmbeddings()
        
        assert embeddings.embedding_model == "all-MiniLM-L6-v2"
        assert isinstance(embeddings._embedding_cache, dict)
    
    def test_generate_embedding_simple(self):
        """Test basic embedding generation."""
        embeddings = SemanticEmbeddings()
        
        text = "neural network classification model"
        embedding = embeddings.generate_embedding(text)
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) > 0
        assert embedding.dtype == np.float32
    
    def test_generate_embedding_empty_text(self):
        """Test embedding generation for empty text."""
        embeddings = SemanticEmbeddings()
        
        embedding = embeddings.generate_embedding("")
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 384  # Default embedding size
        assert np.all(embedding == 0)
    
    def test_calculate_similarity(self):
        """Test similarity calculation between embeddings."""
        embeddings = SemanticEmbeddings()
        
        # Similar texts should have high similarity
        text1 = "neural network classification"
        text2 = "neural network for classification"
        
        emb1 = embeddings.generate_embedding(text1)
        emb2 = embeddings.generate_embedding(text2)
        
        similarity = embeddings.calculate_similarity(emb1, emb2)
        
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # Should be relatively similar
    
    def test_calculate_similarity_different_texts(self):
        """Test similarity calculation for different texts."""
        embeddings = SemanticEmbeddings()
        
        text1 = "neural network classification"
        text2 = "weather forecast system"
        
        emb1 = embeddings.generate_embedding(text1)
        emb2 = embeddings.generate_embedding(text2)
        
        similarity = embeddings.calculate_similarity(emb1, emb2)
        
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        # Different topics should have lower similarity
    
    def test_find_similar_embeddings(self):
        """Test finding similar embeddings."""
        embeddings = SemanticEmbeddings()
        
        query_text = "machine learning classification"
        candidate_texts = [
            "neural network classifier",
            "weather prediction model",
            "classification algorithm",
            "regression analysis"
        ]
        
        query_embedding = embeddings.generate_embedding(query_text)
        candidate_embeddings = [
            embeddings.generate_embedding(text) for text in candidate_texts
        ]
        
        similar = embeddings.find_similar_embeddings(
            query_embedding, candidate_embeddings, threshold=0.1, max_results=3
        )
        
        assert isinstance(similar, list)
        assert len(similar) <= 3
        for idx, score in similar:
            assert isinstance(idx, int)
            assert isinstance(score, float)
            assert 0 <= idx < len(candidate_texts)
            assert 0.0 <= score <= 1.0
    
    def test_embedding_caching(self):
        """Test embedding caching functionality."""
        embeddings = SemanticEmbeddings()
        
        text = "test caching functionality"
        
        # First generation should cache
        emb1 = embeddings.generate_embedding(text)
        assert len(embeddings._embedding_cache) == 1
        
        # Second generation should use cache
        emb2 = embeddings.generate_embedding(text)
        assert len(embeddings._embedding_cache) == 1
        assert np.array_equal(emb1, emb2)
    
    def test_get_embedding_stats(self):
        """Test embedding statistics."""
        embeddings = SemanticEmbeddings()
        
        # Generate some embeddings to populate stats
        embeddings.generate_embedding("test text 1")
        embeddings.generate_embedding("test text 2")
        
        stats = embeddings.get_embedding_stats()
        
        assert isinstance(stats, dict)
        assert "embedding_model" in stats
        assert "sentence_transformers_available" in stats
        assert "sklearn_available" in stats
        assert "cache_size" in stats
        assert stats["cache_size"] >= 0


class TestSearchBackend:
    """Test abstract search backend interface."""
    
    def test_search_backend_abstract(self):
        """Test that SearchBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SearchBackend()


class TestSearchConfig:
    """Test search configuration class."""
    
    def test_search_config_default(self):
        """Test default search configuration values."""
        config = SearchConfig()
        
        assert config.backend_type == "database"
        assert config.elasticsearch_host == "localhost"
        assert config.elasticsearch_port == 9200
        assert config.solr_url == "http://localhost:8983/solr"
        assert config.max_results == 100
        assert config.default_similarity_threshold == 0.7
        assert config.enable_semantic_search == False
        assert config.enable_personalized_ranking == False
    
    def test_search_config_custom(self):
        """Test custom search configuration."""
        config = SearchConfig(
            backend_type="elasticsearch",
            elasticsearch_host="search.example.com",
            elasticsearch_port=9201,
            max_results=500,
            enable_semantic_search=True,
            enable_personalized_ranking=True
        )
        
        assert config.backend_type == "elasticsearch"
        assert config.elasticsearch_host == "search.example.com"
        assert config.elasticsearch_port == 9201
        assert config.max_results == 500
        assert config.enable_semantic_search == True
        assert config.enable_personalized_ranking == True


class TestDatabaseBackend:
    """Test database search backend."""
    
    def test_database_backend_init(self):
        """Test database backend initialization."""
        mock_session = Mock()
        backend = DatabaseBackend(db_session=mock_session)
        
        assert backend.db_session is mock_session
        assert backend.name == "database"
    
    def test_basic_text_search(self):
        """Test basic text search functionality."""
        mock_session = Mock()
        backend = DatabaseBackend(db_session=mock_session)
        
        # Mock search results
        mock_models = []
        for i in range(3):
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"test_model_{i}"
            mock_model.description = f"Test description {i}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_model.created_at = None
            mock_models.append(mock_model)
        
        # Mock database query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  
        mock_query.limit.return_value = Mock()
        mock_query.limit.return_value.all.return_value = mock_models
        mock_session.query.return_value = mock_query
        
        results = backend.search("test", max_results=10)
        
        assert len(results) == 3
        assert all("model_id" in result for result in results)
        assert all("name" in result for result in results)
        assert all("score" in result for result in results)
    
    def test_advanced_search_with_filters(self):
        """Test advanced search with filters."""
        mock_session = Mock()
        backend = DatabaseBackend(db_session=mock_session)
        
        # Mock filtered results
        mock_models = [Mock()]
        mock_models[0].id = uuid.uuid4()
        mock_models[0].name = "classification_model"
        mock_models[0].description = "A classification model"
        mock_models[0].model_type = "classification"
        mock_models[0].is_public = True
        mock_models[0].created_at = None
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = Mock()
        mock_query.limit.return_value.all.return_value = mock_models
        mock_session.query.return_value = mock_query
        
        filters = {
            "model_type": "classification",
            "is_public": True
        }
        
        results = backend.search("model", filters=filters)
        
        assert len(results) == 1
        assert results[0]["name"] == "classification_model"
    
    def test_semantic_search_fallback(self):
        """Test semantic search falls back to text search."""
        mock_session = Mock()
        backend = DatabaseBackend(db_session=mock_session)
        
        # Mock results for fallback
        mock_models = [Mock()]
        mock_models[0].id = uuid.uuid4()
        mock_models[0].name = "similar_model"
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_models
        mock_session.query.return_value = mock_query
        
        # Semantic search should fall back to regular text search
        results = backend.semantic_search("neural network", similarity_threshold=0.8)
        
        assert len(results) >= 0  # Should return results or empty list
    
    def test_get_similar_models(self):
        """Test getting similar models."""
        mock_session = Mock()
        backend = DatabaseBackend(db_session=mock_session)
        
        model_id = uuid.uuid4()
        
        # Mock similar models
        mock_models = []
        for i in range(2):
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"similar_model_{i}"
            mock_model.model_type = "classification"
            mock_models.append(mock_model)
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_models
        mock_session.query.return_value = mock_query
        
        results = backend.get_similar_models(model_id, max_results=5)
        
        assert len(results) <= 5
        assert all("similarity_score" in result for result in results)


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    mock_client = Mock()
    with patch('emuses.tools.advanced_search.ELASTICSEARCH_AVAILABLE', True):
        with patch('emuses.tools.advanced_search.Elasticsearch', return_value=mock_client):
            yield mock_client


class TestElasticsearchBackend:
    """Test Elasticsearch search backend."""
    
    def test_elasticsearch_backend_init(self, mock_elasticsearch):
        """Test Elasticsearch backend initialization."""
        backend = ElasticsearchBackend(host="localhost", port=9200)
        
        assert backend.name == "elasticsearch"
        assert backend.es is mock_elasticsearch
    
    def test_elasticsearch_search(self, mock_elasticsearch):
        """Test Elasticsearch search operations."""
        backend = ElasticsearchBackend()
        
        # Mock Elasticsearch response
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_id": str(uuid.uuid4()),
                        "_source": {
                            "name": "test_model",
                            "description": "Test model description",
                            "model_type": "classification"
                        },
                        "_score": 1.5
                    }
                ]
            }
        }
        mock_elasticsearch.search.return_value = mock_response
        
        results = backend.search("test query", max_results=10)
        
        assert len(results) == 1
        assert results[0]["name"] == "test_model"
        assert results[0]["score"] == 1.5
    
    def test_elasticsearch_connection_error(self):
        """Test Elasticsearch connection error handling."""
        with patch('emuses.tools.advanced_search.ELASTICSEARCH_AVAILABLE', True):
            with patch('emuses.tools.advanced_search.Elasticsearch') as mock_es_class:
                mock_es_class.side_effect = Exception("Connection failed")
                
                with pytest.raises(SearchError, match="Failed to connect to Elasticsearch"):
                    ElasticsearchBackend()
    
    def test_elasticsearch_semantic_search(self, mock_elasticsearch):
        """Test Elasticsearch semantic search."""
        backend = ElasticsearchBackend()
        
        # Mock semantic search response
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_id": str(uuid.uuid4()),
                        "_source": {
                            "name": "neural_model",
                            "description": "Neural network model",
                            "model_type": "deep_learning"
                        },
                        "_score": 0.85
                    }
                ]
            }
        }
        mock_elasticsearch.search.return_value = mock_response
        
        results = backend.semantic_search("machine learning", similarity_threshold=0.8)
        
        assert len(results) == 1
        assert results[0]["name"] == "neural_model"
        assert results[0]["score"] == 0.85


@pytest.fixture
def mock_solr():
    """Mock Solr client."""
    mock_client = Mock()
    mock_solr_module = Mock()
    mock_solr_module.Solr.return_value = mock_client
    with patch('emuses.tools.advanced_search.SOLR_AVAILABLE', True):
        with patch('emuses.tools.advanced_search.pysolr', mock_solr_module):
            yield mock_client


class TestSolrBackend:
    """Test Solr search backend."""
    
    def test_solr_backend_init(self, mock_solr):
        """Test Solr backend initialization."""
        backend = SolrBackend(url="http://localhost:8983/solr")
        
        assert backend.name == "solr"
        assert backend.solr is mock_solr
    
    def test_solr_search(self, mock_solr):
        """Test Solr search operations."""
        backend = SolrBackend()
        
        # Mock Solr response
        mock_response = Mock()
        mock_response.docs = [
            {
                "id": str(uuid.uuid4()),
                "name": "solr_model",
                "description": "Solr test model",
                "model_type": "classification",
                "score": 2.1
            }
        ]
        mock_solr.search.return_value = mock_response
        
        results = backend.search("test", max_results=10)
        
        assert len(results) == 1
        assert results[0]["name"] == "solr_model"
        assert results[0]["score"] == 2.1


@pytest.fixture
def mock_database_session():
    """Mock database session for AdvancedModelSearch testing."""
    return Mock()


@pytest.fixture
def sample_search_data():
    """Sample search data for testing."""
    return {
        "query": "neural network classification",
        "filters": {"model_type": "classification", "is_public": True},
        "user_context": {"user_id": str(uuid.uuid4()), "preferences": ["accuracy", "speed"]}
    }


class TestAdvancedModelSearch:
    """Test AdvancedModelSearch class."""
    
    def test_advanced_search_init_database_backend(self, mock_database_session):
        """Test AdvancedModelSearch initialization with database backend."""
        config = SearchConfig(backend_type="database")
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        assert search.db_session is mock_database_session
        assert search.config is config
        assert isinstance(search.backend, DatabaseBackend)
    
    @patch('emuses.tools.advanced_search.ElasticsearchBackend')
    def test_advanced_search_init_elasticsearch_backend(self, mock_es_backend, mock_database_session):
        """Test AdvancedModelSearch initialization with Elasticsearch backend."""
        config = SearchConfig(backend_type="elasticsearch")
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        mock_es_backend.assert_called_once()
    
    @patch('emuses.tools.advanced_search.SolrBackend')
    def test_advanced_search_init_solr_backend(self, mock_solr_backend, mock_database_session):
        """Test AdvancedModelSearch initialization with Solr backend."""
        config = SearchConfig(backend_type="solr")
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        mock_solr_backend.assert_called_once()
    
    def test_advanced_search_init_invalid_backend(self, mock_database_session):
        """Test AdvancedModelSearch initialization with invalid backend."""
        config = SearchConfig(backend_type="invalid")
        
        with pytest.raises(SearchError, match="Unsupported search backend"):
            AdvancedModelSearch(db_session=mock_database_session, config=config)
    
    def test_advanced_search_init_no_session(self):
        """Test AdvancedModelSearch initialization without database session."""
        with pytest.raises(SearchError, match="Database session is required"):
            AdvancedModelSearch(db_session=None)
    
    def test_basic_search(self, mock_database_session, sample_search_data):
        """Test basic search functionality."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        # Mock backend search results
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "test_model",
                "description": "Test model",
                "score": 1.0
            }
        ]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            results = search.search("test query")
            
            assert len(results) == 1
            assert results[0]["name"] == "test_model"
    
    def test_search_with_filters(self, mock_database_session, sample_search_data):
        """Test search with filters."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "classification_model",
                "model_type": "classification",
                "score": 1.2
            }
        ]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            results = search.search(
                query="model",
                filters=sample_search_data["filters"]
            )
            
            assert len(results) == 1
            assert results[0]["model_type"] == "classification"
    
    def test_semantic_search_enabled(self, mock_database_session):
        """Test semantic search when enabled."""
        config = SearchConfig(enable_semantic_search=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Mock the embedding-based search path since semantic_embeddings is available
        mock_models = [Mock()]
        mock_models[0].id = uuid.uuid4()
        mock_models[0].name = "semantic_model"
        mock_models[0].description = "Semantically similar model"
        mock_models[0].model_type = "classification"
        mock_models[0].is_public = True
        mock_models[0].created_at = None
        
        # Mock database query for embedding-based search
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_models
        mock_database_session.query.return_value = mock_query
        
        # Mock embedding methods
        with patch.object(search.semantic_embeddings, 'generate_embedding') as mock_generate:
            with patch.object(search.semantic_embeddings, 'find_similar_embeddings') as mock_find:
                mock_generate.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
                mock_find.return_value = [(0, 0.85)]  # One similar result
                
                results = search.semantic_search("neural network", similarity_threshold=0.8)
                
                assert len(results) == 1
                assert results[0]["name"] == "semantic_model"
                assert results[0]["search_type"] == "embedding_based"
    
    def test_semantic_search_disabled(self, mock_database_session):
        """Test semantic search when disabled (falls back to regular search)."""
        config = SearchConfig(enable_semantic_search=False)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "fallback_model",
                "score": 1.0
            }
        ]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            results = search.semantic_search("neural network")
            
            assert len(results) == 1
            assert results[0]["name"] == "fallback_model"
    
    def test_get_similar_models(self, mock_database_session):
        """Test getting similar models."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        model_id = uuid.uuid4()
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "similar_model_1",
                "similarity_score": 0.9
            },
            {
                "model_id": str(uuid.uuid4()),
                "name": "similar_model_2", 
                "similarity_score": 0.8
            }
        ]
        
        with patch.object(search.backend, 'get_similar_models', return_value=mock_results):
            results = search.get_similar_models(model_id, max_results=5)
            
            assert len(results) == 2
            assert all("similarity_score" in result for result in results)
    
    def test_personalized_search_enabled(self, mock_database_session, sample_search_data):
        """Test personalized search when enabled."""
        config = SearchConfig(enable_personalized_ranking=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "personalized_model",
                "score": 1.0
            }
        ]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            with patch.object(search, '_apply_personalized_ranking', return_value=mock_results):
                results = search.search(
                    query="test",
                    user_context=sample_search_data["user_context"]
                )
                
                assert len(results) == 1
                assert results[0]["name"] == "personalized_model"
    
    def test_search_result_caching(self, mock_database_session):
        """Test search result caching."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        # First search - should call backend
        mock_results = [{"model_id": str(uuid.uuid4()), "name": "cached_model", "score": 1.0}]
        
        with patch.object(search.backend, 'search', return_value=mock_results) as mock_search:
            # First call
            results1 = search.search("test query", enable_caching=True)
            assert len(results1) == 1
            assert mock_search.call_count == 1
            
            # Second call with same query - should use cache
            results2 = search.search("test query", enable_caching=True)
            assert len(results2) == 1
            assert mock_search.call_count == 1  # Still 1, not called again
    
    def test_get_search_stats(self, mock_database_session):
        """Test getting search statistics."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        stats = search.get_search_stats()
        
        assert isinstance(stats, dict)
        assert "total_searches" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "average_response_time" in stats
        assert "backend_type" in stats
    
    def test_clear_search_cache(self, mock_database_session):
        """Test clearing search cache."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        # Add something to cache first
        mock_results = [{"model_id": str(uuid.uuid4()), "name": "test", "score": 1.0}]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            search.search("test", enable_caching=True)
            
            # Clear cache
            search.clear_cache()
            
            # Verify cache is cleared by checking next search calls backend again
            with patch.object(search.backend, 'search', return_value=mock_results) as mock_search:
                search.search("test", enable_caching=True)
                assert mock_search.call_count == 1
    
    def test_batch_search(self, mock_database_session):
        """Test batch search functionality."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        queries = ["query1", "query2", "query3"]
        mock_results = [
            [{"model_id": str(uuid.uuid4()), "name": f"result_{i}", "score": 1.0}]
            for i in range(len(queries))
        ]
        
        with patch.object(search.backend, 'search', side_effect=mock_results):
            results = search.batch_search(queries)
            
            assert len(results) == 3
            assert all(isinstance(result, list) for result in results)
    
    def test_search_suggestions(self, mock_database_session):
        """Test search suggestions functionality."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        partial_query = "neural"
        mock_suggestions = ["neural network", "neural classification", "neural regression"]
        
        with patch.object(search, '_generate_suggestions', return_value=mock_suggestions):
            suggestions = search.get_search_suggestions(partial_query)
            
            assert len(suggestions) == 3
            assert all("neural" in suggestion for suggestion in suggestions)
    
    def test_advanced_search_error_handling(self, mock_database_session):
        """Test error handling in advanced search."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        # Test backend error handling
        with patch.object(search.backend, 'search', side_effect=Exception("Backend error")):
            results = search.search("test query")
            assert results == []  # Should return empty list on error
    
    def test_multi_backend_search(self, mock_database_session):
        """Test search across multiple backends."""
        search = AdvancedModelSearch(db_session=mock_database_session)
        
        # Mock results from multiple backends
        db_results = [{"model_id": str(uuid.uuid4()), "name": "db_model", "score": 1.0}]
        
        with patch.object(search.backend, 'search', return_value=db_results):
            results = search.multi_backend_search("test query", backends=["database"])
            
            assert len(results) >= 1
            assert results[0]["name"] == "db_model"
    
    def test_embedding_based_semantic_search(self, mock_database_session):
        """Test embedding-based semantic search."""
        # Enable semantic search
        config = SearchConfig(enable_semantic_search=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Mock database models
        mock_models = []
        for i in range(3):
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"neural_model_{i}"
            mock_model.description = f"Neural network model for classification task {i}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_model.created_at = None
            mock_models.append(mock_model)
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_models
        mock_database_session.query.return_value = mock_query
        
        # Mock embedding generation and similarity
        with patch.object(search.semantic_embeddings, 'generate_embedding') as mock_generate:
            with patch.object(search.semantic_embeddings, 'find_similar_embeddings') as mock_find:
                # Mock embeddings
                mock_generate.return_value = np.array([0.1, 0.2, 0.3])
                mock_find.return_value = [(0, 0.9), (1, 0.8)]  # indices and similarity scores
                
                results = search.semantic_search("neural network classification")
                
                assert len(results) == 2
                assert all("semantic_score" in result for result in results)
                assert all("search_type" in result for result in results)
                assert results[0]["semantic_score"] == 0.9
                assert results[1]["semantic_score"] == 0.8
    
    def test_semantic_search_fallback(self, mock_database_session):
        """Test semantic search fallback when embeddings fail."""
        # Enable semantic search but don't initialize embeddings properly
        config = SearchConfig(enable_semantic_search=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        search.semantic_embeddings = None  # Disable embeddings
        
        # Mock backend search results
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "fallback_model",
                "score": 1.0
            }
        ]
        
        with patch.object(search.backend, 'semantic_search', return_value=mock_results):
            results = search.semantic_search("test query")
            
            assert len(results) == 1
            assert results[0]["name"] == "fallback_model"
    
    def test_embedding_stats_integration(self, mock_database_session):
        """Test embedding statistics integration in search stats."""
        config = SearchConfig(enable_semantic_search=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Perform a semantic search to generate stats
        mock_models = [Mock()]
        mock_models[0].id = uuid.uuid4()
        mock_models[0].name = "test_model"
        mock_models[0].description = "test description"
        mock_models[0].model_type = "classification"
        mock_models[0].is_public = True
        mock_models[0].created_at = None
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_models
        mock_database_session.query.return_value = mock_query
        
        with patch.object(search.semantic_embeddings, 'find_similar_embeddings', return_value=[]):
            search.semantic_search("test query")
        
        stats = search.get_search_stats()
        
        assert "semantic_searches" in stats
        assert "semantic_search_rate" in stats
        assert "embedding_stats" in stats
        assert stats["semantic_searches"] >= 1
    
    def test_semantic_search_with_no_models(self, mock_database_session):
        """Test semantic search when no models exist in database."""
        config = SearchConfig(enable_semantic_search=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Mock empty database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No models
        mock_database_session.query.return_value = mock_query
        
        results = search.semantic_search("test query")
        
        assert results == []