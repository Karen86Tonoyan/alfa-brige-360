import argparse
import requests

API_URL = "http://127.0.0.1:8000"

def cmd_health(args):
    r = requests.get(f"{API_URL}/health", timeout=5)
    print(r.status_code, r.json())

def cmd_status(args):
    r = requests.get(f"{API_URL}/status", timeout=5)
    print(r.status_code, r.json())

def main():
    parser = argparse.ArgumentParser(prog="alfa-core")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Sprawdź health ALFA_CORE")
    p_health.set_defaults(func=cmd_health)

    p_status = sub.add_parser("status", help="Sprawdź status ALFA_CORE")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
