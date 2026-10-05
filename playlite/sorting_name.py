"""Playnite-compatible title conversion, adapted from SortableNameConverter.

Copyright (c) 2020 Josef Nemec. MIT license: ../licenses/Playnite-MIT.txt.
https://github.com/JosefNemec/Playnite/blob/master/source/Playnite/SortableNameConverter.cs
"""
import re

EXCLUDED = {'XL', 'XD', 'DX', 'XXX', 'L', 'C', 'D', 'M', 'MII', 'MIX', 'MX', 'MC', 'DC'}
ROMAN = dict(zip('IVXLCDM', (1, 5, 10, 50, 100, 500, 1000)))
for chars in ('ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅬⅭⅮⅯ', 'ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅺⅻⅼⅽⅾⅿ'):
    ROMAN.update(zip(chars, (*range(1, 13), 50, 100, 500, 1000)))
ROMAN.update(zip('ↀↁↂↃↄↅↆↇↈ', (1000, 5000, 10000, 100, 100, 6, 50, 50000, 100000)))
EDITION = re.compile(r"(\s*[:-])?(\s+([a-z']+\s+(edition|cut)|hd|collection|remaster(ed)?|remake|ultimate|anthology|game of the))+$", re.I)
TOKENS = re.compile(r'(?<![\w.])(?<!^)(?:(?P<roman>[IVXLCDM\u2160-\u2188]+)(?!\.)|(?P<number>[0-9]+))(?=\W|$)|(?P<article>^(?i:The|A|An)\s+)|\b(?P<word>(?i:one|two|three))\b')


def roman_number(text):
    total = largest = previous = repeats = 0
    for char in reversed(text):
        value = ROMAN.get(char)
        if value is None:
            return None
        subtract = value < largest
        if subtract and (previous < largest or value * 5 > largest):
            return None
        if value == previous:
            power = value
            while power > 9 and power % 10 == 0:
                power //= 10
            repeats += 1
            if power != 1 or repeats >= 4:
                return None
        else:
            repeats = 1
        total += -value if subtract else value
        largest = max(largest, value)
        previous = value
    return total or None


def sorting_name(title):
    if not title or not title.strip():
        return title
    suffix = EDITION.search(title)
    edition = suffix.group() if suffix else ''
    title = title[:suffix.start()] if suffix else title
    def contextual(match, distance=0):
        return len(title) - match.end() <= distance or any(
            word in title[max(0, match.start() - 9):match.start()].casefold()
            for word in ('chapter', 'season', 'episode'))
    def replace(match):
        value = match.group()
        if match['article']:
            return ''
        if match['number']:
            return value.zfill(2)
        if match['word']:
            return str({'one': 1, 'two': 2, 'three': 3}[value.casefold()]).zfill(2) if contextual(match) else value
        if value == 'I' and not contextual(match):
            return value
        if value == 'X':
            if not contextual(match, 4):
                return value
            following = title[match.end():]
            if following.startswith('-') and len(following) > 1:
                word = following[1:].split()[0]
                if word.isalpha() and (word in EXCLUDED or roman_number(word) is None):
                    return value
        if value in EXCLUDED:
            return value
        number = roman_number(value)
        return str(number).zfill(2) if number is not None else value
    return TOKENS.sub(replace, title) + edition
