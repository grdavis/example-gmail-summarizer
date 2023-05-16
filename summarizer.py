import os.path
import os
import openai
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

'''
Following guidance from https://developers.google.com/workspace/guides/get-started and
https://developers.google.com/gmail/api/quickstart/python, I completed the following steps:
 - created a Google Cloud project
 - enabled the gmail API
 - configured OAuth consent screen and added the 'modify' gmail scope
 - added only my personal email as a test user
 - created and downloaded OAuth client ID credentials as credentials.json

Then, by modifying guidance from https://ericmjl.github.io/blog/2023/3/29/a-developer-first-guide-to-llm-apis-march-2023/
and https://platform.openai.com/docs/quickstart, I used OpenAIs API to summarize a selected subset of emails
from my inbox.
'''

#EMAIL SEARCH PARAMETERS
#which email address(es) are we looking for emails from?
ADDRESSES = [] #e.g. 'sports@mail.morningconsult.com'
#what date range should we look for emails? (easier to specify a small range for testing)
AFTER = '' #e.g. 2023/05/10
BEFORE = '' #e.g. 2023/05/12

#stored OpenAI key in a file called .env (not included in repo)
openai.api_key_path = '.env'

#INSTRUCTIONS FOR GPT
GPT_INSTRUCTIONS = '''You are my virtual assistant. Your objective is to summarize the contents of emails.

Here are a few examples of summarized stories:
1. The scene at the border as the immigration restriction known as Title 42 expires was one of resolve, uncertainty and waiting.
2. Turkey’s president, Recep Tayyip Erdogan, has concentrated government power to tilt tomorrow’s elections to his advantage. He could still lose.
3. The Chinese government has targeted consulting and advisory firms with foreign ties through raids and arrests, reigniting concerns about doing business in China.
4. Legislators and regulators (are tightening oversight of the gambling industry.'''


# I set up my Google project with the scope to 'modify' my email, which includes privileges to read
# and send (maybe I will mark the summarized emails as read and send the summaries back to myself 
# as an email in the future)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def setup():
    '''
    Handles the authentication and authorization steps for gmail then returns the built service
    '''
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    return build('gmail', 'v1', credentials=creds)

def message_collection(service):
    '''
    Queries my gmail inbox for message ids meeting the criteria specified by the ADDRESSES, AFTER, 
    and BEFORE variables. Then, after identifying those message ids, grab the text of those
    messages, clean it up be decoding and removing links before return a list containing 
    the cleaned text of these messages
    '''
    
    # Get the messages from inbox where the sender is in the list of target ADDRESSES
    # the results will be a list of dictionaries containing an 'id' and 'threadId'
    results = []
    for add in ADDRESSES:
        results.extend(service.users().messages().list(userId = 'me', q = f'from:{add} after:{AFTER} before:{BEFORE}').execute()['messages'])
    # Using those message ids, seperately query, piece together, and decode the message body for each
    # then append them to the eventual list of gmails to return in utf-8 format
    decoded_messages = []
    for message in results:
        email = service.users().messages().get(userId = 'me', id = message['id']).execute()
        parts = email['payload']['parts']
        text = parts[0]['body']['data']
        # text = ' '.join([part['body']['data'] for part in parts])
        
        # Decode the text from base64
        text = text.replace('-', '+').replace('_', '/') 
        text = base64.b64decode(text).decode('utf-8')
        text = re.sub(r"<.*>", "", text) 
        decoded_messages.append(text)

    return decoded_messages

def summarize_text(instructions, input_text):
    '''
    Sets up a chat interaction with an OpenAI model. Providing the system with instructions and then feeding
    it the input_text, this function prints out the resulting response and token cost from OpenAI
    '''
    prompt = [{"role": "system", "content": instructions}, {"role": "user", "content": f"Here is an email: {input_text}"}]
    result = openai.ChatCompletion.create(messages=prompt, model="gpt-3.5-turbo", temperature=0.0)
    summary = result["choices"][0]["message"]["content"]
    print(summary)
    print(result['usage'])

def main():
    '''
    Calls functions to setup, collect messages, and call OpenAI's API to get email summaries
    '''
    service = setup()
    selected_messages = message_collection(service)
    for message in selected_messages:
        summarize_text(GPT_INSTRUCTIONS, message)

if __name__ == '__main__':
    main()
