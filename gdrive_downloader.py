"""
Download all the files from your Google Drive (including files shared with you with download access)

TODO: Get the ID of 'My Drive' - done
TODO: Check if the files shared WITH me are being downloaded - done
TODO: Create directory structure - done
TODO: Create another folder for files 'Shared With Me' - done
TODO: Remove the files that have a size of 0 (zero) - done
TODO: Get the size and md5checksum of the files - done
TODO: Store the data in a local csv file - done
TODO: Verify the md5checksum of the files - done # verification going on for files for which md5 is provided by google
TODO: handle Google files that are larger than 10 MB - done
TODO: Implement logging
TODO: Multithreading for parallel downloading of files
"""


import pickle
import io
import os
import os.path
from pprint import pprint
import datetime
import hashlib
import uuid
import logging
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient import errors

log_file_name = 'gDriveDownload.log'

root_logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)

logging.basicConfig(
    filename=os.getcwd() + "/" + log_file_name, 
    level=logging.INFO, 
    format='%(asctime)s %(message)s'
)

root_logger.addHandler(handler)

# Defines the scope this app has access to
# Following scope gives full access to one's drive
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Mimetypes for google docs and their corresponding export mimetypes
MIMES = {'application/vnd.google-apps.document' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.google-apps.presentation' : 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.google-apps.spreadsheet' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            'application/vnd.google-apps.script' : 'application/vnd.google-apps.script+json', 
            'default' : 'application/pdf'}

# File extensions according to mimetypes
EXPORTED_FORMAT = {'application/vnd.google-apps.document' : 'docx',
            'application/vnd.google-apps.presentation' : 'pptx',
            'application/vnd.google-apps.spreadsheet' : 'xlsx', 
            'application/vnd.google-apps.script' : 'json', 
            'default' : 'pdf'}

def authenticate():
    """
    Authentication section, don't modify 
    Taken from official google getting started guide
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

def sanitize_name(filename):
    """
    Removes characters not supported as filename on Windows platform

    Returns: a sanitized filename
    """
    logging.info("Sanitizing filename {0}".format(filename['name']))
    invalid_chars = ['\\', '/', '<', '>', ':', '"', '|', '?', '*', '\'']
    replace_char = '_'
    filename['name'] = filename['name'].strip()
    for char in invalid_chars:
        if char in filename['name']:
            filename['name'] = filename['name'].replace(char, replace_char)
    return filename['name']

def find_parent(service, file_id):
    """
    Returns the ID of the parent folder
    """
    ret_val = service.files().get(fileId=file_id, fields="id, name, parents").execute()
    if 'parents' in ret_val.keys():
        logging.info("ID of the parent folder is {0}".format(ret_val['parents']))
    else:
        logging.warning("No parent ID for file id {0}".format(file_id))
    return ret_val


def export_assistant(service, filename, mimeType, folder_path, exportedFormat, successType):
    data = service.files().export_media(fileId=filename['id'], mimeType=mimeType).execute()
    if data:
        filename['name'] = sanitize_name(filename)
        logging.info('Sanitized filename is {0}'.format(filename['name']))
        fn = folder_path + '/' + filename['name'] + '.' + exportedFormat
        with open(fn, 'wb') as fh:
            fh.write(data)
    logging.info("File {0} exported successfully".format(filename['name']))


def download_file(service, filename, folder_path, mimeType='', successType='success', exportedFormat=None):
    """
    Download the given file id to the given folder_path with the given mimetype

    mimeType for the binary files is None
    """
    if folder_path == None:
        folder_path = os.getcwd() + '/' + 'My Drive'

    # TODO: Implement file existence check in the calling function; check in the file with ID
    # TODO: If the file is different with same name, create new name and then call this function

    try:
        logging.info("Attempting binary download")
        data_bytes = service.files().get_media(fileId=filename['id'])
        filename['name'] = sanitize_name(filename)
        logging.info("Sanitized filename is {0}".format(filename['name']))
        fh = io.FileIO(folder_path + '/' + filename['name'], mode='wb')
        downloader = MediaIoBaseDownload(fh, data_bytes)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            if status:
                pass
        fh.close()

        logging.info("Binary download successful for filename {0}, file id: {1}".format(filename['name'], filename['id']))

    except:
        if fh:
            fh.close()
        try:
            logging.info('Attempting to remove zero size file {0}'.format(filename['name']))
            if os.stat(folder_path + '/' + filename['name']).st_size == 0:
                os.remove(folder_path + '/' + filename['name'])
                logging.info("File {0} successfully removed".format(filename['name']))

        except Exception as e:
            logging.info("Error in removing zero size file {0}".format(filename['name']))
            logging.error(str(e))

        try:
            logging.info("Attempting to export the file")
            export_assistant(service, filename, mimeType, folder_path, exportedFormat, successType)
        except Exception as e:
            logging.error("Failed to download or export the file {0}, id = {1}".format(filename['name'], filename['id']))
            logging.error(e)


def create_folder(filename, root_id, service, filetype=0):
    """
    Creates folder(s) if it doesn't exist
    """
    # If the folder parent is root, create a sub-dir in root dir

    if 'parents' in filename.keys():
        if filename['parents'][0] == root_id['id']:
            if filetype == 1:
                folder_path = os.getcwd() + '/' + root_id['name']
            else:
                folder_path = os.getcwd() + '/' + root_id['name'] + '/' + filename['name']
            if not os.path.exists(folder_path):
                logging.info("Creating folder {0}".format(folder_path))
                os.makedirs(folder_path)
                print(folder_path)
                logging.info("Folder created - {0}".format(folder_path))

        # If the folder parent is not root, traceback all the subdirs to root and then create the path
        elif filename['parents'][0] != root_id['id']:
            parents_list = [filename['name']]
            parent_id = filename['parents'][0]
            a = find_parent(service, parent_id)
            parents_list.append(a['name'])
            while 'parents' in a.keys():
                parent_id = a['parents'][0]
                a = find_parent(service, parent_id)                
                parents_list.append(a['name'])
                
            parents_list.reverse()

            if root_id['name'] in parents_list:
                print(parents_list)
                folder_path = os.getcwd()
            else:
                folder_path = os.getcwd() + '/Shared With Me/'

            if filetype == 1:
                folder_path = folder_path + '/'.join(parents_list[:-1])
            else:
                folder_path = folder_path + '/'.join(parents_list)
            if not os.path.exists(folder_path):
                logging.info("Creating folder {0}".format(folder_path))
                os.makedirs(folder_path)
                print(folder_path)
                logging.info("Folder created - {0}".format(folder_path))
    else:
        # If the file doesn't have a parent for some reason, put it in root folder
        logging.warning("No parent found for the file")
        logging.info("Putting the file in root directory")
        folder_path = os.getcwd() + '/' + root_id['name']
    return folder_path

def loop_through_files(token, result, service, root_id):
    """ 
    This function loops through all of the files in the Google Drive trying to download each one
    """


    while token:
        for filename in result['files']:
            # Things to do if the file is a folder    
            if filename['mimeType'] == 'application/vnd.google-apps.folder':
                logging.info('Creating folder as the mimetype is folder')
                logging.info(', '.join(str(x) for x in filename.values()))
                create_folder(filename, root_id, service)

            # Things to do otherwise
            else:
                try:
                    logging.info('Attempting to export')
                    logging.info(', '.join(str(x) for x in filename.values()))
                    # For Google Drive files
                    file_id = filename['id']
                    parent_id = find_parent(service, file_id)
#                    print("BLAH BLAH BLAH {0}, {1} \n {2}".format(type(parent_id), parent_id, parent_id['parents']))
                    if parent_id and 'parents' in parent_id.keys():
                        if parent_id['parents'][0] != root_id['id']:
                            folder_path = create_folder(filename, root_id, service, filetype=1)
                        else:
                            folder_path = os.getcwd() + '/My Drive'
                    else:
                        folder_path = os.getcwd() + '/My Drive'
                    try:
                        if filename['mimeType'] in MIMES.keys():
                            mimeType = MIMES[filename['mimeType']]
                            exported_format = EXPORTED_FORMAT[filename['mimeType']]
                        else:
                            mimeType = 'application/pdf'
                            exported_format = 'pdf'
                        download_file(service, filename, folder_path, mimeType, successType='success', exportedFormat=exported_format)
                    except Exception as e:
                        logging.error("Download of " + filename['name'] + " failed")
                        logging.error(e)
                except:
                    # For binary files
                    logging.info('Trying binary download...')
                    file_id = filename['id']
                    parent_id = find_parent(service, file_id)
                    if parent_id:
                        if parent_id['parents'][0] != root_id['id']:
                            folder_path = create_folder(filename, root_id, service, filetype=1)
                    else:
                        folder_path = os.getcwd() + '/My Drive/'
                    download_file(service, filename, folder_path, None, successType='binarySuccess')
                    logging.info(', '.join(str(x) for x in filename.values()))

        logging.info("Getting new list of files")
        result = service.files().list(fields="files(id, name, mimeType, parents, md5Checksum), nextPageToken", pageToken=token).execute()
        token = result['nextPageToken']

def main():
    # Authenticate and build the service
    logging.info('Starting authentication')
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    logging.info('Authentication successful')

    # Find the ID of the root directory ('My Drive'), create it and cd to it
    logging.info('Getting the ID of the root directory')
    root_id = service.files().get(fileId="root", fields="id, name, mimeType").execute()
    logging.info('ID of the root directory is {0}'.format(root_id))

    if not os.path.exists(os.getcwd() + '/' + root_id['name']):
        logging.info('Creating root directory')
        os.mkdir(root_id['name'])
    else:
        logging.info('Root directory exists')
        
    token = ''
    result = service.files().list(fields="files(id, name, mimeType, parents, md5Checksum), nextPageToken", pageToken=token).execute()
    
    initial_values = (result['nextPageToken'], result)
    loop_through_files(initial_values[0], initial_values[1], service, root_id)

if __name__ == "__main__":
    main()