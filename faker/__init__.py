"""
Lightweight fallback for the external ``faker`` dependency.

Only the ``name`` method is required by ``demo/demo/test/util.py`` when
generating sample data. The implementation here keeps the same public
surface so the automation scripts continue to run inside the constrained
LM Studio environment without installing additional packages.
"""

class Faker:
  def __init__(self, locale: str = "en_US"):
    self.locale = locale

  def name(self) -> str:
    # Minimal placeholder; randomness is not required for the sample skills.
    return "LM Studio User"
