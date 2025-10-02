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

# --- 1. CONFIGURATION AND INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="AI Program Health Dashboard")

# Ensure mock data files exist for quick testing
@st.cache_resource
def setup_mock_files():
    """Generates mock files if they don't exist and provides download links."""
    st.info("Generating mock data files for testing (run once).")
    return generate_mock_data()

mock_files = setup_mock_files()

# --- 2. API KEY INPUT & MOCK DATA DOWNLOAD ---

st.title("🤖 AI-Powered Program Health Dashboard")
st.markdown("Upload your JIRA, Defects, and RAID logs to generate analysis.")

# --- API Key Input ---
with st.sidebar:
    st.header("🔑 Gemini API Key")
    # Using st.session_state to persist the key input
    if 'gemini_api_key' not in st.session_state:
        st.session_state['gemini_api_key'] = ''

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
    
    # Download links for mock files 
    col1, col2, col3 = st.columns(3)
    
    with open('jira_issues.csv', 'rb') as f:
        col1.download_button("JIRA Issues", f, "jira_issues.csv")
    with open('defects.csv', 'rb') as f:
        col2.download_button("Defects Log", f, "defects.csv")
    with open('raid_log.csv', 'rb') as f:
        col3.download_button("RAID Log", f, "raid_log.csv")


# Uploaders for the main app
upload_col1, upload_col2, upload_col3 = st.columns(3)
jira_file = upload_col1.file_uploader("Upload JIRA Issues CSV", type=['csv'])
defects_file = upload_col2.file_uploader("Upload Defects Log CSV", type=['csv'])
raid_file = upload_col3.file_uploader("Upload RAID Log CSV", type=['csv'])

# --- 3. DATA PROCESSING ---

data_ready = False
if jira_file and defects_file and raid_file:
    with st.spinner("Processing uploaded data with Pandas..."):
        metrics_data = load_and_process_data(jira_file, defects_file, raid_file)
    
    if "error" in metrics_data:
        st.error(f"Data Processing Error: {metrics_data['error']}")
    else:
        data_ready = True
elif st.button("📊 Use Mock Data (Default)") and all(os.path.exists(f) for f in mock_files):
    with st.spinner("Processing mock data with Pandas..."):
        # Correctly referencing the new mock file names
        metrics_data = load_and_process_data('jira_issues.csv', 'defects.csv', 'raid_log.csv') 
    if "error" in metrics_data:
        st.error(f"Mock Data Processing Error: {metrics_data['error']}")
    else:
        data_ready = True
    
# --- 4. AI ANALYSIS AND REPORTING ---

if data_ready:
    st.divider()
    
    # Initialize session state for AI summaries
    if 'ai_summaries' not in st.session_state:
        st.session_state['ai_summaries'] = {}
        
    # Button to trigger ALL AI analysis (disabled if no key is present)
    if st.button("🧠 Trigger Full AI Analysis & Report Generation", type="primary", disabled=not st.session_state['gemini_api_key']):
        
        api_key = st.session_state['gemini_api_key']
        st.session_state['ai_summaries'] = {} # Reset
        
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
                # Pass API key to AI function
                summary = get_ai_summary(api_key, name, data_summary) 
                st.session_state['ai_summaries'][key] = summary
                
        with st.spinner("🧠 Running Executive Synthesis (Final AI call)..."):
            # Pass API key to AI function
            exec_summary = get_executive_summary(api_key, metrics_data) 
            st.session_state['ai_summaries']['executive_summary'] = exec_summary
            
        st.success("✅ All 7 AI Summaries complete!")


    # --- 5. EXECUTIVE SUMMARY CARD ---
    
    exec_summary = st.session_state['ai_summaries'].get('executive_summary', 
                                                       "Click 'Trigger Full AI Analysis' to generate the leadership synthesis.")
    
    # Stylized card layout
    st.markdown(f"""
        <div style="padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); margin-bottom: 2rem; border-top: 8px solid #4f46e5; background-color: white;">
            <h2 style="font-size: 1.875rem; font-weight: 700; color: #4f46e5; margin-bottom: 1rem;">Executive Summary</h2>
            <div style="color: #4b5563; font-size: 1.125rem; min-height: 60px;">
                {exec_summary}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Download Button (after AI analysis)
    exec_text = st.session_state['ai_summaries'].get('executive_summary', '')
    if exec_text.startswith('✅') or exec_text.startswith('⚠️') or exec_text.startswith('❌'):
        
        file_path = generate_ppt(metrics_data, st.session_state['ai_summaries'])
        
        st.button("⬇️ Download Program Health PPT", help=f"Simulates creating and downloading the '{file_path}'.", disabled=False, type="secondary")
        st.info("The download button is enabled! In a real Streamlit app, this would provide the PPTX file.")
    else:
        st.button("⬇️ Download Program Health PPT", help="Run the AI Analysis first to enable the report download.", disabled=True)

    
    # --- 6. METRICS CARDS AND CHARTS ---
    
    st.header("Programmatic Health Metrics")
    
    # 6.1 Velocity Trend & Completion (Two charts in one row)
    
    col1, col2 = st.columns(2)
    
    # Metric 1: Velocity Trend (Line Chart)
    with col1:
        st.subheader("1. Velocity Trend (Completed Story Points/Sprint)")
        df_vel = pd.DataFrame(metrics_data['velocity'])
        # Use SprintID for X-axis
        fig_vel = px.line(df_vel, x='SprintID', y='CompletedPoints', 
                         title='Completed Story Points Over Time', markers=True,
                         color_discrete_sequence=['#1e40af'])
        fig_vel.add_trace(go.Scatter(x=df_vel['SprintID'], y=df_vel['CommittedPoints'],
                                    mode='lines', name='Committed Points', line=dict(dash='dot', color='#ef4444')))
        st.plotly_chart(fig_vel, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('velocity', 'Awaiting Analysis...')}")

    # Metric 2: Sprint Goal Completion (Bar Chart)
    with col2:
        st.subheader("2. Sprint Goal Completion (Committed vs. Completed)")
        df_comp = pd.DataFrame(metrics_data['completion'])
        # Use SprintID for X-axis
        fig_comp = px.bar(df_comp, x='SprintID', y=['CommittedPoints', 'CompletedPoints'], 
                         title='Committed vs. Completed Points', barmode='group',
                         color_discrete_map={'CommittedPoints': '#1d4ed8', 'CompletedPoints': '#34d399'})
        st.plotly_chart(fig_comp, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('completion', 'Awaiting Analysis...')}")

    # 6.2 Capacity Utilization & Defect Density (Two charts in one row)
    
    col3, col4 = st.columns(2)

    # Metric 3: Capacity Utilization (Bar Chart)
    with col3:
        st.subheader("3. Capacity Utilization (Assignee Load - Last 5 Sprints)")
        df_cap = pd.DataFrame(metrics_data['capacity'])
        fig_cap = px.bar(df_cap, x='Assignee', y=['Load', 'AssumedCapacity'], 
                         title='Team Member Load vs. Capacity', barmode='group',
                         color_discrete_map={'Load': '#f97316', 'AssumedCapacity': '#d1d5db'})
        st.plotly_chart(fig_cap, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('capacity', 'Awaiting Analysis...')}")

    # Metric 4: Defect Density (Bar Chart)
    with col4:
        st.subheader("4. Defect Density (Defects per Sprint vs. Stories)")
        df_den = pd.DataFrame(metrics_data['density'])
        
        # Use RaisedIn (SprintID) for X-axis
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
        st.plotly_chart(fig_den, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('density', 'Awaiting Analysis...')}")

    # 6.3 Defect Distribution & RAID Summary (Two components in one row)

    col5, col6 = st.columns(2)
    
    # Metric 5: Defect Stage Distribution (Pie Chart)
    with col5:
        st.subheader("5. Defect Stage Distribution (Open Defects by Phase)")
        df_stage = pd.DataFrame(metrics_data['stage'])
        # Use Phase for names
        fig_stage = px.pie(df_stage, values='Count', names='Phase', 
                           title='Open Defects by Phase',
                           color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_stage, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('stage', 'Awaiting Analysis...')}")

    # Metric 6: RAID Summary (Table)
    with col6:
        st.subheader("6. RAID Summary (Open Items)")
        df_raid = pd.DataFrame(metrics_data['raid'])
        
        # Highlight status using styling
        def color_status(val):
            if '⚠️' in val:
                return 'background-color: #fca5a5; color: black;'
            elif '✅' in val:
                return 'background-color: #d1fae5; color: black;'
            return ''

        st.dataframe(df_raid.style.applymap(color_status, subset=['Status']), 
                     hide_index=True, use_container_width=True)
        st.markdown(f"**AI Insight:** {st.session_state['ai_summaries'].get('raid', 'Awaiting Analysis...')}")
