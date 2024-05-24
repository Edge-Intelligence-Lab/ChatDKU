# DKU Website Crawler

## Usage

Install Python 3.8 or above; install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\bin\activate.bat    # For Windows
```

Do an editable install with pip to get the dependencies.
```bash
pip install -e .
```

It might be necessary to increase the OS limit on the number of file descriptors as this script opens a lot of files:
```bash
ulimit -n 100000 # Set this to at most the output of "ulimit -n -H"
```

Run the script:
```bash
./dku_site_crawler.py
```
The directory `./dku_website` would be created with the structure:
```bash
./dku_website/domain/path
```

## About

This script uses `BeautifulSoup` to extract the hyperlinks in HTML pages and
recursively follow them in order to scrape the entire DKU website. The
hyperlinks on webpages outside of the domain `dukekunshan.edu.cn` would not be
followed, though these non-DKU webpages themselves would be included as they are
referenced by the DKU website. The original intention is to not exclude
externally stored static resources, but I currently also include external
webpages as leaf nodes.

The recursive scraping function is implemented as an `asyncio` coroutine in order
to speed up the process. I originally tried to simply use `wget` and its
biggest issue is that it can only download one resource at a time.

A retry package for `aiohttp` is used to make scraping more robust as the
crawler should not stop upon the first failure of loading a resource.

A random delay is applied before starting recursive crawling as I downed the DKU
website briefly without it.

Note that SSL certificate verification is disabled as I got some errors with it
on, yet my browser did not complain. This is a security risk, but I left it on
for now.

`index.html` would be added to webpages without `.html` or `.htm`
extension.

The last part of the path (ignoring `index.html` if that is
added automatically) would be broken up into chunks if it is too long, as it
might exceed the filename length limit of the file system.
