from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, TYPE_CHECKING


if TYPE_CHECKING:
  from .context import SkillContext


class SkillError(RuntimeError):
  """Raised when a skill encounters a recoverable error."""


@dataclass(frozen=True)
class SkillParameter:
  """
  Declarative description of a skill argument.

  Attributes:
    name: Canonical keyword used when invoking the skill.
    type: Human readable type hint (string, int, float, bool, path).
    required: Whether the argument must be provided.
    description: Short usage hint presented in CLI listings.
    default: Optional default used when the argument is omitted.
  """

  name: str
  type: str = "string"
  required: bool = False
  description: str = ""
  default: Optional[Any] = None


@dataclass
class SkillResult:
  """Canonical response payload returned by skills."""

  success: bool
  message: str
  details: Optional[Mapping[str, Any]] = None


class Skill(ABC):
  """
  Base class for Claude-style skills.

  Subclasses only need to define metadata and implement ``run``.
  """

  #: Unique identifier used for registry lookups.
  name: str = ""

  #: Short summary shown when listing skills.
  description: str = ""

  #: Declarative parameter specification.
  parameters: Sequence[SkillParameter] = ()

  def __init__(self, context: "SkillContext"):
    self._context = context

  @property
  def context(self) -> "SkillContext":
    return self._context

  def execute(self, raw_arguments: Optional[Mapping[str, Any]] = None) -> SkillResult:
    """
    Validate and coerce arguments before delegating to ``run``.
    """
    parsed = self._coerce_arguments(raw_arguments or {})
    return self.run(**parsed)

  def _coerce_arguments(self, arguments: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Validate required parameters and coerce supported types.
    """
    parsed: Dict[str, Any] = {}
    provided_keys = set(arguments.keys())

    for spec in self.parameters:
      if spec.name in arguments:
        parsed[spec.name] = self._coerce_value(arguments[spec.name], spec.type)
      elif spec.required and spec.default is None:
        raise SkillError(f"Missing required argument: {spec.name}")
      else:
        parsed[spec.name] = spec.default

    # Pass through unknown arguments so power users can access advanced hooks.
    for key in provided_keys - {spec.name for spec in self.parameters}:
      parsed[key] = arguments[key]

    return parsed

  def _coerce_value(self, value: Any, decl_type: str) -> Any:
    """
    Lightweight coercion to keep CLI ergonomics pleasant.
    """
    if decl_type == "bool":
      if isinstance(value, bool):
        return value
      if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "y"}:
          return True
        if lowered in {"0", "false", "no", "n"}:
          return False
      raise SkillError(f"Cannot coerce value '{value}' to bool")

    if decl_type == "int":
      try:
        return int(value)
      except (TypeError, ValueError) as exc:
        raise SkillError(f"Cannot coerce value '{value}' to int") from exc

    if decl_type == "float":
      try:
        return float(value)
      except (TypeError, ValueError) as exc:
        raise SkillError(f"Cannot coerce value '{value}' to float") from exc

    if decl_type == "path":
      return Path(str(value))

    # Default passthrough for string/any.
    return value

  @abstractmethod
  def run(self, **kwargs: Any) -> SkillResult:
    """
    Implement the skill's core behavior. Subclasses should return ``SkillResult``.
    """
