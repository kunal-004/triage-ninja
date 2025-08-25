import logging
from typing import Dict, Any, List, Optional, Tuple

import weaviate
import google.generativeai as genai
from portia import ToolRunContext
from portia.tool import Tool
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


class WeaviateManager:
    """Enhanced Weaviate manager with improved duplicate detection."""
    
    def __init__(self):
        self._setup_weaviate()
        self._setup_embeddings()
    
    def _setup_weaviate(self):
        """Initialize Weaviate client with proper schema setup."""
        try:
            if not config.WEAVIATE_API_KEY or not config.WEAVIATE_URL:
                logger.warning("Weaviate credentials not configured, using mock functionality")
                self.client = None
                return
            
            import weaviate.classes as wvc
            
            # Use the newer weaviate v4 API
            self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=config.WEAVIATE_URL,
                auth_credentials=wvc.init.Auth.api_key(config.WEAVIATE_API_KEY),
                headers={"X-Google-Api-Key": config.GEMINI_API_KEY}
            )
            
            # Test connection and setup schema
            if self.client.is_ready():
                self._ensure_schema_exists()
                logger.info("✅ WeaviateManager: Successfully connected to Weaviate")
            else:
                logger.warning("⚠️ WeaviateManager: Weaviate connection not ready, using mock functionality")
                self.client = None
                
        except Exception as e:
            logger.error(f"WeaviateManager: Failed to connect to Weaviate: {e}")
            logger.info("Continuing with mock duplicate detection functionality")
            self.client = None

    def _setup_embeddings(self):
        """Initialize Gemini for embeddings."""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            logger.info("WeaviateManager: Configured Gemini for embeddings")
        except Exception as e:
            logger.error(f"WeaviateManager: Failed to configure embeddings: {e}")
            raise
    
    def _ensure_schema_exists(self):
        """Ensure the GitHubIssue schema exists with all required properties."""
        if not self.client:
            return
            
        try:
            import weaviate.classes as wvc
            from weaviate.classes.config import Property, DataType
            
            # Check if collection exists and validate schema
            try:
                collection = self.client.collections.get("GitHubIssue")
                
                # Try a test insert to check if schema is correct
                try:
                    # Test with minimal data
                    test_embedding = [0.1] * 768  # Dummy embedding
                    collection.data.insert(
                        properties={
                            "title": "test",
                            "body": "test body",
                            "issue_number": 999999,  # Use a number that won't conflict
                            "embedding_text": "test"
                        },
                        vector=test_embedding
                    )
                    # If this works, delete the test entry
                    logger.info("WeaviateManager: Schema validation successful")
                    # TODO: Could delete test entry here if needed
                    return
                    
                except Exception as schema_error:
                    if "no such prop with name 'issue_number'" in str(schema_error):
                        logger.warning("WeaviateManager: Existing schema is incompatible, recreating collection")
                        # Delete the existing collection
                        self.client.collections.delete("GitHubIssue")
                        logger.info("WeaviateManager: Deleted incompatible GitHubIssue collection")
                    else:
                        logger.warning(f"WeaviateManager: Schema validation failed: {schema_error}")
                        return  # Don't recreate for other errors
                        
            except Exception as get_error:
                # Collection doesn't exist, which is fine
                logger.info("WeaviateManager: GitHubIssue collection doesn't exist, will create it")
                
            # Create the collection with correct schema
            logger.info("WeaviateManager: Creating GitHubIssue collection with proper schema")
            
            self.client.collections.create(
                name="GitHubIssue",
                description="GitHub issue vectors for duplicate detection",
                properties=[
                    Property(name="title", data_type=DataType.TEXT, description="Issue title"),
                    Property(name="body", data_type=DataType.TEXT, description="Issue body content"),
                    Property(name="issue_number", data_type=DataType.INT, description="GitHub issue number"),
                    Property(name="embedding_text", data_type=DataType.TEXT, description="Combined text for embedding"),
                ],
                vectorizer_config=wvc.config.Configure.Vectorizer.none(),  # We'll provide our own vectors
            )
            logger.info("✅ WeaviateManager: Created GitHubIssue collection with proper schema")
            
        except Exception as e:
            logger.error(f"WeaviateManager: Failed to ensure schema exists: {e}")
            logger.info("Continuing with existing schema or fallback functionality")
    
    def find_duplicate(self, title: str, body: str, threshold: float = 0.85) -> Tuple[Optional[int], Optional[float]]:
        """
        Find duplicate issues with enhanced context.
        
        Args:
            title: Issue title
            body: Issue body
            threshold: Similarity threshold
            
        Returns:
            Tuple of (duplicate_issue_id, similarity_score) or (None, None) if no duplicate
        """
        try:
            if not self.client:
                # Enhanced mock duplicate detection for demo purposes
                logger.info("Using enhanced mock duplicate detection (Weaviate not available)")
                
                # Simulate storing issues in a simple in-memory store for demo
                if not hasattr(self, '_mock_issues'):
                    self._mock_issues = []
                
                # Simple text similarity check for exact or near-exact matches
                search_text = f"{title.lower()} {body.lower()}"
                for stored_issue in self._mock_issues:
                    stored_text = f"{stored_issue['title'].lower()} {stored_issue['body'].lower()}"
                    
                    # Calculate simple word overlap similarity
                    search_words = set(search_text.split())
                    stored_words = set(stored_text.split())
                    
                    if len(search_words) > 0 and len(stored_words) > 0:
                        intersection = len(search_words & stored_words)
                        union = len(search_words | stored_words)
                        similarity = intersection / union
                        
                        if similarity >= threshold:
                            logger.warning(f"Mock duplicate detected: Issue similar to #{stored_issue['issue_id']} (Similarity: {similarity:.1%})")
                            return stored_issue['issue_id'], similarity
                
                # Check for exact title matches (high likelihood of duplicate)
                for stored_issue in self._mock_issues:
                    if title.strip().lower() == stored_issue['title'].strip().lower():
                        logger.warning(f"Mock duplicate detected: Exact title match with issue #{stored_issue['issue_id']}")
                        return stored_issue['issue_id'], 0.95
                
                return None, None
            
            # Create embedding for search
            embedding_text = f"{title}\n\n{body}"
            
            try:
                embedding_response = genai.embed_content(
                    model="models/text-embedding-004", 
                    content=embedding_text,
                    output_dimensionality=768
                )
            except Exception as embed_error:
                logger.warning(f"Embedding generation failed: {embed_error}")
                # Fall back to simple text matching
                return self._fallback_text_similarity(title, body, threshold)
            
            # Search for similar issues using Weaviate v4 API
            try:
                import weaviate.classes as wvc
                collection = self.client.collections.get("GitHubIssue")
                response = collection.query.near_vector(
                    near_vector=embedding_response['embedding'],
                    limit=5,
                    return_metadata=wvc.query.MetadataQuery(certainty=True)
                )
                
                # Process results
                for obj in response.objects:
                    certainty = obj.metadata.certainty
                    if certainty >= threshold:
                        return obj.properties["issue_number"], certainty
            except ImportError:
                # Fall back to older API if available
                logger.warning("Using fallback Weaviate API")
                results = self.client.query.get(
                    "GitHubIssue", 
                    ["title", "body", "issue_number"]
                ).with_near_vector({
                    "vector": embedding_response['embedding']
                }).with_limit(5).with_additional(["certainty"]).do()
                
                if results.get("data", {}).get("Get", {}).get("GitHubIssue"):
                    issues = results["data"]["Get"]["GitHubIssue"]
                    for issue in issues:
                        certainty = issue["_additional"]["certainty"]
                        if certainty >= threshold:
                            return issue["issue_number"], certainty
            
            return None, None
            
        except Exception as e:
            logger.error(f"WeaviateManager: Duplicate search failed: {e}")
            # Fallback to text-based similarity
            return self._fallback_text_similarity(title, body, threshold)
    
    def _fallback_text_similarity(self, title: str, body: str, threshold: float) -> Tuple[Optional[int], Optional[float]]:
        """Fallback text-based similarity when embedding fails."""
        try:
            if hasattr(self, '_mock_issues'):
                search_text = f"{title.lower()} {body.lower()}"
                for stored_issue in self._mock_issues:
                    stored_text = f"{stored_issue['title'].lower()} {stored_issue['body'].lower()}"
                    
                    # Calculate simple word overlap similarity
                    search_words = set(search_text.split())
                    stored_words = set(stored_text.split())
                    
                    if len(search_words) > 0 and len(stored_words) > 0:
                        intersection = len(search_words & stored_words)
                        union = len(search_words | stored_words)
                        similarity = intersection / union
                        
                        if similarity >= threshold:
                            return stored_issue['issue_id'], similarity
        except Exception as e:
            logger.error(f"Fallback text similarity failed: {e}")
        
        return None, None
    
    def add_issue(self, issue_id: int, title: str, body: str):
        """Add issue to Weaviate database after human confirmation."""
        try:
            if not self.client:
                # Initialize mock storage if not exists
                if not hasattr(self, '_mock_issues'):
                    self._mock_issues = []
                
                # Add to mock storage for duplicate detection
                self._mock_issues.append({
                    'issue_id': issue_id,
                    'title': title,
                    'body': body
                })
                logger.info(f"Mock: Added issue #{issue_id} to knowledge base (Weaviate not available)")
                return
            
            # Create embedding text
            embedding_text = f"{title}\n\n{body}"
            
            try:
                # Generate embedding using Gemini
                embedding_response = genai.embed_content(
                    model="models/text-embedding-004",
                    content=embedding_text,
                    output_dimensionality=768
                )
            except Exception as embed_error:
                logger.warning(f"Embedding generation failed: {embed_error}, using mock storage")
                # Fall back to mock storage
                if not hasattr(self, '_mock_issues'):
                    self._mock_issues = []
                self._mock_issues.append({
                    'issue_id': issue_id,
                    'title': title,
                    'body': body
                })
                logger.info(f"Mock fallback: Added issue #{issue_id} to knowledge base")
                return
            
            # Add to Weaviate using v4 API
            try:
                collection = self.client.collections.get("GitHubIssue")
                collection.data.insert(
                    properties={
                        "title": title,
                        "body": body,
                        "issue_number": issue_id,
                        "embedding_text": embedding_text,
                    },
                    vector=embedding_response['embedding']
                )
                logger.info(f"WeaviateManager: Added confirmed issue #{issue_id} to vector database")
                
            except Exception as v4_error:
                logger.warning(f"WeaviateManager: V4 API failed: {v4_error}")
                # Use mock storage as fallback
                if not hasattr(self, '_mock_issues'):
                    self._mock_issues = []
                self._mock_issues.append({
                    'issue_id': issue_id,
                    'title': title,
                    'body': body
                })
                logger.info(f"Mock fallback: Added issue #{issue_id} to knowledge base")
            
        except Exception as e:
            logger.error(f"WeaviateManager: Failed to add issue to database: {e}")
            # Always fall back to mock storage
            if not hasattr(self, '_mock_issues'):
                self._mock_issues = []
            self._mock_issues.append({
                'issue_id': issue_id,
                'title': title,
                'body': body
            })
            logger.info(f"Mock fallback: Added issue #{issue_id} to knowledge base")


# Global WeaviateManager instance
weaviate_manager = WeaviateManager()


class DuplicateCheckSchema(BaseModel):
    """Input schema for duplicate detection."""
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")
    threshold: float = Field(default=0.85, description="Similarity threshold (0.0-1.0)")

class AddIssueSchema(BaseModel):
    """Input schema for adding issues to Weaviate."""
    issue_id: int = Field(..., description="GitHub issue ID")
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")


class EnhancedDuplicateDetectionTool(Tool[str]):
    """Enhanced tool for detecting duplicate GitHub issues."""
    
    id: str = "enhanced_duplicate_detection_tool"
    name: str = "Enhanced Duplicate Detection Tool"
    description: str = "Detects duplicate GitHub issues using vector similarity search with enhanced UX"
    args_schema: type[BaseModel] = DuplicateCheckSchema

    def run(self, context: ToolRunContext, title: str, body: str, threshold: float = 0.85) -> str:
        """
        Check for duplicate issues with enhanced context.
        
        Args:
            context: Portia tool run context
            title: Issue title
            body: Issue body
            threshold: Similarity threshold
            
        Returns:
            Duplicate detection results with similarity score
        """
        try:
            duplicate_id, similarity_score = weaviate_manager.find_duplicate(title, body, threshold)
            
            if duplicate_id and similarity_score:
                result = f"DUPLICATE_FOUND|{duplicate_id}|{similarity_score:.3f}"
                logger.warning(f"Duplicate detected: Issue similar to #{duplicate_id} (Similarity: {similarity_score:.1%})")
            else:
                result = "NO_DUPLICATE_FOUND"
                logger.info(f"No duplicates found for issue: '{title}'")
            
            return result
            
        except Exception as e:
            error_msg = f"Duplicate detection failed: {e}"
            logger.error(error_msg)
            return f"ERROR|{error_msg}"


class AddIssueTool(Tool[str]):
    """Tool for adding confirmed issues to Weaviate database."""
    
    id: str = "add_issue_tool"
    name: str = "Add Issue Tool"
    description: str = "Adds confirmed non-duplicate issues to the vector database"
    args_schema: type[BaseModel] = AddIssueSchema

    def run(self, context: ToolRunContext, issue_id: int, title: str, body: str) -> str:
        """Add confirmed issue to Weaviate database."""
        try:
            weaviate_manager.add_issue(issue_id, title, body)
            return f"Successfully added issue #{issue_id} to knowledge base"
        except Exception as e:
            error_msg = f"Failed to add issue #{issue_id} to database: {e}"
            logger.error(error_msg)
            return error_msg

