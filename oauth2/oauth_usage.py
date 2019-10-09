from flask import Flask, request, redirect
from flask_ngrok import run_with_ngrok
from getpass import getpass
import json
import os
import random
import requests
import sys
from urllib.parse import urlencode

PAIPASS_API_URL = r'https://api.demo.p19dev.com/'
PAIPASS_USER_DATA_URL = r'https://api.demo.p19dev.com/attributes/paipass/user.data/0'
CLIENT_INFO_PATH = r'client_info.txt'

app = Flask(__name__)
run_with_ngrok(app)


def generate_nonce(length=8):
    """Generate pseudorandom number.
    https://stackoverflow.com/questions/5590170/what-is-the-standard-method-for-generating-a-nonce-in-python
    """
    return ''.join([str(random.randint(0, 9)) for i in range(length)])

@app.route("/")
def index():
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
    s = ""
    with open(CLIENT_INFO_PATH, 'r') as f:
        for line in f:
            s += line
    data = json.loads(s)
    client_secret = data['clientSecret']
    client_id = data['clientId']
    redirect_uri = data['redirect_uri']
    response_type = 'code'
    scope = r'READ_ALL.PAIPASS.SSO'
    url = PAIPASS_API_URL + "oauth/authorize"
    url += r'?client_id=%s'% client_id
    url += r'&'
    url += r'redirect_uri=%s'% redirect_uri
    url += r'&'
    url += r'response_type=%s' % response_type
    url += r'&'
    url += r'scope=%s' % scope
    url += r'&'
    url += r'state=%s' % str(generate_nonce(6))
    return redirect(url)

@app.route("/receive-token")
def receive_token():
    print('request.data', request.data, file=sys.stderr)
    print('request.form', request.form, file=sys.stderr)
    print('request.args', request.args, file=sys.stderr)
    auth_code = request.args['code']
    with open('log.txt', 'w') as f:
        f.write("auth_code=%s\n"%auth_code)
    s = ""
    with open(CLIENT_INFO_PATH, 'r') as f:
        for line in f:
             s += line   
    data = json.loads(s)
    url = PAIPASS_API_URL + "oauth/token?"
    body = {'grant_type': 'authorization_code',
            'code':auth_code,
            'redirect_uri': data['redirect_uri'],
            'client_id':data['clientId']}
    url_token = ''.join([url, urlencode(body)])
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    
    response = requests.post(url_token, 
                             auth=(data["clientId"], data["clientSecret"]),
                             headers=headers)
    data["access_token"] = response.json()["access_token"]

    with open(CLIENT_INFO_PATH, 'w') as f:
        f.write(json.dumps(data))
        

    return redirect('/get-info')

@app.route("/get-info")
def get_info():
    s = ""
    with open(CLIENT_INFO_PATH, 'r') as f:
         for line in f:
             s+= line
    data = json.loads(s)
    access_token = data["access_token"]
    auth_header = 'Bearer {0}'.format(access_token)
    headers = {"Authorization": auth_header,
               "Accept": 'application/json',
               "Content-type": 'application/json;charset=utf-8'}
    r = requests.get(PAIPASS_USER_DATA_URL, headers=headers)
    with open('log.txt', 'a') as f:
        f.write('request.data=%s\n'%str(request.data))
        f.write('request.form=%s\n'%str(request.form))
        f.write('request.args=%s\n'%str(request.args))
        for attr in dir(r):
            if not attr.startswith('__'):
                f.write('%s=%s\n'%(attr, getattr(r, attr)))
        try:
            f.write("request.json=%s"%request.json())
        except:
            pass
    return json.dumps(json.loads(r.text), indent=2)
       

@app.route("/register-app")
def app_registration():
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
    data = request.form
    app_info = AppInfo()
    for param, param_type in params_and_types.items():
        val = data[param]
        if param_type == list:
            # we don't handle multiple redirect uris yet.
            # so we have a one element list for this case.
            lst = []
            lst.append(val)
            setattr(app_info, param, lst)
        else:
            val = param_type(val)
            setattr(app_info, param, val)
    session = requests.Session()
    username = data["username"]
    password = data["password"]
    login(session,username=username,password=password)
    response = register_app(session, app_info=app_info)
    json_dict = response.json()
    json_dict["redirect_uri"] = data["webServerRedirectURIs"]
    with open(CLIENT_INFO_PATH, 'w') as f:
        f.write(json.dumps(json_dict))
    return redirect("/", code=302)
    

class AppRegistrationException(Exception):
    pass


class ValidatedParam:

    def __init__(self, storage_name=None, storage_type=None):
        self.storage_name = storage_name
        self.storage_type = storage_type

    def __set__(self, instance, value):
        self.validate_type(instance, value)
        self.validate()
        instance.__dict__[self.storage_name] = value

    def __get__(self, instance, owner):
        return getattr(instance, self.storage_name)

    def validate_type(self, instance, value):
        if type(value) != self.storage_type:
            err = ("Expected type for %s is %s but we received the following" 
                   " type instead: %s.")
            err_parameterized = err % (self.storage_name, self.storage_type, 
                                       type(value))

            raise AppRegistrationException(err_parameterized)

    def validate(self):
        pass

             
class ValidatedPaipassUrl(ValidatedParam):
    
    def validate(self):
        pass


params_and_types = {'name':str, 'namespace':str, 'homePageURL':str, 
                    'description':str, 'webServerRedirectURIs':list,
                    'logoURL':str, 'isPrivate': bool}


def add_app_info_params(cls):

    for param in params_and_types:
        setattr(cls, param, ValidatedParam())
    for key, attr in cls.__dict__.items():
        if isinstance(attr, ValidatedParam):
            param_type = type(attr)
            attr.storage_name = '_{}#{}'.format(param_type, key)
            attr.storage_type = params_and_types[key]
    return cls

   

@add_app_info_params
class AppInfo:
    pass
    

def cli_get_creds():
    username = input("Username?")
    password = getpass()
    return username, password

def cli_get_app_info():
    app_info = AppInfo()
    for param, param_type in params_and_types.items():
        if param_type == list:
            persist = True
            iterable = []
            while persist:
                val = input("%s?"%param)
                iterable.append(val)
                persist = 'y' == input("Continue adding to iterable?(y/n) ")
            setattr(app_info, param, iterable)
        elif param_type == dict:
            persist = True
            d = {}
            while persist:
                val = input("%s?"%param)
                key, value = val.split(':')
                d[key] = value
                persist = 'y' == input("Continue adding to iterable?(y/n) ")
            setattr(app_info, param, d)
        else:
            val = input("%s? "%param)
            setattr(app_info, param, param_type(val))
    return app_info

def login(session=None, username=None, password=None, get_creds=None):
    if get_creds is None:
        get_creds = cli_get_creds
    if session is None:
        session = requests.Session()    
    if username is None and password is None:
        username, password = get_creds()
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    params = {'username':username, 'password':password}
    response = session.post(PAIPASS_API_URL + r'account/make-login', 
                            headers=headers, params=params)
    return response

def register_app(session, app_info=None, get_app_info=None):
    if get_app_info is None:
        get_app_info = cli_get_app_info
    if app_info is None:
        app_info = get_app_info()
    headers = {'content-type':'application/json'}
    params = {}
    for param in params_and_types:
        params[param] = getattr(app_info, param)
    print(params)
    response = session.post(PAIPASS_API_URL + r'application', headers=headers, 
                            json=params)
    return response
    
if __name__ == '__main__':

    def cli_app_registration_example():
        session = requests.Session()
        login_response = login(session=session)
        print(login_response)
        if login_response.status_code != 200:
            exit()
        app_reg_response = register_app(session)
        print(app_reg_response)
        if app_reg_response.status_code == 200:
            print(app_reg_response.json())

    def run_web_app():
        #app.run(debug=True, port=8080)
        app.run()
    run_web_app()
