"""Manifest declarations for dependencies on other Playlite plugins."""
import re


def version_key(value):
    value=str(value).removeprefix('v')
    if not re.fullmatch(r'\d+(?:\.\d+)*',value):
        raise ValueError('Plugin dependency versions must be numeric.')
    parts=list(map(int,value.split('.')))
    while len(parts)>1 and parts[-1]==0:parts.pop()
    return tuple(parts)


def dependencies(manifest):
    entries=manifest.get('plugin_dependencies',[])
    if not isinstance(entries,list):raise ValueError('Invalid plugin dependency declarations.')
    seen=set()
    for entry in entries:
        if not isinstance(entry,dict):raise ValueError('Invalid plugin dependency declaration.')
        identity=entry.get('id','');repository=entry.get('repository','');minimum=entry.get('minimum_version','')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',identity) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):
            raise ValueError('Plugin dependencies need an ID and GitHub repository.')
        version_key(minimum)
        if identity==manifest.get('id') or identity in seen:raise ValueError('Duplicate or self-referencing plugin dependency.')
        seen.add(identity)
        yield entry


def missing_dependencies(manifest,installed):
    known={item['id']:item for item in installed}
    missing=[]
    for dependency in dependencies(manifest):
        current=known.get(dependency['id'])
        if current and current.get('repository','').casefold()!=dependency['repository'].casefold():
            raise ValueError('Plugin dependency ID belongs to a different repository: '+dependency['id'])
        if current is None or version_key(current['version'])<version_key(dependency['minimum_version']):
            missing.append(dependency)
        elif not current.get('enabled',True):
            raise ValueError('Enable required plugin '+dependency['id']+' before installing '+manifest['name']+'.')
    return missing
