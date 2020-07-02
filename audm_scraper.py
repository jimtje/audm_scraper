import configparser
import os
import shutil

import requests
from mutagen.mp4 import MP4, MP4Cover, MP4Tags
import dataset
from alive_progress import alive_bar
import arrow

config = configparser.RawConfigParser()
with open("config.cfg", "r") as cfg:
    config.read_file(cfg)
username = config.get("logins", "username")
password = config.get("logins", "password")

os.makedirs("output", exist_ok=True)
db = dataset.connect("sqlite:///output/files.db")


class AudmException(BaseException):
    pass


class InvalidLogin(AudmException):
    pass


class Audm(object):

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"user-agent": "okhttp/3.12.0"})
        self.session_token = None
        self.user_id = None
        self._login()

    def _login(self):
        url = "https://api.audm.com/v5/auth/login"
        payload = {"email": self.username, "password": self.password}
        r = self.session.post(url, json=payload)
        if r.status_code == 200:
            self.session_token = r.json()["result"]["session_token"]
            self.user_id = r.json()["result"]["user_id"]
            self.session.headers.update({"X-PARSE-SESSION-TOKEN": self.session_token})
        elif r.status_code == 401:
            raise InvalidLogin

    def _get_signed_cookies(self):
        url = "https://api.audm.com/v5/auth/get-cloudfront-signed-cookies"
        r = self.session.get(url)
        cookies = r.json()["result"]["cookies-text"]
        c = cookies.split("Cookie: ")
        hd = {}
        for each in c[1:]:
            each = each.strip()
            e = each.split("=")
            hd[e[0]] = e[1]
        return hd

    def filters(self):
        url = "https://api.audm.com/v3/filter-options/all"
        r = self.session.post(url)
        return r.json()["result"]

    def articles(self, publication_ids=[], narrator_names=[], author_names=[]):
        payload = {
                "publication_ids": publication_ids, "ordering": "byAudmDateDesc", "narrator_names": narrator_names,
                "author_names": author_names
        }
        url = "https://api.audm.com/v2/prefetchMinimumDiscoverScreenDataForArticleList"
        r = self.session.post(url, json=payload)
        return r.json()["result"]

    def articlepreviews(self, article_version_ids=[]):
        payload = {"article_version_ids": article_version_ids}
        url = "https://api.audm.com/v2/fetchPreviewDataForAVsWithIDs"
        r = self.session.post(url, json=payload)
        return r.json()["result"]

    def paragraphs(self, article_version_ids=[]):
        payload = {"article_version_ids": article_version_ids}
        url = "https://api.audm.com/v2/paragraphsForAVsWithIDs"
        r = self.session.post(url, json=payload)
        return r.json()["result"]

    def get_file(self, filename):
        cookies = self._get_signed_cookies()
        url = "https://dxtq18gq89iho.cloudfront.net/"
        headers = {"user-agent": "okhttp/3.12.0"}
        r = requests.get(url + filename, cookies=cookies, headers=headers)
        return r


def main():
    audm = Audm(username, password)
    # This grabs the filtering options available. Filtering is first done by narrator, publication, or author.
    filters = audm.filters()
    publication_counter = 1
    totalpublications = len(filters["publications"])
    for eachpublication in filters["publications"]:
        publication_name = eachpublication["name_full"]


        print("Publication: " + publication_name + " " + str(publication_counter) + "/" + str(totalpublications))
        publication_counter += 1

        # I've found it way easier to sort by publication first
        # publications_dir = os.path.abspath("output/" + eachpublication["name_full"])
        # os.makedirs(publications_dir, exist_ok=True)

        articles = audm.articles(publication_ids=[eachpublication["object_id"]])
        article_ids = []
        # With the article_ids, it's then possible to get the full metadata on each article.
        for i in articles["article_versions"]:
            article_ids.append(i["object_id"])

        t = audm.articlepreviews(article_ids)
        num_articles = len(t["article_versions"])
        counter = 1
        for article in t["article_versions"]:
            files = []
            article_text = []
            article["publication_name"] = publication_name
            article_title = article["title"]
            author = article["author_name"].replace('"', '')
            pubdate = arrow.get(article["pub_date"])
            article_text_string = ""
            eventual_outfile = os.path.join("output",
                                            pubdate.format('YYYY-MM-DD') + "-" + publication_name + "-" + article[
                                                "short_name"] + ".m4a")
            illegal_char = ("?", "'", '"', "*", "^", "%", "$", "#", "~", "<", ">", ",", ";", ":", "|",)
            for char in illegal_char:
                eventual_outfile = eventual_outfile.replace(char, "")




            if db["articles"].find_one(object_id=article["object_id"]) == None:

                if not os.path.exists(eventual_outfile):

                    print("Article: " + article_title + " by " + author + " " + str(counter) + "/" + str(num_articles))
                    p = audm.paragraphs([article["object_id"]])
                    os.makedirs("output/" + article["short_name"], exist_ok=True)


                    # Articles are split up by paragraph and there can be quite a few. Although they are numbered and
                    # timestamped, makes more sense to join them
                    with alive_bar(len(p), force_tty=True) as filebar:
                        for f in p:
                            file = audm.get_file(f["audio_filename"])
                            filename = os.path.join("output", article["short_name"] + "/" + f["audio_filename"])
                            with open(filename, "wb") as fz:
                                fz.write(file.content)
                                files.append({"filename": filename, "index": f["index"]})
                                article_text.append({"index": f["index"], "text": f["text"]})
                            filebar()
                    fo = sorted(files, key=lambda i: i['index'])
                    textfo = sorted(article_text, key=lambda i: i['index'])

                    for part in textfo:
                        article_text_string += part["text"] + "\n"
                    db["article_text"].insert_ignore(
                            {"publication": article["publication_name"], "title": article_title, "author": author, "pubdate": pubdate.timestamp, "object_id": article["object_id"], "text": article_text_string}, ["object_id"])
                    # Temporary file to enable ffmpeg to demux and concat the m4a files
                    tempfile = os.path.join("output/" + article["short_name"], "templist.txt").replace("'","'\\''")

                    with open(tempfile, "a") as listf:

                        for fn in fo:
                            listf.write("file '" + os.path.abspath(fn["filename"]) + "'\n")
                            # -nostats -loglevel 0

                    concat_command = f"ffmpeg -nostats -loglevel 0 -y -f concat -safe 0 -i \"{tempfile}\" -c copy \"" \
                                     f"{eventual_outfile}\""
                    os.system(concat_command)
                    # Tagging
                    shutil.rmtree("output/" + article["short_name"])
                    counter += 1
                    db["articles"].upsert({"publication": article["publication_name"], "title": article_title, "author": author, "pubdate": pubdate.timestamp, "narrator": article["narrator_name"], "description": article["desc"], "object_id": article["object_id"], "file_path": eventual_outfile}, ["object_id"])
                    audio = MP4(eventual_outfile)
                    audio.delete()
                    try:
                        audio.add_tags()
                    except:
                        pass
                    image = audm.get_file(article["img_lock_2x"])
                    audio["covr"] = [MP4Cover(data=image.content, imageformat=MP4Cover.FORMAT_PNG)]

                    audio['\xa9nam'] = article_title
                    audio['\xa9alb'] = publication_name
                    audio['\xa9ART'] = author
                    audio['\xa9wrt'] = article["narrator_name"]
                    audio['\xa9day'] = pubdate.format('YYYY-MM-DD')
                    audio['desc'] = article["desc"]

                    audio.save()
                    # Cleanup

                else:
                    print(article_title + " by " + author + " file exists, skipping article." + " " + str(
                        counter) + "/" + str(num_articles))
                    counter += 1
            else:
                print(article_title + " by " + author + " already downloaded, skipping article." + " " + str(counter) + "/" + str(num_articles))
                counter += 1


if __name__ == '__main__':
    main()