from pathlib import Path

import yaml


OPTICS_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_optics_config(path=OPTICS_CONFIG_PATH):
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    base_dir = path.parent

    cfg["project_dir"] = base_dir
    cfg["config_path"] = path
    cfg["paths"]["results_dir"] = _resolve_path(base_dir, cfg["paths"]["results_dir"])
    cfg["camera"]["image_size_px"] = _as_int_pair(
        cfg["camera"]["image_size_px"],
        "camera.image_size_px",
    )
    cfg["optics"]["lenslet_pitch_px"] = float(
        cfg["optics"]["lenslet_pitch_m"] / cfg["camera"]["pixel_pitch_m"]
    )
    cfg["optics"]["zernike_aperture_diameter_m"] = float(cfg["optics"]["zernike_aperture_diameter_m"])
    return cfg


def _resolve_path(base_dir, value):
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def _as_int_pair(value, name):
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two values.")
    return tuple(int(v) for v in value)
