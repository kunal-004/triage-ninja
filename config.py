"""
Configuration module for Support-Triage Ninja.
Loads environment variables and provides them as constants.
Built for AgentHack 2025 with Portia AI framework.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Portia AI Configuration
PORTIA_API_KEY: str = os.getenv("PORTIA_API_KEY", "")

# Google Gemini Configuration
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# GitHub Configuration
GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

# Discord Configuration
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID: str = os.getenv("DISCORD_CHANNEL_ID", "")
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# Weaviate Vector Database Configuration  
WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "")
WEAVIATE_API_KEY: str = os.getenv("WEAVIATE_API_KEY", "")

# Webhook Security
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# Flask Configuration
FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"

def validate_config() -> None:
    """Validate that all required environment variables are set."""
    required_vars = [
        ("PORTIA_API_KEY", PORTIA_API_KEY),
        ("GEMINI_API_KEY", GEMINI_API_KEY),
        ("GITHUB_REPO", GITHUB_REPO),
        ("GITHUB_TOKEN", GITHUB_TOKEN),
        ("DISCORD_BOT_TOKEN", DISCORD_BOT_TOKEN),
        ("DISCORD_CHANNEL_ID", DISCORD_CHANNEL_ID),
        ("WEAVIATE_URL", WEAVIATE_URL),
        ("WEAVIATE_API_KEY", WEAVIATE_API_KEY),
        ("GITHUB_WEBHOOK_SECRET", GITHUB_WEBHOOK_SECRET),
    ]
    
    missing_vars = [var_name for var_name, var_value in required_vars if not var_value]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

if __name__ == "__main__":
    try:
        validate_config()
        print("Configuration validation passed!")
    except ValueError as e:
        print(f"Configuration validation failed: {e}")

class Config:
    """Configuration class for the application."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load environment variables from .env file
        load_dotenv()
        
        # Store all config as instance variables
        self.PORTIA_API_KEY = PORTIA_API_KEY
        self.GEMINI_API_KEY = GEMINI_API_KEY
        self.GITHUB_REPO = GITHUB_REPO
        self.GITHUB_TOKEN = GITHUB_TOKEN
        self.DISCORD_BOT_TOKEN = DISCORD_BOT_TOKEN
        self.DISCORD_CHANNEL_ID = DISCORD_CHANNEL_ID
        self.WEAVIATE_URL = WEAVIATE_URL
        self.WEAVIATE_API_KEY = WEAVIATE_API_KEY
        self.WEBHOOK_SECRET = WEBHOOK_SECRET
    
    def validate_required(self):
        """Validate that all required config is present."""
        validate_config()
    
    def has_api_keys(self) -> bool:
        """Check if basic API keys are available."""
        return bool(self.GEMINI_API_KEY and self.GITHUB_TOKEN)
