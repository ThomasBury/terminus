from typing import List
from pydantic import BaseModel, Field

from terminus.config import settings


class FollowUp(BaseModel):
    """
    You are an assistant helping users understand user-defined topic terms by breaking them down.
    For each key term, generate a follow-up question and optionally provide a brief definition.
    """

    term: str = Field(
        ..., description="The follow-up term related to the original query."
    )
    question: str = Field(
        ...,
        description="A concise question that can help the user explore the follow-up term appearing in the definition of the original query.",
    )
    definition: str = Field(
        ..., description="A brief definition of the follow-up term."
    )


class terminusAnswer(BaseModel):
    """
    You return a clear user-defined topic term definition along with related follow-up questions to deepen understanding.
    """

    term: str = Field(
        ..., description=f"The main {settings.topic_domain} term being defined."
    )
    definition: str = Field(
        ..., description="A clear, concise, and factual definition of the term."
    )
    follow_ups: List[FollowUp] = Field(
        ..., description="A list of up to 3 follow-up questions related to sub-terms."
    )


class terminusEntryCreate(BaseModel):
    """
    Represents user input to create a new terminus entry.
    The user may provide a definition, or the system will fetch one automatically.
    """

    term: str = Field(..., description=f"The {settings.topic_domain} term to define.")
    definition: str = Field(
        ..., description="User-provided definition. If not given, use Wikipedia or LLM."
    )


class CandidateterminusAnswer(BaseModel):
    """
    Represents a generated terminus entry that is pending review before becoming official.
    """

    term: str = Field(..., description="The candidate term being evaluated.")
    definition: str = Field(
        ..., description="Auto-generated or Wikipedia-based definition of the term."
    )
    follow_ups: List[FollowUp] = Field(
        ..., description="List of follow-up questions generated for this term."
    )
    status: str = Field(
        ..., description="Validation status such as 'pending' or 'under_review'."
    )

    class Config:
        from_attributes = True


class CandidateValidation(BaseModel):
    """
    Represents a review decision for a candidate term.
    Use this to approve or reject whether a generated entry should be moved to the official terminus.
    """

    term: str = Field(..., description="The candidate term to validate.")
    approve: bool = Field(
        ...,
        description="Set to true to promote the candidate to the official terminus.",
    )
    reason: str = Field(..., description="Concise reason for the decision.")


class ExtractedTerm(BaseModel):
    """
    Represents a term relevant to the configured topic domain, extracted from text.
    """

    term: str = Field(
        ...,
        description=f"A single {settings.topic_domain} term identified in the input text.",
    )


class ExtractedTerms(BaseModel):
    """
    A list of topic-relevant terms extracted from user input, intended for further processing or tagging.
    """

    terms: List[ExtractedTerm] = Field(
        ...,
        description=f"A list of {settings.topic_domain} terms extracted from user input.",
    )


class TermCritique(BaseModel):
    """
    You are a domain expert asked to determine whether a term is relevant to the topic domain.
    Justify your decision clearly and concisely based on the current subject area.
    """

    term: str = Field(
        ...,
        description=f"The term being evaluated for {settings.topic_domain} relevance.",
    )
    is_relevant: bool = Field(
        ...,
        description=f"Set to true if the term is relevant to {settings.topic_domain}.",
    )
    reason: str = Field(
        ...,
        description=f"Explanation of why the term is or isn't relevant to {settings.topic_domain}.",
    )


class DefinitionValidationResult(BaseModel):
    """
    You are a meticulous user-defined topic expert and editor tasked with validating definitions.
    Focus solely on the user-defined topic/economic context.
    """

    is_valid: bool = Field(
        ...,
        description=f"Is the information factually correct within the {settings.topic_domain} context?",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence level of the validation."
    )
    reasoning: str = Field(..., description="Your reasoning for the validation.")
