from b2sdk.v1 import B2Api, InMemoryAccountInfo, ScanPoliciesManager, parse_sync_folder, Synchronizer, NewerFileSyncMode, SyncReport, CompareVersionMode, KeepOrDeleteMode
from feedgen.feed import FeedGenerator
import time
import sys
from backports.zoneinfo import ZoneInfo
import datetime
import dataset
import configparser
from stuf import stuf
config = configparser.RawConfigParser()
with open("config.cfg", "r") as cfg:
    config.read_file(cfg)

db = dataset.connect("sqlite:///output/files.db", row_type=stuf)

application_key = config.get("logins", "backblazekey")
application_secret = config.get("logins", "backblazesecret")
bucketname = config.get("logins", "backblazebucket")
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

fg = FeedGenerator()
fg.load_extension('podcast', atom=True, rss=True)
fg.title('Audm Feed')
fg.language('en')
fg.podcast.itunes_category('News')

bk = b2.get_bucket_by_name(bucketname)
for i in bk.ls(recursive=True):
    if i[0].as_dict()["fileName"].endswith(".m4a"):
        fn = i[0].as_dict()["fileName"]
        article = db["articles"].find_one(file_path="output/" + fn)
        fe = fg.add_entry()
        downloadurl = bk.get_download_url(i[0].as_dict()['fileName'])
        imageurl = bk.get_download_url(i[0].as_dict()['fileName'].rsplit('.', 1)[0] + '.png')
        fe.id(downloadurl)
        fe.title(article.title)
        fe.podcast.itunes_author(article.author)
        fe.podcast.itunes_subtitle(article.publication + ": " + article.title)
        pubdate = datetime.datetime.fromtimestamp(article.pubdate).replace(tzinfo=ZoneInfo('UTC'))
        fe.published(pubdate)
        fe.description(article.album + "\nnarrated by: " + article.narrator + "\n" + article.description)
        fe.author(article.author)
        fe.enclosure(downloadurl, 0, 'audio/x-m4a')
        fe.podcast.itunes_image(imageurl)
fg.rss_str(pretty=True)
fg.rss_file('podcast.xml')
