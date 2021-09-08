# This server tool checks for cards that come in through webhooks
import configparser
from flask.scaffold import F
import requests
from flask import Flask, json, request
import os

wUsername = ""
wPassword = ""
wekanUrl = ""
authorId = ""
newListId = ""
wActions = []
checkFieldlist = []

# Define REST server api
api = Flask(__name__)
@api.route('/', methods=['POST'])
def defaultroutepost():
    global wUsername 
    global wPassword 
    global wekanUrl 
    global authorId
    global wActions
    global newListId
    data = request.json

    # We allow cards in the new column in an incomplete state. Also we just listen to certain actions
    if data['listId'] != newListId and data['description'] in wActions: 
        token = getToken(wekanUrl, wUsername, wPassword)
        cardDetails = getWekanData(wekanUrl, token, "boards/" + data['boardId'] + "/lists/" + data['listId'] + "/cards/" + data['cardId'])
        message, missingData = checkCardFields(wekanUrl, token, data['boardId'], cardDetails)
        if missingData:
            rc = sendCardUpdate(wekanUrl, token, "boards/" + data['boardId'] + "/lists/" + data['listId'] + "/cards/" + data['cardId'],"red")
            rc = sendCardComment(wekanUrl, token, "boards/" + data['boardId'] + "/cards/" + data['cardId'] + "/comments", message)
        else:
            rc = sendCardUpdate(wekanUrl, token, "boards/" + data['boardId'] + "/lists/" + data['listId'] + "/cards/" + data['cardId'],"white")

    return json.dumps({'postsuccess':True}), rc, {'ContentType':'application/json'} 

@api.route('/wekan/webhook', methods=['POST'])
def checkCard():
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 

# Helper function for K8S deployment
def endless_loop(msg):
    print(msg + " Entering endless loop. Check and redo deployment?")
    while True:
        pass
# Retrieve WeKan token for successive API calls
def getToken(url, wUsername, wPassword):
    callUrl = url + "users/login"
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*"}
    body = { "username": wUsername, "password": wPassword}
    response = requests.post(callUrl, headers = headers, data = body ) 
    data = json.loads(response.text)
    print("Login to WeKan with response status " + str(response.status_code) + ".")
    return data["token"]

def getWekanData(url, token, api, log = True):
    callUrl = url + "api/" + api
    headers = { "Content-Type": "application/json", "Accept": "application/json", "Authorization": "" }
    headers["Authorization"] = "Bearer " + token
    response = requests.get(callUrl, headers = headers)
    data = json.loads(response.text)
    if log:
        print("Retrieved data object " + api + " with response status " + str(response.status_code) + ".")
    return data

# Flag a card that has not all fields filled
def sendCardUpdate(url, token, api, color, log = True):
    callUrl = url + "api/" + api
    headers = { "Content-Type": "application/json", "Accept": "application/json", "Authorization": "" }
    headers["Authorization"] = "Bearer " + token
    body = { "color": color }
    response = requests.put(callUrl, headers = headers, json = body)
    if log:
        print("Sent update for data object " + api + " with response status " + str(response.status_code) + ".")
    return response.status_code

# Send a comment into a card
def sendCardComment(url, token, api, comment, log = True):
    callUrl = url + "api/" + api
    headers = { "Content-Type": "application/json", "Accept": "application/json", "Authorization": "" }
    headers["Authorization"] = "Bearer " + token
    body = { "authorId": authorId, "comment": comment }
    response = requests.post(callUrl, headers = headers, json = body)
    if log:
        print("Sent comment for data object " + api + " with response status " + str(response.status_code) + ".")
    return response.status_code

def getFieldname(fList, name):
    for f in fList:
        if fList[f] == name: return True
    return False

# Check for missing fields in a card
def checkCardFields(wekanUrl, token, boardId, cardDetails):
    global checkFieldlist
    message = ""
    missingData = False
    customFields = getWekanData(wekanUrl, token, "boards/" + boardId + "/custom-fields")
    for cf in checkFieldlist:
        fieldName = checkFieldlist[cf].split(",")
        try:
            if "textfield" == fieldName[0]:
                if cardDetails[fieldName[1]] == "" or cardDetails[fieldName[1]] == None:
                    message = message + fieldName[1] + ", "
                    missingData = True
            elif "array" == fieldName[0]: # e.g. assignees
                if cardDetails[fieldName[1]] == []:
                    message = message + fieldName[1] + ", "
                    missingData = True
            elif "date" == fieldName[0]: # e.g. due date
                if cardDetails[fieldName[1]] == None:
                    message = message + fieldName[1] + ", "
                    missingData = True
            elif "customtext" == fieldName[0]: # Custom field handling                
                foundField = False
                for cusField in customFields:
                    if cusField["name"] == fieldName[1]:
                        for cusf in cardDetails["customFields"]:
                            if cusf["_id"] == cusField["_id"]: # Check if field is in card
                                 if not(cusf["value"] == None or cusf["value"] == ""): # We want something in it!
                                     foundField = True
                if not foundField:
                    message = message + fieldName[1] + ", "
                    missingData = True
        except Exception: # Likely the field is not there (e.g. due date)
            message = message + fieldName[1] + ", "
            missingData = True
    print("Card '" + cardDetails["title"] + "' ID '" + cardDetails["_id"] + "': " + message[:-2] + " missing.")
    message = "Please fill in the missing fields: " + message[:-2] + ".\n Check the <a href='https://wekanprod.c-88f9b3a.kyma.shoot.live.k8s-hana.ondemand.com/b/zmrySF3AjmD6z5mmP/wekan-feedback'>field descriptions</a> in case of doubt or ask your colleagues."
    return message, missingData

def main():
    global checkFieldlist
    global wUsername 
    global wPassword 
    global wekanUrl 
    global authorId
    global wActions
    global newListId
    #Get configuration
    config = configparser.ConfigParser(inline_comment_prefixes="#")
    config.read(['./config/settings.cfg'],encoding="utf8")
    if not config.has_section("server"):
        endless_loop("Config: Server section missing.")
    if not config.has_section("masterdata"):
        endless_loop("Config: masterdata section missing.")
    if not config.has_section("actions"):
        endless_loop("Config: actions section missing.")
    if not config.has_section("checkFieldlist"):
        endless_loop("Config: checkFieldlist section missing.")        
    # -------------- Parameters ------------------>>>
    wekanUrl = config.get("server","wekanUrl")
    authorId = config.get("masterdata","authorId")
    newListId = config.get("masterdata","newListId")
    actions = dict(config.items("actions"))
    checkFieldlist = dict(config.items("checkFieldlist"))
    for action in actions:
        if ",X" in actions[action]:
            wActions.append(actions[action][:-2])
    # -------------- Parameters ------------------<<<

    # Get username and password for WeKan
    try:
        wUsername = os.environ['USERNAME']
        wPassword = os.environ['PASSWORD']
    except Exception:
        endless_loop("Could not retrieve username and/or password.") # Stop here
    
    api.run(host='0.0.0.0', port=3002, debug=False)

    # Get token from WeKan

if __name__ == "__main__":
    main()