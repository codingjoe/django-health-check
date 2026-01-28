from __future__ import annotations

try:
    from warnings import deprecated
except ImportError:

    def deprecated(message: str, *, category: type[Warning] | None = DeprecationWarning, stacklevel: int = 1):
        import warnings

        def _decorator(obj):
            warnings.warn(message, category, stacklevel=stacklevel)
            obj.__deprecated__ = message
            return obj

        return _decorator
