import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

def export_to_excel(opportunities, output_path):
    if not opportunities:
        print("No opportunities to export.")
        return

    # Convert list of dicts to flat rows
    data = []
    import datetime
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    for item in opportunities:
        if not item or "opp" not in item: continue
        
        opp = item["opp"]
        msg = item["msg"]
        
        scraped_date = msg.get("scraped_date", today_str)
        # Handle source field
        source = msg.get("source", msg.get("sender", "World Scholarship Opportunities(WhatsApp)"))
        
        row = {
            "Category": opp.category,
            "Title": opp.opportunity_title,
            "Type": opp.opportunity_type,
            "Deadline": opp.deadline,
            "Funding": opp.funding_status,
            "Fields": ", ".join(opp.fields_of_study),
            "Link": opp.application_link,
            "Action Items": opp.action_items,
            "Institution/Country": opp.institution_or_country,
            "Scraped Date": scraped_date,
            "Web Source": source,
            "Match Score": opp.match_score,
            "AI Rationale": opp.reasoning
        }
        data.append(row)

    df = pd.DataFrame(data)
    
    backup_path = os.path.join(os.path.dirname(output_path), "data", "pending_exports.csv")
    if os.path.exists(backup_path):
        print("Found pending exports from a previous run. Merging them in...")
        backup_df = pd.read_csv(backup_path)
        df = pd.concat([backup_df, df], ignore_index=True)
    
    # Define desired column order
    column_order = [
        "Category", "Title", "Type", "Deadline", "Funding", 
        "Fields", "Link", "Action Items", "Institution/Country", 
        "Scraped Date", "Web Source", "Match Score", "AI Rationale", "Deep Checked"
    ]
    
    import time
    lock_file = output_path + ".lock"
    
    # Wait for lock to be released (max 30 seconds)
    timeout = 30
    start_time = time.time()
    while os.path.exists(lock_file):
        if time.time() - start_time > timeout:
            print("Timeout waiting for Excel lock file. Breaking lock.")
            try:
                os.remove(lock_file)
            except: pass
            break
        time.sleep(1)
        
    # Acquire lock
    try:
        with open(lock_file, 'w') as f:
            f.write("locked")
    except: pass
    
    try:
        if os.path.exists(output_path):
            existing_df = pd.read_excel(output_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            # Drop duplicates based on Title and Link
            combined_df.drop_duplicates(subset=['Title', 'Link'], keep='first', inplace=True)
            df_to_save = combined_df
        else:
            df_to_save = df
            
        # Reorder columns to enforce the new layout (fill missing with NaN)
        for col in column_order:
            if col not in df_to_save.columns:
                df_to_save[col] = ""
                
        # Ensure columns match our exact list
        extra_cols = [c for c in df_to_save.columns if c not in column_order]
        df_to_save = df_to_save[column_order + extra_cols]
            
        # Make sure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
        # Save to excel with a basic retry mechanism if the user has it open
        max_retries = 3
        success = False
        for attempt in range(max_retries):
            try:
                df_to_save.to_excel(output_path, index=False)
                apply_excel_formatting(output_path)
                success = True
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    print(f"Excel file is open in another program. Retrying in 2 seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(2)
                else:
                    print(f"CRITICAL: Could not write to {output_path} because it is open in Excel.")
                    print(f"Saving data to backup queue: {backup_path}")
                    df.to_csv(backup_path, index=False)
                    return # Exit gracefully so scraper can commit hashes to DB
                    
        if success and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                print("Cleared pending backup queue.")
            except: pass
            
    finally:
        # Release lock
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except: pass

def apply_excel_formatting(file_path):
    wb = load_workbook(file_path)
    ws = wb.active

    # Define colors
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    score_col_idx = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=col).value == "Match Score":
            score_col_idx = col
            break

    if score_col_idx:
        for row in range(2, ws.max_row + 1):
            score_val = ws.cell(row=row, column=score_col_idx).value
            try:
                score = int(score_val)
                fill = None
                if score >= 75:
                    fill = green_fill
                elif score >= 50:
                    fill = yellow_fill
                else:
                    fill = red_fill
                
                # Apply fill to the entire row
                for col in range(1, ws.max_column + 1):
                    ws.cell(row=row, column=col).fill = fill
            except (ValueError, TypeError):
                continue
    
    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        if adjusted_width > 50:
            adjusted_width = 50 # Cap width
        ws.column_dimensions[column].width = adjusted_width

    # Make links clickable
    link_col_idx = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=col).value == "Link":
            link_col_idx = col
            break
            
    if link_col_idx:
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=link_col_idx)
            if cell.value and isinstance(cell.value, str) and cell.value.startswith('http'):
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"

    wb.save(file_path)
