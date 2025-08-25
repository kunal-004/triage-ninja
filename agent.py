import asyncio
import logging
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv # type: ignore
from portia import Config, Portia, DefaultToolRegistry, LogLevel # type: ignore

import config
from tools.ai_tools_portia import ai_manager
from tools.weaviate_tools_portia import weaviate_manager
from tools.discord_tools_portia import discord_manager, TriageClarification
from tools.github_tools_portia import github_manager

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TriageState:
    def __init__(self, issue_data: Dict[str, Any]):
        self.issue_id = issue_data.get('number', 0)
        self.issue_title = issue_data.get('title', 'Unknown')
        self.issue_body = issue_data.get('body', '')
        self.issue_url = issue_data.get('html_url', '')
        self.repository = issue_data.get('repository', {}).get('full_name', 'unknown/repo')
        self.severity: Optional[str] = None
        self.ai_summary: Optional[str] = None
        self.is_duplicate: bool = False
        self.similarity_score: Optional[float] = None
        self.duplicate_issue_id: Optional[int] = None
        self.proposed_comment: Optional[str] = None
        self.human_decision: Optional[Dict[str, Any]] = None
        self.actions_executed: Dict[str, bool] = {}
        self.completion_message_sent: bool = False


class SophisticatedTriageAgent:
    def __init__(self):
        self.portia = None
        self._setup_portia()
    
    def _setup_portia(self):
        try:
            # Set the API key for Gemini
            if config.GEMINI_API_KEY:
                import google.generativeai as genai # type: ignore
                genai.configure(api_key=config.GEMINI_API_KEY)
            
            if config.PORTIA_API_KEY:
                os.environ["PORTIA_API_KEY"] = config.PORTIA_API_KEY
            
            portia_config = Config.from_default(default_log_level=LogLevel.INFO)
            self.portia = Portia(
                config=portia_config,
                tools=DefaultToolRegistry(portia_config),
            )
            logger.info("Portia agent initialized")
        except Exception as e:
            logger.error(f"Portia setup failed: {e}")
            self.portia = None

    async def triage_new_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        state = TriageState(issue_data)
        logger.info(f"Starting triage for issue #{state.issue_id}: {state.issue_title}")
        
        try:
            await self._perform_ai_analysis(state)
            await self._perform_duplicate_detection(state)
            await self._request_human_clarification(state)
            await self._execute_decision(state)
            await self._send_completion_notification(state)
            
            return {
                'success': True,
                'issue_number': state.issue_id,
                'severity': state.severity,
                'ai_summary': state.ai_summary,
                'is_duplicate': state.is_duplicate,
                'similarity_score': state.similarity_score,
                'human_decision': state.human_decision,
                'actions_executed': state.actions_executed,
                'completion_notification_sent': state.completion_message_sent
            }
        except Exception as e:
            logger.error(f"Triage failed for issue #{state.issue_id}: {e}")
            return {
                'success': False,
                'issue_number': state.issue_id,
                'error': str(e)
            }
    
    async def _perform_ai_analysis(self, state: TriageState):
        try:
            state.severity = ai_manager.classify_severity(state.issue_title, state.issue_body)
            logger.info(f"AI Severity Classification: {state.severity}")
            state.ai_summary = ai_manager.summarize_issue(state.issue_title, state.issue_body)
            logger.info(f"AI Summary generated: {state.ai_summary[:100]}...")
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            state.severity = "Medium"
            state.ai_summary = f"Issue: {state.issue_title}"

    async def _perform_duplicate_detection(self, state: TriageState):
        try:
            duplicate_id, similarity_score = weaviate_manager.find_duplicate(
                state.issue_title, state.issue_body, threshold=0.85
            )
            if duplicate_id and similarity_score:
                state.is_duplicate = True
                state.similarity_score = similarity_score
                state.duplicate_issue_id = duplicate_id
                state.proposed_comment = ai_manager.draft_duplicate_comment(
                    duplicate_id, similarity_score
                )
                logger.warning(f"Duplicate detected: #{duplicate_id} (Similarity: {similarity_score:.1%})")
            else:
                logger.info("No duplicates found")
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            state.is_duplicate = False

    async def _request_human_clarification(self, state: TriageState):
        try:
            clarification = TriageClarification(
                issue_title=state.issue_title,
                issue_number=state.issue_id,
                severity=state.severity,
                ai_summary=state.ai_summary,
                issue_body=state.issue_body,
                is_duplicate=state.is_duplicate,
                similarity_score=state.similarity_score,
                duplicate_issue_id=state.duplicate_issue_id
            )
            state.human_decision = await discord_manager.send_triage_request(clarification)
            logger.info(f"👤 Human decision received: {state.human_decision.get('decision')}")
        except Exception as e:
            logger.error(f"Human clarification failed: {e}")
            raise Exception(f"Human clarification required but failed: {e}")

    async def _execute_decision(self, state: TriageState):
        decision = state.human_decision.get("decision")
        modified_data = state.human_decision.get("data", {})
        if decision == "approve":
            logger.info(f"Executing approved plan for issue #{state.issue_id}")
            comment = modified_data.get("comment", state.proposed_comment)
            
            if state.is_duplicate:
                try:
                    success = github_manager.post_comment(state.issue_id, comment)
                    state.actions_executed["comment_posted"] = success
                    success = github_manager.add_label(state.issue_id, "duplicate")
                    state.actions_executed["duplicate_label_added"] = success
                    success = github_manager.close_issue(state.issue_id, "duplicate")
                    state.actions_executed["issue_closed"] = success
                except Exception as e:
                    logger.error(f"Error executing duplicate actions: {e}")
                    state.actions_executed["error"] = str(e)
            else:
                severity_label = modified_data.get("severity", state.severity)
                summary = modified_data.get("summary", state.ai_summary)
                
                try:
                    success = github_manager.add_label(state.issue_id, severity_label)
                    state.actions_executed["severity_label_added"] = success
                    
                    severity_emoji = {
                        "Critical": "🔴", "High": "🟠", "Medium": "🟡",
                        "Low": "🟢", "Info": "🔵"
                    }.get(severity_label, "📋")
                    
                    summary_comment = f"""## {severity_emoji} AI Triage Analysis

**Severity Classification:** {severity_label}

**Analysis Summary:**
{summary}

**Recommended Actions:**
- Issue has been classified as **{severity_label}** priority
- Appropriate severity label has been applied
- Issue details have been recorded in the knowledge base

*This analysis was generated by AI and approved by a human triager.*"""
                    
                    success = github_manager.post_comment(state.issue_id, summary_comment)
                    state.actions_executed["summary_posted"] = success
                    
                    # Add to Weaviate now that it's confirmed not a duplicate
                    weaviate_manager.add_issue(state.issue_id, state.issue_title, state.issue_body)
                    state.actions_executed["added_to_knowledge_base"] = True
                    
                except Exception as e:
                    logger.error(f"Error executing new issue actions: {e}")
                    state.actions_executed["error"] = str(e)
                    
        elif decision == "reject":
            logger.info(f"Plan rejected for issue #{state.issue_id}. No actions taken.")
            state.actions_executed["rejected"] = True
            
        elif decision == "timeout":
            logger.warning(f"⏰ Action timed out for issue #{state.issue_id}. No actions taken.")
            state.actions_executed["timed_out"] = True
    
    async def _send_completion_notification(self, state: TriageState):
        """Phase 5: Send completion notification with audit trail."""
        try:
            approver_name = "Discord User"  # In real implementation, get from Discord interaction
            
            # Create action summary
            executed_actions = [k for k, v in state.actions_executed.items() if v]
            action_summary = f"Issue #{state.issue_id} processed: " + ", ".join(executed_actions)
            
            # Send completion message
            success = discord_manager.send_completion_message(
                channel_id="general",  # Would use actual channel ID
                original_message_id=f"triage-{state.issue_id}",
                approver_name=approver_name,
                action_summary=action_summary
            )
            
            state.completion_message_sent = success
            
            if success:
                logger.info(f"📬 Completion notification sent for issue #{state.issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")


_sophisticated_agent = None

def get_agent():
    global _sophisticated_agent
    if _sophisticated_agent is None:
        _sophisticated_agent = SophisticatedTriageAgent()
    return _sophisticated_agent

async def process_webhook(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        action = webhook_data.get('action', '')
        if action != 'opened':
            return {
                'success': True,
                'skipped': True,
                'reason': f'Only processing "opened" issues, got: {action}'
            }
        
        issue_data = webhook_data.get('issue', {})
        agent = get_agent()
        result = await agent.triage_new_issue(issue_data)
        result['webhook_action'] = action
        return result
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'webhook_processed': False
        }

async def triage_issue(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    agent = get_agent()
    return await agent.triage_new_issue(issue_data)
