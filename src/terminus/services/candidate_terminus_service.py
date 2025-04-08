import json
from sqlalchemy.orm import Session
from terminus.models import CandidateterminusEntry
from terminus.schemas import FollowUp, CandidateterminusAnswer


class CandidateterminusService:
    """
    Service class for managing candidate terminus entries in the database.

    This class provides methods to interact with the `CandidateterminusEntry` model,
    including retrieving, saving, deleting, and checking the existence of entries.
    It also handles serialization and deserialization of follow-up data associated
    with terminus entries.

    Attributes
    ----------
    session : sqlalchemy.orm.Session
        The database session used for querying and modifying `CandidateterminusEntry` records.
    """

    def __init__(self, session: Session):
        """
        Initialize the CandidateterminusService with a database session.

        Parameters
        ----------
        session : sqlalchemy.orm.Session
            The database session to be used for operations.
        """
        self.session = session

    def get(self, term: str) -> CandidateterminusEntry | None:
        """
        Retrieve a candidate terminus entry by term.

        Parameters
        ----------
        term : str
            The term to search for in the terminus.

        Returns
        -------
        CandidateterminusEntry or None
            The matching `CandidateterminusEntry` object if found, otherwise None.
        """
        return (
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .first()
        )

    def get_as_pydantic(self, term: str) -> CandidateterminusAnswer | None:
        """
        Retrieve a candidate terminus entry as a Pydantic model.

        Parameters
        ----------
        term : str
            The term to search for in the terminus.

        Returns
        -------
        CandidateterminusAnswer or None
            A Pydantic model representation of the entry if found, otherwise None.
        """
        db_obj = (
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .first()
        )
        if not db_obj:
            return None
        # We do NOT overwrite db_obj.follow_ups
        follow_ups_list = self._deserialize_follow_ups(db_obj.follow_ups)
        return CandidateterminusAnswer(
            term=db_obj.term,
            definition=db_obj.definition,
            follow_ups=follow_ups_list,
            status=db_obj.status,
        )

    def get_dict(self, term: str) -> dict | None:
        """
        Retrieve a candidate terminus entry as a dictionary.

        Parameters
        ----------
        term : str
            The term to search for in the terminus.

        Returns
        -------
        dict or None
            A dictionary representation of the entry if found, otherwise None.
        """
        db_obj = (
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .first()
        )
        if not db_obj:
            return None
        follow_ups_list = self._deserialize_follow_ups(db_obj.follow_ups)
        self.session.expunge(db_obj)
        return {
            "term": db_obj.term,
            "definition": db_obj.definition,
            "follow_ups": follow_ups_list,
            "status": db_obj.status,
        }

    def save(
        self,
        term: str,
        definition: str,
        follow_ups: list[dict | FollowUp],
        status: str = "under_review",
    ):
        """
        Save or update a candidate terminus entry in the database.

        Parameters
        ----------
        term : str
            The term to save or update.
        definition : str
            The definition of the term.
        follow_ups : list[dict or FollowUp]
            A list of follow-up questions or actions related to the term.
        status : str, optional
            The status of the entry, by default "under_review".
        """
        entry = CandidateterminusEntry(
            term=term.lower(),
            definition=definition,
            follow_ups=self._serialize_follow_ups(follow_ups),
            status=status,
        )
        self.session.merge(entry)
        self.session.commit()

    def delete(self, term: str) -> bool:
        """
        Delete a candidate terminus entry by term.

        Parameters
        ----------
        term : str
            The term to delete from the terminus.

        Returns
        -------
        bool
            True if the entry was deleted, False if it was not found.
        """
        entry = (
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .first()
        )
        if not entry:
            return False
        self.session.delete(entry)
        self.session.commit()
        return True

    def exists(self, term: str) -> bool:
        """
        Check if a candidate terminus entry exists for a given term.

        Parameters
        ----------
        term : str
            The term to check for existence.

        Returns
        -------
        bool
            True if the entry exists, False otherwise.
        """
        return self.session.query(
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .exists()
        ).scalar()

    def reject(self, term: str, reason: str = "No reason provided"):
        """
        Mark a candidate terminus entry as rejected with an optional reason.

        Parameters
        ----------
        term : str
            The term to reject.
        reason : str, optional
            The reason for rejection, by default "No reason provided".
        """
        entry = (
            self.session.query(CandidateterminusEntry)
            .filter_by(term=term.lower())
            .first()
        )
        if entry:
            entry.status = f"rejected: {reason}"
            self.session.commit()

    def _serialize_follow_ups(self, follow_ups: list[dict | FollowUp]) -> str:
        """
        Serialize a list of follow-ups into a JSON string.

        Parameters
        ----------
        follow_ups : list[dict or FollowUp]
            A list of follow-up questions or actions.

        Returns
        -------
        str
            A JSON string representation of the follow-ups.
        """
        serialized = []
        for fu in follow_ups:
            if isinstance(fu, FollowUp):
                serialized.append(fu.dict())
            else:
                serialized.append(fu)
        return json.dumps(serialized)

    def _deserialize_follow_ups(self, follow_ups_str: str) -> list[FollowUp]:
        """
        Deserialize a JSON string of follow-ups into a list of FollowUp objects.

        Parameters
        ----------
        follow_ups_str : str
            A JSON string representation of follow-ups.

        Returns
        -------
        list[FollowUp]
            A list of `FollowUp` objects.
        """
        if not follow_ups_str:
            return []
        import json

        data = json.loads(follow_ups_str)
        return [FollowUp(**fu) for fu in data]
