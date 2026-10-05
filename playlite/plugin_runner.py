"""Start a worker supplied by an installed plugin in a separate process."""
import importlib
import sys
from .providers import discover_plugins


def main():
    if len(sys.argv) < 2:
        return 2
    identity = sys.argv[1]
    plugin = discover_plugins().get(identity)
    if plugin is None:
        return 2
    module = importlib.import_module(type(plugin).__module__ + '.runner')
    sys.argv = [module.__file__, *sys.argv[2:]]
    return module.main()


if __name__ == '__main__':
    sys.exit(main())
