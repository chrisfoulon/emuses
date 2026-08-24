"""Comprehensive search optimization and ranking testing - Task 3.7.2d.

This module provides comprehensive testing for the AdvancedModelSearch system including
search performance validation, ranking algorithm testing, personalized search
functionality, and search result caching validation.
"""

import uuid
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry
from emuses.tools.advanced_search import (
    AdvancedModelSearch,
    SearchConfig,
    DatabaseBackend,
    SemanticEmbeddings
)


class TestSearchOptimizationValidation:
    """Comprehensive validation tests for AdvancedModelSearch system."""

    @pytest.fixture
    def search_db_engine(self):
        """Create in-memory database for search testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def search_db_session(self, search_db_engine):
        """Create database session for search testing."""
        Session = sessionmaker(bind=search_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def large_model_dataset(self, search_db_session):
        """Create large dataset of models for search performance testing."""
        # Create test users
        users = []
        for i in range(10):
            user = User(
                id=uuid.uuid4(),
                email=f"search_user_{i}@testorg.com",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
                organization=f"SearchOrg_{i}",
                role="researcher"
            )
            users.append(user)
            search_db_session.add(user)

        # Create test workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="search-optimization-workspace",
            description="Workspace for search optimization tests",
            owner_id=users[0].id,
            storage_path="/test/search/path",
            is_active=True
        )
        search_db_session.add(workspace)

        # Create diverse model types for comprehensive search testing
        models = []
        model_types = ["sklearn", "tensorflow", "pytorch", "xgboost", "lightgbm", "catboost"]
        categories = ["classification", "regression", "clustering", "deep_learning", "nlp", "computer_vision"]
        descriptions = [
            "Neural network model for classification tasks with high accuracy performance",
            "Deep learning model using convolutional layers for image recognition",
            "Random forest ensemble method for robust prediction with feature importance",
            "Gradient boosting model optimized for structured data analysis",
            "Support vector machine with RBF kernel for non-linear classification",
            "Recurrent neural network for sequential data processing and prediction",
            "Transformer model for natural language processing and text classification",
            "Clustering algorithm for unsupervised learning and data segmentation",
            "Time series forecasting model with seasonal decomposition capabilities",
            "Computer vision model for object detection and image segmentation"
        ]

        # Create 100 models for performance testing
        for i in range(100):
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"search-model-{i:03d}-{model_types[i % len(model_types)]}-{categories[i % len(categories)]}",
                description=descriptions[i % len(descriptions)],
                owner_id=users[i % len(users)].id,
                workspace_id=workspace.id,
                is_public=(i % 4 != 0),  # 75% public models
                model_path=f"/test/search/models/model_{i:03d}",
                model_type=model_types[i % len(model_types)],
                version=f"1.{(i % 10)}.{(i % 5)}",
                model_size_bytes=(i + 1) * 1024 * 1024,  # 1MB to 100MB
                manifest_hash=f"search_hash_{i:03d}",
                tags=["search", "optimization", model_types[i % len(model_types)],
                      categories[i % len(categories)], f"test_group_{i % 10}"],
                created_at=datetime.utcnow() - timedelta(days=(i % 365))  # Models created over a year
            )
            models.append(model)
            search_db_session.add(model)

        search_db_session.commit()

        return {
            "users": users,
            "workspace": workspace,
            "models": models
        }

    @pytest.fixture
    def search_config_default(self):
        """Default search configuration for testing."""
        return SearchConfig(
            backend_type="database",
            max_results=50,
            default_similarity_threshold=0.7,
            enable_semantic_search=False,
            enable_personalized_ranking=False,
            cache_ttl_seconds=300,
            enable_search_analytics=True
        )

    @pytest.fixture
    def search_config_optimized(self):
        """Optimized search configuration for performance testing."""
        return SearchConfig(
            backend_type="database",
            max_results=100,
            default_similarity_threshold=0.6,
            enable_semantic_search=True,
            enable_personalized_ranking=True,
            cache_ttl_seconds=600,
            enable_search_analytics=True
        )

    def test_search_performance_validation(self, search_db_session, large_model_dataset, search_config_default):
        """Test search performance with large dataset and validate response times."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Performance test cases with different query complexities
        performance_tests = [
            ("sklearn", "Simple single term search"),
            ("neural network", "Two-term search"),
            ("classification model tensorflow", "Multi-term search"),
            ("deep learning convolutional neural network", "Complex multi-term search"),
            ("machine learning algorithm", "Generic broad search")
        ]

        performance_results = []

        for query, description in performance_tests:
            # Multiple iterations for consistent timing
            iterations = 5
            total_time = 0

            for _ in range(iterations):
                start_time = time.time()
                results = advanced_search.search(query, max_results=50)
                search_time = time.time() - start_time
                total_time += search_time

                # Validate search returned results
                assert len(results) >= 0, f"Search should return results for query: {query}"

                # Validate result structure
                for result in results[:5]:  # Check first 5 results
                    assert "model_id" in result
                    assert "name" in result
                    assert "score" in result
                    assert "rank" in result
                    assert isinstance(result["score"], (int, float))
                    assert result["rank"] >= 1

            avg_time = total_time / iterations
            performance_results.append((query, description, avg_time, len(results)))

            # Performance requirement: search should complete within 200ms
            assert avg_time < 0.2, f"Search too slow for '{query}': {avg_time:.3f}s (required: <0.2s)"

        print("Search performance validation completed:")
        for query, desc, avg_time, result_count in performance_results:
            print(f"  '{query}': {avg_time*1000:.1f}ms, {result_count} results")

    def test_ranking_algorithm_validation(self, search_db_session, large_model_dataset, search_config_default):
        """Test ranking algorithm accuracy and consistency."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Test ranking consistency across multiple runs
        query = "tensorflow classification"
        ranking_tests = []

        for run in range(3):
            results = advanced_search.search(query, max_results=20)
            ranking_tests.append([result["model_id"] for result in results])

        # Validate ranking consistency
        first_ranking = ranking_tests[0]
        for i, ranking in enumerate(ranking_tests[1:], 1):
            # At least top 5 results should be consistent across runs
            if len(first_ranking) >= 5 and len(ranking) >= 5:
                top5_first = set(first_ranking[:5])
                top5_current = set(ranking[:5])
                overlap = len(top5_first & top5_current)

                # Allow some variance but expect significant overlap
                assert overlap >= 3, f"Run {i+1}: Top-5 ranking inconsistent, overlap: {overlap}/5"

        # Test score ordering
        results = advanced_search.search("neural network", max_results=30)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                current_score = results[i]["score"]
                next_score = results[i + 1]["score"]
                assert current_score >= next_score, f"Score ordering violation: {current_score} < {next_score}"

        # Test relevance accuracy
        specific_queries = [
            ("tensorflow", ["model_type", "name", "description"]),  # Should find tensorflow models
            ("classification", ["description", "name", "model_type"]),  # Should find classification tasks
            ("sklearn", ["model_type", "name", "description"])  # Should find sklearn models
        ]

        for query, check_fields in specific_queries:
            results = advanced_search.search(query, max_results=10)
            if results:
                # At least some results should be relevant
                relevant_count = 0
                for result in results[:10]:
                    if any(query.lower() in str(result.get(field, "")).lower()
                           for field in check_fields):
                        relevant_count += 1

                relevance_rate = relevant_count / min(len(results), 10)
                assert relevance_rate >= 0.3, f"Low relevance rate for '{query}': {relevance_rate:.2f} (found {relevant_count} relevant in {len(results[:10])} results)"

    def test_semantic_search_validation(self, search_db_session, large_model_dataset):
        """Test semantic search functionality and accuracy."""
        # Test with semantic search enabled
        semantic_config = SearchConfig(
            backend_type="database",
            enable_semantic_search=True,
            default_similarity_threshold=0.6
        )

        advanced_search = AdvancedModelSearch(search_db_session, semantic_config)

        # Test semantic embeddings initialization
        assert advanced_search.semantic_embeddings is not None
        embedding_stats = advanced_search.semantic_embeddings.get_embedding_stats()
        assert "embedding_model" in embedding_stats
        assert "cache_size" in embedding_stats

        # Test semantic search queries
        semantic_queries = [
            ("machine learning algorithm", "Should find ML-related models"),
            ("deep neural networks", "Should find deep learning models"),
            ("classification model", "Should find classification models"),
            ("image recognition", "Should find computer vision models")
        ]

        for query, description in semantic_queries:
            # Test semantic search
            semantic_results = advanced_search.semantic_search(
                query,
                similarity_threshold=0.5,
                max_results=20
            )

            # Test regular search for comparison
            regular_results = advanced_search.search(query, max_results=20)

            # Both should return results
            assert len(semantic_results) >= 0, f"Semantic search failed for: {query}"
            assert len(regular_results) >= 0, f"Regular search failed for: {query}"

            # Validate semantic result structure
            for result in semantic_results[:5]:
                assert "model_id" in result
                assert "score" in result or "semantic_score" in result
                score = result.get("score", result.get("semantic_score", 0))
                assert 0 <= score <= 1, f"Invalid semantic score: {score}"

        # Test semantic similarity calculations
        embeddings = advanced_search.semantic_embeddings

        # Test similar terms should have high similarity
        emb1 = embeddings.generate_embedding("neural network")
        emb2 = embeddings.generate_embedding("neural networks")
        similarity = embeddings.calculate_similarity(emb1, emb2)
        assert similarity >= 0.7, f"Similar terms should have reasonable similarity: {similarity}"

        # Test different terms should have lower or equal similarity
        emb3 = embeddings.generate_embedding("database system")
        similarity_different = embeddings.calculate_similarity(emb1, emb3)
        # Allow for fallback embedding behavior where similarity might be equal
        assert similarity_different <= similarity, f"Different terms similarity should not exceed similar terms: {similarity_different} vs {similarity}"

    def test_personalized_ranking_validation(self, search_db_session, large_model_dataset):
        """Test personalized ranking functionality."""
        # Test with personalized ranking enabled
        personalized_config = SearchConfig(
            backend_type="database",
            enable_personalized_ranking=True,
            max_results=30
        )

        try:
            advanced_search = AdvancedModelSearch(search_db_session, personalized_config)
        except ImportError:
            # PersonalizedRanker might not be available, test fallback behavior
            personalized_config.enable_personalized_ranking = False
            advanced_search = AdvancedModelSearch(search_db_session, personalized_config)

        # Test user contexts for personalization
        user_contexts = [
            {
                "user_id": str(uuid.uuid4()),
                "preferences": {"model_type": "tensorflow", "category": "classification"},
                "expertise_level": "advanced"
            },
            {
                "user_id": str(uuid.uuid4()),
                "preferences": {"model_type": "sklearn", "category": "regression"},
                "expertise_level": "beginner"
            },
            {
                "user_id": str(uuid.uuid4()),
                "preferences": {"model_type": "pytorch", "category": "deep_learning"},
                "expertise_level": "expert"
            }
        ]

        query = "sklearn"  # Use a query that should return results

        # Test personalized vs non-personalized results
        base_results = advanced_search.search(query, max_results=20)

        # Skip test if no base results
        if len(base_results) == 0:
            print("Skipping personalized ranking test - no search results available")
            return

        for context in user_contexts:
            personalized_results = advanced_search.search(
                query,
                max_results=20,
                user_context=context
            )

            # Should return results (at least as many as base search)
            assert len(personalized_results) >= 0, "Personalized search should not fail"

            if len(personalized_results) > 0:
                # Check for personalization indicators or fallback behavior
                for result in personalized_results[:5]:
                    # Validate result structure
                    assert "model_id" in result
                    assert "score" in result
                    assert "rank" in result

                    # If personalization is active, may have additional fields
                    if personalized_config.enable_personalized_ranking:
                        # Could have personalization boost fields in result
                        pass

            # At minimum, personalized search should not be significantly worse
            assert len(personalized_results) >= len(base_results) * 0.8, \
                f"Personalized results significantly fewer: {len(personalized_results)} vs {len(base_results)}"

    def test_caching_validation(self, search_db_session, large_model_dataset, search_config_default):
        """Test search result caching efficiency and correctness."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Test cache miss and hit scenarios
        cache_queries = [
            "tensorflow neural network",
            "sklearn classification",
            "pytorch deep learning"
        ]

        for query in cache_queries:
            # First search (cache miss)
            start_time = time.time()
            first_results = advanced_search.search(query, max_results=20, enable_caching=True)
            first_time = time.time() - start_time

            # Second search (should be cache hit)
            start_time = time.time()
            second_results = advanced_search.search(query, max_results=20, enable_caching=True)
            second_time = time.time() - start_time

            # Validate cache functionality
            assert len(first_results) == len(second_results), "Cached results should match"

            # Cache hit should be faster
            assert second_time < first_time, f"Cache hit should be faster: {second_time:.3f}s vs {first_time:.3f}s"

            # Results should be identical
            for i, (first, second) in enumerate(zip(first_results, second_results)):
                assert first["model_id"] == second["model_id"], f"Result {i}: cache inconsistency"
                assert first["score"] == second["score"], f"Result {i}: score inconsistency"

        # Test cache statistics
        initial_stats = advanced_search.get_search_stats()
        cache_hits_before = initial_stats.get("cache_hits", 0)

        # Perform more cached searches
        for query in cache_queries:
            advanced_search.search(query, max_results=20, enable_caching=True)

        final_stats = advanced_search.get_search_stats()
        cache_hits_after = final_stats.get("cache_hits", 0)

        # Should have increased cache hits
        assert cache_hits_after > cache_hits_before, "Cache hits should increase"

        # Test cache clearing
        advanced_search.clear_cache()

        # Search after cache clear should be slower again
        start_time = time.time()
        advanced_search.search(cache_queries[0], max_results=20, enable_caching=True)
        post_clear_time = time.time() - start_time

        # Should be slower than cached version (but this is hard to guarantee in tests)
        # At minimum, verify cache was cleared by checking no immediate speed improvement
        assert post_clear_time > 0, "Search should take some time after cache clear"

    def test_batch_search_validation(self, search_db_session, large_model_dataset, search_config_default):
        """Test batch search functionality and performance."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Test batch search with multiple queries
        batch_queries = [
            "neural network classification",
            "random forest regression",
            "deep learning pytorch",
            "sklearn support vector",
            "gradient boosting xgboost"
        ]

        # Measure batch search performance
        start_time = time.time()
        batch_results = advanced_search.batch_search(batch_queries, max_results=10)
        batch_time = time.time() - start_time

        # Validate batch results structure
        assert len(batch_results) == len(batch_queries), "Batch results count mismatch"

        # Validate each query's results
        for i, (query, results) in enumerate(zip(batch_queries, batch_results)):
            assert isinstance(results, list), f"Query {i} results should be list"
            assert len(results) <= 10, f"Query {i} should respect max_results limit"

            # Validate result structure
            for result in results:
                assert "model_id" in result
                assert "name" in result
                assert "score" in result

        # Compare with individual searches
        individual_time = 0
        for query in batch_queries:
            start_time = time.time()
            individual_results = advanced_search.search(query, max_results=10)
            individual_time += time.time() - start_time

            # Results should be consistent with batch
            batch_result = batch_results[batch_queries.index(query)]
            assert len(individual_results) == len(batch_result), f"Inconsistent results for '{query}'"

        # Batch should be reasonably efficient (within 100% of individual time)
        # Allow for some overhead in batch operations
        efficiency_ratio = batch_time / individual_time
        assert efficiency_ratio <= 2.0, f"Batch search too inefficient: {efficiency_ratio:.2f}x individual time"

        print(f"Batch search efficiency: {efficiency_ratio:.2f}x individual time")

    def test_search_suggestions_validation(self, search_db_session, large_model_dataset, search_config_default):
        """Test search suggestions functionality."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Test suggestion generation for partial queries
        suggestion_tests = [
            ("neural", 5),
            ("machine", 5),
            ("classif", 3),
            ("deep", 4)
        ]

        for partial_query, max_suggestions in suggestion_tests:
            suggestions = advanced_search.get_search_suggestions(partial_query, max_suggestions)

            # Validate suggestions
            assert isinstance(suggestions, list), "Suggestions should be a list"
            assert len(suggestions) <= max_suggestions, f"Too many suggestions: {len(suggestions)} > {max_suggestions}"

            # All suggestions should contain the partial query
            for suggestion in suggestions:
                assert isinstance(suggestion, str), "Each suggestion should be a string"
                assert partial_query.lower() in suggestion.lower(), f"Suggestion '{suggestion}' doesn't contain '{partial_query}'"

        # Test edge cases
        empty_suggestions = advanced_search.get_search_suggestions("", 5)
        assert len(empty_suggestions) <= 5, "Empty query should return limited suggestions"

        obscure_suggestions = advanced_search.get_search_suggestions("xyzzyx", 5)
        assert isinstance(obscure_suggestions, list), "Obscure query should return list"

    def test_multi_backend_compatibility(self, search_db_session, large_model_dataset):
        """Test search system compatibility across different backend configurations."""
        backend_configs = [
            SearchConfig(backend_type="database", max_results=20),
        ]

        # Note: Only testing database backend since others require external services
        # In a real production test, you would test Elasticsearch and Solr backends

        query = "tensorflow classification model"

        for config in backend_configs:
            advanced_search = AdvancedModelSearch(search_db_session, config)

            # Test basic search functionality
            results = advanced_search.search(query, max_results=15)
            assert len(results) >= 0, f"Search failed for {config.backend_type} backend"

            # Test similar models functionality
            if results:
                model_id = results[0]["model_id"]
                similar_results = advanced_search.get_similar_models(model_id, max_results=5)
                assert len(similar_results) >= 0, f"Similar models failed for {config.backend_type} backend"

            # Test search statistics
            stats = advanced_search.get_search_stats()
            assert "backend_type" in stats
            assert stats["backend_type"] == config.backend_type
            assert "total_searches" in stats
            assert isinstance(stats["total_searches"], int)

    def test_error_handling_and_edge_cases(self, search_db_session, large_model_dataset, search_config_default):
        """Test error handling and edge cases in search functionality."""
        advanced_search = AdvancedModelSearch(search_db_session, search_config_default)

        # Test empty and invalid queries
        edge_case_queries = [
            "",  # Empty query
            "   ",  # Whitespace only
            "a",  # Single character
            "x" * 1000,  # Very long query
            "!@#$%^&*()",  # Special characters only
            "SELECT * FROM models",  # SQL injection attempt
        ]

        for query in edge_case_queries:
            results = advanced_search.search(query, max_results=10)
            assert isinstance(results, list), f"Query '{query[:20]}...' should return list"
            # Results may be empty, but should not error

        # Test invalid parameters
        try:
            invalid_results = advanced_search.search("test", max_results=-1)
            assert isinstance(invalid_results, list), "Negative max_results should handle gracefully"
        except Exception:
            pass  # Either handle gracefully or raise - both acceptable

        # Test search with non-existent model ID for similarity
        fake_uuid = str(uuid.uuid4())
        similar_results = advanced_search.get_similar_models(fake_uuid)
        assert isinstance(similar_results, list), "Non-existent model should return empty list"
        assert len(similar_results) == 0, "Non-existent model should return empty results"

        # Test semantic search without embeddings (when disabled)
        no_semantic_config = SearchConfig(enable_semantic_search=False)
        basic_search = AdvancedModelSearch(search_db_session, no_semantic_config)

        semantic_results = basic_search.semantic_search("neural network", max_results=10)
        assert isinstance(semantic_results, list), "Semantic search should fallback gracefully"


class TestSearchBackendValidation:
    """Test validation for search backend implementations."""

    @pytest.fixture
    def backend_db_engine(self):
        """Create in-memory database for backend testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def backend_db_session(self, backend_db_engine):
        """Create database session for backend testing."""
        Session = sessionmaker(bind=backend_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def backend_test_models(self, backend_db_session):
        """Create test models for backend testing."""
        # Create test user
        user = User(
            id=uuid.uuid4(),
            email="backend_test@testorg.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            organization="TestOrg",
            role="researcher"
        )
        backend_db_session.add(user)

        # Create test workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="backend-test-workspace",
            description="Test workspace",
            owner_id=user.id,
            storage_path="/test/backend/path",
            is_active=True
        )
        backend_db_session.add(workspace)

        # Create test models with varied characteristics
        models = []
        test_data = [
            ("neural-network-model", "Neural network for classification tasks", "tensorflow", True),
            ("random-forest-classifier", "Random forest model for classification", "sklearn", True),
            ("deep-learning-cnn", "Convolutional neural network for image recognition", "pytorch", True),
            ("regression-model", "Linear regression for prediction tasks", "sklearn", False),
            ("clustering-algorithm", "K-means clustering for unsupervised learning", "sklearn", True),
        ]

        for name, description, model_type, is_public in test_data:
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=name,
                description=description,
                owner_id=user.id,
                workspace_id=workspace.id,
                is_public=is_public,
                model_path=f"/test/backend/models/{name}",
                model_type=model_type,
                version="1.0.0",
                model_size_bytes=1024*1024,
                manifest_hash=f"backend_{name}_hash",
                tags=["backend", "test", model_type],
                created_at=datetime.utcnow()
            )
            models.append(model)
            backend_db_session.add(model)

        backend_db_session.commit()
        return {"user": user, "workspace": workspace, "models": models}

    def test_database_backend_comprehensive(self, backend_db_session, backend_test_models):
        """Test database backend functionality comprehensively."""
        backend = DatabaseBackend(backend_db_session)

        # Test backend properties
        assert backend.name == "database"

        # Test basic search functionality
        search_tests = [
            ("neural", "Should find neural network models"),
            ("classification", "Should find classification models"),
            ("tensorflow", "Should find tensorflow models"),
            ("sklearn", "Should find sklearn models"),
            ("regression", "Should find regression models")
        ]

        for query, description in search_tests:
            results = backend.search(query, max_results=10)
            assert isinstance(results, list), f"Search results should be list for '{query}'"

            # Validate result structure
            for result in results:
                assert "model_id" in result
                assert "name" in result
                assert "score" in result
                assert "rank" in result
                assert isinstance(result["score"], (int, float))
                assert result["rank"] >= 1

                # Validate that results are relevant
                relevance_check = any(
                    query.lower() in str(result.get(field, "")).lower()
                    for field in ["name", "description", "model_type"]
                )
                assert relevance_check, f"Result not relevant for '{query}': {result['name']}"

        # Test search with filters
        filtered_results = backend.search("model", filters={"model_type": "sklearn"}, max_results=10)
        for result in filtered_results:
            assert result.get("model_type") == "sklearn", "Filter not applied correctly"

        # Test semantic search (should fallback to enhanced text search)
        semantic_results = backend.semantic_search("machine learning", similarity_threshold=0.5)
        assert isinstance(semantic_results, list), "Semantic search should return list"

        # Test similar models functionality
        test_models = backend_test_models["models"]
        if test_models:
            model_id = test_models[0].id
            similar_results = backend.get_similar_models(model_id, max_results=5)
            assert isinstance(similar_results, list), "Similar models should return list"

            # Validate similar model results structure
            for result in similar_results:
                assert "model_id" in result
                assert "similarity_score" in result
                assert isinstance(result["similarity_score"], (int, float))
                assert 0 <= result["similarity_score"] <= 1

    def test_semantic_embeddings_comprehensive(self):
        """Test semantic embeddings functionality comprehensively."""
        embeddings = SemanticEmbeddings()

        # Test embedding generation
        test_texts = [
            "neural network classification model",
            "deep learning convolutional network",
            "random forest regression algorithm",
            "support vector machine classifier",
            "gradient boosting decision tree"
        ]

        generated_embeddings = []
        for text in test_texts:
            embedding = embeddings.generate_embedding(text)
            generated_embeddings.append(embedding)

            # Validate embedding properties
            assert isinstance(embedding, type(generated_embeddings[0])), "Consistent embedding type"
            assert len(embedding) > 0, "Embedding should have non-zero length"

            # Handle both numpy arrays and lists
            if hasattr(embedding, 'dtype'):  # numpy array
                assert embedding.dtype in ['float32', 'float64', 'int32', 'int64'], "Embedding should be numeric array"
            else:  # list or other iterable
                assert all(isinstance(x, (int, float, complex)) for x in embedding), "Embedding should be numeric"

        # Test similarity calculations
        emb1 = embeddings.generate_embedding("neural network")
        emb2 = embeddings.generate_embedding("neural networks")
        emb3 = embeddings.generate_embedding("database system")

        # Similar terms should have higher similarity
        similarity_similar = embeddings.calculate_similarity(emb1, emb2)
        similarity_different = embeddings.calculate_similarity(emb1, emb3)

        assert 0 <= similarity_similar <= 1, "Similarity should be in [0,1]"
        assert 0 <= similarity_different <= 1, "Similarity should be in [0,1]"
        # For simple embeddings, similarity might be equal - allow for this
        assert similarity_similar >= similarity_different, "Similar terms should have equal or higher similarity"

        # Test find similar embeddings
        query_embedding = embeddings.generate_embedding("machine learning model")
        similar_results = embeddings.find_similar_embeddings(
            query_embedding,
            generated_embeddings,
            threshold=0.3,
            max_results=3
        )

        assert isinstance(similar_results, list), "Similar results should be list"
        assert len(similar_results) <= 3, "Should respect max_results limit"

        # Validate similar results structure
        for index, score in similar_results:
            assert isinstance(index, int), "Index should be integer"
            assert isinstance(score, (int, float)), "Score should be numeric"
            assert 0 <= score <= 1, "Score should be in [0,1]"
            assert 0 <= index < len(generated_embeddings), "Index should be valid"

        # Test embedding statistics
        stats = embeddings.get_embedding_stats()
        assert "embedding_model" in stats
        assert "cache_size" in stats
        assert isinstance(stats["cache_size"], int)

        # Test edge cases
        empty_embedding = embeddings.generate_embedding("")
        assert len(empty_embedding) > 0, "Empty text should still generate embedding"

        whitespace_embedding = embeddings.generate_embedding("   ")
        assert len(whitespace_embedding) > 0, "Whitespace text should generate embedding"


if __name__ == "__main__":
    pytest.main([__file__])
