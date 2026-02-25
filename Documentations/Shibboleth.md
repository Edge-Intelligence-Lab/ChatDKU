# Manual for ChatDKU's Shibboleth implementation

Duke provides ChatDKU with Shibboleth-based user authentication to verify that the user is affiliated with Duke/DKU.

You may visit https://authentication.oit.duke.edu/manager to view/manage what Shibboleth provides for ChatDKU.

On our server side, Shibboleth routing is confugured in the Apache confs, specifically at `/etc/apache2/sites-available/chatdku-ssl.conf`.

> Please **do not edit** the apache confs without backing up the files you're changing. The `rsync` command is recommneded for backup creation & restoration.

Shibboleth also provides user attributes that we can use for access control, such as NetID, full name, and Duke affiliation type.
