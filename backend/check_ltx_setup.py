"""Read-only prerequisites for the pinned LTX/Q8 setup; never downloads weights."""
import importlib.metadata
import re
import shutil
import struct
import subprocess
import sys


def main():
    errors = []
    print(f"Python {sys.version.split()[0]}, {struct.calcsize('P') * 8}-bit")
    if sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8:
        errors.append("Use 64-bit Python 3.12 for this pinned environment.")
    for name in ('git', 'cl', 'nvcc'):
        path = shutil.which(name)
        print(f"{name}: {path or 'MISSING'}")
        if not path:
            errors.append(f"{name} must be available in this terminal before Q8 setup.")
    if shutil.which('nvcc'):
        result = subprocess.run(['nvcc', '--version'], capture_output=True, text=True, timeout=15)
        match = re.search(r'release (\d+)\.(\d+)', result.stdout)
        if result.returncode or not match or tuple(map(int, match.groups())) < (12, 8):
            errors.append("CUDA Toolkit 12.8 or later is required.")
        elif int(match[1]) != 12:
            errors.append("The pinned PyTorch cu128 build needs a compatible CUDA 12 toolkit, not a different major version.")
    try:
        import torch
        print(f"PyTorch {torch.__version__}; CUDA runtime {torch.version.cuda}")
        if not torch.cuda.is_available():
            errors.append("CUDA is unavailable to PyTorch.")
        else:
            free, total = torch.cuda.mem_get_info(0)
            print(f"GPU: {torch.cuda.get_device_name(0)}; free {free / 1024**3:.2f}/{total / 1024**3:.2f} GiB")
            print("This diagnostic does not unload Ollama. Generation checks free memory after unloading the planner.")
    except ImportError:
        errors.append("PyTorch is missing; install the pinned cu128 build.")
    for name in ('ltx-video', 'av', 'diffusers', 'transformers', 'accelerate', 'huggingface-hub', 'setuptools'):
        try:
            print(f"{name}: {importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"{name}: not installed")
    for error in errors:
        print('BLOCKED: ' + error)
    print('No installation, kernel compilation, inference or model download was attempted.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
