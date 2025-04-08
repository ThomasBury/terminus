import asyncio  # Import asyncio
import wikipedia
import wikipedia.exceptions
import re
import logging

from terminus.config import settings

# Assume logger is configured elsewhere
logger = logging.getLogger(__name__)


class WikipediaService:
    """
    An asynchronous service for querying Wikipedia and retrieving summaries of user-defined terms.

    This class provides methods to search Wikipedia, handle disambiguation, and
    prioritize topic-relevant Wikipedia content. It uses asyncio.to_thread to run blocking
    Wikipedia library calls in a separate thread, making it suitable for async applications.

    Attributes
    ----------
    context_hint : str, optional
        A string providing context for searches (default: "topic economics banking investment market").
        This hint is appended to the search term in fallback searches.
    topic_keywords : list of str
        A list of keywords used to identify and prioritize topic-related Wikipedia pages.
    topic_pattern : re.Pattern
        A compiled regular expression pattern for efficiently matching topic keywords.
    """

    def __init__(self, context_hint: str = f"{settings.topic_domain}"):
        """
        Initializes the WikipediaService with a context hint and topic keywords.

        Parameters
        ----------
        context_hint : str, optional
            A string providing context for searches (default: "topic economics banking investment market").
            This hint is appended to the search term in fallback searches.
        """
        self.context_hint = context_hint
        self.topic_keywords = settings.topic_keywords
        self.topic_pattern = re.compile(
            r"\b("
            + "|".join(re.escape(k) for k in self.topic_keywords)
            + r")\b"
            + r"|\(("
            + "|".join(re.escape(k) for k in self.topic_keywords)
            + r")\)",
            re.IGNORECASE,
        )

    async def _get_summary(self, title: str) -> str | None:  # Changed to async def
        """
        Safely fetches a summary from Wikipedia for a given title asynchronously.

        Runs the blocking wikipedia.summary call in a separate thread. Handles
        potential errors such as DisambiguationError and PageError.

        Parameters
        ----------
        title : str
            The title of the Wikipedia page to summarize.

        Returns
        -------
        str or None
            A short summary of the Wikipedia page, or None if an error occurred.
        """
        try:
            # Run the blocking summary call in a thread
            summary = await asyncio.to_thread(
                wikipedia.summary, title, sentences=2, auto_suggest=False
            )
            return summary
        except wikipedia.exceptions.DisambiguationError as e:
            logger.warning(
                f"Disambiguation error encountered for '{title}': {e.options}"
            )
            # Disambiguation handling now needs to be awaited
            return await self._handle_disambiguation(title, e.options)
        except wikipedia.exceptions.PageError:
            logger.warning(f"PageError fetching summary for '{title}'.")
            return None
        except Exception as e:
            # Catch unexpected errors from the library or threading
            logger.error(f"Unexpected error fetching summary for '{title}': {e}")
            return None

    async def _handle_disambiguation(
        self, term: str, options: list[str]
    ) -> str | None:  # Changed to async def
        """
        Asynchronously selects the best option from a disambiguation list, prioritizing topic.

        Parameters
        ----------
        term : str
            The original search term that led to disambiguation.
        options : list of str
            A list of disambiguation options provided by Wikipedia.

        Returns
        -------
        str or None
            A summary of the best disambiguation option, or None if no suitable option is found.
        """
        logger.info(f"Handling disambiguation for '{term}'. Options: {options}")

        topic_opts = [opt for opt in options if self.topic_pattern.search(opt)]
        if topic_opts:
            logger.info(
                f"Found {settings.topic_domain} related options: {topic_opts}. Selecting '{topic_opts[0]}'."
            )
            # Call _get_summary asynchronously
            return await self._get_summary(topic_opts[0])

        # Optional: Add handling for exact match if needed, calling await self._get_summary(...)

        if options:
            logger.info(
                f"No specific {settings.topic_domain} option found. Falling back to first option: '{options[0]}'."
            )
            # Call _get_summary asynchronously
            return await self._get_summary(options[0])

        logger.warning(
            f"Could not resolve disambiguation for '{term}'. No suitable options."
        )
        return None

    async def query(self, term: str) -> str:  # Changed to async def
        """
        Asynchronously fetch a ~2-sentence summary from Wikipedia, prioritizing topic topics.

        Uses asyncio.to_thread for blocking calls.

        Parameters
        ----------
        term : str
            The search term for which to retrieve a Wikipedia summary.

        Returns
        -------
        str
            A summary of the Wikipedia page, or an error message if no suitable page is found.
        """
        term = term.strip()
        if not term:
            return "Please provide a term to search."  # No async needed for this simple return

        preferred_candidate = None  # Keep track of candidate tested

        try:
            # === Strategy 1: Try explicit "term (topic)" ===
            explicit_topic_term = f"{term} ({settings.topic_domain})"
            logger.info(
                f"Trying explicit {settings.topic_domain} term: '{explicit_topic_term}'"
            )
            try:
                # Use page() first - run blocking call in thread
                page_obj = await asyncio.to_thread(
                    wikipedia.page, explicit_topic_term, auto_suggest=False
                )
                page_title = page_obj.title

                logger.info(
                    f"Found direct page for '{explicit_topic_term}' with title '{page_title}'."
                )
                # Use page.title for summary - await the async _get_summary
                summary = await self._get_summary(page_title)
                if summary:
                    return summary
            except wikipedia.exceptions.PageError:
                logger.info(
                    f"'{explicit_topic_term}' not found directly. Proceeding to search."
                )
            except wikipedia.exceptions.DisambiguationError as e:
                logger.info(f"'{explicit_topic_term}' led to disambiguation.")
                # Await the async handler
                summary = await self._handle_disambiguation(
                    explicit_topic_term, e.options
                )
                if summary:
                    return summary
            except Exception as e:
                logger.error(
                    f"Unexpected error checking explicit term '{explicit_topic_term}': {e}"
                )
                # Continue to general search

            # === Strategy 2: Use wikipedia.search() ===
            logger.info(f"Performing search for term: '{term}'")
            # Run blocking search call in thread
            search_results = await asyncio.to_thread(wikipedia.search, term, results=5)
            logger.info(f"Search results for '{term}': {search_results}")

            if search_results:
                # Prioritize results (same logic as before)
                for result in search_results:
                    if self.topic_pattern.search(result):
                        preferred_candidate = result
                        logger.info(
                            f"Selected {settings.topic_domain}-related candidate from search: '{preferred_candidate}'"
                        )
                        break
                if not preferred_candidate:
                    top_result_lower = search_results[0].lower()
                    term_lower = term.lower()
                    if top_result_lower == term_lower or top_result_lower.startswith(
                        term_lower + " ("
                    ):
                        preferred_candidate = search_results[0]
                        logger.info(
                            f"No {settings.topic_domain} keyword match, selecting top search result: '{preferred_candidate}'"
                        )
                    else:
                        preferred_candidate = search_results[0]
                        logger.info(
                            f"No {settings.topic_domain} keyword match or direct term match, defaulting to top search result: '{preferred_candidate}'"
                        )

            # === Strategy 3: Attempt summary for the best candidate ===
            if preferred_candidate:
                logger.info(
                    f"Attempting to get summary for candidate: '{preferred_candidate}'"
                )
                # Await the async summary fetch
                summary = await self._get_summary(preferred_candidate)
                if summary:
                    return summary

            logger.info(
                f"Initial search and candidate summary failed or yielded no result for '{term}'."
            )

            # === Strategy 4: Fallback - Search with context hint ===
            context_term = f"{term} {self.context_hint}"
            logger.info(f"Falling back to search with context hint: '{context_term}'")
            # Run blocking context search call in thread
            context_search_results = await asyncio.to_thread(
                wikipedia.search, context_term, results=3
            )
            logger.info(f"Context search results: {context_search_results}")

            if context_search_results:
                context_candidate = context_search_results[0]
                if context_candidate == preferred_candidate:
                    logger.warning(
                        f"Context search yielded same candidate '{context_candidate}' which already failed."
                    )
                else:
                    logger.info(
                        f"Attempting summary for context search candidate: '{context_candidate}'"
                    )
                    # Await the async summary fetch
                    summary = await self._get_summary(context_candidate)
                    if summary:
                        return summary

            # === Final Fallback ===
            logger.warning(
                f"Could not find relevant Wikipedia page for '{term}' after all strategies."
            )
            return f"Could not find a relevant Wikipedia page for '{term}'."

        except Exception as e:
            # Catch-all for unexpected errors during the query process
            logger.exception(
                f"An unexpected error occurred during Wikipedia query for '{term}': {e}"
            )
            return f"An error occurred while searching Wikipedia for '{term}'."
