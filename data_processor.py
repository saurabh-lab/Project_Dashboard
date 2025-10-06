import pandas as pd
import numpy as np
import re

def load_and_process_data(jira_file, defects_file, raid_file):
    """
    Loads raw CSV data, processes it, and calculates key agile metrics.
    Ensures Sprints are sorted numerically, handling 'SPRINT-X' format,
    and output dataframes are correctly sorted for plotting.
    """
    try:
        df_jira = pd.read_csv(jira_file)
        df_defects = pd.read_csv(defects_file)
        df_raid = pd.read_csv(raid_file)
    except Exception as e:
        return {"error": f"Failed to load data: {e}"}

    # --- Data Cleaning and Pre-processing ---
    required_jira_cols = ['StoryPoints', 'Type', 'Status', 'SprintID', 'Assignee']
    if not all(col in df_jira.columns for col in required_jira_cols):
        missing_cols = [col for col in required_jira_cols if col not in df_jira.columns]
        return {"error": f"JIRA data is missing required columns: {', '.join(missing_cols)}."}
        
    df_jira['StoryPoints'] = df_jira['StoryPoints'].fillna(0).astype(int)
    
    df_jira['SprintNumeric'] = df_jira['SprintID'].apply(
        lambda x: int(re.search(r'\d+', str(x)).group()) if pd.notna(x) and re.search(r'\d+', str(x)) else np.nan
    )
    df_jira.dropna(subset=['SprintNumeric'], inplace=True)
    df_jira['SprintNumeric'] = df_jira['SprintNumeric'].astype(int)
    # The sort here applies to df_jira, but subsequent groupbys might lose this order if not careful.
    df_jira.sort_values(by='SprintNumeric', inplace=True, ignore_index=True) # Ensure initial JIRA sort and reset index
    
    df_jira_stories = df_jira[df_jira['Type'] == 'Story'] 
    df_jira_done = df_jira_stories[df_jira_stories['Status'] == 'Done']

    required_defects_cols = ['RaisedIn', 'Status', 'Phase']
    if not all(col in df_defects.columns for col in required_defects_cols):
        missing_cols = [col for col in required_defects_cols if col not in df_defects.columns]
        return {"error": f"Defects data is missing required columns: {', '.join(missing_cols)}."}
    df_defects['RaisedIn'] = df_defects['RaisedIn'].astype(str)

    required_raid_cols = ['Type', 'Status', 'Owner', 'Target Date']
    if not all(col in df_raid.columns for col in required_raid_cols):
        missing_cols = [col for col in required_raid_cols if col not in df_raid.columns]
        return {"error": f"RAID data is missing required columns: {', '.join(missing_cols)}."}
    
    df_raid['DueDate'] = pd.to_datetime(df_raid['Target Date'], errors='coerce')

    # --- Get Unique Sorted Sprints ---
    unique_sprints_df = df_jira[['SprintID', 'SprintNumeric']].drop_duplicates().sort_values('SprintNumeric', ignore_index=True)
    unique_sprints_sorted = unique_sprints_df['SprintID'].tolist()
    # sprint_numeric_to_id_map is now only used in app.py, no longer needed here.


    # --- METRIC CALCULATION ---
    # 1. Velocity Trend (StoryPoints per SprintID)
    velocity_trend_data = []
    for sprint_id, sprint_numeric in unique_sprints_df.itertuples(index=False):
        completed_points = df_jira_done[df_jira_done['SprintID'] == sprint_id]['StoryPoints'].sum()
        velocity_trend_data.append({'SprintID': sprint_id, 'SprintNumeric': sprint_numeric, 'CompletedPoints': completed_points})
    velocity_trend_df = pd.DataFrame(velocity_trend_data)
    # --- IMPORTANT: Ensure final DF is sorted before converting ---
    velocity_trend_df.sort_values(by='SprintNumeric', inplace=True, ignore_index=True)


    # 2. Sprint Goal Completion (Committed Points vs. Completed Points) ---
    committed_data = []
    for sprint_id, sprint_numeric in unique_sprints_df.itertuples(index=False):
        committed_points = df_jira_stories[df_jira_stories['SprintID'] == sprint_id]['StoryPoints'].sum()
        committed_data.append({'SprintID': sprint_id, 'SprintNumeric': sprint_numeric, 'CommittedPoints': committed_points})
    committed_df = pd.DataFrame(committed_data)
    # --- IMPORTANT: Ensure final DF is sorted before converting ---
    committed_df.sort_values(by='SprintNumeric', inplace=True, ignore_index=True)
    
    completion_trend = pd.merge(committed_df, velocity_trend_df, on=['SprintID', 'SprintNumeric'], how='outer').fillna(0)
    # --- IMPORTANT: Ensure final DF is sorted after merge ---
    completion_trend.sort_values(by='SprintNumeric', inplace=True, ignore_index=True)
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

    for sprint_id, sprint_numeric in unique_sprints_df.itertuples(index=False):
        defect_count = df_defects[df_defects['RaisedIn'] == sprint_id].shape[0]
        defect_counts_data.append({'SprintID': sprint_id, 'SprintNumeric': sprint_numeric, 'DefectCount': defect_count})
        
        story_count = df_jira_stories[df_jira_stories['SprintID'] == sprint_id].shape[0]
        story_counts_data.append({'SprintID': sprint_id, 'SprintNumeric': sprint_numeric, 'StoryCount': story_count})

    defect_counts_df = pd.DataFrame(defect_counts_data)
    story_counts_df = pd.DataFrame(story_counts_data)
    
    density_data_df = pd.merge(defect_counts_df, story_counts_df, on=['SprintID', 'SprintNumeric'], how='outer').fillna(0)
    # --- IMPORTANT: Ensure final DF is sorted after merge ---
    density_data_df.sort_values(by='SprintNumeric', inplace=True, ignore_index=True)

    density_data_df.rename(columns={'SprintID': 'RaisedIn'}, inplace=True)
    density_data_df['DefectDensity'] = density_data_df['DefectCount'] / density_data_df['StoryCount'].replace(0, np.nan)
    density_data_for_return = density_data_df[['RaisedIn', 'SprintNumeric', 'DefectCount', 'StoryCount']].to_dict('records')
    
    
    # 5. Defect Stage Distribution (Open Defects by Phase) ---
    stage_data_df = df_defects[df_defects['Status'] == 'Open'].groupby('Phase').size().reset_index(name='Count')
    stage_data_for_return = stage_data_df.to_dict('records')


    # 6. RAID Summary (Open Items) ---
    open_raid_detailed_df = df_raid[df_raid['Status'] == 'Open'].copy() 
    
    def get_raid_status_display(row):
        if 'Open' in str(row['Status']) or 'New' in str(row['Status']): 
            return '⚠️ Open'
        elif pd.notna(row['DueDate']) and row['DueDate'] < pd.to_datetime('today'):
            return '🚨 Overdue'
        return '🟢 Active'

    open_raid_detailed_df['StatusDisplay'] = open_raid_detailed_df.apply(get_raid_status_display, axis=1)

    raid_grouped_status = open_raid_detailed_df.groupby('Type').agg(
        Total=('Type', 'count'), 
        Open=('StatusDisplay', lambda x: x[x == '⚠️ Open'].count()), 
        Overdue=('StatusDisplay', lambda x: x[x == '🚨 Overdue'].count()) 
    ).reset_index()

    raid_grouped_status['Status'] = '✅'
    raid_grouped_status.loc[raid_grouped_status['Overdue'] > 0, 'Status'] = '🚨'
    raid_grouped_status.loc[raid_grouped_status['Open'] > 0, 'Status'] = '⚠️'
    
    raid_data_for_return = raid_grouped_status[['Type', 'Status', 'Total', 'Open']].to_dict('records')
    
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