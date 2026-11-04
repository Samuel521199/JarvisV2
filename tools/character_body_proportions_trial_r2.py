"""Compatibility entry; use the apps/studio3d Blender bootstrap or project PYTHONPATH."""
from pathlib import Path

def main():
    from adapters.studio3d.learning_worker import install_runtime
    install_runtime(Path(__file__).resolve().parents[1]/"apps/studio3d/character_body_proportions_worker_r2.py")
    from adapters.studio3d.character_body_proportions_trial_r2 import main as run
    return run()

if __name__ == "__main__":
    main()
