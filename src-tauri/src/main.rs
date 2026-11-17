//! Desktop shell: starts the local Python engine, waits until it answers, then opens the
//! studio window on it. The engine is stopped when the app exits.
//!
//! Engine lookup order:
//!   1. CLIPFORGE_ENGINE env var (path to an executable)
//!   2. bundled `engine/clipforge-engine(.exe)` next to the app (PyInstaller build, see INSTALLATION.md)
//!   3. development: `<repo>/backend/.venv` Python running `-m clipforge.main`
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8756;

struct Engine(Mutex<Option<Child>>);

fn port_open() -> bool {
    TcpStream::connect_timeout(&([127, 0, 0, 1], PORT).into(), Duration::from_millis(300)).is_ok()
}

fn hide_console(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let _ = cmd;
}

fn engine_command(resource_dir: Option<PathBuf>) -> Option<Command> {
    let exe = if cfg!(windows) { "clipforge-engine.exe" } else { "clipforge-engine" };
    if let Ok(p) = std::env::var("CLIPFORGE_ENGINE") {
        return Some(Command::new(p));
    }
    if let Some(dir) = resource_dir {
        let bundled = dir.join("engine").join(exe);
        if bundled.is_file() {
            return Some(Command::new(bundled));
        }
    }
    // Development: repo/backend/.venv
    let repo = Path::new(env!("CARGO_MANIFEST_DIR")).parent()?.to_path_buf();
    let backend = repo.join("backend");
    let py = if cfg!(windows) { backend.join(".venv/Scripts/python.exe") } else { backend.join(".venv/bin/python") };
    if py.is_file() {
        let mut c = Command::new(py);
        c.args(["-m", "clipforge.main"]).current_dir(&backend);
        return Some(c);
    }
    None
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Engine(Mutex::new(None)))
        .setup(|app| {
            // An engine that is already running (e.g. started from a terminal) is reused.
            if !port_open() {
                let mut cmd = engine_command(app.path().resource_dir().ok()).ok_or(
                    "ClipForge's engine was not found. Reinstall the app, or see INSTALLATION.md for development setup.",
                )?;
                cmd.args(["--port", &PORT.to_string(), "--parent-pid", &std::process::id().to_string()]);
                hide_console(&mut cmd);
                let child = cmd.spawn().map_err(|e| format!("Could not start the ClipForge engine: {e}"))?;
                *app.state::<Engine>().0.lock().unwrap() = Some(child);
            }
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let t0 = Instant::now();
                while !port_open() && t0.elapsed() < Duration::from_secs(90) {
                    std::thread::sleep(Duration::from_millis(250));
                }
                let url = if port_open() {
                    WebviewUrl::External(format!("http://127.0.0.1:{PORT}/").parse().unwrap())
                } else {
                    WebviewUrl::App("index.html".into())
                };
                let _ = WebviewWindowBuilder::new(&handle, "main", url)
                    .title("ClipForge AI")
                    .inner_size(1440.0, 900.0)
                    .min_inner_size(1024.0, 640.0)
                    .build();
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building ClipForge");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(mut child) = handle.state::<Engine>().0.lock().unwrap().take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    });
}
