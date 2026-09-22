# Offline Shack-Hartmann Image Analysis Tutorial

This tutorial shows how to calculate Zernike aberration coefficients from saved Shack-Hartmann images and optical parameters. You do not need to control a camera, a deformable mirror (DM), or a spatial light modulator (SLM).

The program uses two types of input:

- Experimental images: a reference image taken with no added aberration or in a known reference state, and a measurement image taken after adding Zernike aberrations.
- Optical parameters: the setup information stored in `config.yaml`. The program uses these values to convert pixel shifts into wavefront slopes and then fit Zernike coefficients.

## Optical Parameters in the Config File

`config.yaml` stores the parameters of the optical setup.

`camera.image_size_px`

The camera image size in pixels. For example, `[1440, 1080]` means an image width of 1440 px and a height of 1080 px. This value is mainly used to check whether the image size matches the configuration.

`camera.pixel_pitch_m`

The physical size of one camera pixel, in meters. For example, `3.45e-6` means 3.45 micrometers per pixel. The program uses this value to convert image shifts from pixels to meters.

`optics.wavelength_m`

The light wavelength in meters. For example, 635 nm red light is written as `635.0e-9`. The output Zernike coefficients describe phase in radians, so the wavelength is needed to convert between phase and wavefront height.

`optics.lenslet_pitch_m`

The distance between the centers of neighboring microlenses, in meters. For example, `300.0e-6` means a pitch of 300 micrometers. This value gives the approximate spot spacing and helps set the spot matching distance and gate size. A gate is the region used to select spots for analysis.

`optics.lenslet_focal_length_m`

The focal length of each microlens, in meters. In a Shack-Hartmann sensor, the spot shift at the focal plane divided by the microlens focal length gives the local wavefront slope. This value therefore directly affects the calculated Zernike coefficients.

`optics.sh_magnification`

The optical magnification from the wavefront plane being measured to the Shack-Hartmann sensor plane. If the optical system does not enlarge or reduce the wavefront, this is usually `1.0`.

`optics.zernike_aperture_diameter_m`

The effective aperture diameter used for Zernike fitting, in meters. This is the physical aperture used to normalize the Zernike modes, rather than the gate size. It affects the scale of the Zernike coefficients. If the measured and true coefficients differ by a nearly constant factor, check this parameter first.

## Program Structure

We suggest splitting the program into the following modules.

`config_loader.py`

Reads `config.yaml` and calculates values needed by later steps. For example:

```python
lenslet_pitch_px = lenslet_pitch_m / pixel_pitch_m
```

This is the approximate number of image pixels in one microlens pitch.

`spot_analysis.py`

Handles image processing and spot detection. It should:

1. Read PNG or NPY images.
2. Detect the center of each spot.
3. Match spots in the reference and measurement images to find each spot's displacement, `dx_px, dy_px`.

The expected result is a table of matched spots. Each row should include the reference position, the measurement position, and the displacement between them.

`calibration.py`

Uses calibration images to find the information needed for later calculations. It usually needs four images: reference, defocus, x tilt, and y tilt.

The defocus image is used to estimate the center of the spot array. The tilt images are used to find the pupil x and y directions in image coordinates.

The expected output is a calibration file, such as `pupil_center_calibration.json`. It should contain:

- Center position: `center_x_px, center_y_px`
- Pupil x direction: `pupil_x_axis_image`
- Pupil y direction: `pupil_y_axis_image`
- Gate size
- Number of spots used in the calculation

Use the same calibration file for later measurement images, as long as the optical setup and calibration conditions stay the same.

`wavefront_reconstruction.py`

Converts spot displacements into Zernike coefficients. The main steps are:

1. Convert image coordinates to pupil coordinates.
2. Convert spot displacements to local wavefront slopes.
3. Build a matrix of Zernike mode slopes using the effective aperture in the configuration.
4. Solve for the Zernike coefficients using least squares or a regularized method.

The expected result is a table, such as `measured_zernike_coeffs.csv`. Each row represents one Zernike mode and contains `zernike_j`, the mode name, and the measured phase coefficient `coeff_rad`.

`analyze_zernike.py`

This is the main program. It connects the modules above and should:

1. Read the configuration.
2. Read the calibration file.
3. Read the reference image for one dataset group.
4. Read each measurement image in turn.
5. Detect spots, match them, apply the gate, and calculate Zernike coefficients.
6. Compare the true and measured coefficients if true values are included in the dataset.

## Dataset Structure

The dataset is organized as follows:

```text
dataset/
  first_10_zernike/
    reference_flat.png
    sample_01_j02_tilt_x/
      measurement.png
      true_zernike_phase_coeffs.csv
    sample_02_j03_tilt_y/
      measurement.png
      true_zernike_phase_coeffs.csv

  last_10_zernike/
    reference_flat.png
    sample_01_j12_secondary_astig_45/
      measurement.png
      true_zernike_phase_coeffs.csv

  mixed_zernike/
    reference_flat.png
    sample_01_mixed/
      measurement.png
      true_zernike_phase_coeffs.csv
```

Each group needs only one `reference_flat.png`. All measurement images in that group are compared with this reference image.

Each sample folder contains one `measurement.png`. It can also contain `true_zernike_phase_coeffs.csv` for checking the results.

## Suggested Coding Steps

### Step 1. Read the Configuration

Start with a simple loader. Check that it reads the image size, pixel size, microlens pitch, focal length, wavelength, and effective Zernike aperture correctly. You do not need to process images yet.

Expected result: the loader can print calculated values such as `lenslet_pitch_px`.

### Step 2. Read an Image and Detect Spots

Start with the reference image. Find all spot centers and plot them on the image to check their positions.

Expected result: the number of detected spots is reasonable, the detected centers cover the array, and there are few false detections near the edges.

### Step 3. Match Reference and Measurement Spots

Detect spots separately in the reference and measurement images from the same group. Then match them using their nearest neighbors.

Expected result: each matched spot has a displacement vector. For tilt, the vectors should point in roughly the same direction. For defocus, they should point roughly toward or away from the center.

### Step 4. Run Calibration

Use the defocus image to estimate the pupil center. Use the two tilt images to estimate the pupil x and y directions. Save these results in a calibration file.

Expected result: `pupil_center_calibration.json`, plus displacement plots for the defocus, x tilt, and y tilt images showing the spots kept by the gate.

### Step 5. Calculate Zernike Coefficients

Read the reference image, measurement image, and calibration file. Convert spot displacements to wavefront slopes, then fit the Zernike coefficients.

Expected result: `measured_zernike_coeffs.csv`. If true coefficients are available, also plot a comparison of the true and measured values.

### Step 6. Check the Results

If all measured values are smaller or larger than the true values by a nearly constant factor, first check `zernike_aperture_diameter_m`, the microlens focal length, and the pixel size.

If some modes have the wrong sign, first check whether the pupil x or y direction is reversed.

If errors are much larger for higher-order modes, first check the gate size, the quality of edge spots, and whether spot matching is reliable.

## Output Files

After a full analysis, we suggest saving these files:

`measured_zernike_coeffs.csv`

The measured Zernike coefficients.

`true_vs_measured_zernike_coeffs.csv`

A table comparing the true and measured coefficients.

`true_vs_measured_zernike.png`

A bar chart comparing the true and measured coefficients.

`spot_displacements_gate.png`

A plot of the spot displacements selected by the gate for fitting.

These files can be used to check the program's results and explain the analysis steps in a course report.

## Main Idea

Shack-Hartmann image analysis follows four basic steps:

1. Find each spot's position in the image.
2. Find the local displacement by subtracting the reference position from the measurement position.
3. Use the microlens focal length to convert the displacement into a wavefront slope.
4. Fit the measured slopes using the theoretical slopes of Zernike modes.

You can calculate Zernike aberration coefficients entirely offline, as long as the reference image, measurement image, optical parameters, and calibration file all correspond to the same setup and conditions.
