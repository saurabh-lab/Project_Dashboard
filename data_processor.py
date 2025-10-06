import pandas as pd
import numpy as np
import re

def load_and_process_data(jira_file, defects_file, raid_file):
    """
    Loads raw CSV data, processes it, and calculates key agile metrics.
    Ensures Sprints are sorted numerically, handling 'SPRINT-X' format.
    Correctly maps column names from JIRA, Defects, and RAID files.
    """
    try:
        # Load dataframes
        df_jira = pd.read_csv(jira_file)
        df_defects = pd.read_csv(defects_file)
        df_raid = pd.read_csv(raid_file)
    except Exception as e:
        return {"error": f"Failed to load data: {e}"}

    # --- Data Cleaning and Pre-processing ---

    # JIRA Data
    required_jira_cols = ['StoryPoints', 'Type', 'Status', 'SprintID', 'Assignee']
    if not all(col in df_jira.columns for col in required_jira_cols):
        missing_cols = [col for col in required_jira_cols if col not in df_jira.columns]
        return {"error": f"JIRA data is missing required columns: {', '.join(missing_cols)}."}
        
    df_jira['StoryPoints'] = df_jira['StoryPoints'].fillna(0).astype(int)
    
    # Extract numeric part of SprintID for sorting ('SPRINT-1' -> 1)
    df_jira['SprintNumeric'] = df_jira['SprintID'].apply(
        lambda x: int(re.search(r'\d+', str(x)).group()) if pd.notna(x) and re.search(r'\d+', str(x)) else np.nan
    )
    df_jira.dropna(subset=['SprintNumeric'], inplace=True)
    df_jira['SprintNumeric'] = df_jira['SprintNumeric'].astype(int)
    df_jira.sort_values(by='SprintNumeric', inplace=True) # Sort JIRA data by sprint number
    
    df_jira_stories = df_jira[df_jira['Type'] == 'Story'] 
    df_jira_done = df_jira_stories[df_jira_stories['Status'] == 'Done']

    # Defects Data
    required_defects_cols = ['RaisedIn', 'Status', 'Phase']
    if not all(col in df_defects.columns for col in required_defects_cols):
        missing_cols = [col for col in required_defects_cols if col not in df_defects.columns]
        return {"error": f"Defects data is missing required columns: {', '.join(missing_cols)}."}
    # Ensure 'RaisedIn' is consistent with 'SprintID' format in JIRA
    df_defects['RaisedIn'] = df_defects['RaisedIn'].astype(str)

    # RAID Data
    required_raid_cols = ['Type', 'Status', 'Owner', 'Target Date'] # <--- CORRECTED: 'Target Date'
    if not all(col in df_raid.columns for col in required_raid_cols):
        missing_cols = [col for col in required_raid_cols if col not in df_raid.columns]
        return {"error": f"RAID data is missing required columns: {', '.join(missing_cols)}."}
    
    # Corrected: Use 'Target Date' and then rename it to 'DueDate' internally for consistent code
    df_raid['DueDate'] = pd.to_datetime(df_raid['Target Date'], errors='coerce') # <--- CORRECTED
    # Now, `df_raid` has a 'DueDate' column derived from 'Target Date'


    # --- Get Unique Sorted Sprints ---
    unique_sprints_sorted = sorted(
        df_jira['SprintID'].unique(), 
        key=lambda x: int(re.search(r'\d+', str(x)).group()) if pd.notna(x) and re.search(r'\d+', str(x)) else 0
    )


    # --- METRIC CALCULATION ---

    # 1. Velocity Trend (StoryPoints per SprintID)
    velocity_trend_data = []
    for sprint in unique_sprints_sorted:
        completed_points = df_jira_done[df_jira_done['SprintID'] == sprint]['StoryPoints'].sum()
        velocity_trend_data.append({'SprintID': sprint, 'CompletedPoints': completed_points})
    velocity_trend_df = pd.DataFrame(velocity_trend_data)
    
    # 2. Sprint Goal Completion (Committed Points vs. Completed Points) ---
    committed_data = []
    for sprint in unique_sprints_sorted:
        committed_points = df_jira_stories[df_jira_stories['SprintID'] == sprint]['StoryPoints'].sum()
        committed_data.append({'SprintID': sprint, 'CommittedPoints': committed_points})
    committed_df = pd.DataFrame(committed_data)
    
    completion_trend = pd.merge(committed_df, velocity_trend_df, on='SprintID', how='outer').fillna(0)
    completion_data_for_return = completion_trend.to_dict('records') 


    # 3. Capacity Utilization (Last 5 Sprints) ---
    latest_sprints_numeric = sorted(df_jira['SprintNumeric'].unique(), reverse=True)[:5]
    latest_sprint_names = df_jira[df_jira['SprintNumeric'].isin(latest_sprints_numeric)]['SprintID'].unique()
    
    df_recent_jira = df_jira[df_jira['SprintID'].isin(latest_sprint_names)]
    
    capacity_data_df = df_recent_jira.groupby('Assignee')['StoryPoints'].sum().reset_index(name='Load')
    capacity_data_df['AssumedCapacity'] = 40 
    capacity_data_df = capacity_data_df.sort_values(by='Load', ascending=False)
    capacity_data_for_return = capacity_data_df.to_dict('records')


    # 4. Defect Density (Defects per sprint vs stories) ---
    defect_counts_data = []
    story_counts_data = []
    for sprint in unique_sprints_sorted:
        defect_count = df_defects[df_defects['RaisedIn'] == sprint].shape[0]
        defect_counts_data.append({'SprintID': sprint, 'DefectCount': defect_count})
        
        story_count = df_jira_stories[df_jira_stories['SprintID'] == sprint].shape[0]
        story_counts_data.append({'SprintID': sprint, 'StoryCount': story_count})

    defect_counts_df = pd.DataFrame(defect_counts_data)
    story_counts_df = pd.DataFrame(story_counts_data)
    
    density_data_df = pd.merge(defect_counts_df, story_counts_df, 
                            on='SprintID', how='outer').fillna(0)
    
    density_data_df.rename(columns={'SprintID': 'RaisedIn'}, inplace=True)
    density_data_df['DefectDensity'] = density_data_df['DefectCount'] / density_data_df['StoryCount'].replace(0, np.nan)
    density_data_for_return = density_data_df[['RaisedIn', 'DefectCount', 'StoryCount']].to_dict('records')
    
    
    # 5. Defect Stage Distribution (Open Defects by Phase) ---
    stage_data_df = df_defects[df_defects['Status'] == 'Open'].groupby('Phase').size().reset_index(name='Count')
    stage_data_for_return = stage_data_df.to_dict('records')


    # 6. RAID Summary (Open Items) ---
    raid_summary_df = df_raid.groupby('Type').size().reset_index(name='Total')
    raid_open_df = df_raid[df_raid['Status'] == 'Open'].groupby('Type').size().reset_index(name='Open')
    
    raid_data_df = pd.merge(raid_summary_df, raid_open_df, on='Type', how='left').fillna(0)
    raid_data_df['Open'] = raid_data_df['Open'].astype(int)
    
    # Corrected: Use the internally created 'DueDate' for logic, but 'Target Date' from original file
    # The get_raid_status_display function needs the 'DueDate' column that we created
    # on the df_raid dataframe itself after reading 'Target Date'.
    
    # Custom status mapping for display with emojis
    def get_raid_status_display(row):
        if 'Open' in str(row['Status']) or 'New' in str(row['Status']): # Ensure string comparison
            return '⚠️ Open'
        # Use the 'DueDate' column we just created from 'Target Date'
        elif pd.notna(row['DueDate']) and row['DueDate'] < pd.to_datetime('today'):
            return '🚨 Overdue'
        return '🟢 Active' # Default or other active status

    # Ensure 'DueDate' exists before applying the function (it should after line ~90)
    # The apply function needs access to 'Status' and 'DueDate' from the `raid_data_df`
    # which is the merged df containing 'Type', 'Total', 'Open', 'Status' (from merge).
    # We need the original 'Status' from df_raid and the 'DueDate' we made.

    # Re-evaluating RAID processing to cleanly apply status logic
    # Start with the filtered open_raid_df that already has 'DueDate'
    open_raid_detailed_df = df_raid[df_raid['Status'] == 'Open'].copy() # Use a copy to avoid warnings
    open_raid_detailed_df['StatusDisplay'] = open_raid_detailed_df.apply(get_raid_status_display, axis=1)

    # Now group by Type and summarize status
    raid_grouped_status = open_raid_detailed_df.groupby('Type').agg(
        Total=('Type', 'count'), # Count total items of each type
        Open=('StatusDisplay', lambda x: x[x == '⚠️ Open'].count()), # Count how many are '⚠️ Open'
        Overdue=('StatusDisplay', lambda x: x[x == '🚨 Overdue'].count()) # Count how many are '🚨 Overdue'
    ).reset_index()

    # Determine overall status for each RAID type based on the counts
    raid_grouped_status['Status'] = '✅' # Default to good
    raid_grouped_status.loc[raid_grouped_status['Overdue'] > 0, 'Status'] = '🚨' # Overdue takes precedence
    raid_grouped_status.loc[raid_grouped_status['Open'] > 0, 'Status'] = '⚠️' # Then open
    
    # We only need 'Type', 'Status' (emoji), 'Total', 'Open' (count of actual open) for the dashboard summary
    raid_data_for_return = raid_grouped_status[['Type', 'Status', 'Total', 'Open']].to_dict('records')
    
    # Return all processed data
    return {
        "velocity": completion_data_for_return, 
        "completion": completion_data_for_return, 
        "capacity": capacity_data_for_return, 
        "density": density_data_for_return, 
        "stage": stage_data_for_return, 
        "raid": raid_data_for_return, 
        "raw_jira_summary": df_jira.describe(include='all').to_string(), 
        "raw_defects_summary": df_defects[df_defects['Status'] == 'Open'].to_string() 
    }