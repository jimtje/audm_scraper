import requests
import os
import taglib
import shutil
import configparser

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
        payload = {"publication_ids":publication_ids,"ordering":"byAudmDateDesc","narrator_names":narrator_names,"author_names":author_names}
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

        # I've found it way easier to sort by publication first
        publications_dir = os.path.abspath("output/" + eachpublication["name_full"])
        os.makedirs(publications_dir, exist_ok=True)

        articles = audm.articles(publication_ids=[eachpublication["object_id"]])
        article_ids = []
        # With the article_ids, it's then possible to get the full metadata on each article.
        for i in articles["article_versions"]:
            article_ids.append(i["object_id"])

        t = audm.articlepreviews(article_ids)
        for article in t["article_versions"]:
            files = []
            article["publication_name"] = eachpublication["name_full"]

            print(article)

            os.makedirs(publications_dir + "/" + article["short_name"], exist_ok=True)
            p = audm.paragraphs([article["object_id"]])
            # Articles are split up by paragraph and there can be quite a few. Although they are numbered and timestamped, makes more sense to join them
            for f in p:
                file = audm.get_file(f["audio_filename"])
                filename = publications_dir + "/" + article["short_name"] + "/" + f["audio_filename"]
                with open(filename, "wb") as fz:
                    fz.write(file.content)
                    files.append({"filename": filename, "index": f["index"]})
            fo = sorted(files, key = lambda i: i['index'])
            # Temporary file to enable ffmpeg to demux and concat the m4a files
            tempfile = os.path.join(publications_dir + "/" + article["short_name"], "templist.txt").replace("'", "'\\''")

            eventual_outfile = os.path.join(publications_dir, article["short_name"] + "-" + article["author_name"] + "-" + article["pub_date"] + ".m4a").replace("'", "'\\''")

            with open(tempfile, "a") as listf:
                for fn in fo:
                    sanitized_file = fn["filename"].replace("'", "'\\''")
                    print(sanitized_file)
                    listf.write("file '" + sanitized_file + "'\n")

            concat_command = f"ffmpeg -nostats -loglevel 0 -y -f concat -safe 0 -i \"{tempfile}\" -c copy \"{eventual_outfile}\""
            os.system(concat_command)
            # Tagging
            audio = taglib.File(eventual_outfile)
            audio.tags["PERFORMER"] = article["narrator_name"]
            audio.tags["ARTIST"] = article["author_name"]
            audio.tags["TITLE"] = article["title"]
            audio.tags["ALBUM"] = article["publication_name"]
            audio.tags["DATE"] = article["pub_date"]
            audio.tags["DESCRIPTION"] = article["desc"]
            print(audio.tags)
            audio.save()
            # Cleanup
            shutil.rmtree(publications_dir + "/" + article["short_name"])

if __name__ == '__main__':
    main()