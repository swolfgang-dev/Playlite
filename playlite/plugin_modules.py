"""Load each plugin package consistently for the lifetime of a process."""
import importlib.util
from pathlib import Path
import sys
import threading
import types


_LOCK = threading.RLock()


def load_module(identity, directory):
    """Reuse a package, or replace its whole namespace when the root changes.

    Installing updated code requires a restart. Re-executing only plugin.py
    would mix new classes with cached helpers, clients and module-level state.
    """
    path = Path(directory).resolve() / 'plugin.py'
    name = 'playlite_plugins.' + identity.lower()
    with _LOCK:
        existing = sys.modules.get(name)
        if existing is not None and Path(existing.__file__).resolve() == path:
            return existing
        namespace = sys.modules.setdefault('playlite_plugins', types.ModuleType('playlite_plugins'))
        namespace.__path__ = []
        previous = {key: value for key, value in sys.modules.copy().items()
                    if key == name or key.startswith(name + '.')}
        for key in previous:
            del sys.modules[key]
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            for key in list(sys.modules):
                if key == name or key.startswith(name + '.'):
                    del sys.modules[key]
            sys.modules.update(previous)
            raise
        return module
