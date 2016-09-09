import base64, urllib2, json, datetime, time, sys, getpass, plistlib
def tokenFactory(dsid, mmeAuthToken):
    mmeAuthTokenEncoded = base64.b64encode("%s:%s" % (dsid, mmeAuthToken))
    #now that we have proper auth code, we will attempt to get all account tokens.
    url = "https://setup.icloud.com/setup/get_account_settings"
    headers = {
        'Authorization': 'Basic %s' % mmeAuthTokenEncoded,
        'Content-Type': 'application/xml',
        'X-MMe-Client-Info': '<iPhone6,1> <iPhone OS;9.3.2;13F69> <com.apple.AppleAccount/1.0 (com.apple.Preferences/1.0)>'
    }

    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return ("HTTP Error: %s" % e.code, 0) #expects tuple
        else:
            print e
            raise HTTPError
    #staple it together & call it bad weather; only need FMFAppToken
    content = response.read()
    mmeFMFAppToken = plistlib.readPlistFromString(content)["tokens"]["mmeFMFAppToken"]
    return mmeFMFAppToken

def dsidFactory(uname, passwd): #can also be a regular DSID with AuthToken
    creds = base64.b64encode("%s:%s" % (uname, passwd))
    url = "https://setup.icloud.com/setup/authenticate/%s" % uname
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
                return ("HTTP Error 401: Unauthorized. Are you sure the credentials are correct?", 0)
            elif e.code == 409:
                return ("HTTP Error 409: Conflict. 2 Factor Authentication appears to be enabled. You cannot use this script unless you get your MMeAuthToken manually (generated either on your PC/Mac or on your iOS device).", 0)
            elif e.code == 404:
                return ("HTTP Error 404: URL not found. Did you enter a username?", 0)
            else:
                return ("HTTP Error %s.\n" % e.code, 0)
        else:
            print e
            raise HTTPError
    content = response.read()
    DSID = int(plistlib.readPlistFromString(content)["appleAccountInfo"]["dsPrsID"]) #stitch our own auth DSID
    mmeAuthToken = plistlib.readPlistFromString(content)["tokens"]["mmeAuthToken"] #stitch with token
    return (DSID, mmeAuthToken)

def HeardItFromAFriendWho(dsid, mmeFMFAppToken, user):
    url = 'https://p04-fmfmobile.icloud.com/fmipservice/friends/%s/refreshClient' % dsid
    headers = {
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (dsid, mmeFMFAppToken)),#FMF APP TOKEN
        'Content-Type': 'application/json; charset=utf-8',
    }
    data = {
        "clientContext": {
            "appVersion": "5.0" #critical for getting appropriate config / time apparently.
        }
    }
    jsonData = json.dumps(data)
    request = urllib2.Request(url, jsonData, headers)
    i = 0
    while 1:
        try:
            response = urllib2.urlopen(request)
            break
        except: #for some reason this exception needs to be caught a bunch of times before the request is made.
            i +=1
            continue
    x = json.loads(response.read())
    dsidList = []
    phoneList = [] #need to find how to get corresponding name from CalDav
    for y in x["following"]: #we need to get contact information.
        for z, v in y.items():
            #do some cleanup
            if z == "invitationAcceptedHandles":
                v = v[0] #v is a list of contact information, we will grab just the first identifier
                phoneList.append(v)
            if z == "id":
                v = v.replace("~", "=")
                v = base64.b64decode(v)
                dsidList.append(v)
    zippedList = zip(dsidList, phoneList)
    retString = ""
    i = 0
    for y in x["locations"]:#[0]["location"]["address"]:
        streetAddress, country, state, town, timeStamp = " " *5
        dsid = y["id"].replace("~", "=")
        dsid = base64.b64decode(dsid) #decode the base64 id, and find its corresponding one in the zippedList.
        for g in zippedList:
            if g[0] == dsid:
                phoneNumber = g[1] #we should get this for every person. no errors if no phone number found. 
        if y["location"]["timestamp"]:
            timeStamp = y["location"]["timestamp"] / 1000
            timeNow = time.time()
            timeDelta = timeNow - timeStamp #time difference in seconds
            minutes, seconds = divmod(timeDelta, 60) #great function, saves annoying maths
            hours, minutes = divmod(minutes, 60)
            timeStamp = datetime.datetime.fromtimestamp(timeStamp).strftime("%A, %B %d at %I:%M:%S")
            timeStamp = "%s (%sm %ss ago)" % (timeStamp, str(minutes).split(".")[0], str(seconds).split(".")[0]) #split at decimal
        else:
            timeStamp = "n/a"
        for z, v in y["location"]["address"].items(): #loop through address info
            #counter of threes for pretty print...
            if type(v) is list:
                continue
            if z == "streetAddress":
                streetAddress = v
            if z == "countryCode":
                country = v
            if z == "stateCode":
                state = v
            if z == "locality":
                town = v
        if streetAddress != " ": #in the event that we cant get a street address, dont print it to the final thing
            retString += "%s\n%s\n%s, %s, %s\n%s\n%s\n" % ("\033[34m" + phoneNumber, "\033[92m" + streetAddress, town, state, country, "\033[0m" + timeStamp,"-----")
        else:
            retString += "%s\n%s, %s, %s\n%s\n%s\n" % ("\033[34m" + phoneNumber, "\033[92m" + town, state, country, "\033[0m" + timeStamp,"-----")

        i += 1
    return retString + "\033[91mFound \033[93m[%s]\033[91m friends for %s!\033[0m" % (i, user)

if __name__ == '__main__':
    user = raw_input("Apple ID: ")
    try: #in the event we are supplied with an DSID, convert it to an int
        int(user)
        user = int(user)
    except ValueError: #otherwise we have an apple id and can not convert
        pass
    passw = getpass.getpass()
    (DSID, authToken) = dsidFactory(user, passw)
    if authToken == 0: #http error
        print DSID
        sys.exit()
    mmeFMFAppToken = tokenFactory(DSID, authToken)
    print HeardItFromAFriendWho(DSID, mmeFMFAppToken, user),
