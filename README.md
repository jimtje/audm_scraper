# Audm Scraper
![Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue) ![GitHub](https://img.shields.io/github/license/jimtje/audm_scraper)

Tested on MacOS and Ubuntu.

This is a quick way to grab all of the audio from Audm, join, and tag the output audio file, categorized by publication. The code is commented but largely self-explanatory. I think audm has a great service and really fills in a void that isn't necessarily covered by most podcasts, but the app is terrible, with lackluster search features, and no way of either playing the files on a desktop or through an RSS feed, which I'd prefer.

## Quickstart

### Prerequisites:

* ffmpeg
```
brew install ffmpeg
```
* Taglib
```
brew install taglib
```

### Configuration

Start by renaming config.cfg.example to config.cfg and adding your Audm account credentials to the file.

Then, install requirements.
```
pip install -r requirements.txt
```
And that's it, off you go.
```
python audm_scraper.py
```
Audio files are saved to output/[:publication name]/ by default.

### Licensing
This project is licensed under Unlicense license. This license does not require you to take the license with you to your project.

