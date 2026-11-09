import argparse

from .server import serve


def main():
    ap = argparse.ArgumentParser(prog="python3 -m evaldiff")
    ap.add_argument("command", nargs="?", default="serve", choices=["serve"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    serve(args.host, args.port)


main()
