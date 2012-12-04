cardsync
========

Sync Oracle CommSuite Adressbook to carddav server davical

As far as the Oracle davserver do not support carddav this script is intend
to use for sync the CommSuite Addressbook to the davserver 
Davical http://www.davical.org 
For continuous syning on the LDAP server have to enable the 'Retro Change Log'
Plugin.

Initial Sync can do with:
$ cardsync -i <username>
The user must created before in davical with the davical admintool.

For continuous sync add a line in crontab like:
0 * * * * cardsync -u

Limitations:
At the moment no syncing back to the CommSuite Addressbook and no deletion of vcards.
