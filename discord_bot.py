import asyncio
import logging
from typing import Dict, Any

import discord
from discord.ext import commands

import config
from tools.github_tools_portia import github_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = False
intents.members = False
intents.presences = False
bot = commands.Bot(command_prefix='!', intents=intents)

pending_decisions: Dict[str, asyncio.Future] = {}

class SeveritySelect(discord.ui.Select):
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
        self.selected_severity = current_severity
    
    async def callback(self, interaction: discord.Interaction):
        self.selected_severity = self.values[0]
        await interaction.response.defer()


class ModifyModal(discord.ui.Modal, title="Modify Triage Plan"):
    """Modal for modifying triage decisions."""
    
    def __init__(self, issue_number: int, current_severity: str, current_text: str, is_duplicate: bool):
        super().__init__()
        self.issue_number = issue_number
        self.is_duplicate = is_duplicate
        
        # Severity input
        self.severity = discord.ui.TextInput(
            label="Severity Level",
            placeholder="Critical, High, Medium, Low, or Info",
            default=current_severity,
            max_length=20
        )
        self.add_item(self.severity)
        
        # Comment/summary input
        label = "Comment" if is_duplicate else "Summary"
        self.text_content = discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.paragraph,
            placeholder=f"Modify the AI-generated {label.lower()}...",
            default=current_text,
            max_length=2000
        )
        self.add_item(self.text_content)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        try:
            modified_data = {
                "decision": "approve",  # Modified approval
                "data": {
                    "severity": self.severity.value,
                    "summary": self.text_content.value if not self.is_duplicate else None,
                    "comment": self.text_content.value if self.is_duplicate else None,
                    "modified": True
                }
            }
            
            # Find and resolve the pending decision
            decision_key = f"issue_{self.issue_number}"
            if decision_key in pending_decisions:
                if not pending_decisions[decision_key].done():
                    pending_decisions[decision_key].set_result(modified_data)
            
            await interaction.response.send_message(
                f"Modifications saved for Issue #{self.issue_number}! The agent will proceed with your changes.", 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error handling modal submission: {e}")
            await interaction.response.send_message(
                f"Error processing modifications: {e}",
                ephemeral=True
            )


class TriageView(discord.ui.View):
    """Interactive view with Approve/Reject/Modify buttons."""
    
    def __init__(self, issue_number: int, issue_title: str, severity: str, ai_text: str, is_duplicate: bool):
        super().__init__(timeout=3600.0)  # 1 hour timeout
        self.issue_number = issue_number
        self.issue_title = issue_title
        self.severity = severity
        self.ai_text = ai_text
        self.is_duplicate = is_duplicate
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle approve button click."""
        try:
            response_data = {"decision": "approve", "data": {}}
            
            # Find and resolve the pending decision
            decision_key = f"issue_{self.issue_number}"
            if decision_key in pending_decisions:
                if not pending_decisions[decision_key].done():
                    pending_decisions[decision_key].set_result(response_data)
            
            # Update the message
            embed = discord.Embed(
                title="✅ Approved",
                description=f"Issue #{self.issue_number} approved by {interaction.user.mention}\n\nExecuting actions on GitHub...",
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
            
            # Find and resolve the pending decision
            decision_key = f"issue_{self.issue_number}"
            if decision_key in pending_decisions:
                if not pending_decisions[decision_key].done():
                    pending_decisions[decision_key].set_result(response_data)
            
            # Update the message
            embed = discord.Embed(
                title="❌ Rejected",
                description=f"Issue #{self.issue_number} rejected by {interaction.user.mention}\n\nNo actions will be taken.",
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
            modal = ModifyModal(self.issue_number, self.severity, self.ai_text, self.is_duplicate)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error showing modify modal: {e}")
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
    
    async def on_timeout(self):
        """Handle view timeout."""
        try:
            # Set timeout response
            decision_key = f"issue_{self.issue_number}"
            if decision_key in pending_decisions:
                if not pending_decisions[decision_key].done():
                    pending_decisions[decision_key].set_result({
                        "decision": "timeout", 
                        "data": {}
                    })
            
            logger.warning(f"Triage action expired for issue #{self.issue_number}")
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")


@bot.event
async def on_ready():
    """Bot ready event."""
    logger.info(f'Triage Discord Bot ready! Logged in as {bot.user}')
    logger.info(f'Serving {len(bot.guilds)} servers')


async def send_triage_request(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send interactive triage request and wait for human decision."""
    # Initialize decision_key early to avoid UnboundLocalError
    issue_number = issue_data.get('issue_number', 0)
    decision_key = f"issue_{issue_number}"
    
    try:
        # Reload config to get latest values
        import importlib
        importlib.reload(config)
        
        channel_id = int(config.DISCORD_CHANNEL_ID)
        logger.info(f"Looking for Discord channel: {channel_id}")
        
        # Make sure bot is ready
        if not bot.is_ready():
            logger.warning("Bot is not ready, waiting...")
            await bot.wait_until_ready()
        
        channel = bot.get_channel(channel_id)
        
        if not channel:
            logger.error(f"Discord channel {channel_id} not found")
            logger.info(f"Available channels:")
            for guild in bot.guilds:
                logger.info(f"  Guild: {guild.name}")
                for ch in guild.text_channels:
                    logger.info(f"    #{ch.name} (ID: {ch.id})")
            # DO NOT AUTO-APPROVE - Raise error instead
            raise Exception(f"Discord channel {channel_id} not accessible - HUMAN INPUT REQUIRED")
        
        # Extract data
        issue_title = issue_data.get('issue_title', 'Unknown')
        issue_body = issue_data.get('issue_body', '')
        severity = issue_data.get('severity', 'Medium')
        ai_summary = issue_data.get('ai_summary', '')
        is_duplicate = issue_data.get('is_duplicate', False)
        similarity_score = issue_data.get('similarity_score')
        duplicate_issue_id = issue_data.get('duplicate_issue_id')
        
        # Create enhanced embed with more details
        severity_colors = {
            "Critical": discord.Color.red(),
            "High": discord.Color.orange(),
            "Medium": discord.Color.yellow(),
            "Low": discord.Color.green(),
            "Info": discord.Color.blue()
        }
        
        embed = discord.Embed(
            title=f"🥷 Triage Required: Issue #{issue_number}",
            description=f"**{issue_title}**\n{issue_body[:200] + ('...' if len(issue_body) > 200 else '')}",
            color=severity_colors.get(severity, discord.Color.blue())
        )
        
        # Add severity with reasoning
        severity_descriptions = {
            "Critical": "🔴 System down, data loss, security vulnerability",
            "High": "🟠 Major functionality broken, performance issues",
            "Medium": "🟡 Minor bugs with workarounds, feature requests",
            "Low": "🟢 Cosmetic issues, typos, documentation",
            "Info": "🔵 Questions, discussions, feedback"
        }
        
        embed.add_field(
            name="AI Severity Classification",
            value=f"**{severity}**\n{severity_descriptions.get(severity, '')}",
            inline=True
        )
        
        # Add impact assessment
        impact_level = {
            "Critical": "🔥 Immediate action required",
            "High": "⚡ High priority - address soon",
            "Medium": "📋 Standard workflow",
            "Low": "📝 Low priority - can be scheduled",
            "Info": "💬 Informational - review when convenient"
        }.get(severity, "📋 Standard workflow")
        
        embed.add_field(
            name="⚡ Impact Assessment",
            value=impact_level,
            inline=True
        )
        
        # Add duplicate or summary field with more details
        if is_duplicate and similarity_score and duplicate_issue_id:
            embed.add_field(
                name="🔍 Duplicate Analysis",
                value=f"**Duplicate Found ({similarity_score:.1%} Similarity)**\n"
                      f"Similar to Issue #{duplicate_issue_id}\n"
                      f"💡 *Recommend closing as duplicate*",
                inline=False
            )
            ai_text = f"This issue appears to be a duplicate of #{duplicate_issue_id} with {similarity_score:.1%} similarity. Consider closing this issue and directing the user to the original issue for updates."
        else:
            embed.add_field(
                name="📝 Detailed AI Analysis",
                value=ai_summary[:800] + ("..." if len(ai_summary) > 800 else ""),
                inline=False
            )
            ai_text = ai_summary
            
        # Add recommended actions
        if is_duplicate:
            recommended_actions = "🔄 Close as duplicate\n📝 Add explanatory comment\n🔗 Link to original issue"
        elif severity in ["Critical", "High"]:
            recommended_actions = f"🏷️ Add '{severity}' severity label\n📝 Post AI analysis\n🔔 Notify relevant team\n📊 Track in knowledge base"
        else:
            recommended_actions = f"🏷️ Add '{severity}' severity label\n📝 Post AI analysis\n📊 Add to knowledge base"
            
        embed.add_field(
            name="Recommended Actions",
            value=recommended_actions,
            inline=False
        )
        
        embed.set_footer(text="⏱️ Action required within 1 hour • Built with Portia AI")
        
        # Create view with buttons
        view = TriageView(issue_number, issue_title, severity, ai_text, is_duplicate)
        
        # Send message
        message = await channel.send(embed=embed, view=view)
        
        # Create future for waiting for response
        decision_key = f"issue_{issue_number}"
        pending_decisions[decision_key] = asyncio.Future()
        
        logger.info(f"Sent interactive triage request for issue #{issue_number}")
        
        # Wait for human decision (with manual timeout handling)
        start_time = asyncio.get_event_loop().time()
        timeout_duration = 3700  # Just over 1 hour
        
        while True:
            try:
                # Check if the future is done
                if pending_decisions[decision_key].done():
                    response = pending_decisions[decision_key].result()
                    break
                    
                # Check timeout manually
                if asyncio.get_event_loop().time() - start_time > timeout_duration:
                    logger.warning(f"Triage request timed out for issue #{issue_number}")
                    return {"decision": "timeout", "data": {}}
                
                # Sleep briefly to avoid busy waiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error while waiting for decision: {e}")
                return {"decision": "timeout", "data": {}}
        
        # Send completion message
        await send_completion_message(channel, message.id, "Discord User", issue_number, response)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to send interactive triage request: {e}")
        # DO NOT AUTO-APPROVE - Re-raise the error instead
        raise Exception(f"Discord integration failed: {e} - HUMAN INPUT REQUIRED")
        
    finally:
        # Clean up
        if decision_key in pending_decisions:
            del pending_decisions[decision_key]


async def send_completion_message(channel, original_message, approver_name: str, issue_number: int, response: Dict[str, Any]):
    """Send completion message after actions are executed."""
    try:
        # Determine what actions were taken based on response
        decision = response.get("decision")
        data = response.get("data", {})
        
        if decision == "approve":
            # Just report what the main agent will do/has done - don't execute actions here
            actions_planned = []
            
            if data.get("modified"):
                actions_planned.append("modified_by_human")
            
            # Report planned actions based on data
            severity = data.get("severity", "medium")
            actions_planned.append(f"severity_{severity.lower()}_label")
            
            if "summary" in data and data["summary"]:
                actions_planned.append("ai_summary_posted")
            elif "comment" in data and data["comment"]:
                actions_planned.append("duplicate_comment_posted")
                actions_planned.append("issue_closed_as_duplicate")
            
            action_summary = f"Issue #{issue_number} approved: " + ", ".join(actions_planned)
            
        elif decision == "reject":
            action_summary = f"Issue #{issue_number} rejected: no actions taken"
        else:
            action_summary = f"Issue #{issue_number} timed out: no actions taken"
        
        # Create completion embed
        embed = discord.Embed(
            title="✅ Triage Action Completed",
            description=f"Action completed as {decision} by **{approver_name}**",
            color=discord.Color.green() if decision == "approve" else discord.Color.orange()
        )
        
        embed.add_field(
            name="📋 Action Summary",
            value=action_summary,
            inline=False
        )
        
        embed.set_footer(text=f"Audit Trail • triage-{issue_number}")
        
        # Send as reply to original message
        await original_message.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Failed to send completion message: {e}")


# Function to start the bot
async def start_bot():
    """Start the Discord bot."""
    await bot.start(config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    # Run the bot
    asyncio.run(start_bot())
