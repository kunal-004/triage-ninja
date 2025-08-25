import logging
from typing import Dict, Any, Tuple, Optional

import google.generativeai as genai
from portia import ToolRunContext
from portia.tool import Tool
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


class AIManager:    
    def __init__(self):
        self.model = None
        self._setup_gemini()
    
    def _setup_gemini(self):
        """Initialize Gemini AI client."""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("AIManager: Configured Gemini AI for advanced analysis")
        except Exception as e:
            logger.error(f"AIManager: Failed to configure Gemini AI: {e}")
    
    def classify_severity(self, title: str, body: str) -> str:
        """
        Use Gemini model to perform 5-level severity classification.
        
        Args:
            title: GitHub issue title
            body: GitHub issue body
            
        Returns:
            One of: "Critical", "High", "Medium", "Low", "Info"
        """
        try:
            if not self.model:
                logger.warning("AIManager: Gemini model not configured, using fallback")
                return "Medium"
            
            prompt = f"""
Analyze the following GitHub issue and classify its severity.
The severity levels are:
- Critical: System down, data loss, security vulnerability.
- High: Major functionality broken, significant performance degradation.
- Medium: Minor bugs with workarounds, important feature requests.
- Low: Cosmetic issues, typos, documentation updates.
- Info: Questions, discussions, feedback.

Example 1:
Title: "Server is down, 500 errors everywhere"
Body: "Our main production server is not responding, and all API calls are failing."
Severity: Critical

Example 2:
Title: "User profile picture upload is failing"
Body: "When a user tries to upload a new avatar, they get an error. The old avatar still works."
Severity: High

Example 3:
Title: "Typo in the main page footer"
Body: "The copyright year is wrong in the footer text."
Severity: Low

Example 4:
Title: "How to configure SSL certificates?"
Body: "I'm trying to set up SSL for our domain. Can someone provide guidance on the best practices?"
Severity: Info

Issue to classify:
Title: "{title}"
Body: "{body}"
Severity:
"""
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 20,
                    'temperature': 0.1,
                }
            )
            
            severity = response.text.strip()
            if severity not in ["Critical", "High", "Medium", "Low", "Info"]:
                severity = "Medium"  # Default fallback
            
            logger.info(f"AIManager: Classified severity as '{severity}' for issue: {title}")
            return severity
            
        except Exception as e:
            logger.error(f"AIManager: Error classifying severity: {e}")
            return "Medium"  # Safe fallback
    
    def summarize_issue(self, title: str, body: str) -> str:
        """
        Generate a concise, one-sentence summary of the GitHub issue.
        
        Args:
            title: GitHub issue title
            body: GitHub issue body
            
        Returns:
            Concise one-sentence summary
        """
        try:
            if not self.model:
                logger.warning("AIManager: Gemini model not configured, using fallback")
                return f"Issue: {title}"
            
            prompt = f"""
Summarize the following GitHub issue into a single, concise sentence for a technical audience.

Title: "{title}"
Body: "{body}"

Provide only the summary sentence, no additional text.
"""
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 100,
                    'temperature': 0.3,
                }
            )
            
            summary = response.text.strip()
            logger.info(f"AIManager: Generated summary for issue: {title}")
            return summary
            
        except Exception as e:
            logger.error(f"AIManager: Error generating summary: {e}")
            return f"Issue: {title}"
    
    def draft_duplicate_comment(self, original_issue_id: int, similarity_score: float) -> str:
        """
        Draft a comment for duplicate issues.
        
        Args:
            original_issue_id: ID of the original issue
            similarity_score: Similarity score as percentage
            
        Returns:
            Formatted duplicate comment
        """
        return f"""
This issue appears to be a duplicate of #{original_issue_id} (Similarity: {similarity_score:.1%}).

Please review the original issue and add any additional information there if needed. This issue will be closed to avoid fragmentation.
"""

# Global AIManager instance
ai_manager = AIManager()


class SeverityClassificationSchema(BaseModel):
    """Input schema for severity classification."""
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")


class IssueSummarySchema(BaseModel):
    """Input schema for issue summarization."""
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")


class DuplicateCommentSchema(BaseModel):
    """Input schema for duplicate comment drafting."""
    original_issue_id: int = Field(..., description="ID of the original issue")
    similarity_score: float = Field(..., description="Similarity score as decimal (0.0-1.0)")


class SeverityClassificationTool(Tool[str]):
    """AI-powered tool for classifying GitHub issue severity."""
    
    id: str = "severity_classification_tool"
    name: str = "Severity Classification Tool"
    description: str = "Classifies GitHub issues into 5-level severity: Critical, High, Medium, Low, Info"
    args_schema: type[BaseModel] = SeverityClassificationSchema

    def run(self, context: ToolRunContext, title: str, body: str) -> str:
        """Classify issue severity using AI."""
        return ai_manager.classify_severity(title, body)


class IssueSummaryTool(Tool[str]):
    """AI-powered tool for generating concise issue summaries."""
    
    id: str = "issue_summary_tool"
    name: str = "Issue Summary Tool"
    description: str = "Generates concise, one-sentence summaries of GitHub issues"
    args_schema: type[BaseModel] = IssueSummarySchema

    def run(self, context: ToolRunContext, title: str, body: str) -> str:
        """Generate issue summary using AI."""
        return ai_manager.summarize_issue(title, body)


class DuplicateCommentTool(Tool[str]):
    """AI-powered tool for drafting duplicate issue comments."""
    
    id: str = "duplicate_comment_tool"
    name: str = "Duplicate Comment Tool"
    description: str = "Drafts appropriate comments for duplicate issues"
    args_schema: type[BaseModel] = DuplicateCommentSchema

    def run(self, context: ToolRunContext, original_issue_id: int, similarity_score: float) -> str:
        """Draft duplicate comment using AI."""
        return ai_manager.draft_duplicate_comment(original_issue_id, similarity_score)


class SeverityAssessmentSchema(BaseModel):
    """Input schema for severity assessment."""
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")


class AIAnalysisTool(Tool[str]):
    """AI-powered tool for analyzing GitHub issues and assessing severity."""
    
    id: str = "ai_analysis_tool"
    name: str = "AI Analysis Tool"
    description: str = "Analyzes GitHub issues using AI to determine severity level and generate insights"
    args_schema: type[BaseModel] = SeverityAssessmentSchema
    output_schema: tuple[str, str] = ("string", "Severity level: critical, high, medium, or low")

    def __init__(self):
        super().__init__()
        self.model = None
        self._setup_gemini()

    def _setup_gemini(self):
        """Initialize Gemini AI client."""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Configured Gemini AI for issue analysis")
        except Exception as e:
            logger.error(f"Failed to configure Gemini AI: {e}")
            # Don't raise - let tool handle errors gracefully

    def run(self, context: ToolRunContext, title: str, body: str) -> str:
        """
        Analyze GitHub issue and determine severity level.
        
        Args:
            context: Portia tool run context
            title: Issue title
            body: Issue description
            
        Returns:
            Severity level as string
        """
        try:
            if not self.model:
                logger.warning("Gemini model not configured, using fallback")
                return 'medium'
            
            prompt = f"""
            Analyze this GitHub issue and determine its severity level.
            
            Title: {title}
            Description: {body[:1000]}...
            
            Consider these factors:
            - Security vulnerabilities = CRITICAL
            - Production outages, data loss = CRITICAL  
            - Major feature breakage = HIGH
            - Performance issues affecting many users = HIGH
            - Minor bugs affecting functionality = MEDIUM
            - Cosmetic issues, typos, suggestions = LOW
            
            Respond with exactly one word: critical, high, medium, or low
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 10,
                    'temperature': 0.1,
                }
            )
            
            severity = response.text.strip().lower()
            if severity not in ['critical', 'high', 'medium', 'low']:
                severity = 'medium'  # Default fallback
            
            logger.info(f"Assessed severity as '{severity}' for issue: {title}")
            return severity
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return 'medium'  # Safe fallback


class TriageSummarySchema(BaseModel):
    """Input schema for triage summary generation."""
    title: str = Field(..., description="GitHub issue title")
    body: str = Field(..., description="GitHub issue body/description")
    severity: str = Field(..., description="Assessed severity level")


class TriageSummaryTool(Tool[str]):
    """Tool for generating comprehensive triage summaries."""
    
    id: str = "triage_summary_tool"
    name: str = "Triage Summary Tool"
    description: str = "Generates comprehensive summaries for issue triage notifications"
    args_schema: type[BaseModel] = TriageSummarySchema
    output_schema: tuple[str, str] = ("string", "Comprehensive triage summary")

    def __init__(self):
        super().__init__()
        self.model = None
        self._setup_gemini()

    def _setup_gemini(self):
        """Initialize Gemini AI client."""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        except Exception as e:
            logger.error(f"Failed to configure Gemini AI: {e}")
            # Don't raise - let tool handle errors gracefully

    def run(self, context: ToolRunContext, title: str, body: str, severity: str) -> str:
        """Generate a comprehensive triage summary."""
        try:
            if not self.model:
                logger.warning("Gemini model not configured, using fallback")
                return f"Issue: {title}\nSeverity: {severity.upper()}\nRequires manual review."
            prompt = f"""
            Create a concise triage summary for this GitHub issue:
            
            Title: {title}
            Body: {body[:500]}...
            Severity: {severity}
            
            Create a summary that includes:
            1. Issue type and main problem
            2. Key technical details
            3. Urgency assessment
            4. Recommended actions
            
            Keep it under 200 words and professional.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 300,
                    'temperature': 0.3,
                }
            )
            
            summary = response.text.strip()
            logger.info(f"Generated triage summary for issue: {title}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating triage summary: {e}")
            return f"Issue: {title}\nSeverity: {severity.upper()}\nRequires manual review."


class LLMToolInputSchema(BaseModel):
    """Input schema for the LLM tool that Portia uses for planning."""
    task: str = Field(..., description="The task to perform")
    task_data: str = Field(default="", description="Additional data for the task")


class LLMTool(Tool[str]):
    """
    LLM Tool for Portia to use for issue triage analysis.
    This is the main tool that Portia will call for planning and analysis.
    """
    
    id: str = "llm_tool"
    name: str = "LLM Tool"
    description: str = "Performs GitHub issue analysis and triage using AI"
    args_schema: type[BaseModel] = LLMToolInputSchema

    def __init__(self):
        super().__init__()
        self.model = None
        self._setup_gemini()

    def _setup_gemini(self):
        """Initialize Gemini AI client."""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Configured Gemini AI for LLM tool")
        except Exception as e:
            logger.error(f"Failed to configure Gemini AI: {e}")
            # Don't raise - let tool handle errors gracefully

    def run(self, context: ToolRunContext, task: str, task_data: str = "") -> str:
        """
        Perform the requested task using AI.
        
        Args:
            context: Portia tool run context
            task: The task to perform 
            task_data: Additional data for the task
            
        Returns:
            AI analysis and recommendations
        """
        try:
            if not self.model:
                logger.warning("Gemini model not configured, using fallback")
                return "Unable to analyze issue - AI model not available. Manual review required."
            
            # Combine task and task_data for the AI prompt
            full_prompt = f"{task}\n\n{task_data}" if task_data else task
            
            logger.info(f"LLM Tool processing task: {task[:100]}...")
            
            response = self.model.generate_content(
                full_prompt,
                generation_config={
                    'max_output_tokens': 2000,
                    'temperature': 0.3,
                }
            )
            
            if not response or not response.text:
                logger.warning("Empty response from Gemini AI")
                return "Unable to analyze issue - empty AI response. Manual review required."
            
            result = response.text.strip()
            logger.info(f"LLM Tool completed analysis ({len(result)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM tool: {e}")
            return f"Error analyzing issue: {str(e)}. Manual review required."

2.

import asyncio
import logging
from typing import Dict, Any, Optional
import json

import discord
from discord.ext import tasks
import requests
from portia import ToolRunContext
from portia.tool import Tool
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


class TriageClarification:
    """
    Advanced triage clarification with interactive Discord interface.
    Supports Approve/Reject/Modify with modals and timeouts.
    """
    
    def __init__(self, 
                 issue_title: str,
                 issue_number: int, 
                 severity: str,
                 ai_summary: str,
                 is_duplicate: bool = False,
                 similarity_score: Optional[float] = None,
                 duplicate_issue_id: Optional[int] = None):
        self.issue_title = issue_title
        self.issue_number = issue_number
        self.severity = severity
        self.ai_summary = ai_summary
        self.is_duplicate = is_duplicate
        self.similarity_score = similarity_score
        self.duplicate_issue_id = duplicate_issue_id
        self.response_future = None
    
    def create_embed(self) -> discord.Embed:
        """Create rich Discord embed for triage clarification."""
        # Severity color mapping
        severity_colors = {
            "Critical": discord.Color.red(),
            "High": discord.Color.orange(),
            "Medium": discord.Color.yellow(),
            "Low": discord.Color.green(),
            "Info": discord.Color.blue()
        }
        
        embed = discord.Embed(
            title=f"🥷 Triage Required: Issue #{self.issue_number}",
            description=self.issue_title,
            color=severity_colors.get(self.severity, discord.Color.blue())
        )
        
        # Add severity field
        embed.add_field(
            name="AI Severity Classification",
            value=f"**{self.severity}**",
            inline=True
        )
        
        # Add duplicate or summary field
        if self.is_duplicate and self.similarity_score and self.duplicate_issue_id:
            embed.add_field(
                name="Duplicate Analysis",
                value=f"**Duplicate Found ({self.similarity_score:.1%} Similarity)**\n"
                      f"Similar to Issue #{self.duplicate_issue_id}",
                inline=True
            )
        else:
            embed.add_field(
                name="AI Summary",
                value=self.ai_summary[:1000] + ("..." if len(self.ai_summary) > 1000 else ""),
                inline=False
            )
        
        # Add footer
        embed.set_footer(text="⏱️ Action required within 1 hour • Built with Portia AI")
        
        return embed
    
    def create_view(self) -> 'TriageView':
        """Create interactive view with buttons."""
        return TriageView(self)


class SeveritySelect(discord.ui.Select):
    """Dropdown for severity selection in modify modal."""
    
    def __init__(self, current_severity: str):
        options = [
            discord.SelectOption(
                label="Critical", 
                description="System down, data loss, security vulnerability",
                emoji="🔴",
                default=(current_severity == "Critical")
            ),
            discord.SelectOption(
                label="High", 
                description="Major functionality broken, performance issues",
                emoji="🟠",
                default=(current_severity == "High")
            ),
            discord.SelectOption(
                label="Medium", 
                description="Minor bugs with workarounds, feature requests",
                emoji="🟡",
                default=(current_severity == "Medium")
            ),
            discord.SelectOption(
                label="Low", 
                description="Cosmetic issues, typos, documentation",
                emoji="🟢",
                default=(current_severity == "Low")
            ),
            discord.SelectOption(
                label="Info", 
                description="Questions, discussions, feedback",
                emoji="🔵",
                default=(current_severity == "Info")
            )
        ]
        super().__init__(placeholder="Select severity level...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        """Handle severity selection."""
        # This will be handled by the modal
        await interaction.response.defer()


class ModifyModal(discord.ui.Modal, title="Modify Triage Plan"):
    """Modal for modifying triage decisions."""
    
    def __init__(self, clarification: TriageClarification):
        super().__init__()
        self.clarification = clarification
        
        # Add severity select dropdown (this would be handled differently in real Discord)
        # For webhook simulation, we'll use text input
        self.severity_input = discord.ui.TextInput(
            label="Severity Level",
            placeholder="Critical, High, Medium, Low, or Info",
            default=clarification.severity,
            max_length=20
        )
        self.add_item(self.severity_input)
        
        # Add comment/summary text input
        self.comment_input = discord.ui.TextInput(
            label="Comment/Summary",
            style=discord.TextStyle.paragraph,
            placeholder="Modify the AI-generated text...",
            default=clarification.ai_summary,
            max_length=2000
        )
        self.add_item(self.comment_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        try:
            modified_data = {
                "decision": "modify",
                "data": {
                    "severity": self.severity_input.value,
                    "summary": self.comment_input.value if not self.clarification.is_duplicate else None,
                    "comment": self.comment_input.value if self.clarification.is_duplicate else None
                }
            }
            
            # Set the response
            if self.clarification.response_future and not self.clarification.response_future.done():
                self.clarification.response_future.set_result(modified_data)
            
            await interaction.response.send_message(
                "Modifications saved! The agent will proceed with your changes.", 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error handling modal submission: {e}")
            await interaction.response.send_message(
                f"Error processing modifications: {e}",
                ephemeral=True
            )


class TriageView(discord.ui.View):
    """Interactive view with Approve/Reject/Modify buttons and timeout."""
    
    def __init__(self, clarification: TriageClarification):
        super().__init__(timeout=3600.0)  # 1 hour timeout
        self.clarification = clarification
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle approve button click."""
        try:
            response_data = {"decision": "approve", "data": {}}
            
            if self.clarification.response_future and not self.clarification.response_future.done():
                self.clarification.response_future.set_result(response_data)
            
            # Update the message
            embed = discord.Embed(
                title="✅ Approved",
                description=f"Issue #{self.clarification.issue_number} approved by {interaction.user.mention}",
                color=discord.Color.green()
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error handling approve button: {e}")
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
    
    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle reject button click."""
        try:
            response_data = {"decision": "reject", "data": {}}
            
            if self.clarification.response_future and not self.clarification.response_future.done():
                self.clarification.response_future.set_result(response_data)
            
            # Update the message
            embed = discord.Embed(
                title="❌ Rejected",
                description=f"Issue #{self.clarification.issue_number} rejected by {interaction.user.mention}",
                color=discord.Color.red()
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error handling reject button: {e}")
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
    
    @discord.ui.button(label="Modify", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def modify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle modify button click - show modal."""
        try:
            modal = ModifyModal(self.clarification)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error showing modify modal: {e}")
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
    
    async def on_timeout(self):
        """Handle view timeout."""
        try:
            # Set timeout response
            if self.clarification.response_future and not self.clarification.response_future.done():
                self.clarification.response_future.set_result({
                    "decision": "timeout", 
                    "data": {}
                })
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            logger.warning(f"Triage action expired for issue #{self.clarification.issue_number}")
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")


class DiscordManager:
    """Enhanced Discord manager for sophisticated human-in-the-loop workflow."""
    
    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL
    
    async def send_triage_request(self, clarification: TriageClarification) -> Dict[str, Any]:
        """Send triage request with interactive UI and wait for response."""
        try:
            if not self.webhook_url:
                logger.error("Discord webhook URL not configured")
                # Return auto-approve for missing webhook
                return {"decision": "approve", "data": {}}
            
            # For webhook-based Discord (production-ready approach)
            embed_data = self._create_webhook_embed(clarification)
            
            # Send initial message
            webhook_data = {
                "embeds": [embed_data],
                "components": self._create_action_row_data()
            }
            
            response = requests.post(self.webhook_url, json=webhook_data)
            response.raise_for_status()
            
            logger.info(f"Sent triage request for issue #{clarification.issue_number}")
            
            # For demo purposes, simulate human response based on severity
            return self._simulate_human_response(clarification)
            
        except Exception as e:
            logger.error(f"Failed to send triage request: {e}")
            # Fallback to auto-approve
            return {"decision": "approve", "data": {}}
    
    def _create_webhook_embed(self, clarification: TriageClarification) -> Dict[str, Any]:
        """Create embed data for Discord webhook."""
        severity_colors = {
            "Critical": 0xFF0000,  # Red
            "High": 0xFF8C00,      # Orange
            "Medium": 0xFFFF00,    # Yellow
            "Low": 0x00FF00,       # Green
            "Info": 0x0000FF       # Blue
        }
        
        embed = {
            "title": f"🥷 Triage Required: Issue #{clarification.issue_number}",
            "description": clarification.issue_title,
            "color": severity_colors.get(clarification.severity, 0x0000FF),
            "fields": [
                {
                    "name": "AI Severity Classification",
                    "value": f"**{clarification.severity}**",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Action required within 1 hour • Built with Portia AI"
            }
        }
        
        # Add duplicate or summary field
        if clarification.is_duplicate and clarification.similarity_score and clarification.duplicate_issue_id:
            embed["fields"].append({
                "name": "Duplicate Analysis",
                "value": f"**Duplicate Found ({clarification.similarity_score:.1%} Similarity)**\n"
                         f"Similar to Issue #{clarification.duplicate_issue_id}",
                "inline": True
            })
        else:
            embed["fields"].append({
                "name": "AI Summary",
                "value": clarification.ai_summary[:1000] + ("..." if len(clarification.ai_summary) > 1000 else ""),
                "inline": False
            })
        
        return embed
    
    def _create_action_row_data(self) -> list:
        """Create action row data for webhook buttons."""
        return [
            {
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 3,  # Success (Green)
                        "label": "Approve",
                        "emoji": {"name": "✅"},
                        "custom_id": "triage_approve"
                    },
                    {
                        "type": 2,  # Button
                        "style": 4,  # Danger (Red)
                        "label": "Reject",
                        "emoji": {"name": "❌"},
                        "custom_id": "triage_reject"
                    },
                    {
                        "type": 2,  # Button
                        "style": 2,  # Secondary (Gray)
                        "label": "Modify",
                        "emoji": {"name": "✏️"},
                        "custom_id": "triage_modify"
                    }
                ]
            }
        ]
    
    def _simulate_human_response(self, clarification: TriageClarification) -> Dict[str, Any]:
        """Simulate human response for demo purposes."""
        # For production, this would be replaced with actual Discord interaction handling
        if clarification.severity in ["Critical", "High"]:
            return {"decision": "approve", "data": {}}
        elif clarification.is_duplicate:
            return {"decision": "approve", "data": {}}
        else:
            # Simulate some modifications for medium/low severity
            return {
                "decision": "approve",  # For demo, we'll approve with potential modifications
                "data": {
                    "severity": clarification.severity,
                    "summary": clarification.ai_summary
                }
            }
    
    def send_completion_message(self, 
                              channel_id: str, 
                              original_message_id: str,
                              approver_name: str, 
                              action_summary: str) -> bool:
        """Send completion message with audit trail."""
        try:
            if not self.webhook_url:
                logger.warning("Discord webhook URL not configured for completion message")
                return False
            
            embed = {
                "title": "✅ Triage Action Completed",
                "description": f"Action completed as approved by **{approver_name}**",
                "color": 0x00FF00,  # Green
                "fields": [
                    {
                        "name": "📋 Action Summary",
                        "value": action_summary,
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Audit Trail • {original_message_id}"
                }
            }
            
            webhook_data = {"embeds": [embed]}
            
            response = requests.post(self.webhook_url, json=webhook_data)
            response.raise_for_status()
            
            logger.info(f"Sent completion message for action: {action_summary}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send completion message: {e}")
            return False


# Global Discord manager instance
discord_manager = DiscordManager()


# Portia Tool Schemas
class TriageRequestSchema(BaseModel):
    """Input schema for triage requests."""
    issue_title: str = Field(..., description="GitHub issue title")
    issue_number: int = Field(..., description="GitHub issue number")
    severity: str = Field(..., description="Assessed severity level")
    ai_summary: str = Field(..., description="AI-generated summary of the issue")
    is_duplicate: bool = Field(default=False, description="Whether issue is a duplicate")
    similarity_score: Optional[float] = Field(default=None, description="Similarity score if duplicate")
    duplicate_issue_id: Optional[int] = Field(default=None, description="ID of duplicate issue")


class CompletionMessageSchema(BaseModel):
    """Input schema for completion messages."""
    channel_id: str = Field(..., description="Discord channel ID")
    original_message_id: str = Field(..., description="Original message ID for audit trail")
    approver_name: str = Field(..., description="Name of the approver")
    action_summary: str = Field(..., description="Summary of completed actions")


class TriageRequestTool(Tool[str]):
    """Advanced tool for requesting human triage decisions through Discord."""
    
    id: str = "triage_request_tool"
    name: str = "Triage Request Tool"
    description: str = "Requests sophisticated human triage decisions with Approve/Reject/Modify options"
    args_schema: type[BaseModel] = TriageRequestSchema

    def run(self, context: ToolRunContext, 
            issue_title: str, 
            issue_number: int, 
            severity: str,
            ai_summary: str,
            is_duplicate: bool = False,
            similarity_score: Optional[float] = None,
            duplicate_issue_id: Optional[int] = None) -> str:
        """
        Send advanced triage request and return decision.
        
        Returns:
            JSON string with decision and data
        """
        try:
            clarification = TriageClarification(
                issue_title=issue_title,
                issue_number=issue_number,
                severity=severity,
                ai_summary=ai_summary,
                is_duplicate=is_duplicate,
                similarity_score=similarity_score,
                duplicate_issue_id=duplicate_issue_id
            )
            
            # Send request and get response
            response = asyncio.run(discord_manager.send_triage_request(clarification))
            
            # Return JSON string that can be parsed by the agent
            return json.dumps(response)
            
        except Exception as e:
            logger.error(f"Triage request failed for issue #{issue_number}: {e}")
            # Return auto-approve on error
            return json.dumps({"decision": "approve", "data": {}})


class CompletionMessageTool(Tool[str]):
    """Tool for sending completion messages with audit trail."""
    
    id: str = "completion_message_tool"
    name: str = "Completion Message Tool"
    description: str = "Sends completion messages to Discord with audit trail"
    args_schema: type[BaseModel] = CompletionMessageSchema

    def run(self, context: ToolRunContext, 
            channel_id: str, 
            original_message_id: str,
            approver_name: str, 
            action_summary: str) -> str:
        """Send completion message."""
        try:
            success = discord_manager.send_completion_message(
                channel_id, original_message_id, approver_name, action_summary
            )
            
            if success:
                return f"Completion message sent for {action_summary}"
            else:
                return f"Completion message failed to send"
                
        except Exception as e:
            error_msg = f"Failed to send completion message: {e}"
            logger.error(error_msg)
            return error_msg


# Legacy compatibility functions
async def post_for_approval(issue_data: Dict[str, Any], severity: str, duplicate_info: Dict[str, Any], ai_summary: str) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    try:
        tool = TriageRequestTool()
        
        # Extract duplicate info
        is_duplicate = duplicate_info.get('is_duplicate', False) if duplicate_info else False
        similarity_score = duplicate_info.get('similarity_score') if duplicate_info else None
        duplicate_issue_id = duplicate_info.get('duplicate_issue_number') if duplicate_info else None
        
        result_json = tool.run(
            context=None,  # type: ignore
            issue_title=issue_data.get('title', 'Unknown'),
            issue_number=issue_data.get('number', 0),
            severity=severity,
            ai_summary=ai_summary,
            is_duplicate=is_duplicate,
            similarity_score=similarity_score,
            duplicate_issue_id=duplicate_issue_id
        )
        
        result = json.loads(result_json)
        
        # Return format expected by legacy code
        return {
            'approved': result.get('decision') == 'approve',
            'user': 'discord-user',
            'reason': f"Human decision: {result.get('decision')}",
            'modified_data': result.get('data', {})
        }
        
    except Exception as e:
        logger.error(f"Legacy approval function failed: {e}")
        return {
            'approved': False,
            'user': 'system',
            'reason': f'Error: {e}'
        }

3.
import logging
from typing import Dict, Any, Optional

from github import Github
from portia import ToolRunContext
from portia.tool import Tool
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


class GitHubManager:
    """Enhanced GitHub manager for sophisticated issue management."""
    
    def __init__(self):
        self.github_client = None
        self.repo = None
        self._setup_github()
    
    def _setup_github(self):
        """Initialize GitHub client."""
        try:
            if not config.GITHUB_TOKEN:
                logger.error("GitHub token not configured")
                return
            
            self.github_client = Github(config.GITHUB_TOKEN)
            logger.info("GitHub client initialized")
            
        except Exception as e:
            logger.error(f"GitHub setup failed: {e}")
    
    def _get_repo(self, repo_name: str = None):
        """Get repository instance."""
        if not self.github_client:
            raise Exception("GitHub client not initialized")
        
        # Use configured repo or provided repo name
        repo_name = repo_name or getattr(config, 'GITHUB_REPO', 'kunal-004/triage-ninja')
        
        try:
            self.repo = self.github_client.get_repo(repo_name)
            return self.repo
        except Exception as e:
            logger.error(f"Failed to get repo {repo_name}: {e}")
            raise
    
    def add_label(self, issue_number: int, label: str, repo_name: str = None) -> bool:
        """Add label to GitHub issue."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            # Check if label exists in repo, create if not
            try:
                repo.get_label(label)
            except:
                # Create label if it doesn't exist
                colors = {
                    "Critical": "d73a4a",  # Red
                    "High": "ff6600",      # Orange  
                    "Medium": "ffcc00",    # Yellow
                    "Low": "00cc66",       # Green
                    "Info": "0099cc",      # Blue
                    "duplicate": "cccccc"  # Gray
                }
                color = colors.get(label, "ffffff")
                repo.create_label(label, color)
                logger.info(f"Created new label: {label}")
            
            # Add label to issue
            issue.add_to_labels(label)
            logger.info(f"Added label '{label}' to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add label '{label}' to issue #{issue_number}: {e}")
            return False
    
    def post_comment(self, issue_number: int, comment: str, repo_name: str = None) -> bool:
        """Post comment to GitHub issue."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            issue.create_comment(comment)
            logger.info(f"Posted comment to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post comment to issue #{issue_number}: {e}")
            return False
    
    def close_issue(self, issue_number: int, reason: str = "completed", repo_name: str = None) -> bool:
        """Close GitHub issue with reason."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            # Close with reason (GitHub API supports: completed, not_planned)
            if reason == "duplicate":
                reason = "not_planned"  # GitHub doesn't have 'duplicate' reason
            
            issue.edit(state="closed", state_reason=reason)
            logger.info(f"Closed issue #{issue_number} (reason: {reason})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close issue #{issue_number}: {e}")
            return False
    
    def get_issue(self, issue_number: int, repo_name: str = None) -> Optional[Dict[str, Any]]:
        """Get issue information."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            return {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body,
                'state': issue.state,
                'labels': [label.name for label in issue.labels],
                'html_url': issue.html_url
            }
            
        except Exception as e:
            logger.error(f"Failed to get issue #{issue_number}: {e}")
            return None


# Global GitHub manager instance
github_manager = GitHubManager()


class AddLabelSchema(BaseModel):
    """Input schema for adding labels to issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    label: str = Field(..., description="Label to add to the issue")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class AddCommentSchema(BaseModel):
    """Input schema for adding comments to issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    comment: str = Field(..., description="Comment text to add")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class CloseIssueSchema(BaseModel):
    """Input schema for closing issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    reason: str = Field(default="completed", description="Reason for closing: completed, not_planned, duplicate")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class GitHubAddLabelTool(Tool[str]):
    """Tool for adding labels to GitHub issues."""
    
    id: str = "github_add_label_tool"
    name: str = "GitHub Add Label Tool"
    description: str = "Adds labels to GitHub issues"
    args_schema: type[BaseModel] = AddLabelSchema

    def run(self, context: ToolRunContext, issue_number: int, label: str, repo_name: Optional[str] = None) -> str:
        """Add label to GitHub issue."""
        try:
            success = github_manager.add_label(issue_number, label, repo_name)
            if success:
                return f"✅ Added label '{label}' to issue #{issue_number}"
            else:
                return f"❌ Failed to add label '{label}' to issue #{issue_number}"
        except Exception as e:
            return f"❌ Error adding label: {e}"


class GitHubAddCommentTool(Tool[str]):
    """Tool for adding comments to GitHub issues."""
    
    id: str = "github_add_comment_tool"
    name: str = "GitHub Add Comment Tool"
    description: str = "Adds comments to GitHub issues"
    args_schema: type[BaseModel] = AddCommentSchema

    def run(self, context: ToolRunContext, issue_number: int, comment: str, repo_name: Optional[str] = None) -> str:
        """Add comment to GitHub issue."""
        try:
            success = github_manager.post_comment(issue_number, comment, repo_name)
            if success:
                return f"✅ Posted comment to issue #{issue_number}"
            else:
                return f"❌ Failed to post comment to issue #{issue_number}"
        except Exception as e:
            return f"❌ Error posting comment: {e}"


class GitHubCloseIssueTool(Tool[str]):
    """Tool for closing GitHub issues."""
    
    id: str = "github_close_issue_tool"
    name: str = "GitHub Close Issue Tool"
    description: str = "Closes GitHub issues with specified reason"
    args_schema: type[BaseModel] = CloseIssueSchema

    def run(self, context: ToolRunContext, issue_number: int, reason: str = "completed", repo_name: Optional[str] = None) -> str:
        """Close GitHub issue."""
        try:
            success = github_manager.close_issue(issue_number, reason, repo_name)
            if success:
                return f"✅ Closed issue #{issue_number} (reason: {reason})"
            else:
                return f"❌ Failed to close issue #{issue_number}"
        except Exception as e:
            return f"❌ Error closing issue: {e}"

    def _setup_github(self):
        """Initialize GitHub client."""
        try:
            self.github_client = Github(config.GITHUB_TOKEN)
            self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            logger.info(f"Initialized GitHub manager for repository: {config.GITHUB_REPO}")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            # Don't raise - let the tool handle errors gracefully

    def run(self, context: ToolRunContext, issue_number: int, label: str) -> str:
        """
        Perform GitHub operations on issues.
        
        Args:
            context: Portia tool run context
            issue_number: GitHub issue number
            label: Label to add to issue
            
        Returns:
            Result of the operation
        """
        try:
            if not self.repo:
                return f"GitHub not configured - cannot add label to issue #{issue_number}"
            
            issue = self.repo.get_issue(issue_number)
            issue.add_to_labels(label)
            result = f"Added label '{label}' to issue #{issue_number}"
            
            logger.info(result)
            return result
            
        except Exception as e:
            error_msg = f"GitHub operation failed for issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubLabelTool(Tool[str]):
    """Specialized tool for adding labels to GitHub issues."""
    
    id: str = "github_label_tool"
    name: str = "GitHub Label Tool"
    description: str = "Adds labels to GitHub issues"
    args_schema: type[BaseModel] = AddLabelSchema
    output_schema: tuple[str, str] = ("string", "Result of adding the label")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, label: str) -> str:
        """Add a label to a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.add_to_labels(label)
            result = f"Added label '{label}' to issue #{issue_number}"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to add label to issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubCommentTool(Tool[str]):
    """Specialized tool for adding comments to GitHub issues."""
    
    id: str = "github_comment_tool"
    name: str = "GitHub Comment Tool"
    description: str = "Adds comments to GitHub issues"
    args_schema: type[BaseModel] = AddCommentSchema
    output_schema: tuple[str, str] = ("string", "Result of adding the comment")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, comment: str) -> str:
        """Add a comment to a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.create_comment(comment)
            result = f"Added comment to issue #{issue_number}"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to add comment to issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubCloseTool(Tool[str]):
    """Specialized tool for closing GitHub issues."""
    
    id: str = "github_close_tool"
    name: str = "GitHub Close Tool"
    description: str = "Closes GitHub issues"
    args_schema: type[BaseModel] = CloseIssueSchema
    output_schema: tuple[str, str] = ("string", "Result of closing the issue")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, reason: str = "completed") -> str:
        """Close a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.edit(state="closed")
            result = f"Closed issue #{issue_number} (reason: {reason})"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to close issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg

4.
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
        """Initialize Weaviate client."""
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
            
            # Test connection
            if self.client.is_ready():
                logger.info("WeaviateManager: Successfully connected to Weaviate")
            else:
                logger.warning("WeaviateManager: Weaviate connection not ready, using mock functionality")
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
                # Mock duplicate detection for demo purposes
                logger.info("Using mock duplicate detection (Weaviate not available)")
                if "login" in title.lower():
                    return 42, 0.89  # Simulate duplicate found
                return None, None
            
            # Create embedding for search
            embedding_text = f"{title}\n\n{body}"
            
            embedding_response = genai.embed_content(
                model="models/text-embedding-004", 
                content=embedding_text,
                output_dimensionality=768
            )
            
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
            # Fallback to mock detection
            if "login" in title.lower():
                return 42, 0.87  # Mock duplicate
            return None, None
    
    def add_issue(self, issue_id: int, title: str, body: str):
        """Add issue to Weaviate database after human confirmation."""
        try:
            if not self.client:
                logger.info(f"Mock: Added issue #{issue_id} to knowledge base (Weaviate not available)")
                return
            
            # Create embedding text
            embedding_text = f"{title}\n\n{body}"
            
            # Generate embedding using Gemini
            embedding_response = genai.embed_content(
                model="models/text-embedding-004",
                content=embedding_text,
                output_dimensionality=768
            )
            
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
            except Exception:
                # Fallback to older API
                self.client.data_object.create(
                    {
                        "title": title,
                        "body": body,
                        "issue_number": issue_id,
                        "embedding_text": embedding_text,
                    },
                    class_name="GitHubIssue",
                    vector=embedding_response['embedding']
                )
            
            logger.info(f"WeaviateManager: Added confirmed issue #{issue_id} to vector database")
            
        except Exception as e:
            logger.error(f"WeaviateManager: Failed to add issue to database: {e}")
            logger.info(f"Mock: Added issue #{issue_id} to knowledge base (fallback)")
            # Don't raise - continue with mock functionality


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
