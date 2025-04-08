import httpx
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from terminus.database import get_session
from terminus.services.terminus_service import terminusService
from terminus.services.candidate_terminus_service import CandidateterminusService
from terminus.services.llm_service import TermExtractionService
from terminus.services.wikipedia_service import WikipediaService
from terminus.schemas import ExtractedTerms
from terminus.utils import _extract_terms_async
from terminus.config import settings

router = APIRouter()


@router.post("/terms/extract", response_model=ExtractedTerms)
async def extract_terms(text: str = Body(..., embed=True)) -> ExtractedTerms:
    """
    Extract validated user-defined terms from the provided text.

    Parameters
    ----------
    text : str
        Input text from which user-defined terms are to be extracted.

    Returns
    -------
    ExtractedTerms
        A list of extracted user-defined terms formatted as per the response schema.
    """
    extraction_service = TermExtractionService(model=settings.llm_model)
    validated_terms = await extraction_service.validate_terms(text, temperature=0.0)
    terms = [{"term": t} for t in validated_terms]
    return ExtractedTerms(terms=terms)


@router.post("/terms/precompute", response_model=dict)
async def precompute_terms(
    text: str = Body(..., embed=True), session: Session = Depends(get_session)
) -> dict:
    """
    Precompute definitions and follow-up questions for user-defined terms extracted from text.

    This endpoint extracts user-defined terms, fetches their definitions via Wikipedia,
    generates follow-up questions, and saves them as candidate entries if they don't exist.

    Parameters
    ----------
    text : str
        Input text to analyze for user-defined terms.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    dict
        A dictionary containing the added terms and a completion message.
    """
    terminus_service = terminusService(session)
    candidate_service = CandidateterminusService(session)
    extraction_service = TermExtractionService()

    async with httpx.AsyncClient() as client:
        wikipedia_service = WikipediaService(client)

        # Extract validated user-defined terms from the input text
        validated_terms = await extraction_service.validate_terms(text, temperature=0.0)
        added_terms = []
        for term in validated_terms:
            # Skip terms that already exist in either terminus
            if terminus_service.get(term) or candidate_service.get(term):
                continue

            # Fetch definition from Wikipedia
            definition = await wikipedia_service.query(term)
            # Extract related sub-terms for follow-up questions
            related_terms = await _extract_terms_async(definition)
            follow_ups = []
            for sub_term in related_terms[:3]:
                if sub_term.lower() == term.lower():
                    continue
                sub_def = await wikipedia_service.query(sub_term)
                follow_ups.append(
                    {
                        "term": sub_term,
                        "question": f"What is {sub_term}?",
                        "definition": sub_def,
                    }
                )

            # Save candidate entry with pending status
            candidate_service.save(term, definition, follow_ups, status="pending")
            added_terms.append(term)

    session.close()
    return {"added_terms": added_terms, "message": "Precompute completed"}
