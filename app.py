import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from data_processor import load_and_process_data
from ai_engine import get_ai_summary, get_executive_summary
from report_generator import generate_ppt
from mock_data import generate_mock_data
from datetime import date # Used for date.today() in report_generator and other general date needs if any

import base64 # IMPORTANT: Added for encoding PPT for download
# Ensure you have `python-pptx` installed for generate_ppt to work, which should be in requirements.txt

# --- 1. CONFIGURATION AND INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="AI Program Health Dashboard")

st.info("App Start: Config set.") # Debug message

# Ensure mock data files exist for quick testing
@st.cache_resource
def setup_mock_files():
    """Generates mock files if they don't exist and provides download links."""
    st.info("Setup Mock Files: Checking file existence.") # Debug message
    # Check if files exist before regenerating
    mock_file_names = ['jira_issues.csv', 'defects.csv', 'raid_log.csv']
    if not all(os.path.exists(f) for f in mock_file_names):
        st.info("Setup Mock Files: Generating new mock data.") # Debug message
        return generate_mock_data()
    st.info("Setup Mock Files: Mock data already exists.") # Debug message
    return mock_file_names # Return existing file names if they are there

mock_files = setup_mock_files()

# --- 2. API KEY INPUT & MOCK DATA DOWNLOAD ---

st.title("🤖 AI-Powered Program Health Dashboard")
st.markdown("Upload your JIRA, Defects, and RAID logs to generate analysis.")

st.info("After Title and Upload Prompts.") # Debug message

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
    
    # Ensure files exist before attempting to open them
    jira_mock_path = 'jira_issues.csv'
    defects_mock_path = 'defects.csv'
    raid_mock_path = 'raid_log.csv'

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

data_ready = False
metrics_data = {} # Initialize to avoid NameError
if jira_file and defects_file and raid_file:
    st.info("Data Processing: User files uploaded.") # Debug message
    with st.spinner("Processing uploaded data with Pandas..."):
        metrics_data = load_and_process_data(jira_file, defects_file, raid_file)
    
    if "error" in metrics_data:
        st.error(f"Data Processing Error: {metrics_data['error']}")
    else:
        data_ready = True
elif st.button("📊 Use Mock Data (Default)") and all(os.path.exists(f) for f in mock_files):
    st.info("Data Processing: Using Mock Data.") # Debug message
    with st.spinner("Processing mock data with Pandas..."):
        metrics_data = load_and_process_data('jira_issues.csv', 'defects.csv', 'raid_log.csv') 
    if "error" in metrics_data:
        st.error(f"Mock Data Processing Error: {metrics_data['error']}")
    else:
        data_ready = True
    
st.info(f"Data Processing Complete. Data Ready: {data_ready}") # Debug message

# --- 4. AI ANALYSIS AND REPORTING ---

if data_ready:
    st.divider()
    
    # Initialize session state for AI summaries
    if 'ai_summaries' not in st.session_state:
        st.session_state['ai_summaries'] = {}
        
    # Button to trigger ALL AI analysis (disabled if no key is present)
    if st.button("🧠 Trigger Full AI Analysis & Report Generation", type="primary", disabled=not st.session_state['gemini_api_key']):
        st.info("AI Analysis Triggered!") # Debug message
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
                summary = get_ai_summary(api_key, name, data_summary) 
                st.session_state['ai_summaries'][key] = summary
                
        with st.spinner("🧠 Running Executive Synthesis (Final AI call)..."):
            exec_summary = get_executive_summary(api_key, metrics_data) 
            st.session_state['ai_summaries']['executive_summary'] = exec_summary
            
        st.success("✅ All 7 AI Summaries complete!")

    st.info("After AI Analysis Button Check.") # Debug message

    # --- 5. EXECUTIVE SUMMARY CARD ---
    
    exec_summary_raw = st.session_state['ai_summaries'].get('executive_summary', 
                                                       "Click 'Trigger Full AI Analysis' to generate the leadership synthesis.")
    
    # Check if AI analysis has run and produced a meaningful summary
    ai_analysis_complete = exec_summary_raw.startswith(('🔴', '🟠', '🟢'))
    
    emoji = ''
    final_html_content = ''

    if ai_analysis_complete:
        st.info("Executive Summary: AI analysis complete, processing content.") # Debug message
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
                html_content_parts.append(f"<h3>{heading.strip()}</h3>")
            
            if len(lines) > 1:
                html_content_parts.append("<ul>")
                for line in lines[1:]:
                    if line.strip().startswith('*'):
                        html_content_parts.append(f"<li>{line.strip()[1:].strip()}</li>")
                    elif line.strip(): 
                        html_content_parts.append(f"<p>{line.strip()}</p>")
                html_content_parts.append("</ul>")
                
        final_html_content = "".join(html_content_parts)
    else:
        st.info("Executive Summary: AI analysis not yet complete, showing placeholder.") # Debug message
        final_html_content = f"<p>{exec_summary_raw}</p>" 

    # Generate the PPT file (simulated) if analysis is complete
    ppt_file_path = ""
    if ai_analysis_complete:
        st.info("Attempting to generate PPT.") # Debug message
        try:
            ppt_file_path = generate_ppt(metrics_data, st.session_state['ai_summaries'])
            st.info(f"PPT generated at: {ppt_file_path}") # Debug message
        except Exception as e:
            st.error(f"Error generating PPT: {e}")
            ai_analysis_complete = False # Disable download if PPT generation fails

    # Stylized card layout - Part 1: Top section of the card
    st.markdown(f"""
        <div id="executive_summary_card_top" style="padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); margin-bottom: 0rem; border-top: 8px solid #4f46e5; background-color: white;">
            <h2 style="font-size: 1.875rem; font-weight: 700; color: #4f46e5; margin-bottom: 1rem;">{emoji} Executive Summary</h2>
            <div style="color: #4b5563; font-size: 1.125rem; min-height: 60px; margin-bottom: 1rem;">
                {final_html_content}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Stylized card layout - Part 2: Bottom section with download button
    # This will be a separate Streamlit component so it can handle the a-tag dynamically.
    # We create a container just for the button part for better alignment.
    with st.container():
        # Adjust margin-top to visually connect the two parts of the card
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
            
        # Render the actual download button logic here using st.download_button
        # This is the most reliable way to create a download button in Streamlit
        # and ensures it's correctly interpreted as a functional button.
        if ai_analysis_complete and os.path.exists(ppt_file_path):
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
            # Use st.button for consistency, but disabled
            st.button(label="⬇️ Download Program Health PPT", disabled=True, 
                      help="Run the AI Analysis first to enable the report download.")
            st.markdown('<p style="color: #6b7280; font-size: 0.875rem; margin-top: 0.5rem;">Run the AI Analysis first to enable the report download.</p>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True) # Close the container div

    st.info("After Executive Summary Card.") # Debug message

    # --- 6. METRICS CARDS AND CHARTS ---
    
    st.header("Programmatic Health Metrics")
    st.info("Before Metrics Cards and Charts.") # Debug message
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

    st.info("End of App Execution Path.") # Debug message