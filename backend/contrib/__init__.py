"""Teammate-owned feature packages (docs/contributing/in-repo/README.md).

Packages here load fail-soft in the app factory's discovery loop. This
``__init__.py`` exists so pytest's ``prepend`` import mode walks up to the
repo root and imports contrib tests as ``backend.contrib.<slug>.tests.*``,
the same module names every other feature gets.
"""
