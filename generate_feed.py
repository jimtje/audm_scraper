from b2sdk.v1 import B2Api, InMemoryAccountInfo, ScanPoliciesManager, parse_sync_folder, Synchronizer, NewerFileSyncMode, SyncReport, CompareVersionMode, KeepOrDeleteMode
from podgen import Podcast, Category, Episode, Media, Person, htmlencode
import time
import sys
from backports.zoneinfo import ZoneInfo
import datetime
import dataset
import configparser
from github import Github
from stuf import stuf

config = configparser.RawConfigParser()
with open("config.cfg", "r") as cfg:
    config.read_file(cfg)

db = dataset.connect("sqlite:///output/files.db", row_type=stuf)

application_key = config.get("logins", "backblazekey")
application_secret = config.get("logins", "backblazesecret")
bucketname = config.get("logins", "backblazebucket")
githubtoken = config.get("logins", "githubtoken")
b2 = B2Api(InMemoryAccountInfo())
b2.authorize_account("production", application_key, application_secret)
source = 'output'
destination = 'b2://' + bucketname
source = parse_sync_folder(source, b2)
destination = parse_sync_folder(destination, b2)
policies_manager = ScanPoliciesManager(exclude_all_symlinks=True)
synchronizer = Synchronizer(
        max_workers=10,
        policies_manager=policies_manager,
        dry_run=False,
        allow_empty_source=True,
compare_version_mode=CompareVersionMode.SIZE,
compare_threshold=100,
newer_file_mode=NewerFileSyncMode.SKIP,
keep_days_or_delete=KeepOrDeleteMode.DELETE
    )
no_progress = False
with SyncReport(sys.stdout, no_progress) as reporter:
    synchronizer.sync_folders(source_folder=source, dest_folder=destination, now_millis=int(round(time.time() * 1000)),
            reporter=reporter)

p = Podcast()

p.name = 'Audm Feed'
p.explicit = False
p.language = "en-US"
p.website = "https://www.audm.com"
p.description = "Audm"
p.category = Category("News")
bk = b2.get_bucket_by_name(bucketname)
for i in bk.ls(recursive=True):
    if i[0].as_dict()["fileName"].endswith(".m4a"):
        fn = i[0].as_dict()["fileName"]
        print(fn)
        article = db["articles"].find_one(file_path="output/" + fn)
        fe = p.add_episode()
        downloadurl = bk.get_download_url(i[0].as_dict()['fileName'])
        imageurl = bk.get_download_url(i[0].as_dict()['fileName'].rsplit('.', 1)[0] + '.png')
        size = i[0].as_dict()["size"]
        fe.media = Media(downloadurl, size=size)
        fe.title = article.title + " by " + article.author + " (" + article.publication + ")"
        fe.subtitle = article.publication + ": " + article.title
        pubdate = datetime.datetime.fromtimestamp(article.pubdate).replace(tzinfo=ZoneInfo('UTC'))
        fe.publication_date = pubdate
        fe.summary = "By: " + article.author + "\n" + article.publication + "\nNarrated by: " + article.narrator + "\n" + article.description
        fe.authors = [Person(article.author), Person(article.publication)]
        fe.image = imageurl

p.rss_file('podcast.xml')
g = Github(githubtoken)
user = g.get_user()
gists = user.get_gists()
gist_updated = False
for gist in gists:
    if "podcast.xml" in gist.files.keys():
        with open("podcast.xml") as fd:
            t = fd.read()
        gist.edit(files={"podcast.xml": t})
        gist_updated = True
if not gist_updated:
    with open("podcast.xml") as fd:
        t = fd.read()
    user.create_gist(True, {"podcast.xml", t})

