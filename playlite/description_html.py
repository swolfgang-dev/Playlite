"""Keep description formatting while excluding embedded images."""
from html.parser import HTMLParser


class _WithoutImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in ('img', 'source'):
            self.parts.append(self.get_starttag_text())

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag not in ('img', 'source'):
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f'&{name};')

    def handle_charref(self, name):
        self.parts.append(f'&#{name};')


def without_images(content):
    parser = _WithoutImages()
    parser.feed(content or '')
    return ''.join(parser.parts)
