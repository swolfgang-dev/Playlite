"""Shared API-v1 manifest validation for installation and discovery."""
import re
from .plugin_dependencies import check_core_version, dependencies
from .plugin_fields import validate_declarations


PLUGIN_TYPES = frozenset(('metadata', 'game', 'generic', 'installation', 'integration', 'image', 'theme'))


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Plugin manifest must be an object.')
    identity = manifest.get('id')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', identity) or identity.casefold() in ('manual', 'current'):
        raise ValueError('Invalid or reserved plugin ID.')
    if type(manifest.get('api_version')) is not int or manifest['api_version'] != 1:
        raise ValueError('Unsupported plugin API version.')
    kind = manifest.get('type', 'metadata')
    if not isinstance(kind, str) or kind not in PLUGIN_TYPES:
        raise ValueError('Unsupported plugin type.')
    for key in ('name', 'version'):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError('Plugin name and version are required.')
    if not isinstance(manifest.get('enabled', True), bool):
        raise ValueError('Plugin enabled must be true or false.')
    fields = manifest.get('fields', [])
    if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
        raise ValueError('fields must be a list of metadata field names.')
    validate_declarations(manifest.get('game_fields', []))
    if not isinstance(manifest.get('image_defaults', {}), dict):
        raise ValueError('Plugin image_defaults must be an object.')
    requirements = manifest.get('requirements', [])
    if not isinstance(requirements, list) or not all(
            isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]+(?:>=[0-9.]+)?', value)
            for value in requirements):
        raise ValueError('Invalid plugin dependency list.')
    list(dependencies(manifest))
    check_core_version(manifest)
    return manifest
