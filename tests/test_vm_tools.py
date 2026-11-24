"""VM tooling: the health check, the port-conflict message, and the service file."""
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_doctor_passes_on_a_ready_store(tmp_path):
    from velora import create_app
    from velora.cli import init_database
    from velora.doctor import run
    from velora.seed import seed
    ready = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'ready.db'}", UPLOAD_FOLDER=str(tmp_path / "up"))
    lines = []
    with ready.app_context():
        init_database()
        seed()
        assert run(lines.append) is True, lines
    text = "\n".join(lines)
    assert "Foreign keys enforced" in text and "pages and API endpoints answer 200" in text and "[FAIL]" not in text


def test_doctor_explains_an_empty_database(tmp_path):
    from velora import create_app
    from velora.doctor import run
    empty = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'empty.db'}")
    lines = []
    with empty.app_context():
        assert run(lines.append) is False
    assert any("init-db" in l for l in lines)


def test_serve_says_clearly_when_the_port_is_taken():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        out = subprocess.run([sys.executable, "serve.py"], cwd=ROOT, capture_output=True, text=True, timeout=60,
                             env={"PORT": str(port), "HOST": "127.0.0.1", "PATH": "/usr/bin:/bin", "VELORA_ENV": "development"})
    assert out.returncode == 1 and f"Port {port} is already in use" in out.stdout


def test_service_file_and_scripts_are_complete():
    unit = (ROOT / "deploy" / "aurelune.service").read_text()
    for needed in ("Restart=on-failure", "WantedBy=multi-user.target", "@DIR@/.venv/bin/python serve.py", "upgrade-demo"):
        assert needed in unit
    for script in ("vm-setup.sh", "vm-check.sh"):
        path = ROOT / "scripts" / script
        assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
        assert b"\r\n" not in path.read_bytes()  # Linux scripts must have LF line endings
    setup = (ROOT / "scripts" / "vm-setup.sh").read_text()
    assert "HOST 0.0.0.0" in setup and "systemctl enable aurelune" in setup and "vm-check.sh" in setup


def test_api_demo_script_and_presentation_script_are_complete():
    demo = ROOT / "scripts" / "api-demo.sh"
    assert subprocess.run(["bash", "-n", str(demo)]).returncode == 0 and b"\r\n" not in demo.read_bytes()
    text = demo.read_text()
    for needed in ("-X PATCH", "-X DELETE", "Idempotency-Key", "/rates", "/geocode/reverse", "/products", "401", "422", "409"):
        assert needed in text or needed in ("-X PATCH", "-X DELETE") and ("PATCH" in text and "DELETE" in text), needed
    script = (ROOT / "docs" / "PRESENTATION_SCRIPT.md").read_text(encoding="utf-8")
    for speaker in ("Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4"):
        assert f"## {speaker}:" in script
    # every row of both rubrics is mapped to a speaker
    for row in ("IPT: Core e-commerce", "IPT: API integration and design", "IPT: Python back end and database",
                "IPT: Virtual machine and localhost", "IPT: UI/UX and documentation", "PlatTech: Error-free execution",
                "PlatTech: Localhost and VM network", "PlatTech: VM provisioning", "PlatTech: Service and database reliability",
                "PlatTech: VM verification"):
        assert row in script, row
    # the commands the speakers type must exist in the project
    for command in ("scripts/vm-check.sh", "scripts/api-demo.sh", "systemctl status aurelune", "journalctl -u aurelune"):
        assert command in script
    assert (ROOT / "scripts" / "vm-check.sh").is_file() and (ROOT / "scripts" / "api-demo.sh").is_file()
