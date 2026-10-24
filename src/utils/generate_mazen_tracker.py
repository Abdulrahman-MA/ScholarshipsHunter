import os
import sys
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_EXCEL = os.path.join(BASE_DIR, "scholarships_tracker.xlsx")
OUTPUT_EXCEL = os.path.join(BASE_DIR, "Mazen_Scholarships_Tracker.xlsx")

RE_INTERNSHIP = re.compile(r'\b(internships?|interns?|summer school|summer student|summer research|vsrp|reu|student programme)\b', re.IGNORECASE)
RE_PLASMA_NUCLEAR = re.compile(r'\b(plasma|nuclear|accelerator|cyclotron|synchrotron|fusion|tokamak|iter|beam physics)\b', re.IGNORECASE)
RE_FELLOWSHIP = re.compile(r'\b(fellowships?|fellows?)\b', re.IGNORECASE)
RE_MSC = re.compile(r'\b(msc|master\'?s?|masters|magister|postgraduate diploma)\b', re.IGNORECASE)

def build_mazen_tracker():
    if not os.path.exists(SOURCE_EXCEL):
        print(f"Error: Source tracker {SOURCE_EXCEL} not found.")
        return

    print("=" * 60)
    print(" GENERATING PERSONALIZED TRACKER FOR MAZEN MORSI ")
    print(" Target: B.Sc. Physics (Graduating July 2027) | CGPA: 3.3/4.0")
    print(" Focus: Undergrad Summer Internships, Plasma/Nuclear, & DSU MSc")
    print("=" * 60)

    wb_in = openpyxl.load_workbook(SOURCE_EXCEL, data_only=True)
    ws_in = wb_in.active

    headers = [cell.value for cell in ws_in[1]]
    mazen_rows = []

    for row in ws_in.iter_rows(min_row=2, values_only=True):
        cat, title, opp_type, deadline, funding, fields, link, action, inst, date, source, score, rationale, deep = row

        cat_str = str(cat or "").strip()
        title_str = str(title or "").strip()
        type_str = str(opp_type or "").strip()
        fields_str = str(fields or "").strip()
        rationale_str = str(rationale or "").strip()
        funding_str = str(funding or "").strip()

        # Disqualify any record that was Red in the master tracker
        if cat_str not in ["Green", "Yellow"]:
            continue

        combined_target = f"{title_str} {type_str} {fields_str}"

        # Hard non-STEM filter
        if any(bad in combined_target.lower() for bad in ["business administration", "mba", "accounting", "pharmacy", "medicine", "nursing", "journalism", "us citizen only"]):
            continue

        is_internship = bool(RE_INTERNSHIP.search(title_str) or RE_INTERNSHIP.search(type_str))
        is_plasma_nuclear = bool(RE_PLASMA_NUCLEAR.search(title_str) or RE_PLASMA_NUCLEAR.search(fields_str) or RE_PLASMA_NUCLEAR.search(type_str))
        is_fellowship = bool(RE_FELLOWSHIP.search(title_str) or RE_FELLOWSHIP.search(type_str))
        is_msc = bool(RE_MSC.search(title_str) or RE_MSC.search(type_str))

        base_score = int(score) if isinstance(score, (int, float)) else 60

        # Tier 1: Undergraduate Summer Internships & Research Fellowships (Immediate priority for 2027 grad)
        if is_internship:
            mazen_category = "Green"
            tier = 1
            mazen_score = max(base_score, 95)
            mazen_note = f"[TOP FIT: UNDERGRAD RESEARCH INTERNSHIP] Prime pre-graduation research program open to current students. {rationale_str}".strip()

        # Tier 2: Plasma, Fusion & Accelerator/Nuclear Physics Programs
        elif is_plasma_nuclear:
            mazen_category = "Green"
            tier = 2
            mazen_score = max(base_score, 92)
            mazen_note = f"[TOP SPECIALTY: PLASMA / ACCELERATOR] Aligns with Mazen's EAEA accelerator internship and EgyPlasma research defense. {rationale_str}".strip()

        # Tier 3: Research Fellowships
        elif is_fellowship and cat_str == "Green":
            mazen_category = "Green"
            tier = 3
            mazen_score = max(base_score, 88)
            mazen_note = f"[RESEARCH FELLOWSHIP] Prestigious international fellowship. {rationale_str}".strip()

        # Tier 4: Recurring 100% Fully Funded MSc & Italian DSU (2027 application cycle)
        elif is_msc and cat_str == "Green":
            mazen_category = "Green"
            tier = 4
            mazen_score = max(base_score, 82)
            mazen_note = f"[RECURRING MSc ROADMAP (2027 INTAKE)] 100% full-ride / DSU regional grant. Save requirements for next cycle. {rationale_str}".strip()

        # Tier 5: General Green Physics programs
        elif cat_str == "Green":
            mazen_category = "Green"
            tier = 5
            mazen_score = max(base_score, 78)
            mazen_note = f"[APPROVED PHYSICS FIT] Fully funded physics program matching academic background. {rationale_str}".strip()

        # Tier 6: Yellow backups & borderline fits
        else:
            mazen_category = "Yellow"
            tier = 6
            mazen_score = min(max(base_score, 55), 74)
            mazen_note = f"[BACKUP / REVIEW] Valid physics opportunity. Check English requirements and fee policies. {rationale_str}".strip()

        mazen_rows.append({
            "category": mazen_category,
            "tier": tier,
            "title": title_str,
            "type": type_str,
            "deadline": deadline,
            "funding": funding_str,
            "fields": fields_str,
            "link": link,
            "action": action,
            "institution": inst,
            "date": date,
            "source": source,
            "score": mazen_score,
            "rationale": mazen_note,
            "deep": deep
        })

    # Sort strictly by Tier (Internships first, Plasma second, MSc third), then by score descending
    mazen_rows.sort(key=lambda r: (r["tier"], -int(r["score"] if isinstance(r["score"], (int, float)) else 0)))

    print(f"Total curated opportunities for Mazen: {len(mazen_rows)}")
    greens = sum(1 for r in mazen_rows if r["category"] == "Green")
    yellows = sum(1 for r in mazen_rows if r["category"] == "Yellow")
    print(f"  [Green - Top Fits & Internships]: {greens}")
    print(f"  [Yellow - Backups & Reviews]: {yellows}")

    # Build stylized Excel workbook
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "Mazen Opportunities 2026-2027"
    ws_out.views.sheetView[0].showGridLines = True

    # Styling definitions
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    green_font = Font(name="Calibri", size=10, color="006100", bold=True)
    
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    yellow_font = Font(name="Calibri", size=10, color="9C6500", bold=True)

    link_font = Font(name="Calibri", size=10, color="0563C1", underline="single")
    regular_font = Font(name="Calibri", size=10)
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # Write Header
    ws_out.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws_out.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws_out.row_dimensions[1].height = 28

    # Write Rows
    for row_idx, r in enumerate(mazen_rows, start=2):
        row_data = [
            r["category"],
            r["title"],
            r["type"],
            r["deadline"],
            r["funding"],
            r["fields"],
            r["link"],
            r["action"],
            r["institution"],
            r["date"],
            r["source"],
            r["score"],
            r["rationale"],
            r["deep"]
        ]
        ws_out.append(row_data)
        ws_out.row_dimensions[row_idx].height = 22

        # Format Category cell
        cat_cell = ws_out.cell(row=row_idx, column=1)
        if r["category"] == "Green":
            cat_cell.fill = green_fill
            cat_cell.font = green_font
        else:
            cat_cell.fill = yellow_fill
            cat_cell.font = yellow_font
        cat_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Format Link cell with hyperlink if URL
        link_cell = ws_out.cell(row=row_idx, column=7)
        if r["link"] and str(r["link"]).startswith("http"):
            link_cell.hyperlink = str(r["link"])
            link_cell.font = link_font
        
        # Border & standard font for other cells
        for c_idx in range(1, len(headers) + 1):
            cell = ws_out.cell(row=row_idx, column=c_idx)
            cell.border = thin_border
            if c_idx not in [1, 7]:
                cell.font = regular_font
                cell.alignment = Alignment(vertical="center")

    # Auto-adjust column widths
    col_widths = {
        1: 12,  # Category
        2: 36,  # Title
        3: 18,  # Type
        4: 16,  # Deadline
        5: 24,  # Funding
        6: 28,  # Fields
        7: 35,  # Link
        8: 24,  # Action Items
        9: 25,  # Institution
        10: 14, # Date
        11: 22, # Source
        12: 12, # Score
        13: 45, # Rationale
        14: 12  # Deep Checked
    }
    for col_idx, width in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws_out.column_dimensions[col_letter].width = width

    # Enable auto-filter and freeze top row
    ws_out.auto_filter.ref = ws_out.dimensions
    ws_out.freeze_panes = "A2"

    wb_out.save(OUTPUT_EXCEL)
    print(f"\n[SUCCESS] Mazen's personalized tracker generated at:\n  {OUTPUT_EXCEL}")
    print("=" * 60)

if __name__ == "__main__":
    build_mazen_tracker()
