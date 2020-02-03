# gdrive2onedrive
Utility to backup your Google Drive data to Micosoft OneDrive

## This utility is licensed under MIT license

## Note:
1. Files are downloaded from _Google Drive_ to your local machine and then uploaded to your _Microsoft OneDrive_
2. If a Google doc file is greater than 10 MB in size, it can't be exported (a limitation imposed by Google)
  a. A download link is given for such files
  b. You need to be logged into your Google account for the link to work
 
 ## Dependencies
To install the dependencies run:
python3 -m pip install google-api-python-client==1.7.11 google-auth==1.11.0 google-auth-httplib2==0.0.3 google-auth-oauthlib==0.4.1
