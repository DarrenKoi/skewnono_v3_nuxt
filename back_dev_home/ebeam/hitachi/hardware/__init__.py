"""Hardware feature package.

`bp` is exported lazily (PEP 562): the app factory reads it via
`getattr(module, "bp")` during blueprint discovery, but importing a leaf
submodule (e.g. `providers.beam_shape_mock`) no longer drags in the whole
`routes -> data -> providers` chain. This keeps provider/metrics modules
independently importable.
"""

__all__ = ["bp"]


def __getattr__(name):
    if name == "bp":
        from back_dev_home.ebeam.hitachi.hardware.routes import bp

        return bp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
