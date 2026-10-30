"""Translate display text only; identifiers, player data and counters stay intact."""
import json
from pathlib import Path
import re
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

LANGUAGES = ('fr', 'en', 'es', 'de', 'it', 'pt')
FIELDS = frozenset(('name', 'title', 'subTitle', 'description', 'categoryName', 'message',
                    'packs', 'items', 'AWD_PACKS_STRING', 'rewardName', 'packName', 'campaignName', 'bio'))
PRESERVE = frozenset(('squad', 'homeSquad', 'awaySquad', 'opponentSquad', 'opponent'))
DATA = json.loads((Path(__file__).with_name('ui-translations.json')).read_text(encoding='utf-8'))


def normalize(text):
    return str(text).replace('’', "'").replace('\u00a0', ' ').replace('\u202f', ' ').strip()


@lru_cache(maxsize=512)
def compile_template(source):
    parts = re.split(r'(\{\w+\})', normalize(source))
    return re.compile(''.join('(?P<'+part[1:-1]+'>'+('\\d+' if part[1:-1] in ('n','m','year') else '.+?')+')'
                             if part.startswith('{') else re.escape(part) for part in parts))


EXACT = {}
for row in DATA['entries']:
    EXACT[normalize(row[0])] = row
    EXACT.setdefault(normalize(row[1]), row)
TEMPLATES = [(compile_template(row[0]), row) for row in sorted(DATA['templates'],key=lambda row:len(row[0]),reverse=True)]


@lru_cache(maxsize=16384)
def translate(text, lang, depth=0):
    """Return None for names/unknown strings so the caller retains the original."""
    if not isinstance(text, str) or not text or depth > 5:
        return None
    lang = lang if lang in LANGUAGES else 'en'
    index = LANGUAGES.index(lang)
    key = normalize(text)
    if key in EXACT:
        row = EXACT[key]
        return text if lang == 'fr' and key == normalize(row[0]) else row[index]
    from fut_i18n import WORDS, TEMPLATES as BASE_TEMPLATES, LANGUAGES as BASE_LANGUAGES, MESSAGES, EN_MESSAGES
    for english, values in WORDS.items():
        if key in (normalize(english), normalize(values[0])):
            return english if lang == 'en' else values[BASE_LANGUAGES.index(lang)]
    for pattern, row in TEMPLATES:
        match = pattern.fullmatch(key)
        if match:
            if lang == 'fr': return text
            args = {k: translate(v, lang, depth+1) or v for k,v in match.groupdict().items()}
            return row[index].format(**args)
    for english, values in BASE_TEMPLATES.items():
        match = compile_template(values[0]).fullmatch(key)
        if match:
            return (english if lang == 'en' else values[BASE_LANGUAGES.index(lang)]).format(**match.groupdict())
    for message, values in MESSAGES.items():
        match = compile_template(values[0]).fullmatch(key)
        if match and (lang != 'en' or message in EN_MESSAGES):
            args = {k: translate(v,lang,depth+1) or v for k,v in match.groupdict().items()}
            return (EN_MESSAGES[message] if lang == 'en' else values[BASE_LANGUAGES.index(lang)]).format(**args)
    if '\n' in text:
        lines = text.split('\n')
        changed = [translate(line,lang,depth+1) or line for line in lines]
        if changed != lines: return '\n'.join(changed)
    if ' — ' in text:
        name, edition = text.rsplit(' — ',1)
        translated = translate(edition,lang,depth+1)
        if translated is not None: return name+' — '+translated
    return None


def request_language(s, path, headers, body=b''):
    """Remember the game's explicit locale within this account's own club."""
    from fut_i18n import language_for_request
    default = s.STATE.get('mng_ui_language', str(s.CFG.get('language','fr')))
    lower = {str(k).lower():str(v) for k,v in headers.items()}
    query = parse_qs(urlsplit(path).query)
    explicit = next((query[k][0] for k in ('locale','language','lang') if query.get(k)), '')
    explicit = explicit or lower.get('x-ut-uilanguage','')
    if not explicit and urlsplit('/'+path.lstrip('/')).path.rstrip('/') == '/ut/auth':
        try:
            payload = json.loads(body)
            explicit = next((payload[k] for k in ('locale','language','uiLanguage')
                             if isinstance(payload.get(k),str)), '')
        except (ValueError,TypeError,AttributeError): pass
    explicit = explicit or lower.get('accept-language','')
    if explicit:
        language = language_for_request(path, dict(headers, **{'X-UT-UILanguage': explicit}), default)
    else:
        language = language_for_request(path,headers,default)
    if language != default:
        s.STATE.set('mng_ui_language', language)
    return language


def response(s, path, result):
    if result[0] != 200 or not re.match(r'^/ut/game/fifa21/(scmp|sbs)(?:/|$)',path):
        return result
    from fut_i18n import LANGUAGE
    lang = LANGUAGE.get()
    try: document = json.loads(result[2])
    except (ValueError,TypeError,UnicodeError): return result
    def visit(value):
        if isinstance(value,list): return [visit(child) for child in value]
        if not isinstance(value,dict): return value
        return {key: child if key in PRESERVE else
                (translate(child,lang) or child) if key in FIELDS and isinstance(child,str) else visit(child)
                for key,child in value.items()}
    headers = {k:v for k,v in result[1].items() if k.lower()!='content-length'}
    headers.update({'Content-Language':lang, 'Vary':'Accept-Language, X-UT-UILanguage', 'Cache-Control':'no-store'})
    return result[0],headers,s.json_bytes(visit(document))
