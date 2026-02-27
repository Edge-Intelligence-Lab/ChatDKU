# DKU Website Scraper

## Usage

Install Python 3.9 or above; install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\Scripts\activate.bat    # For Windows
```

Do an editable install with pip to get the dependencies.
```bash
pip install -e .
```

It might be necessary to increase the OS limit on the number of file descriptors as
this script opens a lot of files:
```bash
ulimit -n 100000 # Set this to at most the output of "ulimit -n -H"
```

Run the script with no arguments to scrape `https://www.dukekunshan.edu.cn/`
recursively with some reasonable defaults:
```bash
./scraper.py
```
The output directory would be created with the structure:
```bash
./dku_website/domain/path
```
The infomation and download status about the URLs visited is stored in
`./progress.pkl`.

For a detailed description of the arguments, run
```bash
./scraper.py -h
```

To get detailed information about all URLs visited from the progress file, run
```bash
./report.py progress.pkl
```
Alternatively, just to get an overall summary:
```bash
./report.py -s progress.pkl
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
biggest issue is that it can only download one resource at a time. A global task
group is maintained, so that for each URL on the current page, a recursive scraping
task would be enqueued for that URL. For failed scraping tasks, they would be
reenqued after some delay calculated using exponential backoff.

The status of the URLs visited (downloading, success, failed) are kept in a map so
that:
1. No URL would be visited twice.
2. A report of what URLs have being successfully downloaded or not could be
   generated.
3. Incomplete downloads could be continued _(to be implemented in the future)_.

A background task of printing out the scraping progress would be run periodically,
listing the number of currently visited URLs in each status category.

A global delay between initiating each request is applied as I had downed the DKU
website briefly without it.

Note that SSL certificate verification is disabled as I got some errors with it
on, yet my browser did not complain. This is a security risk, but I left it on
for now.

`index.html` would be added to webpages without `.html` nor `.htm`
extension.

The last part of the path (ignoring `index.html` if that is
added automatically) would be broken up into chunks if it is too long, as it
might exceed the filename length limit of the file system.
