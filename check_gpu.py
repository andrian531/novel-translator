import subprocess
import sys
import re

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout + r.stderr
    except Exception:
        return ""

def get_cuda_version():
    out = run(["nvidia-smi"])
    m = re.search(r'CUDA Version:\s*(\d+)\.(\d+)', out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def get_vram_mb_nvidia():
    """Get VRAM in MB directly from nvidia-smi, no torch needed."""
    out = run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])
    try:
        return int(out.strip().splitlines()[0].strip())
    except Exception:
        return 0

def get_gpu_name_nvidia():
    out = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    name = out.strip().splitlines()[0].strip() if out.strip() else "NVIDIA GPU"
    return name

def get_torch_cuda_url(cuda_major):
    py_minor = sys.version_info.minor
    py_major = sys.version_info.major
    if py_major == 3 and py_minor >= 13:
        if cuda_major >= 12:
            return "cu124", "https://download.pytorch.org/whl/cu124"
        elif cuda_major == 11:
            return "cu118", "https://download.pytorch.org/whl/cu118"
        else:
            return "cpu", None
    else:
        if cuda_major >= 12:
            return "cu121", "https://download.pytorch.org/whl/cu121"
        elif cuda_major == 11:
            return "cu118", "https://download.pytorch.org/whl/cu118"
        else:
            return "cpu", None

def detect_gpu_vendor():
    out = run(["nvidia-smi", "-L"])
    if "GPU" in out and ("NVIDIA" in out.upper() or "GeForce" in out or "RTX" in out or "GTX" in out):
        return "nvidia"
    out = run(["rocm-smi", "--showproductname"])
    if out and "error" not in out.lower() and len(out.strip()) > 0:
        return "amd"
    out = run(["wmic", "path", "win32_VideoController", "get", "name"])
    out_lower = out.lower()
    if "nvidia" in out_lower:
        return "nvidia"
    if "amd" in out_lower or "radeon" in out_lower:
        return "amd"
    if "intel" in out_lower:
        return "intel"
    return "unknown"

def ollama_recommendation(vram_gb):
    """Return (recommended_models, reason) based on VRAM in GB."""
    # Model VRAM requirements:
    #   qwen2.5:3b          ~2.0 GB
    #   dolphin-mistral:7b  ~4.1 GB
    #   qwen2.5:7b          ~4.7 GB
    #   gemma2:9b           ~5.4 GB
    #   gemma3:9b           ~5.4 GB
    #   gemma3:12b          ~8.1 GB
    if vram_gb >= 10:
        return "qwen2.5:7b,gemma3:12b,gemma3:9b", f"{vram_gb}GB VRAM: gemma3:12b runs comfortably"
    elif vram_gb >= 6:
        return "qwen2.5:7b,gemma2:9b,gemma3:9b", f"{vram_gb}GB VRAM: 7-9B models run comfortably"
    elif vram_gb >= 4:
        return "qwen2.5:7b,dolphin-mistral:7b", f"{vram_gb}GB VRAM: 7B models fit with minimal overhead"
    elif vram_gb >= 2:
        return "qwen2.5:3b", f"{vram_gb}GB VRAM: use qwen2.5:3b (lighter 3B model)"
    else:
        return "qwen2.5:3b", f"{vram_gb}GB VRAM: only small models, consider CPU mode"

def nllb_recommendation(vram_gb):
    if vram_gb >= 4:
        return "1.3B", "4GB+ VRAM: 1.3B model gives better accuracy"
    else:
        return "600M", "<4GB VRAM: 600M model is safer"

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"

    if mode == "detect":
        vendor = detect_gpu_vendor()
        print(f"GPU_VENDOR={vendor}")

        if vendor == "nvidia":
            gpu_name = get_gpu_name_nvidia()
            vram_mb  = get_vram_mb_nvidia()
            vram_gb  = round(vram_mb / 1024, 1) if vram_mb else 0

            print(f"GPU_NAME={gpu_name}")
            print(f"VRAM={vram_gb}")

            cuda_major, cuda_minor = get_cuda_version()
            if cuda_major:
                print(f"CUDA_VERSION={cuda_major}.{cuda_minor}")
                tag, url = get_torch_cuda_url(cuda_major)
                print(f"TORCH_TAG={tag}")
                print(f"TORCH_URL={url if url else 'none'}")
            else:
                print("CUDA_VERSION=unknown")
                print("TORCH_TAG=cu121")
                print("TORCH_URL=https://download.pytorch.org/whl/cu121")

            rec, reason = ollama_recommendation(vram_gb)
            print(f"OLLAMA_RECOMMENDED={rec}")
            print(f"OLLAMA_REASON={reason}")

            nllb_rec, nllb_reason = nllb_recommendation(vram_gb)
            print(f"NLLB_RECOMMENDED={nllb_rec}")
            print(f"NLLB_RECOMMENDED_REASON={nllb_reason}")

        elif vendor == "amd":
            print("GPU_NAME=AMD GPU")
            print("VRAM=0")
            print("CUDA_VERSION=ROCm")
            print("TORCH_TAG=rocm5.6")
            print("TORCH_URL=https://download.pytorch.org/whl/rocm5.6")
            print("OLLAMA_RECOMMENDED=qwen2.5:7b,gemma2:9b")
            print("OLLAMA_REASON=AMD GPU: 7-9B models generally supported")
            print("NLLB_RECOMMENDED=600M")
            print("NLLB_RECOMMENDED_REASON=AMD GPU: 600M model is safer")
        else:
            print("GPU_NAME=CPU only")
            print("VRAM=0")
            print("CUDA_VERSION=none")
            print("TORCH_TAG=cpu")
            print("TORCH_URL=none")
            print("OLLAMA_RECOMMENDED=qwen2.5:3b")
            print("OLLAMA_REASON=No GPU: use qwen2.5:3b for reasonable CPU speed")
            print("NLLB_RECOMMENDED=600M")
            print("NLLB_RECOMMENDED_REASON=No GPU: 600M model runs well on CPU")

    elif mode == "verify":
        # Used after torch is installed — confirms CUDA is active via torch
        cuda_ok = False
        mps_ok  = False
        try:
            import torch
            cuda_ok = torch.cuda.is_available()
            if not cuda_ok:
                mps_ok = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        except ImportError:
            pass

        print("CUDA_OK=true" if cuda_ok else "CUDA_OK=false")

        if cuda_ok:
            print("GPU_DEVICE=cuda")
            try:
                import torch
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
                print(f"GPU_NAME={torch.cuda.get_device_name(0)}")
                print(f"VRAM={vram_gb}")
                nllb_rec, nllb_reason = nllb_recommendation(vram_gb)
                print(f"NLLB_RECOMMENDED={nllb_rec}")
                print(f"NLLB_RECOMMENDED_REASON={nllb_reason}")
            except Exception:
                print("NLLB_RECOMMENDED=600M")
                print("NLLB_RECOMMENDED_REASON=VRAM unknown: 600M model is safer")
        elif mps_ok:
            print("GPU_DEVICE=mps")
            print("NLLB_RECOMMENDED=1.3B")
            print("NLLB_RECOMMENDED_REASON=Apple MPS available: 1.3B model supported")
        else:
            print("GPU_DEVICE=cpu")
            print("NLLB_RECOMMENDED=600M")
            print("NLLB_RECOMMENDED_REASON=No GPU: 600M model runs well on CPU")
