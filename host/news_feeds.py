"""Publisher feeds for the owner's personal reader. Fetch metadata only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
import xml.etree.ElementTree as ET
from host.news_topics import topic_filter

# One editorial section per selectable source. Region is publisher location.
BBC = 'https://feeds.bbci.co.uk/'
CNA = 'https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category='
FEEDS = {
    'bbc-zh': ('BBC 中文', '英国', '国际', BBC+'zhongwen/trad/rss.xml'),
    'un-zh': ('联合国新闻 · 中文', '联合国', '国际', 'https://news.un.org/feed/subscribe/zh/news/all/rss.xml'),
    'dw-world': ('德国之声', '德国', '国际', 'https://rss.dw.com/xml/rss-en-world'),
    'cna-asia': ('CNA 亚洲', '新加坡', '亚洲', CNA+'6511'),
    'agencia-brasil': ('巴西通讯社', '巴西', '拉美', 'https://agenciabrasil.ebc.com.br/feed/ultimasnoticias/feed.xml'),
    'sanews': ('SAnews', '南非', '非洲', 'https://www.sanews.gov.za/rss.xml'),
    'abc-au': ('ABC News', '澳大利亚', '综合', 'https://www.abc.net.au/news/feed/51120/rss.xml'),
    'bbc-tech': ('BBC 科技', '英国', '科技', BBC+'news/technology/rss.xml'),
    'nasa': ('NASA', '美国', '科学', 'https://www.nasa.gov/feed/'),
    'cna-business': ('CNA 商业', '新加坡', '财经', CNA+'6936'),
    'bbc-health': ('BBC 健康', '英国', '健康', BBC+'news/health/rss.xml'),
    'bbc-arts': ('BBC 文化', '英国', '文化', BBC+'news/entertainment_and_arts/rss.xml'),
    'bbc-sport': ('BBC 体育', '英国', '体育', BBC+'sport/rss.xml'),
}
LIMIT = 2_000_000


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != 'https' or target.netloc != urlsplit(req.full_url).netloc:
            raise ValueError('unexpected redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def plain(value, limit):
    parser = Text()
    parser.feed((value or '')[:12000])
    text = ' '.join(' '.join(parser.parts).split())
    return text if len(text) <= limit else text[:limit-1].rstrip()+'…'


def read_feed(key, now, check):
    check()
    req = Request(FEEDS[key][3], headers={'User-Agent':'Jarvis-Personal-RSS/1.0', 'Accept':'application/rss+xml, application/xml, text/xml'})
    with build_opener(SameHostRedirect()).open(req, timeout=8) as response:
        deadline = time.monotonic()+12
        raw = bytearray()
        while len(raw)<=LIMIT:
            if time.monotonic()>deadline:
                raise TimeoutError('feed deadline')
            chunk = response.read1(min(65536,LIMIT+1-len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
    if len(raw)>LIMIT or re.search(br'<!\s*(ENTITY|DOCTYPE)', raw, re.I):
        raise ValueError('feed exceeds format limits')
    channel = ET.fromstring(raw).find('channel')
    if channel is None:
        raise ValueError('expected RSS channel')
    result = []
    for entry in channel.findall('item')[:120]:
        try:
            stamp = parsedate_to_datetime(entry.findtext('pubDate') or '')
            if stamp.tzinfo is None:
                continue
            published = stamp.astimezone(timezone.utc).timestamp()
            url = urlsplit((entry.findtext('link') or '').strip())
            if not now-86400 <= published <= now or url.scheme not in ('https','http') or not url.hostname or url.username or url.password:
                continue
            title = plain(entry.findtext('title'), 300)
            if title:
                result.append(dict(title=title, summary=plain(entry.findtext('description'), 250),
                                   url=urlunsplit(url._replace(fragment='')), published=published, source=key))
        except (ValueError, OverflowError, TypeError):
            continue
    return result


def collect(keys, now, check):
    def one(key):
        try:
            return key, read_feed(key, now, check), ''
        except HTTPError as exc:
            return key, [], 'HTTP '+str(exc.code)
        except (OSError, ET.ParseError, ValueError) as exc:
            return key, [], type(exc).__name__
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(one, keys))


def select_items(rows, prefs, rank=None):
    buckets, urls, titles = {}, set(), set()
    banned = [word.casefold() for word in prefs['exclude']]
    matches = topic_filter(prefs)
    ordered = sorted(rows, key=lambda r:r['published'], reverse=True)
    for row in ordered:
        title = ' '.join(row['title'].casefold().split())
        if row['url'] in urls or title in titles or any(w in title+' '+row['summary'].casefold() for w in banned):
            continue
        if matches and not matches(FEEDS[row['source']][2],title+' '+row['summary']):
            continue
        urls.add(row['url'])
        titles.add(title)
        topic = FEEDS[row['source']][2]
        buckets.setdefault(topic, []).append(row)
    # Interleave sections so a prolific desk cannot crowd out the other news.
    candidates = []
    while len(candidates)<64 and any(buckets.values()):
        for bucket in buckets.values():
            if bucket and len(candidates)<64:
                candidates.append(bucket.pop(0))
    method = '兴趣筛选 · 按栏目与时间' if matches else '按栏目与时间'
    if rank and prefs['interest'] and candidates:
        texts = [dict(id=str(i), key=row['title'][:125], value='') for i,row in enumerate(candidates)]
        result = rank(texts, prefs['interest'], wait_seconds=2.2)
        if result.get('status')=='ready' and len(result['scores'])==len(texts):
            candidates = [row for _,row in sorted(enumerate(candidates),key=lambda p:result['scores'][str(p[0])],reverse=True)]
            method = '本地模型 · '+result['model']
        else:
            method += '（本地模型暂不可用）'
    return candidates[:prefs['limit']], method
