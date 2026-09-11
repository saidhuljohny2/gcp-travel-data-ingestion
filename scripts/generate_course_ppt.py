"""Generate an editable PowerPoint marketing deck using only Python stdlib.

Run:
    python scripts/generate_course_ppt.py

Output:
    presentation/GCP_Travel_Data_Engineering_Course.pptx
"""

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile

W, H = 12_192_000, 6_858_000  # 13.333 x 7.5 inches (16:9)
OUT = Path(__file__).resolve().parents[1] / "presentation"
PPTX = OUT / "GCP_Travel_Data_Engineering_Course.pptx"

NAVY = "081426"
NAVY_2 = "10213B"
BLUE = "4285F4"
CYAN = "27C5E8"
GREEN = "34A853"
YELLOW = "FBBC04"
RED = "EA4335"
WHITE = "FFFFFF"
MUTED = "AFC2D9"
PALE = "E8F0FE"
DARK_TEXT = "152238"
SOFT = "1A2E49"


def emu(inches: float) -> int:
    return int(inches * 914_400)


def run(text: str, size: int, color: str, bold: bool = False,
        font: str = "Arial") -> str:
    weight = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="en-US" sz="{size * 100}"{weight}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{font}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>'
    )


def paragraph(text: str, size: int = 20, color: str = WHITE,
              bold: bool = False, align: str = "l", bullet: bool = False,
              font: str = "Arial") -> str:
    bullet_xml = '<a:buChar char="•"/>' if bullet else '<a:buNone/>'
    margin = ' marL="260000" indent="-180000"' if bullet else ""
    return (
        f'<a:p><a:pPr algn="{align}"{margin}>{bullet_xml}</a:pPr>'
        f'{run(text, size, color, bold, font)}'
        f'<a:endParaRPr lang="en-US" sz="{size * 100}"/></a:p>'
    )


class Slide:
    def __init__(self, title: str, number: int, section: str = "GCP DATA ENGINEERING"):
        self.number = number
        self.shapes: list[str] = []
        self._id = 2
        self.rect(0, 0, 13.333, 7.5, NAVY, radius=False)
        self.circle(10.9, -1.4, 3.9, BLUE, alpha=12)
        self.circle(-1.4, 5.5, 3.2, CYAN, alpha=8)
        self.text(section, 0.65, 0.36, 8.5, 0.26, 10, CYAN, bold=True)
        self.text(title, 0.65, 0.78, 12.0, 0.65, 28, WHITE, bold=True)
        self.line(0.65, 1.52, 12.67, 1.52, SOFT, 1)
        self.text(f"{number:02d}", 12.15, 7.05, 0.5, 0.2, 9, MUTED, align="r")

    def _next(self, prefix: str) -> tuple[int, str]:
        value = self._id
        self._id += 1
        return value, f"{prefix} {value}"

    def rect(self, x: float, y: float, w: float, h: float, fill: str,
             radius: bool = True, line: str | None = None,
             alpha: int | None = None) -> None:
        sid, name = self._next("Shape")
        geom = "roundRect" if radius else "rect"
        alpha_xml = f'<a:alpha val="{alpha * 1000}"/>' if alpha is not None else ""
        line_xml = (
            f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{line}"/>'
            f'</a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
        )
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
            f'<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}">{alpha_xml}</a:srgbClr></a:solidFill>'
            f'{line_xml}</p:spPr></p:sp>'
        )

    def circle(self, x: float, y: float, d: float, fill: str,
               alpha: int | None = None) -> None:
        sid, name = self._next("Circle")
        alpha_xml = f'<a:alpha val="{alpha * 1000}"/>' if alpha is not None else ""
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
            f'<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(d)}" cy="{emu(d)}"/></a:xfrm>'
            f'<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}">{alpha_xml}</a:srgbClr></a:solidFill>'
            f'<a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )

    def text(self, text: str, x: float, y: float, w: float, h: float,
             size: int = 20, color: str = WHITE, bold: bool = False,
             align: str = "l", font: str = "Arial",
             valign: str = "ctr") -> None:
        sid, name = self._next("Text")
        paras = "".join(
            paragraph(part, size, color, bold, align, font=font)
            for part in text.split("\n")
        )
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" anchor="{valign}" '
            f'lIns="0" rIns="0" tIns="0" bIns="0"/><a:lstStyle/>{paras}</p:txBody></p:sp>'
        )

    def bullets(self, items: list[str], x: float, y: float, w: float, h: float,
                size: int = 19, color: str = WHITE) -> None:
        sid, name = self._next("Bullets")
        paras = "".join(paragraph(item, size, color, bullet=True) for item in items)
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" anchor="t" lIns="0" rIns="0" '
            f'tIns="0" bIns="0"/><a:lstStyle/>{paras}</p:txBody></p:sp>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float,
             color: str = BLUE, width: int = 2, arrow: bool = False) -> None:
        sid, name = self._next("Line")
        arrow_xml = '<a:tailEnd type="none"/><a:headEnd type="triangle"/>' if arrow else ""
        self.shapes.append(
            f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="{name}"/>'
            f'<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{emu(x1)}" y="{emu(y1)}"/>'
            f'<a:ext cx="{emu(x2-x1)}" cy="{emu(y2-y1)}"/></a:xfrm>'
            f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{width * 12700}"><a:solidFill><a:srgbClr val="{color}"/>'
            f'</a:solidFill>{arrow_xml}</a:ln></p:spPr></p:cxnSp>'
        )

    def card(self, x: float, y: float, w: float, h: float, kicker: str,
             heading: str, body: str, accent: str = BLUE) -> None:
        self.rect(x, y, w, h, SOFT, line="27415F")
        self.rect(x, y, 0.08, h, accent, radius=False)
        self.text(kicker.upper(), x + 0.28, y + 0.2, w - 0.48, 0.24, 9, accent, bold=True)
        self.text(heading, x + 0.28, y + 0.58, w - 0.5, 0.42, 18, WHITE, bold=True)
        self.text(body, x + 0.28, y + 1.08, w - 0.5, h - 1.25, 12, MUTED, valign="t")

    def xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>'
            f'</p:grpSpPr>{"".join(self.shapes)}</p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        )


def title_slide() -> Slide:
    s = Slide("", 1, "BUILD • DEPLOY • AUTOMATE")
    s.text("GCP Travel Data\nIngestion Platform", 0.72, 1.2, 7.6, 1.45, 36, WHITE, bold=True)
    s.text("A production-style Data Engineering project—built live, end to end.",
           0.75, 2.95, 7.1, 0.55, 19, PALE)
    s.rect(0.75, 3.75, 3.6, 0.62, BLUE)
    s.text("ENROLL & BUILD WITH ME  →", 0.98, 3.86, 3.1, 0.28, 14, WHITE, bold=True)
    for i, (label, color) in enumerate([
        ("GCS", BLUE), ("Cloud Run", GREEN), ("BigQuery", YELLOW), ("Eventarc", RED)
    ]):
        x = 8.35 + (i % 2) * 2.05
        y = 1.72 + (i // 2) * 1.55
        s.rect(x, y, 1.72, 1.13, SOFT, line=color)
        s.text(label, x, y + 0.38, 1.72, 0.3, 15, color, bold=True, align="ctr")
    s.text("YOUR NAME  •  YOUR COURSE / ENROLLMENT LINK",
           0.75, 6.72, 7.5, 0.25, 10, MUTED, bold=True)
    return s


def build_slides() -> list[Slide]:
    slides = [title_slide()]

    s = Slide("Not another toy tutorial.", 2, "THE PROMISE")
    s.text("Students build a system that behaves like a real company pipeline.",
           0.68, 1.8, 7.1, 0.75, 26, WHITE, bold=True)
    s.bullets([
        "Dirty daily CSV files—not perfect demo data",
        "Validation, rejection reasons, lineage and audit",
        "Idempotent BigQuery MERGE for safe replays",
        "Cloud Run API + event-driven ingestion",
        "IAM without service-account JSON keys",
    ], 0.78, 2.8, 6.4, 2.9, 18)
    s.card(8.25, 2.0, 3.95, 3.7, "Outcome", "Portfolio proof",
           "A deployable repository, cloud architecture, live API, BigQuery tables, "
           "automation and interview-ready explanations.", CYAN)
    slides.append(s)

    s = Slide("The business problem", 3, "WHY THIS PROJECT EXISTS")
    s.card(0.7, 1.85, 3.7, 3.65, "01 • LAND", "Daily travel files",
           "Timestamped employee booking CSVs arrive with missing IDs, invalid dates, "
           "zero prices, mixed case and duplicates.", BLUE)
    s.card(4.8, 1.85, 3.7, 3.65, "02 • TRUST", "Protect analytics",
           "Good rows must reach reporting. Bad rows need clear rejection reasons—not "
           "silent loss or a poisoned fact table.", YELLOW)
    s.card(8.9, 1.85, 3.7, 3.65, "03 • PROVE", "Audit every run",
           "Operations needs file name, execution ID, counts, duration and failure details "
           "for every ingestion attempt.", GREEN)
    s.text("Raw files are easy. Trusted, replay-safe data is the engineering.",
           1.1, 6.05, 11.1, 0.45, 20, PALE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("Architecture: one pipeline, two entry points", 4, "SYSTEM DESIGN")
    nodes = [
        (0.65, "GCS", "incoming/*.csv", BLUE),
        (3.15, "Eventarc", "object finalized", RED),
        (5.65, "Cloud Run", "/events or /load", GREEN),
        (8.15, "Python", "validate • transform", CYAN),
        (10.65, "BigQuery", "MERGE • audit", YELLOW),
    ]
    for i, (x, name, sub, color) in enumerate(nodes):
        s.rect(x, 2.35, 1.85, 1.45, SOFT, line=color)
        s.text(name, x, 2.68, 1.85, 0.3, 17, color, bold=True, align="ctr")
        s.text(sub, x + 0.1, 3.16, 1.65, 0.23, 10, MUTED, align="ctr")
        if i < len(nodes) - 1:
            s.line(x + 1.88, 3.08, x + 2.42, 3.08, color, 2, arrow=True)
    s.rect(4.0, 4.65, 5.3, 0.85, SOFT, line=BLUE)
    s.text("Manual: POST /load     •     Automated: POST /events",
           4.2, 4.92, 4.9, 0.25, 14, WHITE, bold=True, align="ctr")
    s.text("Same src.pipeline.run_pipeline. Only the caller changes.",
           1.0, 5.95, 11.3, 0.4, 20, PALE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("Under the hood: readable Python modules", 5, "CODE WALKTHROUGH")
    modules = [
        ("gcs_reader.py", "Read CSV", BLUE),
        ("validator.py", "Trust rules", RED),
        ("transformer.py", "Standardize", CYAN),
        ("bigquery_loader.py", "Stage + MERGE", YELLOW),
        ("audit.py", "Prove the run", GREEN),
    ]
    for i, (name, job, color) in enumerate(modules):
        x = 0.65 + i * 2.5
        s.rect(x, 2.0, 2.15, 1.7, SOFT, line=color)
        s.text(f"{i+1:02d}", x + 0.18, 2.18, 0.45, 0.3, 12, color, bold=True)
        s.text(name, x + 0.18, 2.68, 1.8, 0.3, 13, WHITE, bold=True)
        s.text(job, x + 0.18, 3.16, 1.8, 0.24, 11, MUTED)
    s.rect(2.1, 4.45, 9.15, 1.05, SOFT, line=CYAN)
    s.text("src/pipeline.py", 2.42, 4.68, 2.2, 0.28, 16, CYAN, bold=True)
    s.text("glues every module into run_pipeline()", 4.5, 4.68, 6.2, 0.28, 17, WHITE)
    s.text("Students test each module first—then watch automation call the same code.",
           1.0, 6.02, 11.3, 0.35, 17, PALE, align="ctr")
    slides.append(s)

    s = Slide("Data quality you can see", 6, "VALIDATE • REJECT • EXPLAIN")
    s.card(0.7, 1.9, 3.7, 3.75, "VALID", "286 records",
           "Cleaned names and cities, uppercase status and currency, calculated travel "
           "duration, source file and execution lineage.", GREEN)
    s.card(4.8, 1.9, 3.7, 3.75, "REJECTED", "14 records",
           "Missing identifiers, duplicate booking IDs, invalid dates, non-positive fares "
           "and unsupported booking statuses.", RED)
    s.card(8.9, 1.9, 3.7, 3.75, "AUDITED", "Every execution",
           "Read / loaded / rejected counts, timing, status and error message—queryable "
           "in BigQuery.", BLUE)
    s.text("Bad data becomes teachable evidence—not a hidden failure.",
           1.1, 6.15, 11.0, 0.35, 19, WHITE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("Two automations. Two different jobs.", 7, "PRODUCTION THINKING")
    s.rect(0.75, 1.9, 5.7, 3.65, SOFT, line=BLUE)
    s.text("DATA AUTOMATION", 1.1, 2.25, 4.9, 0.28, 12, CYAN, bold=True)
    s.text("New CSV → Eventarc → /events", 1.1, 2.85, 4.9, 0.4, 22, WHITE, bold=True)
    s.text("Moves one object through validation and BigQuery.", 1.1, 3.55, 4.8, 0.5, 15, MUTED)
    s.rect(6.88, 1.9, 5.7, 3.65, SOFT, line=GREEN)
    s.text("DEPLOY AUTOMATION", 7.23, 2.25, 4.9, 0.28, 12, GREEN, bold=True)
    s.text("git push → Build → Cloud Run", 7.23, 2.85, 4.9, 0.4, 22, WHITE, bold=True)
    s.text("Ships a new container revision. It does not ingest data.", 7.23, 3.55, 4.8, 0.5, 15, MUTED)
    s.text("Knowing the difference is an interview-level skill.",
           1.1, 6.05, 11.1, 0.4, 19, PALE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("Live proof—not slides-only theory", 8, "PROJECT RESULTS")
    stats = [
        ("300", "ROWS READ", BLUE),
        ("286", "ROWS LOADED", GREEN),
        ("14", "ROWS REJECTED", RED),
        ("0", "FINAL DUPLICATES", YELLOW),
    ]
    for i, (value, label, color) in enumerate(stats):
        x = 0.72 + i * 3.1
        s.rect(x, 2.05, 2.75, 2.15, SOFT, line=color)
        s.text(value, x, 2.45, 2.75, 0.72, 36, color, bold=True, align="ctr")
        s.text(label, x, 3.47, 2.75, 0.25, 11, WHITE, bold=True, align="ctr")
    s.rect(2.1, 4.95, 9.15, 0.9, SOFT, line=CYAN)
    s.text("Re-upload safe: MERGE on booking_id  •  Eventarc delivery: at-least-once",
           2.35, 5.22, 8.65, 0.3, 15, PALE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("The GCP stack students actually touch", 9, "HANDS-ON CLOUD")
    services = [
        ("Cloud Storage", "Landing zone", BLUE),
        ("Cloud Run", "Container API", GREEN),
        ("BigQuery", "Warehouse", YELLOW),
        ("Eventarc", "Object events", RED),
        ("Artifact Registry", "Image store", CYAN),
        ("Cloud Build", "CI/CD", BLUE),
        ("IAM", "Least privilege", GREEN),
        ("Cloud Logging", "Operations", YELLOW),
    ]
    for i, (name, job, color) in enumerate(services):
        x = 0.72 + (i % 4) * 3.08
        y = 1.88 + (i // 4) * 2.1
        s.rect(x, y, 2.72, 1.55, SOFT, line=color)
        s.circle(x + 0.22, y + 0.28, 0.35, color)
        s.text(name, x + 0.7, y + 0.25, 1.8, 0.3, 15, WHITE, bold=True)
        s.text(job, x + 0.7, y + 0.82, 1.8, 0.25, 11, MUTED)
    s.text("Plus Python • Flask • Pandas • Docker • SQL • REST APIs",
           1.1, 6.18, 11.0, 0.3, 17, PALE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("How you will learn", 10, "COURSE EXPERIENCE")
    stages = [
        ("01", "Understand", "Business problem\n& architecture", BLUE),
        ("02", "Build", "Python modules\n& validations", CYAN),
        ("03", "Deploy", "Docker +\nCloud Run", GREEN),
        ("04", "Automate", "Eventarc +\nCloud Build", YELLOW),
        ("05", "Prove", "Logs, audit\n& interview", RED),
    ]
    for i, (num, head, body, color) in enumerate(stages):
        x = 0.58 + i * 2.54
        s.circle(x + 0.72, 1.95, 0.88, color)
        s.text(num, x + 0.72, 2.22, 0.88, 0.25, 13, NAVY, bold=True, align="ctr")
        s.text(head, x, 3.2, 2.3, 0.35, 17, WHITE, bold=True, align="ctr")
        s.text(body, x, 3.75, 2.3, 0.75, 13, MUTED, align="ctr")
        if i < 4:
            s.line(x + 1.65, 2.39, x + 2.42, 2.39, SOFT, 2)
    s.rect(2.45, 5.42, 8.45, 0.72, BLUE)
    s.text("SEE → DO → CHECK → EXPLAIN", 2.7, 5.63, 7.95, 0.28,
           16, WHITE, bold=True, align="ctr")
    slides.append(s)

    s = Slide("What you leave with", 11, "CAREER & PORTFOLIO")
    s.card(0.7, 1.85, 3.7, 3.8, "GITHUB", "A credible repository",
           "Modular source, sample data, SQL, Docker, deployment automation, demos and "
           "production-minded documentation.", BLUE)
    s.card(4.8, 1.85, 3.7, 3.8, "INTERVIEW", "A complete story",
           "Explain tool choices, validation order, staging, MERGE, IAM, idempotency, "
           "Eventarc and CI/CD with evidence.", CYAN)
    s.card(8.9, 1.85, 3.7, 3.8, "CONFIDENCE", "A live cloud system",
           "Run it, break it, replay it and verify it through APIs, logs, audits and "
           "BigQuery queries.", GREEN)
    slides.append(s)

    s = Slide("Is this course for you?", 12, "WHO SHOULD ENROLL")
    s.card(0.72, 1.85, 3.75, 3.9, "STARTING OUT", "Aspiring data engineers",
           "You know basic Python/SQL and want your first complete cloud project—not "
           "isolated syntax exercises.", BLUE)
    s.card(4.8, 1.85, 3.75, 3.9, "UPSKILLING", "Working professionals",
           "You want practical GCP, container, API, IAM and automation experience for "
           "your next role.", GREEN)
    s.card(8.88, 1.85, 3.75, 3.9, "TEACHING", "Interview preparation",
           "You need a system you can explain end-to-end, defend design choices and demo "
           "with confidence.", YELLOW)
    s.text("Prerequisites: basic Python + SQL curiosity. We build the cloud path together.",
           0.9, 6.2, 11.5, 0.3, 16, PALE, align="ctr")
    slides.append(s)

    s = Slide("Your capstone checklist", 13, "WHAT YOU WILL SHIP")
    left = [
        "Timestamped daily CSV landing zone",
        "Validation + rejected-record framework",
        "Transformations with lineage",
        "Staging + idempotent MERGE",
        "SUCCESS / FAILED audit trail",
    ]
    right = [
        "Flask REST API on Cloud Run",
        "Docker + Artifact Registry",
        "Eventarc file automation",
        "Cloud Build CI/CD",
        "IAM, logs and interview walkthrough",
    ]
    s.rect(0.75, 1.85, 5.75, 4.3, SOFT, line=BLUE)
    s.text("DATA PIPELINE", 1.08, 2.18, 4.9, 0.3, 13, CYAN, bold=True)
    s.bullets(left, 1.05, 2.75, 4.95, 2.8, 17)
    s.rect(6.85, 1.85, 5.75, 4.3, SOFT, line=GREEN)
    s.text("CLOUD DELIVERY", 7.18, 2.18, 4.9, 0.3, 13, GREEN, bold=True)
    s.bullets(right, 7.15, 2.75, 4.95, 2.8, 17)
    slides.append(s)

    s = Slide("Build the project. Tell the story. Get noticed.", 14, "READY TO START?")
    s.text("Stop collecting disconnected tutorials.\nShip one complete GCP data platform.",
           0.78, 1.65, 8.2, 1.25, 30, WHITE, bold=True)
    s.rect(0.8, 3.35, 4.55, 0.78, BLUE)
    s.text("ENROLL NOW  →", 1.08, 3.56, 3.95, 0.34, 19, WHITE, bold=True)
    s.text("YOUR ENROLLMENT LINK", 0.85, 4.42, 5.9, 0.32, 14, CYAN, bold=True)
    s.text("YOUR NAME  •  YOUR EMAIL / SOCIAL", 0.85, 5.02, 6.6, 0.3, 12, MUTED)
    s.rect(8.65, 1.75, 3.15, 3.15, WHITE, radius=False)
    s.text("ADD QR\nCODE HERE", 8.65, 2.7, 3.15, 0.85, 18, DARK_TEXT, bold=True, align="ctr")
    s.text("Live project • Source code • Teacher-led demos • Portfolio outcome",
           0.85, 6.25, 11.5, 0.35, 16, PALE, bold=True, align="ctr")
    slides.append(s)
    return slides


def content_types(count: int) -> str:
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f'{slides}</Types>'
    )


def package_parts(slides: list[Slide]) -> dict[str, str]:
    count = len(slides)
    slide_ids = "".join(
        f'<p:sldId id="{255+i}" r:id="rId{1+i}"/>' for i in range(1, count + 1)
    )
    pres_rels = (
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
        + "".join(
            f'<Relationship Id="rId{1+i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{i}.xml"/>' for i in range(1, count + 1)
        )
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parts = {
        "[Content_Types].xml": content_types(count),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>GCP Travel Data Engineering Course</dc:title>'
            '<dc:subject>Student showcase and enrollment deck</dc:subject>'
            '<dc:creator>GCP Travel Data Ingestion Platform</dc:creator>'
            '<cp:keywords>GCP, Data Engineering, Cloud Run, BigQuery, Eventarc</cp:keywords>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
            '</cp:coreProperties>'
        ),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Microsoft Office PowerPoint</Application>'
            f'<Slides>{count}</Slides><PresentationFormat>Widescreen</PresentationFormat>'
            '<AppVersion>16.0000</AppVersion></Properties>'
        ),
        "ppt/presentation.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            f'<p:sldIdLst>{slide_ids}</p:sldIdLst>'
            f'<p:sldSz cx="{W}" cy="{H}" type="screen16x9"/>'
            '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
        ),
        "ppt/_rels/presentation.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{pres_rels}</Relationships>'
        ),
        "ppt/slideMasters/slideMaster1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
            '<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
            '<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" '
            'accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" '
            'folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>'
            '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'
        ),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
            '</Relationships>'
        ),
        "ppt/slideLayouts/slideLayout1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank">'
            '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
            '<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
        ),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
            '</Relationships>'
        ),
        "ppt/theme/theme1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="GCP Dark">'
            '<a:themeElements><a:clrScheme name="GCP"><a:dk1><a:srgbClr val="081426"/></a:dk1>'
            '<a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="152238"/></a:dk2>'
            '<a:lt2><a:srgbClr val="E8F0FE"/></a:lt2><a:accent1><a:srgbClr val="4285F4"/></a:accent1>'
            '<a:accent2><a:srgbClr val="34A853"/></a:accent2><a:accent3><a:srgbClr val="FBBC04"/></a:accent3>'
            '<a:accent4><a:srgbClr val="EA4335"/></a:accent4><a:accent5><a:srgbClr val="27C5E8"/></a:accent5>'
            '<a:accent6><a:srgbClr val="AFC2D9"/></a:accent6><a:hlink><a:srgbClr val="4285F4"/></a:hlink>'
            '<a:folHlink><a:srgbClr val="7B61FF"/></a:folHlink></a:clrScheme>'
            '<a:fontScheme name="Arial"><a:majorFont><a:latin typeface="Arial"/></a:majorFont>'
            '<a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme>'
            '<a:fmtScheme name="GCP"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '</a:fillStyleLst><a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/>'
            '</a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/>'
            '</a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/>'
            '</a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'
        ),
    }
    for i, slide in enumerate(slides, 1):
        parts[f"ppt/slides/slide{i}.xml"] = slide.xml()
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '</Relationships>'
        )
    return parts


def main() -> None:
    slides = build_slides()
    parts = package_parts(slides)
    OUT.mkdir(exist_ok=True)
    with zipfile.ZipFile(PPTX, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    print(f"Created {PPTX}")
    print(f"Slides: {len(slides)} | Size: {PPTX.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
