from __future__ import annotations

from importlib import import_module
from typing import Dict, Iterable, Optional, Type

from .base import Skill, SkillError


class SkillRegistry:
  """Central registry for all Claude-style skills."""

  def __init__(self):
    self._skills: Dict[str, Type[Skill]] = {}
    self._loaded_builtin = False

  def register(self, skill_cls: Type[Skill]) -> Type[Skill]:
    if not issubclass(skill_cls, Skill):
      raise TypeError("Only Skill subclasses can be registered")

    name = skill_cls.name or skill_cls.__name__.lower()
    if name in self._skills:
      raise ValueError(f"Skill '{name}' already registered")

    self._skills[name] = skill_cls
    return skill_cls

  def get(self, name: str) -> Optional[Type[Skill]]:
    return self._skills.get(name)

  def create(self, name: str, context, **kwargs):
    skill_cls = self.get(name)
    if skill_cls is None:
      raise SkillError(f"Skill '{name}' is not registered")
    skill = skill_cls(context)
    return skill.execute(kwargs)

  def list_skill_types(self) -> Iterable[Type[Skill]]:
    return self._skills.values()

  def ensure_builtin_loaded(self):
    if self._loaded_builtin:
      return
    import_module("lm_studio_skills.skills")
    self._loaded_builtin = True


global_registry = SkillRegistry()


def register_skill(cls: Type[Skill]) -> Type[Skill]:
  """Decorator used by skill modules."""
  return global_registry.register(cls)


def load_builtin_skills():
  """Ensure bundled example skills are available."""
  global_registry.ensure_builtin_loaded()
