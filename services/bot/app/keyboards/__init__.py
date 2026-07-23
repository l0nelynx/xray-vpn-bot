from .keyboards import get_connect

# Export the connect function directly
connect = get_connect


# Module-level lazy loading for backward compatibility (e.g. kb.subcheck)
def __getattr__(name: str):
    from . import keyboards as _kb

    builder = _kb._LAZY_BUILDERS.get(name)
    if builder:
        return builder()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
