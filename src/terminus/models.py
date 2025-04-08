from sqlalchemy import Column, String, JSON, Text
from terminus.database import Base


class terminusEntry(Base):
    """
    Represents an official, human-validated terminus entry.

    This class defines the structure of the `terminus` table in the database,
    which stores terms along with their definitions and follow-up information.

    Attributes
    ----------
    term : str
        The primary key and unique identifier for each terminus entry.
    definition : str
        The detailed explanation or meaning of the term.
    follow_ups : str
        Additional information or related terms associated with the main term.

    Methods
    -------
    None
    """

    __tablename__ = "terminus"
    term: str = Column(String, primary_key=True, index=True)
    definition: str = Column(Text)
    follow_ups: str = Column(Text)


class CandidateterminusEntry(Base):
    """
    Represents a candidate terminus entry that is under review.

    This class defines the structure of the `candidate_terminus` table in the database,
    which stores terms that are proposed for inclusion in the official terminus but
    have not yet been validated.

    Attributes
    ----------
    term : str
        The primary key and unique identifier for each candidate terminus entry.
    definition : str
        The proposed explanation or meaning of the term.
    follow_ups : dict
        Additional information or related terms associated with the proposed term.
    status : str
        The current review status of the candidate entry, defaulting to "under_review".

    Methods
    -------
    None
    """

    __tablename__ = "candidate_terminus"
    term: str = Column(String, primary_key=True, index=True)
    definition: str = Column(String)
    follow_ups: dict = Column(JSON)
    status: str = Column(String, default="under_review")
