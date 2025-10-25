"""
Bundled example skills for LM Studio.

Modules within this package register themselves with the global registry
via the ``@register_skill`` decorator.
"""

# Import side-effect modules to ensure registration occurs.
from . import list_devices  # noqa: F401
from . import fingerprint_auth  # noqa: F401
