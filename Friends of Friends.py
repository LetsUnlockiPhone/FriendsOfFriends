import base64, urllib2, json, datetime, time, sys, getpass, plistlib
def token_factory(dsid, mmeAuthToken):
    mme_auth_token_encoded = base64.b64encode('%s:%s' % (dsid, mmeAuthToken))
    #now that we have proper auth code, we will attempt to get all account tokens.
    url = 'https://setup.icloud.com/setup/get_account_settings'
    headers = {
        'Authorization': 'Basic %s' % mme_auth_token_encoded,
        'Content-Type': 'application/xml',
        'X-MMe-Client-Info': '<iPhone6,1> <iPhone OS;9.3.2;13F69> <com.apple.AppleAccount/1.0 (com.apple.Preferences/1.0)>'
    }

    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return ('HTTP Error: %s' % e.code, 0) #expects tuple
        else:
            print e
            raise urllib2.HTTPError
    #only need FMFAppToken from here on out
    content = response.read()
    mme_FMF_app_token = plistlib.readPlistFromString(content)['tokens']['mmeFMFAppToken']
    return mme_FMF_app_token

def dsid_factory(uname, passwd): #can also be a regular DSID with AuthToken
    creds = base64.b64encode('%s:%s' % (uname, passwd))
    url = 'https://setup.icloud.com/setup/authenticate/%s' % uname
    headers = {
        'Authorization': 'Basic %s' % creds,
        'Content-Type': 'application/xml',
    }

    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            if e.code == 401:
                return ('HTTP Error 401: Unauthorized. Are you sure the credentials are correct?', 0)
            elif e.code == 409:
                return ('HTTP Error 409: Conflict. 2 Factor Authentication appears to be enabled. You cannot use this script unless you get your MMeAuthToken manually (generated either on your PC/Mac or on your iOS device).', 0)
            elif e.code == 404:
                return ('HTTP Error 404: URL not found. Did you enter a username?', 0)
            else:
                return ('HTTP Error %s.\n' % e.code, 0)
        else:
            print e
            raise urllib2.HTTPError
    content = response.read()
    DSID = int(plistlib.readPlistFromString(content)['appleAccountInfo']['dsPrsID']) #stitch our own auth DSID
    mme_auth_token = plistlib.readPlistFromString(content)['tokens']['mmeAuthToken'] #stitch with token
    return (DSID, mme_auth_token)

def heard_it_from_a_friend_who(dsid, mme_FMF_app_token, user):
    while 1:
        url = 'https://p04-fmfmobile.icloud.com/fmipservice/friends/%s/refreshClient' % dsid
        headers = {
            'Authorization': 'Basic %s' % base64.b64encode('%s:%s' % (dsid, mme_FMF_app_token)),#FMF APP TOKEN
            'Content-Type': 'application/json; charset=utf-8',
        }
        data = {
            'clientContext': {
                'appVersion': '5.0' #critical for getting appropriate config / time apparently.
            }
        }
        json_data = json.dumps(data)
        request = urllib2.Request(url, json_data, headers)
        while 1:
            try:
                response = urllib2.urlopen(request)
                break
            except: #for some reason this exception needs to be caught a bunch of times before the request is made.
                continue
        response_dict = json.loads(response.read())
        dsid_list = []
        phone_list = [] #need to find how to get corresponding name from CalDav
        for friend in response_dict['following']: #we need to get contact information.
            for key, value in friend.items():
                #do some cleanup
                if key == 'invitationAcceptedHandles':
                    value = value[0] #value is a list of contact information, we will grab just the first identifier
                    phone_list.append(value)
                if key == 'id':
                    value = value.replace('~', '=')
                    value = base64.b64decode(value)
                    dsid_list.append(value)
        zipped_list = zip(dsid_list, phone_list)
        return_string = ''
        user_count = 0
        try:
            locations = response_dict['locations']
        except KeyError:
            appendable = ''
            if dsid_list:
                appendable = ' for the following users %s ' % dsid_list
            return 'Error getting locations%s.' % appendable
        for friend in response_dict['locations']:
            street_address, country, state, town, timeStamp = ' ' *5
            dsid = friend['id'].replace('~', '=')
            dsid = base64.b64decode(dsid) #decode the base64 id, and find its corresponding one in the zippedList.
            for user_id in zipped_list:
                if user_id[0] == dsid:
                    phone_number = user_id[1] #we should get this for every person. no errors if no phone number found. 
            
            try:
                time_stamp = friend['location']['timestamp'] / 1000
                time_now = time.time()
                time_delta = time_now - time_stamp #time difference in seconds
                minutes, seconds = divmod(time_delta, 60) #great function, saves annoying maths
                hours, minutes = divmod(minutes, 60)
                time_stamp = datetime.datetime.fromtimestamp(time_stamp).strftime('%A, %B %d at %I:%M:%S')
                time_stamp = '%s (%sm %ss ago)' % (time_stamp, str(minutes).split('.')[0], str(seconds).split('.')[0]) #split at decimal
            except TypeError:
                time_stamp = 'Could not get last location time.'

            if not friend['location']: #once satisfied, all is good, return fxn will end
                continue #go back to top of loop and re-run query
            
            for key, value in friend['location']['address'].items(): #loop through address info
                #counter of threes for pretty print...
                if type(value) is list:
                    continue
                if key == 'streetAddress':
                    street_address = value
                if key == 'countryCode':
                    country = value
                if key == 'stateCode':
                    state = value
                if key == 'locality':
                    town = value

            if street_address != ' ': #in the event that we cant get a street address, dont print it to the final thing
                return_string += '%s\n%s\n%s, %s, %s\n%s\n%s\n' % ('\033[34m' + phone_number, '\033[92m' + street_address, town, state, country, '\033[0m' + time_stamp,'-----')
            else:
                return_string += '%s\n%s, %s, %s\n%s\n%s\n' % ('\033[34m' + phone_number, '\033[92m' + town, state, country, '\033[0m' + time_stamp,'-----')

            user_count += 1
        return '%s\033[91mFound \033[93m[%s]\033[91m friends for %s!\033[0m' % (return_string, user_count, user)

if __name__ == '__main__':
    user = raw_input('Apple ID: ')
    try: #in the event we are supplied with an DSID, convert it to an int
        int(user)
        user = int(user)
    except ValueError: #otherwise we have an apple id and can not convert
        pass
    passw = getpass.getpass()
    (DSID, auth_token) = dsid_factory(user, passw)
    if auth_token == 0: #http error
        print DSID
        sys.exit()
    mme_FMF_app_token = token_factory(DSID, auth_token)
    print heard_it_from_a_friend_who(DSID, mme_FMF_app_token, user),
