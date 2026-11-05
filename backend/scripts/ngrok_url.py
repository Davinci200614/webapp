"""Print the local ngrok HTTPS tunnel to port 8000; 1=unavailable, 2=no match."""
import json
import sys
import urllib.request
from urllib.parse import urlsplit


def find_url(tunnels):
    for tunnel in tunnels:
        address = str(tunnel.get('config', {}).get('addr', ''))
        if address.isdigit():
            address = 'http://localhost:' + address
        elif '://' not in address:
            address = 'http://' + address
        target = urlsplit(address)
        public = urlsplit(tunnel.get('public_url', ''))
        try:
            matches = target.hostname in {'localhost', '127.0.0.1', '[::1]', '::1'} and target.port == 8000
        except ValueError:
            matches = False
        if matches and public.scheme == 'https' and public.netloc:
            return public.geturl().rstrip('/')
    return None


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open('http://127.0.0.1:4040/api/tunnels', timeout=1) as response:
            url = find_url(json.load(response).get('tunnels', []))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1
    if not url:
        return 2
    print(url)
    return 0


if __name__ == '__main__':
    sys.exit(main())
