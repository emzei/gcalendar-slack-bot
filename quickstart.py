from __future__ import print_function

import datetime
import time
import os.path

import requests

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

SLACKBOT_RESTAPI = 'URL' #incoming-webhook url in your slack app
GCALENDAR_ID = 'googlecalendar id to look for'
SERVER_PORT = 30000

PERIOD_MINUTES = 1
SECONDS = 60
UNIXTIME_DAY= 24*60*60

def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=SERVER_PORT)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        updated_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=PERIOD_MINUTES)
        updated_isoformat = updated_ago.isoformat() + 'Z'  # 'Z' indicates UTC time

        print(f'Updated schedules after', updated_isoformat)
        page_token = None
        calendar_id=GCALENDAR_ID
        toSlackBot=[]
        while True:
            events = service.events().list(calendarId=calendar_id, pageToken=page_token, updatedMin=updated_isoformat).execute()
            for event in events['items']:
                if event['status'] == 'confirmed':
                    if event['created'] == event['updated']:
                        toSlackBot.append(['created',event['id']])
                    else:
                        toSlackBot.append(['updated',event['id']])
                else:
                    toSlackBot.append(['cancelled',event['id']])
            page_token = events.get('nextPageToken')
            if not page_token:
                break
        
        for evt, eid in toSlackBot:
            event = service.events().get(calendarId=calendar_id, eventId=eid).execute()
            #print(event['summary'],event['start'],event['end'] )
            s,e = '',''
            date=[0,0] # pretty date
            allday = False

            if 'dateTime' in event['start']:
                s,e = event['start']['dateTime'][:-6], event['end']['dateTime'][:-6]
                tmp=datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S')
                date[0] = str(time.mktime(tmp.timetuple()))[:-2]
                tmp=datetime.datetime.strptime(e,'%Y-%m-%dT%H:%M:%S')
                date[1] =  str(time.mktime(tmp.timetuple()))[:-2]
                
            else:
                s,e = event['start']['date'], event['end']['date']
                tmp=datetime.datetime.strptime(s,'%Y-%m-%d')
                date[0] = str(time.mktime(tmp.timetuple()))[:-2]
                tmp=datetime.datetime.strptime(e,'%Y-%m-%d') - datetime.timedelta(days=1)
                date[1] = str(time.mktime(tmp.timetuple()))[:-2]
                allday=True

            title = ''
            if evt == 'created':
                title = ':white_check_mark: [New Event] ' + event['summary']
            elif evt == 'updated':
                title= ':white_check_mark: [Updated] ' + event['summary'] 
            else: #cancelled
                title = ':white_check_mark: [Cancelled] ' + event['summary']

            send_data = {}
            send_data['blocks'] = []
            send_data['blocks'].append( {
                "type":"section",
                "text":{
                    "type":"mrkdwn",
                    "text":f"*{title}*"
                }
            })
            if allday:
                if date[0]== date[1]:
                    tmp_date = str(datetime.datetime.strptime(s,'%Y-%m-%d'))[:-9]
                    send_data['blocks'].append( 
                    { 
                        "type":"section", 
                        "text":
                            {
                                "type":"mrkdwn",
                                "text":f'<!date^{date[0]}'+'^ {date_long_pretty} | '+f'{tmp_date} (All day)>'
                            }
                        
                        }
                    )
                else:
                    tmp_date_s= str(datetime.datetime.strptime(s,'%Y-%m-%d'))[:-9]
                    tmp_date_e= str(datetime.datetime.strptime(e,'%Y-%m-%d')-datetime.timedelta(days=1))[:-9]
                    send_data['blocks'].append( 
                    { 
                        "type":"section", 
                        "text":
                            {
                                "type":"mrkdwn",
                                "text":f'from <!date^{date[0]}'+'^ {date_long_pretty} |'+f'{tmp_date_s}> to'+ \
                                    f'<!date^{date[1]}'+'^ {date_long_pretty} | '+f'{tmp_date_e}> '
                            }
                        
                        }
                    )
            else:
                tmp_date_s=str(datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S'))[:-3]
                tmp_date_e=''
                if int(date[1]) - int(date[0]) < UNIXTIME_DAY:
                    tmp_date_e=datetime.datetime.strptime(e,'%Y-%m-%dT%H:%M:%S')
                    tmp_date_e=str(tmp_date_e)[10:-3]

                else:
                    tmp_date_e=str(datetime.datetime.strptime(e,'%Y-%m-%dT%H:%M:%S'))[:-3]
                
                send_data['blocks'].append( 
                { 
                    "type":"section", 
                    "text":
                        {
                            "type":"mrkdwn",
                            "text":f'from <!date^{date[0]}'+'^ {date_long_pretty} {time}|'+f'{tmp_date_s}> to'+ \
                                f'<!date^{date[1]}'+'^ {date_long_pretty} {time}|'+f'{tmp_date_e}> '
                        }
                    
                    }
                )
            response=requests.post(SLACKBOT_RESTAPI, json=send_data)
            
            if response.status_code == 400:
                print(response.content)
                
    except HttpError as error:
        print('An error occurred: %s' % error)


if __name__ == '__main__':
    main()
