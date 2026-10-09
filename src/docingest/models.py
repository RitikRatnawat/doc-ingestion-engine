from pydantic import BaseModel, Field


class Page(BaseModel):
    """
    Represents a Webpage in a Document.
    """

    url: str = Field(description="The URL of the webpage.")
    title: str = Field(description="The title of the webpage.")
    markdown: str = Field(description="The content of the webpage.")
