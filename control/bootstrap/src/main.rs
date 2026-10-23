//! Small native stop/recovery entry. No cloud, Python framework or third-party crates.
//! A stop marker is cooperative control, NOT an OS security boundary.
use std::env;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

fn checked(path: &Path) -> io::Result<PathBuf> {
    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        env::current_dir()?.join(path)
    };
    for ancestor in absolute.ancestors() {
        if let Ok(info) = fs::symlink_metadata(ancestor) {
            #[cfg(windows)]
            {
                use std::os::windows::fs::MetadataExt;
                if info.file_attributes() & 0x400 != 0 {
                    return Err(io::Error::other("reparse path rejected"));
                }
            }
            if info.file_type().is_symlink() {
                return Err(io::Error::other("symlink rejected"));
            }
        }
    }
    fs::canonicalize(absolute)
}

fn stopped(root: &Path) -> bool {
    root.join("state/STOP").exists() || root.join("state/LATCH").exists()
}

fn stop(root: &Path, latch: bool) -> io::Result<()> {
    let state = checked(&root.join("state"))?;
    let target = state.join(if latch { "LATCH" } else { "STOP" });
    match OpenOptions::new().write(true).create_new(true).open(target) {
        Ok(mut file) => {
            let epoch = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos();
            write!(file, "native-{}-{}", std::process::id(), epoch)?;
            file.sync_all()?;
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => (),
        Err(error) => return Err(error),
    }
    Ok(())
}

fn value(args: &[String], key: &str) -> io::Result<String> {
    args.iter()
        .position(|item| item == key)
        .and_then(|pos| args.get(pos + 1))
        .cloned()
        .ok_or_else(|| io::Error::other(format!("missing {}", key)))
}

fn run() -> io::Result<u8> {
    let args: Vec<String> = env::args().skip(1).collect();
    let operation = args.first().map(String::as_str).unwrap_or("help");
    if operation == "help" || operation == "--help" {
        println!("jarvis-control status|stop|latch --data-root PATH");
        println!("jarvis-control run --data-root PATH --project-root PATH --python EXE");
        println!("Recovery never deletes a latch or restores old task/grant state.");
        return Ok(0);
    }
    let root = checked(Path::new(&value(&args, "--data-root")?))?;
    checked(&root.join("state"))?;
    match operation {
        "status" => {
            println!(
                "control={}; host_liveness=not_inspected",
                if root.join("state/LATCH").exists() {
                    "latched"
                } else if stopped(&root) {
                    "stopped"
                } else {
                    "ready"
                }
            );
            Ok(0)
        }
        "stop" | "latch" => {
            stop(&root, operation == "latch")?;
            println!("stop marker persisted; in-flight effects require host reconciliation");
            Ok(0)
        }
        "run" => {
            if stopped(&root) {
                return Err(io::Error::other("stopped; automatic restart refused"));
            }
            let project = checked(Path::new(&value(&args, "--project-root")?))?;
            let entry = checked(&project.join("apps/cli/main.py"))?;
            let python = checked(Path::new(&value(&args, "--python")?))?;
            let mut child = Command::new(python)
                .arg("-I")
                .arg("-B")
                .arg(entry)
                .arg("--data-root")
                .arg(&root)
                .arg("run")
                .current_dir(project)
                .spawn()?;
            loop {
                if let Some(exit) = child.try_wait()? {
                    return Ok(if exit.success() { 0 } else { 2 });
                }
                if stopped(&root) {
                    // Current host exposes no subprocess tool. Future worker trees need OS job control.
                    let _ = child.kill();
                    child.wait()?;
                    println!("host exited after stop; inspect UNKNOWN actions before resuming");
                    return Ok(2);
                }
                thread::sleep(Duration::from_millis(50));
            }
        }
        _ => Err(io::Error::other("unknown operation")),
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            eprintln!("control error: {}", error);
            ExitCode::from(2)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn arguments_require_a_value() {
        assert!(value(&["--data-root".into()], "--data-root").is_err());
    }
    #[test]
    fn persistent_stop_is_idempotent_and_latch_is_separate() {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = env::temp_dir().join(format!(
            "jarvis-control-test-{}-{}",
            std::process::id(),
            stamp
        ));
        fs::create_dir_all(root.join("state")).unwrap();
        assert!(!stopped(&root));
        stop(&root, false).unwrap();
        let generation = fs::read(root.join("state/STOP")).unwrap();
        stop(&root, false).unwrap();
        assert_eq!(generation, fs::read(root.join("state/STOP")).unwrap());
        stop(&root, true).unwrap();
        fs::remove_file(root.join("state/STOP")).unwrap();
        assert!(stopped(&root));
        // Only exact files made by this test; never recursive computed-path deletion.
        fs::remove_file(root.join("state/LATCH")).unwrap();
        fs::remove_dir(root.join("state")).unwrap();
        fs::remove_dir(root).unwrap();
    }
}
