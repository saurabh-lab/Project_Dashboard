import pandas as pd
import numpy as np
import os
from datetime import date, timedelta

def generate_mock_data():
    """Generates and saves mock JIRA, Defects, and RAID data as CSV files 
    based on the requested schema and row counts.
    """
    
    start_date = date(2024, 1, 1)
    num_sprints = 10
    
    assignees = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Fiona']
    priorities = ['Highest', 'High', 'Medium', 'Low', 'Lowest']
    story_points = [1, 2, 3, 5, 8, 13]

    # --- 1. JIRA Issues Data Generation (jira_issues.csv) ---
    jira_records = []
    num_jira_rows = 180 
    
    for i in range(1, num_jira_rows + 1):
        sprint_id = f'SPRINT-{np.random.randint(1, num_sprints + 1)}'
        
        issue_type = np.random.choice(['Story', 'Bug', 'Task'], p=[0.6, 0.25, 0.15])
        
        if issue_type == 'Story':
            sp = np.random.choice(story_points, p=[0.1, 0.2, 0.3, 0.2, 0.15, 0.05])
        else:
            sp = 0

        status = np.random.choice(['Done', 'In Progress', 'To Do', 'Blocked'], p=[0.55, 0.25, 0.15, 0.05])
        
        created_date = start_date + timedelta(days=np.random.randint(0, 150))
        closed_date = ''
        if status == 'Done':
            closed_date = created_date + timedelta(days=np.random.randint(7, 45))

        jira_records.append({
            'IssueID': f'PROG-{1000 + i}',
            'Type': issue_type,
            'SprintID': sprint_id,
            'Status': status,
            'Assignee': np.random.choice(assignees),
            'StoryPoints': sp,
            'CreatedDate': created_date.strftime('%Y-%m-%d'),
            'ClosedDate': closed_date.strftime('%Y-%m-%d') if closed_date else '',
            'Priority': np.random.choice(priorities)
        })

    df_jira = pd.DataFrame(jira_records)
    df_jira.to_csv('jira_issues.csv', index=False)

    # --- 2. RAID Log Data Generation (raid_log.csv) ---
    raid_types = ['Risk', 'Assumption', 'Issue', 'Dependency']
    raid_statuses = ['Open', 'Closed', 'Mitigated']
    impacts_probs = ['High', 'Medium', 'Low']
    num_raid_rows = 55
    
    raid_records = []
    for i in range(1, num_raid_rows + 1):
        item_type = np.random.choice(raid_types, p=[0.35, 0.15, 0.3, 0.2])
        status = np.random.choice(raid_statuses, p=[0.6, 0.2, 0.2])
        impact = np.random.choice(impacts_probs)
        probability = np.random.choice(impacts_probs)
        
        target_date = start_date + timedelta(days=np.random.randint(60, 200))
        
        raid_records.append({
            'ID': f'RAID-{i}',
            'Type': item_type,
            'Description': f'{item_type} concerning external API integration or scope creep.',
            'Owner': np.random.choice(assignees + ['Sponsor', 'Vendor']),
            'Status': status,
            'Impact': impact,
            'Probability': probability,
            'Mitigation': f'Detailed plan to address {item_type.lower()}',
            'TargetDate': target_date.strftime('%Y-%m-%d')
        })

    df_raid = pd.DataFrame(raid_records)
    df_raid.to_csv('raid_log.csv', index=False)
    
    # --- 3. Defects Data Generation (defects.csv) ---
    defect_phases = ['SIT', 'UAT', 'Prod']
    defect_severities = ['S1-Critical', 'S2-High', 'S3-Medium', 'S4-Low']
    num_defect_rows = 130
    
    defect_records = []
    for i in range(1, num_defect_rows + 1):
        phase = np.random.choice(defect_phases, p=[0.45, 0.35, 0.2])
        status = np.random.choice(['Open', 'Closed'], p=[0.4, 0.6])
        
        if phase == 'Prod':
            # Higher severity in production
            severity = np.random.choice(defect_severities, p=[0.2, 0.4, 0.3, 0.1])
        else:
            severity = np.random.choice(defect_severities, p=[0.05, 0.25, 0.4, 0.3])

        date_raised = start_date + timedelta(days=np.random.randint(30, 180))
        date_closed = ''
        if status == 'Closed':
            date_closed = date_raised + timedelta(days=np.random.randint(1, 30))

        defect_records.append({
            'DefectID': f'DEF-{i}',
            'Severity': severity,
            'Priority': np.random.choice(priorities),
            'Status': status,
            'RaisedIn': f'SPRINT-{np.random.randint(1, num_sprints + 1)}',
            'Phase': phase,
            'Owner': np.random.choice(assignees),
            'DateRaised': date_raised.strftime('%Y-%m-%d'),
            'DateClosed': date_closed.strftime('%Y-%m-%d') if date_closed else ''
        })

    df_defects = pd.DataFrame(defect_records)
    df_defects.to_csv('defects.csv', index=False)
    
    return [
        'jira_issues.csv', 
        'raid_log.csv', 
        'defects.csv'
    ]

if __name__ == '__main__':
    files = generate_mock_data()
    print(f"Mock data successfully generated: {files}")
