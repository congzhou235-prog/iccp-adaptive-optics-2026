# Shack-Hartmann sensor hardware

[Hardware section](../index.html#hardware) · [Parts list (CSV)](BOM.csv) · [Illustrated assembly guide](../Assembly%20Guide%20for%20the%20Hartmann%20Sensor.pdf)

The sensor uses a DAHENG VEN-161-61U3M bare-board camera, an LBTEK MLAS10-F15-P300-AB mounted microlens array, an SM1-12.5A lens tube, and a printed front and back housing.

## Supplier pages

- [Camera: VEN-161-61U3M](https://en.daheng-imaging.com/show-93-2117-1.html). Select the bare-board version without a lens mount for this housing.
- [Microlens array: MLAS10-F15-P300-AB](https://en.lbtek.com/product/378). Pitch: 300 µm. Focal length: 14.6 mm. Mount diameter: 25.4 mm.
- [Lens tube: SM1-12.5A](https://en.lbtek.com/product/221). Includes one SM1R retaining ring. The assembly needs two rings in total, so add one extra.

- [Retaining ring: SM1R](https://en.lbtek.com/product/135#SM1R). SM1 external thread, 2.0 mm thickness, Ø23.0 mm clear aperture, for Ø25.4 mm optics. Black anodized 6061-T6 aluminum alloy. Two rings are needed in total, including the one supplied with the lens tube.

Quantities in the CSV are for one sensor. Also prepare clean gloves, a computer with the camera driver and Galaxy Viewer, and a collimated beam for adjustment.

## Printed parts

The front housing holds the camera board and has an SM1 opening. The back housing secures the board and leaves the camera connector accessible. Four M2 screws and four M2×2 brass insert nuts join the two parts.

[Download both STEP models (ZIP)](../downloads/camera-housing-step.zip). Extract the archive to get a `camera-housing` folder containing both files.

Individual files:

- [hartmann1.STEP](../hartmann1.STEP)
- [hartmann2 - 0923new.step](../hartmann2%20-%200923new.step)

Dimensions for M2×2 from the supplier’s table (all in mm):

| Model | Length | Pilot hole diameter | Workpiece outer diameter |
| --- | --- | --- | --- |
| M2×2 | 3.5 | 3.2 | 6.2 |

The 6.2 mm value describes the workpiece outer diameter, not the nut outer diameter.

During printing, pause when the housing’s recessed holes are accessible. Use M2×2 brass insert nuts to fit the reserved holes. Press the four nuts into the recesses, then resume printing. Use the embedded nuts to secure the housing with the M2 screws.

Choose a strong printing material with good heat resistance. The specific material, print settings, and STL files are still to be added.

## Assembly

Follow the PDF for the illustrated steps: install the camera and housings, mount the array between two rings, attach the tube, connect the camera, and adjust focus and alignment. Tighten the housing screws and retaining rings gently.
