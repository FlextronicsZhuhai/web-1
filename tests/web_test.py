try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import atexit
import datetime
import glob
import hashlib
import os
import os.path
import re
import tempfile
import traceback
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2

from flask import json, url_for

from libearth.compat import binary
from libearth.crawler import crawl
from libearth.feed import Entry, Feed, Person, Text
from libearth.feedlist import (Feed as FeedOutline,
                               FeedCategory as CategoryOutline, FeedList)
from libearth.schema import write
from libearth.tz import utc

from earthreader.web import app, get_hash

from pytest import fixture


@app.errorhandler(400)
def bad_request_handler_for_testing(exception):
    '''Custom error handler of :http:statuscode:`400` for unit testing
    to know how it's going in the application.

    '''
    traceback.print_exc(exception)
    return (
        traceback.format_exc(exception),
        400,
        {'Content-Type': 'text/plain; charset=utf-8'}
    )


@app.errorhandler(500)
def server_error_handler_for_testing(exception):
    '''Custom error handler of :http:statuscode:`500` for unit testing
    to know how it's going in the application.

    '''
    traceback.print_exc(exception)
    return (
        traceback.format_exc(exception),
        500,
        {'Content-Type': 'text/plain; charset=utf-8'}
    )


tmp_dir = tempfile.mkdtemp() + '/'


def rm_tmp_dir():
    os.rmdir(tmp_dir)

atexit.register(rm_tmp_dir)


app.config.update(dict(
    REPOSITORY=tmp_dir,
    OPML='test.opml'
))


REPOSITORY = app.config['REPOSITORY']
OPML = app.config['OPML']


opml = '''
<opml version="1.0">
  <head>
    <title>test opml</title>
  </head>
  <body>
    <outline text="categoryone" title="categoryone">
        <outline type="atom" text="Feed One" title="Feed One"
        xmlUrl="http://feedone.com/feed/atom/" />
        <outline text="categorytwo" title="categorytwo">
            <outline type="atom" text="Feed Two" title="Feed Two"
            xmlUrl="http://feedtwo.com/feed/atom/" />
        </outline>
    </outline>
    <outline type="atom" text="Feed Three" title="Feed Three"
    xmlUrl="http://feedthree.com/feed/atom/" />
    <outline text="categorythree" title="categorythree">
        <outline type="atom" text="Feed Four" title="Feed Four"
        xmlUrl="http://feedfour.com/feed/atom/" />
    </outline>
  </body>
</opml>
'''


feed_one = '''
<feed xmlns="http://www.w3.org/2005/Atom">
    <title type="text">Feed One</title>
    <id>http://feedone.com/feed/atom/</id>
    <updated>2013-08-19T07:49:20+07:00</updated>
    <link type="text/html" rel="alternate" href="http://feedone.com" />
    <entry>
        <title>Feed One: Entry One</title>
        <id>http://feedone.com/feed/atom/1/</id>
        <updated>2013-08-19T07:49:20+07:00</updated>
        <published>2013-08-19T07:49:20+07:00</published>
        <content>This is content of Entry One in Feed One</content>
    </entry>
    <entry>
        <title>Feed One: Entry Two</title>
        <id>http://feedone.com/feed/atom/2/</id>
        <updated>2013-10-19T07:49:20+07:00</updated>
        <published>2013-10-19T07:49:20+07:00</published>
        <content>This is content of Entry Two in Feed One</content>
    </entry>
</feed>
'''

feed_two = '''
<feed xmlns="http://www.w3.org/2005/Atom">
    <title type="text">Feed Two</title>
    <id>http://feedtwo.com/feed/atom/</id>
    <updated>2013-08-20T07:49:20+07:00</updated>
    <link type="text/html" rel="alternate" href="http://feedtwo.com" />
    <entry>
        <title>Feed Two: Entry One</title>
        <id>http://feedtwo.com/feed/atom/1/</id>
        <updated>2013-08-20T07:49:20+07:00</updated>
        <published>2013-08-20T07:49:20+07:00</published>
        <content>This is content of Entry One in Feed Two</content>
    </entry>
</feed>
'''


feed_three = '''
<feed xmlns="http://www.w3.org/2005/Atom">
    <title type="text">Feed Three</title>
    <id>http://feedthree.com/feed/atom/</id>
    <updated>2013-08-21T07:49:20+07:00</updated>
    <link type="text/html" rel="alternate" href="http://feedthree.com" />
    <entry>
        <title>Feed Three: Entry One</title>
        <id>http://feedthree.com/feed/atom/1/</id>
        <updated>2013-08-21T07:49:20+07:00</updated>
        <published>2013-08-21T07:49:20+07:00</published>
        <content>This is content of Entry One in Feed Three</content>
    </entry>
</feed>
'''


feed_four = '''
<feed xmlns="http://www.w3.org/2005/Atom">
    <title type="text">Feed Four</title>
    <id>http://feedfour.com/feed/atom/</id>
    <updated>2013-08-22T07:49:20+07:00</updated>
    <link type="text/html" rel="alternate" href="http://feedfour.com" />
    <entry>
        <title>Feed Four: Entry One</title>
        <id>http://feedfour.com/feed/atom/1/</id>
        <updated>2013-08-22T07:49:20+07:00</updated>
        <published>2013-08-22T07:49:20+07:00</published>
        <content>This is content of Entry One in Feed Four</content>
    </entry>
</feed>
'''


feed_to_add = '''
<feed xmlns="http://www.w3.org/2005/Atom">
    <title type="text">Feed Five</title>
    <id>http://feedfive.com/feed/atom/</id>
    <updated>2013-08-23T07:49:20+07:00</updated>
    <link type="text/html" rel="alternate" href="http://feedfive.com" />
    <entry>
        <title>Feed Five: Entry One</title>
        <id>http://feedfive.com/feed/atom/1/</id>
        <updated>2013-08-22T07:49:20+07:00</updated>
        <published>2013-08-22T07:49:20+07:00</published>
        <content>This is content of Entry One in Feed Four</content>
    </entry>
</feed>
'''


def get_feed_urls(category, urls=[]):
    for child in category:
        if isinstance(child, FeedOutline):
            urls.append(child.xml_url)
        elif isinstance(child, CategoryOutline):
            get_feed_urls(child, urls)
    return urls


def mock_response(req):
    if req.get_full_url() == 'http://feedone.com/feed/atom/':
        resp = urllib2.addinfourl(StringIO(feed_one), 'mock message',
                                  req.get_full_url())
        resp.code = 200
        resp.msg = "OK"
        return resp
    if req.get_full_url() == 'http://feedtwo.com/feed/atom/':
        resp = urllib2.addinfourl(StringIO(feed_two), 'mock message',
                                  req.get_full_url())
        resp.code = 200
        resp.msg = "OK"
        return resp
    if req.get_full_url() == 'http://feedthree.com/feed/atom/':
        resp = urllib2.addinfourl(StringIO(feed_three), 'mock message',
                                  req.get_full_url())
        resp.code = 200
        resp.msg = "OK"
        return resp
    if req.get_full_url() == 'http://feedfour.com/feed/atom/':
        resp = urllib2.addinfourl(StringIO(feed_four), 'mock message',
                                  req.get_full_url())
        resp.code = 200
        resp.msg = "OK"
        return resp
    if req.get_full_url() == 'http://feedfive.com/feed/atom/':
        resp = urllib2.addinfourl(StringIO(feed_to_add), 'mock message',
                                  req.get_full_url())
        resp.code = 200
        resp.msg = "OK"
        return resp


class TestHTTPHandler(urllib2.HTTPHandler):
    def http_open(self, req):
        return mock_response(req)


my_opener = urllib2.build_opener(TestHTTPHandler)
urllib2.install_opener(my_opener)


@fixture
def xmls(request):
    if not os.path.isdir(REPOSITORY):
        os.mkdir(REPOSITORY)
    feed_list = FeedList(opml, is_xml_string=True)
    feed_urls = get_feed_urls(feed_list)
    generator = crawl(feed_urls, 4)
    for result in generator:
        feed_data = result[1][0]
        feed_url = result[0]
        file_name = hashlib.sha1(binary(feed_url)).hexdigest() + '.xml'
        with open(REPOSITORY + file_name, 'w+') as f:
            for chunk in write(feed_data, indent='    ',
                               canonical_order=True):
                f.write(chunk)
    feed_list.save_file(REPOSITORY + OPML)

    def remove_test_repo():
        files = glob.glob(REPOSITORY + '*')
        for file in files:
            os.remove(file)

    request.addfinalizer(remove_test_repo)


def test_all_feeds(xmls):
    FEED_ID_PATTERN = re.compile('(?:.?)+/feeds/(.+)/entries/')
    with app.test_client() as client:
        # /
        r = client.get('/feeds/')
        assert r.status_code == 200
        result = json.loads(r.data)
        root_feeds = result['feeds']
        root_categories = result['categories']
        assert root_feeds[0]['title'] == 'Feed Three'
        assert root_categories[0]['title'] == 'categoryone'
        assert root_categories[1]['title'] == 'categorythree'
        # /feedthree
        feed_url = root_feeds[0]['entries_url']
        feed_id = FEED_ID_PATTERN.match(feed_url).group(1)
        assert feed_url == \
            url_for(
                'feed_entries',
                feed_id=feed_id,
                _external=True
            )
        r = client.get(feed_url)
        assert r.status_code == 200
        result = json.loads(r.data)
        entries = result['entries']
        assert entries[0]['title'] == 'Feed Three: Entry One'
        assert entries[0]['entry_url'] == \
            url_for(
                'feed_entry',
                feed_id=feed_id,
                entry_id=get_hash('http://feedthree.com/feed/atom/1/'),
                _external=True
            )
        assert entries[0]['updated'] == '2013-08-21 07:49:20+07:00'
        r = client.get(entries[0]['entry_url'])
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'Feed Three: Entry One'
        assert result['content'] == \
            'This is content of Entry One in Feed Three'
        assert result['updated'] == '2013-08-21 07:49:20+07:00'
        # /categoryone
        category_url = root_categories[0]['feeds_url']
        assert category_url == \
            url_for(
                'feeds',
                category_id='-categoryone',
                _external=True
            )
        one_r = client.get(root_categories[0]['feeds_url'])
        assert one_r.status_code == 200
        one_result = json.loads(one_r.data)
        one_feeds = one_result['feeds']
        one_categories = one_result['categories']
        assert one_feeds[0]['title'] == 'Feed One'
        assert one_categories[0]['title'] == 'categorytwo'
        # /categoryone/feedone
        feed_url = one_feeds[0]['entries_url']
        feed_id = FEED_ID_PATTERN.match(feed_url).group(1)
        assert feed_url == \
            url_for(
                'feed_entries',
                category_id='-categoryone',
                feed_id=feed_id,
                _external=True
            )
        r = client.get(feed_url)
        assert r.status_code == 200
        result = json.loads(r.data)
        entries = result['entries']
        assert entries[0]['title'] == 'Feed One: Entry Two'
        assert entries[0]['entry_url'] == \
            url_for(
                'feed_entry',
                category_id='-categoryone',
                feed_id=feed_id,
                entry_id=get_hash('http://feedone.com/feed/atom/2/'),
                _external=True
            )
        assert entries[0]['updated'] == '2013-10-19 07:49:20+07:00'
        assert entries[1]['title'] == 'Feed One: Entry One'
        assert entries[1]['entry_url'] == \
            url_for(
                'feed_entry',
                category_id='-categoryone',
                feed_id=feed_id,
                entry_id=get_hash('http://feedone.com/feed/atom/1/'),
                _external=True
            )
        assert entries[1]['updated'] == '2013-08-19 07:49:20+07:00'
        r = client.get(entries[0]['entry_url'])
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'Feed One: Entry Two'
        assert result['content'] == \
            'This is content of Entry Two in Feed One'
        assert result['updated'] == '2013-10-19 07:49:20+07:00'
        # /categoryone/categorytwo
        two_r = client.get(one_categories[0]['feeds_url'])
        assert two_r.status_code == 200
        two_result = json.loads(two_r.data)
        two_feeds = two_result['feeds']
        two_categories = two_result['categories']
        assert two_feeds[0]['title'] == 'Feed Two'
        assert len(two_categories) == 0
        # /categoryone/categorytwo/feedtwo
        category_url = one_categories[0]['feeds_url']
        assert category_url == \
            url_for(
                'feeds',
                category_id='-categoryone/-categorytwo',
                _external=True
            )

        feed_url = two_feeds[0]['entries_url']
        feed_id = FEED_ID_PATTERN.match(feed_url).group(1)
        assert feed_url == \
            url_for(
                'feed_entries',
                category_id='-categoryone/-categorytwo',
                feed_id=feed_id,
                _external=True
            )
        r = client.get(feed_url)
        assert r.status_code == 200
        result = json.loads(r.data)
        entries = result['entries']
        assert entries[0]['title'] == 'Feed Two: Entry One'
        assert entries[0]['entry_url'] == \
            url_for(
                'feed_entry',
                category_id='-categoryone/-categorytwo',
                feed_id=feed_id,
                entry_id=get_hash('http://feedtwo.com/feed/atom/1/'),
                _external=True
            )
        assert entries[0]['updated'] == '2013-08-20 07:49:20+07:00'
        r = client.get(entries[0]['entry_url'])
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'Feed Two: Entry One'
        assert result['content'] == \
            'This is content of Entry One in Feed Two'
        assert result['updated'] == '2013-08-20 07:49:20+07:00'
        # categorythree
        category_url = root_categories[1]['feeds_url']
        assert category_url == \
            url_for(
                'feeds',
                category_id='-categorythree',
                _external=True
            )
        three_r = client.get(root_categories[1]['feeds_url'])
        assert three_r.status_code == 200
        three_result = json.loads(three_r.data)
        three_feeds = three_result['feeds']
        three_categories = three_result['categories']
        assert three_feeds[0]['title'] == 'Feed Four'
        assert len(three_categories) == 0
        # /categorythree/feedone
        feed_url = three_feeds[0]['entries_url']
        feed_id = FEED_ID_PATTERN.match(feed_url).group(1)
        assert feed_url == \
            url_for(
                'feed_entries',
                category_id='-categorythree',
                feed_id=feed_id,
                _external=True
            )
        r = client.get(feed_url)
        assert r.status_code == 200
        result = json.loads(r.data)
        entries = result['entries']
        assert entries[0]['title'] == 'Feed Four: Entry One'
        assert entries[0]['entry_url'] == \
            url_for(
                'feed_entry',
                category_id='-categorythree',
                feed_id=feed_id,
                entry_id=get_hash('http://feedfour.com/feed/atom/1/'),
                _external=True
            )
        assert entries[0]['updated'] == '2013-08-22 07:49:20+07:00'
        r = client.get(entries[0]['entry_url'])
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'Feed Four: Entry One'
        assert result['content'] == \
            'This is content of Entry One in Feed Four'
        assert result['updated'] == '2013-08-22 07:49:20+07:00'


def test_invalid_path(xmls):
    with app.test_client() as client:
        feed_id = hashlib.sha1(
            binary('http://feedone.com/feed/atom/')).hexdigest()
        r = client.get('/non-exist-category/feeds/' + feed_id + '/entries/')
        result = json.loads(r.data)
        assert r.status_code == 404
        assert result['error'] == 'category-path-invalid'


def test_add_feed(xmls):
    with app.test_client() as client:
        r = client.post('/feeds/',
                        data=dict(url='http://feedfive.com/feed/atom/'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['feeds'][1]['title'] == 'Feed Five'
        opml = FeedList(REPOSITORY + OPML)
        assert opml[3].title == 'Feed Five'


def test_add_feed_in_category(xmls):
    with app.test_client() as client:
        r = client.get('/-categoryone/feeds/')
        assert r.status_code == 200
        result = json.loads(r.data)
        add_feed_url = result['categories'][0]['add_feed_url']
        r = client.post(add_feed_url,
                        data=dict(url='http://feedfive.com/feed/atom/'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['feeds'][0]['title'] == 'Feed Two'
        assert result['feeds'][1]['title'] == 'Feed Five'
        opml = FeedList(REPOSITORY + OPML)
        assert opml[0][1][1].title == 'Feed Five'


def test_add_category(xmls):
    with app.test_client() as client:
        r = client.post('/',
                        data=dict(title='addedcategory'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['categories'][2]['title'] == 'addedcategory'
        opml = FeedList(REPOSITORY + OPML)
        assert opml[3].text == 'addedcategory'


def test_add_category_in_category(xmls):
    with app.test_client() as client:
        r = client.get('/feeds/')
        assert r.status_code == 200
        result = json.loads(r.data)
        add_category_url = result['categories'][0]['add_category_url']
        r = client.post(add_category_url,
                        data=dict(title='addedcategory'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['categories'][1]['title'] == 'addedcategory'
        opml = FeedList(REPOSITORY + OPML)
        assert opml[0][2].text == 'addedcategory'


def test_add_category_without_opml():
    with app.test_client() as client:
        r = client.post('/',
                        data=dict(title='testcategory'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['categories'][0]['title'] == 'testcategory'
        REPOSITORY = app.config['REPOSITORY']
        OPML = app.config['OPML']
        feed_list = FeedList(REPOSITORY + OPML)
        assert feed_list[0].text == 'testcategory'
        os.remove(REPOSITORY + OPML)
        os.rmdir(REPOSITORY)


def test_add_feed_without_opml():
    with app.test_client() as client:
        r = client.post('/feeds/',
                        data=dict(url='http://feedone.com/feed/atom/'))
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['feeds'][0]['title'] == 'Feed One'
        REPOSITORY = app.config['REPOSITORY']
        OPML = app.config['OPML']
        feed_list = FeedList(REPOSITORY + OPML)
        assert feed_list[0].title == 'Feed One'
    files = glob.glob(REPOSITORY + '*')
    for file in files:
        os.remove(file)
    os.rmdir(REPOSITORY)


def test_delete_feed(xmls):
    REPOSITORY = app.config['REPOSITORY']
    with app.test_client() as client:
        feed_id = hashlib.sha1(
            binary('http://feedthree.com/feed/atom/')).hexdigest()
        r = client.delete('/feeds/' + feed_id + '/')
        assert r.status_code == 200
        result = json.loads(r.data)
        for child in result['feeds']:
            assert child['title'] != 'Feed Three'
        assert not REPOSITORY + feed_id + '.xml' in glob.glob(REPOSITORY + '*')


def test_delete_feed_in_category(xmls):
    REPOSITORY = app.config['REPOSITORY']
    with app.test_client() as client:
        feed_id = get_hash('http://feedone.com/feed/atom/')
        assert REPOSITORY + feed_id + '.xml' in glob.glob(REPOSITORY + '*')
        r = client.get('/-categoryone/feeds/')
        assert r.status_code == 200
        result = json.loads(r.data)
        remove_feed_url = result['feeds'][0]['remove_feed_url']
        r = client.delete(remove_feed_url)
        assert r.status_code == 200
        result = json.loads(r.data)
        assert len(result['feeds']) == 0
        assert not REPOSITORY + feed_id + '.xml' in glob.glob(REPOSITORY + '*')


def test_delete_feed_in_two_category(xmls):
    REPOSITORY = app.config['REPOSITORY']
    with app.test_client() as client:
        feed_id = get_hash('http://feedone.com/feed/atom/')
        assert REPOSITORY + feed_id + '.xml' in glob.glob(REPOSITORY + '*')
        r = client.post('/feeds/',
                        data=dict(url='http://feedone.com/feed/atom/'))
        assert r.status_code == 200
        feed_list = FeedList(REPOSITORY + OPML)
        assert feed_list[0][0].title == 'Feed One'
        assert feed_list[3].title == 'Feed One'
        feed_id = hashlib.sha1(
            binary('http://feedone.com/feed/atom/')).hexdigest()
        r = client.delete('/-categoryone/feeds/' + feed_id + '/')
        assert r.status_code == 200
        feed_list = FeedList(REPOSITORY + OPML)
        for child in feed_list[0]:
            assert not child.title == 'Feed One'
        assert feed_list[3].title == 'Feed One'
        assert REPOSITORY + feed_id + '.xml' in glob.glob(REPOSITORY + '*')


def test_delete_non_exists_feed(xmls):
    with app.test_client() as client:
        r = client.delete('/feeds/non-exists-feed/')
        assert r.status_code == 400
        result = json.loads(r.data)
        assert result['error'] == 'feed-not-found-in-path'


def test_delete_category_in_root(xmls):
    with app.test_client() as client:
        r = client.delete('/categoryone/')
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result == json.loads(client.get('/feeds/').data)
        for child in result['feeds']:
            assert not child['title'] == 'categoryone'


def test_delete_category_in_category(xmls):
    with app.test_client() as client:
        r = client.get('/-categoryone/feeds/')
        assert r.status_code == 200
        result = json.loads(r.data)
        remove_category_url = result['categories'][0]['remove_category_url']
        r = client.delete(remove_category_url)
        assert r.status_code == 200
        result = json.loads(client.get('/-categoryone/feeds/').data)
        for child in result['categories']:
            assert not child['title'] == 'categorytwo'
        feed_list = FeedList(REPOSITORY + OPML)
        assert len(feed_list[0]) == 1


def test_category_all_entries(xmls):
    with app.test_client() as client:
        r = client.get('/-categoryone/entries/')
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'categoryone'
        assert result['entries'][0]['title'] == 'Feed One: Entry Two'
        entry_url = result['entries'][0]['entry_url']
        r = client.get(entry_url)
        assert r.status_code == 200
        two_result = json.loads(r.data)
        assert two_result['title'] == 'Feed One: Entry Two'
        assert two_result['content'] == \
            'This is content of Entry Two in Feed One'
        assert two_result['updated'] == '2013-10-19 07:49:20+07:00'
        assert two_result['permalink'] == 'http://feedone.com/feed/atom/2/'
        assert two_result['feed']['title'] == 'Feed One'
        assert two_result['feed']['permalink'] == \
            'http://feedone.com'
        feed_id = get_hash('http://feedone.com/feed/atom/')
        assert two_result['feed']['entries_url'] == \
            url_for(
                'feed_entries',
                feed_id=feed_id,
                _external=True
            )
        assert result['entries'][1]['title'] == 'Feed Two: Entry One'
        entry_url = result['entries'][1]['entry_url']
        r = client.get(entry_url)
        assert r.status_code == 200
        one_result = json.loads(r.data)
        assert one_result['content'] == \
            'This is content of Entry One in Feed Two'
        r = client.get('/-categoryone/-categorytwo/entries/')
        assert r.status_code == 200
        result = json.loads(r.data)
        assert result['title'] == 'categorytwo'
        assert result['entries'][0]['title'] == 'Feed Two: Entry One'


def test_empty_category_all_entries(xmls):
    with app.test_client() as client:
        r = client.post('/', data=dict(title='test'))
        assert r.status_code == 200
        r = client.get('/-test/entries/')
        assert r.status_code == 200


@fixture
def xmls_for_next(request):
    opml = '''
    <opml version="1.0">
      <head>
        <title>test opml</title>
      </head>
      <body>
        <outline text="categoryone" title="categoryone">
            <outline type="atom" text="Feed One" title="Feed One"
            xmlUrl="http://feedone.com/" />
            <outline type="atom" text="Feed Two" title="Feed Two"
            xmlUrl="http://feedtwo.com/" />
        </outline>
      </body>
    </opml>
    '''
    authors = [Person(name='vio')]
    feed_one = Feed(id='http://feedone.com/', authors=authors,
                    title=Text(value='Feed One'),
                    updated_at=datetime.datetime(2013, 10, 30, 20, 55, 30,
                                                 tzinfo=utc))
    feed_two = Feed(id='http://feedtwo.com/', authors=authors,
                    title=Text(value='Feed Two'),
                    updated_at=datetime.datetime(2013, 10, 30, 21, 55, 30,
                                                 tzinfo=utc))
    for i in range(25):
        feed_one.entries.append(
            Entry(id='http://feedone.com/' + str(i),
                  authors=authors,
                  title=Text(value='Feed One: Entry ' + str(i)),
                  updated_at=datetime.datetime(2013, 10, 6, 20, 55, 30,
                                               tzinfo=utc) +
                  datetime.timedelta(days=1)*i)
        )
        feed_two.entries.append(
            Entry(id='http://feedtwo.com/' + str(i),
                  authors=authors,
                  title=Text(value='Feed Two: Entry ' + str(i)),
                  updated_at=datetime.datetime(2013, 10, 6, 19, 55, 30,
                                               tzinfo=utc) +
                  datetime.timedelta(days=1)*i)
        )
    feed_list = FeedList(opml, is_xml_string=True)
    feed_list.save_file(os.path.join(REPOSITORY, OPML))
    with open(os.path.join(
            REPOSITORY, get_hash('http://feedone.com/') + '.xml'), 'w+') as f:
        for chunk in write(feed_one, indent='    ',
                           canonical_order=True):
            f.write(chunk)
    with open(os.path.join(
            REPOSITORY, get_hash('http://feedtwo.com/') + '.xml'), 'w+') as f:
        for chunk in write(feed_two, indent='    ',
                           canonical_order=True):
            f.write(chunk)

    def remove_test_repo():
        files = glob.glob(os.path.join(REPOSITORY, '*'))
        for file in files:
            os.remove(file)

    request.addfinalizer(remove_test_repo)


def test_feed_entries_next(xmls_for_next):
    with app.test_client() as client:
        r = client.get('/-categoryone/feeds/' +
                       get_hash('http://feedone.com/') +
                       '/entries/')
        assert r.status_code == 200
        result = json.loads(r.data)
        assert len(result['entries']) == 20
        assert result['entries'][-1]['title'] == 'Feed One: Entry 5'
        r = client.get(result['next_url'])
        assert r.status_code == 200
        result = json.loads(r.data)
        assert len(result['entries']) == 5
        assert result['entries'][-1]['title'] == 'Feed One: Entry 0'
        assert not result['next_url']


def test_category_entries_next(xmls_for_next):
    with app.test_client() as client:
        r = client.get('/-categoryone/entries/')
        assert r.status_code == 200
        result = json.loads(r.data)
        assert len(result['entries']) == 20
        assert result['entries'][-1]['title'] == 'Feed Two: Entry 15'
        r = client.get(result['next_url'])
        result = json.loads(r.data)
        assert len(result['entries']) == 20
        assert result['entries'][-1]['title'] == 'Feed Two: Entry 5'
        r = client.get(result['next_url'])
        result = json.loads(r.data)
        assert len(result['entries']) == 10
        assert result['entries'][-1]['title'] == 'Feed Two: Entry 0'
