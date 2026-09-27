"""Symmetrigaea desktop simulator. Run with Python 3 and Tkinter.

All project source uses Python 2.4-compatible syntax for easier Civ IV porting.
"""

import random
import sys
import threading
import traceback

try:
    import Tkinter as tk
    import tkMessageBox as messagebox
    import Queue as queue
except ImportError:
    import tkinter as tk
    from tkinter import messagebox
    import queue

import Symmetrigaea_Generator as generator


BG = "#111b28"
PANEL = "#182535"
INPUT = "#223348"
TEXT = "#e3ecf5"
MUTED = "#9cacc0"
ACCENT = "#78d4be"
OCEAN = "#102c40"
LAND = "#7aaa80"
ADDED = "#f3bc61"
REMOVED = "#e783a3"
PROTECTED = "#6dd7ee"
PALETTE = ["#91b7a5", "#739fcb", "#ac93c5", "#caab74", "#73b5ae",
           "#cb8c93", "#8da866", "#9aace0", "#c7976d", "#77aec2",
           "#b6a0bd", "#a5b777", "#cf9eb9"]


class SimulatorApp:
    def __init__(self, root, autostart=True):
        self.root = root
        self.root.title("Symmetrigaea | Continent laboratory")
        self.root.geometry("1240x840")
        self.root.minsize(1020, 650)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.result = None
        self.busy = False
        self.closed = False
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.is_cancelled = getattr(self.stop_event, "is_set", None)
        if self.is_cancelled is None:
            self.is_cancelled = self.stop_event.isSet
        self.rng = random.Random()
        self.widgets = []
        self.variables = {}
        self.repaint_id = None
        self.view = tk.StringVar(root)
        self.view.set("plots")
        self.repair_view = tk.StringVar(root)
        self.repair_view.set("after")
        self.outlines = tk.IntVar(root)
        self.outlines.set(0)
        self.centers = tk.IntVar(root)
        self.centers.set(0)
        self.repairs = tk.IntVar(root)
        self.repairs.set(1)
        self.grid = tk.IntVar(root)
        self.grid.set(0)
        self.pending_text = tk.StringVar(root)
        self.pending_text.set("Settings apply on generation.")
        self.stage_text = tk.StringVar(root)
        self.stage_text.set("Ready")
        self.stats_text = tk.StringVar(root)
        self.stats_text.set("Generate a map to inspect its connectivity.")
        self.build_ui()
        self.root.after(80, self.poll)
        if autostart:
            self.root.after(150, self.apply_settings)

    def label(self, parent, text, color=TEXT, **options):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, **options)

    def button(self, parent, text, command, primary=False):
        bg = INPUT
        fg = TEXT
        if primary:
            bg = ACCENT
            fg = BG
        button = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                           activebackground=ACCENT, activeforeground=BG,
                           relief="flat", bd=0, padx=12, pady=8,
                           disabledforeground=MUTED, cursor="hand2")
        return button

    def section(self, parent, title):
        self.label(parent, title.upper(), ACCENT, font=("Segoe UI", 9, "bold"),
                   anchor="w").pack(fill="x", padx=16, pady=(18, 7))

    def field(self, parent, key, title, hint):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=16, pady=3)
        self.label(row, title, anchor="w").pack(side="left")
        variable = tk.StringVar(self.root)
        variable.set(str(generator.DEFAULTS[key]))
        self.variables[key] = variable
        entry = tk.Entry(row, textvariable=variable, width=8, justify="right",
                         bg=INPUT, fg=TEXT, insertbackground=TEXT, relief="flat",
                         highlightthickness=1, highlightbackground=INPUT,
                         highlightcolor=ACCENT)
        entry.pack(side="right", ipady=4)
        self.widgets.append(entry)
        self.label(parent, hint, MUTED, font=("Segoe UI", 8), anchor="w").pack(
            fill="x", padx=16, pady=(0, 2))
        if hasattr(variable, "trace_add"):
            variable.trace_add("write", self.settings_changed)
        else:
            variable.trace("w", self.settings_changed)

    def choice(self, parent, variable, value, title, command):
        button = tk.Radiobutton(parent, text=title, variable=variable, value=value,
                                command=command, indicatoron=0, selectcolor=INPUT,
                                bg=PANEL, fg=TEXT, activebackground=INPUT,
                                activeforeground=ACCENT, relief="flat", bd=0,
                                padx=10, pady=7, cursor="hand2")
        button.pack(side="left", padx=(0, 3))
        return button

    def checkbox(self, parent, text, variable, command):
        box = tk.Checkbutton(parent, text=text, variable=variable, command=command,
                             bg=parent.cget("bg"), fg=MUTED, selectcolor=INPUT,
                             activebackground=parent.cget("bg"), activeforeground=TEXT,
                             bd=0, highlightthickness=0)
        return box

    def build_ui(self):
        sidebar = tk.Frame(self.root, bg=PANEL, width=310)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.label(sidebar, "SYMMETRIGAEA", ACCENT,
                   font=("Segoe UI", 17, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(20, 1))
        self.label(sidebar, "A continent, two related halves", MUTED, anchor="w").pack(
            fill="x", padx=16, pady=(0, 15))

        actions = tk.Frame(sidebar, bg=PANEL)
        actions.pack(side="bottom", fill="x", padx=16, pady=12)
        self.apply_button = self.button(actions, "Apply settings", self.apply_settings)
        self.apply_button.pack(fill="x", pady=(0, 5))
        rerolls = tk.Frame(actions, bg=PANEL)
        rerolls.pack(fill="x")
        self.all_button = self.button(rerolls, "Reroll all", self.reroll_all, True)
        self.all_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.noise_button = self.button(rerolls, "Reroll noise", self.reroll_noise)
        self.noise_button.pack(side="left", fill="x", expand=True)
        self.noise_button.configure(state="disabled")
        self.cancel_button = self.button(actions, "Cancel generation", self.cancel)
        self.cancel_button.pack(fill="x", pady=(5, 0))
        self.cancel_button.configure(state="disabled")
        tk.Label(actions, textvariable=self.pending_text, bg=PANEL, fg=MUTED,
                 wraplength=270, justify="left", anchor="w",
                 font=("Segoe UI", 8)).pack(fill="x", pady=(7, 0))

        scroller = tk.Frame(sidebar, bg=PANEL)
        scroller.pack(fill="both", expand=True)
        self.settings_canvas = tk.Canvas(scroller, bg=PANEL, highlightthickness=0,
                                         width=287)
        scrollbar = tk.Scrollbar(scroller, orient="vertical",
                                 command=self.settings_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.settings_canvas.pack(side="left", fill="both", expand=True)
        self.settings_canvas.configure(yscrollcommand=scrollbar.set)
        form = tk.Frame(self.settings_canvas, bg=PANEL)
        form_id = self.settings_canvas.create_window(0, 0, window=form, anchor="nw")
        form.bind("<Configure>", lambda event: self.settings_canvas.configure(
            scrollregion=self.settings_canvas.bbox("all")))
        self.settings_canvas.bind("<Configure>", lambda event:
                                  self.settings_canvas.itemconfigure(form_id, width=event.width))
        self.root.bind_all("<MouseWheel>", self.scroll_settings)

        self.section(form, "Map & symmetry")
        self.field(form, "width", "Map width", "32-192 tiles")
        self.field(form, "height", "Map height", "32-192 tiles")
        self.field(form, "ocean_margin_x", "Ocean X margin %", "0-30% on west and east edges; rounded up")
        self.field(form, "ocean_margin_y", "Ocean Y margin %", "0-30% on south and north edges; rounded up")
        symmetry = tk.StringVar(self.root)
        symmetry.set("mirror")
        self.variables["symmetry"] = symmetry
        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=16, pady=8)
        self.widgets.append(self.choice(row, symmetry, "mirror", "Left / right", self.settings_changed))
        self.widgets.append(self.choice(row, symmetry, "rotation", "180 rotation", self.settings_changed))
        self.label(form, "Left/right: the core moves along the centerline.\n"
                   "Rotation: the core stays at the map center.", MUTED,
                   font=("Segoe UI", 8), justify="left", anchor="w").pack(
            fill="x", padx=16, pady=(0, 5))
        self.field(form, "seed", "Layout seed", "0-2147483647; Apply repeats the full generation")

        self.section(form, "Region layout")
        self.field(form, "pairs", "Region pairs", "1-12 pairs, plus the core")
        self.field(form, "region_width", "Region width %", "10-60% of map width")
        self.field(form, "region_height", "Region height %", "10-60% of map height")
        self.field(form, "variation", "Size variation %", "0-50%; independent width and height variation")
        self.field(form, "overlap", "Minimum overlap %", "5-60%; fraction of the smaller mask")
        self.field(form, "max_overlap", "Maximum overlap %", "5-100%; cap for every pair, including mirrors")
        self.field(form, "min_mask_area", "Min map-wide mask area %", "0-90% of whole map; overlapping tiles count once")
        self.field(form, "max_mask_area", "Max map-wide mask area %", "1-100% of whole map; 100 disables the cap")
        self.section(form, "Donut hole")
        donut = tk.IntVar(self.root)
        donut.set(int(generator.DEFAULTS["donut_hole"]))
        self.variables["donut_hole"] = donut
        box = self.checkbox(form, "Enclosed donut hole", donut, self.settings_changed)
        box.pack(anchor="w", padx=12, pady=6)
        self.widgets.append(box)
        self.field(form, "hole_width", "Hole width %", "2-50% of map width; at least 2 tiles")
        self.field(form, "hole_height", "Hole height %", "2-50% of map height; at least 2 tiles")
        self.field(form, "hole_variation", "Max size variation %", "0-50%; +/- relative to base hole dimensions")
        self.field(form, "hole_angle", "Base angle (degrees)", "0-359; counterclockwise from horizontal")
        self.field(form, "hole_rotation", "Max rotation (degrees)", "0-180; +/- around the base angle")
        self.field(form, "hole_jitter_x", "Max X shift %", "0-20%; +/- map width from the map center")
        self.field(form, "hole_jitter_y", "Max Y shift %", "0-20%; +/- map height from the map center")
        self.field(form, "hole_water", "Hole water %", "1-100% of the footprint; 100 fills the ellipse")
        self.field(form, "hole_grain", "Hole fractal grain", "0-6; GMF-style grain, higher is finer")
        self.label(form, "The hole works with the single core.\n"
                   "Protected water overrides all land masks.\n"
                   "Reroll all varies geometry within your limits.\n"
                   "Reroll noise reshapes the water shoreline.\n"
                   "Shore repairs count against the land budget.", MUTED,
                   font=("Segoe UI", 8), justify="left", anchor="w").pack(
            fill="x", padx=16, pady=(4, 6))
        self.section(form, "Shape weights")
        self.field(form, "ellipse_weight", "Ellipse", "0-100 relative weight")
        self.field(form, "rect_weight", "Rectangle", "0-100 relative weight")
        self.field(form, "triangle_weight", "Triangle", "0-100; at least one shape must be enabled")

        self.section(form, "Plot generation")
        self.field(form, "water", "Water %", "0-85%; per-region threshold, not total ocean %")
        self.field(form, "grain", "Land fractal grain", "0-6; GMF-style grain, higher is finer")
        edge = tk.IntVar(self.root)
        edge.set(1)
        self.variables["edge_reduction"] = edge
        box = self.checkbox(form, "Solid centers / softened edges (land + hole)",
                            edge, self.settings_changed)
        box.pack(anchor="w", padx=12, pady=6)
        self.widgets.append(box)

        self.section(form, "Connectivity repair")
        self.field(form, "bridge_width", "Bridge width", "1, 3, 5, or 7 tiles across the path")
        self.field(form, "repair_budget", "Added land budget %", "0-25% of original land; mirrored bridges count")
        self.label(form, "Target: 97% in the main continent, with no\n"
                   "secondary island larger than 1% of land.\n"
                   "Mask area and enabled hole target must be met.\n"
                   "Up to 8 attempts; failures remain visible.", MUTED,
                   justify="left", anchor="w", font=("Segoe UI", 8)).pack(
            fill="x", padx=16, pady=(6, 20))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=22, pady=20)
        heading = tk.Frame(main, bg=BG)
        heading.pack(fill="x")
        self.label(heading, "Continent laboratory", TEXT,
                   font=("Segoe UI", 22, "bold")).pack(side="left")
        self.badge = self.label(heading, "READY", MUTED, font=("Segoe UI", 10, "bold"))
        self.badge.pack(side="right")
        self.label(main, "Mirrored geometry. Independent coastlines. Measured connectivity.",
                   MUTED, anchor="w").pack(fill="x", pady=(3, 18))
        toolbar = tk.Frame(main, bg=PANEL)
        toolbar.pack(fill="x")
        self.choice(toolbar, self.view, "masks", "Region masks", self.redraw)
        self.choice(toolbar, self.view, "plots", "Generated plots", self.redraw)
        right = tk.Frame(toolbar, bg=PANEL)
        right.pack(side="right")
        self.choice(right, self.repair_view, "before", "Before repair", self.redraw)
        self.choice(right, self.repair_view, "after", "After repair", self.redraw)
        overlays = tk.Frame(main, bg=BG)
        overlays.pack(fill="x", pady=(8, 10))
        for title, variable in [("Region outlines", self.outlines), ("Centers", self.centers),
                                ("Repair marks", self.repairs), ("Grid", self.grid)]:
            self.checkbox(overlays, title, variable, self.redraw).pack(side="left", padx=(0, 10))
        self.canvas = tk.Canvas(main, bg=OCEAN, highlightthickness=1,
                                highlightbackground="#2b4056")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.schedule_redraw)
        legend = tk.Frame(main, bg=BG)
        legend.pack(fill="x", pady=(10, 4))
        for title, color in [("Land", LAND), ("Bridge additions", ADDED),
                              ("Removed islands", REMOVED), ("Protected water", PROTECTED)]:
            self.label(legend, "  " , color).pack(side="left")
            swatch = tk.Frame(legend, bg=color, width=10, height=10)
            swatch.pack(side="left", padx=(0, 5))
            self.label(legend, title, MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))
        self.stats_label = tk.Label(main, textvariable=self.stats_text, bg=BG, fg=TEXT,
                                   anchor="w", justify="left", font=("Segoe UI", 10))
        self.stats_label.pack(fill="x", pady=(8, 2))
        self.stage_label = tk.Label(main, textvariable=self.stage_text, bg=BG, fg=ACCENT,
                                   anchor="w", justify="left", wraplength=780)
        self.stage_label.pack(fill="x", pady=(3, 8))
        self.label(main, "Standalone port of Civ IV's unwrapped fractal algorithm. "
                   "Four-neighbor connectivity, no map wrapping.", MUTED,
                   anchor="w", font=("Segoe UI", 8), wraplength=800,
                   justify="left").pack(fill="x")

    def scroll_settings(self, event):
        pointer_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
        if pointer_x < 310:
            self.settings_canvas.yview_scroll(-int(event.delta / 120), "units")

    def settings_changed(self, *args):
        if self.result is not None:
            self.pending_text.set("Settings changed. Apply or Reroll all to regenerate.")

    def read_settings(self):
        values = {}
        for key in self.variables:
            values[key] = self.variables[key].get()
        return generator.validate_settings(values)

    def apply_settings(self):
        self.start("all")

    def reroll_all(self):
        if not self.busy:
            self.variables["seed"].set(str(self.rng.randrange(2147483648)))
            self.start("all")

    def reroll_noise(self):
        self.start("noise")

    def start(self, mode):
        if self.busy:
            return
        try:
            settings = self.read_settings()
            if mode == "noise" and self.result is None:
                return
            if mode == "noise" and settings != self.result["settings"]:
                raise ValueError("Apply the changed settings first, or restore their previous values. "
                                 "Reroll noise keeps the displayed region layout.")
        except ValueError:
            messagebox.showerror("Check settings", str(sys.exc_info()[1]), parent=self.root)
            return
        self.busy = True
        self.stop_event.clear()
        self.badge.configure(text="GENERATING", fg=ACCENT)
        self.stage_text.set("Starting generation...")
        self.set_controls(False)
        noise_seed = self.rng.randrange(2147483648)
        worker = threading.Thread(target=self.work, args=(mode, settings, self.result, noise_seed))
        if hasattr(worker, "daemon"):
            worker.daemon = True
        else:
            worker.setDaemon(True)
        worker.start()

    def set_controls(self, enabled):
        state = "disabled"
        cancel_state = "normal"
        if enabled:
            state = "normal"
            cancel_state = "disabled"
        for widget in self.widgets + [self.apply_button, self.all_button]:
            widget.configure(state=state)
        self.noise_button.configure(state=state)
        if self.result is None:
            self.noise_button.configure(state="disabled")
        self.cancel_button.configure(state=cancel_state)

    def progress(self, text):
        self.messages.put(("progress", text))

    def work(self, mode, settings, previous, noise_seed):
        try:
            if mode == "noise":
                result = generator.reroll_noise(previous, noise_seed, self.progress,
                                                self.is_cancelled)
            else:
                result = generator.generate(settings, self.progress, self.is_cancelled)
            generator.check_cancel(self.is_cancelled)
            self.messages.put(("result", result))
        except generator.Cancelled:
            self.messages.put(("cancelled", "Generation cancelled; previous map retained."))
        except Exception:
            self.messages.put(("error", (str(sys.exc_info()[1]), traceback.format_exc())))

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "progress":
                    self.stage_text.set(payload)
                else:
                    self.busy = False
                    if kind == "result":
                        self.result = payload
                        self.pending_text.set("Settings applied. Switching views preserves this map.")
                        self.redraw()
                        self.stage_text.set(payload["reason"])
                    elif kind == "cancelled":
                        self.stage_text.set(payload)
                        self.badge.configure(text="CANCELLED", fg=MUTED)
                    else:
                        self.stage_text.set(payload[0])
                        self.badge.configure(text="FAILED", fg=REMOVED)
                        sys.stderr.write(payload[1])
                        messagebox.showerror("Generation failed", payload[0] +
                                             "\n\nThe previous map has been retained.", parent=self.root)
                    self.set_controls(True)
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def cancel(self):
        self.stop_event.set()
        self.stage_text.set("Cancelling...")

    def schedule_redraw(self, event=None):
        if self.repaint_id is not None:
            self.root.after_cancel(self.repaint_id)
        self.repaint_id = self.root.after(80, self.redraw)

    def redraw(self):
        self.repaint_id = None
        canvas = self.canvas
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        self.stats_label.configure(wraplength=max(200, cw - 10))
        self.stage_label.configure(wraplength=max(200, cw - 10))
        if self.result is None:
            canvas.create_text(cw / 2, ch / 2, text="Your continent will appear here",
                               fill=MUTED, font=("Segoe UI", 15))
            return
        result = self.result
        settings = result["settings"]
        width = settings["width"]
        height = settings["height"]
        scale = min((cw - 24) / float(width), (ch - 24) / float(height))
        if scale <= 0:
            return
        ox = (cw - width * scale) / 2.0
        oy = (ch - height * scale) / 2.0
        colors = [OCEAN] * (width * height)
        ghost_marks = []
        masks = self.view.get() == "masks"
        if masks:
            for region in result["regions"]:
                color = PALETTE[region.pair % len(PALETTE)]
                for index in region.tiles:
                    colors[index] = color
        else:
            land = result["land"]
            if self.repair_view.get() == "before":
                land = result["raw"]
            for index in land:
                colors[index] = LAND
            if self.repairs.get():
                for index in result["added"]:
                    if index in land:
                        colors[index] = ADDED
                    else:
                        ghost_marks.append((index, ADDED, False))
                for index in result["removed"]:
                    if index in land:
                        colors[index] = REMOVED
                    else:
                        ghost_marks.append((index, REMOVED, True))
        water_preview = result["water_outline"]
        if masks:
            water_preview = result["water_region"]
        if water_preview is not None:
            for index in water_preview.tiles:
                colors[index] = OCEAN
        # Compress equal-color horizontal runs; this remains fast at 192x192.
        for y in range(height):
            x = 0
            top = oy + (height - 1 - y) * scale
            while x < width:
                color = colors[y * width + x]
                end = x + 1
                while end < width and colors[y * width + end] == color:
                    end += 1
                canvas.create_rectangle(ox + x * scale, top, ox + end * scale,
                                        top + scale, fill=color, outline="")
                x = end
        if self.grid.get() and scale >= 5:
            for x in range(width + 1):
                canvas.create_line(ox + x * scale, oy, ox + x * scale,
                                   oy + height * scale, fill="#294153")
            for y in range(height + 1):
                canvas.create_line(ox, oy + y * scale, ox + width * scale,
                                   oy + y * scale, fill="#294153")
        if self.outlines.get():
            for region in result["regions"]:
                self.draw_outline(region, width, height, ox, oy, scale)
            if not masks and result["water_region"] is not None:
                self.draw_outline(result["water_region"], width, height, ox, oy, scale, MUTED)
        if water_preview is not None:
            self.draw_outline(water_preview, width, height, ox, oy, scale, PROTECTED)
        for index, color, crossed in ghost_marks:
            left = ox + (index % width) * scale
            top = oy + (height - 1 - index // width) * scale
            inset = min(1.0, scale / 4.0)
            if crossed:
                canvas.create_line(left + inset, top + inset,
                                   left + scale - inset, top + scale - inset, fill=color)
                canvas.create_line(left + scale - inset, top + inset,
                                   left + inset, top + scale - inset, fill=color)
            else:
                canvas.create_rectangle(left + inset, top + inset,
                                        left + scale - inset, top + scale - inset,
                                        outline=color)
        if self.centers.get():
            for region in result["regions"]:
                x = ox + region.cx * scale
                y = oy + (height - region.cy) * scale
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=BG, outline=TEXT)
                canvas.create_text(x + 6, y - 7, text=region.name, anchor="sw",
                                   fill=TEXT, font=("Segoe UI", 9, "bold"))
            if result["water_region"] is not None:
                hole = result["water_region"]
                x = ox + hole.cx * scale
                y = oy + (height - hole.cy) * scale
                canvas.create_text(x, y, text="Water", fill=PROTECTED,
                                   font=("Segoe UI", 9, "bold"))
        canvas.create_rectangle(ox, oy, ox + width * scale, oy + height * scale,
                                outline="#4a6379")
        if masks:
            canvas.create_line(ox + width * scale / 2, oy,
                               ox + width * scale / 2, oy + height * scale,
                               fill=TEXT, dash=(4, 5))
            if settings["symmetry"] == "rotation":
                canvas.create_line(ox, oy + height * scale / 2,
                                   ox + width * scale, oy + height * scale / 2,
                                   fill=TEXT, dash=(4, 5))
        stats = result["stats"]
        status = "FINAL: TARGET MET"
        color = ACCENT
        if not stats["accepted"]:
            status = "FINAL: TARGET NOT MET"
            color = ADDED
        if not self.busy:
            self.badge.configure(text=status, fg=color)
        shown = stats
        name = "After repair"
        if self.repair_view.get() == "before":
            shown = result["raw_stats"]
            name = "Before repair"
        if masks:
            name = "Region masks (plots retained)"
        hole_status = "off"
        hole_details = ""
        if settings["donut_hole"]:
            hole_status = "NOT enclosed"
            if result["hole_enclosed"]:
                hole_status = "enclosed"
            hole = result["water_region"]
            hole_details = "\nHole: center %.1f, %.1f | size %.1f x %.1f | angle %.0f deg | water %d%%" % (
                hole.cx, hole.cy, hole.width, hole.height, hole.angle, settings["hole_water"])
        self.stats_text.set(
            "%s  |  %d x %d  |  %d regions\n"
            "Map-wide land-mask area %.1f%%  |  target %d-%d%%  |  final hole: %s\n"
            "%d land tiles (%.1f%%)  |  %d components  |  main continent %.2f%%\n"
            "Repairs: +%d / -%d tiles  |  layout %d / %d attempts\n"
            "Layout seed %d  |  noise seed %d" %
            (name, width, height, len(result["regions"]), result["mask_coverage"],
             settings["min_mask_area"], settings["max_mask_area"], hole_status,
             shown["land"], shown["coverage"],
             shown["components"], shown["share"], len(result["added"]), len(result["removed"]),
             result["layout_attempt"], result["attempts"], settings["seed"], result["noise_seed"]) + hole_details)

    def draw_outline(self, region, width, height, ox, oy, scale, color=TEXT):
        tiles = region.tiles
        for index in tiles:
            x = index % width
            y = index // width
            left = ox + x * scale
            top = oy + (height - 1 - y) * scale
            if index - 1 not in tiles or x == 0:
                self.canvas.create_line(left, top, left, top + scale, fill=color)
            if index + 1 not in tiles or x == width - 1:
                self.canvas.create_line(left + scale, top, left + scale, top + scale, fill=color)
            if index + width not in tiles:
                self.canvas.create_line(left, top, left + scale, top, fill=color)
            if index - width not in tiles:
                self.canvas.create_line(left, top + scale, left + scale, top + scale, fill=color)

    def close(self):
        self.closed = True
        self.stop_event.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    SimulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
