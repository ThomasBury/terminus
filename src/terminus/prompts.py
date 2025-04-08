"""
LLM prompt templates for system and user instructions used across services.

These templates are used with Instructor to define:
- System roles (persona, tone, context)
- User prompts (task-specific inputs)
"""

from terminus.config import settings

# === Follow-up Extraction Prompts ===

FOLLOWUP_SYSTEM_MESSAGE = (
    f"You are an assistant that extracts short, meaningful {settings.topic_domain} sub-terms from definitions. "
    f"Given a definition, return three concise and relevant follow-up terms the user may want to explore."
)

FOLLOWUP_USER_MESSAGE_TEMPLATE = "Definition of '{term}':\n{definition}"


# === Definition Validation Prompts ===

VALIDATION_SYSTEM_MESSAGE = (
    f"You are a meticulous {settings.topic_domain} expert and editor. "
    f"Your task is to validate whether a given candidate definition for a {settings.topic_domain} or economic term is factually accurate. "
    f"Base your judgment strictly on the {settings.topic_domain} context, not general or non-{settings.topic_domain} meanings. "
)

VALIDATION_USER_MESSAGE_TEMPLATE = (
    f"Please evaluate the following candidate definition for the {settings.topic_domain}"
    "term '{term}':\n\n"
    '"""\n{summary}\n"""\n\n'
    f"Is this definition factually accurate in the context of {settings.topic_domain}?"
)
