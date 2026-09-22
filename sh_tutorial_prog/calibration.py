from datetime import datetime
from pathlib import Path
import argparse
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis_config_loader import load_analysis_config
from optics_config_loader import load_optics_config
from spot_analysis import detect_spots, load_image, match_spots


DEFAULT_IMAGE_DIR = Path(__file__).with_name("calibration_pics")
LATEST_CALIBRATION_FILE = Path(__file__).with_name("results") / "latest_pupil_center_calibration.json"


def find_image_file(image_dir, stem):
    image_dir = Path(image_dir)
    for suffix in (".png", ".tif", ".tiff", ".bmp", ".jpg", ".jpeg", ".npy"):
        path = image_dir / f"{stem}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Calibration image not found: {image_dir / stem}.[png/npy]")


def load_calibration_images(image_dir):
    image_dir = Path(image_dir)
    return {
        "reference": load_image(find_image_file(image_dir, "reference_flat")),
        "defocus": load_image(find_image_file(image_dir, "measurement_defocus")),
        "tilt_x": load_image(find_image_file(image_dir, "measurement_tilt_x")),
        "tilt_y": load_image(find_image_file(image_dir, "measurement_tilt_y")),
    }


def compute_calibration_from_images(image_dir=DEFAULT_IMAGE_DIR, optics_cfg=None, analysis_cfg=None):
    images = load_calibration_images(image_dir)
    reference = images["reference"]
    defocus = images["defocus"]
    tilt_x = images["tilt_x"]
    tilt_y = images["tilt_y"]

    spot_params = analysis_cfg["spot_detection"]
    reference_spots = detect_spots(reference, spot_params)
    defocus_spots = detect_spots(defocus, spot_params)
    tilt_x_spots = detect_spots(tilt_x, spot_params)
    tilt_y_spots = detect_spots(tilt_y, spot_params)

    max_distance_px = spot_params["max_match_distance_px"]
    defocus_matches = match_spots(reference_spots, defocus_spots, max_distance_px)
    tilt_x_matches = match_spots(reference_spots, tilt_x_spots, max_distance_px)
    tilt_y_matches = match_spots(reference_spots, tilt_y_spots, max_distance_px)

    center_global = estimate_center(defocus_matches)
    defocus_gate_1 = gate_by_center(defocus_matches, center_global, optics_cfg, analysis_cfg)
    center_gate_1 = estimate_center(defocus_gate_1)
    defocus_gate_2 = gate_by_center(defocus_matches, center_gate_1, optics_cfg, analysis_cfg)
    center_final = estimate_center(defocus_gate_2)

    tilt_x_gate = gate_by_center(tilt_x_matches, center_final, optics_cfg, analysis_cfg)
    tilt_y_gate = gate_by_center(tilt_y_matches, center_final, optics_cfg, analysis_cfg)
    tilt_x_axis = estimate_axis(tilt_x_gate)
    tilt_y_axis = estimate_axis(tilt_y_gate)
    axes = make_axis_calibration(tilt_x_axis, tilt_y_axis)

    calibration = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": "offline_defocus_center_plus_tilt_axes",
        "center_x_px": center_final["center_x_px"],
        "center_y_px": center_final["center_y_px"],
        "center_steps": {
            "global": center_global,
            "gate_once": center_gate_1,
            "gate_twice": center_final,
        },
        "pupil_x_axis_image": axes["pupil_x_axis_image"],
        "pupil_y_axis_image": axes["pupil_y_axis_image"],
        "pupil_y_axis_orthogonalized_image": axes["pupil_y_axis_orthogonalized_image"],
        "pupil_x_rotation_deg_image_y_down": axes["pupil_x_rotation_deg_image_y_down"],
        "pupil_y_rotation_deg_image_y_down": axes["pupil_y_rotation_deg_image_y_down"],
        "axis_dot": axes["axis_dot"],
        "axis_determinant": axes["axis_determinant"],
        "axis_angle_between_deg": axes["axis_angle_between_deg"],
        "tilt_x_response": tilt_x_axis,
        "tilt_y_response": tilt_y_axis,
        "reference_spots": int(len(reference_spots)),
        "defocus_final_gated_spots": int(len(defocus_gate_2)),
        "tilt_x_final_gated_spots": int(len(tilt_x_gate)),
        "tilt_y_final_gated_spots": int(len(tilt_y_gate)),
        "gate_half_cols": analysis_cfg["gate"]["half_cols"],
        "gate_half_rows": analysis_cfg["gate"]["half_rows"],
        "optics_config": str(optics_cfg["config_path"]),
        "analysis_config": str(analysis_cfg["config_path"]),
    }
    return calibration


def save_calibration_files(calibration, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "pupil_center_calibration.json"
    csv_path = output_dir / "pupil_center_calibration.csv"
    json_path.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame([flatten_calibration(calibration)]).to_csv(csv_path, index=False)

    LATEST_CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_CALIBRATION_FILE.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
    return json_path, csv_path


def load_calibration_file(path=LATEST_CALIBRATION_FILE):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Calibration file not found: {path}. Run calibration.py first.")
    calibration = json.loads(path.read_text(encoding="utf-8"))
    calibration["calibration_file"] = str(path.resolve())
    return calibration


def flatten_calibration(calibration):
    row = {
        "center_x_px": calibration["center_x_px"],
        "center_y_px": calibration["center_y_px"],
        "gate_half_cols": calibration["gate_half_cols"],
        "gate_half_rows": calibration["gate_half_rows"],
        "reference_spots": calibration["reference_spots"],
        "defocus_final_gated_spots": calibration["defocus_final_gated_spots"],
        "tilt_x_final_gated_spots": calibration["tilt_x_final_gated_spots"],
        "tilt_y_final_gated_spots": calibration["tilt_y_final_gated_spots"],
        "axis_dot": calibration["axis_dot"],
        "axis_determinant": calibration["axis_determinant"],
        "axis_angle_between_deg": calibration["axis_angle_between_deg"],
    }
    for name in ("pupil_x_axis_image", "pupil_y_axis_image", "pupil_y_axis_orthogonalized_image"):
        row[f"{name}_x"] = calibration[name][0]
        row[f"{name}_y"] = calibration[name][1]
    return row


def run_calibration(image_dir=DEFAULT_IMAGE_DIR, optics_config=None, analysis_config=None):
    optics_cfg = load_optics_config(optics_config) if optics_config else load_optics_config()
    analysis_cfg = (
        load_analysis_config(analysis_config, optics_cfg=optics_cfg)
        if analysis_config
        else load_analysis_config(optics_cfg=optics_cfg)
    )

    output_dir = optics_cfg["paths"]["results_dir"] / f"calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    images = load_calibration_images(image_dir)
    reference = images["reference"]
    defocus = images["defocus"]
    tilt_x = images["tilt_x"]
    tilt_y = images["tilt_y"]

    spot_params = analysis_cfg["spot_detection"]
    reference_spots = detect_spots(reference, spot_params)
    defocus_spots = detect_spots(defocus, spot_params)
    tilt_x_spots = detect_spots(tilt_x, spot_params)
    tilt_y_spots = detect_spots(tilt_y, spot_params)

    max_distance_px = spot_params["max_match_distance_px"]
    defocus_matches = match_spots(reference_spots, defocus_spots, max_distance_px)
    tilt_x_matches = match_spots(reference_spots, tilt_x_spots, max_distance_px)
    tilt_y_matches = match_spots(reference_spots, tilt_y_spots, max_distance_px)

    center_global = estimate_center(defocus_matches)
    defocus_gate_1 = gate_by_center(defocus_matches, center_global, optics_cfg, analysis_cfg)
    center_gate_1 = estimate_center(defocus_gate_1)
    defocus_gate_2 = gate_by_center(defocus_matches, center_gate_1, optics_cfg, analysis_cfg)
    center_final = estimate_center(defocus_gate_2)

    tilt_x_gate = gate_by_center(tilt_x_matches, center_final, optics_cfg, analysis_cfg)
    tilt_y_gate = gate_by_center(tilt_y_matches, center_final, optics_cfg, analysis_cfg)
    tilt_x_axis = estimate_axis(tilt_x_gate)
    tilt_y_axis = estimate_axis(tilt_y_gate)
    axes = make_axis_calibration(tilt_x_axis, tilt_y_axis)

    save_displacement_plot(
        defocus,
        defocus_gate_2,
        center_final,
        axes,
        output_dir / "defocus_displacements_gate_center.png",
        "Defocus gated displacement",
        analysis_cfg["visualization"]["arrow_gain"],
    )
    save_displacement_plot(
        tilt_x,
        tilt_x_gate,
        center_final,
        axes,
        output_dir / "tilt_x_displacements_gate_axis.png",
        "Tilt x gated displacement",
        analysis_cfg["visualization"]["arrow_gain"],
    )
    save_displacement_plot(
        tilt_y,
        tilt_y_gate,
        center_final,
        axes,
        output_dir / "tilt_y_displacements_gate_axis.png",
        "Tilt y gated displacement",
        analysis_cfg["visualization"]["arrow_gain"],
    )

    calibration = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": "offline_defocus_center_plus_tilt_axes",
        "center_x_px": center_final["center_x_px"],
        "center_y_px": center_final["center_y_px"],
        "center_steps": {
            "global": center_global,
            "gate_once": center_gate_1,
            "gate_twice": center_final,
        },
        "pupil_x_axis_image": axes["pupil_x_axis_image"],
        "pupil_y_axis_image": axes["pupil_y_axis_image"],
        "pupil_y_axis_orthogonalized_image": axes["pupil_y_axis_orthogonalized_image"],
        "pupil_x_rotation_deg_image_y_down": axes["pupil_x_rotation_deg_image_y_down"],
        "pupil_y_rotation_deg_image_y_down": axes["pupil_y_rotation_deg_image_y_down"],
        "axis_dot": axes["axis_dot"],
        "axis_determinant": axes["axis_determinant"],
        "axis_angle_between_deg": axes["axis_angle_between_deg"],
        "tilt_x_response": tilt_x_axis,
        "tilt_y_response": tilt_y_axis,
        "reference_spots": int(len(reference_spots)),
        "defocus_final_gated_spots": int(len(defocus_gate_2)),
        "tilt_x_final_gated_spots": int(len(tilt_x_gate)),
        "tilt_y_final_gated_spots": int(len(tilt_y_gate)),
        "gate_half_cols": analysis_cfg["gate"]["half_cols"],
        "gate_half_rows": analysis_cfg["gate"]["half_rows"],
        "optics_config": str(optics_cfg["config_path"]),
        "analysis_config": str(analysis_cfg["config_path"]),
    }
    json_path, csv_path = save_calibration_files(calibration, output_dir)

    print(f"Output: {output_dir}")
    print(f"Calibration JSON: {json_path}")
    print(f"Latest calibration JSON: {LATEST_CALIBRATION_FILE}")
    print(f"Center: ({calibration['center_x_px']:.2f}, {calibration['center_y_px']:.2f}) px")
    print(f"X axis: {calibration['pupil_x_axis_image']}")
    print(f"Y axis: {calibration['pupil_y_axis_image']}")
    return calibration


def estimate_center(matches, min_displacement_px=0.25):
    points = matches[["ref_x_px", "ref_y_px"]].to_numpy(dtype=np.float64)
    vectors = matches[["dx_px", "dy_px"]].to_numpy(dtype=np.float64)
    magnitudes = np.linalg.norm(vectors, axis=1)
    keep = magnitudes >= float(min_displacement_px)
    if np.count_nonzero(keep) < 4:
        raise RuntimeError("Not enough displacement vectors to estimate center.")

    points = points[keep]
    vectors = vectors[keep]
    magnitudes = magnitudes[keep]
    normals = np.column_stack([-vectors[:, 1], vectors[:, 0]]) / magnitudes[:, None]
    rhs = np.sum(normals * points, axis=1)
    weights = np.clip(np.sqrt(magnitudes / max(float(np.median(magnitudes)), 1e-12)), 0.25, 3.0)

    center, *_ = np.linalg.lstsq(normals * weights[:, None], rhs * weights, rcond=1e-8)
    residual = normals @ center - rhs
    return {
        "center_x_px": float(center[0]),
        "center_y_px": float(center[1]),
        "used_vectors": int(len(points)),
        "total_vectors": int(len(matches)),
        "median_displacement_px": float(np.median(magnitudes)),
        "rms_line_residual_px": float(np.sqrt(np.mean(residual * residual))),
    }


def gate_by_center(matches, center, optics_cfg, analysis_cfg):
    pitch = float(optics_cfg["optics"]["lenslet_pitch_px"])
    half_w = float(analysis_cfg["gate"]["half_cols"]) * pitch
    half_h = float(analysis_cfg["gate"]["half_rows"]) * pitch
    cx = float(center["center_x_px"])
    cy = float(center["center_y_px"])
    keep = (
        (matches["ref_x_px"] >= cx - half_w)
        & (matches["ref_x_px"] <= cx + half_w)
        & (matches["ref_y_px"] >= cy - half_h)
        & (matches["ref_y_px"] <= cy + half_h)
    )
    gated = matches.loc[keep].copy().reset_index(drop=True)
    if gated.empty:
        raise RuntimeError("Center gate removed all matched spots.")
    return gated


def estimate_axis(matches, min_displacement_px=0.25):
    vectors = matches[["dx_px", "dy_px"]].to_numpy(dtype=np.float64)
    magnitudes = np.linalg.norm(vectors, axis=1)
    keep = magnitudes >= float(min_displacement_px)
    if np.count_nonzero(keep) < 3:
        raise RuntimeError("Not enough tilt vectors to estimate axis.")

    vector = np.median(vectors[keep], axis=0)
    if np.linalg.norm(vector) <= 1e-12:
        vector = np.mean(vectors[keep], axis=0)
    axis = vector / max(float(np.linalg.norm(vector)), 1e-12)
    return {
        "axis_x": float(axis[0]),
        "axis_y": float(axis[1]),
        "angle_deg_image_y_down": float(np.degrees(np.arctan2(axis[1], axis[0]))),
        "median_dx_px": float(vector[0]),
        "median_dy_px": float(vector[1]),
        "used_vectors": int(np.count_nonzero(keep)),
        "total_vectors": int(len(matches)),
    }


def make_axis_calibration(tilt_x_axis, tilt_y_axis):
    x_axis = np.array([tilt_x_axis["axis_x"], tilt_x_axis["axis_y"]], dtype=np.float64)
    y_axis = np.array([tilt_y_axis["axis_x"], tilt_y_axis["axis_y"]], dtype=np.float64)
    x_axis /= max(float(np.linalg.norm(x_axis)), 1e-12)
    y_axis /= max(float(np.linalg.norm(y_axis)), 1e-12)

    y_orth = y_axis - np.dot(y_axis, x_axis) * x_axis
    if np.linalg.norm(y_orth) > 1e-12:
        y_orth /= float(np.linalg.norm(y_orth))
        if np.dot(y_orth, y_axis) < 0:
            y_orth = -y_orth
    else:
        y_orth = np.array([-x_axis[1], x_axis[0]], dtype=np.float64)

    dot = float(np.dot(x_axis, y_axis))
    determinant = float(x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0])
    return {
        "pupil_x_axis_image": [float(x_axis[0]), float(x_axis[1])],
        "pupil_y_axis_image": [float(y_axis[0]), float(y_axis[1])],
        "pupil_y_axis_orthogonalized_image": [float(y_orth[0]), float(y_orth[1])],
        "pupil_x_rotation_deg_image_y_down": float(np.degrees(np.arctan2(x_axis[1], x_axis[0]))),
        "pupil_y_rotation_deg_image_y_down": float(np.degrees(np.arctan2(y_axis[1], y_axis[0]))),
        "axis_dot": dot,
        "axis_determinant": determinant,
        "axis_angle_between_deg": float(np.degrees(np.arccos(np.clip(dot, -1.0, 1.0)))),
    }


def save_displacement_plot(image, matches, center, axes, output_png, title, arrow_gain):
    vmin, vmax = np.percentile(image, [1.0, 99.8])
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin, vmax = float(np.min(image)), float(np.max(image))
    cx = float(center["center_x_px"])
    cy = float(center["center_y_px"])
    x_axis = np.array(axes["pupil_x_axis_image"], dtype=np.float64)
    y_axis = np.array(axes["pupil_y_axis_image"], dtype=np.float64)
    axis_len = 0.12 * float(min(image.shape))

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
    ax.scatter([cx], [cy], s=80, marker="+", c="lime", linewidths=2.0, label="center")
    ax.arrow(cx, cy, x_axis[0] * axis_len, x_axis[1] * axis_len, color="lime", width=1.5)
    ax.arrow(cx, cy, y_axis[0] * axis_len, y_axis[1] * axis_len, color="yellow", width=1.5)
    ax.text(cx + x_axis[0] * axis_len, cy + x_axis[1] * axis_len, "x", color="lime", fontsize=12)
    ax.text(cx + y_axis[0] * axis_len, cy + y_axis[1] * axis_len, "y", color="yellow", fontsize=12)
    ax.set_title(title)
    ax.axis("off")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_png, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Offline Shack-Hartmann pupil calibration from saved images.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--optics-config", type=Path, default=None)
    parser.add_argument("--analysis-config", type=Path, default=None)
    args = parser.parse_args()
    run_calibration(args.image_dir, args.optics_config, args.analysis_config)


if __name__ == "__main__":
    main()
