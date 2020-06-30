import configparser
import os
import shutil

import requests
import taglib
from alive_progress import alive_bar

config = configparser.RawConfigParser()
with open("config.cfg", "r") as cfg:
    config.read_file(cfg)
username = config.get("logins", "username")
password = config.get("logins", "password")


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

    for eachpublication in filters["publications"]:
        print("Publication: " + eachpublication["name_full"])

        # I've found it way easier to sort by publication first
        publications_dir = os.path.abspath("output/" + eachpublication["name_full"])
        os.makedirs(publications_dir, exist_ok=True)

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
            article["publication_name"] = eachpublication["name_full"]


            eventual_outfile = os.path.join(publications_dir,
                                            article["short_name"] + "-" + article["author_name"] + "-" + article[
                                                "pub_date"] + ".m4a").replace("'", "'\\''")
            if not os.path.exists(eventual_outfile):
                print("Article: " + article["title"] + " by " + article["author_name"] + " " + str(counter) + "/" + str(num_articles))
                p = audm.paragraphs([article["object_id"]])
                os.makedirs(publications_dir + "/" + article["short_name"], exist_ok=True)

                # Articles are split up by paragraph and there can be quite a few. Although they are numbered and
                # timestamped, makes more sense to join them
                with alive_bar(len(p), force_tty=True) as filebar:
                    for f in p:
                        file = audm.get_file(f["audio_filename"])
                        filename = publications_dir + "/" + article["short_name"] + "/" + f["audio_filename"]
                        with open(filename, "wb") as fz:
                            fz.write(file.content)
                            files.append({"filename": filename, "index": f["index"]})
                        filebar()
                fo = sorted(files, key=lambda i: i['index'])
                # Temporary file to enable ffmpeg to demux and concat the m4a files
                tempfile = os.path.join(publications_dir + "/" + article["short_name"], "templist.txt").replace("'",
                                                                                                                "'\\''")

                with open(tempfile, "a") as listf:

                    for fn in fo:
                        sanitized_file = fn["filename"].replace("'", "'\\''")
                        listf.write("file '" + sanitized_file + "'\n")

                concat_command = f"ffmpeg -nostats -loglevel 0 -y -f concat -safe 0 -i \"{tempfile}\" -c copy \"" \
                                 f"{eventual_outfile}\""
                os.system(concat_command)
                # Tagging
                audio = taglib.File(eventual_outfile)
                audio.tags["PERFORMER"] = article["narrator_name"]
                audio.tags["ARTIST"] = article["author_name"]
                audio.tags["TITLE"] = article["title"]
                audio.tags["ALBUM"] = article["publication_name"]
                audio.tags["DATE"] = article["pub_date"]
                audio.tags["DESCRIPTION"] = article["desc"]
                audio.save()
                # Cleanup
                shutil.rmtree(publications_dir + "/" + article["short_name"])
                counter += 1
            else:
                print(article["title"] + " by " + article["author_name"] + " already downloaded, skipping article." + " " + str(counter) + "/" + str(num_articles))
                counter += 1


if __name__ == '__main__':
    main()