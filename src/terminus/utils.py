from terminus.services.llm_service import TermExtractionService
from terminus.config import settings


async def _extract_terms_async(definition: str) -> list[str]:
    """
    Extract terms from a given definition asynchronously.

    This function uses the `TermExtractionService` to validate and extract
    terms from the provided definition. It is designed to run asynchronously
    to support non-blocking operations.

    Parameters
    ----------
    definition : str
        The text definition from which user-defined terms will be extracted.

    Returns
    -------
    list of str
        A list of validated  terms extracted from the definition.
    """
    # Initialize the term extraction service
    extractor = TermExtractionService(model=settings.llm_model)

    # Use the service to validate and extract terms with a low temperature for deterministic results
    return await extractor.validate_terms(definition, temperature=0.0)
