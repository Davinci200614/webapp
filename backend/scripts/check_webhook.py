"""Read-only webhook/tunnel diagnostics. Never display credentials or messages."""
import argparse
import json
import re
import sqlite3
from urllib import error, parse, request
from app.db import database_path


def fetch_json(url):
    opener=request.build_opener(request.ProxyHandler({}))
    with opener.open(url,timeout=3) as response:
        return json.load(response)


def inspect_database():
    path=database_path()
    print('Target database:',path)
    if not path.is_file():
        print('Database has not been initialized. Start the backend first.');return
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        for table in ('webhook_inbox','messages'):
            try:
                count=db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                print(f'{table}: {count} stored records')
                field='state' if table=='webhook_inbox' else 'status'
                states=db.execute(f'SELECT {field},count(*) FROM {table} GROUP BY {field}').fetchall()
                for state,total in states:
                    label=state if re.fullmatch(r'[a-z_]{1,30}',str(state)) else '[redacted]'
                    print(f'  {label}: {total}')
            except sqlite3.Error:print(f'{table}: unavailable; start the backend to apply migrations')
        try:
            rows=db.execute('SELECT status,error,created_at FROM messages ORDER BY rowid DESC LIMIT 5').fetchall()
            for status,code,created in rows:
                code=code if code and re.fullmatch(r'[a-z0-9_]{1,80}',str(code)) else ('[redacted]' if code else 'none')
                print(f'  Recent processing: {created}, status={status}, error={code}')
        except sqlite3.Error:pass


def inspect_ngrok():
    try:
        data=fetch_json('http://127.0.0.1:4040/api/tunnels')
        tunnels=data.get('tunnels',[])
        if not tunnels:print('ngrok agent is running but reports no active tunnels.')
        for tunnel in tunnels:
            url=tunnel.get('public_url','')
            target=tunnel.get('config',{}).get('addr','')
            # These are public/local routing URLs, never an account token.
            if parse.urlsplit(url).scheme in ('http','https'):
                print('Active ngrok public URL:',url.split('?',1)[0])
            if re.fullmatch(r'(?:https?://)?(?:localhost|127\.0\.0\.1):8000|8000',str(target)):
                print('  Target port: 8000 (correct)')
            else:print('  Target is not recognized as localhost:8000; check the ngrok terminal.')
    except PermissionError:
        print('Local network inspection was blocked. Run this command from your normal terminal.')
    except (OSError,error.URLError,ValueError,AttributeError,TypeError):
        print('No readable ngrok agent at localhost:4040. Start/check your tunnel in another terminal.')
        print('If you use another tunnel provider, check its public URL and target port instead.')


def inspect_public(url):
    parsed=parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query:
        raise ValueError('Provide only the public HTTPS URL or callback URL, without credentials/query parameters.')
    origin=f'https://{parsed.netloc}'
    try:
        data=fetch_json(origin+'/api/public/config')
        if isinstance(data,dict) and 'whatsapp_number' in data:
            print('Public URL reaches the integrated webapp backend.')
            print('Meta callback path must be /webhook/whatsapp on this same public host.')
        else:print('Public URL responded, but the integrated-backend marker is missing.')
    except error.HTTPError as exc:print(f'Public backend probe returned HTTP {exc.code}. Check the tunnel target and running app.')
    except (OSError,error.URLError,ValueError):print('Public backend probe failed. Check the tunnel and public hostname.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',help='Optional public HTTPS host or Meta callback URL; never supply a token')
    args=parser.parse_args()
    inspect_database();inspect_ngrok()
    if args.url:
        try:inspect_public(args.url)
        except ValueError as exc:parser.error(str(exc))
    print('No stored inbound messages means no accepted inbound message reached this database.')
    print('It can also mean Meta sent only delivery/status events or a request was rejected; check POST logs.')

if __name__=='__main__':main()
