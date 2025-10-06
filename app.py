import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from data_processor import load_and_process_data
from ai_engine import get_ai_summary, get_executive_summary
from report_generator import generate_ppt
from mock_data import generate_mock_data
from datetime import date 

import base64 
import re 

# --- 1. CONFIGURATION AND INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="AI Program Health Dashboard")

# Initialize session state variables if they don't exist
if 'data_ready' not in st.session_state:
    st.session_state['data_ready'] = False
if 'metrics_data' not in st.session_state:
    st.session_state['metrics_data'] = {}
if 'gemini_api_key' not in st.session_state:
    st.session_state['gemini_api_key'] = ''
if 'ai_summaries' not in st.session_state:
    st.session_state['ai_summaries'] = {}

# Ensure mock data files exist for quick testing
@st.cache_resource
def setup_mock_files():
    """Generates mock files if they don't exist and provides download links."""
    mock_file_names = ['jira_issues.csv', 'defects.csv', 'raid_log.csv']
    if not all(os.path.exists(f) for f in mock_file_names):
        return generate_mock_data()
    return mock_file_names 

mock_files = setup_mock_files()

# --- 2. API KEY INPUT & MOCK DATA DOWNLOAD ---

st.title("🤖 AI-Powered Program Health Dashboard")
st.markdown("Upload your JIRA, Defects, and RAID logs to generate analysis.")

# --- API Key Input ---
with st.sidebar:
    st.header("🔑 Gemini API Key")
    st.session_state['gemini_api_key'] = st.text_input(
        "Enter your Gemini API Key:", 
        type="password",
        value=st.session_state['gemini_api_key'],
        key='key_input',
        help="The API key is required to run the AI analysis features."
    )
    if not st.session_state['gemini_api_key']:
        st.warning("⚠️ Please enter your API key to enable AI analysis.")
    st.divider()
    
    st.header("📥 Mock Data Files")
    st.markdown("Download these to test the dashboard immediately:")
    
    col1, col2, col3 = st.columns(3)
    
    jira_mock_path = 'jira_issues.csv'
    defects_mock_path = 'defects.csv'
    raid_mock_path = 'raid_log.csv'

    # Download buttons for mock data
    # (No changes needed here, as these are just file downloads)
    if os.path.exists(jira_mock_path):
        with open(jira_mock_path, 'rb') as f:
            col1.download_button("JIRA Issues", f, "jira_issues.csv")
    else:
        col1.info("JIRA mock file not found.")

    if os.path.exists(defects_mock_path):
        with open(defects_mock_path, 'rb') as f:
            col2.download_button("Defects Log", f, "defects.csv")
    else:
        col2.info("Defects mock file not found.")

    if os.path.exists(raid_mock_path):
        with open(raid_mock_path, 'rb') as f:
            col3.download_button("RAID Log", f, "raid_log.csv")
    else:
        col3.info("RAID mock file not found.")


# Uploaders for the main app
upload_col1, upload_col2, upload_col3 = st.columns(3)
jira_file = upload_col1.file_uploader("Upload JIRA Issues CSV", type=['csv'])
defects_file = upload_col2.file_uploader("Upload Defects Log CSV", type=['csv'])
raid_file = upload_col3.file_uploader("Upload RAID Log CSV", type=['csv'])

# --- 3. DATA PROCESSING ---

# Check if data is already loaded in session state (from a previous run)
if not st.session_state['data_ready']: # Only attempt to load if not already loaded
    if jira_file and defects_file and raid_file:
        with st.spinner("Processing uploaded data with Pandas..."):
            temp_metrics_data = load_and_process_data(jira_file, defects_file, raid_file)
        
        if "error" in temp_metrics_data:
            st.error(f"Data Processing Error: {temp_metrics_data['error']}")
            st.session_state['data_ready'] = False # Ensure state is explicitly false on error
        else:
            st.session_state['metrics_data'] = temp_metrics_data
            st.session_state['data_ready'] = True
    elif st.button("📊 Use Mock Data (Default)") and all(os.path.exists(f) for f in mock_files):
        with st.spinner("Processing mock data with Pandas..."):
            temp_metrics_data = load_and_process_data('jira_issues.csv', 'defects.csv', 'raid_log.csv') 
        if "error" in temp_metrics_data:
            st.error(f"Mock Data Processing Error: {temp_metrics_data['error']}")
            st.session_state['data_ready'] = False # Ensure state is explicitly false on error
        else:
            st.session_state['metrics_data'] = temp_metrics_data
            st.session_state['data_ready'] = True
    
# Now use st.session_state['data_ready'] and st.session_state['metrics_data']
# everywhere else in the script
metrics_data = st.session_state['metrics_data'] # Alias for convenience

# --- 4. AI ANALYSIS AND REPORTING ---

if st.session_state['data_ready']: # Use session state for data_ready
    st.divider()
    
    # Check if AI analysis has already been performed in this session
    ai_analysis_already_run = st.session_state['ai_summaries'].get('executive_summary', '') not in ["", "Click 'Trigger Full AI Analysis' to generate the leadership synthesis."]

    if st.button("🧠 Trigger Full AI Analysis & Report Generation", type="primary", 
                 disabled=not st.session_state['gemini_api_key']): # Button is only enabled if API key is present
        api_key = st.session_state['gemini_api_key']
        st.session_state['ai_summaries'] = {} # Reset summaries before re-running
        
        metric_keys = [
            ("velocity", "Velocity Trend"), 
            ("completion", "Sprint Goal Completion"), 
            ("capacity", "Capacity Utilization"), 
            ("density", "Defect Density"), 
            ("stage", "Defect Stage Distribution"), 
            ("raid", "RAID Summary")
        ]
        
        with st.spinner("⏳ Running 6 Metric Summaries (AI calls in progress)..."):
            for key, name in metric_keys:
                data_summary = str(metrics_data[key])
                summary = get_ai_summary(api_key, name, data_summary) 
                st.session_state['ai_summaries'][key] = summary
                
        with st.spinner("🧠 Running Executive Synthesis (Final AI call)..."):
            exec_summary = get_executive_summary(api_key, metrics_data) 
            st.session_state['ai_summaries']['executive_summary'] = exec_summary
            
        st.success("✅ All 7 AI Summaries complete!")

    # --- 5. EXECUTIVE SUMMARY CARD ---
    
    exec_summary_raw = st.session_state['ai_summaries'].get('executive_summary', 
                                                       "Click 'Trigger Full AI Analysis' to generate the leadership synthesis.")
    
    ai_analysis_complete = exec_summary_raw not in ["", "Click 'Trigger Full AI Analysis' to generate the leadership synthesis."]
    
    emoji = ''
    final_html_content = ''

    if ai_analysis_complete:
        emoji = exec_summary_raw[0]
        content_without_emoji = exec_summary_raw[1:].strip()
        
        html_content_parts = []
        
        sections = content_without_emoji.split('##')
        for i, section in enumerate(sections):
            if not section.strip():
                continue
            
            lines = section.strip().split('\n')
            
            heading = lines[0].strip()
            if heading:
                html_content_parts.append(f"<h3>{heading.replace('**', '').strip()}</h3>") 
            
            if len(lines) > 1:
                html_content_parts.append("<ul>")
                for line in lines[1:]:
                    if line.strip().startswith('*'):
                        list_item_content = line.strip()[1:].strip()
                        list_item_content = list_item_content.replace('**', '') 
                        html_content_parts.append(f"<li>{list_item_content}</li>")
                    elif line.strip(): 
                        html_content_parts.append(f"<p>{line.strip()}</p>")
                html_content_parts.append("</ul>")
                
        final_html_content = "".join(html_content_parts)
    else:
        final_html_content = f"<p>{exec_summary_raw}</p>" 

    ppt_file_path = ""
    # Only try to generate PPT if AI analysis is complete AND metrics_data is available
    if ai_analysis_complete and st.session_state['data_ready']: 
        try:
            # Pass metrics_data from session state
            ppt_file_path = generate_ppt(st.session_state['metrics_data'], st.session_state['ai_summaries'])
        except Exception as e:
            st.error(f"Error generating PPT: {e}")
            # Do not set ai_analysis_complete to False, as AI analysis itself was successful.
            # Just indicate PPT generation failed.
            ppt_file_path = "" # Reset path if generation failed


    st.markdown(f"""
        <div id="executive_summary_card_top" style="padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); margin-bottom: 0rem; border-top: 8px solid #4f46e5; background-color: white;">
            <h2 style="font-size: 1.875rem; font-weight: 700; color: #4f46e5; margin-bottom: 1rem;">{emoji} Executive Summary</h2>
            <div style="color: #4b5563; font-size: 1.125rem; min-height: 60px; margin-bottom: 1rem;">
                {final_html_content}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown(f"""
            <div style="
                background-color: white; 
                border-bottom-left-radius: 0.75rem; 
                border-bottom-right-radius: 0.75rem; 
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); 
                padding: 0.5rem 1.5rem 1.5rem 1.5rem; 
                margin-top: -1.5rem; 
                margin-bottom: 2rem;
                text-align: right;">
            """, unsafe_allow_html=True)
            
        if ai_analysis_complete and ppt_file_path and os.path.exists(ppt_file_path): # Check ppt_file_path and existence
            try:
                with open(ppt_file_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Program Health PPT",
                        data=f.read(),
                        file_name=os.path.basename(ppt_file_path),
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        type="secondary",
                        help=f"Download the generated '{os.path.basename(ppt_file_path)}' report."
                    )
            except Exception as e:
                st.error(f"Error preparing PPT for download: {e}")
                st.markdown('<p style="color: #ef4444; font-size: 0.875rem;">Error creating download link.</p>', unsafe_allow_html=True)
        else:
            st.button(label="⬇️ Download Program Health PPT", disabled=True, 
                      help="Run the AI Analysis first to enable the report download.")
            st.markdown('<p style="color: #6b7280; font-size: 0.875rem; margin-top: 0.5rem;">Run the AI Analysis first to enable the report download.</p>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True) 

    # --- 6. METRICS CARDS AND CHARTS ---
    
    st.header("Programmatic Health Metrics")

    # --- PREPARE SPRINT ORDER FOR PLOTLY ---
    # Use metrics_data from session state
    temp_df_for_sprints = pd.DataFrame(st.session_state['metrics_data']['velocity']) 
    ordered_sprints_for_plotly = []
    if not temp_df_for_sprints.empty and 'SprintID' in temp_df_for_sprints.columns:
        all_sprint_ids = temp_df_for_sprints['SprintID'].unique()
        ordered_sprints_for_plotly = sorted(
            all_sprint_ids, 
            key=lambda x: int(re.search(r'\d+', str(x)).group()) if pd.notna(x) and re.search(r'\d+', str(x)) else 0
        )
    
    # 6.1 Velocity Trend & Completion (Two charts in one row)
    col1, col2 = st.columns(2)
    
    # Metric 1: Velocity Trend (Line Chart)
    with col1:
        st.subheader("1. Velocity Trend (Completed Story Points/Sprint)")
        df_vel = pd.DataFrame(st.session_state['metrics_data']['velocity'])
        fig_vel = px.line(df_vel, x='SprintID', y='CompletedPoints', 
                         title='Completed Story Points Over Time', markers=True,
                         color_discrete_sequence=['#1e40af'])
        fig_vel.add_trace(go.Scatter(x=df_vel['SprintID'], y=df_vel['CommittedPoints'],
                                    mode='lines', name='Committed Points', line=dict(dash='dot', color='#ef4444')))
        
        if ordered_sprints_for_plotly:
            fig_vel.update_xaxes(categoryorder='array', categoryarray=ordered_sprints_for_plotly) 
        
        st.plotly_chart(fig_vel, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('velocity', 'Awaiting Analysis...')}")

    # Metric 2: Sprint Goal Completion (Bar Chart)
    with col2:
        st.subheader("2. Sprint Goal Completion (Committed vs. Completed)")
        df_comp = pd.DataFrame(st.session_state['metrics_data']['completion'])
        fig_comp = px.bar(df_comp, x='SprintID', y=['CommittedPoints', 'CompletedPoints'], 
                         title='Committed vs. Completed Points', barmode='group',
                         color_discrete_map={'CommittedPoints': '#1d4ed8', 'CompletedPoints': '#34d399'})
        
        if ordered_sprints_for_plotly:
            fig_comp.update_xaxes(categoryorder='array', categoryarray=ordered_sprints_for_plotly)
            
        st.plotly_chart(fig_comp, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('completion', 'Awaiting Analysis...')}")

    # 6.2 Capacity Utilization & Defect Density (Two charts in one row)
    col3, col4 = st.columns(2)

    # Metric 3: Capacity Utilization (Bar Chart) 
    with col3:
        st.subheader("3. Capacity Utilization (Assignee Load - Last 5 Sprints)")
        df_cap = pd.DataFrame(st.session_state['metrics_data']['capacity'])
        fig_cap = px.bar(df_cap, x='Assignee', y=['Load', 'AssumedCapacity'], 
                         title='Team Member Load vs. Capacity', barmode='group',
                         color_discrete_map={'Load': '#f97316', 'AssumedCapacity': '#d1d5db'})
        st.plotly_chart(fig_cap, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('capacity', 'Awaiting Analysis...')}")

    # Metric 4: Defect Density (Bar Chart) - X-axis is RaisedIn (SprintID)
    with col4:
        st.subheader("4. Defect Density (Defects per Sprint vs. Stories)")
        df_den = pd.DataFrame(st.session_state['metrics_data']['density'])
        
        fig_den = go.Figure(data=[
            go.Bar(name='Defect Count', x=df_den['RaisedIn'], y=df_den['DefectCount'], yaxis='y1', marker_color='#ef4444'),
            go.Scatter(name='Story Count', x=df_den['RaisedIn'], y=df_den['StoryCount'], yaxis='y2', mode='lines+markers', marker_color='#059669')
        ])

        fig_den.update_layout(
            title='Defect Count vs. Story Count per Sprint',
            xaxis_title='SprintID (Raised In)',
            yaxis=dict(title='Defect Count', side='left', showgrid=False),
            yaxis2=dict(title='Story Count', side='right', overlaying='y', showgrid=False),
            legend=dict(x=0.01, y=0.99)
        )
        if ordered_sprints_for_plotly: 
            fig_den.update_xaxes(categoryorder='array', categoryarray=ordered_sprints_for_plotly) 
        
        st.plotly_chart(fig_den, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('density', 'Awaiting Analysis...')}")

    # 6.3 Defect Distribution & RAID Summary (Two components in one row)
    col5, col6 = st.columns(2)
    
    # Metric 5: Defect Stage Distribution (Pie Chart) 
    with col5:
        st.subheader("5. Defect Stage Distribution (Open Defects by Phase)")
        df_stage = pd.DataFrame(st.session_state['metrics_data']['stage'])
        fig_stage = px.pie(df_stage, values='Count', names='Phase', 
                           title='Open Defects by Phase',
                           color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_stage, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('stage', 'Awaiting Analysis...')}")

    # Metric 6: RAID Summary (Table) 
    with col6:
        st.subheader("6. RAID Summary (Open Items)")
        df_raid = pd.DataFrame(st.session_state['metrics_data']['raid'])
        
        def color_status(val):
            if '⚠️' in val or '🚨' in val:
                return 'background-color: #fca5a5; color: black;'
            elif '✅' in val:
                return 'background-color: #d1fae5; color: black;'
            return ''

        st.dataframe(df_raid.style.applymap(color_status, subset=['Status']), 
                     hide_index=True, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('raid', 'Awaiting Analysis...')}")