import pandas as pd
import numpy as np

def load_and_process_data(jira_file, defects_file, raid_file):
    """
    Loads CSV files and calculates all 6 required agile metrics based on the
    new column names (SprintID, Phase, etc.).
    Returns a dictionary of structured data for charting and AI analysis.
    """
    try:
        # Load dataframes
        df_jira = pd.read_csv(jira_file)
        df_defects = pd.read_csv(defects_file)
        df_raid = pd.read_csv(raid_file)
    except Exception as e:
        return {"error": f"Failed to load data: {e}"}

    # Clean and filter JIRA data
    df_jira['StoryPoints'] = df_jira['StoryPoints'].fillna(0).astype(int)
    # Filter only Stories for capacity and velocity
    df_jira_stories = df_jira[df_jira['Type'] == 'Story'] 
    df_jira_done = df_jira_stories[df_jira_stories['Status'] == 'Done']

    # --- 1. Velocity Trend (StoryPoints per SprintID) ---
    velocity_trend = df_jira_done.groupby('SprintID')['StoryPoints'].sum().reset_index(name='CompletedPoints')
    
    # --- 2. Sprint Goal Completion (Committed Points vs. Completed Points) ---
    # We must calculate Committed points based on all points assigned to a sprint, regardless of status.
    committed_data = df_jira_stories.groupby('SprintID')['StoryPoints'].sum().reset_index(name='CommittedPoints')
    
    # Merge completed points (velocity) with committed points
    completion_trend = pd.merge(committed_data, velocity_trend, on='SprintID', how='outer').fillna(0)
    completion_data = completion_trend.to_dict('list') # Used for both 1 & 2

    # --- 3. Capacity Utilization (Last 5 Sprints) ---
    latest_sprints = sorted(df_jira['SprintID'].unique(), reverse=True)[:5]
    df_recent_jira = df_jira[df_jira['SprintID'].isin(latest_sprints)]
    
    capacity_data = df_recent_jira.groupby('Assignee')['StoryPoints'].sum().reset_index(name='Load')
    # Assumed capacity is a hardcoded benchmark for the LLM context
    capacity_data['AssumedCapacity'] = 40 
    capacity_data = capacity_data.sort_values(by='Load', ascending=False).to_dict('list')

    # --- 4. Defect Density (Defects per sprint vs stories) ---
    # Count defects raised in each sprint
    defect_counts = df_defects.groupby('RaisedIn').size().reset_index(name='DefectCount')
    # Count stories assigned to each sprint
    story_counts = df_jira_stories.groupby('SprintID').size().reset_index(name='StoryCount')
    
    density_data = pd.merge(defect_counts, story_counts, 
                            left_on='RaisedIn', right_on='SprintID', how='outer').fillna(0)
    density_data['DefectDensity'] = density_data['DefectCount'] / density_data['StoryCount'].replace(0, np.nan)
    density_data = density_data[['RaisedIn', 'DefectCount', 'StoryCount']].to_dict('list')
    
    # --- 5. Defect Stage Distribution (Open Defects by Phase) ---
    stage_data = df_defects[df_defects['Status'] == 'Open'].groupby('Phase').size().reset_index(name='Count')
    stage_data = stage_data.to_dict('list')

    # --- 6. RAID Summary (Open Items) ---
    raid_summary = df_raid.groupby('Type').size().reset_index(name='Total')
    raid_open = df_raid[df_raid['Status'] == 'Open'].groupby('Type').size().reset_index(name='Open')
    
    raid_data = pd.merge(raid_summary, raid_open, on='Type', how='left').fillna(0)
    raid_data['Open'] = raid_data['Open'].astype(int)
    raid_data['Status'] = np.where(raid_data['Open'] > 0, '⚠️', '✅') 
    raid_data = raid_data.to_dict('list')
    
    # Return all processed data
    return {
        "velocity": completion_data,
        "completion": completion_data,
        "capacity": capacity_data,
        "density": density_data,
        "stage": stage_data,
        "raid": raid_data,
        "raw_jira_summary": df_jira.describe(include='all').to_string(), 
        "raw_defects_summary": df_defects[df_defects['Status'] == 'Open'].to_string() 
    }
