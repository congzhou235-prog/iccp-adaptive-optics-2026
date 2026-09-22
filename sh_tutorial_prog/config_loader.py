from analysis_config_loader import load_analysis_config
from optics_config_loader import load_optics_config


def load_config(optics_path=None, analysis_path=None):
    optics_cfg = load_optics_config() if optics_path is None else load_optics_config(optics_path)
    analysis_cfg = (
        load_analysis_config(optics_cfg=optics_cfg)
        if analysis_path is None
        else load_analysis_config(analysis_path, optics_cfg=optics_cfg)
    )

    cfg = dict(optics_cfg)
    cfg.update(analysis_cfg)
    cfg["optics_config_path"] = optics_cfg["config_path"]
    cfg["analysis_config_path"] = analysis_cfg["config_path"]
    return cfg
