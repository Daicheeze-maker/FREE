"""Cross-platform server using Waitress (works on Windows, macOS and Linux).

    python serve.py                 # http://127.0.0.1:5000 (this machine only)
    HOST=0.0.0.0 python serve.py    # reachable from other devices, and through VirtualBox port forwarding
    PORT=5050 python serve.py       # another port
    OPEN_BROWSER=1 python serve.py  # also open the store in your browser
"""
import logging
import os
import socket
import sys
import threading
import webbrowser

from waitress import serve

from wsgi import app


def port_taken(host, port):
    """True if something already listens on this port (another copy of the store, or another program)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":  # Linux/macOS: ignore closed connections still waiting (TIME_WAIT) after a quick restart
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0" if host == "0.0.0.0" else host, port))
        except OSError:
            return True
    return False


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    name = app.config["BRAND_NAME"]
    shown = "127.0.0.1" if host == "0.0.0.0" else host
    if port_taken(host, port):
        print(f"\n  Port {port} is already in use, so {name} can't start on it.")
        print(f"  - If the store is already running (for example as the 'aurelune' service), just open http://{shown}:{port}")
        print(f"  - Or start it on another port:  PORT=5050 (Windows: set PORT=5050) and run again.\n")
        sys.exit(1)
    logging.getLogger("waitress").setLevel(logging.INFO)
    print(f"{name} running on http://{shown}:{port}  (Ctrl+C to stop)")
    if host == "0.0.0.0":
        print(f"Listening on all network interfaces: VirtualBox port forwarding and other devices can reach port {port}.")
    if os.environ.get("OPEN_BROWSER") == "1":
        threading.Timer(1.5, webbrowser.open, args=(f"http://{shown}:{port}",)).start()
    serve(app, host=host, port=port, threads=8, ident=name)
