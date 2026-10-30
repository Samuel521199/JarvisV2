"""Development launcher; stable workbench launch behaviour is unchanged."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host.development_runtime import main

if __name__ == '__main__':
    main()
