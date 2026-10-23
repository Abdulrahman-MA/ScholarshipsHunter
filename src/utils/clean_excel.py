import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core import exporter

def run():
    print("==================================================")
    print(" Excel Cleaner Utility ")
    print("==================================================")
    
    excel_path = config.OUTPUT_EXCEL_FILE
    
    if not os.path.exists(excel_path):
        print(f"Error: Could not find {excel_path}")
        return
        
    print(f"Loading {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Failed to read Excel file. Is it open? Error: {e}")
        return
        
    initial_count = len(df)
    
    # Filter out rows where Match Score < 50 (which correspond to the red rows)
    df['Match Score Numeric'] = pd.to_numeric(df['Match Score'], errors='coerce')
    
    # Check if the user manually typed "DELETE" in Category or Action Items or Title
    df['Category_Str'] = df['Category'].astype(str).str.upper()
    df['Action_Str'] = df['Action Items'].astype(str).str.upper()
    
    # We want to KEEP rows where:
    # 1. Match Score is >= 50 OR Match Score is NaN
    # AND
    # 2. They did not type "DELETE" in the Category or Action Items
    keep_mask = (
        ((df['Match Score Numeric'] >= 50) | df['Match Score Numeric'].isna()) &
        (~df['Category_Str'].str.contains("DELETE", na=False)) &
        (~df['Action_Str'].str.contains("DELETE", na=False))
    )
    
    # Exception: If they explicitly changed the score to 0 or under 50, it drops it (because keep_mask is false)
    
    filtered_df = df[keep_mask].copy()
    
    # Drop the temporary columns
    filtered_df.drop(columns=['Match Score Numeric', 'Category_Str', 'Action_Str'], inplace=True)
    
    final_count = len(filtered_df)
    removed_count = initial_count - final_count
    
    if removed_count == 0:
        print("No low-match (red) scholarships found to clean up! Your sheet is already pristine.")
        return
        
    print(f"Found {removed_count} unmatching/red scholarships (Match Score < 50).")
    
    while True:
        choice = input(f"Are you sure you want to delete these {removed_count} rows? (y/n): ").lower().strip()
        if choice in ['y', 'yes']:
            break
        elif choice in ['n', 'no']:
            print("Operation cancelled. No changes made.")
            return
            
    print("Deleting rows and saving Excel file...")
    
    try:
        filtered_df.to_excel(excel_path, index=False)
        exporter.apply_excel_formatting(excel_path)
        print(f"✅ Successfully cleaned! Excel file now has {final_count} high-quality scholarships.")
    except PermissionError:
        print("\nCRITICAL ERROR: The Excel file is open!")
        print("Please close Microsoft Excel and run this tool again.")
    except Exception as e:
        print(f"Failed to save Excel file: {e}")
        
    input("\nPress ENTER to return to menu...")

if __name__ == "__main__":
    run()
