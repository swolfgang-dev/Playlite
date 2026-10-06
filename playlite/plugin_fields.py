"""Plugin-declared game fields; core never identifies an individual provider."""

def collect_fields(fields, game, *, validate=True):
    for key, field in fields.items():
        source = field.property('metadata_provider')
        if not source:
            continue
        value = field.text().strip()
        if validate and field.property('positive_id') and value and (not value.isascii() or not value.isdigit() or int(value) < 1):
            raise ValueError('Game IDs must be positive whole numbers.')
        ids = dict(game.get('MetadataIds') or {})
        if value:
            ids[source] = value
        else:
            ids.pop(source, None)
        game['MetadataIds'] = ids
    return game


def refresh_fields(fields, ids):
    for field in fields.values():
        source = field.property('metadata_provider')
        if source:
            field.setText(str(ids.get(source) or ''))


def legacy_action_fields(providers):
    return {'Executable', 'Prefix', 'LaunchArguments', 'ProviderGameId'} | {
        provider.action_id_field for provider in providers if getattr(provider, 'action_id_field', None)}


def validate_declarations(fields):
    """Reject malformed field declarations before building an editor."""
    if not isinstance(fields, list):
        raise ValueError('Plugin game_fields must be a list.')
    for field in fields:
        if not isinstance(field, dict) or not all(isinstance(field.get(key), str) and field[key] for key in ('key', 'label')):
            raise ValueError('Plugin game fields need a key and label.')
        source = field.get('metadata_provider')
        if source is not None and (not isinstance(source, str) or not source):
            raise ValueError('Metadata field providers must be nonempty strings.')
        if not isinstance(field.get('positive_id', False), bool):
            raise ValueError('positive_id must be a boolean.')
    return fields
