"""Cross-platform server using Waitress (works on Windows, macOS and Linux).

    python serve.py                 # http://127.0.0.1:5000 (this machine only)
    HOST=0.0.0.0 python serve.py    # reachable from other devices on the network
    OPEN_BROWSER=1 python serve.py  # also open the store in your browser
"""
import os
import threading
import webbrowser

from waitress import serve

from wsgi import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"Velora Market running on http://{host}:{port}  (Ctrl+C to stop)")
    if host == "0.0.0.0":
        print("Listening on all interfaces — open http://<this-VM-IP>:%d from another device." % port)
    if os.environ.get("OPEN_BROWSER") == "1":
        shown = "127.0.0.1" if host == "0.0.0.0" else host
        threading.Timer(1.5, webbrowser.open, args=(f"http://{shown}:{port}",)).start()
    serve(app, host=host, port=port, threads=8)
