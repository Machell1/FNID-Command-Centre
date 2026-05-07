"""Route blueprints for the FNID portal."""

from .. import constants as _constants


def _cfg_module():
    """Return the constants module for use as 'cfg' in templates.

    Templates reference cfg.FIREARM_TYPES, cfg.ALL_PARISHES, etc.
    This preserves backward compatibility with existing templates.
    """
    return _constants
