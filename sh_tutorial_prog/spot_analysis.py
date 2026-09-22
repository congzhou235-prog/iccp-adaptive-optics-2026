from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from scipy.spatial import cKDTree


def load_image(path):
    path = Path(path)
    if path.suffix.lower() == ".npy":
        return np.asarray(np.load(path), dtype=np.float64)

    image = Image.open(path)
    if image.mode not in ("L", "I;16", "I"):
        image = image.convert("L")
    return np.asarray(image, dtype=np.float64)


def detect_spots(image, params):
    image = np.asarray(image, dtype=np.float64)
    background = np.percentile(image, params["background_percentile"])
    signal = np.clip(image - background, 0.0, None)
    filtered = ndi.gaussian_filter(signal, sigma=params["blur_sigma_px"])
    threshold = float(params["threshold_relative"]) * float(np.max(filtered))
    labels, count = ndi.label(filtered >= threshold, structure=np.ones((3, 3), dtype=bool))

    records = []
    height, width = image.shape
    edge = int(params["edge_margin_px"])
    for label_id, slc in enumerate(ndi.find_objects(labels), start=1):
        if slc is None:
            continue
        y0, y1 = slc[0].start, slc[0].stop
        x0, x1 = slc[1].start, slc[1].stop
        if x0 < edge or y0 < edge or x1 > width - edge or y1 > height - edge:
            continue

        component = labels[slc] == label_id
        area = int(np.count_nonzero(component))
        if area < params["min_area_px"] or area > params["max_area_px"]:
            continue

        yy, xx = np.nonzero(component)
        yy = yy + y0
        xx = xx + x0
        weights = signal[yy, xx]
        weight_sum = float(np.sum(weights))
        if weight_sum <= 0:
            continue

        records.append(
            {
                "x_px": float(np.sum(xx * weights) / weight_sum),
                "y_px": float(np.sum(yy * weights) / weight_sum),
                "area_px": area,
                "sum_signal": weight_sum,
            }
        )

    spots = pd.DataFrame.from_records(records)
    if spots.empty:
        raise RuntimeError(f"No spots detected. Raw components: {count}.")
    spots = spots.sort_values(["y_px", "x_px"], ignore_index=True)
    spots.insert(0, "spot_id", np.arange(len(spots), dtype=int))
    return spots





def match_spots(reference_spots, measurement_spots, max_distance_px):
    reference_xy = reference_spots[["x_px", "y_px"]].to_numpy(dtype=np.float64)
    measurement_xy = measurement_spots[["x_px", "y_px"]].to_numpy(dtype=np.float64)
    distances, measurement_indices = cKDTree(measurement_xy).query(reference_xy, k=1)

    candidates = []
    for reference_index, (distance, measurement_index) in enumerate(zip(distances, measurement_indices)):
        if np.isfinite(distance) and distance <= float(max_distance_px):
            candidates.append((float(distance), int(reference_index), int(measurement_index)))
    candidates.sort(key=lambda item: item[0])

    used_measurements = set()
    records = []
    for match_distance, reference_index, measurement_index in candidates:
        if measurement_index in used_measurements:
            continue
        used_measurements.add(measurement_index)
        reference = reference_spots.iloc[reference_index]
        measurement = measurement_spots.iloc[measurement_index]
        dx = float(measurement["x_px"] - reference["x_px"])
        dy = float(measurement["y_px"] - reference["y_px"])
        records.append(
            {
                "spot_id": int(reference["spot_id"]),
                "ref_x_px": float(reference["x_px"]),
                "ref_y_px": float(reference["y_px"]),
                "meas_x_px": float(measurement["x_px"]),
                "meas_y_px": float(measurement["y_px"]),
                "dx_px": dx,
                "dy_px": dy,
                "distance_px": float(np.hypot(dx, dy)),
                "match_distance_px": match_distance,
            }
        )

    matches = pd.DataFrame.from_records(records)
    if matches.empty:
        raise RuntimeError("No spot matches were found.")
    return matches.sort_values("spot_id", ignore_index=True)
