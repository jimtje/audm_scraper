# Audm Scraper
![Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue) ![GitHub](https://img.shields.io/github/license/jimtje/audm_scraper)

This script will download and join all segments that make up each story as read and available on the [Audm](https://www.audm.com/) app.

## Installation

Tested on python 3.6+

### Prerequisites:
####  1. ffmpeg

```bash
brew install ffmpeg
```
or
```bash
sudo apt-get install ffmpeg
```
#### 2. taglib
```bash
brew install taglib
```
or
```bash
sudo apt-get install libtag1-dev
```
#### 3. Requirements

```bash
pip3 install -r requirements.txt
```

## Configuration

```bash
cp config.cfg.example config.cfg
```
Add in your Audm username and password into config.cfg

## Run

```bash
python3 audm_scraper.py
```
Audio files are saved to output/{publication name}/ by default.

## Licensing
This project is licensed under Unlicense license. This license does not require you to take the license with you to your project.

