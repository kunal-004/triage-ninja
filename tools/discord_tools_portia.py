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
                 issue_body: str = "",
                 is_duplicate: bool = False,
                 similarity_score: Optional[float] = None,
                 duplicate_issue_id: Optional[int] = None):
        self.issue_title = issue_title
        self.issue_number = issue_number
        self.severity = severity
        self.ai_summary = ai_summary
        self.issue_body = issue_body
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
            name="🎯 AI Severity Classification",
            value=f"**{self.severity}**",
            inline=True
        )
        
        # Add duplicate or summary field
        if self.is_duplicate and self.similarity_score and self.duplicate_issue_id:
            embed.add_field(
                name="🔍 Duplicate Analysis",
                value=f"**Duplicate Found ({self.similarity_score:.1%} Similarity)**\n"
                      f"Similar to Issue #{self.duplicate_issue_id}",
                inline=True
            )
        else:
            embed.add_field(
                name="📝 AI Summary",
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
                "✅ Modifications saved! The agent will proceed with your changes.", 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error handling modal submission: {e}")
            await interaction.response.send_message(
                f"❌ Error processing modifications: {e}",
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
        """Send triage request with REAL interactive UI and wait for human response."""
        try:
            if not self.webhook_url:
                logger.error("Discord webhook URL not configured")
                return {"decision": "approve", "data": {}}
            
            # Try to use the real interactive Discord bot
            try:
                from discord_bot import send_triage_request, bot
                import asyncio
                
                # Prepare data for interactive bot
                issue_data = {
                    'issue_number': clarification.issue_number,
                    'issue_title': clarification.issue_title,
                    'issue_body': clarification.issue_body,
                    'severity': clarification.severity,
                    'ai_summary': clarification.ai_summary,
                    'is_duplicate': clarification.is_duplicate,
                    'similarity_score': clarification.similarity_score,
                    'duplicate_issue_id': clarification.duplicate_issue_id
                }
                
                # Wait for REAL human decision via Discord bot
                logger.info(f"🤖 Waiting for human decision via Discord bot for issue #{clarification.issue_number}")
                
                # Check if we're already in Discord's event loop or need to use run_coroutine_threadsafe
                try:
                    # Try to get current event loop
                    current_loop = asyncio.get_event_loop()
                    
                    # Check if Discord bot has its own loop
                    bot_loop = getattr(bot, 'loop', None)
                    
                    if bot_loop and bot_loop != current_loop:
                        # We're in a different loop, use run_coroutine_threadsafe
                        logger.info("Running Discord triage request from different event loop")
                        future = asyncio.run_coroutine_threadsafe(send_triage_request(issue_data), bot_loop)
                        response = future.result(timeout=3700)  # 1 hour + buffer
                    else:
                        # We're in the same loop, call directly
                        response = await send_triage_request(issue_data)
                        
                except RuntimeError as e:
                    if "no running event loop" in str(e).lower():
                        # No current loop, try to run in bot's loop
                        bot_loop = getattr(bot, 'loop', None)
                        if bot_loop:
                            logger.info("Running Discord triage request in bot's event loop")
                            future = asyncio.run_coroutine_threadsafe(send_triage_request(issue_data), bot_loop)
                            response = future.result(timeout=3700)  # 1 hour + buffer
                        else:
                            raise Exception("No event loop available for Discord bot communication")
                    else:
                        raise
                
                logger.info(f"👤 Human decision received: {response}")
                return response
                
            except ImportError:
                logger.warning("Discord bot not available, falling back to webhook notification")
                # Fall back to webhook-based notification (without real interaction)
                embed_data = self._create_webhook_embed(clarification)
                webhook_data = {
                    "embeds": [embed_data],
                    "components": self._create_action_row_data()
                }
                
                response = requests.post(self.webhook_url, json=webhook_data)
                response.raise_for_status()
                
                logger.info(f"✅ Sent webhook triage request for issue #{clarification.issue_number}")
                
                # For webhook-only mode, raise error instead of auto-approve
                logger.error("❌ DISCORD BOT NOT AVAILABLE: Human input required via Discord bot")
                raise Exception("Discord bot integration failed - Cannot proceed without human interaction")
                
        except Exception as e:
            logger.error(f"Failed to send triage request: {e}")
            # DO NOT AUTO-APPROVE - Re-raise the error
            raise Exception(f"Discord triage request failed: {e} - HUMAN INPUT REQUIRED")
    
    def _create_webhook_embed(self, clarification: TriageClarification) -> Dict[str, Any]:
        """Create enhanced embed data for Discord webhook with detailed analysis."""
        severity_colors = {
            "Critical": 0xFF0000,  # Red
            "High": 0xFF8C00,      # Orange
            "Medium": 0xFFFF00,    # Yellow
            "Low": 0x00FF00,       # Green
            "Info": 0x0000FF       # Blue
        }
        
        # Enhanced description with issue body preview
        description = f"**{clarification.issue_title}**\n"
        if clarification.issue_body:
            body_preview = clarification.issue_body[:200] + ('...' if len(clarification.issue_body) > 200 else '')
            description += body_preview
        
        embed = {
            "title": f"🥷 Triage Required: Issue #{clarification.issue_number}",
            "description": description,
            "color": severity_colors.get(clarification.severity, 0x0000FF),
            "fields": [],
            "footer": {
                "text": "⏱️ Action required within 1 hour • Built with Portia AI"
            }
        }
        
        # Add severity with reasoning
        severity_descriptions = {
            "Critical": "🔴 System down, data loss, security vulnerability",
            "High": "🟠 Major functionality broken, performance issues",
            "Medium": "🟡 Minor bugs with workarounds, feature requests",
            "Low": "🟢 Cosmetic issues, typos, documentation",
            "Info": "🔵 Questions, discussions, feedback"
        }
        
        embed["fields"].append({
            "name": "🎯 AI Severity Classification",
            "value": f"**{clarification.severity}**\n{severity_descriptions.get(clarification.severity, '')}",
            "inline": True
        })
        
        # Add impact assessment
        impact_level = {
            "Critical": "🔥 Immediate action required",
            "High": "⚡ High priority - address soon",
            "Medium": "📋 Standard workflow",
            "Low": "📝 Low priority - can be scheduled",
            "Info": "💬 Informational - review when convenient"
        }.get(clarification.severity, "📋 Standard workflow")
        
        embed["fields"].append({
            "name": "⚡ Impact Assessment",
            "value": impact_level,
            "inline": True
        })
        
        # Add duplicate or summary field with enhanced details
        if clarification.is_duplicate and clarification.similarity_score and clarification.duplicate_issue_id:
            embed["fields"].append({
                "name": "🔍 Duplicate Analysis",
                "value": f"**Duplicate Found ({clarification.similarity_score:.1%} Similarity)**\n"
                         f"Similar to Issue #{clarification.duplicate_issue_id}\n"
                         f"💡 *Recommend closing as duplicate*",
                "inline": False
            })
        else:
            embed["fields"].append({
                "name": "📝 Detailed AI Analysis",
                "value": clarification.ai_summary[:800] + ("..." if len(clarification.ai_summary) > 800 else ""),
                "inline": False
            })
            
        # Add recommended actions
        if clarification.is_duplicate:
            recommended_actions = "🔄 Close as duplicate\n📝 Add explanatory comment\n🔗 Link to original issue"
        elif clarification.severity in ["Critical", "High"]:
            recommended_actions = f"🏷️ Add '{clarification.severity}' severity label\n📝 Post AI analysis\n🔔 Notify relevant team\n📊 Track in knowledge base"
        else:
            recommended_actions = f"🏷️ Add '{clarification.severity}' severity label\n📝 Post AI analysis\n📊 Add to knowledge base"
            
        embed["fields"].append({
            "name": "🎯 Recommended Actions",
            "value": recommended_actions,
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
            
            logger.info(f"✅ Sent completion message for action: {action_summary}")
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
        import concurrent.futures
        import threading
        
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
            
            # Run the async function in a new thread with its own event loop
            def run_async_in_thread():
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(discord_manager.send_triage_request(clarification))
                    finally:
                        loop.close()
                except Exception as e:
                    logger.error(f"Thread async execution failed: {e}")
                    raise
            
            # Use ThreadPoolExecutor to run async code in separate thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_in_thread)
                try:
                    response = future.result(timeout=3700)  # 1 hour timeout
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Discord triage request timed out for issue #{issue_number}")
                    raise Exception("Discord triage request timed out - HUMAN INPUT REQUIRED")
            
            # Return JSON string that can be parsed by the agent
            return json.dumps(response)
            
        except Exception as e:
            logger.error(f"Triage request failed for issue #{issue_number}: {e}")
            # DO NOT AUTO-APPROVE - Raise error for human input requirement
            raise Exception(f"Discord triage request failed: {e} - HUMAN INPUT REQUIRED")


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
                return f"✅ Completion message sent for {action_summary}"
            else:
                return f"⚠️ Completion message failed to send"
                
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
