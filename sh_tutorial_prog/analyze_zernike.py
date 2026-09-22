from datetime import datetime
from pathlib import Path
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis_config_loader import load_analysis_config
from calibration import LATEST_CALIBRATION_FILE, load_calibration_file
from optics_config_loader import load_optics_config
from spot_analysis import detect_spots, load_image, match_spots
from wavefront_reconstruction import ZERNIKE_META, gate_by_pupil_box, reconstruct_zernike


DATASET_ROOT = Path(__file__).with_name("dataset")
GROUP_NAME = "first_10_zernike"
SAMPLE = "all"
CALIBRATION_FILE = LATEST_CALIBRATION_FILE


def run_analysis(
    group_name=GROUP_NAME,
    sample=SAMPLE,
    dataset_root=DATASET_ROOT,
    calibration_file=CALIBRATION_FILE,
    optics_config=None,
    analysis_config=None,
):
    optics_cfg = load_optics_config(optics_config) if optics_config else load_optics_config()
    analysis_cfg = (
        load_analysis_config(analysis_config, optics_cfg=optics_cfg)
        if analysis_config
        else load_analysis_config(optics_cfg=optics_cfg)
    )
    calibration = load_calibration_file(calibration_file)

    group_dir = Path(dataset_root) / str(group_name)
    reference_path = find_first_existing(group_dir, ["reference_flat.png", "reference.png", "reference_flat.npy", "reference.npy"])
    reference_image = load_image(reference_path)
    reference_spots = detect_spots(reference_image, analysis_cfg["spot_detection"])
    samples = select_samples(find_samples(group_dir), sample)

    output_dir = optics_cfg["paths"]["results_dir"] / f"zernike_{group_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for sample_info in samples:
        sample_output = output_dir / sample_info["name"]
        sample_output.mkdir(parents=True, exist_ok=True)
        measured_coeffs, comparison, info = analyze_one_sample(
            reference_image,
            reference_spots,
            sample_info,
            calibration,
            optics_cfg,
            analysis_cfg,
            sample_output,
        )
        measured_coeffs.insert(0, "sample", sample_info["name"])
        measured_coeffs.to_csv(sample_output / "measured_zernike_coeffs.csv", index=False)
        measured_coeffs.to_csv(output_dir / f"{sample_info['name']}_measured_zernike_coeffs.csv", index=False)

        if comparison is not None:
            comparison.to_csv(sample_output / "true_vs_measured_zernike_coeffs.csv", index=False)
            save_true_vs_measured_plot(comparison, sample_output / "true_vs_measured_zernike.png")
            summary_rows.extend(comparison.assign(sample=sample_info["name"]).to_dict("records"))

        print(
            f"{sample_info['name']}: matched {info['matched_spots']} spots, "
            f"fit {info['fit_spots']} spots"
        )

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(output_dir / "group_true_vs_measured_zernike_coeffs.csv", index=False)

    print(f"Output: {output_dir}")
    return output_dir


def analyze_one_sample(reference_image, reference_spots, sample_info, calibration, optics_cfg, analysis_cfg, output_dir):
    measurement_image = load_image(sample_info["measurement_path"])
    measurement_spots = detect_spots(measurement_image, analysis_cfg["spot_detection"])
    matches = match_spots(
        reference_spots,
        measurement_spots,
        analysis_cfg["spot_detection"]["max_match_distance_px"],
    )
    _, gate_matches = gate_by_pupil_box(matches, calibration, optics_cfg, analysis_cfg)
    measured_coeffs, info = reconstruct_zernike(gate_matches, calibration, optics_cfg, analysis_cfg)

    save_displacement_plot(
        measurement_image,
        gate_matches,
        calibration,
        output_dir / "spot_displacements_gate.png",
        analysis_cfg["visualization"]["arrow_gain"],
    )

    true_coeffs = load_true_coeffs(sample_info.get("truth_path"))
    comparison = build_comparison(true_coeffs, measured_coeffs, analysis_cfg) if true_coeffs is not None else None
    return measured_coeffs, comparison, info


def find_samples(group_dir):
    if not group_dir.exists():
        raise FileNotFoundError(f"Dataset group not found: {group_dir}")

    sample_dirs = sorted(path for path in group_dir.iterdir() if path.is_dir())
    samples = []
    for sample_dir in sample_dirs:
        measurement_path = find_first_existing(
            sample_dir,
            [
                "measurement.png",
                "measurement_zernike.png",
                "measurement_camera.png",
                "measurement.npy",
                "measurement_zernike.npy",
                "measurement_camera.npy",
            ],
            required=False,
        )
        if measurement_path is None:
            continue
        truth_path = find_first_existing(
            sample_dir,
            ["true_zernike_phase_coeffs.csv", "true_coeffs.csv"],
            required=False,
        )
        samples.append(
            {
                "name": sample_dir.name,
                "measurement_path": measurement_path,
                "truth_path": truth_path,
            }
        )

    if not samples:
        raise RuntimeError(f"No samples found in {group_dir}.")
    return samples


def select_samples(samples, sample):
    if str(sample).lower() == "all":
        return samples
    wanted = {name.strip() for name in str(sample).split(",") if name.strip()}
    selected = [item for item in samples if item["name"] in wanted]
    if not selected:
        raise ValueError(f"No selected samples found: {sample}")
    return selected


def find_first_existing(directory, names, required=True):
    directory = Path(directory)
    for name in names:
        path = directory / name
        if path.exists():
            return path
    if required:
        raise FileNotFoundError(f"None of these files were found in {directory}: {names}")
    return None


def load_true_coeffs(path):
    if path is None:
        return None
    table = pd.read_csv(path)
    if "true_phase_coeff_rad" in table.columns:
        value_column = "true_phase_coeff_rad"
    elif "coeff_rad" in table.columns:
        value_column = "coeff_rad"
    else:
        raise ValueError(f"True coefficient file must contain true_phase_coeff_rad or coeff_rad: {path}")
    return {int(row.zernike_j): float(getattr(row, value_column)) for row in table.itertuples(index=False)}


def build_comparison(true_coeffs, measured_coeffs, analysis_cfg):
    measured = measured_coeffs.set_index("zernike_j")["coeff_rad"].to_dict()
    rows = []
    for j in analysis_cfg["zernike"]["indices"]:
        n, m, name = ZERNIKE_META[int(j)]
        true_value = float(true_coeffs.get(int(j), 0.0))
        measured_value = float(measured.get(int(j), 0.0))
        rows.append(
            {
                "zernike_j": int(j),
                "n": int(n),
                "m": int(m),
                "name": name,
                "true_phase_coeff_rad": true_value,
                "measured_phase_coeff_rad": measured_value,
                "error_phase_coeff_rad": measured_value - true_value,
            }
        )
    return pd.DataFrame(rows)


def save_displacement_plot(image, matches, calibration, output_png, arrow_gain):
    vmin, vmax = np.percentile(image, [1.0, 99.8])
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin, vmax = float(np.min(image)), float(np.max(image))

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.imshow(image, cmap="gray", origin="upper", vmin=vmin, vmax=vmax)
    ax.scatter(matches["ref_x_px"], matches["ref_y_px"], s=12, c="cyan", label="reference")
    ax.scatter(matches["meas_x_px"], matches["meas_y_px"], s=12, c="orange", label="measurement")
    ax.quiver(
        matches["ref_x_px"],
        matches["ref_y_px"],
        matches["dx_px"] * float(arrow_gain),
        matches["dy_px"] * float(arrow_gain),
        color="red",
        angles="xy",
        scale_units="xy",
        scale=1,
        width=0.0025,
    )
    ax.scatter([calibration["center_x_px"]], [calibration["center_y_px"]], s=80, marker="+", c="lime")
    ax.axis("off")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_png, dpi=200)
    plt.close(fig)


def save_true_vs_measured_plot(comparison, output_png):
    x = np.arange(len(comparison))
    width = 0.38

    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.bar(x - width / 2.0, comparison["true_phase_coeff_rad"], width, label="true")
    ax.bar(x + width / 2.0, comparison["measured_phase_coeff_rad"], width, label="measured")
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(j)) for j in comparison["zernike_j"]])
    ax.set_xlabel("Zernike j")
    ax.set_ylabel("phase coefficient (rad)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_png, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Offline Zernike reconstruction from saved Shack-Hartmann images.")
    parser.add_argument("--group", default=GROUP_NAME)
    parser.add_argument("--sample", default=SAMPLE, help="Sample folder name, comma list, or all.")
    parser.add_argument("--dataset-root", type=Path, default=DATASET_ROOT)
    parser.add_argument("--calibration-file", type=Path, default=CALIBRATION_FILE)
    parser.add_argument("--optics-config", type=Path, default=None)
    parser.add_argument("--analysis-config", type=Path, default=None)
    args = parser.parse_args()
    run_analysis(
        group_name=args.group,
        sample=args.sample,
        dataset_root=args.dataset_root,
        calibration_file=args.calibration_file,
        optics_config=args.optics_config,
        analysis_config=args.analysis_config,
    )


if __name__ == "__main__":
    main()
