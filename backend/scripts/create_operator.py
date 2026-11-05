"""Provision an operator locally; passwords are never command-line arguments."""
import argparse
import getpass
from app.auth import _password_hash
from app.db import connect, init_db

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('email');parser.add_argument('--role',choices=['operator','admin'],default='operator')
    args=parser.parse_args();email=args.email.strip().lower()
    if '@' not in email:parser.error('Provide a valid email')
    password=getpass.getpass('Password (at least 12 characters): ')
    if len(password)<12:parser.error('Password is too short')
    if password!=getpass.getpass('Repeat password: '):parser.error('Passwords differ')
    init_db()
    with connect() as db:
        if db.execute('SELECT 1 FROM operators WHERE email=?',(email,)).fetchone():
            parser.error('Account already exists')
        db.execute('INSERT INTO operators(email,password_hash,role) VALUES (?,?,?)',(email,_password_hash(password),args.role))
    print(f'Created {args.role}: {email}')

if __name__=='__main__':main()
