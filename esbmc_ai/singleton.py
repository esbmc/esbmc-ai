# Author: Yiannis Charalambous

from typing import Any, Callable, Dict, Tuple, Type

class SingletonMeta(type):
    """Implements classes as singletons. This is a metaclass, so it should not
    be directly inherited.
    
    If the class you are assigning this as a metaclass of, has a parent that is
    not using this metaclass, you need to use a metaclass factory like makecls
    to automatically resolve conflicts:
    
    ```py
    from noconflict import makecls
    class TestClass(ExistingBase, metaclass=makecls(SingletonMeta)):
        pass
    ```"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


# Cache of previously generated metaclasses
metadic: Dict[Tuple[Type[Any], ...], Type[Any]] = {}

def _generatemetaclass(
    bases: Tuple[type, ...],
    metas: Tuple[Type[Any], ...],
    priority: bool
) -> Type[Any]:
    # A metaclass is considered "trivial" if it's the default 'type',
    # or if it's a superclass of any explicitly provided metaclass.
    def trivial(m: Type[Any]) -> bool:
        return sum([issubclass(M, m) for M in metas], int(m is type)) > 0

    # Determine non-trivial metaclasses of the base classes
    metabs: Tuple[Type[Any], ...] = tuple([mb for mb in map(type, bases) if not trivial(mb)])

    # Combine explicit metas and base-class metas according to priority
    # If priority is True, explicit metas come first; else base metas come first
    metabases: Tuple[Type[Any], ...] = (metabs + metas) if not priority else (metas + metabs)

    if metabases in metadic:
        # If a metaclass with this combination of bases was already generated, reuse it
        return metadic[metabases]
    elif not metabases:
        # If no metaclasses are provided, default to Python's 'type'
        meta: Type[Any] = type
    elif len(metabases) == 1:
        # If there's exactly one metaclass, use it directly
        meta = metabases[0]
    else:
        # Multiple metaclasses — generate a new one that inherits from all
        # Create a synthetic name from the names of the base metaclasses
        metaname = "_" + ''.join([m.__name__ for m in metabases])
        meta = makecls()(metaname, metabases, {})  # Recursive class creation with new metaclass

    # Cache and return the new metaclass
    return metadic.setdefault(metabases, meta)

def makecls(
    *metas: Type[Any],
    **options: Any
) -> Callable[[str, Tuple[type, ...], Dict[str, Any]], Type[Any]]:
    """
    Class factory that avoids metaclass conflicts.

    Invocation syntax:
        makecls(M1, M2, ..., priority=True)(name, bases, dict)

    Parameters:
    - metas: Explicit metaclasses to consider when creating the new class.
    - priority: If True, explicit metaclasses are preferred over the bases' metaclasses.

    This function returns a class constructor function. When invoked, it resolves
    all metaclass conflicts among the base classes and the explicitly provided
    metaclasses by dynamically generating a suitable metaclass if necessary.
    """

    # If 'priority' is set, the given metaclasses are considered before base class metaclasses
    priority: bool = options.get('priority', False)
    
    # Return a constructor function that creates the class using the resolved metaclass
    return lambda n, b, d: _generatemetaclass(b, metas, priority)(n, b, d)
