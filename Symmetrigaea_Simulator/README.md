# Symmetrigaea

A standalone continent simulator based on the geometric masks in
GeometricMultiFractal. It uses only Python's standard library and Tkinter.
No virtual environment or pip packages are needed.

## Run

Install Python 3.13 or 3.14 with Tcl/Tk support. To check Tkinter, run
`python -m tkinter`; it should open a small demonstration window. Then open a
terminal in this directory and run:

```
python Symmetrigaea_Simulation.py
```

No virtual environment, Civ IV installation, or third-party packages are needed.

## Explore

- **Reroll all** creates a new seed, layout, and coastline.
- **Reroll noise** keeps the displayed region layout and changes the coastline.
  Apply any edited settings first. A noise reroll does not silently relocate regions.
- **Apply settings** repeats full generation using the entered layout seed.
- **Region masks / Generated plots** changes only the preview, never the data.
- **Before repair / After repair** compares raw land with the final continent.
- **Repair marks** shows bridge additions in gold and removed tiny islands in pink.
  In the before view, future bridges are hollow gold squares. In the after view,
  removed islands are pink crosses on water. Filled marks always represent land
  present in the selected view. Turn marks off to inspect the plain coastline.
- **Region outlines**, **Centers**, and **Grid** help inspect the layout. Grid lines
  are suppressed when tiles are too small. Scroll the left panel for all options.
- Generation runs in a worker thread. **Cancel generation** retains the previous map.

Mirrored pairs share a color in mask view; later masks cover earlier ones in overlaps.
Enable outlines to see individual footprints. The core is always an ellipse. In
left/right mode its X coordinate is fixed at the map center and its vertical
placement is randomized. Rotation mode keeps the core centered. Enable
**Enclosed donut hole** to reserve an inland sea.

### Enclosed donut hole

Enable **Enclosed donut hole** in the Donut hole section. The water footprint is
anchored at the map center, then moved, resized, and rotated within the limits
below. The core's vertical position does not move
this anchor. A zero Y shift always puts the ellipse center at half the map height.
**Hole width %** and **Hole height %** default to 30% and 20% of the corresponding
map dimensions. They accept 2-50% as base dimensions, with a minimum physical size
of two tiles. Size variation is applied relative to those base dimensions.

| Control | Default | Allowed limit |
| --- | --- | --- |
| Max size variation % | +/-15% | 0-50%, independently for width and height |
| Base angle | 0 degrees | 0-359 degrees counterclockwise |
| Max rotation | +/-20 degrees | 0-180 degrees around the base angle |
| Max X shift % | +/-3% | 0-20% of map width from the map center |
| Max Y shift % | +/-3% | 0-20% of map height from the map center |
| Hole water % | 70% | 1-100% of tiles in the sampled water footprint |
| Hole fractal grain | 1 | 0-6; higher values produce finer detail |

All geometry variation is bounded by the entered values. Zero locks that part of
the geometry. The rotated footprint, including two tiles of room for a shore, must
fit inside the ocean margins. If no position fits within your limits, generation
fails; it never clips the footprint or moves it beyond the configured displacement.
Free hole movement and rotation can break exact mask symmetry; the land-region
pairing still follows the selected symmetry mode.

Below 100% water, fractal noise guides connected water growth inside the footprint.
The requested percentage, rounded up to whole tiles, is protected water. Keeping
growth connected produces one irregular hole rather than scattered ponds. At 100%,
the entire ellipse becomes water, so shoreline noise has no effect. Unselected
tiles retain their generated plot type; naturally adjacent water may extend the lake.
**Solid centers / softened edges** now applies to both land and the donut hole.
For the hole it uses GMF's reversed edge thresholds: water is favored at the
center and discouraged near the ellipse edge. Connected growth still keeps the
requested water-tile count exact, so it does not reproduce every tile selected by
GMF's independent thresholding.

**Reroll all** changes the footprint's geometry and its noise. **Reroll noise** keeps
the footprint's position, dimensions, and rotation, but regenerates the irregular
water shoreline along with the continent's coastlines. Seeds reproduce both stages.

This water mask overrides every land region before connectivity repair. Bridge
paths go around it and widened bridges cannot fill its water tiles. If the hole
opens to the outer ocean, repair adds a two-tile shore and connects it to the main
continent. These added tiles count against the existing repair budget. If the budget
is insufficient, the app retries and then reports failure rather than labeling an
open hole successful. Increase the added-land budget or reduce the hole size if needed.

An eight-neighbor flood fill checks enclosure by the main continent, including
diagonal leaks. Small islands inside the lake do not invalidate its enclosure.
**Region masks** shows the full water ellipse with a cyan outline, independent of
water percentage and shoreline noise. **Generated plots** shows the actual noisy
protected water with a cyan outline. In plot view, enable **Region outlines** to
also see the full elliptical footprint in gray.
Disable the donut checkbox to restore the previous unconstrained behavior.
Left/right means reflection across the vertical centerline; the other mode is a
180-degree rotation. Both transform full region geometry, including triangle orientation.
The preview places north at the top. **Ocean margin %** is editable from 0 to 30
(default 5). The percentage applies to each edge: map width for left/right and map
height for top/bottom, rounded up to whole tiles independently. At 5%, a 96x64 map
reserves five columns and four rows. Complete rotated masks must fit inside these
margins; shapes are never truncated to make them fit. Bridge repairs also respect
the ocean margins. A zero margin allows land to reach the map edges.

**Maximum overlap %** defaults to 70. For every pair of masks, including mirrored
partners, shared tiles may occupy no more than this percentage of the smaller
mask. It must be at least the minimum overlap; 100 removes this cap. The existing
minimum overlap applies to at least one neighbor for each new region, not every
pair. Tight overlap bounds may require rerolls or fail to produce a valid layout.

**Min map-wide mask area %** defaults to 50 and **Max map-wide mask area %** defaults to 70.
Together they bound the union of land region masks, minus protected donut-water
tiles, as a percentage of the whole map. Overlaps count only once. This does not
measure generated land area. A minimum of 0 or maximum of 100 disables that bound.
The preview reports the actual mask area and both limits; maps outside the range
are retried and cannot be labeled successful.

## Connectivity and limitations

Each region overlaps an existing region, with a minimum 2x2 shared block. Masks are
checked using four-neighbor connectivity. The simulator ports BTS's unwrapped
`CvFractal` height generation, `CvRandom`, and percentile thresholds from the SDK.
**Land fractal grain** defaults to 2 and accepts 0-6; higher values produce finer
variation. Each region gets its own fractal, so coastlines can differ across
mirrored regions. Water percent is a per-region threshold;
overlaps and solid centers mean it is not the final map's ocean percentage.

The target is at least 97% of land on the main continent, with no secondary island
larger than 1% of all land. Repairs join disconnected land using widened paths and
their symmetry-transformed partners. Added tiles are limited by the repair budget.
**Bridge width** sets the thickness of those paths: each path tile is expanded by
a square of 1, 3, 5, or 7 tiles per side. There is no separate bridge height
because the path can bend and its length follows the gap between landmasses.
Tiny islands of at most two tiles can be removed, within a total limit of 1% of the
original land, rounded up. Default acceptance allows small islands.

Full generation tries at most eight layouts. A failed connectivity, mask-area, or
enabled donut-enclosure target is shown
honestly using the best available attempt; failure to place any layout leaves the
previous map intact. Noise rerolls try once on the existing layout. The badge reports
the **after-repair** target, even when viewing masks or raw plots.

The status displays both the layout seed and the noise seed. Apply repeats the
initial full-generation result; a separately rerolled noise seed can be reproduced
through `Symmetrigaea_Generator.reroll_noise(result, noise_seed)`.
Repeatability is intended within the simulator. Its standalone `CvRandom` stream
does not follow every random call made by the game, so the same numeric seed does
not imply the same coastline in BTS.

The fractal method matches the unwrapped SDK algorithm, but the protected donut
water uses those heights to grow one connected lake rather than GMF's independent
height threshold. The simulator also does not model map-wrapping fractal flags.
Terrain, hills/peaks, rivers, resources, and starting positions are outside this
simulator. Nothing here imports or modifies an existing Civ IV mapscript.

## Sharing

For a source release, keep `README.md`, `Symmetrigaea_Simulation.py`,
`Symmetrigaea_Generator.py`, and `Symmetrigaea_CivFractal.py` together in one
folder. Zip that folder or publish it in a repository and attach the ZIP to a
release. The recipient installs Python with Tkinter and runs the command above.
The test file is optional for recipients but useful in a public source repository.
Do not include `__pycache__` or local Python installations. A standalone Windows
executable can be built later if recipients should not have to install Python.

## Files and checks

- `Symmetrigaea_Simulation.py`: Tkinter GUI.
- `Symmetrigaea_Generator.py`: engine-free generation and repair functions.
- `Symmetrigaea_CivFractal.py`: Python 2.4 port of unwrapped BTS fractal heights.
- `test_symmetrigaea.py`: deterministic geometry, noise, connectivity, and repair tests.

Run checks with:

```
python -B test_symmetrigaea.py
python -B test_symmetrigaea.py --gui
```

The optional GUI check creates a hidden Tk window, exercises generation and view
switching, and then closes it. It does not replace a visual inspection of the app.

Source intentionally uses Python 2.4-compatible syntax and avoids newer standard
library dependencies in generation logic. Running tests on Python 3 does not
establish compatibility with BTS's embedded runtime. The actual mapscript must be
tested inside the game, especially for division semantics and synchronized RNG use.

The user confirmed GUI startup after the Tcl 9 tracing fix. The generation test
suite covers core placement, complete rotated shapes, per-axis ocean margins,
donut enclosures, mask-area targets, maximum overlap, symmetry, repeatability,
connectivity, and repair budgets.
