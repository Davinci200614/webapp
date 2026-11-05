"""Check live AI understanding using synthetic text; never print keys or user data."""
import argparse
import asyncio
import json
import time
from app import config
from app.ai import AIError
from app.understanding import understand,selected_provider,selected_model

async def check():
    started=time.monotonic()
    print(json.dumps({'provider':selected_provider(),'model':selected_model(),'timeout_seconds':config.CONVERSATION_TIMEOUT_SECONDS}),flush=True)
    try:
        result=await understand('بغيت تراكتور للحرث',{'active_task':'none','draft':{},'pending_field':None})
    except AIError as exc:
        print(json.dumps({'outcome':'error','error_code':exc.code,'duration_ms':round((time.monotonic()-started)*1000)}))
        print('Connection/timeout: check network, firewall and API reachability. Authentication/model errors: check the configured key and model access.')
        return 1
    print(json.dumps({'outcome':'ok','task':result.task,'duration_ms':round((time.monotonic()-started)*1000)}))
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout',type=float,default=None)
    args=parser.parse_args()
    if args.timeout is not None:
        if args.timeout<=0:parser.error('--timeout must be positive')
        config.CONVERSATION_TIMEOUT_SECONDS=args.timeout
    raise SystemExit(asyncio.run(check()))

if __name__=='__main__':main()
