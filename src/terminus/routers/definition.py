import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Response
from sqlalchemy.orm import Session

from terminus.database import get_session
from terminus.services.terminus_service import terminusService
from terminus.services.candidate_terminus_service import CandidateterminusService
from terminus.services.wikipedia_service import WikipediaService
from terminus.services.llm_service import DefinitionValidationService, FUService
from terminus.schemas import terminusAnswer


from terminus.config import settings
import asyncio
from typing import List, Dict, Optional, Any  # Ensure these are imported

logger = logging.getLogger(__name__)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/definition/{term}", response_model=terminusAnswer)
async def get_definition(
    term: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> terminusAnswer:
    """
    Retrieve the definition for a given term.

    Checks official terminus first. If not found, checks candidate terminus.
    If not in either, queues a background task to fetch, validate, and store
    the definition, then returns a placeholder response.
    """
    term = term.strip().lower()  # Normalize here too for consistency
    terminus_service = terminusService(session)
    candidate_service = CandidateterminusService(session)

    # Check official DB (Synchronous call - okay in sync route handler)
    if lex_answer := terminus_service.get_as_pydantic(term):
        logger.info(f"Cache hit for '{term}' in official terminus.")
        return lex_answer

    # Check candidate DB (Synchronous call - okay in sync route handler)
    # One might want to tailor the response based on candidate status later
    if cand_answer := candidate_service.get_as_pydantic(term):
        logger.info(
            f"Cache hit for '{term}' in candidate terminus (status: {cand_answer.status}). Returning placeholder."
        )
        # Return the standard placeholder - the background task won't run again
        # because the pre-check inside the task will find it.
        return terminusAnswer(
            term=term,
            definition="I don't know yet, please check back later",
            follow_ups=[],
        )

    # If not found anywhere, queue the *new* background task
    logger.info(
        f"Term '{term}' not found in cache. Queuing background task for generation and validation."
    )
    background_tasks.add_task(
        _fetch_validate_and_store_definition, term
    )  # Use the new task function

    # Return placeholder response while background task runs
    return terminusAnswer(
        term=term, definition="I don't know yet, please check back later", follow_ups=[]
    )


@router.delete("/definition/{term}", status_code=204)
async def delete_definition(
    term: str, session: Session = Depends(get_session)
) -> Response:
    """
    Delete an official definition for a given term.

    Parameters
    ----------
    term : str
        The term whose definition is to be deleted.
    session : Session, optional
        SQLAlchemy session provided by dependency injection.

    Returns
    -------
    Response
        HTTP 204 response if deletion is successful.
    """
    if not terminusService(session).delete(term):
        raise HTTPException(404, "Term not found")
    return Response(status_code=204)


# --- Define constants for status clarity ---
# (These might match constants in your main actions/routes file if you have one)
STATUS_FOUND_IN_DB = "FOUND_IN_DB"
STATUS_CREATED_VALID = "CREATED_VALID"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_NOT_FOUND = "NOT_FOUND"
STATUS_ERROR = "ERROR"


async def _fetch_validate_and_store_definition(term: str) -> None:
    """
    Background task to fetch, validate, and store a definition.

    1. Checks caches (official and candidate DBs).
    2. Fetches candidate definition from Wikipedia.
    3. Validates the definition using an LLM (DefinitionValidationService).
    4. If valid:
        - Generates follow-up questions using an LLM (FUService).
        - Saves the term, definition, and follow-ups to the official terminus DB.
    5. If invalid:
        - Saves the term, definition, and rejection reason to the Candidate DB.

    Parameters
    ----------
    term : str
        The term for which to generate and store the definition.
    """
    term = term.strip().lower()  # Normalize term
    logger.info(f"[Background Task] Starting process for term: '{term}'")

    # Create a new session specifically for this background task
    # Use try/finally to ensure session is always closed
    session: Optional[Session] = None
    try:
        session = next(get_session())  # Get a synchronous session
        # Instantiate services needed for this task
        terminus_service = terminusService(session)
        candidate_service = CandidateterminusService(session)
        wiki_service = WikipediaService()
        validation_service = DefinitionValidationService(model=settings.llm_model)
        fu_service = FUService(model=settings.llm_model)

        # --- 1. Pre-checks (Avoid redundant work / race conditions) ---
        # Check official DB
        logger.debug(f"[Background Task] Checking primary terminus cache for '{term}'")
        # Run synchronous DB check in a separate thread
        exists_in_terminus = await asyncio.to_thread(terminus_service.exists, term)
        if exists_in_terminus:
            logger.info(
                f"[Background Task] Term '{term}' already exists in the official terminus. Skipping."
            )
            return

        # Check candidate DB
        logger.debug(
            f"[Background Task] Checking candidate terminus cache for '{term}'"
        )
        # Run synchronous DB check in a separate thread
        exists_in_candidate = await asyncio.to_thread(candidate_service.exists, term)
        if exists_in_candidate:
            logger.info(
                f"[Background Task] Term '{term}' already exists in the candidate terminus. Skipping."
            )
            # Note: You might want more nuanced logic here, e.g., re-process if status was 'failed'?
            return

        # --- 2. Fetch Candidate Definition from Wikipedia ---
        logger.info(f"[Background Task] Fetching '{term}' definition from Wikipedia.")
        try:
            # WikipediaService.query is already async
            candidate_summary = await wiki_service.query(term)
        except Exception as e:
            logger.exception(
                f"[Background Task] Error fetching from Wikipedia for '{term}': {e}"
            )
            # Optionally save to candidate DB with 'wikipedia_error' status
            error_status = f"wikipedia_error: {str(e)[:200]}"  # Truncate error
            await asyncio.to_thread(
                candidate_service.save,
                term,
                f"Error fetching: {e}",
                [],
                status=error_status,
            )
            return  # Stop processing this term

        # Handle known failure messages from WikipediaService
        if candidate_summary.startswith(
            "Could not find"
        ) or candidate_summary.startswith("An error occurred"):
            logger.warning(
                f"[Background Task] WikipediaService could not find or failed for '{term}': {candidate_summary}"
            )
            # Save to candidate DB with 'wikipedia_failed' status
            fail_status = (
                f"wikipedia_failed: {candidate_summary[:200]}"  # Truncate message
            )
            await asyncio.to_thread(
                candidate_service.save, term, candidate_summary, [], status=fail_status
            )
            return  # Stop processing this term
        elif candidate_summary.startswith("Please provide"):
            logger.error(
                f"[Background Task] Invalid term provided to WikipediaService for '{term}'."
            )
            # Don't save this, it was likely an empty term initially
            return

        # --- 3. Validate Definition using LLM ---
        logger.info(f"[Background Task] Validating definition for '{term}'...")
        try:
            # DefinitionValidationService.validate_definition is async
            validation_result = await validation_service.validate_definition(
                term, candidate_summary
            )
        except Exception as e:
            logger.exception(
                f"[Background Task] Error during LLM validation call for '{term}': {e}"
            )
            # Optionally save to candidate DB with 'validation_error' status
            error_status = f"validation_error: {str(e)[:200]}"  # Truncate error
            await asyncio.to_thread(
                candidate_service.save, term, candidate_summary, [], status=error_status
            )
            return  # Stop processing

        if validation_result is None:
            logger.error(
                f"[Background Task] LLM validation returned None for '{term}'."
            )
            # Save to candidate DB with 'validation_failed' status
            fail_status = "validation_failed: LLM returned no result"
            await asyncio.to_thread(
                candidate_service.save, term, candidate_summary, [], status=fail_status
            )
            return  # Stop processing

        # --- 4. Process Based on Validation Result ---
        if validation_result.is_valid:
            logger.info(
                f"[Background Task] Definition for '{term}' PASSED validation. Confidence: {validation_result.confidence:.2f}"
            )

            # --- 4a. Generate Follow-ups (Only if Valid) ---
            logger.info(
                f"[Background Task] Generating follow-up questions for '{term}'..."
            )

            #########################################################################
            # This block extracts related user-defined terms from the validated definition
            # look up the definition in the database and on wikipedia if not found
            # Then call the LLM to validate the definition
            # Not optimized for performance nor cost
            ##########################################################################S

            # # Extract related user-defined terms from the main term's validated definition
            # related_terms = await _extract_terms_async(candidate_summary)
            # follow_ups_to_save: List[Dict[str, Any]] = []

            # for sub_term in related_terms[:5]:
            #     if sub_term.lower() == term.lower():
            #         continue  # Skip if it's the same as the main term

            #     # Try to get sub-term from DB
            #     sub_entry = await asyncio.to_thread(
            #         lambda: terminus_service.get(sub_term) or candidate_service.get(sub_term)
            #     )
            #     if sub_entry:
            #         sub_def = sub_entry.definition
            #     else:
            #         try:
            #             sub_def = await wiki_service.query(sub_term)
            #         except Exception as e:
            #             logger.warning(f"Skipping sub-term '{sub_term}' due to Wikipedia error: {e}")
            #             continue

            #         # Validate the sub-definition
            #         try:
            #             validation = await validation_service.validate_definition(sub_term, sub_def)
            #             if not validation or not validation.is_valid:
            #                 logger.info(
            #                     f"Skipping sub-term '{sub_term}' due to failed validation: {getattr(validation, 'reasoning', 'No reason')}"
            #                 )
            #                 continue  # Only keep valid sub-term definitions
            #         except Exception as e:
            #             logger.warning(f"Skipping sub-term '{sub_term}' due to validation error: {e}")
            #             continue

            #     # Add validated follow-up entry
            #     follow_ups_to_save.append(
            #         FollowUp(
            #             term=sub_term,
            #             question=f"What is {sub_term}?",
            #             definition=sub_def,
            #         ).model_dump()
            #     )

            follow_ups_to_save: List[Dict[str, Any]] = []
            try:
                # FUService.generate_followups is async
                # Ensure FUService returns terminusAnswer or similar with follow_ups list
                llm_answer: Optional[
                    terminusAnswer
                ] = await fu_service.generate_followups(term, candidate_summary)

                if llm_answer and llm_answer.follow_ups:
                    # Convert FollowUp Pydantic models to dicts for saving
                    follow_ups_to_save = [
                        fu.model_dump() for fu in llm_answer.follow_ups
                    ]
                    logger.info(
                        f"[Background Task] Generated {len(follow_ups_to_save)} follow-ups for '{term}'."
                    )
                else:
                    logger.warning(
                        f"[Background Task] Failed to generate follow-ups for validated term '{term}'. Saving definition without follow-ups."
                    )

            except Exception as e:
                logger.exception(
                    f"[Background Task] Error generating follow-ups for '{term}': {e}. Saving definition without follow-ups."
                )
                # Proceed to save the definition anyway, as it was validated

            # --- 4b. Save to Official terminus DB ---
            logger.info(
                f"[Background Task] Saving validated definition and follow-ups for '{term}' to official DB."
            )
            try:
                # Run synchronous save in a separate thread
                await asyncio.to_thread(
                    terminus_service.save,
                    term,
                    candidate_summary,
                    follow_ups_to_save,  # Pass the list of dicts
                )
                logger.info(
                    f"[Background Task] Successfully saved '{term}' to official DB."
                )
            except Exception as e:
                logger.exception(
                    f"[Background Task] Failed to save validated term '{term}' to official DB: {e}"
                )
                # Decide recovery strategy: maybe save to candidate as 'save_error'?
                error_status = f"save_to_official_error: {str(e)[:200]}"
                await asyncio.to_thread(
                    candidate_service.save,
                    term,
                    candidate_summary,
                    follow_ups_to_save,
                    status=error_status,
                )

        else:
            # --- 5. Validation Failed: Save to Candidate DB ---
            logger.warning(
                f"[Background Task] Definition for '{term}' FAILED validation. Reason: {validation_result.reasoning}"
            )
            # Construct status message from reason, truncate if necessary
            # Max length depends on your CandidateterminusEntry.status column size
            max_status_len = 255  # Example limit
            status_reason = f"rejected_llm: {validation_result.reasoning}"
            if len(status_reason) > max_status_len:
                status_reason = status_reason[: max_status_len - 3] + "..."

            logger.info(
                f"[Background Task] Saving '{term}' to candidate DB for review with status: '{status_reason}'."
            )
            try:
                # Run synchronous save in a separate thread
                await asyncio.to_thread(
                    candidate_service.save,
                    term,
                    candidate_summary,
                    [],  # No follow-ups generated for rejected candidates
                    status=status_reason,
                )
                logger.info(
                    f"[Background Task] Successfully saved '{term}' to candidate DB."
                )
            except Exception as e:
                logger.exception(
                    f"[Background Task] Failed to save rejected term '{term}' to candidate DB: {e}"
                )
                # Log error, might be hard to recover state here.

    except Exception as e:
        # Catch-all for unexpected errors during the task setup or flow
        logger.exception(
            f"[Background Task] An unexpected error occurred processing term '{term}': {e}"
        )

    finally:
        # Ensure the session is closed regardless of success or failure
        if session:
            session.close()
            logger.debug(
                f"[Background Task] Database session closed for term '{term}'."
            )
        logger.info(f"[Background Task] Finished process for term: '{term}'.")
