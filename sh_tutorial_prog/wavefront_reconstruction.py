import numpy as np
import pandas as pd


ZERNIKE_META = {
    1: (0, 0, "piston"),
    2: (1, 1, "tilt_x"),
    3: (1, -1, "tilt_y"),
    4: (2, 0, "defocus"),
    5: (2, -2, "astig_45"),
    6: (2, 2, "astig_0"),
    7: (3, -1, "coma_y"),
    8: (3, 1, "coma_x"),
    9: (3, -3, "trefoil_y"),
    10: (3, 3, "trefoil_x"),
    11: (4, 0, "spherical"),
    12: (4, -2, "secondary_astig_45"),
    13: (4, 2, "secondary_astig_0"),
    14: (4, -4, "quadrafoil_45"),
    15: (4, 4, "quadrafoil_0"),
    16: (5, -1, "secondary_coma_y"),
    17: (5, 1, "secondary_coma_x"),
    18: (5, -3, "secondary_trefoil_y"),
    19: (5, 3, "secondary_trefoil_x"),
    20: (5, -5, "pentafoil_y"),
    21: (5, 5, "pentafoil_x"),
}


def gate_by_pupil_box(matches, calibration, optics_cfg, analysis_cfg):
    col_pitch, row_pitch = reference_pupil_pitch(matches, calibration, optics_cfg)
    col_limit = float(analysis_cfg["gate"]["half_cols"]) + 0.5
    row_limit = float(analysis_cfg["gate"]["half_rows"]) + 0.5
    keep = (np.abs(col_pitch) <= col_limit) & (np.abs(row_pitch) <= row_limit)

    labeled = matches.copy().reset_index(drop=True)
    labeled["gate_col_pitch"] = col_pitch
    labeled["gate_row_pitch"] = row_pitch
    labeled["gate_keep"] = keep
    gated = labeled.loc[keep].copy().reset_index(drop=True)
    if gated.empty:
        raise RuntimeError("Pupil gate removed all matched spots.")
    return labeled, gated


def reconstruct_zernike(matches, calibration, optics_cfg, analysis_cfg):
    indices = np.asarray(analysis_cfg["zernike"]["indices"], dtype=int)
    xy_m, slopes = matches_to_pupil_meters_and_slopes(matches, calibration, optics_cfg)

    radius_m = 0.5 * float(optics_cfg["optics"]["zernike_aperture_diameter_m"])
    inside = np.linalg.norm(xy_m, axis=1) <= float(analysis_cfg["zernike"]["fit_edge_radius_fraction"]) * radius_m
    if np.count_nonzero(inside) < len(indices):
        raise RuntimeError("Not enough gated spots inside the Zernike fit aperture.")

    A = zernike_slope_matrix(indices, xy_m[inside], radius_m, optics_cfg["optics"]["wavelength_m"])
    b = np.concatenate([slopes[inside, 0], slopes[inside, 1]])
    coeff, residual, solve_info = solve_coefficients(A, b, analysis_cfg)

    rows = []
    for j, value in zip(indices, coeff):
        n, m, name = ZERNIKE_META[int(j)]
        rows.append(
            {
                "zernike_j": int(j),
                "n": int(n),
                "m": int(m),
                "name": name,
                "coeff_rad": float(value),
            }
        )

    info = {
        "matched_spots": int(len(matches)),
        "fit_spots": int(np.count_nonzero(inside)),
        "fit_radius_m": float(radius_m),
        "rms_displacement_px": float(np.sqrt(np.mean(matches["distance_px"].to_numpy(dtype=np.float64) ** 2))),
        "rms_slope_residual": float(np.sqrt(np.mean(residual * residual))),
        **solve_info,
    }
    return pd.DataFrame(rows), info


def matches_to_pupil_meters_and_slopes(matches, calibration, optics_cfg):
    cx = float(calibration["center_x_px"])
    cy = float(calibration["center_y_px"])
    ref_x, ref_y = image_vectors_to_pupil_components(
        matches["ref_x_px"].to_numpy(dtype=np.float64) - cx,
        matches["ref_y_px"].to_numpy(dtype=np.float64) - cy,
        calibration,
    )
    slope_x_px, slope_y_px = image_vectors_to_pupil_components(
        matches["dx_px"].to_numpy(dtype=np.float64),
        matches["dy_px"].to_numpy(dtype=np.float64),
        calibration,
    )

    pixel_pitch_m = float(optics_cfg["camera"]["pixel_pitch_m"])
    focal_length_m = float(optics_cfg["optics"]["lenslet_focal_length_m"])
    magnification = float(optics_cfg["optics"]["sh_magnification"])

    xy_m = np.column_stack([ref_x * pixel_pitch_m / magnification, ref_y * pixel_pitch_m / magnification])
    slopes = np.column_stack([slope_x_px * pixel_pitch_m / focal_length_m, slope_y_px * pixel_pitch_m / focal_length_m])
    return xy_m, slopes


def reference_pupil_pitch(matches, calibration, optics_cfg):
    cx = float(calibration["center_x_px"])
    cy = float(calibration["center_y_px"])
    ref_x, ref_y = image_vectors_to_pupil_components(
        matches["ref_x_px"].to_numpy(dtype=np.float64) - cx,
        matches["ref_y_px"].to_numpy(dtype=np.float64) - cy,
        calibration,
    )
    return ref_x / optics_cfg["optics"]["lenslet_pitch_px"], ref_y / optics_cfg["optics"]["lenslet_pitch_px"]


def image_vectors_to_pupil_components(dx_px, dy_px, calibration):
    vectors = np.column_stack([np.asarray(dx_px, dtype=np.float64), np.asarray(dy_px, dtype=np.float64)])
    x_axis = unit(calibration["pupil_x_axis_image"])
    y_axis = unit(calibration.get("pupil_y_axis_orthogonalized_image", calibration["pupil_y_axis_image"]))
    return vectors @ x_axis, vectors @ y_axis


def zernike_slope_matrix(indices, xy_m, radius_m, wavelength_m):
    eps_m = (2.0 * float(radius_m)) / 2000.0
    columns = []
    for j in indices:
        dz_dx = (
            zernike_at_xy(j, xy_m + np.array([eps_m, 0.0]), radius_m)
            - zernike_at_xy(j, xy_m - np.array([eps_m, 0.0]), radius_m)
        ) / (2.0 * eps_m)
        dz_dy = (
            zernike_at_xy(j, xy_m + np.array([0.0, eps_m]), radius_m)
            - zernike_at_xy(j, xy_m - np.array([0.0, eps_m]), radius_m)
        ) / (2.0 * eps_m)
        columns.append(np.concatenate([dz_dx, dz_dy]) * float(wavelength_m) / (2.0 * np.pi))
    return np.column_stack(columns)


def zernike_at_xy(j, xy_m, radius_m):
    x = xy_m[:, 0] / float(radius_m)
    y = xy_m[:, 1] / float(radius_m)
    inside = x * x + y * y <= 1.0
    values = np.full(x.shape, np.nan, dtype=np.float64)
    values[inside] = zernike_mode(int(j), x[inside], y[inside])
    return values


def zernike_mode(j, x, y):
    rho2 = x * x + y * y
    rho4 = rho2 * rho2
    if j == 1:
        return np.ones_like(x)
    if j == 2:
        return x
    if j == 3:
        return y
    if j == 4:
        return 2.0 * rho2 - 1.0
    if j == 5:
        return 2.0 * x * y
    if j == 6:
        return x * x - y * y
    if j == 7:
        return y * (3.0 * rho2 - 2.0)
    if j == 8:
        return x * (3.0 * rho2 - 2.0)
    if j == 9:
        return y * (3.0 * x * x - y * y)
    if j == 10:
        return x * (x * x - 3.0 * y * y)
    if j == 11:
        return 6.0 * rho4 - 6.0 * rho2 + 1.0
    if j == 12:
        return 2.0 * x * y * (4.0 * rho2 - 3.0)
    if j == 13:
        return (x * x - y * y) * (4.0 * rho2 - 3.0)
    if j == 14:
        return 4.0 * x * y * (x * x - y * y)
    if j == 15:
        return x**4 - 6.0 * x * x * y * y + y**4
    if j == 16:
        return y * (10.0 * rho4 - 12.0 * rho2 + 3.0)
    if j == 17:
        return x * (10.0 * rho4 - 12.0 * rho2 + 3.0)
    if j == 18:
        return y * (3.0 * x * x - y * y) * (5.0 * rho2 - 4.0)
    if j == 19:
        return x * (x * x - 3.0 * y * y) * (5.0 * rho2 - 4.0)
    if j == 20:
        return y * (5.0 * x**4 - 10.0 * x * x * y * y + y**4)
    if j == 21:
        return x * (x**4 - 10.0 * x * x * y * y + 5.0 * y**4)
    raise ValueError("Supported Zernike j values are 1..21.")


def solve_coefficients(A, b, analysis_cfg):
    valid = np.all(np.isfinite(A), axis=1) & np.isfinite(b)
    A = A[valid]
    b = b[valid]

    method = str(analysis_cfg["zernike"]["regularization"]).lower()
    if method in ("none", "ols", "least_squares"):
        coeff, *_ = np.linalg.lstsq(A, b, rcond=1e-6)
        return coeff, A @ coeff - b, {"regularization": "none", "l1_iterations": 0}

    coeff, iterations = solve_l1_fista(
        A,
        b,
        l1_fraction=float(analysis_cfg["zernike"]["l1_lambda"]),
        max_iter=int(analysis_cfg["zernike"]["l1_max_iter"]),
        tol=float(analysis_cfg["zernike"]["l1_tol"]),
    )
    return coeff, A @ coeff - b, {"regularization": "l1", "l1_iterations": int(iterations)}


def solve_l1_fista(A, b, l1_fraction, max_iter, tol):
    atb = A.T @ b
    alpha = float(l1_fraction) * float(np.max(np.abs(atb)))
    if alpha <= 0:
        coeff, *_ = np.linalg.lstsq(A, b, rcond=1e-6)
        return coeff, 0

    step = max(float(np.linalg.norm(A, ord=2)) ** 2, 1e-30)
    coeff = np.zeros(A.shape[1], dtype=np.float64)
    y = coeff.copy()
    t = 1.0
    for iteration in range(1, int(max_iter) + 1):
        previous = coeff.copy()
        gradient = A.T @ (A @ y - b)
        coeff = soft_threshold(y - gradient / step, alpha / step)
        t_next = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
        y = coeff + ((t - 1.0) / t_next) * (coeff - previous)
        t = t_next
        if np.linalg.norm(coeff - previous) / max(1.0, np.linalg.norm(previous)) < float(tol):
            break
    coeff[np.abs(coeff) < 1e-10] = 0.0
    return coeff, iteration


def soft_threshold(values, threshold):
    return np.sign(values) * np.maximum(np.abs(values) - float(threshold), 0.0)


def unit(vector):
    vector = np.asarray(vector, dtype=np.float64).reshape(2)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Calibration axis has near-zero length.")
    return vector / norm
