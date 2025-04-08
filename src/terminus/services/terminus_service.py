import json
from sqlalchemy.orm import Session
from terminus.models import terminusEntry
from terminus.schemas import FollowUp, terminusAnswer


class terminusService:
    """
    Service class for managing terminus entries.

    This class provides methods to interact with the terminus database, including
    retrieving, saving, deleting, and checking the existence of entries. It also
    handles serialization and deserialization of follow-up data.

    Attributes
    ----------
    session : Session
        SQLAlchemy session used to interact with the database.
    """

    def __init__(self, session: Session):
        """
        Initialize the terminusService with a database session.

        Parameters
        ----------
        session : Session
            SQLAlchemy session used to interact with the database.
        """
        self.session = session

    def get_as_pydantic(self, term: str) -> terminusAnswer | None:
        """
        Retrieve a terminus entry as a Pydantic model.

        This method fetches a terminus entry from the database and deserializes
        its follow-ups into a list of `FollowUp` objects.

        Parameters
        ----------
        term : str
            The term to search for in the terminus.

        Returns
        -------
        terminusAnswer or None
            A Pydantic model representing the terminus entry, or None if the
            entry does not exist.
        """
        db_obj = self.session.query(terminusEntry).filter_by(term=term.lower()).first()
        if not db_obj:
            return None
        # Deserialize follow-ups from JSON string to a list of FollowUp objects
        follow_ups = self._deserialize_follow_ups(db_obj.follow_ups)
        return terminusAnswer(
            term=db_obj.term, definition=db_obj.definition, follow_ups=follow_ups
        )

    def get(self, term: str) -> terminusEntry | None:
        """
        Retrieve a raw terminusEntry SQLAlchemy object.

        Parameters
        ----------
        term : str
            The term to search for in the terminus.

        Returns
        -------
        terminusEntry or None
            The SQLAlchemy object representing the terminus entry, or None if
            the entry does not exist.
        """
        return self.session.query(terminusEntry).filter_by(term=term.lower()).first()

    def save(self, term: str, definition: str, follow_ups: list[dict | FollowUp]):
        """
        Save or update a terminus entry in the database.

        Parameters
        ----------
        term : str
            The term to save in the terminus.
        definition : str
            The definition of the term.
        follow_ups : list[dict or FollowUp]
            A list of follow-up questions or related terms, either as `FollowUp`
            objects or dictionaries.
        """
        # Serialize follow-ups into a JSON string for storage
        entry = terminusEntry(
            term=term.lower(),
            definition=definition,
            follow_ups=self._serialize_follow_ups(follow_ups),
        )
        # Use `merge` to insert or update the entry
        self.session.merge(entry)
        self.session.commit()

    def delete(self, term: str) -> bool:
        """
        Delete a terminus entry from the database.

        Parameters
        ----------
        term : str
            The term to delete from the terminus.

        Returns
        -------
        bool
            True if the entry was deleted, False if it did not exist.
        """
        entry = self.session.query(terminusEntry).filter_by(term=term.lower()).first()
        if not entry:
            return False
        self.session.delete(entry)
        self.session.commit()
        return True

    def exists(self, term: str) -> bool:
        """
        Check if a terminus entry exists in the database.

        Parameters
        ----------
        term : str
            The term to check for in the terminus.

        Returns
        -------
        bool
            True if the entry exists, False otherwise.
        """
        # Use a subquery to check for existence
        return self.session.query(
            self.session.query(terminusEntry).filter_by(term=term.lower()).exists()
        ).scalar()

    def _serialize_follow_ups(self, follow_ups: list[dict | FollowUp]) -> str:
        """
        Serialize follow-ups into a JSON string.

        Parameters
        ----------
        follow_ups : list[dict or FollowUp]
            A list of follow-up questions or related terms, either as `FollowUp`
            objects or dictionaries.

        Returns
        -------
        str
            A JSON string representing the serialized follow-ups.
        """
        serialized = []
        for fu in follow_ups:
            # Convert FollowUp objects to dictionaries if necessary
            if isinstance(fu, FollowUp):
                serialized.append(fu.model_dump())
            else:
                serialized.append(fu)
        return json.dumps(serialized)

    def _deserialize_follow_ups(self, follow_ups_str: str) -> list[FollowUp]:
        """
        Deserialize a JSON string into a list of FollowUp objects.

        Parameters
        ----------
        follow_ups_str : str
            A JSON string representing the serialized follow-ups.

        Returns
        -------
        list[FollowUp]
            A list of `FollowUp` objects.
        """
        if not follow_ups_str:
            return []
        # Parse the JSON string and convert each item to a FollowUp object
        data = json.loads(follow_ups_str)
        return [FollowUp(**fu) for fu in data]
