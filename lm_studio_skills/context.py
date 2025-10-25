from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG = Path("demo/demo/config.json")
DEFAULT_ENVIRON = Path("demo/demo/test/environ.json")


class SkillContext:
  """
  Convenience wrapper for locating shared resources and creating ``ServiceManager`` instances.
  """

  def __init__(
    self,
    base_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    environ_path: Optional[Path] = None,
  ):
    self._base_path = Path(base_path) if base_path else Path(__file__).resolve().parent.parent
    self._config_path = self._resolve_relative(config_path or DEFAULT_CONFIG)
    self._environ_path = self._resolve_relative(environ_path or DEFAULT_ENVIRON)

    self._config_cache: Optional[Dict[str, Any]] = None
    self._environ_cache: Optional[Dict[str, Any]] = None
    self._svc_manager = None

  @property
  def base_path(self) -> Path:
    return self._base_path

  @property
  def config_path(self) -> Path:
    return self._config_path

  @property
  def environ_path(self) -> Path:
    return self._environ_path

  @property
  def config(self) -> Dict[str, Any]:
    if self._config_cache is None:
      self._config_cache = self._load_json(self._config_path)
    return self._config_cache

  @property
  def environ(self) -> Dict[str, Any]:
    if self._environ_cache is None:
      self._environ_cache = self._load_json(self._environ_path)
    return self._environ_cache

  @property
  def service_manager(self):
    if self._svc_manager is None:
      from manager import ServiceManager
      self._svc_manager = ServiceManager(self.config)
    return self._svc_manager

  def reset_service_manager(self):
    """
    Force the creation of a new ``ServiceManager`` the next time ``service_manager`` is accessed.
    """
    self._svc_manager = None

  def _resolve_relative(self, candidate: Path) -> Path:
    candidate = Path(candidate)
    if candidate.is_absolute():
      return candidate
    return self._base_path / candidate

  def _load_json(self, path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
      return json.load(handle)
