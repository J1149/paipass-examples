from flask import Flask, request, redirect
from getpass import getpass
import json
import os
import random
import requests
import sys
from urllib.parse import urlencode

import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())
logger = logging.getLogger()

PAIPASS_API_URL = r'https://api.demo.p19dev.com/'
PAIPASS_USER_DATA_URL = PAIPASS_API_URL + r'attributes/paipass/user.data/0'
CLIENT_INFO_PATH = r'client_info.txt'

app = Flask(__name__)


class IllegalStateError(Exception):
    '''
    A state error that corresponds to a ClientInfo instance. Specifically,
    this is raised when that instance did not use the syntax of:
        
        with client_info_instance:
            ... do arbitrary things with client_info_instance ...
    
    and instead probably did:

        ... do arbitrary things with client_info_instance ...

    The context manager "with" syntax is required.
    '''
    pass


class ClientInfo:
    '''
    This is simply a helper class to keep the client info data
    easily accessible, modifiable, and consistent.
    '''
    def __init__(self, info_path=None, data=None):
        self.data = data
        
        if info_path is None:
            self.info_path = CLIENT_INFO_PATH
        else:
            self.info_path = info_path

        self.entered = False
        self.updated = False

    def __enter__(self):
        self.entered = True

        if self.data is not None:
            return self

        if os.path.exists(self.info_path):
            with open(self.info_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {}

        return self

    def __exit__(self, type, value, traceback):
        self.entered = False
        # Let's not write a new file if the data hasn't been updated.
        if not self.updated:
            logger.debug("Nothing to Update!")
            return
        logger.debug("We're updating the client_info file with %s"%self.data)
        # No traceback; everything seems to have run correctly.
        if traceback is None:
            with open(self.info_path, 'w') as f:
                json.dump(self.data, f)
        # If there is a traceback, let's save to a backup file. 
        else:
            # lets_make a unique backup path using the time in milliseconds
            import time
            millis = str(int(round(time.time()*1000)))
            backup_path = self.info_path + '.' + millis +  '.traceback_sav'
            with open(backup_path, 'w' ):
                json.dump(self.data, f)

    def __setitem__(self, key, value):
        self.verify_entrance()
        self.data[key] = value
        self.updated = True

    def __getitem__(self, key):
        self.verify_entrance()
        return self.data[key]

    def _err_msg(self):
        m = "The data of %s was accessed without using the context " \
                + " manager synax of with client_info_instance:"
        return m

    def update(self, data2):
        self.verify_entrance()
        self.data.update(data2)
        self.updated = True

    def verify_entrance(self):
        if not self.entered:
            raise IllegalStateError(self._err_msg())

def generate_nonce(length=8):
    """Generate pseudorandom number.
    https://stackoverflow.com/questions/5590170
    """
    return ''.join([str(random.randint(0, 9)) for i in range(length)])

@app.route("/")
def index():
    '''
    In this method we display the index.
    '''
    # We disable the button to grab client info until we have saved
    # the registered app data in CLIENT_INFO_PATH,
    grab_client_info_state = 'disabled'
    if os.path.exists(CLIENT_INFO_PATH):
        grab_client_info_state = ''
    html = """
    <button onclick="window.location.href = '/register-app';"> Register App </button>
    <button onclick="window.location.href = '/grab-client-info';" %s> Grab Client Info </button>
           """%grab_client_info_state
    return html

@app.route("/grab-client-info")
def grab_client_info():
    '''
    This is the point where we begin the process of requesting info from the
    user. Specifically, we redirect the user to paipass to allow the user
    to authorize us to view their data.
    '''
    url = PAIPASS_API_URL + "oauth/authorize?"

    scope = r'READ_ALL.PAIPASS.SSO'

    with client_info as ci:
        body = {"client_id":     ci['clientId'],
                "redirect_uri":  ci['redirect_uri'],
                "response_type": 'code',
                "scope":         scope,
                "state":         generate_nonce(6)}

    url_token = ''.join([url, urlencode(body)])

    return redirect(url_token)

@app.route("/receive-token")
def receive_token():
    '''
    This is where we receive the token from the server after the user has
    authorized us to use their data.

    Notice that this endpoint corresponds to the endpoint we specified on the
    page where we were registered the app.
    '''
    auth_code = request.args['code']
    url = PAIPASS_API_URL + "oauth/token?"

    with client_info as ci:
        body = {'grant_type':   'authorization_code',
                'code':         auth_code,
                'redirect_uri': ci['redirect_uri'],
                'client_id':    ci['clientId']}

    url_token = ''.join([url, urlencode(body)])
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    
    with client_info as ci:
        auth = (ci["clientId"], ci["clientSecret"])

    response = requests.post(url_token, auth=auth, headers=headers)

    with client_info as ci:
        ci["access_token"] = response.json()["access_token"]

    return redirect('/get-info')

@app.route("/get-info")
def get_info():
    '''
    At this we can use the access_token retrieved in receive_toke() to
    request the User's data.
    '''
    with client_info as ci:
        access_token = ci["access_token"]
    auth_header = 'Bearer {0}'.format(access_token)
    headers = {"Authorization": auth_header,
               "Accept": 'application/json',
               "Content-type": 'application/json;charset=utf-8'}
    r = requests.get(PAIPASS_USER_DATA_URL, headers=headers)
    return json.dumps(json.loads(r.text), indent=2)
       

@app.route("/register-app")
def app_registration():
    """
    A simple HTML page to register an app for oauth.
    """
    html = """
            <form action="/post-registration" method="post" enctype="application/json">
            <div>
                <label for="user_name">Username:</label>
                <input type="text" id="user_name" name="username">
            </div>
            <div>
                <label for="password">Password:</label>
                <input type="password" id="pw" name="password">
            </div>
            <div>
                <label for="appname">App Name:</label>
                <input type="text" id="appname" name="name">
            </div>

            <div>
                <label for="name_space">Namespace:</label>
                <input type="text" id="name_space" name="namespace">
            </div>
            <div>
                <label for="home_page_url">Home Page URL:</label>
                <input type="text" id="home_page_url" name="homePageURL">
            </div>
            
            <div>
                <label for="descr">Description:</label>
                <input type="text" id="descr" name="description">
            </div>
            
            <div>
                <label for="web_server_redirect_uris">Web Server Redirect URI:</label>
                <input type="text" id="web_server_redirect_uris" name="webServerRedirectURIs">
            </div>

            <div>
                <label for="logo_url">Logo Url:</label>
                <input type="text" id="logo_url" name="logoURL">
            </div>
            <div>
            <label for="is_private">Is Private:</label>
                <select name='isPrivate' id='is_private'>
                    <option selected>True</option>
                    <option>False</option>
                </select>
            </div>
            <div>
                <input type="submit" value="Register App">
            </div>
            </form>
           """
    return html

@app.route("/post-registration", methods=['POST'])
def post_registration():
    """
    Here we post the registration after we have filled in the registration
    form rendered by app_registration().
    """
    app_registration = request.form
    
    session = requests.Session()
    login_response = login(session, app_registration)

    registration_response = register_app(session, app_registration)

    json_dict = registration_response.json()
    json_dict["redirect_uri"] = app_registration["webServerRedirectURIs"]
    with client_info:
        client_info.update(json_dict)
    return redirect("/", code=302)
    

app_registration_params = ['name', 'namespace', 'homePageURL',
                           'description', 'webServerRedirectURIs',
                           'logoURL', 'isPrivate']


def login(session, app_registration):
    """
    Login so we can register the app.
    """
    username = app_registration["username"]
    password = app_registration["password"]
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    params = {'username':username, 'password':password}
    response = session.post(PAIPASS_API_URL + r'account/make-login', 
                            headers=headers, params=params)
    return response

def register_app(session, app_registration):
    # Register the app with the authenticated session generated by login().
    sparse_info = {}
    for param in app_registration_params:
        sparse_info[param] = app_registration[param]
    # Web server redirect URIs must be in list form
    val = sparse_info['webServerRedirectURIs']
    l = list()
    l.append(val)
    sparse_info['webServerRedirectURIs'] =l
    # isPrivate must be a bool type
    sparse_info['isPrivate'] = bool(sparse_info['isPrivate'])
    headers = {'content-type':'application/json'}
    response = session.post(PAIPASS_API_URL + r'application', headers=headers, 
                            json=sparse_info)
    return response
    
if __name__ == '__main__':
    client_info = ClientInfo()
    app.run(debug=True, port=8080)
