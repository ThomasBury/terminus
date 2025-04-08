import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session

from terminus.database import get_session
from terminus.services.terminus_service import terminusService
from terminus.services.candidate_terminus_service import CandidateterminusService
from terminus.services.wikipedia_service import WikipediaService
from terminus.schemas import (
    terminusAnswer,
    terminusEntryCreate,
    CandidateterminusAnswer,
    CandidateValidation,
)
from terminus.utils import _extract_terms_async

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/candidates", response_model=CandidateterminusAnswer, status_code=201)
async def create_candidate(
    entry: terminusEntryCreate, session: Session = Depends(get_session)
) -> CandidateterminusAnswer:
    """
    Create a new candidate terminus entry.

    This endpoint validates that the term does not already exist in the official
    or candidate terminuss. It fetches a definition (using Wikipedia if not provided)
    and generates follow-up sub-term definitions.

    Parameters
    ----------
    entry : terminusEntryCreate
        Data for the candidate entry including term and optional definition.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    CandidateterminusAnswer
        The candidate entry as a Pydantic model.
    """
    terminus_service = terminusService(session)
    candidate_service = CandidateterminusService(session)

    # Ensure the term is not already defined officially or as a candidate
    if terminus_service.get(entry.term):
        raise HTTPException(409, "Term already in official terminus")
    if candidate_service.get(entry.term):
        raise HTTPException(409, "Candidate already exists")

    # Fetch definition from Wikipedia if not provided
    async with httpx.AsyncClient() as client:
        wikipedia = WikipediaService(client)
        definition = entry.definition or await wikipedia.query(entry.term)

        # Extract sub-terms and generate follow-up questions
        sub_terms = await _extract_terms_async(definition)
        follow_ups = []
        for t in sub_terms[:3]:
            sub_entry = terminus_service.get(t) or candidate_service.get(t)
            if sub_entry:
                sub_def = sub_entry.definition
            else:
                try:
                    sub_def = await wikipedia.query(t)
                except Exception as e:
                    logger.warning(
                        f"Could not fetch definition for follow-up term '{t}': {e}"
                    )
                    continue
            follow_ups.append(
                {"term": t, "question": f"What is {t}?", "definition": sub_def}
            )

    # Save the candidate entry with a pending status
    candidate_service.save(
        term=entry.term, definition=definition, follow_ups=follow_ups, status="pending"
    )
    candidate_answer = candidate_service.get_as_pydantic(entry.term)
    return candidate_answer


@router.post("/candidates/validate", response_model=terminusAnswer)
async def validate_candidate(
    validation: CandidateValidation, session: Session = Depends(get_session)
) -> terminusAnswer:
    """
    Validate a candidate terminus entry.

    If approved, the candidate is moved to the official terminus.
    Otherwise, it is rejected.

    Parameters
    ----------
    validation : CandidateValidation
        Contains the term and approval flag.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    terminusAnswer
        The newly validated official terminus entry.
    """
    candidate_service = CandidateterminusService(session)
    terminus_service = terminusService(session)

    candidate_db_obj = candidate_service.get(validation.term)
    if not candidate_db_obj:
        raise HTTPException(404, "Candidate not found")

    if not validation.approve:
        candidate_service.reject(validation.term, reason="Disapproved by user")
        raise HTTPException(400, "Candidate rejected")

    follow_ups_list = candidate_service._deserialize_follow_ups(
        candidate_db_obj.follow_ups
    )
    terminus_service.save(
        term=candidate_db_obj.term,
        definition=candidate_db_obj.definition,
        follow_ups=follow_ups_list,
    )
    # Delete candidate entry after moving to official terminus
    candidate_service.delete(candidate_db_obj.term)

    official = terminus_service.get_as_pydantic(candidate_db_obj.term)
    if not official:
        raise HTTPException(500, "Error saving candidate to official terminus")
    return official


@router.get("/candidates/{term}", response_model=CandidateterminusAnswer)
async def get_candidate(
    term: str, session: Session = Depends(get_session)
) -> CandidateterminusAnswer:
    """
    Retrieve a candidate terminus entry.

    Parameters
    ----------
    term : str
        The candidate term to retrieve.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    CandidateterminusAnswer
        The candidate entry as a Pydantic model.
    """
    candidate_service = CandidateterminusService(session)
    candidate_answer = candidate_service.get_as_pydantic(term)
    if not candidate_answer:
        raise HTTPException(404, "Candidate not found")
    return candidate_answer


@router.delete("/candidates/{term}", status_code=204)
async def delete_candidate(
    term: str, session: Session = Depends(get_session)
) -> Response:
    """
    Delete a candidate terminus entry.

    Parameters
    ----------
    term : str
        The candidate term to delete.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    Response
        HTTP 204 response if deletion is successful.
    """
    if not CandidateterminusService(session).delete(term):
        raise HTTPException(404, "Candidate not found")
    return Response(status_code=204)
