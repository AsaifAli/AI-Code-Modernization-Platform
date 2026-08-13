from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field


class DetectedTech(BaseModel):
    language: str = Field(..., description="The primary programming language used in the project.")
    framework: Optional[str] = Field(None, description="The main framework used, if any.")
    libraries: List[str] = Field(default_factory=list, description="A list of libraries used in the project.")


class FolderNode(BaseModel):
    name: str
    kind: Literal["file", "folder"]
    content: Optional[str] = None
    children: Optional[List["FolderNode"]] = None