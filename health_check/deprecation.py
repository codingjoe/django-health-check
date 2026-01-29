from __future__ import annotations

try:
    from warnings import deprecated
except ImportError:
    import functools
    import warnings

    def deprecated(message: str, *, category: type[Warning] | None = DeprecationWarning, stacklevel: int = 1):
        def _decorator(obj):
            obj.__deprecated__ = message

            # For classes, wrap __init__ to warn on instantiation
            if isinstance(obj, type):
                original_init = obj.__init__

                @functools.wraps(original_init)
                def new_init(self, *args, **kwargs):
                    warnings.warn(message, category, stacklevel=stacklevel + 1)
                    original_init(self, *args, **kwargs)

                obj.__init__ = new_init
            # For functions, wrap the function to warn on call
            else:

                @functools.wraps(obj)
                def wrapper(*args, **kwargs):
                    warnings.warn(message, category, stacklevel=stacklevel + 1)
                    return obj(*args, **kwargs)

                return wrapper

            return obj

        return _decorator
