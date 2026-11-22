"""Parametric templates in millimetres. Never execute model-produced code."""
from dataclasses import dataclass
from math import pi, isfinite, isclose
from build123d import Box, Cylinder, Align, Pos

MIN = (Align.MIN,) * 3

@dataclass(frozen=True)
class Field:
    label: str
    default: float
    min: float = 0.5
    max: float = 300

TEMPLATES = {
    "plate": {"label": "Mounting plate / لوح تثبيت", "fields": {
        "length": Field("Length / الطول", 80), "width": Field("Width / العرض", 50),
        "thickness": Field("Thickness / السمك", 6), "hole_diameter": Field("Hole diameter / قطر الثقوب", 6),
        "edge_offset": Field("Hole centre from edge / بُعد مركز الثقب عن الحافة", 12)}},
    "bushing": {"label": "Spacer / bushing / جلبة", "fields": {
        "outer_diameter": Field("Outer diameter / القطر الخارجي", 30),
        "inner_diameter": Field("Inner diameter / القطر الداخلي", 12), "height": Field("Height / الارتفاع", 20)}},
    "bracket": {"label": "L-bracket / زاوية تثبيت", "fields": {
        "length": Field("Base length / طول القاعدة", 60), "width": Field("Width / العرض", 40),
        "height": Field("Total height / الارتفاع الكلي", 50), "thickness": Field("Thickness / السمك", 5),
        "hole_diameter": Field("Base hole diameter / قطر ثقوب القاعدة", 6)}},
    "enclosure": {"label": "Open enclosure / علبة مفتوحة", "fields": {
        "length": Field("Length / الطول", 80), "width": Field("Width / العرض", 60),
        "height": Field("Height / الارتفاع", 30), "thickness": Field("Wall and floor / سمك الحائط والقاع", 3)}}
}


def schema():
    return {key: {"label": item["label"], "fields": {
        name: vars(field) for name, field in item["fields"].items()}}
        for key, item in TEMPLATES.items()}


def validate_dimensions(part_type: str, dimensions: dict) -> dict[str, float]:
    if part_type not in TEMPLATES:
        raise ValueError("Unknown part type.")
    if not isinstance(dimensions, dict):
        raise ValueError("Dimensions must be an object.")
    fields = TEMPLATES[part_type]["fields"]
    if set(dimensions) != set(fields):
        raise ValueError("Provide exactly these dimensions: " + ", ".join(fields))
    d = {}
    for name, field in fields.items():
        value = dimensions[name]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"{name} must be a number in mm.")
        value = float(value)
        if not isfinite(value) or not field.min <= value <= field.max:
            raise ValueError(f"{name} must be {field.min} to {field.max} mm.")
        d[name] = value
    t = d.get("thickness", 0)
    if part_type == "plate":
        r, e = d["hole_diameter"] / 2, d["edge_offset"]
        if not r + 0.5 <= e or 2 * e + 2 * r + 0.5 >= min(d["length"], d["width"]):
            raise ValueError("Plate holes need 0.5 mm edge clearance and must not overlap.")
    elif part_type == "bushing":
        if d["outer_diameter"] - d["inner_diameter"] < 1:
            raise ValueError("Bushing wall must be at least 0.5 mm thick.")
    elif part_type == "enclosure":
        if 2*t + 0.5 >= min(d["length"], d["width"]) or t + 0.5 >= d["height"]:
            raise ValueError("Enclosure needs a positive inner cavity of at least 0.5 mm.")
    elif part_type == "bracket":
        r = d["hole_diameter"] / 2
        if (t + r + 0.5 >= 0.65*d["length"] or r+0.5 >= 0.35*d["length"]
                or r+0.5 >= d["width"]/4 or t+0.5 >= d["height"]):
            raise ValueError("Bracket holes or wall do not fit. Increase base/height or reduce thickness/hole size.")
    return d


def generate_shape(part_type: str, dimensions: dict):
    """Return (OCCT shape, measured report). A failed check is never exported."""
    d = validate_dimensions(part_type, dimensions)
    if part_type == "bushing":
        h, ro, ri = d["height"], d["outer_diameter"]/2, d["inner_diameter"]/2
        shape = Cylinder(ro, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        shape -= Pos(0, 0, -1) * Cylinder(ri, h+2, align=(Align.CENTER, Align.CENTER, Align.MIN))
        expected_volume, expected_bbox = pi*(ro*ro-ri*ri)*h, (2*ro, 2*ro, h)
    else:
        l, w, t = d["length"], d["width"], d["thickness"]
        if part_type == "plate":
            shape = Box(l, w, t, align=MIN)
            e, r = d["edge_offset"], d["hole_diameter"]/2
            for x in (e, l-e):
                for y in (e, w-e):
                    shape -= Pos(x,y,-1) * Cylinder(r,t+2,align=(Align.CENTER,Align.CENTER,Align.MIN))
            expected_volume, expected_bbox = l*w*t - 4*pi*r*r*t, (l,w,t)
        elif part_type == "bracket":
            h, r = d["height"], d["hole_diameter"]/2
            shape = Box(l,w,t,align=MIN) + Pos(0,0,t)*Box(t,w,h-t,align=MIN)
            for y in (w/4,3*w/4):
                shape -= Pos(l*0.65,y,-1)*Cylinder(r,t+2,align=(Align.CENTER,Align.CENTER,Align.MIN))
            expected_volume, expected_bbox = l*w*t+t*w*(h-t)-2*pi*r*r*t, (l,w,h)
        else:
            h = d["height"]
            shape = Box(l,w,h,align=MIN) - Pos(t,t,t)*Box(l-2*t,w-2*t,h,align=MIN)
            expected_volume, expected_bbox = l*w*h-(l-2*t)*(w-2*t)*(h-t), (l,w,h)
    bbox = shape.bounding_box().size
    measured_bbox = (bbox.X, bbox.Y, bbox.Z)
    volume = shape.volume
    if not shape.is_valid or len(shape.solids()) != 1:
        raise ValueError("CAD validation failed: expected one valid solid.")
    if not isfinite(volume) or volume <= 0 or not isclose(volume,expected_volume,rel_tol=1e-6,abs_tol=1e-5):
        raise ValueError("CAD validation failed: volume mismatch.")
    if not all(isclose(a,b,rel_tol=1e-6,abs_tol=1e-5) for a,b in zip(measured_bbox,expected_bbox)):
        raise ValueError("CAD validation failed: bounding box mismatch.")
    return shape, {"valid": True, "solids": 1, "volume_mm3": round(volume,6),
                   "bbox_mm": [round(v,6) for v in measured_bbox], "units": "mm"}
