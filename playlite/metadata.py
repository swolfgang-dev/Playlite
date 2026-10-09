"""Shared metadata, links, dates, and artwork utilities."""
from datetime import datetime
import json
from pathlib import Path
import urllib.parse
import urllib.request
from .sorting_name import sorting_name as sorting_name
from .description_html import without_images as without_images


class MetadataError(Exception):
    pass


def link_name(url, existing='', category=None):
    host = (urllib.parse.urlsplit(url).hostname or '').removeprefix('www.')
    if existing and existing.casefold() not in (host.casefold(), ('www.' + host).casefold()):
        return existing
    domains = {'steampowered.com': 'Steam', 'igdb.com': 'IGDB', 'facebook.com': 'Facebook',
               'xbox.com': 'Xbox', 'playstation.com': 'PlayStation Store', 'twitter.com': 'Twitter',
               'x.com': 'X', 'youtube.com': 'YouTube', 'youtu.be': 'YouTube', 'instagram.com': 'Instagram',
               'discord.gg': 'Discord', 'discord.com': 'Discord', 'fandom.com': 'Community Wiki',
               'wikia.com': 'Community Wiki', 'twitch.tv': 'Twitch', 'wikipedia.org': 'Wikipedia',
               'gog.com': 'GOG', 'epicgames.com': 'Epic Games Store', 'itch.io': 'itch.io',
               'reddit.com': 'Reddit', 'bsky.app': 'Bluesky'}
    for domain, name in domains.items():
        if host == domain or host.endswith('.' + domain):
            return name
    categories = {1: 'Official Website', 2: 'Community Wiki', 'official': 'Official Website',
                  'wikia': 'Community Wiki', 'wiki': 'Community Wiki'}
    return categories.get(category, host or existing)


def friendly_links(links):
    return [dict(link, Name=link_name(link.get('Url', ''), link.get('Name', ''))) for link in links]


def request(url, limit=4 * 1024 * 1024):
    req = urllib.request.Request(url, headers={'User-Agent': 'Playlite/0.1', 'Accept-Language': 'en'})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read(limit + 1)
    except (OSError, ValueError) as error:
        raise MetadataError(f'Could not download metadata: {error}') from error
    if len(content) > limit:
        raise MetadataError('The source returned a response that is too large.')
    return content


def request_json(url):
    try:
        return json.loads(request(url))
    except (ValueError, UnicodeError) as error:
        raise MetadataError('The source returned an invalid response. Please try again.') from error






def release_date(value):
    for pattern in ('%d %b, %Y', '%b %d, %Y', '%d %B, %Y', '%B %d, %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return None






def merge_links(existing, incoming):
    result = [dict(link) for link in existing]
    for link in incoming:
        # Keep unrelated existing links; update the canonical Steam/website link.
        by_name = next((old for old in result if old['Name'].casefold() == link['Name'].casefold()), None) \
            if link['Name'].casefold() in ('steam', 'official website') else None
        if by_name:
            by_name.update(link)
        elif not any(old['Url'].rstrip('/') == link['Url'].rstrip('/') for old in result):
            result.append(dict(link))
    return result


def download_artwork(url, target):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or not (
            parsed.hostname == 'images.igdb.com' or parsed.hostname in ('cdn.steamgriddb.com', 'cdn2.steamgriddb.com', 'shared.fastly.steamstatic.com') or parsed.hostname.endswith('.steamstatic.com') or parsed.hostname.endswith('.akamaihd.net')):
        raise MetadataError('The source returned an unsupported artwork address.')
    from PyQt6.QtGui import QImageReader
    content = request(url, limit=20 * 1024 * 1024)
    if content.startswith(b'PK\x03\x04') or parsed.path.lower().endswith('.tga'):
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        from zipfile import ZipFile, BadZipFile
        try:
            if content.startswith(b'PK\x03\x04'):
                choices = []
                with ZipFile(BytesIO(content)) as archive:
                    for entry in archive.infolist():
                        if entry.file_size > 20 * 1024 * 1024 or entry.is_dir():
                            continue
                        try:
                            image = Image.open(BytesIO(archive.read(entry)))
                            if image.width * image.height <= 40_000_000:
                                image.load()
                                choices.append(image.copy())
                        except (UnidentifiedImageError, OSError, ValueError):
                            continue
                if not choices:
                    raise ValueError('No images in icon archive')
                image = max(choices, key=lambda item: item.width * item.height)
            else:
                image = Image.open(BytesIO(content))
            output = BytesIO()
            image.convert('RGBA').save(output, format='PNG')
            content = output.getvalue()
            target = Path(target).with_suffix('.png')
        except (BadZipFile, OSError, ValueError, Image.DecompressionBombError) as error:
            raise MetadataError('Could not read the downloaded client icon.') from error
    target = Path(target)
    target.write_bytes(content)
    reader = QImageReader(str(target))
    if not reader.canRead():
        target.unlink(missing_ok=True)
        raise MetadataError('The downloaded artwork is not a readable image.')
    if bytes(reader.format()).lower() == b'ico':
        # Qt defaults to the first ICO frame, often only 16×16. Keep the largest.
        sizes = []
        for index in range(reader.imageCount()):
            if reader.jumpToImage(index):
                size = reader.size()
                sizes.append((size.width() * size.height(), index))
        if sizes:
            reader.jumpToImage(max(sizes)[1])
        image = reader.read()
        converted = target.with_suffix('.png')
        if image.isNull() or not image.save(str(converted), 'PNG'):
            target.unlink(missing_ok=True)
            raise MetadataError('Could not read the downloaded client icon.')
        if converted != target:
            target.unlink(missing_ok=True)
        target = converted
    return str(target)
