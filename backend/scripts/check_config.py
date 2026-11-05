"""Check required configuration presence without printing secrets or making requests."""
import argparse
import sqlite3
from app import config
from app.db import database_path
from app.understanding import selected_provider, model_for


def check(mode, has_operator=False):
    issues=[]
    if mode=='dashboard' and not has_operator:
        if not config.AUTH_BOOTSTRAP_EMAIL or '@' not in config.AUTH_BOOTSTRAP_EMAIL:
            issues.append('Set AUTH_BOOTSTRAP_EMAIL for the first administrator.')
        if len(config.AUTH_BOOTSTRAP_PASSWORD)<12:
            issues.append('Set AUTH_BOOTSTRAP_PASSWORD to at least 12 characters.')
    if mode!='dashboard':
        for name in ('META_VERIFY_TOKEN','META_APP_SECRET','META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_GRAPH_VERSION'):
            if not getattr(config,name):issues.append(f'Set {name}.')
        if not config.CONVERSATION_ENABLED:issues.append('Enable CONVERSATION_ENABLED for WhatsApp intake.')
        provider=selected_provider()
        key={'openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY'}.get(provider)
        if key and not getattr(config,key):issues.append(f'Set {key}.')
        if provider not in {'openai','gemini','ollama'}:issues.append('Choose a supported CONVERSATION_PROVIDER.')
        elif not model_for(provider):issues.append('Set the model for your selected conversation provider.')
    if mode=='whatsapp-voice':
        if config.STT_PROVIDER=='openai':
            for name in ('OPENAI_API_KEY','OPENAI_STT_MODEL'):
                if not getattr(config,name):issues.append(f'Set {name} for voice notes.')
        elif config.STT_PROVIDER=='gemini':
            if not config.GEMINI_API_KEY:issues.append('Set GEMINI_API_KEY for voice notes.')
            if not (config.GEMINI_STT_MODEL or config.GEMINI_MODEL):issues.append('Set a Gemini transcription model.')
        else:issues.append('Choose openai or gemini for STT_PROVIDER.')
    return issues


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['dashboard','whatsapp-text','whatsapp-voice'],default='whatsapp-voice')
    args=parser.parse_args()
    has_operator=False
    path=database_path()
    if path.is_file():
        try:
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                has_operator=bool(db.execute('SELECT 1 FROM operators WHERE active=1 LIMIT 1').fetchone())
        except sqlite3.Error:
            pass
    issues=check(args.mode,has_operator)
    for issue in issues:print('- '+issue)
    if args.mode!='dashboard' and not config.WHATSAPP_CONTACT_NUMBER.isdigit():
        print('Optional: set WHATSAPP_CONTACT_NUMBER to enable website WhatsApp links.')
    if issues:raise SystemExit(1)
    print('Required settings are present. Live credentials, model access and webhook reachability still need verification.')

if __name__=='__main__':main()
