from CvPythonExtensions import *
import CvUtil
import CvMapGeneratorUtil
from CvMapGeneratorUtil import MultilayeredFractal
from CvMapGeneratorUtil import TerrainGenerator
from CvMapGeneratorUtil import FeatureGenerator
import math
import heapq

'''
##############################################################################
GEOMETRIC MULTIFRACTAL NOTES

This mapscript was based on Earth2.py.

Below are its main features:
- GeometricMultiFractal Genrator: an improved MultilayeredFractal generator
	- Takes matrix inputs
	- More property inputs for regions
	- Allows Rectangular, Elliptical, and Triangular fractal masks with rotation.
- Custom Climate Generator
	- Generates terrain and features based on custom-placed temperature and moisture vectors.
- Bonus generator
	- Rewrote Vanilla's strategic and food bonus additions to starting plots
	- Optional team resource balancing and start resources
- Custom River / Waterway Generator
	- Allows generation of rivers and waterways through map coordinates.
- Optional two-team starting locations

- AineiasStymph, April 29, 2026
##############################################################################
'''


	
def getDescription():
	desc = "Generates a semi-symmetrical single-continent map."
	desc += "Option to generate an inland sea within the continent."
	return desc

def isAdvancedMap():
	"This map should show up in simple mode"
	return 0


# -----------------------------------------------------------------------------
# Custom Options
# -----------------------------------------------------------------------------
def getNumCustomMapOptions():
	return 10

def getCustomMapOptionName(argsList):
	index = argsList[0]
	names = [
		"World Wrap",
		"Continent Symmetry",
		"Center Terrain",
		"Climate Details",
		"Start Options",
		"Teamer Resource Balancing",
		"Land Food Across Map",
		"Land Food on Starts",
		"Strategic Resources Near Starts",
		"Reveal Start Area Radius"
	]
	if index < len(names):
		return names[index]
	return ""

def getNumCustomMapOptionValues(argsList):
	index = argsList[0]
	if index == 0: return 3 # World Wrap: Flat, Cylindrical, Toroidal
	if index == 1: return 2 # Left/right or rotational symmetry
	if index == 2: return 2 # Donut enabled or disabled
	if index == 3: return 3 # Moist center and rim, dry center, Civ4 default
	if index == 4: return 2 # Start Options: Team Start, Default Starts
	if index == 5: return 2 # Teamer Resource Balancing
	if index == 6: return 4 # Map-wide land food spacing
	if index == 7: return 4 # Land Food on Starts
	if index == 8: return 3 # Early strategic resources near starts
	if index == 9: return 4 # Reveal radius
	return 0

def getCustomMapOptionDescAt(argsList):
	index = argsList[0]
	selection = argsList[1]
	if index == 0: # World Wrap
		if selection == 0: return "Flat"
		elif selection == 1: return "Cylindrical"
		return "Toroidal"
	if index == 1: # Continent Symmetry
		if selection == 0: return "Left / Right"
		return "180-degree Rotation"
	if index == 2: # Center Terrain
		if selection == 0: return "Inland Sea"
		return "Land Bridge"
	if index == 3: # Climate Details
		if selection == 0: return "Moist center and Rim"
		if selection == 1: return "Dry Center"
		return "Civ4 default"
	if index == 4: # Start Options
		if selection == 0: return "Team Start"
		return "Default Starts"
	if index == 5: # Teamer Resource Balancing
		if selection == 0: return "Disabled"
		return "Enabled"
	if index == 6: # Land Food Across Map
		if selection == 0: return "Disabled"
		if selection == 1: return "Minimum spacing 3 tiles"
		if selection == 2: return "Minimum spacing 4 tiles"
		return "Minimum spacing 5 tiles"
	if index == 7: # Land Food on Starts
		if selection == 0: return "Disabled"
		if selection == 1: return "At least 1"
		if selection == 2: return "At least 2"
		return "At least 3"
	if index == 8: # Strategic Resources Near Starts
		if selection == 0: return "Disabled"
		if selection == 1: return "Ensure Iron + Copper OR Horse"
		return "Ensure Iron + Copper + Horse"
	if index == 9: # Reveal Start Area Radius
		if selection == 0: return "Disabled"
		if selection == 1: return "Radius 2"
		if selection == 2: return "Radius 3"
		return "Radius 4"
	return ""

def getCustomMapOptionDefault(argsList):
	index = argsList[0]
	if index == 0: return 1 # Cylindrical wrap
	if index == 1: return 1 # Symmetry
	if index == 2: return 0 # Center Terrain
	if index == 3: return 1 # Dry Center climate
	if index == 4: return 0 # Two-team starts
	if index == 5: return 1 # Teamer Resource Balancing enabled
	if index == 6: return 2 # Land food spacing 4
	if index == 7: return 2 # At least 2 start food
	if index == 8: return 1 # Iron and Copper or Horse
	if index == 9: return 0 # Reveal disabled
	return 0

# -----------------------------------------------------------------------------
# Map Properties
# -----------------------------------------------------------------------------

def getGridSize(argsList):
	# Map sizes here. Multiply each dimension by 4x to get map width and height.
	grid_sizes = {
		WorldSizeTypes.WORLDSIZE_DUEL:      (8, 5),
		WorldSizeTypes.WORLDSIZE_TINY:      (10, 6),
		WorldSizeTypes.WORLDSIZE_SMALL:     (13, 8),
		WorldSizeTypes.WORLDSIZE_STANDARD:  (16, 10),
		WorldSizeTypes.WORLDSIZE_LARGE:     (21, 13),
		WorldSizeTypes.WORLDSIZE_HUGE:      (26, 16),
	}
	if argsList[0] == -1:
		return []
	return grid_sizes[argsList[0]]

def isSeaLevelMap():
	return 1

def getWrapX():
	map = CyMap()
	return (map.getCustomMapOption(0) == 1 or map.getCustomMapOption(0) == 2)

def getWrapY():
	map = CyMap()
	return (map.getCustomMapOption(0) == 2)

def isClimateMap():
	return 1

def getClimate():
	"""This is now ignored by the engine because isClimateMap is 1, 
	but we keep it for safety."""
	return ClimateTypes.CLIMATE_TEMPERATE

_all_start_coords = [] # Store player start coords
def beforeGeneration():
	"""
	Official Civ4 hook called before map generation starts.
	Guaranteed to run on Map Regeneration and New Games.
	"""
	# Clear the starting plot cache
	global _START_PLOT_MAP, _TEAM_START_ACTIVE, _TEAM_SIDE_MAP
	global _INLAND_SEA_TILES, _RIVER_DISTANCE_CACHE, _MASK_GENERATION_FAILED
	_START_PLOT_MAP = None
	_TEAM_START_ACTIVE = False
	_TEAM_SIDE_MAP = {}
	_INLAND_SEA_TILES = set()
	_RIVER_DISTANCE_CACHE = None
	_MASK_GENERATION_FAILED = False
	
	# RESET CLIMATE GLOBALS HERE to prevent settings from "sticking"
	global _CLIMATE_ENGINE
	_CLIMATE_ENGINE = None
	
	return None

_DEBUG_REGIONS = [] # Global to store regions for sign placement
_MASK_GENERATION_FAILED = False

def _add_region_signs(region_data):
	"""Adds map signs to the center of each fractal region."""
	m = CyMap()
	engine = CyEngine()
	iW = m.getGridWidth()
	iH = m.getGridHeight()
	
	for data in region_data:
		name = data[0]
		cx = data[2]
		cy = data[3]
		
		# Convert fractional center to plot coordinates
		iX = int(iW * cx)
		iY = int(iH * cy)
		
		pPlot = m.plot(iX, iY)
		if pPlot and not pPlot.isNone():
			# -1 makes the sign visible to all players (global)
			engine.addSign(pPlot, -1, str(name))


# -----------------------------------------------------------------------------
# GeometricMultiFractal Generator
# -----------------------------------------------------------------------------
class GeometricMultiFractal(CvMapGeneratorUtil.MultilayeredFractal):
	"""
	Fractal generator supporting geometric masking and rotation.
	Shapes: RECT, ELLIPSE, ISOTRI.
	"""
	def getReducedEdgeWaterThreshold(self, r_type, water_prc, iWaterThreshold, iWaterThresholds,
	                                 rx, ry, invRxSq, invRySq, radius_x, radius_y,
	                                 height_tiles, b_dist, v_dist, max_rx, is_subtractive):
		fCenterInner = 0.45
		fCenterOuter = 0.65
		fCenterMultiplier = 2.0
		fEdgeInner = 0.80
		fEdgeOuter = 1.00
		fEdgeMultiplier = 1.0
		fIsotriEdgeBand = 0.20
		edgeStrength = 0.0
		centerStrength = 0.0
		shape_fill = 0.0
		if r_type == "ELLIPSE":
			shape_fill = math.sqrt((rx*rx * invRxSq) + (ry*ry * invRySq))
		elif r_type == "ISOTRI":
			edgeBand = min(radius_x, height_tiles) * fIsotriEdgeBand
			edgeMargin = min(ry + b_dist, v_dist - ry, max_rx - abs(rx))
			if edgeBand <= 0:
				shape_fill = 1.0
			else:
				shape_fill = 1.0 - (edgeMargin / edgeBand)
		else:
			if radius_x > 0: shape_fill = abs(rx) / radius_x
			if radius_y > 0:
				y_fill = abs(ry) / radius_y
				if y_fill > shape_fill: shape_fill = y_fill
		if shape_fill < fCenterInner:
			centerStrength = 1.0 * fCenterMultiplier
		elif shape_fill < fCenterOuter:
			if fCenterOuter > fCenterInner:
				centerStrength = ((fCenterOuter - shape_fill) / (fCenterOuter - fCenterInner)) * fCenterMultiplier
		if shape_fill > fEdgeInner:
			if fEdgeOuter > fEdgeInner:
				edgeStrength = ((shape_fill - fEdgeInner) / (fEdgeOuter - fEdgeInner)) * fEdgeMultiplier
		if edgeStrength > 1.0: edgeStrength = 1.0
		if centerStrength > 1.0: centerStrength = 1.0
		if edgeStrength > 0.0:
			if is_subtractive:
				iLocalWaterPercent = int(water_prc * (1.0 - edgeStrength))
				if iLocalWaterPercent <= 0: return -1
			else:
				iLocalWaterPercent = water_prc + int((100 - water_prc) * edgeStrength)
			return iWaterThresholds[iLocalWaterPercent]
		elif centerStrength > 0.0:
			if is_subtractive:
				iLocalWaterPercent = water_prc + int((100 - water_prc) * centerStrength)
				if iLocalWaterPercent >= 100: return 255
			else:
				iLocalWaterPercent = int(water_prc * (1.0 - centerStrength))
			return iWaterThresholds[iLocalWaterPercent]

		return iWaterThreshold

	def generatePlotsByRegion(self, region_data):
		sea = 0 
		
		# Define Terrain Profiles: (HillDensity%, PeakDensity%_of_Hills)
		terrain_profiles = {
			"flat":         (15, 1),
			"plateau":      (60, 25),
			"highland":     (75, 40),
			"alpine":       (95, 60),
			# "default":      (30, 20)
			"default":      (30, 40)
		}
		
		gc = CyGlobalContext()
		m = CyMap()
		iRocky = gc.getInfoTypeForString("CLIMATE_ROCKY")
		if m.getClimate() == iRocky:
			for key in terrain_profiles.keys():
				h_dens, p_dens = terrain_profiles[key]
				new_h = int(h_dens * 1.2)
				new_p = int(p_dens * 1.1)
				if new_h > 100: new_h = 100
				if new_p > 100: new_p = 100
				terrain_profiles[key] = (new_h, new_p)

		for data in region_data:
			name, r_type_raw, cx, cy, d1, d2, d3, terrain, grain, h_grain, water_prc, bReduceEdges = data
			r_type = r_type_raw.upper()
			
			# 1. Coordinate Math
			center_x = cx * self.iW
			center_y = cy * self.iH
			radius_x = (d1 / 2.0) * self.iW
			radius_y = (d2 / 2.0) * self.iH
			height_tiles = d2 * self.iH

			# Rotation/Geometry Math
			rad = -math.radians(d3)
			cosA, sinA = math.cos(rad), math.sin(rad)
			v_dist, b_dist = (2.0 / 3.0) * height_tiles, (1.0 / 3.0) * height_tiles
			invRxSq, invRySq = 0.0, 0.0
			if radius_x > 0: invRxSq = 1.0 / (radius_x * radius_x)
			if radius_y > 0: invRySq = 1.0 / (radius_y * radius_y)

			if r_type == "ELLIPSE":
				x_extent = math.sqrt((radius_x * cosA) * (radius_x * cosA) + (radius_y * sinA) * (radius_y * sinA))
				y_extent = math.sqrt((radius_x * sinA) * (radius_x * sinA) + (radius_y * cosA) * (radius_y * cosA))
				min_x = -x_extent
				max_x = x_extent
				min_y = -y_extent
				max_y = y_extent
			elif r_type == "ISOTRI":
				points = [(-radius_x, -b_dist), (radius_x, -b_dist), (0.0, v_dist)]
				min_x = 0.0
				max_x = 0.0
				min_y = 0.0
				max_y = 0.0
				for iPoint in range(len(points)):
					local_x, local_y = points[iPoint]
					world_dx = local_x * cosA + local_y * sinA
					world_dy = -local_x * sinA + local_y * cosA
					if iPoint == 0 or world_dx < min_x: min_x = world_dx
					if iPoint == 0 or world_dx > max_x: max_x = world_dx
					if iPoint == 0 or world_dy < min_y: min_y = world_dy
					if iPoint == 0 or world_dy > max_y: max_y = world_dy
			else:
				x_extent = abs(radius_x * cosA) + abs(radius_y * sinA)
				y_extent = abs(radius_x * sinA) + abs(radius_y * cosA)
				min_x = -x_extent
				max_x = x_extent
				min_y = -y_extent
				max_y = y_extent
			
			iWest = max(0, int(center_x + min_x))
			iEast = min(self.iW - 1, int(center_x + max_x))
			iSouth = max(0, int(center_y + min_y))
			iNorth = min(self.iH - 1, int(center_y + max_y))
			
			reg_w, reg_h = iEast - iWest + 1, iNorth - iSouth + 1
			if reg_w <= 0 or reg_h <= 0: continue

			# 2. Fractal Initialization
			NiTextOut("Generating %s (Geometric Fractal) ..." % name)
			
			# This fractal is now shared by BOTH Land and Water regions
			regionContFrac = CyFractal()
			regionContFrac.fracInit(reg_w, reg_h, grain, self.dice, self.iFlags, -1, -1)
			
			# Calculate threshold for the "Active" part of the fractal
			if water_prc <= 0:
				iWaterThreshold = -1
			elif water_prc >= 100:
				iWaterThreshold = 255
			else:
				iWaterThreshold = regionContFrac.getHeightFromPercent(water_prc + sea)

			is_subtractive = (terrain == "water")
			iWaterThresholds = []
			if bReduceEdges and water_prc > 0 and water_prc < 100:
				for iPercent in range(101):
					iWaterThresholds.append(regionContFrac.getHeightFromPercent(iPercent))
			
			# Only Land regions need Hill/Peak fractals
			if not is_subtractive:
				regionHillsFrac = CyFractal()
				regionPeaksFrac = CyFractal()
				regionHillsFrac.fracInit(reg_w, reg_h, h_grain, self.dice, 0, -1, -1)
				regionPeaksFrac.fracInit(reg_w, reg_h, h_grain+1, self.dice, 0, -1, -1)

				h_dens, p_dens = terrain_profiles.get(terrain, terrain_profiles["default"])
				iHillThreshold = regionHillsFrac.getHeightFromPercent(100 - h_dens)
				iPeakThreshold = regionPeaksFrac.getHeightFromPercent(100 - p_dens)

			# 3. Iterate over the grid
			for x in range(reg_w):
				world_x = x + iWest
				# Add 0.5 to world_x to get the center of the tile
				dx = (float(world_x) + 0.5) - center_x
				for y in range(reg_h):
					world_y = y + iSouth
					# Add 0.5 to world_y to get the center of the tile
					dy = (float(world_y) + 0.5) - center_y

					# Now, tiles on either side of an even-numbered split will have 
					# identical distance values (e.g., -0.5 and 0.5).
					# Geometry Check
					rx = dx * cosA - dy * sinA
					ry = dx * sinA + dy * cosA
					is_inside = False
					max_rx = 0.0
					if r_type == "ELLIPSE":
						if (rx*rx * invRxSq) + (ry*ry * invRySq) <= 1.0: is_inside = True
					elif r_type == "ISOTRI":
						if ry >= -b_dist and ry <= v_dist:
							max_rx = radius_x * (v_dist - ry) / height_tiles
							if abs(rx) <= max_rx: is_inside = True
					else: # RECT
						if abs(rx) <= radius_x and abs(ry) <= radius_y: is_inside = True

					if not is_inside: continue
						
					# Decide plot type
					world_i = world_y * self.iW + world_x
					val = regionContFrac.getHeight(x, y)
					# Edge reduction
					iLocalWaterThreshold = iWaterThreshold
					if bReduceEdges and water_prc > 0 and water_prc < 100:
						iLocalWaterThreshold = self.getReducedEdgeWaterThreshold(
							r_type, water_prc, iWaterThreshold, iWaterThresholds,
							rx, ry, invRxSq, invRySq, radius_x, radius_y,
							height_tiles, b_dist, v_dist, max_rx, is_subtractive)
					
					if is_subtractive:
						# WATER REGION: If fractal roll is within the water percent, punch a hole.
						# Setting water_prc=100 will now correctly turn every tile to ocean.
						if val <= iLocalWaterThreshold:
							self.wholeworldPlotTypes[world_i] = PlotTypes.PLOT_OCEAN
					else:
						# LAND REGION: Skip tiles within the water percent threshold (remains ocean).
						if val <= iLocalWaterThreshold: 
							continue
						
						# Process Hills and Peaks for land
						if regionHillsFrac.getHeight(x, y) >= iHillThreshold:
							if regionPeaksFrac.getHeight(x, y) >= iPeakThreshold:
								self.wholeworldPlotTypes[world_i] = PlotTypes.PLOT_PEAK
							else:
								self.wholeworldPlotTypes[world_i] = PlotTypes.PLOT_HILLS
						else:
							self.wholeworldPlotTypes[world_i] = PlotTypes.PLOT_LAND
							
		return self.wholeworldPlotTypes


SYMMETRIGAEA_SETTINGS = {
	"pairs": 3, "region_width": 25, "region_height": 35,
	"variation": 25, "ellipse_weight": 70, "rect_weight": 30,
	"overlap": 5, "max_overlap": 40, "mask_water": 50, "grain": 3,
	"hills_grain": 4,
	"edge_reduction": True, "ocean_margin_x": 5, "ocean_margin_y": 2,
	"min_total_mask_area": 40, "max_total_mask_area": 50,
	"bridge_width": 3, "repair_budget": 25,
	"hole_width": 40, "hole_height": 20, "hole_water": 60,
	"hole_grain": 1, "hole_variation": 5, "hole_angle": 0,
	"hole_rotation": 7, "hole_jitter_x": 1, "hole_jitter_y": 3
}


class SymmetrigaeaMaskGenerator:
	"""Build masks and pass regional plots to the existing GMF class."""
	def __init__(self):
		self.map = CyMap()
		self.width = self.map.getGridWidth()
		self.height = self.map.getGridHeight()
		self.dice = CyGlobalContext().getGame().getMapRand()
		# Sea level
		self.s = dict(SYMMETRIGAEA_SETTINGS)
		seaLevelType = CyGlobalContext().getSeaLevelInfo(self.map.getSeaLevel()).getType()
		pairsChange = 0
		seaChange = 0
		inlandSeaChange = 0
		if self.map.getCustomMapOption(2) == 1: # add extra pair if land bridge
			pairsChange = 1
		if seaLevelType == "SEALEVEL_LOW":
			pairsChange = 1
			seaChange = -10
			inlandSeaChange = -5
		elif seaLevelType == "SEALEVEL_HIGH":
			pairsChange = 0
			seaChange = 10
			inlandSeaChange = 10
		self.s["pairs"] = max(0, min(100, self.s["pairs"] + pairsChange))
		self.s["mask_water"] = max(0, min(100, self.s["mask_water"] + seaChange))
		self.s["hole_water"] = max(0, min(100, self.s["hole_water"] + inlandSeaChange))
		self.s["min_total_mask_area"] = max(0, min(100, self.s["min_total_mask_area"] - seaChange))
		self.s["max_total_mask_area"] = max(0, min(100, self.s["max_total_mask_area"] - seaChange))
		print "PY: Symmetrigaea sea level change %d; inland water %d; total mask area %d-%d" % (
			seaChange, self.s["hole_water"], self.s["min_total_mask_area"],
			self.s["max_total_mask_area"])
		self.retry_count = 32
		self.best_partial_layout = None
		self.bx = (self.width * self.s["ocean_margin_x"] + 99) // 100
		self.by = (self.height * self.s["ocean_margin_y"] + 99) // 100
		self.rotation = self.map.getCustomMapOption(1) == 1
		self.donut = self.map.getCustomMapOption(2) == 0

	def _uniform(self, low, high):
		if high <= low:
			return low
		return low + (high - low) * self.dice.get(65535, "Symmetrigaea") / 65534.0

	def _mirror(self, index):
		x = self.width - 1 - index % self.width
		y = index // self.width
		if self.rotation:
			y = self.height - 1 - y
		return y * self.width + x

	def _neighbors(self, index, diagonal):
		x = index % self.width
		y = index // self.width
		result = []
		for dy in range(-1, 2):
			for dx in range(-1, 2):
				if dx == 0 and dy == 0:
					continue
				if not diagonal and abs(dx) + abs(dy) != 1:
					continue
				nx = x + dx
				ny = y + dy
				if 0 <= nx < self.width and 0 <= ny < self.height:
					result.append(ny * self.width + nx)
		return result

	def _components(self, tiles):
		unseen = set(tiles)
		groups = []
		while unseen:
			start = min(unseen)
			unseen.remove(start)
			group = set([start])
			stack = [start]
			while stack:
				for other in self._neighbors(stack.pop(), False):
					if other in unseen:
						unseen.remove(other)
						group.add(other)
						stack.append(other)
			groups.append(group)
		groups.sort(key=lambda group: (-len(group), min(group)))
		return groups

	def _extents(self, region):
		rx = region["w"] / 2.0
		ry = region["h"] / 2.0
		c = math.cos(math.radians(region["angle"]))
		s = math.sin(math.radians(region["angle"]))
		if region["shape"] == "ELLIPSE":
			dx = math.sqrt((rx * c) ** 2 + (ry * s) ** 2)
			dy = math.sqrt((rx * s) ** 2 + (ry * c) ** 2)
		elif region["shape"] == "RECT":
			dx = abs(rx * c) + abs(ry * s)
			dy = abs(rx * s) + abs(ry * c)
		else:
			points = [(-rx, -region["h"] / 3.0), (rx, -region["h"] / 3.0),
			          (0.0, region["h"] * 2.0 / 3.0)]
			xs = []
			ys = []
			for px, py in points:
				xs.append(px * c - py * s)
				ys.append(px * s + py * c)
			return (min(xs), min(ys), max(xs), max(ys))
		return (-dx, -dy, dx, dy)

	def _region(self, name, shape, cx, cy, rw, rh, angle, shore):
		region = {"name": name, "shape": shape, "cx": cx, "cy": cy,
		          "w": rw, "h": rh, "angle": angle}
		min_x, min_y, max_x, max_y = self._extents(region)
		bx = self.bx + shore
		by = self.by + shore
		if (cx + min_x < bx or cx + max_x > self.width - bx or
		    cy + min_y < by or cy + max_y > self.height - by):
			return None
		west = max(bx, int(math.floor(cx + min_x)))
		east = min(self.width - bx - 1, int(math.ceil(cx + max_x)))
		south = max(by, int(math.floor(cy + min_y)))
		north = min(self.height - by - 1, int(math.ceil(cy + max_y)))
		c = math.cos(math.radians(angle))
		s = math.sin(math.radians(angle))
		rx = rw / 2.0
		ry = rh / 2.0
		tiles = {}
		for y in range(south, north + 1):
			for x in range(west, east + 1):
				dx = x + 0.5 - cx
				dy = y + 0.5 - cy
				px = dx * c + dy * s
				py = -dx * s + dy * c
				fill = 2.0
				if shape == "ELLIPSE":
					fill = math.sqrt((px / rx) ** 2 + (py / ry) ** 2)
				elif shape == "RECT":
					fill = max(abs(px) / rx, abs(py) / ry)
				elif -rh / 3.0 <= py <= rh * 2.0 / 3.0:
					limit = rx * (rh * 2.0 / 3.0 - py) / rh
					if abs(px) <= limit:
						margin = min(py + rh / 3.0, rh * 2.0 / 3.0 - py,
						             limit - abs(px))
						fill = 1.0 - margin / (min(rx, rh) * 0.20)
				if fill <= 1.0 + 0.0000000001:
					tiles[y * self.width + x] = fill
		if not tiles:
			return None
		region["tiles"] = tiles
		region["bounds"] = (west, south, east, north)
		return region

	def _overlap(self, a, b):
		shared = set(a["tiles"]).intersection(b["tiles"])
		small = min(len(a["tiles"]), len(b["tiles"]))
		cap = len(shared) * 100 > self.s["max_overlap"] * small
		if len(shared) * 100 < self.s["overlap"] * small:
			return (False, cap)
		for index in shared:
			if (index % self.width + 1 < self.width and
			    index + 1 in shared and index + self.width in shared and
			    index + self.width + 1 in shared):
				return (True, cap)
		return (False, cap)

	def _layout(self, attempt):
		base_w = self.width * self.s["region_width"] / 100.0
		base_h = self.height * self.s["region_height"] / 100.0
		core_y = self.height / 2.0
		if not self.rotation:
			core_y = self._uniform(self.by + base_h / 2.0,
			                       self.height - self.by - base_h / 2.0)
		core = self._region("Core", "ELLIPSE", self.width / 2.0,
		                    core_y, base_w, base_h, 0, 0)
		if core is None:
			return None
		regions = [core]
		union = set(core["tiles"])
		if self.best_partial_layout is None:
			self.best_partial_layout = (regions[:], set(union))
		variation = self.s["variation"] / 100.0
		floor = 1.0 - variation + 2.0 * variation * attempt / float(max(1, self.retry_count - 1))
		for pair in range(1, self.s["pairs"] + 1):
			placed = False
			for proposal in range(200):
				rw = base_w * self._uniform(floor, 1.0 + variation)
				rh = base_h * self._uniform(floor, 1.0 + variation)
				roll = self.dice.get(100, "Symmetrigaea shape")
				shape = "ELLIPSE"
				if roll >= self.s["ellipse_weight"]:
					shape = "RECT"
				angle = self.dice.get(360, "Symmetrigaea angle")
				trial = {"shape": shape, "w": rw, "h": rh, "angle": angle}
				min_x, min_y, max_x, max_y = self._extents(trial)
				low_x = self.bx - min_x
				high_x = min(self.width / 2.0 - 0.5,
				             self.width - self.bx - max_x)
				low_y = self.by - min_y
				high_y = self.height - self.by - max_y
				if low_x > high_x or low_y > high_y:
					continue
				cx = self._uniform(low_x, high_x)
				cy = self._uniform(low_y, high_y)
				too_close = False
				for existing in regions:
					spacing = 0.25 * min(rw, rh, existing["w"], existing["h"])
					if ((cx - existing["cx"]) ** 2 +
					    (cy - existing["cy"]) ** 2 < spacing ** 2):
						too_close = True
						break
				if too_close:
					continue
				candidate = self._region("R%d" % pair, shape, cx, cy,
				                         rw, rh, angle, 0)
				if candidate is None or len(candidate["tiles"]) < 4:
					continue
				if len(self._components(candidate["tiles"])) != 1:
					continue
				partner_y = cy
				partner_angle = -angle
				if self.rotation:
					partner_y = self.height - cy
					partner_angle = angle + 180
				partner = self._region("R%d'" % pair, shape, self.width - cx,
				                       partner_y, rw, rh, partner_angle % 360, 0)
				if partner is None:
					continue
				partner["tiles"] = {}
				for index in candidate["tiles"]:
					partner["tiles"][self._mirror(index)] = candidate["tiles"][index]
				touch = False
				excessive = self._overlap(candidate, partner)[1]
				for existing in regions:
					overlap, cap = self._overlap(candidate, existing)
					if overlap:
						touch = True
					if cap or self._overlap(partner, existing)[1]:
						excessive = True
						break
				if not touch or excessive:
					continue
				spacing = 0.25 * min(rw, rh)
				if ((cx - partner["cx"]) ** 2 +
				    (cy - partner["cy"]) ** 2 < spacing ** 2):
					continue
				regions.extend([candidate, partner])
				union.update(candidate["tiles"])
				union.update(partner["tiles"])
				if (self.best_partial_layout is None or
				    len(regions) >= len(self.best_partial_layout[0])):
					self.best_partial_layout = (regions[:], set(union))
				placed = True
				break
			if not placed:
				return None
		if len(self._components(union)) != 1:
			return None
		return (regions, union)

	def _add_fallback_pair(self, regions, mask):
		"""Avoid returning only the core when normal pair placement fails."""
		core = regions[0]
		for scale in (1.0, 0.85, 0.7):
			for shift in (0.65, 0.55, 0.75):
				rw = core["w"] * scale
				rh = core["h"] * scale
				cx = core["cx"] - core["w"] * shift
				cy = core["cy"]
				candidate = self._region("R1", "ELLIPSE", cx, cy, rw, rh, 0, 0)
				partner_y = cy
				if self.rotation: partner_y = self.height - cy
				partner = self._region("R1'", "ELLIPSE", self.width - cx,
				                       partner_y, rw, rh, 0, 0)
				if candidate is None or partner is None: continue
				partner["tiles"] = {}
				for index in candidate["tiles"]:
					partner["tiles"][self._mirror(index)] = candidate["tiles"][index]
				if not self._overlap(candidate, core)[0]: continue
				if not self._overlap(partner, core)[0]: continue
				newMask = mask.union(candidate["tiles"])
				newMask.update(partner["tiles"])
				if len(self._components(newMask)) == 1:
					return ([core, candidate, partner], newMask)
		return (regions, mask)

	def _hole(self):
		if not self.donut:
			return None
		base_w = self.width * self.s["hole_width"] / 100.0
		base_h = self.height * self.s["hole_height"] / 100.0
		variation = self.s["hole_variation"] / 100.0
		shift_x = self.width * self.s["hole_jitter_x"] / 100.0
		shift_y = self.height * self.s["hole_jitter_y"] / 100.0
		for proposal in range(200):
			rw = self._uniform(max(2.0, base_w * (1.0 - variation)),
			                   base_w * (1.0 + variation))
			rh = self._uniform(max(2.0, base_h * (1.0 - variation)),
			                   base_h * (1.0 + variation))
			angle = (self.s["hole_angle"] +
			         self._uniform(-self.s["hole_rotation"],
			                       self.s["hole_rotation"])) % 360.0
			trial = {"shape": "ELLIPSE", "w": rw, "h": rh, "angle": angle}
			min_x, min_y, max_x, max_y = self._extents(trial)
			low_x = max(self.width / 2.0 - shift_x, self.bx + 2 - min_x)
			high_x = min(self.width / 2.0 + shift_x,
			             self.width - self.bx - 2 - max_x)
			low_y = max(self.height / 2.0 - shift_y, self.by + 2 - min_y)
			high_y = min(self.height / 2.0 + shift_y,
			             self.height - self.by - 2 - max_y)
			if low_x > high_x or low_y > high_y:
				continue
			hole = self._region("Inland Sea", "ELLIPSE",
			                    self._uniform(low_x, high_x),
			                    self._uniform(low_y, high_y),
			                    rw, rh, angle, 2)
			if hole is not None and len(self._components(hole["tiles"])) == 1:
				return hole
		return None

	def _water(self, hole):
		if hole is None:
			return set()
		eligible = set(hole["tiles"])
		count = max(1, (len(eligible) * self.s["hole_water"] + 99) // 100)
		if count >= len(eligible):
			return eligible
		west, south, east, north = hole["bounds"]
		fractal = CyFractal()
		fractal.fracInit(east - west + 1, north - south + 1,
		                 self.s["hole_grain"], self.dice, 0, -1, -1)
		thresholds = [-1]
		for percent in range(1, 100):
			thresholds.append(fractal.getHeightFromPercent(percent))
		thresholds.append(255)
		start = sorted(eligible, key=lambda index: (hole["tiles"][index], index))[0]
		water = set([start])
		seen = set([start])
		queue = []
		current = start
		while len(water) < count:
			for other in self._neighbors(current, False):
				if other in eligible and other not in seen:
					seen.add(other)
					fill = hole["tiles"][other]
					local_percent = self.s["hole_water"]
					if self.s["edge_reduction"]:
						if fill > 0.80:
							local_percent = int(local_percent *
							                    (1.0 - min(1.0, (fill - 0.80) / 0.20)))
						elif fill < 0.65:
							strength = min(1.0, (0.65 - fill) / 0.20 * 2.0)
							local_percent += int((100 - local_percent) * strength)
					x = other % self.width - west
					y = other // self.width - south
					priority = fractal.getHeight(x, y) - thresholds[local_percent]
					heapq.heappush(queue, (priority, other))
			if not queue:
				return None
			priority, current = heapq.heappop(queue)
			water.add(current)
		return water

	def _accepted(self, land):
		if not land:
			return False
		groups = self._components(land)
		secondary = 0
		if len(groups) > 1:
			secondary = len(groups[1])
		return (len(groups[0]) * 100 >= len(land) * 97 and
		        secondary * 100 <= len(land))

	def _enclosed(self, land, water):
		if not water:
			return True
		if water.intersection(land):
			return False
		groups = self._components(land)
		if not groups:
			return False
		main = groups[0]
		seen = set(water)
		stack = list(water)
		while stack:
			index = stack.pop()
			x = index % self.width
			y = index // self.width
			if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
				return False
			for other in self._neighbors(index, True):
				if other not in main and other not in seen:
					seen.add(other)
					stack.append(other)
		return True

	def _bridge(self, main, target, land, mask, water):
		queue = []
		costs = {}
		previous = {}
		for index in sorted(target):
			costs[index] = 0
			heapq.heappush(queue, (0, index))
		while queue:
			cost, index = heapq.heappop(queue)
			if cost != costs.get(index):
				continue
			if index in main:
				path = [index]
				while index in previous:
					index = previous[index]
					path.append(index)
				return path
			for other in self._neighbors(index, False):
				x = other % self.width
				y = other // self.width
				if (other in water or x < self.bx or x >= self.width - self.bx or
				    y < self.by or y >= self.height - self.by):
					continue
				step = 30
				if other in land:
					step = 1
				elif other in mask:
					step = 10
				new_cost = cost + step
				if new_cost < costs.get(other, 1000000000):
					costs[other] = new_cost
					previous[other] = index
					heapq.heappush(queue, (new_cost, other))
		return []

	def _repair(self, raw, mask, water):
		land = set(raw)
		addition_limit = len(raw) * self.s["repair_budget"] // 100
		removal_limit = (len(raw) + 99) // 100
		removed = 0
		if water and not self._enclosed(land, water):
			shore = set()
			frontier = set(water)
			for step in range(2):
				next_frontier = set()
				for index in frontier:
					next_frontier.update(self._neighbors(index, True))
				shore.update(next_frontier)
				frontier = next_frontier
			shore.difference_update(water)
			for index in shore:
				x = index % self.width
				y = index // self.width
				if x < self.bx or x >= self.width - self.bx or y < self.by or y >= self.height - self.by:
					return None
			land.update(shore)
			if len(land.difference(raw)) > addition_limit:
				return None
		for iteration in range(max(1, len(raw))):
			if self._accepted(land) and self._enclosed(land, water):
				return land
			groups = self._components(land)
			if len(groups) < 2:
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
			path = self._bridge(groups[0], groups[1], land, mask, water)
			if not path:
				break
			radius = self.s["bridge_width"] // 2
			bridge = set()
			for index in path:
				x = index % self.width
				y = index // self.width
				for dy in range(-radius, radius + 1):
					for dx in range(-radius, radius + 1):
						nx = x + dx
						ny = y + dy
						if self.bx <= nx < self.width - self.bx and self.by <= ny < self.height - self.by:
							other = ny * self.width + nx
							bridge.add(other)
							bridge.add(self._mirror(other))
			bridge.difference_update(water)
			candidate = land.union(bridge)
			if candidate == land or len(candidate.difference(raw)) > addition_limit:
				break
			land = candidate
		if self._accepted(land) and self._enclosed(land, water):
			return land
		return None

	def _region_data(self, regions):
		data = []
		for region in regions:
			data.append((region["name"], region["shape"],
			             region["cx"] / float(self.width),
			             region["cy"] / float(self.height),
			             region["w"] / float(self.width),
			             region["h"] / float(self.height),
			             region["angle"], "default", self.s["grain"],
			             self.s["hills_grain"], self.s["mask_water"],
			             self.s["edge_reduction"]))
		return data

	def generate(self):
		global _MASK_GENERATION_FAILED
		map_area = self.width * self.height
		self.best_partial_layout = None
		last_layout = None
		last_candidate = None
		for attempt in range(self.retry_count):
			layout = self._layout(attempt)
			if layout is None:
				continue
			regions, mask = layout
			last_layout = (regions, set(mask))
			hole = self._hole()
			if self.donut and hole is None:
				continue
			water = self._water(hole)
			if water is None:
				continue
			mask.difference_update(water)
			last_candidate = (regions, set(mask), set(water), None)
			if (len(mask) * 100 < self.s["min_total_mask_area"] * map_area or
			    len(mask) * 100 > self.s["max_total_mask_area"] * map_area):
				continue
			data = self._region_data(regions)
			plots = GeometricMultiFractal().generatePlotsByRegion(data)
			for index in range(len(plots)):
				if index not in mask or index in water:
					plots[index] = PlotTypes.PLOT_OCEAN
			last_candidate = (regions, set(mask), set(water), plots)
			raw = set([index for index in range(len(plots))
			           if plots[index] != PlotTypes.PLOT_OCEAN])
			repaired = self._repair(raw, mask, water)
			if repaired is None:
				continue
			for index in raw.difference(repaired):
				plots[index] = PlotTypes.PLOT_OCEAN
			for index in repaired.difference(raw):
				plots[index] = PlotTypes.PLOT_LAND
			plots = _reduce_coastal_peaks(plots, self.width, self.height)
			return (plots, data, water)
		_MASK_GENERATION_FAILED = True
		print "PY: Symmetrigaea mask retries exhausted after %d attempts" % self.retry_count
		if last_candidate is not None:
			regions, mask, water, plots = last_candidate
			print "PY: Symmetrigaea using last generated candidate with %d pairs" % ((len(regions) - 1) // 2)
		elif last_layout is not None:
			regions, mask = last_layout
			water = set()
			plots = None
			print "PY: Symmetrigaea using last full region layout without inland sea"
		elif self.best_partial_layout is not None:
			regions, mask = self.best_partial_layout
			if len(regions) == 1:
				regions, mask = self._add_fallback_pair(regions, mask)
			water = set()
			plots = None
			print "PY: Symmetrigaea using best partial layout with %d of %d pairs" % (((len(regions) - 1) // 2), self.s["pairs"])
			if self.donut:
				hole = self._hole()
				if hole is not None:
					trialWater = self._water(hole)
					if trialWater:
						trialMask = mask.difference(trialWater)
						if self._enclosed(trialMask, trialWater):
							mask = trialMask
							water = trialWater
				if not water:
					print "PY: Symmetrigaea partial fallback cannot enclose an inland sea"
		else:
			base_w = self.width * self.s["region_width"] / 100.0
			base_h = self.height * self.s["region_height"] / 100.0
			core = self._region("Core", "ELLIPSE", self.width / 2.0,
			                    self.height / 2.0, base_w, base_h, 0, 0)
			if core is None:
				plots = [PlotTypes.PLOT_OCEAN] * map_area
				plots[(self.height // 2) * self.width + self.width // 2] = PlotTypes.PLOT_LAND
				print "PY: Symmetrigaea could not create a core fallback"
				return (plots, [], set())
			regions = [core]
			mask = set(core["tiles"])
			water = set()
			plots = None
			print "PY: Symmetrigaea had no usable layout; using core fallback"
		data = self._region_data(regions)
		if plots is None:
			plots = GeometricMultiFractal().generatePlotsByRegion(data)
			for index in range(len(plots)):
				if index not in mask or index in water:
					plots[index] = PlotTypes.PLOT_OCEAN
		plots = _reduce_coastal_peaks(plots, self.width, self.height)
		return (plots, data, water)


def _reduce_coastal_peaks(plotTypes, iW, iH):
	reducedPlots = []
	for x in range(iW):
		for y in range(iH):
			i = y * iW + x
			if plotTypes[i] != PlotTypes.PLOT_PEAK: continue
			bCoastal = False
			for dx in range(-1, 2):
				for dy in range(-1, 2):
					if dx == 0 and dy == 0: continue
					adjX = x + dx
					adjY = y + dy
					if adjX < 0 or adjX >= iW: continue
					if adjY < 0 or adjY >= iH: continue
					if plotTypes[adjY * iW + adjX] == PlotTypes.PLOT_OCEAN:
						bCoastal = True
						break
				if bCoastal: break
			if bCoastal: reducedPlots.append(i)
	for i in reducedPlots:
		plotTypes[i] = PlotTypes.PLOT_HILLS
	if reducedPlots:
		print "Symmetrigaea reduced %d coastal peaks to hills" % len(reducedPlots)
	return plotTypes


def generatePlotTypes():
	NiTextOut("Generating Symmetrigaea plots...")
	global _START_PLOT_MAP, _DEBUG_REGIONS, _INLAND_SEA_TILES
	global _RIVER_DISTANCE_CACHE, _MASK_GENERATION_FAILED
	_START_PLOT_MAP = None
	_INLAND_SEA_TILES = set()
	_RIVER_DISTANCE_CACHE = None
	_MASK_GENERATION_FAILED = False
	plots, _DEBUG_REGIONS, _INLAND_SEA_TILES = SymmetrigaeaMaskGenerator().generate()
	return plots


# -----------------------------------------------------------------------------
# Custom Climate Generation
# -----------------------------------------------------------------------------
_CLIMATE_ENGINE = None

def get_climate_engine():
	global _CLIMATE_ENGINE
	if _CLIMATE_ENGINE is None:
		m = CyMap()
		iW = m.getGridWidth()
		iH = m.getGridHeight()
		
		manager = CustomClimateManager(m)
		_CLIMATE_ENGINE = CustomClimateGenerator(manager, iW, iH)
		
	return _CLIMATE_ENGINE

class ClimateDriver:
	"""
	Data structure representing a single climate influence vector.
	target: "TEMP" or "MOISTURE"
	type: "LINEAR", "MIRRORED", "RADIAL"
	origin: Tuple (cX, cY)
	start_val: Float. Influence at the origin.
	end_val: Float. Influence at the radius boundary.
	radius: Float. The distance of the transition.
	angle: Rotation of the vector (for Linear/Mirrored).
	"""
	def __init__(self, target, type, origin, start_val, end_val, radius, angle=0.0):
		self.target = target
		self.type = type
		self.origin = origin
		self.start_val = start_val
		self.end_val = end_val
		self.radius = radius
		self.angle = angle

class CustomClimateGenerator:
	"""
	The engine that processes a specific X, Y coordinate against the Driver Stack.
	"""
	def __init__(self, manager, iW, iH):
		self.manager = manager
		self.iW = float(iW)
		self.iH = float(iH)
		
		# Initialize fractal noise for jitter (Increased grain for visible scatter)
		gc = CyGlobalContext()
		self.noise = CyFractal()
		self.noise.fracInit(int(iW), int(iH), 3, gc.getGame().getMapRand(), 0, -1, -1)

	def get_climate_at(self, iX, iY):
		fx = float(iX) / self.iW
		fy = float(iY) / self.iH
		
		temp = self.manager.base_temp
		moisture = self.manager.base_moisture
		
		for driver in self.manager.drivers:
			# Vector from driver origin to current plot
			dx = fx - driver.origin[0]
			dy = fy - driver.origin[1]
			
			# 1. Determine Distance Factor (0.0 to 1.0)
			factor = 1.1 # Default to "Outside Radius"
			
			if driver.type == "RADIAL":
				dist = math.sqrt(dx*dx + dy*dy)
				factor = dist / driver.radius
				
			else: # LINEAR or MIRRORED
				rad = math.radians(driver.angle)
				cosA, sinA = math.cos(rad), math.sin(rad)
				
				# Dot Product: Projects the distance vector onto the angle's direction
				proj_dist = (dx * cosA) + (dy * sinA)
				
				if driver.type == "LINEAR":
					# Tiles behind the origin are outside the linear influence.
					if proj_dist >= -1e-12:
						factor = max(0.0, proj_dist) / driver.radius
						
				elif driver.type == "MIRRORED":
					# Symmetrical falloff on both sides of the axis
					factor = abs(proj_dist) / driver.radius
			
			# 2. Only apply if within radius
			if factor <= 1.0:
				# Linear Interpolation: Start + (Percentage * Difference)
				val_change = driver.start_val + (factor * (driver.end_val - driver.start_val))
				
				if driver.target == "TEMP":
					temp += val_change
				elif driver.target == "MOISTURE":
					moisture += val_change
				
		# --- Fractal Noise / Jitter Section ---
		# (Keep your existing jitter logic here...)
		offset_X = (iX + 50) % int(self.iW)
		offset_Y = (iY + 50) % int(self.iH)
		noise_t = (float(self.noise.getHeight(iX, iY)) / 255.0) - 0.5
		noise_m = (float(self.noise.getHeight(offset_X, offset_Y)) / 255.0) - 0.5
		
		noise_mult = 0.25 
			
		temp += (noise_t * noise_mult)
		moisture += (noise_m * noise_mult)
		
		# Final Clamp to 0.0 - 1.0
		if temp < 0.0: temp = 0.0
		if temp > 1.0: temp = 1.0
		if moisture < 0.0: moisture = 0.0
		if moisture > 1.0: moisture = 1.0
		
		return temp, moisture

class CustomClimateManager:
	"""
	Holds the Driver Stack. You can define multiple profiles here and select
	them based on map options or climate settings.
	"""
	def __init__(self, map_obj):
		self.map = map_obj
		self.drivers = []
		self.base_temp = 0.3
		self.base_moisture = 0.3
		
		# Load the profile
		self.setup_profile()

	def setup_profile(self):
		"""
		Set climate drivers here.
		Note: In Civ4, Y=0.0 is the South (bottom), Y=1.0 is the North (top).
		"""
		gc = CyGlobalContext()
		m = CyMap()
		iClimateIndex = m.getClimate()
		climate_info = gc.getClimateInfo(iClimateIndex)
		climate_type = climate_info.getType() # e.g., "CLIMATE_TROPICAL"

		# Initialize Base Values (Temperate Defaults)
		self.base_temp = 0.0
		self.base_moisture = 0.0
		
		# Apply Climate selection modifiers
		if climate_type == "CLIMATE_TROPICAL":
			self.base_temp = 0.5
			self.base_moisture = 0.5
			
		elif climate_type == "CLIMATE_COLD":
			self.base_temp = -0.2
			self.base_moisture = -0.2
			
		elif climate_type == "CLIMATE_ARID":
			self.base_temp = 0.3
			self.base_moisture = -0.4
			

		# 1. TEMPERATURE / MOISTURE DRIVERS
		if m.getCustomMapOption(3) == 0: # Moist Center and Rim
			self.drivers.append(ClimateDriver("TEMP", "LINEAR", (0.5, 0.45), 1.2, -0.2, 0.52, 90.0))
			self.drivers.append(ClimateDriver("TEMP", "LINEAR", (0.5, 0.55), 1.2, -0.2, 0.52, -90.0))
			self.drivers.append(ClimateDriver("MOISTURE", "RADIAL", (0.5, 0.5), 1.6, -0.3, 0.3))
			self.drivers.append(ClimateDriver("MOISTURE", "RADIAL", (0.5, 0.5), -0.2, 1.4, 0.7))
		elif m.getCustomMapOption(3) == 1: # Dry Center
			self.drivers.append(ClimateDriver("TEMP", "LINEAR", (0.5, 0.45), 1.2, -0.2, 0.52, 90.0))
			self.drivers.append(ClimateDriver("TEMP", "LINEAR", (0.5, 0.55), 1.2, -0.2, 0.52, -90.0))
			self.drivers.append(ClimateDriver("MOISTURE", "RADIAL", (0.5, 0.5), -0.3, 1.75, 0.55))

# -----------------------------------------------------------------------------
# Terrain & Feature Generation (Downstream of Climate Gen)
# -----------------------------------------------------------------------------
TEMP_THRESHOLDS = [0.10, 0.20, 0.75]
MOISTURE_THRESHOLDS = [0.20, 0.45, 0.70]

# Rows = Temperature (0:Arctic, 1:Cold, 2:Temperate, 3:Tropical)
# Cols = Moisture (0:Arid, 1:Dry, 2:Humid, 3:Wet)
BIOME_TABLE = [
	["Snow", "Snow", "Snow", "Tundra"],
	["Snow", "Tundra", "Tundra", [("Tundra", 80), ("Grassland", 20)]],
	["Desert", [("Desert", 40), ("Plains", 60)], [("Plains", 30), ("Grassland", 70)], "Grassland"],
	["Desert", [("Desert", 40), ("Plains", 60)], [("Plains", 30), ("Grassland", 70)], "Grassland"]
]

FEATURE_TABLE = [
	[None, None, None, "Snow"],
	[None, None, "Snow", [("Snow", 60), ("Pine", 40)]],
	[None, None, [("Deciduous", 30), ("Pine", 70)], [("Deciduous", 70), ("Pine", 30)]],
	[None, "Deciduous", [("Deciduous", 70), ("Jungle", 30)], [("Deciduous", 20), ("Jungle", 80)]]
]

def _get_climate_band(value, thresholds):
	i = 0
	while i < len(thresholds):
		if value < thresholds[i]:
			return i
		i += 1
	return len(thresholds)

def _resolve_table_entry(entry, mapRand, log_label):
	if entry is None:
		return None

	if isinstance(entry, list):
		if len(entry) == 0:
			return None

		first = entry[0]
		if isinstance(first, tuple):
			total = 0
			for item, weight in entry:
				total += weight

			if total <= 0:
				return None

			roll = mapRand.get(total, log_label)
			running = 0
			for item, weight in entry:
				running += weight
				if roll < running:
					return item
			return entry[len(entry) - 1][0]

		roll = mapRand.get(len(entry), log_label)
		return entry[roll]

	return entry

class TerrainGenerator(CvMapGeneratorUtil.TerrainGenerator):
	def __init__(self, fGrassMoistureThreshold=0.5, fDesertMoistureThreshold=0.2):
		# We call the parent but we will use our own logic in generateTerrainAtPlot
		CvMapGeneratorUtil.TerrainGenerator.__init__(self)
		self.fGrassThreshold = fGrassMoistureThreshold
		self.fDesertThreshold = fDesertMoistureThreshold
		self.terrainMap = {
			"Snow": self.gc.getInfoTypeForString("TERRAIN_SNOW"),
			"Tundra": self.gc.getInfoTypeForString("TERRAIN_TUNDRA"),
			"Plains": self.gc.getInfoTypeForString("TERRAIN_PLAINS"),
			"Desert": self.gc.getInfoTypeForString("TERRAIN_DESERT"),
			"Grassland": self.gc.getInfoTypeForString("TERRAIN_GRASS")
		}

	def generateTerrainAtPlot(self, iX, iY):
		pPlot = self.map.plot(iX, iY)
		
		# 1. Handle Water (Early Exit)
		if pPlot.isWater():
			return pPlot.getTerrainType()

		# 2. Fetch climate
		engine = get_climate_engine()
		temp, moisture = engine.get_climate_at(iX, iY)

		temp_band = _get_climate_band(temp, TEMP_THRESHOLDS)
		moisture_band = _get_climate_band(moisture, MOISTURE_THRESHOLDS)
		terrain_name = _resolve_table_entry(BIOME_TABLE[temp_band][moisture_band], self.mapRand, "Terrain Table")

		if self.terrainMap.has_key(terrain_name):
			return self.terrainMap[terrain_name]
		return pPlot.getTerrainType()

def generateTerrainTypes():
	NiTextOut("Generating Terrain (Python Central Plains) ...")
	if CyMap().getCustomMapOption(3) == 2:
		return CvMapGeneratorUtil.TerrainGenerator().generateTerrain()
	
	# We no longer need iDesertPercent or iPlainsPercent because we
	# define the climate via the piecewise moisture gradient.
	# We only pass the thresholds for the terrain bands.
	
	terraingen = TerrainGenerator(
		fGrassMoistureThreshold = 0.5, 
		fDesertMoistureThreshold = 0.2
	)
	
	terrainTypes = terraingen.generateTerrain()
	return terrainTypes

class FeatureGenerator(CvMapGeneratorUtil.FeatureGenerator):
	def __init__(self, iJunglePercent=60, iForestPercent=40):
		CvMapGeneratorUtil.FeatureGenerator.__init__(self, iJunglePercent, iForestPercent)
		
		self.gc = CyGlobalContext()
		self.terrainDesert = self.gc.getInfoTypeForString("TERRAIN_DESERT")
		self.terrainPlains = self.gc.getInfoTypeForString("TERRAIN_PLAINS")
		self.terrainGrass = self.gc.getInfoTypeForString("TERRAIN_GRASS")
		self.featureFloodPlains = self.gc.getInfoTypeForString("FEATURE_FLOOD_PLAINS")
		
		# Initialize fractal for moisture noise
		self.moisture_noise = CyFractal()
		self.moisture_noise.fracInit(self.iGridW, self.iGridH, 3, self.mapRand, 0, -1, -1)

	def addIceAtPlot(self, pPlot, iX, iY, lat):
		# Do nothing - prevents ice placement
		pass

	def addClimateFeature(self, pPlot, feature_name):
		if feature_name is None:
			return False

		if feature_name == "Jungle":
			if self.mapRand.get(100, "J") < self.iJunglePercent:
				if pPlot.canHaveFeature(self.featureJungle):
					pPlot.setFeatureType(self.featureJungle, -1)
					return True
			return False

		iVariety = -1
		if feature_name == "Deciduous":
			iVariety = 0
		elif feature_name == "Pine":
			iVariety = 1
		elif feature_name == "Snow":
			iVariety = 2
		else:
			return False

		if self.mapRand.get(100, "F") < self.iForestPercent:
			if pPlot.canHaveFeature(self.featureForest):
				pPlot.setFeatureType(self.featureForest, iVariety)
				return True

		return False

	def addFeaturesAtPlot(self, iX, iY):
		pPlot = self.map.sPlot(iX, iY)
		if pPlot.isWater() or pPlot.getFeatureType() != -1: return

		engine = get_climate_engine()
		temp, moisture = engine.get_climate_at(iX, iY)

		temp_band = _get_climate_band(temp, TEMP_THRESHOLDS)
		moisture_band = _get_climate_band(moisture, MOISTURE_THRESHOLDS)
		feature_name = _resolve_table_entry(FEATURE_TABLE[temp_band][moisture_band], self.mapRand, "Feature Table")

		if self.addClimateFeature(pPlot, feature_name):
			return

		# 3. Desert Features
		if pPlot.getTerrainType() == self.terrainDesert:
			if pPlot.isRiver():
				# Floodplains only go on Desert tiles with no other features
				if pPlot.getFeatureType() == -1:
					if pPlot.canHaveFeature(self.featureFloodPlains):
						pPlot.setFeatureType(self.featureFloodPlains, -1)
			if self.mapRand.get(100, "O") < 5:
				if pPlot.canHaveFeature(self.featureOasis):
					pPlot.setFeatureType(self.featureOasis, -1)

def addFeatures():
	NiTextOut("Adding Features (Python Central Plains) ...")
	if CyMap().getCustomMapOption(3) == 2:
		CvMapGeneratorUtil.FeatureGenerator().addFeatures()
	else:
		featuregen = FeatureGenerator()
		featuregen.addFeatures()
	# expandCoastToTwoTiles()
	if _MASK_GENERATION_FAILED:
		CyEngine().addSign(CyMap().plot(0, 0), -1,
		                   "DEBUG: Symmetrigaea mask retries exhausted")
	
	# Debug for fractal regions
	global _DEBUG_REGIONS
	# if _DEBUG_REGIONS:
		# _add_region_signs(_DEBUG_REGIONS)
	
	return 0

# -----------------------------------------------------------------------------
# Coast distance
# -----------------------------------------------------------------------------
def expandCoastToTwoTiles():
	"""Convert all water tiles within a BFC (Big Fat Cross) radius of land to coast."""
	map = CyMap()
	gc = CyGlobalContext()
	iW = map.getGridWidth()
	iH = map.getGridHeight()
	coast_id = gc.getInfoTypeForString("TERRAIN_COAST")

	# Collect all land plots
	land_plots = []
	for x in range(iW):
		for y in range(iH):
			if not map.plot(x, y).isWater():
				land_plots.append((x, y))

	# Mark water plots within BFC range
	coast_plots = set()
	for lx, ly in land_plots:
		for dx in range(-2, 3):
			for dy in range(-2, 3):
				# BFC Logic: Skip the four corner tiles of the 5x5 area
				# (where both dx and dy are 2 or -2)
				if abs(dx) == 2 and abs(dy) == 2:
					continue
				
				nx = lx + dx
				ny = ly + dy
				
				# Check bounds
				if 0 <= nx < iW and 0 <= ny < iH:
					pPlot = map.plot(nx, ny)
					if pPlot.isWater():
						coast_plots.add((nx, ny))

	# Apply coast terrain
	for x, y in coast_plots:
		map.plot(x, y).setTerrainType(coast_id, True, True)
		

# -----------------------------------------------------------------------------
# River Generator
# -----------------------------------------------------------------------------
class RiverGenerator:
	"""
	From Tectonics.py class riversFromSea.
	Added to generate more natural-looking rivers.
	Input exclude_rects to prevent river generation in certain regions (used for Sahara in this mapscript).
	"""
	def __init__(self, river_density=1.0, exclude_rects=None, reduce_rects=None, survival_chance=20):
		"""
		exclude_rects: list of (west, south, width, height) – rivers never start or flow here.
		reduce_rects: list of (west, south, width, height) – rivers have only `survival_chance`% chance to flow here.
		river_density: float > 0; 1.0 gives a moderate number of rivers (similar to old divider=2).
		"""
		self.gc = CyGlobalContext()
		self.dice = self.gc.getGame().getMapRand()
		self.map = CyMap()
		self.width = self.map.getGridWidth()
		self.height = self.map.getGridHeight()
		self.straightThreshold = 3
		if (self.width * self.height > 400):
			self.straightThreshold = 2
		self.survival_chance = survival_chance
		self.river_density = river_density
		(iW, iH, bWrapX, bWrapY, outerDistances, holeDistances,
		 outerWater, holeWater) = _get_river_distance_cache()
		self.outerDistances = outerDistances
		self.outerWater = outerWater
		self.holeDistances = holeDistances
		self.holeWater = holeWater
		if holeDistances is not None:
			self.riverDistances = holeDistances
			self.destinationWater = holeWater
		else:
			self.riverDistances = outerDistances
			self.destinationWater = outerWater

		# Convert exclude rectangles
		self.exclude_rects = []
		if exclude_rects:
			for (west, south, width, height) in exclude_rects:
				west_x = int(self.width * west)
				east_x = int(self.width * (west + width))
				south_y = int(self.height * south)
				north_y = int(self.height * (south + height))
				self.exclude_rects.append((west_x, east_x, south_y, north_y))

		# Convert reduce rectangles
		self.reduce_rects = []
		if reduce_rects:
			for (west, south, width, height) in reduce_rects:
				west_x = int(self.width * west)
				east_x = int(self.width * (west + width))
				south_y = int(self.height * south)
				north_y = int(self.height * (south + height))
				self.reduce_rects.append((west_x, east_x, south_y, north_y))

	def is_excluded(self, x, y):
		for (west_x, east_x, south_y, north_y) in self.exclude_rects:
			if west_x <= x <= east_x and south_y <= y <= north_y:
				return True
		return False

	def is_reduced(self, x, y):
		"""Return True if the plot lies in a reduce_rect; also roll for chance."""
		for (west_x, east_x, south_y, north_y) in self.reduce_rects:
			if west_x <= x <= east_x and south_y <= y <= north_y:
				# Roll the dice: return True if the roll is < survival_chance (i.e., allowed)
				return self.dice.get(100, "River reduction") < self.survival_chance
		return True   # not in any reduce_rect -> always allowed

	def is_destination_water(self, plot):
		if not plot.isWater():
			return False
		index = plot.getY() * self.width + plot.getX()
		return index in self.destinationWater

	def mouth_water_tiles(self, plot):
		"""Water tiles beside a possible river mouth on the destination shore."""
		x = plot.getX()
		y = plot.getY()
		result = []
		for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
			nx = x + dx
			ny = y + dy
			if nx < 0 or nx >= self.width or ny < 0 or ny >= self.height: continue
			if ny * self.width + nx in self.destinationWater:
				result.append((nx, ny))
		return result

	def collateCoasts(self):
		"""Return land plots adjacent to the active river destination."""
		result = []
		for x in range(self.width):
			for y in range(self.height):
				plot = self.map.plot(x, y)
				if plot.isCoastalLand() and self.mouth_water_tiles(plot):
					result.append(plot)
		return result

	def seedRivers(self):
		# Base number of rivers proportional to the map's perimeter (width+height)
		# For density 1.0, this gives about the same as the old divider=2.
		base = (self.width + self.height) / 2.0
		riversNumber = int(base * self.river_density) + 1
		destinations = []
		if self.holeDistances is not None:
			self.riverDistances = self.holeDistances
			self.destinationWater = self.holeWater
			destinations.append(("inland sea", self.holeDistances,
			                     self.holeWater, self.collateCoasts()))
		self.riverDistances = self.outerDistances
		self.destinationWater = self.outerWater
		outerName = "outer sea"
		if self.holeDistances is not None: outerName = "outer sea fallback"
		destinations.append((outerName, self.outerDistances,
		                     self.outerWater, self.collateCoasts()))
		coastsNumber = 0
		for name, distances, water, coastList in destinations:
			coastsNumber += len(coastList)
		riversNumber = min(riversNumber, coastsNumber)
		quotas = [riversNumber / 2, riversNumber / 2]
		firstSide = 0
		if riversNumber % 2:
			firstSide = self.dice.get(2, "GMF odd river side")
			quotas[firstSide] += 1
		print "PY: Symmetrigaea GMF river target %d; west quota %d, east quota %d" % (riversNumber, quotas[0], quotas[1])
		placed = [0, 0]
		mouths = []
		existingMouthTiles = set()
		for name, distances, water, coastList in destinations:
			self.destinationWater = water
			for coastPlot in coastList:
				if coastPlot.isRiver():
					existingMouthTiles.update(self.mouth_water_tiles(coastPlot))
		order = [firstSide, 1 - firstSide]
		for name, distances, water, coastList in destinations:
			if placed[0] >= quotas[0] and placed[1] >= quotas[1]: break
			self.riverDistances = distances
			self.destinationWater = water
			self.coasts = coastList
			coasts = [[], []]
			for plot in coastList:
				side = 0
				if plot.getX() >= self.width / 2: side = 1
				coasts[side].append(plot)
			for side in range(2):
				coasts[side] = _synced_shuffle(self.dice, coasts[side])
			positions = [0, 0]
			stagePlaced = [0, 0]
			for slot in range(max(quotas[0] - placed[0], quotas[1] - placed[1])):
				for side in order:
					if placed[side] >= quotas[side]: continue
					while positions[side] < len(coasts[side]):
						plot = coasts[side][positions[side]]
						positions[side] += 1
						x, y = plot.getX(), plot.getY()
						if self.is_excluded(x, y) or not self.is_reduced(x, y): continue
						tooClose = False
						for mouthX, mouthY in mouths:
							if max(abs(x - mouthX), abs(y - mouthY)) < 2:
								tooClose = True
								break
						if tooClose: continue
						candidateWater = self.mouth_water_tiles(plot)
						for waterX, waterY in candidateWater:
							for mouthX, mouthY in existingMouthTiles:
								if max(abs(waterX - mouthX), abs(waterY - mouthY)) < 2:
									tooClose = True
									break
							if tooClose: break
						if tooClose: continue
						(x, y, flow) = self.generateRiverFromPlot(plot, x, y)
						if flow == CardinalDirectionTypes.NO_CARDINALDIRECTION: continue
						riverID = self.map.getNextRiverID()
						self.map.incrementNextRiverID()
						self.addRiverFrom(x, y, flow, riverID)
						if plot.isNOfRiver() or plot.isWOfRiver():
							placed[side] += 1
							stagePlaced[side] += 1
							mouths.append((x, y))
							for coastPlot in self.coasts:
								if coastPlot.isRiver():
									existingMouthTiles.update(self.mouth_water_tiles(coastPlot))
							break
			print "PY: Symmetrigaea GMF %s placed west %d, east %d" % (name, stagePlaced[0], stagePlaced[1])
		print "PY: Symmetrigaea GMF rivers placed west %d, east %d" % (placed[0], placed[1])
		for side in range(2):
			if placed[side] < quotas[side]:
				print "PY: Symmetrigaea GMF rivers side %d placed %d of %d" % (side, placed[side], quotas[side])

	def canFlowFrom(self, plot, upperPlot):
		"""Return True if water can flow from `plot` to `upperPlot`."""
		if plot.isWater() or upperPlot.isWater():
			return False
		if plot.getPlotType() == PlotTypes.PLOT_PEAK:
			return False
		# If the upper plot is in an excluded rectangle, stop
		ux, uy = upperPlot.getX(), upperPlot.getY()
		if self.is_excluded(ux, uy):
			return False
		# If the upper plot is in a reduced rectangle, apply chance
		if not self.is_reduced(ux, uy):
			return False

		if plot.getPlotType() == PlotTypes.PLOT_HILLS:
			return True
		if plot.getPlotType() == PlotTypes.PLOT_LAND:
			return True
		return False

	def generateRiverFromPlot(self, plot, x, y):
		FlowDirection = CardinalDirectionTypes.NO_CARDINALDIRECTION
		if ((y < 1 or y >= self.height - 1) or plot.isNOfRiver() or plot.isWOfRiver()):
			return (x, y, FlowDirection)
		eastX = self.eastX(x)
		westX = self.westX(x)
		otherPlot = True
		eastPlot = self.map.plot(eastX, y)
		if eastPlot.isCoastalLand():
			# Check water at the active river destination
			if (self.is_destination_water(self.map.plot(x, y+1)) or
				self.is_destination_water(self.map.plot(eastX, y+1))):
				landPlot1 = self.map.plot(x, y-1)
				landPlot2 = self.map.plot(eastX, y-1)
				if landPlot1.isWater() or landPlot2.isWater():
					otherPlot = True
				else:
					FlowDirection = CardinalDirectionTypes.CARDINALDIRECTION_NORTH
					otherPlot = False
			if otherPlot:
				if (self.is_destination_water(self.map.plot(x, y-1)) or
					self.is_destination_water(self.map.plot(eastX, y-1))):
					landPlot1 = self.map.plot(x, y+1)
					landPlot2 = self.map.plot(eastX, y+1)
					if landPlot1.isWater() or landPlot2.isWater():
						otherPlot = True
					else:
						FlowDirection = CardinalDirectionTypes.CARDINALDIRECTION_SOUTH
						otherPlot = False
		if otherPlot:
			southPlot = self.map.plot(x, y-1)
			if southPlot.isCoastalLand():
				if (self.is_destination_water(self.map.plot(eastX, y)) or
					self.is_destination_water(self.map.plot(eastX, y-1))):
					landPlot1 = self.map.plot(westX, y)
					landPlot2 = self.map.plot(westX, y-1)
					if landPlot1.isWater() or landPlot2.isWater():
						otherPlot = True
					else:
						FlowDirection = CardinalDirectionTypes.CARDINALDIRECTION_EAST
						otherPlot = False
				if otherPlot:
					if (self.is_destination_water(self.map.plot(westX, y)) or
						self.is_destination_water(self.map.plot(westX, y-1))):
						landPlot1 = self.map.plot(eastX, y)
						landPlot2 = self.map.plot(eastX, y-1)
						if landPlot1.isWater() or landPlot2.isWater():
							otherPlot = True
						else:
							FlowDirection = CardinalDirectionTypes.CARDINALDIRECTION_WEST
		return (x, y, FlowDirection)

	def addRiverFrom(self, x, y, flow, riverID):
		plot = self.map.plot(x, y)
		if plot.isWater():
			return
		eastX = self.eastX(x)
		westX = self.westX(x)
		xShift = 0
		yShift = 0
		if flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST:
			xShift = 1
		elif flow == CardinalDirectionTypes.CARDINALDIRECTION_EAST:
			xShift = -1
		elif flow == CardinalDirectionTypes.CARDINALDIRECTION_NORTH:
			yShift = -1
		elif flow == CardinalDirectionTypes.CARDINALDIRECTION_SOUTH:
			yShift = 1
		nextX = x + xShift
		nextY = y + yShift
		if nextX < 0 or nextX >= self.width or nextY < 0 or nextY >= self.height:
			return
		currentDistance = self.riverDistances[y * self.width + x]
		nextDistance = self.riverDistances[nextY * self.width + nextX]
		if nextDistance <= currentDistance:
			return
		if self.preventRiversFromCrossing(x, y, flow, riverID):
			return
		plot.setRiverID(riverID)
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST) or (flow == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
			plot.setNOfRiver(True, flow)
		else:
			plot.setWOfRiver(True, flow)
		nextPlot = self.map.plot(nextX, nextY)
		if not self.canFlowFrom(plot, nextPlot):
			return
		if plot.getTerrainType() == CyGlobalContext().getInfoTypeForString("TERRAIN_SNOW") and self.dice.get(10, "Stop on ice") > 3:
			return
		flatDesert = (plot.getPlotType() == PlotTypes.PLOT_LAND) and (plot.getTerrainType() == CyGlobalContext().getInfoTypeForString("TERRAIN_DESERT"))
		turnThreshold = 16
		if flatDesert:
			turnThreshold = 18
		turned = False
		northY = y + 1
		southY = y - 1
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST) or (flow == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
			if (northY < self.height) and (self.dice.get(20, "branch from north") > turnThreshold):
				if (self.canFlowFrom(plot, self.map.plot(x, northY)) and
					self.canFlowFrom(self.map.plot(self.eastX(x), y), self.map.plot(self.eastX(x), northY))):
					turned = True
					if flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST:
						self.addRiverFrom(x, y, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH, riverID)
					else:
						westPlot = self.map.plot(westX, y)
						if not westPlot.isNOfRiver() and not westPlot.isWOfRiver():
							westPlot.setRiverID(riverID)
						self.addRiverFrom(westX, y, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH, riverID)
			if (not turned) and (southY >= 0) and (self.dice.get(20, "branch from south") > turnThreshold):
				if (self.canFlowFrom(plot, self.map.plot(x, southY)) and
					self.canFlowFrom(self.map.plot(self.eastX(x), y), self.map.plot(self.eastX(x), southY))):
					turned = True
					if flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST:
						southPlot = self.map.plot(x, y-1)
						if not southPlot.isNOfRiver() and not southPlot.isWOfRiver():
							southPlot.setRiverID(riverID)
						self.addRiverFrom(x, southY, CardinalDirectionTypes.CARDINALDIRECTION_NORTH, riverID)
					else:
						westPlot = self.map.plot(westX, southY)
						if not westPlot.isNOfRiver() and not westPlot.isWOfRiver():
							westPlot.setRiverID(riverID)
						self.addRiverFrom(westX, southY, CardinalDirectionTypes.CARDINALDIRECTION_NORTH, riverID)
		else:
			if (self.canFlowFrom(plot, self.map.plot(eastX, y)) and
				self.canFlowFrom(self.map.plot(x, southY), self.map.plot(eastX, y)) and
				(self.dice.get(20, "branch from east") > turnThreshold)):
				turned = True
				if flow == CardinalDirectionTypes.CARDINALDIRECTION_NORTH:
					eastPlot = self.map.plot(eastX, y)
					if not eastPlot.isNOfRiver() and not eastPlot.isWOfRiver():
						eastPlot.setRiverID(riverID)
					self.addRiverFrom(eastX, y, CardinalDirectionTypes.CARDINALDIRECTION_WEST, riverID)
				else:
					northEastPlot = self.map.plot(eastX, y+1)
					if not northEastPlot.isNOfRiver() and not northEastPlot.isWOfRiver():
						northEastPlot.setRiverID(riverID)
					self.addRiverFrom(eastX, y+1, CardinalDirectionTypes.CARDINALDIRECTION_WEST, riverID)
			if (not turned) and (self.canFlowFrom(plot, self.map.plot(westX, y)) and
				self.canFlowFrom(self.map.plot(x, southY), self.map.plot(westX, southY)) and
				(self.dice.get(20, "branch from west") > turnThreshold)):
				turned = True
				if flow == CardinalDirectionTypes.CARDINALDIRECTION_NORTH:
					self.addRiverFrom(x, y, CardinalDirectionTypes.CARDINALDIRECTION_EAST, riverID)
				else:
					northPlot = self.map.plot(x, y+1)
					if not northPlot.isNOfRiver() and not northPlot.isWOfRiver():
						northPlot.setRiverID(riverID)
					self.addRiverFrom(x, y+1, CardinalDirectionTypes.CARDINALDIRECTION_EAST, riverID)
		spawnInDesert = (not turned) and flatDesert
		if (self.dice.get(10, "straight river") > self.straightThreshold) or spawnInDesert:
			self.addRiverFrom(nextX, nextY, flow, riverID)
		else:
			if not turned:
				plot = self.map.plot(nextX, nextY)
				if (plot.getPlotType() == PlotTypes.PLOT_LAND and
				    not plot.isStartingPlot() and plot.getBonusType(-1) == -1 and
				    plot.getFeatureType() == -1 and
				    self.dice.get(10, "Rivers start in hills") > 3):
					plot.setPlotType(PlotTypes.PLOT_HILLS, True, True)
					if (flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST) or (flow == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
						if southY > 0:
							otherPlot = self.map.plot(nextX, southY)
							if (otherPlot.getPlotType() == PlotTypes.PLOT_LAND and
							    not otherPlot.isStartingPlot() and otherPlot.getBonusType(-1) == -1 and
							    otherPlot.getFeatureType() == -1):
								otherPlot.setPlotType(PlotTypes.PLOT_HILLS, True, True)
					else:
						otherPlot = self.map.plot(eastX, nextY)
						if (otherPlot.getPlotType() == PlotTypes.PLOT_LAND and
						    not otherPlot.isStartingPlot() and otherPlot.getBonusType(-1) == -1 and
						    otherPlot.getFeatureType() == -1):
							otherPlot.setPlotType(PlotTypes.PLOT_HILLS, True, True)

	def preventRiversFromCrossing(self, x, y, flow, riverID):
		plot = self.map.plot(x, y)
		eastX = self.eastX(x)
		westX = self.westX(x)
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_WEST):
			if (plot.isNOfRiver()):
				return True
			if (self.map.plot(eastX, y).isNOfRiver()):
				return True
			southPlot = self.map.plot(x, y-1)
			if (southPlot.isWOfRiver() and southPlot.getRiverNSDirection() == CardinalDirectionTypes.CARDINALDIRECTION_SOUTH):
				return True
			if (plot.isWOfRiver() and plot.getRiverNSDirection() == CardinalDirectionTypes.CARDINALDIRECTION_NORTH):
				return True
			if (self.map.plot(eastX, y).isWater()):
				return True
			if (self.map.plot(x, y-1).isWater()):
				return True
			if (self.map.plot(eastX, y-1).isWater()):
				return True
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
			if (plot.isNOfRiver()):
				return True
			if (self.map.plot(westX, y).isNOfRiver()):
				return True
			southPlot = self.map.plot(westX, y-1)
			if (southPlot.isWOfRiver() and southPlot.getRiverNSDirection() == CardinalDirectionTypes.CARDINALDIRECTION_SOUTH):
				return True
			westPlot = self.map.plot(westX, y)
			if (westPlot.isWOfRiver() and westPlot.getRiverNSDirection() == CardinalDirectionTypes.CARDINALDIRECTION_NORTH):
				return True
			if (self.map.plot(westX, y).isWater()):
				return True
			if (self.map.plot(x, y-1).isWater()):
				return True
			if (self.map.plot(westX, y-1).isWater()):
				return True
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_NORTH):
			if (plot.isWOfRiver()):
				return True
			eastPlot = self.map.plot(eastX, y)
			if (eastPlot.isNOfRiver() and eastPlot.getRiverWEDirection() == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
				return True
			if (plot.isNOfRiver() and plot.getRiverWEDirection() == CardinalDirectionTypes.CARDINALDIRECTION_WEST):
				return True
			if (self.map.plot(x, y-1).isWOfRiver()):
				return True
			if (self.map.plot(x, y-1).isWater()):
				return True
			if (self.map.plot(x+1, y).isWater()):
				return True
			if (self.map.plot(x+1, y-1).isWater()):
				return True
		if (flow == CardinalDirectionTypes.CARDINALDIRECTION_SOUTH):
			if (plot.isWOfRiver()):
				return True
			eastPlot = self.map.plot(eastX, y+1)
			if (eastPlot.isNOfRiver() and eastPlot.getRiverWEDirection() == CardinalDirectionTypes.CARDINALDIRECTION_EAST):
				return True
			northPlot = self.map.plot(x, y+1)
			if (northPlot.isNOfRiver() and northPlot.getRiverWEDirection() == CardinalDirectionTypes.CARDINALDIRECTION_WEST):
				return True
			if (self.map.plot(x, y+1).isWOfRiver()):
				return True
			if (self.map.plot(x, y+1).isWater()):
				return True
			if (self.map.plot(x+1, y).isWater()):
				return True
			if (self.map.plot(x+1, y+1).isWater()):
				return True
		return False

	def westX(self, x):
		westX = x - 1
		if (westX < 0):
			westX = self.width
		return westX

	def eastX(self, x):
		eastX = x + 1
		if (eastX >= self.width):
			eastX = 0
		return eastX
		

# -----------------------------------------------------------------------------
# Custom River Generator
# -----------------------------------------------------------------------------
"""Custom generator for drawing rivers / waterways running through specified coordinates."""
class PathNavigator:
	def __init__(self, map, dice):
		self.map = map
		self.dice = dice
		self.iW = map.getGridWidth()
		self.iH = map.getGridHeight()
		self.noise = CyFractal()
		self.noise.fracInit(self.iW, self.iH, 2, self.dice, 0, -1, -1)
		self.size_factor = float(self.iW + self.iH) / 64.0

	def is_ocean(self, x, y):
		if x < 0 or x >= self.iW or y < 0 or y >= self.iH: return False
		pPlot = self.map.plot(x, y)
		if pPlot.isWater():
			pArea = pPlot.area()
			if pArea:
				if pArea.getNumTiles() >= 10: return True
		return False

	def is_any_water(self, x, y):
		if x < 0 or x >= self.iW or y < 0 or y >= self.iH: return False
		return self.map.plot(x, y).isWater()

	def get_best_move(self, cx, cy, tx, ty, visited, is_water_path, meander):
		best_score = 999999.0
		best_move = None
		dist_to_target = math.sqrt((cx - tx)**2 + (cy - ty)**2)

		if is_water_path:
			moves = [(1,0), (-1,0), (0,1), (0,-1)]
		else:
			moves = [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)]
			
		for move in moves:
			nx, ny = cx + move[0], cy + move[1]
			if nx < 0 or nx >= self.iW or ny < 0 or ny >= self.iH: continue
			
			bVisited = False
			for v in visited:
				if nx == v[0] and ny == v[1]:
					bVisited = True
					break
			if bVisited: continue
			
			if is_water_path:
				bSkip2x2 = False
				if dist_to_target < 4:
					bSkip2x2 = True
				else:
					for adj in [(1,0), (-1,0), (0,1), (0,-1)]:
						if self.is_ocean(nx + adj[0], ny + adj[1]):
							bSkip2x2 = True
							break
				
				if not bSkip2x2:
					if self.is_any_water(nx-1, ny) and self.is_any_water(nx, ny-1) and self.is_any_water(nx-1, ny-1): continue
					if self.is_any_water(nx+1, ny) and self.is_any_water(nx, ny-1) and self.is_any_water(nx+1, ny-1): continue
					if self.is_any_water(nx-1, ny) and self.is_any_water(nx, ny+1) and self.is_any_water(nx-1, ny+1): continue
					if self.is_any_water(nx+1, ny) and self.is_any_water(nx, ny+1) and self.is_any_water(nx+1, ny+1): continue

			dist = math.sqrt((nx - tx)**2 + (ny - ty)**2)
			n_val = (self.noise.getHeight(nx, ny) / 100.0) - 0.5
			score = dist * (1.0 + (n_val * meander))
			
			if score < best_score:
				best_score = score
				best_move = (nx, ny, move[0], move[1])
		return best_move

	def generate_path(self, start, end, meander, is_water_path):
		curr_x, curr_y = start
		path = [(curr_x, curr_y)]
		visited = [(curr_x, curr_y)]
		
		max_steps = (abs(curr_x - end[0]) + abs(curr_y - end[1])) * 4
		for i in range(max_steps):
			if curr_x == end[0] and curr_y == end[1]: break
			move = self.get_best_move(curr_x, curr_y, end[0], end[1], visited, is_water_path, meander)
			if not move: break
			curr_x, curr_y = move[0], move[1]
			path.append((curr_x, curr_y))
			visited.append((curr_x, curr_y))
			
			if is_water_path:
				if self.is_ocean(curr_x, curr_y):
					break
			else:
				# Standard River: Stop if we hit ANY water
				# We skip i=0 to allow rivers to start adjacent to water
				if i > 0:
					if self.is_any_water(curr_x, curr_y):
						break
		return path
	
class WaterwayMaker:
	def __init__(self, navigator):
		self.nav = navigator
		self.map = navigator.map

	def build(self, checkpoints, meander, bridge_spacing, bBridgesEnabled=True):
		full_path = []
		for i in range(len(checkpoints) - 1):
			start = (int(self.nav.iW * checkpoints[i][0]), int(self.nav.iH * checkpoints[i][1]))
			end = (int(self.nav.iW * checkpoints[i+1][0]), int(self.nav.iH * checkpoints[i+1][1]))
			segment = self.nav.generate_path(start, end, meander, True)
			if i == 0:
				full_path.extend(segment)
			else:
				full_path.extend(segment[1:])
			if segment:
				if self.nav.is_ocean(segment[-1][0], segment[-1][1]):
					break
		
		self._apply_to_map(full_path, bridge_spacing, bBridgesEnabled)

	def _apply_to_map(self, path, bridge_spacing, bBridgesEnabled):
		if not path: return
		riverID = self.map.getNextRiverID()
		self.map.incrementNextRiverID()
		step_count = 0
		next_gap = int((self.nav.dice.get(3, "G") + bridge_spacing) * self.nav.size_factor)
		if next_gap < 2: next_gap = 2

		for i in range(len(path)):
			x, y = path[i]
			pPlot = self.map.plot(x, y)
			
			# Force Ocean on last tile or existing ocean
			if i == len(path) - 1 or self.nav.is_ocean(x, y):
				pPlot.setPlotType(PlotTypes.PLOT_OCEAN, True, True)
				step_count = 0
				continue

			bIsBridge = False
			# Only evaluate bridge logic if bBridgesEnabled is True
			if bBridgesEnabled:
				if step_count >= next_gap:
					bNearOcean = False
					for adj in [(1,0), (-1,0), (0,1), (0,-1)]:
						if self.nav.is_ocean(x+adj[0], y+adj[1]):
							bNearOcean = True
							break
					if not bNearOcean:
						bIsBridge = True

			if bIsBridge:
				pPlot.setPlotType(PlotTypes.PLOT_LAND, True, True)
				pPlot.setFeatureType(FeatureTypes.NO_FEATURE, -1)
				
				# Flatten 8-way adjacent peaks
				for adj_x in range(-1, 2):
					for adj_y in range(-1, 2):
						if adj_x == 0 and adj_y == 0: continue
						nx, ny = x + adj_x, y + adj_y
						if nx >= 0 and nx < self.nav.iW and ny >= 0 and ny < self.nav.iH:
							pAdj = self.map.plot(nx, ny)
							if pAdj.getPlotType() == PlotTypes.PLOT_PEAK:
								pAdj.setPlotType(PlotTypes.PLOT_HILLS, True, True)
				
				dx, dy, ndx, ndy = 0, 0, 0, 0
				if i > 0: dx, dy = x - path[i-1][0], y - path[i-1][1]
				if i < len(path)-1: ndx, ndy = path[i+1][0] - x, path[i+1][1] - y
				self._apply_bridge_flags(x, y, dx, dy, ndx, ndy, riverID)
				step_count = 0
				next_gap = int((self.nav.dice.get(3, "G") + bridge_spacing) * self.nav.size_factor)
				if next_gap < 2: next_gap = 2
			else:
				pPlot.setPlotType(PlotTypes.PLOT_OCEAN, True, True)
				step_count += 1

	def _apply_bridge_flags(self, x, y, dx, dy, ndx, ndy, rID):
		N, S, E, W = CardinalDirectionTypes.CARDINALDIRECTION_NORTH, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH, CardinalDirectionTypes.CARDINALDIRECTION_EAST, CardinalDirectionTypes.CARDINALDIRECTION_WEST
		corner = "STRAIGHT"
		if dy==1 and ndx==1: corner="S_E"
		elif dy==1 and ndx==-1: corner="S_W"
		elif dy==-1 and ndx==1: corner="N_E"
		elif dy==-1 and ndx==-1: corner="N_W"
		elif dx==-1 and ndy==-1: corner="E_S"
		elif dx==1 and ndy==-1: corner="W_S"
		elif dx==-1 and ndy==1: corner="E_N"
		elif dx==1 and ndy==1: corner="W_N"

		if corner == "STRAIGHT":
			p = self.map.plot(x, y)
			if dx != 0:
				flow = E
				if dx != 1: flow = W
				p.setNOfRiver(True, flow)
			elif dy != 0:
				flow = N
				if dy != 1: flow = S
				p.setWOfRiver(True, flow)
			p.setRiverID(rID)
		elif corner == "S_E":
			p=self.map.plot(x-1, y); p.setWOfRiver(True, N); p.setRiverID(rID)
			p=self.map.plot(x, y+1); p.setNOfRiver(True, E); p.setRiverID(rID)
		elif corner == "S_W":
			p=self.map.plot(x, y); p.setWOfRiver(True, N); p.setRiverID(rID)
			p=self.map.plot(x, y+1); p.setNOfRiver(True, W); p.setRiverID(rID)
		elif corner == "N_E":
			p=self.map.plot(x-1, y); p.setWOfRiver(True, S); p.setRiverID(rID)
			p=self.map.plot(x, y); p.setNOfRiver(True, E); p.setRiverID(rID)
		elif corner == "N_W":
			p=self.map.plot(x, y); p.setWOfRiver(True, S); p.setNOfRiver(True, W); p.setRiverID(rID)
		elif corner == "E_S":
			p=self.map.plot(x-1, y); p.setWOfRiver(True, S); p.setRiverID(rID)
			p=self.map.plot(x, y+1); p.setNOfRiver(True, W); p.setRiverID(rID)
		elif corner == "W_S":
			# --- INCORPORATED YOUR FIX ---
			p=self.map.plot(x, y); p.setWOfRiver(True, S); p.setRiverID(rID)
			p=self.map.plot(x, y+1); p.setNOfRiver(True, E); p.setRiverID(rID)
		elif corner == "E_N":
			p=self.map.plot(x-1, y); p.setWOfRiver(True, N); p.setRiverID(rID)
			p=self.map.plot(x, y); p.setNOfRiver(True, W); p.setRiverID(rID)
		elif corner == "W_N":
			p=self.map.plot(x, y); p.setWOfRiver(True, N); p.setNOfRiver(True, E); p.setRiverID(rID)

class StandardRiverMaker:
	def __init__(self, navigator):
		self.nav = navigator
		self.map = navigator.map

	def build(self, checkpoints, meander):
		riverID = self.map.getNextRiverID()
		self.map.incrementNextRiverID()
		for i in range(len(checkpoints) - 1):
			start = (int(self.nav.iW * checkpoints[i][0]), int(self.nav.iH * checkpoints[i][1]))
			end = (int(self.nav.iW * checkpoints[i+1][0]), int(self.nav.iH * checkpoints[i+1][1]))
			path = self.nav.generate_path(start, end, meander, False)
			if not path: break
			
			for j in range(len(path)-1):
				curr, next = path[j], path[j+1]
				dx, dy = next[0]-curr[0], next[1]-curr[1]
				bStop = self._apply_river_flags(curr[0], curr[1], dx, dy, riverID)
				if bStop: return

	def _apply_river_flags(self, x, y, dx, dy, rID):
		N, S, E, W = CardinalDirectionTypes.CARDINALDIRECTION_NORTH, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH, CardinalDirectionTypes.CARDINALDIRECTION_EAST, CardinalDirectionTypes.CARDINALDIRECTION_WEST
		bStop = False
		
		# Horizontal
		if dx != 0:
			if dx == 1:
				tx = x
				flow = E
				look_x = tx + 1
			else:
				tx = x - 1
				flow = W
				look_x = tx - 1
			
			# Stop at ANY water (Lake or Coast)
			if self.nav.is_any_water(look_x, y) or self.nav.is_any_water(look_x, y-1):
				bStop = True
			
			p = self.map.plot(tx, y)
			if p:
				if not self.nav.is_any_water(tx, y):
					if not self.nav.is_any_water(tx, y-1):
						if self._check_merge(tx, y, False, flow): 
							bStop = True
						p.setNOfRiver(True, flow)
						p.setRiverID(rID)
			if bStop: return True

		# Vertical
		if dy != 0:
			tx = x + dx - 1
			if dy == 1:
				ty = y
				flow = N
				look_y = ty + 1
			else:
				ty = y - 1
				flow = S
				look_y = ty - 1
			
			# Stop at ANY water (Lake or Coast)
			if self.nav.is_any_water(tx, look_y) or self.nav.is_any_water(tx+1, look_y):
				bStop = True
				
			p = self.map.plot(tx, ty)
			if p:
				if not self.nav.is_any_water(tx, ty):
					if not self.nav.is_any_water(tx+1, ty):
						if self._check_merge(tx, ty, True, flow): 
							bStop = True
						p.setWOfRiver(True, flow)
						p.setRiverID(rID)
		return bStop

	def _check_merge(self, x, y, is_vertical, flow):
		N, S, E, W = CardinalDirectionTypes.CARDINALDIRECTION_NORTH, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH, CardinalDirectionTypes.CARDINALDIRECTION_EAST, CardinalDirectionTypes.CARDINALDIRECTION_WEST
		if is_vertical:
			if flow == N:
				p=self.map.plot(x, y+1)
				if p and ((p.isWOfRiver() and p.getRiverNSDirection()==N) or (p.isNOfRiver() and p.getRiverWEDirection()==W)): return True
				p=self.map.plot(x+1, y+1)
				if p and (p.isNOfRiver() and p.getRiverWEDirection()==E): return True
			else:
				p=self.map.plot(x, y)
				if p and (p.isNOfRiver() and p.getRiverWEDirection()==W): return True
				p=self.map.plot(x, y-1)
				if p and (p.isWOfRiver() and p.getRiverNSDirection()==S): return True
				p=self.map.plot(x+1, y)
				if p and (p.isNOfRiver() and p.getRiverWEDirection()==E): return True
		else:
			if flow == E:
				p=self.map.plot(x, y)
				if p and (p.isWOfRiver() and p.getRiverNSDirection()==N): return True
				p=self.map.plot(x, y-1)
				if p and (p.isWOfRiver() and p.getRiverNSDirection()==S): return True
				p=self.map.plot(x+1, y)
				if p and (p.isNOfRiver() and p.getRiverWEDirection()==E): return True
			else: # W
				p=self.map.plot(x-1, y)
				if p and ((p.isNOfRiver() and p.getRiverWEDirection()==W) or (p.isWOfRiver() and p.getRiverNSDirection()==N)): return True
				p=self.map.plot(x-1, y-1)
				if p and (p.isWOfRiver() and p.getRiverNSDirection()==S): return True
		return False

def addRivers():
	"""Generate GMF rivers without Civ IV's default main river pass."""
	CyMap().recalculateAreas()
	_get_river_distance_cache()
	RiverGenerator(river_density=0.6).seedRivers()
	return None

_INLAND_SEA_TILES = set()
_RIVER_DISTANCE_CACHE = None

def _river_neighbors(index, iW, iH, bWrapX, bWrapY):
	x = index % iW
	y = index // iW
	result = []
	steps = [(0, 1, CardinalDirectionTypes.CARDINALDIRECTION_NORTH),
	         (1, 0, CardinalDirectionTypes.CARDINALDIRECTION_EAST),
	         (0, -1, CardinalDirectionTypes.CARDINALDIRECTION_SOUTH),
	         (-1, 0, CardinalDirectionTypes.CARDINALDIRECTION_WEST)]
	for dx, dy, direction in steps:
		nx = x + dx
		ny = y + dy
		if nx < 0 or nx >= iW:
			if not bWrapX: continue
			nx = nx % iW
		if ny < 0 or ny >= iH:
			if not bWrapY: continue
			ny = ny % iH
		result.append((ny * iW + nx, direction))
	return result

def _river_distances_from(seeds, iW, iH, bWrapX, bWrapY):
	distances = [-1] * (iW * iH)
	queue = []
	for index in sorted(seeds):
		distances[index] = 0
		queue.append(index)
	position = 0
	while position < len(queue):
		index = queue[position]
		position += 1
		for other, direction in _river_neighbors(index, iW, iH, bWrapX, bWrapY):
			if distances[other] != -1: continue
			distances[other] = distances[index] + 1
			queue.append(other)
	return distances

def _get_river_distance_cache():
	global _RIVER_DISTANCE_CACHE
	if _RIVER_DISTANCE_CACHE is not None:
		return _RIVER_DISTANCE_CACHE
	map = CyMap()
	iW = map.getGridWidth()
	iH = map.getGridHeight()
	bWrapX = map.isWrapX()
	bWrapY = map.isWrapY()
	water = set()
	outerSeeds = set()
	for index in range(iW * iH):
		if not map.plotByIndex(index).isWater(): continue
		water.add(index)
		x = index % iW
		y = index // iW
		if x == 0 or x == iW - 1 or y == 0 or y == iH - 1:
			outerSeeds.add(index)
	outerWater = set(outerSeeds)
	queue = sorted(outerSeeds)
	position = 0
	while position < len(queue):
		index = queue[position]
		position += 1
		for other, direction in _river_neighbors(index, iW, iH, bWrapX, bWrapY):
			if other in water and other not in outerWater:
				outerWater.add(other)
				queue.append(other)
	holeWater = set()
	if map.getCustomMapOption(2) == 0:
		holeWater = _INLAND_SEA_TILES.intersection(water)
		if not holeWater:
			print "PY: Symmetrigaea inland sea tiles missing; rivers use outer sea"
	outerDistances = _river_distances_from(outerWater, iW, iH, bWrapX, bWrapY)
	holeDistances = None
	if holeWater:
		holeDistances = _river_distances_from(holeWater, iW, iH, bWrapX, bWrapY)
	_RIVER_DISTANCE_CACHE = (iW, iH, bWrapX, bWrapY,
	                         outerDistances, holeDistances, outerWater, holeWater)
	return _RIVER_DISTANCE_CACHE

def _river_distance_at(index, outerDistances, holeDistances):
	if holeDistances is not None:
		return holeDistances[index]
	return outerDistances[index]

def getRiverAltitude(argsList):
	pPlot = argsList[0]
	(iW, iH, bWrapX, bWrapY, outerDistances, holeDistances,
	 outerWater, holeWater) = _get_river_distance_cache()
	index = pPlot.getY() * iW + pPlot.getX()
	distance = _river_distance_at(index, outerDistances, holeDistances)
	if distance < 0: return 0
	return distance * 100

def getRiverStartCardinalDirection(argsList):
	pPlot = argsList[0]
	(iW, iH, bWrapX, bWrapY, outerDistances, holeDistances,
	 outerWater, holeWater) = _get_river_distance_cache()
	index = pPlot.getY() * iW + pPlot.getX()
	current = _river_distance_at(index, outerDistances, holeDistances)
	bestDirection = CardinalDirectionTypes.CARDINALDIRECTION_NORTH
	bestDistance = current
	for other, direction in _river_neighbors(index, iW, iH, bWrapX, bWrapY):
		distance = _river_distance_at(other, outerDistances, holeDistances)
		if distance >= 0 and (bestDistance < 0 or distance < bestDistance):
			bestDistance = distance
			bestDirection = direction
	return bestDirection

# -----------------------------------------------------------------------------
# Starting plot
# -----------------------------------------------------------------------------

_START_PLOT_MAP = None
_TEAM_START_ACTIVE = False
_TEAM_SIDE_MAP = {}

def minStartingDistanceModifier():
	return 15

def findStartingPlot(argsList):
	[playerID] = argsList
	global _START_PLOT_MAP

	if _START_PLOT_MAP is None:
		_START_PLOT_MAP = _assign_all_starting_plots()

	return _START_PLOT_MAP.get(playerID, -1)

def _is_real_coast(pPlot, min_water_size=5):
	"""
	Checks if a land plot is adjacent to a water body of at least min_water_size.
	This prevents players from being 'Coastal' next to a 1-tile desert pond.
	"""
	if pPlot.isWater(): return False
	map = CyMap()
	# Check all 8 directions (including diagonals) for ocean-sized water
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			if dx == 0 and dy == 0: continue
			adj = map.plot(pPlot.getX() + dx, pPlot.getY() + dy)
			if adj and not adj.isNone():
				if adj.isWater():
					area = adj.area()
					if area and area.getNumTiles() >= min_water_size:
						return True
	return False

def _synced_shuffle(dice, lst):
	result = lst[:]
	for i in range(len(result) - 1, 0, -1):
		j = dice.get(i + 1, "Synced Shuffle")
		result[i], result[j] = result[j], result[i]
	return result

def _count_adjacent_water_tiles(map, x, y):
	iWaterCount = 0
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			if dx == 0 and dy == 0: continue
			pAdjacent = map.plot(x + dx, y + dy)
			if pAdjacent and not pAdjacent.isNone() and pAdjacent.isWater():
				iWaterCount += 1
	return iWaterCount

def _is_start_too_coastal(map, pPlot, playerID, context):
	iWaterCount = _count_adjacent_water_tiles(map, pPlot.getX(), pPlot.getY())
	if iWaterCount > 2:
		print "PY: Map rejected %s start for player %d at (%d, %d): %d adjacent water tiles" % (context, playerID, pPlot.getX(), pPlot.getY(), iWaterCount)
		return True
	return False

def _is_start_too_tundra(map, pPlot, playerID, context):
	iTundra = CyGlobalContext().getInfoTypeForString("TERRAIN_TUNDRA")
	if iTundra == -1: return False
	iTundraCount = 0
	x = pPlot.getX()
	y = pPlot.getY()
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			if dx == 0 and dy == 0: continue
			pAdjacent = map.plot(x + dx, y + dy)
			if pAdjacent and not pAdjacent.isNone() and pAdjacent.getTerrainType() == iTundra:
				iTundraCount += 1
	if iTundraCount > 2:
		print "PY: Map rejected %s start for player %d at (%d, %d): %d adjacent tundra tiles" % (context, playerID, x, y, iTundraCount)
		return True
	return False

def _find_team_start_in_bounds(playerID, bounds, assigned_coords, min_dist):
	map = CyMap()
	(xMin, xMax, yMin, yMax) = bounds
	bestValue = -1
	bestIndex = -1
	for x in range(xMin, xMax + 1):
		for y in range(yMin, yMax + 1):
			pPlot = map.plot(x, y)
			if pPlot.isWater() or pPlot.isPeak(): continue
			alreadyUsed = False
			for (ax, ay) in assigned_coords:
				if ax == x and ay == y:
					alreadyUsed = True
					break
				if plotDistance(x, y, ax, ay) < min_dist:
					alreadyUsed = True
					break
			if alreadyUsed: continue
			value = pPlot.getFoundValue(playerID)
			if value <= 0: continue
			if _is_start_too_coastal(map, pPlot, playerID, "Team Start"): continue
			if _is_start_too_tundra(map, pPlot, playerID, "Team Start"): continue
			if value > bestValue and value > 0:
				bestValue = value
				bestIndex = map.plotNum(x, y)
	return bestIndex

def _find_team_start(playerID, side, sliceIndex, numInTeam, assigned_coords):
	map = CyMap()
	iW = map.getGridWidth()
	iH = map.getGridHeight()
	bandWidth = max(1, (iW * 3) / 10)
	innerWidth = (iW * 2 + 9) / 10
	yMin = (sliceIndex * iH) / numInTeam
	yMax = ((sliceIndex + 1) * iH) / numInTeam - 1
	if side == 0:
		stripXMin, stripXMax = innerWidth, bandWidth - 1
		bandXMin, bandXMax = 0, bandWidth - 1
		halfXMin, halfXMax = 0, (iW / 2) - 1
	else:
		stripXMin, stripXMax = iW - bandWidth, iW - innerWidth - 1
		bandXMin, bandXMax = iW - bandWidth, iW - 1
		halfXMin, halfXMax = iW / 2, iW - 1

	# Keep the player's slice in the preferred strip; relax rows on fallback.
	searches = [
		(stripXMin, stripXMax, yMin, yMax),
		(bandXMin, bandXMax, 0, iH - 1),
		(halfXMin, halfXMax, 0, iH - 1)
	]
	for searchIndex in range(len(searches)):
		bounds = searches[searchIndex]
		if bounds[0] > bounds[1] or bounds[2] > bounds[3]: continue
		minDist = 10
		minAllowed = 5
		if searchIndex == 2: minAllowed = 1
		while minDist >= minAllowed:
			result = _find_team_start_in_bounds(playerID, bounds, assigned_coords, minDist)
			if result != -1: return result
			minDist -= 1
	return -1

def _assign_team_starting_plots(teamPlayers):
	global _TEAM_SIDE_MAP
	map = CyMap()
	gc = CyGlobalContext()
	dice = gc.getGame().getMapRand()
	teamIDs = teamPlayers.keys()
	teamIDs.sort()
	teamSides = [0, 1]
	if dice.get(2, "Shuffle Team Sides") == 1:
		teamSides = [1, 0]
	assignments = {}
	assignedCoords = []
	for teamIndex in range(2):
		teamID = teamIDs[teamIndex]
		side = teamSides[teamIndex]
		_TEAM_SIDE_MAP[teamID] = side
		players = teamPlayers[teamID]
		slices = _synced_shuffle(dice, range(len(players)))
		for playerIndex in range(len(players)):
			playerID = players[playerIndex]
			gc.getPlayer(playerID).AI_updateFoundValues(True)
			plotIndex = _find_team_start(playerID, side, slices[playerIndex], len(players), assignedCoords)
			if plotIndex == -1:
				print "Symmetrigaea: No valid team start for player %d on side %d" % (playerID, side)
				raise RuntimeError("Symmetrigaea: insufficient starting plots in team half")
			assignments[playerID] = plotIndex
			pPlot = map.plotByIndex(plotIndex)
			assignedCoords.append((pPlot.getX(), pPlot.getY()))
			print "Symmetrigaea: Team %d player %d starts at (%d, %d)" % (teamID, playerID, pPlot.getX(), pPlot.getY())
	return assignments

def _fallback_start_placement(playerID, existing_coords):
	map = CyMap()
	gc = CyGlobalContext()
	dice = gc.getGame().getMapRand()
	player = gc.getPlayer(playerID)
	player.AI_updateFoundValues(True)

	COASTAL_START_BIAS = 1.35 

	# Gather the top 3 largest areas
	all_areas = []
	for i in range(map.getIndexAfterLastArea()):
		pArea = map.getArea(i)
		if pArea and not pArea.isNone() and not pArea.isWater():
			all_areas.append((pArea.getNumTiles(), pArea.getID()))
			
	# Sort largest to smallest, keep top 3
	all_areas.sort(key=lambda item: -item[0])
	valid_area_ids = []
	for i in range(min(3, len(all_areas))):
		valid_area_ids.append(all_areas[i][1])

	if not valid_area_ids:
		return -1 # Map has no land at all

	iW, iH = map.getGridWidth(), map.getGridHeight()
	
	# Start with a generous distance
	min_dist = 15
	if map.getWorldSize() >= WorldSizeTypes.WORLDSIZE_LARGE: 
		min_dist = 20

	candidates = []
	
	# Loop to progressively lower the distance requirement if the map is crowded
	while min_dist >= 0:
		
		# Iterate through the top 3 areas in order of size
		for target_area_id in valid_area_ids:
			for x in range(iW):
				for y in range(iH):
					pPlot = map.plot(x, y)
					
					# HARD CHECK: No Water, No Peaks, must be on Target Area
					if not pPlot or pPlot.isWater() or pPlot.isPeak(): continue
					if pPlot.getArea() != target_area_id: continue

					# Distance check using stepDistance (Chebyshev)
					is_too_close = False
					if min_dist > 0:
						for (ax, ay) in existing_coords:
							if stepDistance(x, y, ax, ay) < min_dist:
								is_too_close = True
								break
					if is_too_close: continue

					val = pPlot.getFoundValue(playerID)
					if val > 0:
						if _is_start_too_coastal(map, pPlot, playerID, "Default Starts"): continue
						if _is_start_too_tundra(map, pPlot, playerID, "Default Starts"): continue
						# Use the "Real Coast" check (adjacent to water body >= 10 tiles)
						# We use 10 here so they don't spawn on a tiny 2-tile lake
						if _is_real_coast(pPlot, 10):
							val *= COASTAL_START_BIAS
						candidates.append((val, map.plotNum(x, y)))
			
			# If we found at least one candidate in this area, we stop checking smaller areas
			if len(candidates) > 0:
				break
				
		# If we found at least one candidate across any area, break out of the distance loop
		if len(candidates) > 0:
			break
			
		# If no spots found on any of the top 3 continents, shrink the minimum distance and try again
		if min_dist == 0:
			break # Give up if even 0 distance fails
			
		min_dist -= 3 # Shrink requirement by 3 tiles and rescan
		if min_dist < 0:
			min_dist = 0

	# Absolute emergency fallback if a civilization literally values NO land plot
	if not candidates:
		for x in range(iW):
			for y in range(iH):
				pPlot = map.plot(x, y)
				if pPlot and not pPlot.isWater() and not pPlot.isPeak() and pPlot.getArea() in valid_area_ids:
					if _is_start_too_coastal(map, pPlot, playerID, "Default Starts fallback"): continue
					if _is_start_too_tundra(map, pPlot, playerID, "Default Starts fallback"): continue
					candidates.append((10, map.plotNum(x, y)))
		
		if not candidates:
			print "Symmetrigaea: No start meeting adjacent water and tundra limits for player %d" % playerID
			return -1

	# Sort by highest found value
	candidates.sort(key=lambda item: -item[0])
	num_best_choices = min(5, len(candidates))
	return candidates[dice.get(num_best_choices, "Fallback Start Choice")][1]

# Run Starting Plot Assignments
def _assign_all_starting_plots():
	global _TEAM_START_ACTIVE, _TEAM_SIDE_MAP
	print "PY: Assigning all starting plots..."
	map = CyMap()
	gc = CyGlobalContext()
	# Force a recalculation of areas to ensure 'isWater' and 'area size' are accurate
	map.recalculateAreas()
	_TEAM_START_ACTIVE = False
	_TEAM_SIDE_MAP = {}
	teamPlayers = {}
	for i in range(gc.getMAX_CIV_PLAYERS()):
		player = gc.getPlayer(i)
		if player.isEverAlive():
			teamID = player.getTeam()
			if not teamPlayers.has_key(teamID):
				teamPlayers[teamID] = []
			teamPlayers[teamID].append(i)

	if map.getCustomMapOption(4) == 0 and len(teamPlayers) == 2:
		assignments = _assign_team_starting_plots(teamPlayers)
		_TEAM_START_ACTIVE = True
		return assignments
	if map.getCustomMapOption(4) == 0:
		print "Symmetrigaea: Team Start needs exactly two teams; using Default Starts"

	finalAssignments = {}
	assignedCoords = []
	for i in range(gc.getMAX_CIV_PLAYERS()):
		player = gc.getPlayer(i)
		if not player.isEverAlive(): continue
		plotIndex = _fallback_start_placement(i, assignedCoords)
		if plotIndex != -1:
			finalAssignments[i] = plotIndex
			pPlot = map.plotByIndex(plotIndex)
			assignedCoords.append((pPlot.getX(), pPlot.getY()))
		else:
			raise RuntimeError("Symmetrigaea: insufficient valid Default Starts")
	return finalAssignments


# -----------------------------------------------------------------------------
# Normalization overrides
# -----------------------------------------------------------------------------
def normalizeStartingPlotLocations():
	if _TEAM_START_ACTIVE:
		return None
	CyPythonMgr().allowDefaultImpl()
	return None

# def normalizeAddRiver():
	# return None

def normalizeRemovePeaks():
	"""
	Remove peaks only from the 1-tile radius of each player's starting plot.
	This overrides the default peak removal that could strip too many peaks.
	"""
	map = CyMap()
	gc = CyGlobalContext()
	iW = map.getGridWidth()
	iH = map.getGridHeight()

	# Collect all starting plots
	starts = []
	for i in range(gc.getMAX_CIV_PLAYERS()):
		player = gc.getPlayer(i)
		if player.isEverAlive():
			start_plot = player.getStartingPlot()
			if start_plot:
				starts.append((start_plot.getX(), start_plot.getY()))

	# For each start, look at plots within Chebyshev distance <= 1 (3x3 area)
	for sx, sy in starts:
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				x = sx + dx
				y = sy + dy
				if 0 <= x < iW and 0 <= y < iH:
					pPlot = map.plot(x, y)
					if pPlot.getPlotType() == PlotTypes.PLOT_PEAK:
						# Convert to hills
						pPlot.setPlotType(PlotTypes.PLOT_HILLS, True, True)

def normalizeAddGoodTerrain():
	return None

def normalizeRemoveBadTerrain():
	return None

def normalizeRemoveBadFeatures():
	map = CyMap()
	gc = CyGlobalContext()
	iW = map.getGridWidth()
	iH = map.getGridHeight()
	iJungle = gc.getInfoTypeForString("FEATURE_JUNGLE")
	if iJungle == -1: return None
	for i in range(gc.getMAX_CIV_PLAYERS()):
		player = gc.getPlayer(i)
		if not player.isEverAlive(): continue
		pStart = player.getStartingPlot()
		if pStart is None or pStart.isNone(): continue
		sx = pStart.getX()
		sy = pStart.getY()
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				if dx == 0 and dy == 0: continue
				x = sx + dx
				y = sy + dy
				if x < 0 or x >= iW or y < 0 or y >= iH: continue
				pPlot = map.plot(x, y)
				if pPlot.getFeatureType() != iJungle: continue
				iBonus = pPlot.getBonusType(-1)
				pPlot.setFeatureType(FeatureTypes.NO_FEATURE, -1)
				if iBonus != -1 and pPlot.getBonusType(-1) != iBonus:
					pPlot.setBonusType(iBonus)
	return None

def normalizeAddFoodBonuses():
	return None

def normalizeAddExtras():
	#CyPythonMgr().allowDefaultImpl() # disable default nomalizer
	addCustomResources() # custom Resource Generator
	revealOption = CyMap().getCustomMapOption(9)
	if revealOption > 0:
		revealStartingArea(revealOption + 1)

# -----------------------------------------------------------------------------
# Custom resource addition – Main entry point for all  resource handling
# -----------------------------------------------------------------------------

class ResourceManager:
	"""Manages custom resource placement for the Mediterranean map script."""
	def __init__(self, map, gc, dice, iW, iH):
		self.map = map
		self.gc = gc
		self.dice = dice
		self.iW = iW
		self.iH = iH
		self._cache = {}   
		
		self.world_size = self.map.getWorldSize()
		self.size_multiplier = {
			WorldSizeTypes.WORLDSIZE_DUEL:     0.5,
			WorldSizeTypes.WORLDSIZE_TINY:     0.5,
			WorldSizeTypes.WORLDSIZE_SMALL:    1,
			WorldSizeTypes.WORLDSIZE_STANDARD: 1,
			WorldSizeTypes.WORLDSIZE_LARGE:    1.34,
			WorldSizeTypes.WORLDSIZE_HUGE:     1.5,
		}

	def _bonus_id(self, name):
		if name in self._cache: return self._cache[name]
		bid = self.gc.getInfoTypeForString(name)
		self._cache[name] = bid
		return bid

	def _is_bonus_appropriate_for_plot(self, bonus_id, pPlot, bIgnoreFeature=False):
		"""
		Check plot type, terrain, and optionally feature without placement rules.
		"""
		if bonus_id == -1 or pPlot.isWater() or pPlot.isPeak(): return False
		info = self.gc.getBonusInfo(bonus_id)
		if pPlot.isHills():
			if not info.isHills(): return False
		else:
			if not info.isFlatlands(): return False
		iFeature = pPlot.getFeatureType()
		if iFeature == -1 or bIgnoreFeature:
			if not info.isTerrain(pPlot.getTerrainType()): return False
		else:
			if not info.isFeature(iFeature): return False
			if not info.isFeatureTerrain(pPlot.getTerrainType()): return False

		return True

	def _can_clear_feature_for_bonus(self, bonus_id, pPlot):
		iFeature = pPlot.getFeatureType()
		if iFeature == -1: return False
		if iFeature == self.gc.getInfoTypeForString("FEATURE_FLOOD_PLAINS"): return False
		if self._is_bonus_appropriate_for_plot(bonus_id, pPlot): return False
		return self._is_bonus_appropriate_for_plot(bonus_id, pPlot, True)

	def _place_compatible_bonus(self, bonus_id, pPlot, bAllowFeatureClear=False, bAllowPlotTypeFallback=False):
		if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: return False
		if self._is_bonus_appropriate_for_plot(bonus_id, pPlot):
			pPlot.setBonusType(bonus_id)
			return True
		if bAllowFeatureClear and self._can_clear_feature_for_bonus(bonus_id, pPlot):
			iFeature = pPlot.getFeatureType()
			iVariety = pPlot.getFeatureVariety()
			pPlot.setFeatureType(FeatureTypes.NO_FEATURE, -1)
			if self._is_bonus_appropriate_for_plot(bonus_id, pPlot):
				pPlot.setBonusType(bonus_id)
				return True
			pPlot.setFeatureType(iFeature, iVariety)
		if bAllowPlotTypeFallback and self._can_place_plot_type_fallback(bonus_id, pPlot):
			pPlot.setBonusType(bonus_id)
			print "PY: Symmetrigaea plot-type fallback placed %s at (%d, %d)" % (
				self.gc.getBonusInfo(bonus_id).getType(), pPlot.getX(), pPlot.getY())
			return True
		return False

	def _is_bonus_appropriate_plot_type(self, bonus_id, pPlot):
		"""
		Checks only whether the bonus can use this plot's topography.
		Used as the final fallback when no terrain-compatible tile remains.
		"""
		if pPlot.isWater(): return False
		if pPlot.getPlotType() == PlotTypes.PLOT_PEAK: return False

		info = self.gc.getBonusInfo(bonus_id)
		if pPlot.isHills():
			if not info.isHills(): return False
		else:
			if not info.isFlatlands(): return False

		return True

	def _can_place_plot_type_fallback(self, bonus_id, pPlot):
		if pPlot.getFeatureType() != -1: return False
		return self._is_bonus_appropriate_plot_type(bonus_id, pPlot)
	
	def place_bonus_in_BFC(self, bonus_list, count=1, check_existence=False):
		"""
		Place start food using terrain, feature clearing, then plot-type fallbacks.
		"""
		ids = []
		for b in bonus_list:
			bonusID = self._bonus_id(b)
			if bonusID != -1: ids.append(bonusID)
		iJungle = self.gc.getInfoTypeForString("FEATURE_JUNGLE")

		players = []
		for i in range(self.gc.getMAX_CIV_PLAYERS()):
			player = self.gc.getPlayer(i)
			if player.isEverAlive():
				pStart = player.getStartingPlot()
				if pStart and not pStart.isNone():
					players.append((player.getID(), pStart.getX(), pStart.getY()))

		for (pid, sx, sy) in players:
			# 1. Define the Big Fat Cross (21 tiles)
			bfc_offsets = []
			for dx in range(-2, 3):
				for dy in range(-2, 3):
					if dx == 0 and dy == 0: continue 
					if abs(dx) == 2 and abs(dy) == 2: continue 
					bfc_offsets.append((dx, dy))

			# 2. Remove target food under jungle, then count surviving food.
			existing_count = 0
			for dx, dy in bfc_offsets:
				nx, ny = sx + dx, sy + dy
				if 0 <= nx < self.iW and 0 <= ny < self.iH:
					pPlot = self.map.plot(nx, ny)
					if pPlot.isStartingPlot(): continue
					if pPlot.getBonusType(-1) not in ids: continue
					if iJungle != -1 and pPlot.getFeatureType() == iJungle:
						pPlot.setBonusType(-1)
					elif check_existence:
						existing_count += 1
			
			needed = count - existing_count
			
			# 3. Placement Loop: Run for every bonus still required
			for i in range(needed):
				# Shuffle the full list for every individual placement attempt
				shuffled_ids = _synced_shuffle(self.dice, ids[:])
				placed_successfully = False

				# --- TIER 1: NATURAL FIT ---
				# We iterate through the shuffled bonuses. If Bonus A doesn't fit 
				# anywhere in the BFC, we move to Bonus B.
				for chosen_id in shuffled_ids:
					tier1_plots = []
					for dx, dy in bfc_offsets:
						nx, ny = sx + dx, sy + dy
						if 0 <= nx < self.iW and 0 <= ny < self.iH:
							pPlot = self.map.plot(nx, ny)
							
							# Filter: No starts, no existing bonuses, NO WATER, NO PEAKS
							if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
							if pPlot.isWater() or pPlot.isPeak(): continue
							if iJungle != -1 and pPlot.getFeatureType() == iJungle: continue

							# Natural fit includes the current feature.
							if self._is_bonus_appropriate_for_plot(chosen_id, pPlot):
								tier1_plots.append(pPlot)

					if len(tier1_plots) > 0:
						target_plot = tier1_plots[self.dice.get(len(tier1_plots), "T1 Plot")]
						if self._place_compatible_bonus(chosen_id, target_plot):
							placed_successfully = True
							break

				# Fallback only removes a feature from a tile with matching terrain and plot type.
				if not placed_successfully:
					for chosen_id in shuffled_ids:
						fallback_plots = []
						for dx, dy in bfc_offsets:
							nx, ny = sx + dx, sy + dy
							if 0 <= nx < self.iW and 0 <= ny < self.iH:
								pPlot = self.map.plot(nx, ny)
								if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
								if self._can_clear_feature_for_bonus(chosen_id, pPlot):
									fallback_plots.append(pPlot)
						if fallback_plots:
							target_plot = fallback_plots[self.dice.get(len(fallback_plots), "Start Food Feature Fallback")]
							if self._place_compatible_bonus(chosen_id, target_plot, True):
								placed_successfully = True
								break
				# Final fallback uses an empty, featureless tile with matching plot type.
				if not placed_successfully:
					for chosen_id in shuffled_ids:
						fallback_plots = []
						for dx, dy in bfc_offsets:
							nx, ny = sx + dx, sy + dy
							if 0 <= nx < self.iW and 0 <= ny < self.iH:
								pPlot = self.map.plot(nx, ny)
								if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
								if self._can_place_plot_type_fallback(chosen_id, pPlot):
									fallback_plots.append(pPlot)
						if fallback_plots:
							target_plot = fallback_plots[self.dice.get(len(fallback_plots), "Start Food Plot Fallback")]
							if self._place_compatible_bonus(chosen_id, target_plot, False, True):
								placed_successfully = True
								break
				if not placed_successfully:
					print "Symmetrigaea: no featureless plot-type start food tile for player %d" % pid

	def place_bonus_in_radius(self, bonus_list, radius=5):
		"""
		Generic function to ensure a resource type exists within a radius.
		Uses plotDistance to ensure diagonal resources are correctly scanned.
		"""
		ids = []
		for b in bonus_list:
			bonusID = self._bonus_id(b)
			if bonusID != -1: ids.append(bonusID)

		players = []
		for i in range(self.gc.getMAX_CIV_PLAYERS()):
			player = self.gc.getPlayer(i)
			if player.isEverAlive():
				pStart = player.getStartingPlot()
				if pStart and not pStart.isNone():
					players.append((player.getID(), pStart.getX(), pStart.getY()))

		for (pid, sx, sy) in players:
			# Step 1: Scan for existing bonuses from the list
			has_bonus = False
			found_x, found_y = -1, -1
			
			# Nested loop creates a square, plotDistance trims it to a circle
			for dx in range(-radius, radius + 1):
				for dy in range(-radius, radius + 1):
					nx, ny = sx + dx, sy + dy
					
					# Boundary check
					if 0 <= nx < self.iW and 0 <= ny < self.iH:
						# plotDistance is the engine's standard for circular radii
						if plotDistance(sx, sy, nx, ny) <= radius:
							pPlot = self.map.plot(nx, ny)
							# Use TeamTypes.NO_TEAM to see all placed bonuses
							if pPlot.getBonusType(TeamTypes.NO_TEAM) in ids:
								has_bonus = True
								found_x, found_y = nx, ny
								break
				if has_bonus: break
			
			if has_bonus:
				# DEBUG: Place a sign on the EXISTING resource that triggered the skip
				# This helps you verify that the Horse 3 tiles away was actually detected.
				# CyEngine().addSign(self.map.plot(found_x, found_y), -1, "DEBUG: Found existing for P%d" % pid)
				print "MAP DEBUG: Player %d skipped. Found existing bonus at (%d, %d)" % (pid, found_x, found_y)
				continue

			# Step 2: Placement (Same logic as before, but using plotDistance for consistency)
			shuffled_ids = _synced_shuffle(self.dice, ids[:])
			placed_successfully = False
			target_plot = None
			final_id = -1

			# TIER 1: Natural Fit
			for chosen_id in shuffled_ids:
				tier1_plots = []
				for dx in range(-radius, radius + 1):
					for dy in range(-radius, radius + 1):
						nx, ny = sx + dx, sy + dy
						if 0 <= nx < self.iW and 0 <= ny < self.iH:
							if plotDistance(sx, sy, nx, ny) <= radius:
								pPlot = self.map.plot(nx, ny)
								if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
								if pPlot.isWater() or pPlot.isPeak(): continue

								if self._is_bonus_appropriate_for_plot(chosen_id, pPlot):
									tier1_plots.append(pPlot)

				if len(tier1_plots) > 0:
					target_plot = tier1_plots[self.dice.get(len(tier1_plots), "Radius T1")]
					final_id = chosen_id
					placed_successfully = True
					break 

			# TIER 2: Clear only an incompatible non-Flood Plains feature.
			if not placed_successfully:
				for chosen_id in shuffled_ids:
					fallback_plots = []
					for dx in range(-radius, radius + 1):
						for dy in range(-radius, radius + 1):
							nx, ny = sx + dx, sy + dy
							if 0 <= nx < self.iW and 0 <= ny < self.iH:
								if plotDistance(sx, sy, nx, ny) <= radius:
									pPlot = self.map.plot(nx, ny)
									if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
									if self._can_clear_feature_for_bonus(chosen_id, pPlot):
										fallback_plots.append(pPlot)
					if fallback_plots:
						target_plot = fallback_plots[self.dice.get(len(fallback_plots), "Radius Feature Fallback")]
						if self._place_compatible_bonus(chosen_id, target_plot, True):
							final_id = chosen_id
							placed_successfully = True
							break

			# TIER 3: Featureless tile with matching plot type; terrain may differ.
			if not placed_successfully:
				for chosen_id in shuffled_ids:
					fallback_plots = []
					for dx in range(-radius, radius + 1):
						for dy in range(-radius, radius + 1):
							nx, ny = sx + dx, sy + dy
							if 0 <= nx < self.iW and 0 <= ny < self.iH:
								if plotDistance(sx, sy, nx, ny) <= radius:
									pPlot = self.map.plot(nx, ny)
									if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
									if self._can_place_plot_type_fallback(chosen_id, pPlot):
										fallback_plots.append(pPlot)
					if fallback_plots:
						target_plot = fallback_plots[self.dice.get(len(fallback_plots), "Radius Plot Fallback")]
						if self._place_compatible_bonus(chosen_id, target_plot, False, True):
							final_id = chosen_id
							placed_successfully = True
							break

			if placed_successfully and target_plot:
				if target_plot.getBonusType(-1) == -1:
					placed_successfully = self._place_compatible_bonus(final_id, target_plot)
			if placed_successfully and target_plot:
				
				# Visual Marker for newly added resources
				bonus_name = self.gc.getBonusInfo(final_id).getType()
				# CyEngine().addSign(target_plot, -1, "DEBUG: Added " + bonus_name)
				print "MAP DEBUG: Placed %s for Player %d at (%d, %d)" % (bonus_name, pid, target_plot.getX(), target_plot.getY())
			else:
				print "Symmetrigaea: no featureless plot-type radius bonus tile for player %d" % pid


	def swap_resources(self, swap_rules, clear_feature=False):
		"""
		Swaps resources globally. Now explicitly skips starting plots to 
		prevent accidental changes to the capital's immediate tile.
		"""
		for rule in swap_rules:
			old_name = rule[0]
			new_name = rule[1]
			if len(rule) > 2:
				min_y_fraction = rule[2]
			else:
				min_y_fraction = 0.0
			
			old_id = self._bonus_id(old_name)
			y_thresh = int(self.iH * min_y_fraction)

			for i in range(self.map.numPlots()):
				pPlot = self.map.plotByIndex(i)
				# EXCLUDE starting plots from global swaps
				if pPlot.isStartingPlot(): continue
				
				if pPlot.getY() >= y_thresh and pPlot.getBonusType(-1) == old_id:
					if new_name:
						pPlot.setBonusType(self._bonus_id(new_name))
					else:
						pPlot.setBonusType(-1)
					
					if clear_feature:
						pPlot.setFeatureType(FeatureTypes.NO_FEATURE, -1)

	def _is_feature_allowed_for_bonus(self, bonus_id, feature_id):
		if feature_id == -1:
			return True

		bonusInfo = self.gc.getBonusInfo(bonus_id)
		iFeatureCount = self.gc.getNumFeatureInfos()
		for i in range(iFeatureCount):
			if i == feature_id:
				if bonusInfo.isFeature(i):
					return True
				return False

		return False

	def add_region_specific(self, region_specs, bChangePlains=False):
		"""
		Place bonuses in specified regions using center-based coordinates. 
		region["rect"] format: (cX, cY, width, height)
		region["bonuses"] entry format: (bonus_type, count, bChangePlains)
		"""
		multiplier = self.size_multiplier[self.world_size]
		iPlains = self.gc.getInfoTypeForString("TERRAIN_PLAINS")
		
		for region in region_specs:
			# Unpack center-based coordinates
			cX, cY, width, height = region["rect"]
			
			# Calculate pixel-grid boundaries from center
			west_x = int(self.iW * (cX - (width / 2.0)))
			east_x = int(self.iW * (cX + (width / 2.0)))
			south_y = int(self.iH * (cY - (height / 2.0)))
			north_y = int(self.iH * (cY + (height / 2.0)))

			# Clamp to map edges
			iWest = max(0, west_x)
			iEast = min(self.iW - 1, east_x)
			iSouth = max(0, south_y)
			iNorth = min(self.iH - 1, north_y)

			for bonus_entry in region["bonuses"]:
				scaled_count = int(bonus_entry[1] * multiplier)
				if scaled_count == 0: 
					continue
					
				bonus_id = self._bonus_id(bonus_entry[0])
				if len(bonus_entry) > 2:
					bBonusChangePlains = bonus_entry[2]
				else:
					bBonusChangePlains = False
				
				eligible = []
				plot_type_fallback = []
				
				# Scan the calculated rectangle
				for x in range(iWest, iEast + 1):
					for y in range(iSouth, iNorth + 1):
						pPlot = self.map.plot(x, y)
						
						# EXCLUDE starting plots from region-specific placement
						if pPlot.isStartingPlot(): 
							continue
						
						if pPlot.getBonusType(-1) == -1:
							if pPlot.canHaveBonus(bonus_id, True):
								eligible.append((x, y))
							elif self._is_bonus_appropriate_plot_type(bonus_id, pPlot):
								plot_type_fallback.append((x, y))

				# Placement Loop
				placed = 0
				for _ in range(scaled_count):
					choice = None
					bChangeTerrain = False
					if eligible:
						choice = eligible.pop(self.dice.get(len(eligible), "Region Bonus"))
					elif plot_type_fallback:
						choice = plot_type_fallback.pop(self.dice.get(len(plot_type_fallback), "Fallback Bonus"))
						if bBonusChangePlains:
							bChangeTerrain = True
					
					if choice:
						p = self.map.plot(choice[0], choice[1])
						if bChangeTerrain:
							p.setTerrainType(iPlains, True, True)
							iFeature = p.getFeatureType()
							if not self._is_feature_allowed_for_bonus(bonus_id, iFeature):
								p.setFeatureType(FeatureTypes.NO_FEATURE, -1)
						p.setBonusType(bonus_id)
						placed += 1

	def _team_band_plots(self, teamID):
		if not _TEAM_SIDE_MAP.has_key(teamID): return []
		bandWidth = max(1, (self.iW * 4) / 10)
		if _TEAM_SIDE_MAP[teamID] == 0:
			xMin, xMax = 0, bandWidth - 1
		else:
			xMin, xMax = self.iW - bandWidth, self.iW - 1
		plots = []
		for x in range(xMin, xMax + 1):
			for y in range(self.iH):
				plots.append(self.map.plot(x, y))
		return plots

	def _team_start_radius_plots(self, teamID, bandPlots, radius):
		starts = []
		for i in range(self.gc.getMAX_CIV_PLAYERS()):
			player = self.gc.getPlayer(i)
			if player.isEverAlive() and player.getTeam() == teamID:
				pStart = player.getStartingPlot()
				if pStart and not pStart.isNone():
					starts.append((pStart.getX(), pStart.getY()))
		plots = []
		for pPlot in bandPlots:
			for (sx, sy) in starts:
				if plotDistance(sx, sy, pPlot.getX(), pPlot.getY()) <= radius:
					plots.append(pPlot)
					break
		return plots

	def _balanced_bonus_candidates(self, plots, bonusID, stage):
		candidates = []
		for pPlot in plots:
			if pPlot.isWater() or pPlot.isPeak(): continue
			if pPlot.isStartingPlot() or pPlot.getBonusType(-1) != -1: continue
			if stage == 0:
				if not self._is_bonus_appropriate_for_plot(bonusID, pPlot): continue
			elif stage == 1:
				if not self._can_clear_feature_for_bonus(bonusID, pPlot): continue
			else:
				if not self._can_place_plot_type_fallback(bonusID, pPlot): continue
			candidates.append(pPlot)
		return candidates

	def balance_team_group(self, teamID, bonusNames, typeCount, copies, nearStarts=False, radius=5):
		bandPlots = self._team_band_plots(teamID)
		bonusIDs = []
		for name in bonusNames:
			bonusID = self._bonus_id(name)
			if bonusID != -1: bonusIDs.append(bonusID)
		for pPlot in bandPlots:
			if pPlot.getBonusType(-1) in bonusIDs:
				pPlot.setBonusType(-1)
		placementPlots = bandPlots
		if nearStarts:
			placementPlots = self._team_start_radius_plots(teamID, bandPlots, radius)
		bonusIDs = _synced_shuffle(self.dice, bonusIDs)
		for bonusID in bonusIDs[:typeCount]:
			for iCopy in range(copies):
				pTarget = None
				for stage in range(3):
					candidates = self._balanced_bonus_candidates(placementPlots, bonusID, stage)
					if candidates:
						pTarget = candidates[self.dice.get(len(candidates), "Team Bonus Placement")]
						break
				if pTarget is None:
					print "Symmetrigaea: no featureless plot-type band tile for team %d bonus %d" % (teamID, bonusID)
					break
				if not self._place_compatible_bonus(bonusID, pTarget, stage == 1, stage == 2):
					print "Symmetrigaea: failed team %d bonus %d compatibility check" % (teamID, bonusID)
					break

	def ensure_bonus_poisson(self, bonusNames, minDistance, minAreaSize):
		bonusIDs = []
		for name in bonusNames:
			bonusID = self._bonus_id(name)
			if bonusID != -1: bonusIDs.append(bonusID)
		samplesByArea = {}
		naturalCandidates = []
		fallbackCandidates = []
		plotTypeCandidates = []
		for i in range(self.map.numPlots()):
			pPlot = self.map.plotByIndex(i)
			if pPlot.isWater(): continue
			areaID = pPlot.getArea()
			pArea = self.map.getArea(areaID)
			if not pArea or pArea.isNone() or pArea.getNumTiles() < minAreaSize: continue
			if not samplesByArea.has_key(areaID): samplesByArea[areaID] = []
			if pPlot.getBonusType(-1) in bonusIDs:
				samplesByArea[areaID].append((pPlot.getX(), pPlot.getY()))
				continue
			if pPlot.getBonusType(-1) != -1 or pPlot.isPeak() or pPlot.isStartingPlot(): continue
			bNatural = False
			bFallback = False
			for bonusID in bonusIDs:
				if self._is_bonus_appropriate_for_plot(bonusID, pPlot):
					bNatural = True
					break
				if self._can_clear_feature_for_bonus(bonusID, pPlot): bFallback = True
			if bNatural:
				naturalCandidates.append(pPlot)
			elif bFallback:
				fallbackCandidates.append(pPlot)
			elif pPlot.getFeatureType() == -1:
				for bonusID in bonusIDs:
					if self._can_place_plot_type_fallback(bonusID, pPlot):
						plotTypeCandidates.append(pPlot)
						break
		for stage in range(3):
			if stage == 0:
				candidates = _synced_shuffle(self.dice, naturalCandidates)
			elif stage == 1:
				candidates = _synced_shuffle(self.dice, fallbackCandidates)
			else:
				candidates = _synced_shuffle(self.dice, plotTypeCandidates)
			for pPlot in candidates:
				if pPlot.getBonusType(-1) != -1: continue
				areaID = pPlot.getArea()
				x, y = pPlot.getX(), pPlot.getY()
				tooClose = False
				for (sampleX, sampleY) in samplesByArea[areaID]:
					if plotDistance(x, y, sampleX, sampleY) < minDistance:
						tooClose = True
						break
				if tooClose: continue
				compatible = []
				for bonusID in bonusIDs:
					if stage == 0:
						if self._is_bonus_appropriate_for_plot(bonusID, pPlot): compatible.append(bonusID)
					elif stage == 1:
						if self._can_clear_feature_for_bonus(bonusID, pPlot): compatible.append(bonusID)
					else:
						if self._can_place_plot_type_fallback(bonusID, pPlot): compatible.append(bonusID)
				if not compatible: continue
				bonusID = compatible[self.dice.get(len(compatible), "Map Food Bonus")]
				if self._place_compatible_bonus(bonusID, pPlot, stage == 1, stage == 2):
					samplesByArea[areaID].append((x, y))

def addCustomResources():
	m = CyMap()
	gc = CyGlobalContext()
	dice = gc.getGame().getMapRand()
	iW = m.getGridWidth()
	iH = m.getGridHeight()
	rm = ResourceManager(m, gc, dice, iW, iH)
	
	if _TEAM_START_ACTIVE and m.getCustomMapOption(5) == 1:
		print "PY: Symmetrigaea balancing team resource groups..."
		SemiStrategics = ["BONUS_IVORY", "BONUS_STONE", "BONUS_MARBLE"]
		PreciousMetals = ["BONUS_GOLD", "BONUS_SILVER", "BONUS_GEMS"]
		EarlyHappiness = ["BONUS_FUR", "BONUS_WINE"]
		CalendarBonus = ["BONUS_SPICES", "BONUS_SUGAR", "BONUS_DYE", "BONUS_INCENSE", "BONUS_SILK"]

		rm.swap_resources([("BONUS_IVORY", None)])

		sortedTeams = _TEAM_SIDE_MAP.keys()
		sortedTeams.sort()
		for iTeam in sortedTeams:
			iPlayerCount = 0
			for i in range(gc.getMAX_CIV_PLAYERS()):
				player = gc.getPlayer(i)
				if player.isEverAlive() and player.getTeam() == iTeam:
					iPlayerCount += 1
			iRoundedDown = max(1, int(0.5 * iPlayerCount))
			iRoundedUp = int(0.5 * iPlayerCount + 1)
			# Team, bonus group, number of types, copies of each type.
			rm.balance_team_group(iTeam, CalendarBonus, 4, iRoundedDown)
			rm.balance_team_group(iTeam, PreciousMetals, 3, iRoundedUp)
			rm.balance_team_group(iTeam, EarlyHappiness, 2, iRoundedUp)
			rm.balance_team_group(iTeam, SemiStrategics, 3, iRoundedDown, True, 4)

	mapFoodOption = m.getCustomMapOption(6)
	if mapFoodOption > 0:
		foodDistance = mapFoodOption + 2
		rm.ensure_bonus_poisson(["BONUS_WHEAT", "BONUS_RICE", "BONUS_CORN", "BONUS_COW", "BONUS_SHEEP", "BONUS_PIG", "BONUS_DEER", "BONUS_BANANA"], foodDistance, 5)

	foodCount = m.getCustomMapOption(7)
	if foodCount > 0:
		rm.place_bonus_in_BFC(["BONUS_WHEAT", "BONUS_RICE", "BONUS_CORN", "BONUS_SHEEP", "BONUS_PIG"], count=foodCount, check_existence=True)

	strategicOption = m.getCustomMapOption(8)
	if strategicOption > 0:
		rm.place_bonus_in_radius(["BONUS_IRON"], radius=4)
		if strategicOption == 1:
			rm.place_bonus_in_radius(["BONUS_COPPER", "BONUS_HORSE"], radius=5)
		else:
			rm.place_bonus_in_radius(["BONUS_COPPER"], radius=5)
			rm.place_bonus_in_radius(["BONUS_HORSE"], radius=5)

	# Preserve the existing late-strategic near-start rule.
	Late_Strategics = ["BONUS_COAL", "BONUS_URANIUM", "BONUS_ALUMINUM", "BONUS_OIL"]
	rm.place_bonus_in_radius(Late_Strategics, radius=5)

def revealStartingArea(iRadius=3):
	gc = CyGlobalContext()
	map = CyMap()
	iW = map.getGridWidth()
	iH = map.getGridHeight()
	for iPlayer in range(gc.getMAX_CIV_PLAYERS()):
		pPlayer = gc.getPlayer(iPlayer)
		if not pPlayer.isEverAlive(): continue
		pStart = pPlayer.getStartingPlot()
		if pStart is None or pStart.isNone(): continue
		iTeam = pPlayer.getTeam()
		sx, sy = pStart.getX(), pStart.getY()
		for dx in range(-iRadius, iRadius + 1):
			for dy in range(-iRadius, iRadius + 1):
				nx, ny = sx + dx, sy + dy
				if nx < 0 or nx >= iW or ny < 0 or ny >= iH: continue
				if plotDistance(sx, sy, nx, ny) <= iRadius:
					map.plot(nx, ny).setRevealed(iTeam, True, False, -1)
