import logging
import instructor
from litellm import acompletion, APIConnectionError
from abc import ABC
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel

from terminus.schemas import (
    terminusAnswer,
    ExtractedTerms,
    TermCritique,
    DefinitionValidationResult,
)
from terminus.prompts import (
    VALIDATION_USER_MESSAGE_TEMPLATE,
    VALIDATION_SYSTEM_MESSAGE,
    FOLLOWUP_SYSTEM_MESSAGE,
    FOLLOWUP_USER_MESSAGE_TEMPLATE,
)
from terminus.config import settings


logger = logging.getLogger(__name__)


class BaseLLMService(ABC):
    """
    Abstract base class for LLM services.

    Attributes
    ----------
    model : str
        The model identifier to be used for generating responses.
    response_model : Type[BaseModel]
        The Pydantic model to structure the response.
    client : Any
        The client instance for interacting with the LLM API.
    system_message : str
        The system message to be included in the conversation context.

    Methods
    -------
    build_messages(user_message: str) -> List[Dict[str, str]]
        Constructs the message list for the LLM API call.
    generate_response(messages: List[Dict[str, str]], temperature: float = 0.0, **kwargs) -> BaseModel | None
        Generates a response from the LLM based on the provided messages.
    """

    def __init__(
        self,
        model: str,
        response_model: Type[BaseModel],
        client: Any = instructor.from_litellm(acompletion),
        system_message: str = "",
    ):
        self.model = model
        self.response_model = response_model
        self.client = client
        self.system_message = system_message

    def build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """
        Constructs the message list for the LLM API call.

        Parameters
        ----------
        user_message : str
            The user message to be included in the conversation context.

        Returns
        -------
        List[Dict[str, str]]
            The list of messages formatted for the LLM API.
        """
        return [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": user_message},
        ]

    async def generate_response(
        self, messages: List[Dict[str, str]], temperature: float = 0.0, **kwargs
    ) -> BaseModel | None:
        """
        Generates a response from the LLM based on the provided messages.

        Parameters
        ----------
        messages : List[Dict[str, str]
            The list of messages to be sent to the LLM API.
        temperature : float, optional
            The temperature parameter for the LLM, by default 0.0.
        **kwargs
            Additional keyword arguments for the LLM API call.

        Returns
        -------
        BaseModel | None
            The structured response from the LLM, or None if an error occurs.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                response_model=self.response_model,
                messages=messages,
                **kwargs,
            )
            return response
        except APIConnectionError as e:
            logger.error(f"API connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return self.response_model() if self.response_model else None


class FUService(BaseLLMService):
    """
    Service for generating follow-up questions based on a definition.

    Attributes
    ----------
    user_message_template : str
        The template for the user message to be included in the conversation context.

    Methods
    -------
    generate_followups(term: str, definition: str, temperature: float = 0.0) -> terminusAnswer | None
        Generates follow-up questions based on the provided term and definition.
    """

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        response_model: Type[BaseModel] = terminusAnswer,
        system_message: str = FOLLOWUP_SYSTEM_MESSAGE,
        user_message_template: str = FOLLOWUP_USER_MESSAGE_TEMPLATE,
        client: Any = instructor.from_litellm(acompletion),
    ):
        super().__init__(model, response_model, client, system_message)
        self.user_message_template = user_message_template

    async def generate_followups(
        self, term: str, definition: str, temperature: float = 0.0
    ) -> terminusAnswer | None:
        """
        Generates follow-up questions based on the provided term and definition.

        Parameters
        ----------
        term : str
            The term for which follow-up questions are generated.
        definition : str
            The definition of the term.
        temperature : float, optional
            The temperature parameter for the LLM, by default 0.0.

        Returns
        -------
        terminusAnswer | None
            The structured response containing follow-up questions, or None if an error occurs.
        """
        user_message = self.user_message_template.format(
            term=term, definition=definition
        )
        messages = self.build_messages(user_message)
        return await self.generate_response(messages, temperature=temperature)


class DefinitionValidationService(BaseLLMService):
    """
    Uses an LLM to validate a candidate definition for a given user-defined term.

    This service sends a structured prompt to the LLM, based on the term and its definition,
    and parses the result into a `DefinitionValidationResult`.

    Parameters
    ----------
    model : str
        LLM model identifier (default: 'gemini/gemini-2.0-flash').
    response_model : Type[BaseModel]
        Pydantic model to structure and validate the LLM output.
    client : Any
        LLM client object initialized through Instructor + LiteLLM.
    system_message : str
        Instructional message to set the LLM’s role/context.
    user_message_template : str
        Jinja-style template for the user input prompt.
    """

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        response_model: Type[BaseModel] = DefinitionValidationResult,
        client: Any = instructor.from_litellm(acompletion),
        system_message: str = VALIDATION_SYSTEM_MESSAGE,
        user_message_template: str = VALIDATION_USER_MESSAGE_TEMPLATE,
    ):
        super().__init__(
            model=model,
            response_model=response_model,
            client=client,
            system_message=system_message,
        )
        self.user_message_template = user_message_template

    async def validate_definition(
        self, term: str, summary: str, temperature: float = 0.0
    ) -> Optional[DefinitionValidationResult]:
        """
        Validate a user-defined definition using an LLM.

        Parameters
        ----------
        term : str
            The user-defined term being defined.
        summary : str
            The candidate definition to validate.
        temperature : float, optional
            Sampling temperature for the LLM. Lower is more deterministic.

        Returns
        -------
        Optional[DefinitionValidationResult]
            A structured validation response, or None if validation failed.
        """
        if not term or not summary:
            logger.warning("[Validation] Term or summary missing.")
            return None

        user_message = self.user_message_template.format(term=term, summary=summary)
        messages = self.build_messages(user_message)

        try:
            result = await self.generate_response(
                messages=messages, temperature=temperature
            )

            if isinstance(result, self.response_model):
                return result
            # Should ideally not happen if generate_response works correctly
            logger.error(
                f"[Validation] Unexpected LLM response type: {type(result)} for term '{term}'"
            )
            return None

        except APIConnectionError as e:
            # Already logged in base class, but maybe add context
            logger.error(
                f"[Validation] API connection error during validation for '{term}': {e}"
            )
            return None

        except Exception as e:
            logger.exception(
                f"[Validation] Unexpected error during validation for term '{term}': {e}"
            )
            return None


class ExtractionService(BaseLLMService):
    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        response_model: Type[BaseModel] = ExtractedTerms,
        system_message: str = f"You are a professional entity extractor. Extract relevant {settings.topic_domain} terms.",
        user_message_template: str = f"Extract {settings.topic_domain}  terms"
        + "from:\n{text}",
        client: Any = instructor.from_litellm(acompletion),
    ):
        super().__init__(model, response_model, client, system_message)
        self.user_message_template = user_message_template

    async def extract_user_defined_terms(
        self, text: str, temperature: float = 0.0
    ) -> terminusAnswer | None:
        """
        Extracts user-defined terms from the provided text.

        Parameters
        ----------
        text : str
            The text from which user-defined terms are extracted.
        temperature : float, optional
            The temperature parameter for the LLM, by default 0.0.

        Returns
        -------
        terminusAnswer | None
            The structured response containing extracted user-defined terms, or None if an error occurs.
        """
        user_message = self.user_message_template.format(text=text)
        messages = self.build_messages(user_message)
        return await self.generate_response(messages, temperature=temperature)


class TermExtractionService(BaseLLMService):
    """
    Advanced service for extracting and validating user-defined terms from text.

    Attributes
    ----------
    critique_response_model : Type[BaseModel]
        The Pydantic model to structure the critique response.
    critique_system_message : str
        The system message for the critique step.
    critique_user_message_template : str
        The template for the user message in the critique step.

    Methods
    -------
    validate_terms(text: str, temperature: float = 0.0) -> List[str]
        Validates extracted user-defined terms by critiquing them.
    _critique_term(term: str, temperature: float = 0.0) -> bool
        Critiques a single term to determine if it is a user-defined term.
    """

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        extraction_response_model: Type[BaseModel] = ExtractedTerms,
        critique_response_model: Type[BaseModel] = TermCritique,
        client: Any = instructor.from_litellm(acompletion),
    ):
        extraction_system_message = (
            f"Extract {settings.topic_domain} terms from the text."
        )
        super().__init__(
            model, extraction_response_model, client, extraction_system_message
        )
        self.critique_response_model = critique_response_model
        self.critique_system_message = f"You are a {settings.topic_domain} analyst. Determine whether this is a {settings.topic_domain} term."
        self.critique_user_message_template = "Term: {term}"

    async def validate_terms(self, text: str, temperature: float = 0.0) -> List[str]:
        """
        Validates extracted user-defined terms by critiquing them.

        Parameters
        ----------
        text : str
            The text from which user-defined terms are extracted and validated.
        temperature : float, optional
            The temperature parameter for the LLM, by default 0.0.

        Returns
        -------
        List[str]
            The list of validated user-defined terms.
        """
        # Step 1: Extract raw candidate terms
        messages = self.build_messages(user_message=text)
        extraction_response = await self.generate_response(
            messages, temperature=temperature
        )
        if extraction_response is None:
            return []
        candidate_terms = [ft.term for ft in extraction_response.terms]

        # Step 2: Critique each term
        validated = []
        for term in candidate_terms:
            if await self._critique_term(term, temperature=temperature):
                validated.append(term)
        return validated

    async def _critique_term(self, term: str, temperature: float = 0.0) -> bool:
        """
        Critiques a single term to determine if it is a user-defined term.

        Parameters
        ----------
        term : str
            The term to be critiqued.
        temperature : float, optional
            The temperature parameter for the LLM, by default 0.0.

        Returns
        -------
        bool
            True if the term is a user-defined term, False otherwise.
        """
        messages = [
            {"role": "system", "content": self.critique_system_message},
            {
                "role": "user",
                "content": self.critique_user_message_template.format(term=term),
            },
        ]
        try:
            critique_response = await self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                response_model=self.critique_response_model,
                messages=messages,
            )
            return critique_response.is_relevant
        except Exception as e:
            logger.error(f"Critique error for term '{term}': {e}")
            return False


# Example usage:
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def main():
        sample_text = (
            "The stock market rallied after the Fed announced rate hikes and inflation control measures. "
            "Investors are watching changes in quantitative easing and interest rates, while global economic trends continue."
        )

        service = TermExtractionService()
        validated_terms = await service.validate_terms(sample_text, temperature=0.0)

        print("Validated user-defined terms:")
        for term in validated_terms:
            print("-", term)

    asyncio.run(main())
