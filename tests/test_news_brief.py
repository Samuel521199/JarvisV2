from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from host import news_brief as news
from host.news_feeds import select_items
from sdk.protocol import CoreError


def story(title='News', source='bbc-tech'):
    return dict(title=title, published=1234, source=source, url='https://example.org/'+title, summary='An update')


class NewsBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'config').mkdir()
        self.server=SimpleNamespace(data_root=self.root,background_lane=Mock())
        gate=patch.object(news,'checkpoint');gate.start();self.addCleanup(gate.stop)
        self.now=datetime(2026,11,20,9,0).timestamp()

    def deliver(self, title):
        news.produce(self.root,0,reader=lambda *args:[('bbc-tech',[story(title)],'')],clock=lambda:self.now)
        return news.snapshot(self.root)['briefs'][0]

    def test_read_replay_and_new_edition(self):
        one=self.deliver('One')
        news.command(self.server,dict(action='read',day=one['day'],edition=one['edition']))
        self.assertFalse(self.deliver('One')['unread'])
        self.assertTrue(self.deliver('Two')['unread'])
        with self.assertRaises(CoreError):
            news.command(self.server,dict(action='read',day=one['day'],edition=one['edition']))
        self.assertEqual(news.snapshot(self.root,True),{'unread':1})

    def test_all_failed_preserves_issue_and_can_retry(self):
        original=self.deliver('One')
        with self.assertRaises(CoreError):
            news.produce(self.root,0,reader=lambda *args:[('bbc-tech',[],'timeout')])
        self.assertEqual(news.snapshot(self.root)['briefs'],[original])

    def test_filter_and_optional_local_ranking(self):
        prefs={**news.DEFAULT,'exclude':['blocked'],'interest':'science'}
        rows=[story('first'),story('first'),story('Blocked news'),story('science','nasa')]
        def rank(texts,query,**kw):
            return dict(status='ready',scores={'0':0,'1':1},model='fixture')
        selected,method=select_items(rows,prefs,rank)
        self.assertEqual([r['title'] for r in selected],['science','first'])
        self.assertIn('fixture',method)

    def test_durable_daily_schedule_and_catchup(self):
        prefs={**news.DEFAULT,'enabled':True}
        news.command(self.server,dict(action='save',revision=0,settings=prefs))
        with patch.object(news.time,'time',return_value=self.now-7200):news.start(self.server,True)
        self.server.background_lane.submit.assert_not_called()
        with patch.object(news.time,'time',return_value=self.now):news.start(self.server,True)
        self.server.background_lane.submit.assert_called_once()
        news.produce(self.root,1,reader=lambda *args:[('bbc-tech',[story()],'')],clock=lambda:self.now)
        with patch.object(news.time,'time',return_value=self.now+7200):news.start(self.server,True)
        self.server.background_lane.submit.assert_called_once()
        with patch.object(news.time,'time',return_value=self.now+86400):news.start(self.server,True)
        self.assertEqual(self.server.background_lane.submit.call_count,2)

    def test_changed_subscription_discards_inflight_result(self):
        def changed(*args):
            news.command(self.server,dict(action='save',revision=0,settings=news.DEFAULT))
            return [('bbc-tech',[story()],'')]
        with self.assertRaises(CoreError):news.produce(self.root,0,reader=changed)
        self.assertFalse(news.snapshot(self.root)['briefs'])
        with self.assertRaises(CoreError):news.checked({**news.DEFAULT,'sources':['https://example.org']})
