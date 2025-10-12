import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from data_processor import (
    load_and_preprocess_raw_data,
    calculate_velocity_trend,
    calculate_sprint_completion,
    calculate_capacity_utilization,
    calculate_defect_density,
    calculate_defect_stage_distribution,
    get_raid_summary
)
from ai_engine import chat_with_agent # Import the new agent function
from report_generator import generate_ppt
from mock_data import generate_mock_data
from datetime import date 

import base64 
import re 

# --- 1. CONFIGURATION AND INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="AI Program Health Dashboard")

# Initialize session state variables if they don't exist
if 'preprocessed_dfs' not in st.session_state:
    st.session_state['preprocessed_dfs'] = None # Store the raw preprocessed dataframes (df_jira, df_defects, df_raid)
if 'data_loaded' not in st.session_state:
    st.session_state['data_loaded'] = False
if 'gemini_api_key' not in st.session_state:
    st.session_state['gemini_api_key'] = ''
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = [] # For conversational memory (LLM messages)
if 'executive_summary_output' not in st.session_state:
    st.session_state['executive_summary_output'] = "Ask the AI agent for an overall health assessment!"
if 'metric_insights_output' not in st.session_state:
    st.session_state['metric_insights_output'] = {} # Stores AI insights for individual metrics, indexed by metric name
if 'all_metrics_data' not in st.session_state:
    st.session_state['all_metrics_data'] = {} # Stores ALL calculated metric data (dicts of lists) for dashboard visualization

# Ensure mock data files exist for quick testing
@st.cache_resource
def setup_mock_files():
    """Generates mock files if they don't exist and provides download links."""
    mock_file_names = ['jira_issues.csv', 'defects.csv', 'raid_log.csv']
    if not all(os.path.exists(f) for f in mock_file_names):
        st.info("Generating mock data files for the first time...")
        return generate_mock_data()
    return mock_file_names 

mock_files = setup_mock_files()

# --- 2. API KEY INPUT & MOCK DATA DOWNLOAD ---

st.title("🤖 AI-Powered Program Health Dashboard")
st.markdown("Upload your JIRA, Defects, and RAID logs to generate analysis, or use mock data.")

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
jira_file = upload_col1.file_uploader("Upload JIRA Issues CSV", type=['csv'], key="jira_uploader")
defects_file = upload_col2.file_uploader("Upload Defects Log CSV", type=['csv'], key="defects_uploader")
raid_file = upload_col3.file_uploader("Upload RAID Log CSV", type=['csv'], key="raid_uploader")


# --- 3. DATA PROCESSING ---

# Function to load and store preprocessed dataframes
def process_data_and_store(jira_input, defects_input, raid_input):
    with st.spinner("Processing uploaded data with Pandas..."):
        processed_data = load_and_preprocess_raw_data(jira_input, defects_input, raid_input)
    
    if "error" in processed_data:
        st.error(f"Data Processing Error: {processed_data['error']}")
        st.session_state['data_loaded'] = False
        st.session_state['preprocessed_dfs'] = None
    else:
        st.session_state['preprocessed_dfs'] = processed_data
        st.session_state['data_loaded'] = True
        
        # Calculate ALL metrics once data is loaded for dashboard visualization
        df_jira = processed_data['df_jira']
        df_defects = processed_data['df_defects']
        df_raid = processed_data['df_raid']

        st.session_state['all_metrics_data'] = {
            "velocity": calculate_velocity_trend(df_jira),
            "completion": calculate_sprint_completion(df_jira),
            "capacity": calculate_capacity_utilization(df_jira),
            "density": calculate_defect_density(df_jira, df_defects),
            "stage": calculate_defect_stage_distribution(df_defects),
            "raid": get_raid_summary(df_raid),
        }
        st.success("✅ Data loaded and preprocessed!")

if not st.session_state['data_loaded']: # Only attempt to load if not already loaded
    if jira_file and defects_file and raid_file:
        process_data_and_store(jira_file, defects_file, raid_file)
    elif st.button("📊 Use Mock Data (Default)"):
        if all(os.path.exists(f) for f in mock_files):
            process_data_and_store('jira_issues.csv', 'defects.csv', 'raid_log.csv')
        else:
            st.error("Mock data files not found. Please ensure they are generated.")

# --- 4. AI AGENT INTERACTION ---
st.divider()

if st.session_state['data_loaded'] and st.session_state['gemini_api_key'] and st.session_state['preprocessed_dfs'] is not None:
    st.header("💬 Talk to the AI Program Analyst")
    user_query = st.chat_input("Ask about program health, metrics, risks, etc. (e.g., 'What is our sprint velocity trend?', 'Summarize overall health.')")

    if user_query:
        # Append user message to chat history for display
        st.session_state['chat_history'].append({"role": "user", "parts": [{"text": user_query}]})
        
        with st.spinner("🧠 AI Agent thinking and analyzing..."):
            # Call the new chat_with_agent function
            agent_response_obj = chat_with_agent(
                api_key=st.session_state['gemini_api_key'], 
                user_query=user_query, 
                preprocessed_dataframes=st.session_state['preprocessed_dfs'], # Pass the preprocessed DFs
                history=st.session_state['chat_history'] # Pass current history for conversational context
            )
            
            if "error" in agent_response_obj:
                st.error(f"AI Agent Error: {agent_response_obj['error']}")
                # If there's an error, still update history to show the user's last message
                if st.session_state['chat_history'][-1]['role'] == 'user':
                    st.session_state['chat_history'].append({"role": "model", "parts": [{"text": f"Error: {agent_response_obj['error']}"}]})
            else:
                ai_response_text = agent_response_obj['response']
                st.session_state['chat_history'] = agent_response_obj['history'] # Update history from agent
                
                # Special handling: If the user asks for "overall health" or "executive summary",
                # update the executive summary card content.
                if "overall health" in user_query.lower() or "executive summary" in user_query.lower() or "summarize program" in user_query.lower():
                    st.session_state['executive_summary_output'] = ai_response_text
                
                # Store general metric insights from the agent.
                # A more advanced version might parse the AI response to identify which metric
                # it's describing and update `metric_insights_output` accordingly.
                st.session_state['metric_insights_output'][user_query] = ai_response_text
                
        # Display chat history in the main chat area
        for message in st.session_state['chat_history']:
            if message["role"] == "user":
                st.chat_message("user").write(message["parts"][0]["text"])
            elif message["role"] == "model":
                st.chat_message("assistant").write(message["parts"][0]["text"])
            elif message["role"] == "function":
                # For debugging, you can display function calls, but typically keep them hidden from user
                # st.chat_message("assistant").json(message["parts"][0]["functionResponse"])
                pass # Do not display function calls directly to the user by default
            
    # --- 5. EXECUTIVE SUMMARY CARD ---
    exec_summary_raw = st.session_state['executive_summary_output']
    
    # Determine if AI analysis is complete for the executive summary
    ai_analysis_complete = exec_summary_raw not in ["", "Ask the AI agent for an overall health assessment!"]
    
    emoji = ''
    final_html_content = ''

    if ai_analysis_complete:
        # Attempt to parse emoji if present at the very beginning (e.g., 🔴, 🟠, 🟢)
        emoji_match = re.match(r'^(🔴|🟠|🟢|✅|⚠️|❌)', exec_summary_raw)
        if emoji_match:
            emoji = emoji_match.group(0)
            content_without_emoji = exec_summary_raw[len(emoji):].strip()
        else:
            content_without_emoji = exec_summary_raw.strip() # No emoji found
        
        html_content_parts = []
        
        # Split by Markdown headings (##)
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
                    elif line.strip(): # Fallback for lines not starting with *
                        html_content_parts.append(f"<p>{line.strip()}</p>")
                html_content_parts.append("</ul>")
                
        final_html_content = "".join(html_content_parts)
    else:
        final_html_content = f"<p>{exec_summary_raw}</p>" 

    ppt_file_path = ""
    if ai_analysis_complete and st.session_state['data_loaded']: 
        try:
            # For PPT generation, we need to pass the *actual* calculated metric data
            # and the *AI-generated summaries* for each.
            # This is a bit of a placeholder, as the `chat_with_agent` currently
            # provides one overall response. We would need to prompt the agent
            # to generate specific summaries for each metric if needed for PPT.
            # For now, we reuse the executive summary and default specific summaries.
            
            # This structure will be improved when we refine Response Synthesizer
            simulated_ai_summaries = {}
            simulated_ai_summaries['executive_summary'] = st.session_state['executive_summary_output']
            
            # Populate individual metric summaries if available from the agent's general responses
            # This is a heuristic; a more robust approach would involve the agent explicitly calling
            # a 'summarize_metric' tool for each metric if needed for the PPT.
            for metric_key in ["velocity", "completion", "capacity", "density", "stage", "raid"]:
                # Try to find a previous AI response that might cover this metric
                found_insight = "No specific AI insight generated for this metric in current conversation."
                for q, a in st.session_state['metric_insights_output'].items():
                    if metric_key in q.lower() or metric_key.replace('_', ' ') in q.lower():
                        found_insight = a
                        break
                simulated_ai_summaries[metric_key] = found_insight

            ppt_file_path = generate_ppt(st.session_state['all_metrics_data'], simulated_ai_summaries)
        except Exception as e:
            st.error(f"Error generating PPT: {e}")
            ppt_file_path = "" 


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
            
        if ai_analysis_complete and ppt_file_path and os.path.exists(ppt_file_path): 
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
                      help="Ask the AI agent for an overall health assessment to enable the report download.")
            st.markdown('<p style="color: #6b7280; font-size: 0.875rem; margin-top: 0.5rem;">Ask the AI agent for an overall health assessment to enable the report download.</p>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True) 

    # --- 6. METRICS CARDS AND CHARTS ---
    
    st.header("Programmatic Health Metrics")

    # --- PREPARE SPRINT ORDER FOR PLOTLY ---
    # Use metrics_data from session state
    temp_df_for_sprints = pd.DataFrame(st.session_state['all_metrics_data'].get('velocity', [])) 
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
        df_vel = pd.DataFrame(st.session_state['all_metrics_data'].get('velocity', []))
        if not df_vel.empty:
            fig_vel = px.line(df_vel, x='SprintID', y='CompletedPoints', 
                             title='Completed Story Points Over Time', markers=True,
                             color_discrete_sequence=['#1e40af'])
            # The 'CommittedPoints' are now part of 'completion' metric calculation in data_processor,
            # but for this chart, we'll keep it simple or fetch from 'completion' if needed.
            # For now, let's keep it consistent with the original plot if possible, 
            # by fetching from completion data.
            df_comp_for_vel_plot = pd.DataFrame(st.session_state['all_metrics_data'].get('completion', []))
            if not df_comp_for_vel_plot.empty and 'CommittedPoints' in df_comp_for_vel_plot.columns:
                 fig_vel.add_trace(go.Scatter(x=df_comp_for_vel_plot['SprintID'], y=df_comp_for_vel_plot['CommittedPoints'],
                                             mode='lines', name='Committed Points', line=dict(dash='dot', color='#ef4444')))
            
            if ordered_sprints_for_plotly:
                fig_vel.update_xaxes(categoryorder='array', categoryarray=ordered_sprints_for_plotly) 
            
            st.plotly_chart(fig_vel, use_container_width=True)
        else:
            st.info("No velocity data available to plot.")
        
        # Display AI insight relevant to velocity
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('What is our sprint velocity trend?', 'Ask the AI analyst.')}")


    # Metric 2: Sprint Goal Completion (Bar Chart)
    with col2:
        st.subheader("2. Sprint Goal Completion (Committed vs. Completed)")
        df_comp = pd.DataFrame(st.session_state['all_metrics_data'].get('completion', []))
        if not df_comp.empty:
            fig_comp = px.bar(df_comp, x='SprintID', y=['CommittedPoints', 'CompletedPoints'], 
                             title='Committed vs. Completed Points', barmode='group',
                             color_discrete_map={'CommittedPoints': '#1d4ed8', 'CompletedPoints': '#34d399'})
            
            if ordered_sprints_for_plotly:
                fig_comp.update_xaxes(categoryorder='array', categoryarray=ordered_sprints_for_plotly)
                
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("No sprint completion data available to plot.")
        
        # Display AI insight relevant to sprint completion
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('How is our sprint goal completion?', 'Ask the AI analyst.')}")

    # 6.2 Capacity Utilization & Defect Density (Two charts in one row)
    col3, col4 = st.columns(2)

    # Metric 3: Capacity Utilization (Bar Chart) 
    with col3:
        st.subheader("3. Capacity Utilization (Assignee Load - Last 5 Sprints)")
        df_cap = pd.DataFrame(st.session_state['all_metrics_data'].get('capacity', []))
        if not df_cap.empty:
            fig_cap = px.bar(df_cap, x='Assignee', y=['Load', 'AssumedCapacity'], 
                             title='Team Member Load vs. Capacity', barmode='group',
                             color_discrete_map={'Load': '#f97316', 'AssumedCapacity': '#d1d5db'})
            st.plotly_chart(fig_cap, use_container_width=True)
        else:
            st.info("No capacity utilization data available to plot.")
        
        # Display AI insight relevant to capacity
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('Tell me about team capacity utilization.', 'Ask the AI analyst.')}")

    # Metric 4: Defect Density (Bar Chart) - X-axis is RaisedIn (SprintID)
    with col4:
        st.subheader("4. Defect Density (Defects per Sprint vs. Stories)")
        df_den = pd.DataFrame(st.session_state['all_metrics_data'].get('density', []))
        if not df_den.empty:
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
        else:
            st.info("No defect density data available to plot.")
        
        # Display AI insight relevant to defect density
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('What is our defect density?', 'Ask the AI analyst.')}")

    # 6.3 Defect Distribution & RAID Summary (Two components in one row)
    col5, col6 = st.columns(2)
    
    # Metric 5: Defect Stage Distribution (Pie Chart) 
    with col5:
        st.subheader("5. Defect Stage Distribution (Open Defects by Phase)")
        df_stage = pd.DataFrame(st.session_state['all_metrics_data'].get('stage', []))
        if not df_stage.empty:
            fig_stage = px.pie(df_stage, values='Count', names='Phase', 
                               title='Open Defects by Phase',
                               color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_stage, use_container_width=True)
        else:
            st.info("No defect stage distribution data available to plot.")
        
        # Display AI insight relevant to defect stage
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('How are defects distributed by stage?', 'Ask the AI analyst.')}")


    # Metric 6: RAID Summary (Table) 
    with col6:
        st.subheader("6. RAID Summary (Open Items)")
        df_raid = pd.DataFrame(st.session_state['all_metrics_data'].get('raid', []))
        if not df_raid.empty:
            def color_status(val):
                if '⚠️' in val:
                    return 'background-color: #fce703; color: black;' # Warning color
                elif '🚨' in val:
                    return 'background-color: #ef4444; color: white;' # Critical color
                elif '✅' in val:
                    return 'background-color: #34d399; color: black;' # Healthy color
                return ''

            # Ensure 'Status' column exists before applying style
            if 'Status' in df_raid.columns:
                st.dataframe(df_raid.style.map(color_status, subset=['Status']), 
                             hide_index=True, use_container_width=True)
            else:
                st.dataframe(df_raid, hide_index=True, use_container_width=True)
        else:
            st.info("No open RAID data available.")
        
        # Display AI insight relevant to RAID
        st.markdown(f"**AI Insight:** {st.session_state['metric_insights_output'].get('Summarize our open RAID items.', 'Ask the AI analyst.')}")

else:
    st.info("Upload data files or use mock data to begin analysis and interact with the AI agent.")
