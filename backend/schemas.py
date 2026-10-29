"""Pydantic request models."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import get_settings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(default="User", min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=254)
    current_password: Optional[str] = Field(default=None, max_length=256)

    @field_validator("name")
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class Position(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: float = 0.0
    y: float = 0.0


class NodeModel(BaseModel):
    """UI-only fields (selected, width, dragging...) are dropped via extra='ignore'."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    position: Position = Field(default_factory=Position)
    data: dict[str, Any] = Field(default_factory=dict)


class EdgeModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = Field(default=None, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    sourceHandle: Optional[str] = Field(default=None, max_length=100)
    targetHandle: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _ensure_id(self) -> "EdgeModel":
        if not self.id:
            self.id = f"e-{self.source}-{self.sourceHandle or ''}-{self.target}-{self.targetHandle or ''}"
        return self


class GraphModel(BaseModel):
    nodes: list[NodeModel] = Field(default_factory=list)
    edges: list[EdgeModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _limits(self) -> "GraphModel":
        settings = get_settings()
        if len(self.nodes) > settings.max_nodes:
            raise ValueError(f"A workflow can have at most {settings.max_nodes} nodes")
        if len(self.edges) > settings.max_edges:
            raise ValueError(f"A workflow can have at most {settings.max_edges} connections")
        size = len(json.dumps([n.model_dump() for n in self.nodes], default=str))
        if size > settings.max_graph_bytes:
            raise ValueError("Workflow is too large")
        return self

    def dump(self) -> tuple[list[dict], list[dict]]:
        return [n.model_dump() for n in self.nodes], [e.model_dump() for e in self.edges]


class WorkflowCreate(GraphModel):
    name: str = Field(default="Untitled Workflow", max_length=120)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return value.strip() or "Untitled Workflow"


class WorkflowUpdate(WorkflowCreate):
    """Full replacement update (the editor always sends the whole workflow)."""


class ExecuteRequest(GraphModel):
    stream: bool = False
