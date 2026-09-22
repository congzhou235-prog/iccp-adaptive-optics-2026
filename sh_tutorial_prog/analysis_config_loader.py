from pathlib import Path

import yaml


ANALYSIS_CONFIG_PATH = Path(__file__).with_name("analysis_config.yaml")


def load_analysis_config(path=ANALYSIS_CONFIG_PATH, optics_cfg=None):
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["config_path"] = path

    cfg["zernike"]["indices"] = tuple(int(j) for j in cfg["zernike"]["indices"])
    cfg["gate"]["half_cols"] = float(cfg["gate"]["half_cols"])
    cfg["gate"]["half_rows"] = float(cfg["gate"]["half_rows"])

    if optics_cfg is not None:
        lenslet_pitch_px = float(optics_cfg["optics"]["lenslet_pitch_px"])
        cfg["spot_detection"]["max_match_distance_px"] = float(
            cfg["spot_detection"]["max_match_distance_lenslet_pitch"] * lenslet_pitch_px
        )

    return cfg
