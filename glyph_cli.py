#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple CLI client for Glyph server.

Usage:
  python glyph_cli.py --question "abre el navegador y escribe gemini" [--dry-run]
"""
import argparse
import json
import sys

try:
    import requests
except Exception:
    requests = None

DEFAULT_URL = "http://127.0.0.1:5000"


def send_question(url, question, dry_run=False):
    payload = {"question": question, "dry_run": dry_run}
    if requests is None:
        from urllib import request as urlreq
        data = json.dumps(payload).encode('utf-8')
        req = urlreq.Request(url + '/ask', data=data, headers={'Content-Type': 'application/json'})
        with urlreq.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    else:
        r = requests.post(url + '/ask', json=payload, timeout=30)
        try:
            return r.json()
        except Exception:
            return {"status": "error", "text": r.text}


def accept_pending(url, pid, dry_run=False, learn=False):
    payload = {"pending_id": pid, "execute": True, "dry_run": dry_run, "learn": learn}
    if requests is None:
        from urllib import request as urlreq
        data = json.dumps(payload).encode('utf-8')
        req = urlreq.Request(url + '/pending/accept', data=data, headers={'Content-Type': 'application/json'})
        with urlreq.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    else:
        r = requests.post(url + '/pending/accept', json=payload, timeout=30)
        try:
            return r.json()
        except Exception:
            return {"status": "error", "text": r.text}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=DEFAULT_URL, help='Glyph server URL')
    p.add_argument('--question', '-q', help='Natural language command to send')
    p.add_argument('--dry-run', action='store_true', help='Simulate without executing')
    p.add_argument('--accept-pending', help='Accept pending_id immediately')
    p.add_argument('--learn', action='store_true', help='Save plan when accepting pending')
    args = p.parse_args()

    if args.accept_pending:
        res = accept_pending(args.url, args.accept_pending, dry_run=args.dry_run, learn=args.learn)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if not args.question:
        print('Specify --question or --accept-pending. Example:')
        print('  python glyph_cli.py --question "abre el navegador y escribe gemini" --dry-run')
        sys.exit(1)

    res = send_question(args.url, args.question, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    pid = res.get('pending_id') if isinstance(res, dict) else None
    if pid:
        try:
            ans = input(f"Pending created {pid}. Accept and execute now? (y/N): ")
            if ans.lower().startswith('y'):
                r2 = accept_pending(args.url, pid, dry_run=False, learn=args.learn)
                print(json.dumps(r2, ensure_ascii=False, indent=2))
        except Exception:
            pass


if __name__ == '__main__':
    main()
