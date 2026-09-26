import math
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.stencilview import StencilView
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Line, Rectangle, Ellipse
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp, sp
from kivy.clock import Clock

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

Window.clearcolor = (0.95, 0.96, 0.98, 1)
SQFT_PER_SHATAK = 435.6


# ==========================================
# 1. Math & Geometry Validation Engine
# ==========================================
def get_diagonal_bounds(s1, s2, s3, s4, diag_type="Pt 1-3"):
    """
    বাহুগুলোর মান অনুযায়ী ডায়াগনালের গাণিতিক সর্বনিম্ন ও সর্বোচ্চ সীমা বের করে।
    """
    s1, s2, s3, s4 = float(s1), float(s2), float(s3), float(s4)
    if diag_type == "Pt 1-3":
        min_d = max(abs(s1 - s2), abs(s3 - s4))
        max_d = min(s1 + s2, s3 + s4)
    else:  # "Pt 2-4"
        min_d = max(abs(s1 - s4), abs(s2 - s3))
        max_d = min(s1 + s4, s2 + s3)
    return min_d, max_d


def calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type="Pt 1-3"):
    d_val = float(diag_val)
    s1, s2, s3, s4 = float(s1), float(s2), float(s3), float(s4)

    min_allowed, max_allowed = get_diagonal_bounds(s1, s2, s3, s4, diag_type)

    if not (min_allowed < d_val < max_allowed):
        raise ValueError(
            f"Input diagonal is geometrically impossible!\n"
            f"The {diag_type} diagonal value must be greater than "
            f"{min_allowed:.2f} ft and less than {max_allowed:.2f} ft based on the sides."
        )

    if diag_type == "Pt 1-3":
        x1, y1 = 0.0, 0.0
        x2, y2 = s1, 0.0

        cos_angle_p1 = (s1**2 + d_val**2 - s2**2) / (2 * s1 * d_val)
        cos_angle_p1 = max(-1.0, min(1.0, cos_angle_p1))
        angle_p1 = math.acos(cos_angle_p1)

        x3 = d_val * math.cos(-angle_p1)
        y3 = d_val * math.sin(-angle_p1)

        cos_angle_p4_offset = (s4**2 + d_val**2 - s3**2) / (2 * s4 * d_val)
        cos_angle_p4_offset = max(-1.0, min(1.0, cos_angle_p4_offset))
        angle_p4_offset = math.acos(cos_angle_p4_offset)

        total_angle_p4 = -angle_p1 - angle_p4_offset
        x4 = s4 * math.cos(total_angle_p4)
        y4 = s4 * math.sin(total_angle_p4)

        return [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]

    else:  # "Pt 2-4"
        x1, y1 = 0.0, 0.0
        x2, y2 = s1, 0.0

        cos_p1 = (s1**2 + s4**2 - d_val**2) / (2 * s1 * s4)
        cos_p1 = max(-1.0, min(1.0, cos_p1))
        angle_p4 = -math.acos(cos_p1)

        x4 = s4 * math.cos(angle_p4)
        y4 = s4 * math.sin(angle_p4)

        cos_p2_base = (s1**2 + d_val**2 - s4**2) / (2 * s1 * d_val)
        cos_p2_base = max(-1.0, min(1.0, cos_p2_base))
        beta = math.acos(cos_p2_base)

        cos_p2_tri = (s2**2 + d_val**2 - s3**2) / (2 * s2 * d_val)
        cos_p2_tri = max(-1.0, min(1.0, cos_p2_tri))
        gamma = math.acos(cos_p2_tri)

        angle_p3_dir = math.pi - beta - gamma
        x3 = x2 + s2 * math.cos(-angle_p3_dir)
        y3 = y2 + s2 * math.sin(-angle_p3_dir)

        return [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]


def polygon_area(pts):
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def divide_polygon_directional(pts, num_parts, target_area_sqft, direction):
    total_area = polygon_area(pts)

    if target_area_sqft >= total_area and target_area_sqft > 0:
        return [], 0, "Specified plot area cannot be equal to or greater than total area!", [], []

    is_vertical = direction in ["West to East", "East to West"]
    reverse_order = direction in ["East to West", "North to South"]

    idx = 0 if is_vertical else 1
    vals = [p[idx] for p in pts]
    min_v, max_v = min(vals), max(vals)

    def area_upto(V):
        poly = list(pts)
        clipped = []
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            p1_in = p1[idx] <= V
            p2_in = p2[idx] <= V

            if p1_in and p2_in:
                clipped.append(p2)
            elif p1_in and not p2_in:
                t = (V - p1[idx]) / (p2[idx] - p1[idx]) if p2[idx] != p1[idx] else 0
                clipped.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
            elif not p1_in and p2_in:
                t = (V - p1[idx]) / (p2[idx] - p1[idx]) if p2[idx] != p1[idx] else 0
                clipped.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
                clipped.append(p2)
        return polygon_area(clipped) if len(clipped) >= 3 else 0.0

    div_lines = []
    targets_to_find = []

    if target_area_sqft > 0:
        part_area = target_area_sqft
        req_area = total_area - part_area if reverse_order else part_area
        targets_to_find.append(req_area)
    else:
        part_area = total_area / max(1, num_parts)
        for k in range(1, num_parts):
            target = (total_area - (k * part_area)) if reverse_order else (k * part_area)
            targets_to_find.append(target)

    for target in targets_to_find:
        if target <= 0 or target >= total_area:
            continue
        low, high = min_v, max_v
        for _ in range(80):  # 80 Iterations for Extreme Precision
            mid = (low + high) / 2.0
            if area_upto(mid) < target:
                low = mid
            else:
                high = mid
        div_lines.append((low + high) / 2.0)

    partition_segments = []
    sub_edge_segments = []

    span_x = max(p[0] for p in pts) - min(p[0] for p in pts)
    span_y = max(p[1] for p in pts) - min(p[1] for p in pts)
    pad = max(span_x, span_y) * 3.0

    min_x, max_x = min(p[0] for p in pts) - pad, max(p[0] for p in pts) + pad
    min_y, max_y = min(p[1] for p in pts) - pad, max(p[1] for p in pts) + pad

    n = len(pts)
    div_pts_a, div_pts_b = [], []

    for div_v in div_lines:
        p_a, p_b = ((div_v, min_y), (div_v, max_y)) if is_vertical else ((min_x, div_v), (max_x, div_v))
        intersections = []
        for i in range(n):
            pt_int = line_intersection(p_a, p_b, pts[i], pts[(i + 1) % n])
            if pt_int:
                intersections.append(pt_int)

        if len(intersections) >= 2:
            intersections.sort(key=lambda p: p[1] if is_vertical else p[0])
            partition_segments.append((intersections[0], intersections[1]))
            div_pts_a.append(intersections[0])
            div_pts_b.append(intersections[1])

    if is_vertical:
        top_chain = [pts[0]] + sorted(div_pts_b, key=lambda p: p[0]) + [pts[1]]
        for i in range(len(top_chain) - 1):
            if dist(top_chain[i], top_chain[i + 1]) > 0.01:
                sub_edge_segments.append((top_chain[i], top_chain[i + 1], "top"))

        bot_chain = [pts[3]] + sorted(div_pts_a, key=lambda p: p[0]) + [pts[2]]
        for i in range(len(bot_chain) - 1):
            if dist(bot_chain[i], bot_chain[i + 1]) > 0.01:
                sub_edge_segments.append((bot_chain[i], bot_chain[i + 1], "bottom"))
    else:
        left_chain = [pts[3]] + sorted(div_pts_a, key=lambda p: p[1]) + [pts[0]]
        for i in range(len(left_chain) - 1):
            if dist(left_chain[i], left_chain[i + 1]) > 0.01:
                sub_edge_segments.append((left_chain[i], left_chain[i + 1], "left"))

        right_chain = [pts[2]] + sorted(div_pts_b, key=lambda p: p[1]) + [pts[1]]
        for i in range(len(right_chain) - 1):
            if dist(right_chain[i], right_chain[i + 1]) > 0.01:
                sub_edge_segments.append((right_chain[i], right_chain[i + 1], "right"))

    return div_lines, part_area, is_vertical, partition_segments, sub_edge_segments


# ==========================================
# 2. File Export Utilities (DXF & PDF)
# ==========================================
def get_save_filepath(filename):
    try:
        from kivy.utils import platform
        if platform == "android":
            download_dir = "/sdcard/Download"
            if not os.path.exists(download_dir):
                download_dir = "/storage/emulated/0/Download"
            return os.path.join(download_dir, filename)
        elif platform == "ios":
            from pyobjus import autoclass
            paths = autoclass("NSSearchPathForDirectoriesInDomains")("NSDocumentDirectory", "NSUserDomainMask", True)
            return os.path.join(paths.objectAtIndex(0).UTF8String(), filename)
        else:
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if os.path.exists(download_dir):
                return os.path.join(download_dir, filename)
    except Exception:
        pass
    return filename


def export_to_dxf(pts, div_lines, is_vertical, filename="land_map.dxf"):
    filename = get_save_filepath(filename)
    dxf_content = ["0", "SECTION", "2", "ENTITIES"]
    n = len(pts)
    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        dxf_content.extend([
            "0", "LINE", "8", "BOUNDARY",
            "10", str(p1[0]), "20", str(p1[1]), "30", "0.0",
            "11", str(p2[0]), "21", str(p2[1]), "31", "0.0"
        ])

    min_x, max_x = min(p[0] for p in pts), max(p[0] for p in pts)
    min_y, max_y = min(p[1] for p in pts), max(p[1] for p in pts)

    for div_v in div_lines:
        if is_vertical:
            dxf_content.extend([
                "0", "LINE", "8", "PARTITIONS",
                "10", str(div_v), "20", str(min_y), "30", "0.0",
                "11", str(div_v), "21", str(max_y), "31", "0.0"
            ])
        else:
            dxf_content.extend([
                "0", "LINE", "8", "PARTITIONS",
                "10", str(min_x), "20", str(div_v), "30", "0.0",
                "11", str(max_x), "21", str(div_v), "31", "0.0"
            ])

    dxf_content.extend(["0", "ENDSEC", "0", "EOF"])
    with open(filename, "w") as f:
        f.write("\n".join(dxf_content))
    return os.path.abspath(filename)


def export_to_pdf(pts, sides, diag_val, diag_type, part_summary_text="", partition_segments=None, sub_edge_segments=None, is_vertical=True, filename="land_report.pdf"):
    filename = get_save_filepath(filename)
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0, 0.35, 0.3)
    c.drawString(50, height - 45, "Surveyor Juel - Land Measurement Report")

    c.setStrokeColorRGB(0, 0.35, 0.3)
    c.setLineWidth(1)
    c.line(50, height - 52, width - 50, height - 52)

    text_object = c.beginText(50, height - 80)
    text_object.setFont("Helvetica-Bold", 11)
    text_object.setFillColorRGB(0, 0.3, 0.3)
    text_object.textLine("--- Boundary & Area Summary ---")
    text_object.setFont("Helvetica", 9.5)
    text_object.setFillColorRGB(0.1, 0.1, 0.1)

    total_area = polygon_area(pts)
    shatak = total_area / SQFT_PER_SHATAK
    text_object.textLine(f"Side 1 (P1-P2): {sides[0]:.2f} ft   |   Side 2 (P2-P3): {sides[1]:.2f} ft")
    text_object.textLine(f"Side 3 (P3-P4): {sides[2]:.2f} ft   |   Side 4 (P4-P1): {sides[3]:.2f} ft")
    text_object.textLine(f"Diagonal ({diag_type}): {diag_val:.2f} ft")
    text_object.setFont("Helvetica-Bold", 10)
    text_object.textLine(f"Total Area: {total_area:.2f} sq.ft ({shatak:.2f} Shatak)")
    text_object.textLine("")

    if part_summary_text:
        text_object.setFont("Helvetica-Bold", 11)
        text_object.setFillColorRGB(0, 0.3, 0.3)
        text_object.textLine("--- Partition Summary ---")
        text_object.setFont("Helvetica", 9.5)
        text_object.setFillColorRGB(0.1, 0.1, 0.1)
        for line in part_summary_text.split("\n"):
            text_object.textLine(line)

    c.drawText(text_object)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0, 0.3, 0.3)
    c.drawString(50, height - 240, "--- Graphic Plot Map (With All Dimension Values) ---")

    map_center_x, map_center_y = width / 2, height - 450
    map_box_w, map_box_h = 420, 320

    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    w_data, h_data = max(1e-4, max_x - min_x), max(1e-4, max_y - min_y)
    scale = min((map_box_w - 60) / w_data, (map_box_h - 60) / h_data)
    cx_data, cy_data = (min_x + max_x) / 2, (min_y + max_y) / 2

    def to_pdf_coord(pt):
        px = map_center_x + (pt[0] - cx_data) * scale
        py = map_center_y + (pt[1] - cy_data) * scale
        return px, py

    pdf_pts = [to_pdf_coord(p) for p in pts]

    if diag_val > 0:
        c.setStrokeColorRGB(0.85, 0.35, 0.1)
        c.setLineWidth(0.8)
        if diag_type == "Pt 1-3":
            c.line(pdf_pts[0][0], pdf_pts[0][1], pdf_pts[2][0], pdf_pts[2][1])
        else:
            c.line(pdf_pts[1][0], pdf_pts[1][1], pdf_pts[3][0], pdf_pts[3][1])

    if partition_segments:
        c.setStrokeColorRGB(0.1, 0.5, 0.8)
        c.setLineWidth(1.2)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColorRGB(0.1, 0.35, 0.75)
        for seg in partition_segments:
            sp1, sp2 = to_pdf_coord(seg[0]), to_pdf_coord(seg[1])
            c.line(sp1[0], sp1[1], sp2[0], sp2[1])
            p_len = dist(seg[0], seg[1])
            c.drawString((sp1[0] + sp2[0]) / 2 - 10, (sp1[1] + sp2[1]) / 2 + 2, f"{p_len:.1f}'")

    if sub_edge_segments:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColorRGB(0.1, 0.45, 0.85)
        for seg_info in sub_edge_segments:
            p1, p2, edge_pos = seg_info
            sp1, sp2 = to_pdf_coord(p1), to_pdf_coord(p2)
            seg_len = dist(p1, p2)
            mid_x, mid_y = (sp1[0] + sp2[0]) / 2, (sp1[1] + sp2[1]) / 2

            if edge_pos == "top":
                mid_y += 6
                mid_x -= 10
            elif edge_pos == "bottom":
                mid_y -= 12
                mid_x -= 10
            elif edge_pos == "left":
                mid_x -= 22
                mid_y -= 3
            elif edge_pos == "right":
                mid_x += 6
                mid_y -= 3

            c.drawString(mid_x, mid_y, f"{seg_len:.1f}'")

    c.setStrokeColorRGB(0.0, 0.45, 0.38)
    c.setLineWidth(2)
    n = len(pdf_pts)
    for i in range(n):
        p1, p2 = pdf_pts[i], pdf_pts[(i + 1) % n]
        c.line(p1[0], p1[1], p2[0], p2[1])

    c.setFont("Helvetica-Bold", 9)
    for i in range(n):
        sp1, sp2 = pdf_pts[i], pdf_pts[(i + 1) % n]

        c.setFillColorRGB(0.0, 0.5, 0.4)
        c.circle(sp1[0], sp1[1], 3, fill=1, stroke=0)

        c.setFillColorRGB(0, 0.3, 0.2)
        off_x = 6 if sp1[0] >= map_center_x else -16
        off_y = 6 if sp1[1] >= map_center_y else -12
        c.drawString(sp1[0] + off_x, sp1[1] + off_y, f"P{i+1}")

        mid_x, mid_y = (sp1[0] + sp2[0]) / 2, (sp1[1] + sp2[1]) / 2
        if i == 0:
            mid_y += 10
            mid_x -= 10
        elif i == 1:
            mid_x += 10
        elif i == 2:
            mid_y -= 14
            mid_x -= 10
        elif i == 3:
            mid_x -= 30

        c.setFillColorRGB(0.7, 0.1, 0.1)
        if not sub_edge_segments:
            c.drawString(mid_x, mid_y, f"{sides[i]:.1f}'")
        else:
            if is_vertical and i in [1, 3]:
                c.drawString(mid_x, mid_y, f"{sides[i]:.1f}'")
            elif not is_vertical and i in [0, 2]:
                c.drawString(mid_x, mid_y, f"{sides[i]:.1f}'")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, 40, "Developed by: Md. Juel Badsha | Mobile: +8801744431272")
    c.drawRightString(width - 50, 40, "Surveyor Juel Land App")

    c.save()
    return os.path.abspath(filename)


# ==========================================
# 3. Interactive Map Canvas Component
# ==========================================
class MapCanvasWidget(StencilView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pts = []
        self.div_lines = []
        self.partition_segments = []
        self.sub_edge_segments = []
        self.diag_val = 0.0
        self.diag_type = "Pt 1-3"
        self.part_area = 0.0
        self.sides = []
        self.is_vertical = True

        self.zoom_scale = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_touch_pos = None
        self.bind(size=self.trigger_redraw, pos=self.trigger_redraw)

    def draw_map(self, pts, sides, diag_val=0.0, diag_type="Pt 1-3", div_lines=None, part_area=0.0, is_vertical=True, partition_segments=None, sub_edge_segments=None):
        self.pts = pts
        self.sides = sides
        self.diag_val = diag_val
        self.diag_type = diag_type
        self.div_lines = div_lines if div_lines else []
        self.partition_segments = partition_segments if partition_segments else []
        self.sub_edge_segments = sub_edge_segments if sub_edge_segments else []
        self.part_area = part_area
        self.is_vertical = is_vertical
        self.trigger_redraw()

    def clear_canvas(self):
        self.pts, self.sides, self.div_lines = [], [], []
        self.partition_segments, self.sub_edge_segments = [], []
        self.diag_val = 0.0
        self.part_area = 0.0
        self.zoom_scale = 1.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.canvas.clear()

    def zoom_in(self, *args):
        self.zoom_scale *= 1.25
        self.trigger_redraw()

    def zoom_out(self, *args):
        self.zoom_scale /= 1.25
        self.trigger_redraw()

    def reset_zoom(self, *args):
        self.zoom_scale = 1.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.trigger_redraw()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.last_touch_pos = touch.pos
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self.last_touch_pos:
            dx = touch.x - self.last_touch_pos[0]
            dy = touch.y - self.last_touch_pos[1]
            self.pan_x += dx
            self.pan_y += dy
            self.last_touch_pos = touch.pos
            self.trigger_redraw()
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.last_touch_pos = None
            return True
        return super().on_touch_up(touch)

    def trigger_redraw(self, *args):
        Clock.unschedule(self.redraw)
        Clock.schedule_once(self.redraw, 0.05)

    def draw_text(self, text, pos, base_font_size=9, color=(0, 0, 0, 1)):
        try:
            dynamic_size = sp(base_font_size * (0.6 + 0.4 * self.zoom_scale))
            core_lbl = CoreLabel(text=str(text), font_size=dynamic_size, bold=True)
            core_lbl.refresh()
            texture = core_lbl.texture
            Color(*color)
            Rectangle(texture=texture, pos=pos, size=texture.size)
        except Exception:
            pass

    def redraw(self, dt=None):
        self.canvas.clear()
        if not self.pts or len(self.pts) < 4:
            return

        try:
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(pos=self.pos, size=self.size)

                Color(0.7, 0.8, 0.85, 1)
                Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)

                xs, ys = [p[0] for p in self.pts], [p[1] for p in self.pts]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                w_data, h_data = max(1e-4, max_x - min_x), max(1e-4, max_y - min_y)
                padding_x, padding_y = dp(65), dp(45)

                if self.width <= 2 * padding_x or self.height <= 2 * padding_y:
                    return

                base_scale = min(
                    (self.width - 2 * padding_x) / w_data,
                    (self.height - 2 * padding_y) / h_data,
                )
                scale = base_scale * self.zoom_scale

                cx_screen = self.x + self.width / 2 + self.pan_x
                cy_screen = self.y + self.height / 2 + self.pan_y
                cx_data, cy_data = (min_x + max_x) / 2, (min_y + max_y) / 2

                def to_screen(pt):
                    sx = cx_screen + (pt[0] - cx_data) * scale
                    sy = cy_screen + (pt[1] - cy_data) * scale
                    return (sx, sy)

                screen_pts = [to_screen(p) for p in self.pts]

                # Boundary Line
                Color(0.0, 0.45, 0.38, 1)
                flat_pts = []
                for sp_pt in screen_pts:
                    flat_pts.extend([sp_pt[0], sp_pt[1]])
                flat_pts.extend([screen_pts[0][0], screen_pts[0][1]])
                Line(points=flat_pts, width=2)

                # Diagonal Line
                if self.diag_val > 0:
                    Color(0.85, 0.35, 0.1, 0.35)
                    if self.diag_type == "Pt 1-3":
                        Line(points=[screen_pts[0][0], screen_pts[0][1], screen_pts[2][0], screen_pts[2][1]], width=1.1)
                    else:
                        Line(points=[screen_pts[1][0], screen_pts[1][1], screen_pts[3][0], screen_pts[3][1]], width=1.1)

                offset_factor = 0.7 + 0.3 * self.zoom_scale

                # Partition Lines
                Color(0.1, 0.5, 0.8, 1)
                for seg in self.partition_segments:
                    sp1, sp2 = to_screen(seg[0]), to_screen(seg[1])
                    Line(points=[sp1[0], sp1[1], sp2[0], sp2[1]], width=1.8)
                    p_len = dist(seg[0], seg[1])
                    mid_x = (sp1[0] + sp2[0]) / 2 - dp(10) * offset_factor
                    mid_y = (sp1[1] + sp2[1]) / 2 + dp(2) * offset_factor
                    self.draw_text(f"{p_len:.1f}'", (mid_x, mid_y), base_font_size=8, color=(0.1, 0.35, 0.75, 1))

                # Sub-edge Lengths
                if self.sub_edge_segments:
                    for seg_info in self.sub_edge_segments:
                        p1, p2, edge_pos = seg_info
                        sp1, sp2 = to_screen(p1), to_screen(p2)
                        seg_len = dist(p1, p2)
                        mid_x, mid_y = (sp1[0] + sp2[0]) / 2, (sp1[1] + sp2[1]) / 2

                        if edge_pos == "top":
                            mid_y += dp(6) * offset_factor
                            mid_x -= dp(10) * offset_factor
                        elif edge_pos == "bottom":
                            mid_y -= dp(14) * offset_factor
                            mid_x -= dp(10) * offset_factor
                        elif edge_pos == "left":
                            mid_x -= dp(26) * offset_factor
                            mid_y -= dp(3) * offset_factor
                        elif edge_pos == "right":
                            mid_x += dp(8) * offset_factor
                            mid_y -= dp(3) * offset_factor

                        self.draw_text(f"{seg_len:.1f}'", (mid_x, mid_y), base_font_size=8, color=(0.1, 0.45, 0.85, 1))

                # Vertices
                Color(0.0, 0.5, 0.4, 1)
                dot_size = dp(8) * min(2.5, max(0.8, offset_factor))
                for sp_pt in screen_pts:
                    Ellipse(pos=(sp_pt[0] - dot_size / 2, sp_pt[1] - dot_size / 2), size=(dot_size, dot_size))

                # Labels
                n = len(screen_pts)
                for i in range(n):
                    sp1, sp2 = screen_pts[i], screen_pts[(i + 1) % n]
                    offset_x = (dp(12) if sp1[0] >= cx_screen else -dp(24)) * offset_factor
                    offset_y = (dp(12) if sp1[1] >= cy_screen else -dp(18)) * offset_factor
                    self.draw_text(f"P{i+1}", (sp1[0] + offset_x, sp1[1] + offset_y), base_font_size=10, color=(0, 0.3, 0.2, 1))

                    mid_x, mid_y = (sp1[0] + sp2[0]) / 2, (sp1[1] + sp2[1]) / 2
                    if i == 0:
                        mid_y += dp(16) * offset_factor
                        mid_x -= dp(12) * offset_factor
                    elif i == 1:
                        mid_x += dp(24) * offset_factor
                    elif i == 2:
                        mid_y -= dp(20) * offset_factor
                        mid_x -= dp(12) * offset_factor
                    elif i == 3:
                        mid_x -= dp(38) * offset_factor

                    if not self.sub_edge_segments:
                        self.draw_text(f"{self.sides[i]:.1f}'", (mid_x, mid_y), base_font_size=10.5, color=(0.7, 0.1, 0.1, 1))
                    else:
                        if self.is_vertical and i in [1, 3]:
                            self.draw_text(f"{self.sides[i]:.1f}'", (mid_x, mid_y), base_font_size=10.5, color=(0.7, 0.1, 0.1, 1))
                        elif not self.is_vertical and i in [0, 2]:
                            self.draw_text(f"{self.sides[i]:.1f}'", (mid_x, mid_y), base_font_size=10.5, color=(0.7, 0.1, 0.1, 1))

                if self.part_area > 0:
                    shatak_val = self.part_area / SQFT_PER_SHATAK
                    txt = f"Part: {self.part_area:.0f} sq.ft ({shatak_val:.2f} Sh)"
                    y_offset = (dp(22) if not self.is_vertical else dp(8)) * offset_factor
                    self.draw_text(txt, (cx_screen - dp(55) * offset_factor, cy_screen - y_offset), base_font_size=9.5, color=(0.1, 0.2, 0.6, 1))

        except Exception as e:
            print("Redraw Exception Handled:", e)


# ==========================================
# 4. Main Application Interface
# ==========================================
class SSRKLandApp(App):
    def build(self):
        self.title = "Surveyor Juel - Land Divider"
        self.last_partition_info = ""

        root_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        main_layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10), size_hint_y=None)
        main_layout.bind(minimum_height=main_layout.setter("height"))

        header = Label(
            text="[b]Surveyor Juel[/b] - Land Divider",
            markup=True, size_hint_y=None, height=dp(35),
            color=(0, 0.35, 0.3, 1), font_size=sp(20)
        )
        main_layout.add_widget(header)

        sec1_lbl = Label(
            text="1. Boundary Sides & Diagonals",
            size_hint_y=None, height=dp(25), bold=True,
            color=(0.1, 0.2, 0.3, 1), font_size=sp(15), halign="left"
        )
        sec1_lbl.bind(size=sec1_lbl.setter("text_size"))
        main_layout.add_widget(sec1_lbl)

        grid_inputs = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(220))

        def create_input(default_val):
            inp = TextInput(
                text=default_val, multiline=False, input_filter="float",
                background_normal="", background_color=(1, 1, 1, 1),
                foreground_color=(0, 0, 0, 1), font_size=sp(15),
                padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(45)
            )
            inp.bind(text=self.on_side_input_change)
            return inp

        grid_inputs.add_widget(Label(text="Side 1 (Pt 1-2):", color=(0.2, 0.2, 0.2, 1), font_size=sp(13), halign="left"))
        self.txt_s1 = create_input("165")
        grid_inputs.add_widget(self.txt_s1)

        grid_inputs.add_widget(Label(text="Side 2 (Pt 2-3):", color=(0.2, 0.2, 0.2, 1), font_size=sp(13), halign="left"))
        self.txt_s2 = create_input("97")
        grid_inputs.add_widget(self.txt_s2)

        grid_inputs.add_widget(Label(text="Side 3 (Pt 3-4):", color=(0.2, 0.2, 0.2, 1), font_size=sp(13), halign="left"))
        self.txt_s3 = create_input("122")
        grid_inputs.add_widget(self.txt_s3)

        grid_inputs.add_widget(Label(text="Side 4 (Pt 4-1):", color=(0.2, 0.2, 0.2, 1), font_size=sp(13), halign="left"))
        self.txt_s4 = create_input("96")
        grid_inputs.add_widget(self.txt_s4)

        main_layout.add_widget(grid_inputs)

        diag_box = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(45))
        self.spn_diag_type = Spinner(
            text="Pt 1-3", values=("Pt 1-3", "Pt 2-4"),
            size_hint_x=0.4, font_size=sp(13), background_normal="",
            background_color=(0.2, 0.5, 0.6, 1), color=(1, 1, 1, 1)
        )
        self.spn_diag_type.bind(text=self.on_side_input_change)
        diag_box.add_widget(self.spn_diag_type)

        self.txt_diag = create_input("172.45")
        self.txt_diag.size_hint_x = 0.6
        diag_box.add_widget(self.txt_diag)

        main_layout.add_widget(diag_box)

        # Dynamic Reference Bounds Label
        self.lbl_ref_bounds = Label(
            text="Reference Diagonal Limits: --",
            size_hint_y=None, height=dp(25), color=(0.2, 0.4, 0.7, 1),
            bold=True, font_size=sp(12), halign="left"
        )
        self.lbl_ref_bounds.bind(size=self.lbl_ref_bounds.setter("text_size"))
        main_layout.add_widget(self.lbl_ref_bounds)

        act_box = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))

        btn_calc = Button(
            text="Generate Land Map", background_color=(0.0, 0.5, 0.4, 1),
            color=(1, 1, 1, 1), bold=True, size_hint_x=0.7, font_size=sp(15)
        )
        btn_calc.bind(on_press=self.on_calculate)
        act_box.add_widget(btn_calc)

        btn_reset = Button(
            text="Reset Map", background_color=(0.8, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), bold=True, size_hint_x=0.3, font_size=sp(13)
        )
        btn_reset.bind(on_press=self.on_reset)
        act_box.add_widget(btn_reset)

        main_layout.add_widget(act_box)

        self.lbl_area = Label(
            text="Total Area: 0.00 sq.ft (0.00 Shatak)",
            size_hint_y=None, height=dp(30), color=(0.0, 0.4, 0.3, 1),
            bold=True, font_size=sp(14)
        )
        main_layout.add_widget(self.lbl_area)

        # Map Container Frame
        map_container = FloatLayout(size_hint_y=None, height=dp(420))
        self.map_widget = MapCanvasWidget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        map_container.add_widget(self.map_widget)

        # Floating Zoom Control Panel
        zoom_box = BoxLayout(
            orientation="vertical", spacing=dp(5),
            size_hint=(None, None), size=(dp(40), dp(130)),
            pos_hint={'right': 0.98, 'y': 0.05}
        )

        btn_style = {
            'background_normal': '',
            'background_color': (0.9, 0.9, 0.9, 0.9),
            'color': (0.1, 0.1, 0.1, 1),
            'bold': True, 'font_size': sp(18)
        }

        btn_zoom_in = Button(text="+", **btn_style)
        btn_zoom_in.bind(on_press=self.map_widget.zoom_in)

        btn_zoom_reset = Button(text="R", **btn_style)
        btn_zoom_reset.bind(on_press=self.map_widget.reset_zoom)

        btn_zoom_out = Button(text="-", **btn_style)
        btn_zoom_out.bind(on_press=self.map_widget.zoom_out)

        zoom_box.add_widget(btn_zoom_in)
        zoom_box.add_widget(btn_zoom_reset)
        zoom_box.add_widget(btn_zoom_out)

        map_container.add_widget(zoom_box)
        main_layout.add_widget(map_container)

        sec2_lbl = Label(
            text="2. Partition Settings",
            size_hint_y=None, height=dp(25), bold=True,
            color=(0.1, 0.2, 0.3, 1), font_size=sp(15), halign="left"
        )
        sec2_lbl.bind(size=sec2_lbl.setter("text_size"))
        main_layout.add_widget(sec2_lbl)

        opt_grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(150))

        opt_grid.add_widget(Label(text="Mode:", color=(0.2, 0.2, 0.2, 1), font_size=sp(13), halign="left"))
        self.spn_mode = Spinner(
            text="By Shatak", values=("By Shatak", "By Sq.Ft", "Equal Division"),
            size_hint_y=None, height=dp(42), background_normal="",
            background_color=(0.2, 0.6, 0.6, 1), color=(1, 1, 1, 1), font_size=sp(13)
        )
        opt_grid.add_widget(self.spn_mode)

        opt_grid.add_widget(Label(text="Value / Parts:", color=(0.2, 0.2, 0.2, 1), font_size=sp(14), halign="left"))
        self.txt_part_val = TextInput(
            text="5", multiline=False, input_filter="float",
            background_normal="", background_color=(1, 1, 1, 1),
            foreground_color=(0, 0, 0, 1), font_size=sp(15),
            padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(45)
        )
        opt_grid.add_widget(self.txt_part_val)

        opt_grid.add_widget(Label(text="Direction:", color=(0.2, 0.2, 0.2, 1), font_size=sp(14), halign="left"))
        self.spn_dir = Spinner(
            text="West to East", values=("West to East", "East to West", "North to South", "South to North"),
            size_hint_y=None, height=dp(42), background_normal="",
            background_color=(0.2, 0.5, 0.7, 1), color=(1, 1, 1, 1), font_size=sp(14)
        )
        opt_grid.add_widget(self.spn_dir)

        main_layout.add_widget(opt_grid)

        # Action Buttons
        btn_box = BoxLayout(orientation="horizontal", spacing=dp(5), size_hint_y=None, height=dp(48))

        btn_divide = Button(
            text="Divide Plot", background_color=(0.1, 0.5, 0.35, 1),
            color=(1, 1, 1, 1), bold=True, font_size=sp(13), size_hint_x=0.34
        )
        btn_divide.bind(on_press=self.on_divide)
        btn_box.add_widget(btn_divide)

        btn_export = Button(
            text="Export CAD", background_color=(0.1, 0.4, 0.7, 1),
            color=(1, 1, 1, 1), bold=True, font_size=sp(13), size_hint_x=0.33
        )
        btn_export.bind(on_press=self.on_export_cad)
        btn_box.add_widget(btn_export)

        btn_pdf = Button(
            text="Export PDF", background_color=(0.7, 0.3, 0.1, 1),
            color=(1, 1, 1, 1), bold=True, font_size=sp(13), size_hint_x=0.33
        )
        btn_pdf.bind(on_press=self.on_export_pdf)
        btn_box.add_widget(btn_pdf)

        main_layout.add_widget(btn_box)

        self.lbl_output = Label(
            text="Calculation summary...",
            size_hint_y=None, height=dp(90), color=(0.15, 0.15, 0.15, 1),
            halign="left", valign="top", font_size=sp(13)
        )
        self.lbl_output.bind(size=self.lbl_output.setter("text_size"))
        main_layout.add_widget(self.lbl_output)

        developer_info_text = (
            "[b][color=008080]Developed by[/color][/b]\n"
            "[b][color=E65100]Md: Juel Badsha[/color][/b]\n"
            "[color=2E7D32]Address: Amrulbari polipara, Thana: Badargonj, Zilla: Rangpur, Bangladesh[/color]\n"
            "[b][color=D81B60]Mobile no: +8801744431272[/color][/b]"
        )

        dev_label = Label(
            text=developer_info_text, markup=True, halign="center",
            valign="middle", size_hint_y=None, height=dp(110), font_size=sp(13)
        )
        dev_label.bind(size=dev_label.setter("text_size"))
        main_layout.add_widget(dev_label)

        root_scroll.add_widget(main_layout)
        self.on_side_input_change()  # Initial calculation
        return root_scroll

    def on_side_input_change(self, *args):
        """ইনপুট দেওয়া মাত্রই রেফারেন্স সীমার রিয়েল-টাইম আপডেট দেখায়।"""
        try:
            s1 = float(self.txt_s1.text)
            s2 = float(self.txt_s2.text)
            s3 = float(self.txt_s3.text)
            s4 = float(self.txt_s4.text)
            diag_type = self.spn_diag_type.text

            min_d, max_d = get_diagonal_bounds(s1, s2, s3, s4, diag_type)
            self.lbl_ref_bounds.text = f"Allowed {diag_type} Diagonal: {min_d:.2f} ft to {max_d:.2f} ft"
            self.lbl_ref_bounds.color = (0.0, 0.5, 0.2, 1)
        except Exception:
            self.lbl_ref_bounds.text = "Reference Diagonal Limits: Incomplete inputs"
            self.lbl_ref_bounds.color = (0.8, 0.3, 0.0, 1)

    def get_inputs(self):
        try:
            s1 = float(self.txt_s1.text)
            s2 = float(self.txt_s2.text)
            s3 = float(self.txt_s3.text)
            s4 = float(self.txt_s4.text)
            diag_val = float(self.txt_diag.text)
            diag_type = self.spn_diag_type.text
            return s1, s2, s3, s4, diag_val, diag_type
        except Exception:
            return None

    def on_calculate(self, instance):
        vals = self.get_inputs()
        if not vals:
            self.lbl_output.text = "Error: Please enter valid numeric values for all sides."
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
            area = polygon_area(pts)
            shatak = area / SQFT_PER_SHATAK

            self.last_partition_info = ""
            self.lbl_area.text = f"Total Area: {area:.2f} sq.ft ({shatak:.2f} Shatak)"
            self.map_widget.draw_map(pts, [s1, s2, s3, s4], diag_val=diag_val, diag_type=diag_type)
            self.lbl_output.text = f"Success! Land Boundary Created.\nUsing Diagonal: {diag_type}\nTotal Area: {area:.2f} sq.ft | {shatak:.2f} Shatak"
        except ValueError as ve:
            self.lbl_output.text = f"Geometry Limit Error:\n{str(ve)}"
        except Exception as e:
            self.lbl_output.text = f"Calculation Error: {str(e)}"

    def on_reset(self, instance):
        self.txt_s1.text = ""
        self.txt_s2.text = ""
        self.txt_s3.text = ""
        self.txt_s4.text = ""
        self.txt_diag.text = ""
        self.txt_part_val.text = ""
        self.last_partition_info = ""
        self.lbl_area.text = "Total Area: 0.00 sq.ft (0.00 Shatak)"
        self.lbl_output.text = "Fields and map have been reset."
        self.lbl_ref_bounds.text = "Reference Diagonal Limits: --"
        self.map_widget.clear_canvas()

    def on_divide(self, instance):
        vals = self.get_inputs()
        if not vals:
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
            mode = self.spn_mode.text
            direction = self.spn_dir.text

            try:
                val = float(self.txt_part_val.text)
                if val <= 0:
                    return
            except ValueError:
                return

            target_sqft = val * SQFT_PER_SHATAK if mode == "By Shatak" else (val if mode == "By Sq.Ft" else 0)
            num_parts = int(val) if mode == "Equal Division" else 1

            div_lines, part_area, is_vertical, partition_segments, sub_edge_segments = divide_polygon_directional(
                pts, num_parts, target_sqft, direction
            )

            if isinstance(is_vertical, str):
                self.lbl_output.text = is_vertical
                return

            self.map_widget.draw_map(
                pts, [s1, s2, s3, s4],
                diag_val=diag_val, diag_type=diag_type,
                div_lines=div_lines, part_area=part_area,
                is_vertical=is_vertical, partition_segments=partition_segments,
                sub_edge_segments=sub_edge_segments
            )

            shatak_val = part_area / SQFT_PER_SHATAK
            out_text = f"Direction: {direction}\n"
            out_text += f"Plot Area: {part_area:.2f} sq.ft ({shatak_val:.2f} Shatak)\n"
            out_text += f"Total Plots: {len(div_lines) + 1}"

            self.last_partition_info = out_text
            self.lbl_output.text = f"Partition Summary:\n{out_text}"
        except Exception as e:
            self.lbl_output.text = f"Divide Error: {str(e)}"

    def on_export_cad(self, instance):
        vals = self.get_inputs()
        if not vals:
            self.lbl_output.text = "Error: Invalid inputs for CAD export!"
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
            direction = self.spn_dir.text
            mode = self.spn_mode.text

            try:
                val = float(self.txt_part_val.text)
                target_sqft = val * SQFT_PER_SHATAK if mode == "By Shatak" else (val if mode == "By Sq.Ft" else 0)
                num_parts = int(val) if mode == "Equal Division" else 1
                div_lines, _, is_vertical, _, _ = divide_polygon_directional(pts, num_parts, target_sqft, direction)
            except Exception:
                div_lines = []
                is_vertical = True

            filePath = export_to_dxf(pts, div_lines, is_vertical)
            self.lbl_output.text = f"CAD Export Successful!\nSaved File Path:\n{filePath}"
        except Exception as e:
            self.lbl_output.text = f"Export Error: {str(e)}"

    def on_export_pdf(self, instance):
        vals = self.get_inputs()
        if not vals:
            self.lbl_output.text = "Error: Please measure land before exporting PDF!"
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)

            pdf_path = export_to_pdf(
                pts=pts,
                sides=[s1, s2, s3, s4],
                diag_val=diag_val,
                diag_type=diag_type,
                part_summary_text=self.last_partition_info,
                partition_segments=self.map_widget.partition_segments,
                sub_edge_segments=self.map_widget.sub_edge_segments,
                is_vertical=self.map_widget.is_vertical,
            )
            self.lbl_output.text = f"PDF Export Successful!\nSaved PDF File Path:\n{pdf_path}"
        except Exception as e:
            self.lbl_output.text = f"PDF Export Error: {str(e)}"


# ==========================================
# 5. Program Entry Point
# ==========================================
if __name__ == "__main__":
    SSRKLandApp().run()
