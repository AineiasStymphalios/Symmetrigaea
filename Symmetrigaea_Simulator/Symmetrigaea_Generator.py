"""Engine-free geometry and approximate plot generation for Symmetrigaea.

Python 2.4-compatible source, also executable on Python 3.
This module does not reproduce CyFractal or depend on Civ4 extensions.
"""

import heapq
import math
import random
from Symmetrigaea_CivFractal import CivFractal, CivRandom


DEFAULTS = {
    "width": 96, "height": 64, "symmetry": "mirror", "pairs": 4,
    "region_width": 30, "region_height": 40, "variation": 25,
    "ellipse_weight": 70, "rect_weight": 30, "triangle_weight": 0,
    "overlap": 5, "water": 60, "grain": 3, "hills_grain": 4,
    "edge_reduction": True,
    "bridge_width": 3, "repair_budget": 25, "seed": 12345,
    "ocean_margin_x": 5, "ocean_margin_y": 2,
    "max_overlap": 40, "min_mask_area": 30, "max_mask_area": 60,
    "donut_hole": True, "hole_width": 35, "hole_height": 20,
    "hole_water": 60, "hole_grain": 1, "hole_variation": 5,
    "hole_angle": 0, "hole_rotation": 20, "hole_jitter_x": 3, "hole_jitter_y": 3
}

LIMITS = {
    "width": (24, 192), "height": (24, 192), "pairs": (1, 12),
    "region_width": (10, 60), "region_height": (10, 60),
    "variation": (0, 50), "ellipse_weight": (0, 100),
    "rect_weight": (0, 100), "triangle_weight": (0, 100),
    "overlap": (5, 60), "water": (0, 85), "grain": (0, 6),
    "hills_grain": (0, 6),
    "bridge_width": (1, 7), "repair_budget": (0, 25),
    "seed": (0, 2147483647), "ocean_margin_x": (0, 30),
    "ocean_margin_y": (0, 30), "max_overlap": (5, 100),
    "min_mask_area": (0, 90), "max_mask_area": (1, 100),
    "hole_width": (2, 50), "hole_height": (2, 50),
    "hole_water": (1, 100), "hole_grain": (0, 6), "hole_variation": (0, 50),
    "hole_angle": (0, 359), "hole_rotation": (0, 180),
    "hole_jitter_x": (0, 20), "hole_jitter_y": (0, 20)
}

MAX_ATTEMPTS = 8
MAX_PROPOSALS = 200


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel():
        raise Cancelled("Generation cancelled")


def validate_settings(values):
    settings = DEFAULTS.copy()
    settings.update(values)
    # Ignore an obsolete core-count value from an older caller.
    settings.pop("core_count", None)
    settings.pop("octaves", None)
    settings.pop("hole_octaves", None)
    for key in LIMITS:
        try:
            number = int(settings[key])
        except (TypeError, ValueError, OverflowError):
            raise ValueError("%s must be a whole number." % key.replace("_", " "))
        if str(number) != str(settings[key]).strip():
            raise ValueError("%s must be a whole number." % key.replace("_", " "))
        low, high = LIMITS[key]
        if number < low or number > high:
            raise ValueError("%s must be between %d and %d." %
                             (key.replace("_", " "), low, high))
        settings[key] = number
    if settings["symmetry"] not in ("mirror", "rotation"):
        raise ValueError("Choose left-right reflection or 180-degree rotation.")
    if settings["bridge_width"] not in (1, 3, 5, 7):
        raise ValueError("Bridge width must be 1, 3, 5, or 7.")
    if settings["max_overlap"] < settings["overlap"]:
        raise ValueError("Maximum overlap must be at least the minimum overlap.")
    if settings["max_mask_area"] < settings["min_mask_area"]:
        raise ValueError("Max map-wide mask area must be at least the minimum.")
    if (settings["ellipse_weight"] + settings["rect_weight"] +
            settings["triangle_weight"]) == 0:
        raise ValueError("At least one shape weight must be greater than zero.")
    settings["edge_reduction"] = bool(settings["edge_reduction"])
    settings["donut_hole"] = bool(settings["donut_hole"])
    width = settings["width"]
    height = settings["height"]
    border_x, border_y = ocean_border(width, height, settings["ocean_margin_x"],
                                      settings["ocean_margin_y"])
    inside_w = width - 2 * border_x
    inside_h = height - 2 * border_y
    if settings["min_mask_area"] * width * height > 100 * inside_w * inside_h:
        raise ValueError("Minimum mask area exceeds the space inside the ocean margins.")
    core_width = width * settings["region_width"] / 100.0
    core_height = height * settings["region_height"] / 100.0
    if core_width > inside_w or core_height > inside_h:
        raise ValueError("The core region does not fit inside the ocean margins. "
                         "Reduce region width/height or ocean margin.")
    return settings


def ocean_border(width, height, percent_x=5, percent_y=2):
    """Round each axis's own percentage up to a whole-tile margin."""
    return ((width * percent_x + 99) // 100,
            (height * percent_y + 99) // 100)


def mirror_index(index, width, height, symmetry):
    x = index % width
    y = index // width
    if symmetry == "rotation":
        y = height - 1 - y
    return y * width + width - 1 - x


def neighbors(index, width, height):
    x = index % width
    y = index // width
    result = []
    if x > 0:
        result.append(index - 1)
    if x + 1 < width:
        result.append(index + 1)
    if y > 0:
        result.append(index - width)
    if y + 1 < height:
        result.append(index + width)
    return result


def components(land, width, height):
    """Four-neighbor components, largest first; ties use the lowest tile index."""
    unseen = set(land)
    groups = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        group = set([start])
        stack = [start]
        while stack:
            index = stack.pop()
            for other in neighbors(index, width, height):
                if other in unseen:
                    unseen.remove(other)
                    group.add(other)
                    stack.append(other)
        groups.append(group)
    groups.sort(key=lambda group: (-len(group), min(group)))
    return groups


def land_stats(land, width, height):
    groups = components(land, width, height)
    largest = 0
    secondary = 0
    if groups:
        largest = len(groups[0])
    if len(groups) > 1:
        secondary = len(groups[1])
    share = 0.0
    if land:
        share = 100.0 * largest / len(land)
    accepted = bool(land) and largest * 100 >= len(land) * 97
    accepted = accepted and secondary * 100 <= len(land)
    return {"land": len(land), "coverage": 100.0 * len(land) / (width * height),
            "components": len(groups), "largest": largest, "share": share,
            "secondary": secondary, "accepted": accepted}


class Region:
    def __init__(self, name, shape, cx, cy, width, height, angle, pair):
        self.name = name
        self.shape = shape
        self.cx = cx
        self.cy = cy
        self.width = width
        self.height = height
        self.angle = angle
        self.pair = pair
        self.tiles = {}
        self.bounds = (0, 0, -1, -1)

    def transformed(self, map_width, map_height, symmetry):
        cy = self.cy
        angle = -self.angle
        if symmetry == "rotation":
            cy = map_height - self.cy
            angle = self.angle + 180
        other = Region(self.name + "'", self.shape, map_width - self.cx,
                       cy, self.width, self.height, angle % 360, self.pair)
        for index in self.tiles:
            target = mirror_index(index, map_width, map_height, symmetry)
            other.tiles[target] = self.tiles[index]
        other.update_bounds(map_width)
        return other

    def update_bounds(self, map_width):
        if not self.tiles:
            self.bounds = (0, 0, -1, -1)
            return
        xs = [index % map_width for index in self.tiles]
        ys = [index // map_width for index in self.tiles]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))

    def extents(self):
        """Exact rotated shape bounds relative to the center, before rasterizing."""
        radians = math.radians(self.angle)
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        radius_x = self.width / 2.0
        radius_y = self.height / 2.0
        if self.shape == "ELLIPSE":
            dx = math.sqrt((radius_x * cos_a) ** 2 + (radius_y * sin_a) ** 2)
            dy = math.sqrt((radius_x * sin_a) ** 2 + (radius_y * cos_a) ** 2)
            return (-dx, -dy, dx, dy)
        if self.shape == "RECT":
            dx = abs(radius_x * cos_a) + abs(radius_y * sin_a)
            dy = abs(radius_x * sin_a) + abs(radius_y * cos_a)
            return (-dx, -dy, dx, dy)
        points = [(-radius_x, -self.height / 3.0),
                  (radius_x, -self.height / 3.0), (0.0, self.height * 2.0 / 3.0)]
        xs = []
        ys = []
        for x, y in points:
            xs.append(x * cos_a - y * sin_a)
            ys.append(x * sin_a + y * cos_a)
        return (min(xs), min(ys), max(xs), max(ys))

    def fits_inside(self, map_width, map_height, border):
        border_x, border_y = border
        min_x, min_y, max_x, max_y = self.extents()
        epsilon = 0.000000001
        return (self.cx + min_x >= border_x - epsilon and
                self.cx + max_x <= map_width - border_x + epsilon and
                self.cy + min_y >= border_y - epsilon and
                self.cy + max_y <= map_height - border_y + epsilon)

    def rasterize(self, map_width, map_height, border):
        """Rasterize a complete shape; refuse masks that would require clipping."""
        if not self.fits_inside(map_width, map_height, border):
            raise ValueError("Region %s does not fit inside the ocean margin." % self.name)
        border_x, border_y = border
        min_x, min_y, max_x, max_y = self.extents()
        radians = math.radians(self.angle)
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        radius_x = self.width / 2.0
        radius_y = self.height / 2.0
        v_dist = self.height * 2.0 / 3.0
        b_dist = self.height / 3.0
        west = max(border_x, int(math.floor(self.cx + min_x)))
        east = min(map_width - border_x - 1, int(math.ceil(self.cx + max_x)))
        south = max(border_y, int(math.floor(self.cy + min_y)))
        north = min(map_height - border_y - 1, int(math.ceil(self.cy + max_y)))
        self.tiles = {}
        for y in range(south, north + 1):
            for x in range(west, east + 1):
                dx = x + 0.5 - self.cx
                dy = y + 0.5 - self.cy
                rx = dx * cos_a + dy * sin_a
                ry = -dx * sin_a + dy * cos_a
                fill = 2.0
                if self.shape == "ELLIPSE":
                    fill = math.sqrt((rx / radius_x) ** 2 + (ry / radius_y) ** 2)
                elif self.shape == "RECT":
                    fill = max(abs(rx) / radius_x, abs(ry) / radius_y)
                elif ry >= -b_dist and ry <= v_dist:
                    max_rx = radius_x * (v_dist - ry) / self.height
                    if abs(rx) <= max_rx:
                        margin = min(ry + b_dist, v_dist - ry, max_rx - abs(rx))
                        band = min(radius_x, self.height) * 0.20
                        fill = 1.0 - margin / band
                if fill <= 1.0 + 0.0000000001:
                    self.tiles[y * map_width + x] = fill
        self.update_bounds(map_width)


def strong_overlap(a, b, percent, width):
    shared = set(a).intersection(b)
    if len(shared) * 100 < percent * min(len(a), len(b)):
        return False
    for index in shared:
        if index % width + 1 < width:
            if (index + 1 in shared and index + width in shared and
                    index + width + 1 in shared):
                return True
    return False


def exceeds_overlap(a, b, percent):
    """The cap applies to the smaller mask, including mirrored partners."""
    shared = len(set(a).intersection(b))
    return shared * 100 > percent * min(len(a), len(b))


def choose_shape(rng, settings):
    choices = [("ELLIPSE", settings["ellipse_weight"]),
               ("RECT", settings["rect_weight"]),
               ("ISOTRI", settings["triangle_weight"])]
    total = sum([choice[1] for choice in choices])
    roll = rng.randrange(total)
    for shape, weight in choices:
        if roll < weight:
            return shape
        roll -= weight
    return "ELLIPSE"


def build_cores(settings, rng):
    width = settings["width"]
    height = settings["height"]
    border = ocean_border(width, height, settings["ocean_margin_x"],
                          settings["ocean_margin_y"])
    border_x, border_y = border
    core_w = width * settings["region_width"] / 100.0
    core_h = height * settings["region_height"] / 100.0
    inside_h = height - 2 * border_y
    if core_w > width - 2 * border_x:
        return None
    if core_h > inside_h:
        return None
    cy = height / 2.0
    if settings["symmetry"] == "mirror":
        cy = rng.uniform(border_y + core_h / 2.0,
                         height - border_y - core_h / 2.0)
    core = Region("Core", "ELLIPSE", width / 2.0, cy, core_w, core_h, 0, 0)
    if not core.fits_inside(width, height, border):
        return None
    core.rasterize(width, height, border)
    if not core.tiles or len(components(core.tiles, width, height)) != 1:
        return None
    return [core]


def build_water_region(regions, settings, layout_seed=None):
    """Sample bounded hole geometry independently of the shoreline noise seed."""
    if not settings["donut_hole"]:
        return None
    width = settings["width"]
    height = settings["height"]
    anchor_x = width / 2.0
    anchor_y = height / 2.0
    if layout_seed is None:
        layout_seed = settings["seed"]
    rng = random.Random((layout_seed + 15485863) % 2147483648)
    base_w = max(2.0, width * settings["hole_width"] / 100.0)
    base_h = max(2.0, height * settings["hole_height"] / 100.0)
    size_limit = settings["hole_variation"] / 100.0
    shift_x = width * settings["hole_jitter_x"] / 100.0
    shift_y = height * settings["hole_jitter_y"] / 100.0
    border = ocean_border(width, height, settings["ocean_margin_x"],
                          settings["ocean_margin_y"])
    # Leave two tiles for the shore. Intersect valid coordinates with the user's
    # displacement bounds rather than silently moving the hole beyond them.
    shore_border = (border[0] + 2, border[1] + 2)
    for proposal in range(MAX_PROPOSALS):
        hole_w = rng.uniform(max(2.0, base_w * (1.0 - size_limit)), base_w * (1.0 + size_limit))
        hole_h = rng.uniform(max(2.0, base_h * (1.0 - size_limit)), base_h * (1.0 + size_limit))
        angle = (settings["hole_angle"] + rng.uniform(-settings["hole_rotation"],
                                                      settings["hole_rotation"])) % 360.0
        hole = Region("Water footprint", "ELLIPSE", 0.0, 0.0, hole_w, hole_h, angle, 0)
        min_x, min_y, max_x, max_y = hole.extents()
        low_x = max(anchor_x - shift_x, shore_border[0] - min_x)
        high_x = min(anchor_x + shift_x, width - shore_border[0] - max_x)
        low_y = max(anchor_y - shift_y, shore_border[1] - min_y)
        high_y = min(anchor_y + shift_y, height - shore_border[1] - max_y)
        if low_x > high_x or low_y > high_y:
            continue
        hole.cx = rng.uniform(low_x, high_x)
        hole.cy = rng.uniform(low_y, high_y)
        if not hole.fits_inside(width, height, shore_border):
            continue
        hole.rasterize(width, height, border)
        if hole.tiles and len(components(hole.tiles, width, height)) == 1:
            return hole
    raise ValueError("No donut footprint fits within the variation limits and ocean margin. "
                     "Reduce hole dimensions or ocean margin, or adjust its variation limits.")


def build_layout(settings, seed, cancel=None):
    rng = random.Random(seed)
    width = settings["width"]
    height = settings["height"]
    border = ocean_border(width, height, settings["ocean_margin_x"],
                          settings["ocean_margin_y"])
    border_x, border_y = border
    base_w = width * settings["region_width"] / 100.0
    base_h = height * settings["region_height"] / 100.0
    regions = build_cores(settings, rng)
    if regions is None:
        return None
    try:
        build_water_region(regions, settings, seed)
    except ValueError:
        return None
    union = union_masks(regions)
    variation = settings["variation"] / 100.0
    for pair in range(1, settings["pairs"] + 1):
        placed = False
        for proposal in range(MAX_PROPOSALS):
            check_cancel(cancel)
            reg_w = base_w * rng.uniform(1 - variation, 1 + variation)
            reg_h = base_h * rng.uniform(1 - variation, 1 + variation)
            candidate = Region("R%d" % pair, choose_shape(rng, settings),
                               0.0, 0.0, reg_w, reg_h, rng.randrange(360), pair)
            min_x, min_y, max_x, max_y = candidate.extents()
            low_x = border_x - min_x
            high_x = min(width / 2.0 - 0.5, width - border_x - max_x)
            low_y = border_y - min_y
            high_y = height - border_y - max_y
            if low_x > high_x or low_y > high_y:
                continue
            cx = rng.uniform(low_x, high_x)
            cy = rng.uniform(low_y, high_y)
            candidate.cx = cx
            candidate.cy = cy
            if not candidate.fits_inside(width, height, border):
                continue
            too_close = False
            for existing in regions:
                spacing = 0.25 * min(reg_w, reg_h, existing.width, existing.height)
                if (cx - existing.cx) ** 2 + (cy - existing.cy) ** 2 < spacing ** 2:
                    too_close = True
                    break
            if too_close:
                continue
            candidate.rasterize(width, height, border)
            if len(candidate.tiles) < 4:
                continue
            if len(components(candidate.tiles, width, height)) != 1:
                continue
            touches = False
            for existing in regions:
                if strong_overlap(candidate.tiles, existing.tiles,
                                  settings["overlap"], width):
                    touches = True
                    break
            if not touches:
                continue
            partner = candidate.transformed(width, height, settings["symmetry"])
            if not partner.fits_inside(width, height, border):
                continue
            spacing = 0.25 * min(reg_w, reg_h)
            if ((candidate.cx - partner.cx) ** 2 +
                    (candidate.cy - partner.cy) ** 2 < spacing ** 2):
                continue
            excessive = exceeds_overlap(candidate.tiles, partner.tiles, settings["max_overlap"])
            for existing in regions:
                if (exceeds_overlap(candidate.tiles, existing.tiles, settings["max_overlap"]) or
                        exceeds_overlap(partner.tiles, existing.tiles, settings["max_overlap"])):
                    excessive = True
                    break
            if excessive:
                continue
            regions.extend([candidate, partner])
            union.update(candidate.tiles)
            union.update(partner.tiles)
            placed = True
            break
        if not placed:
            return None
    if len(components(union, width, height)) != 1:
        return None
    return regions


def local_water_percent(water, fill, reduce_edges, subtractive=False):
    if not reduce_edges or water <= 0 or water >= 100:
        return water
    center = 0.0
    edge = 0.0
    if fill < 0.45:
        center = 2.0
    elif fill < 0.65:
        center = (0.65 - fill) / 0.20 * 2.0
    if fill > 0.80:
        edge = (fill - 0.80) / 0.20
    edge = min(1.0, edge)
    center = min(1.0, center)
    if edge > 0:
        if subtractive:
            return int(water * (1.0 - edge))
        return min(100, water + int((100 - water) * edge))
    if center > 0:
        if subtractive:
            return min(100, water + int((100 - water) * center))
        return int(water * (1.0 - center))
    return water


def generate_plots(regions, settings, seed, cancel=None):
    rng = CivRandom(seed)
    width = settings["width"]
    land = set()
    for region in regions:
        check_cancel(cancel)
        west, south, east, north = region.bounds
        rw = east - west + 1
        rh = north - south + 1
        fractal = CivFractal(rw, rh, settings["grain"], rng,
                             lambda: check_cancel(cancel))
        thresholds = [-1]
        for percent in range(1, 100):
            thresholds.append(fractal.get_height_from_percent(percent))
        thresholds.append(255)
        for index in region.tiles:
            x = index % width - west
            y = index // width - south
            percent = local_water_percent(settings["water"], region.tiles[index],
                                          settings["edge_reduction"])
            if fractal.get_height(x, y) > thresholds[percent]:
                land.add(index)
    return land


def generate_water_mask(region, settings, noise_seed, cancel=None):
    """Grow connected water through low fractal heights, up to the chosen coverage.

    Independent thresholding would fragment the required hole into separate ponds.
    Growth preserves a single connected sea while letting noise shape the shore.
    """
    if region is None:
        return set()
    width = settings["width"]
    height = settings["height"]
    eligible = set(region.tiles)
    count = max(1, (len(eligible) * settings["hole_water"] + 99) // 100)
    if count >= len(eligible):
        return eligible
    west, south, east, north = region.bounds
    rw = east - west + 1
    rh = north - south + 1
    rng = CivRandom((noise_seed + 32452843) % 2147483648)
    fractal = CivFractal(rw, rh, settings["hole_grain"], rng,
                         lambda: check_cancel(cancel))
    thresholds = [-1]
    if settings["edge_reduction"]:
        for percent in range(1, 100):
            thresholds.append(fractal.get_height_from_percent(percent))
    thresholds.append(255)
    # sorted(..., key=...) is available in Python 2.4; min(..., key=...) is not.
    start = sorted(eligible, key=lambda index: (region.tiles[index], index))[0]
    water = set([start])
    visited = set([start])
    queue = []
    current = start
    while len(water) < count:
        check_cancel(cancel)
        for other in neighbors(current, width, height):
            if other in eligible and other not in visited:
                visited.add(other)
                x = other % width - west
                y = other // width - south
                priority = fractal.get_height(x, y)
                if settings["edge_reduction"]:
                    percent = local_water_percent(settings["hole_water"],
                                                  region.tiles[other], True, True)
                    priority -= thresholds[percent]
                heapq.heappush(queue, (priority, other))
        if not queue:
            raise ValueError("The water footprint must be connected before adding noise.")
        priority, current = heapq.heappop(queue)
        water.add(current)
    return water


def bridge_path(main, target, land, union, width, height, border, cancel=None, forbidden=None):
    """Dijkstra search from the smaller component to the main continent."""
    border_x, border_y = border
    if forbidden is None:
        forbidden = set()
    queue = []
    costs = {}
    previous = {}
    for index in sorted(target):
        if index in forbidden:
            continue
        costs[index] = 0
        heapq.heappush(queue, (0, index))
    iterations = 0
    while queue:
        cost, index = heapq.heappop(queue)
        if cost != costs.get(index):
            continue
        iterations += 1
        if iterations % 256 == 0:
            check_cancel(cancel)
        if index in main:
            path = [index]
            while index in previous:
                index = previous[index]
                path.append(index)
            return path
        for other in neighbors(index, width, height):
            if other in forbidden:
                continue
            x = other % width
            y = other // width
            if (x < border_x or x >= width - border_x or
                    y < border_y or y >= height - border_y):
                continue
            step_cost = 30
            if other in land:
                step_cost = 1
            elif other in union:
                step_cost = 10
            new_cost = cost + step_cost
            if new_cost < costs.get(other, 1000000000):
                costs[other] = new_cost
                previous[other] = index
                heapq.heappush(queue, (new_cost, other))
    return []


def widen_bridge(path, settings, forbidden=None):
    width = settings["width"]
    height = settings["height"]
    border_x, border_y = ocean_border(width, height, settings["ocean_margin_x"],
                                      settings["ocean_margin_y"])
    radius = settings["bridge_width"] // 2
    tiles = set()
    for index in path:
        x = index % width
        y = index // width
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx = x + dx
                ny = y + dy
                if (nx >= border_x and nx < width - border_x and
                        ny >= border_y and ny < height - border_y):
                    other = ny * width + nx
                    tiles.add(other)
                    tiles.add(mirror_index(other, width, height, settings["symmetry"]))
    if forbidden is not None:
        tiles.difference_update(forbidden)
    return tiles


def water_neighbors(index, width, height):
    """Use eight neighbors for water so diagonal ocean leaks are not accepted."""
    x = index % width
    y = index // width
    result = []
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if dx == 0 and dy == 0:
                continue
            nx = x + dx
            ny = y + dy
            if nx >= 0 and nx < width and ny >= 0 and ny < height:
                result.append(ny * width + nx)
    return result


def hole_enclosed(land, water_mask, width, height):
    """The protected sea must be enclosed by the main land component."""
    if not water_mask:
        return True
    if water_mask.intersection(land):
        return False
    groups = components(land, width, height)
    if not groups:
        return False
    main = groups[0]
    visited = set(water_mask)
    stack = list(water_mask)
    while stack:
        index = stack.pop()
        x = index % width
        y = index // width
        if x == 0 or x == width - 1 or y == 0 or y == height - 1:
            return False
        for other in water_neighbors(index, width, height):
            # Only the main continent counts as an enclosing barrier. Small
            # islands inside a noisy lake neither invalidate nor enclose it.
            if other not in main and other not in visited:
                visited.add(other)
                stack.append(other)
    return True


def hole_shore(water_mask, width, height):
    """Two-tile shore around the reserved water, including diagonal neighbors."""
    expanded = set(water_mask)
    frontier = set(water_mask)
    for step in range(2):
        new_tiles = set()
        for index in frontier:
            new_tiles.update(water_neighbors(index, width, height))
        new_tiles.difference_update(expanded)
        expanded.update(new_tiles)
        frontier = new_tiles
    return expanded.difference(water_mask)


def repair_land(raw, union, settings, cancel=None, forbidden=None):
    width = settings["width"]
    height = settings["height"]
    border = ocean_border(width, height, settings["ocean_margin_x"],
                          settings["ocean_margin_y"])
    land = set(raw)
    if forbidden is not None:
        land.difference_update(forbidden)
    else:
        forbidden = set()
    addition_limit = len(raw) * settings["repair_budget"] // 100
    removal_limit = int(math.ceil(len(raw) / 100.0))
    removed = 0
    reason = "Connectivity target reached."
    if forbidden and not hole_enclosed(land, forbidden, width, height):
        shore = hole_shore(forbidden, width, height)
        border_x, border_y = border
        for index in shore:
            x = index % width
            y = index // width
            if (x < border_x or x >= width - border_x or
                    y < border_y or y >= height - border_y):
                return land, "The donut shore would invade the ocean margin."
        candidate = land.union(shore)
        if len(candidate.difference(raw)) > addition_limit:
            return land, "Closing the donut shore exceeds the repair budget."
        land = candidate
    # Each successful step joins a component or removes one; cap all work as well.
    for iteration in range(max(1, len(raw))):
        check_cancel(cancel)
        stats = land_stats(land, width, height)
        if stats["accepted"] and hole_enclosed(land, forbidden, width, height):
            break
        groups = components(land, width, height)
        if len(groups) < 2:
            reason = "No land was generated."
            break
        tiny = []
        for group in groups[1:]:
            if len(group) <= 2 and removed + len(group) <= removal_limit:
                tiny.append(group)
                removed += len(group)
        if tiny:
            for group in tiny:
                land.difference_update(group)
            continue
        path = bridge_path(groups[0], groups[1], land, union,
                           width, height, border, cancel, forbidden)
        if not path:
            reason = "No bridge route inside the ocean border."
            break
        candidate = land.union(widen_bridge(path, settings, forbidden))
        if len(candidate.difference(raw)) > addition_limit:
            reason = "Required bridge exceeds the repair budget."
            break
        if candidate == land:
            reason = "Repair made no progress."
            break
        land = candidate
    if reason == "Connectivity target reached.":
        if not hole_enclosed(land, forbidden, width, height):
            reason = "The donut hole is not enclosed by the main continent."
        elif not land_stats(land, width, height)["accepted"]:
            reason = "Repair limit reached."
    return land, reason


def union_masks(regions):
    union = set()
    for region in regions:
        union.update(region.tiles)
    return union


def make_result(regions, settings, noise_seed, attempt, cancel=None):
    union = union_masks(regions)
    layout_seed = (settings["seed"] + (attempt - 1) * 1000003) % 2147483648
    water_region = build_water_region(regions, settings, layout_seed)
    water_mask = set()
    if water_region is not None:
        water_mask = generate_water_mask(water_region, settings, noise_seed, cancel)
        union.difference_update(water_mask)
    raw = generate_plots(regions, settings, noise_seed, cancel)
    raw.difference_update(water_mask)
    if water_mask:
        repaired, reason = repair_land(raw, union, settings, cancel, water_mask)
    else:
        repaired, reason = repair_land(raw, union, settings, cancel)
    stats = land_stats(repaired, settings["width"], settings["height"])
    mask_coverage = 100.0 * len(union) / (settings["width"] * settings["height"])
    map_area = settings["width"] * settings["height"]
    mask_accepted = (len(union) * 100 >= settings["min_mask_area"] * map_area and
                     len(union) * 100 <= settings["max_mask_area"] * map_area)
    stats["connectivity_accepted"] = stats["accepted"]
    enclosed = hole_enclosed(repaired, water_mask, settings["width"], settings["height"])
    stats["accepted"] = stats["accepted"] and mask_accepted and enclosed
    if water_mask:
        if enclosed:
            reason = "Donut hole enclosed and protected. %s" % reason
        else:
            reason = "Donut enclosure target not met. %s" % reason
    if mask_coverage < settings["min_mask_area"]:
        reason = "Map-wide mask area %.1f%% is below the %d%% minimum. %s" % (
            mask_coverage, settings["min_mask_area"], reason)
    elif mask_coverage > settings["max_mask_area"]:
        reason = "Map-wide mask area %.1f%% is above the %d%% maximum. %s" % (
            mask_coverage, settings["max_mask_area"], reason)
    water_outline = None
    if water_region is not None:
        water_outline = Region("Protected water", water_region.shape, water_region.cx,
            water_region.cy, water_region.width, water_region.height, water_region.angle, 0)
        for index in water_mask:
            water_outline.tiles[index] = water_region.tiles[index]
        water_outline.update_bounds(settings["width"])
    return {"settings": settings.copy(), "regions": regions, "mask": union,
            "water_region": water_region, "water_mask": water_mask,
            "water_outline": water_outline,
            "hole_enclosed": enclosed,
            "mask_coverage": mask_coverage, "mask_accepted": mask_accepted,
            "raw": raw, "land": repaired, "added": repaired.difference(raw),
            "removed": raw.difference(repaired), "stats": stats,
            "raw_stats": land_stats(raw, settings["width"], settings["height"]),
            "noise_seed": noise_seed, "layout_attempt": attempt,
            "attempts": attempt, "reason": reason}


def result_rank(result):
    stats = result["stats"]
    area_score = 1.0
    coverage = result["mask_coverage"]
    minimum = result["settings"]["min_mask_area"]
    maximum = result["settings"]["max_mask_area"]
    if minimum > 0 and coverage < minimum:
        area_score = coverage / minimum
    elif coverage > maximum:
        area_score = maximum / coverage
    return (stats["accepted"], result["hole_enclosed"], stats["connectivity_accepted"], area_score,
            stats["share"], -stats["secondary"],
            -len(result["added"]) - len(result["removed"]))


def generate(values, progress=None, cancel=None):
    settings = validate_settings(values)
    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        check_cancel(cancel)
        if progress is not None:
            progress("Placing regions: attempt %d/%d" % (attempt, MAX_ATTEMPTS))
        layout_seed = (settings["seed"] + (attempt - 1) * 1000003) % 2147483648
        regions = build_layout(settings, layout_seed, cancel)
        if regions is None:
            continue
        if progress is not None:
            progress("Generating plots and checking connections: attempt %d/%d" %
                     (attempt, MAX_ATTEMPTS))
        noise_seed = (layout_seed + 104729) % 2147483648
        result = make_result(regions, settings, noise_seed, attempt, cancel)
        if best is None or result_rank(result) > result_rank(best):
            best = result
        if result["stats"]["accepted"]:
            return result
    if best is not None:
        best["attempts"] = MAX_ATTEMPTS
        return best
    raise ValueError("No connected region layout after 8 attempts. Try fewer pairs, "
                     "adjusting region size or ocean margin, lowering minimum overlap, "
                     "or raising maximum overlap. "
                     "If donut protection is enabled, try reducing the hole dimensions.")


def reroll_noise(result, noise_seed, progress=None, cancel=None):
    if progress is not None:
        progress("Rerolling noise on the current region layout...")
    return make_result(result["regions"], result["settings"], noise_seed,
                       result["layout_attempt"], cancel)
