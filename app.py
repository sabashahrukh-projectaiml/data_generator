import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import hashlib

# --- MISSION CONTROL INITIALIZATION ---
st.set_page_config(page_title="ProjectAIML Launchpad", page_icon="🚀", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_clearance = 1

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# This function saves your "Quota" by remembering the data
@st.cache_data(ttl=300)
def get_data(worksheet_name):
    df = conn.read(worksheet=worksheet_name)
    
    # If this is the progress sheet, fix the types immediately
    if worksheet_name == "Node_Analytics":
        for col in ['Blog_Read', 'Code_Done', 'Quiz_Done']:
            if col in df.columns:
                df[col] = df[col].astype(bool)
    return df

# --- ARCHITECT'S UTILITIES ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_cleaned_registry():
    try:
        registry = get_data("User_Registry")
        if 'Clearance' in registry.columns:
            registry['Clearance'] = pd.to_numeric(registry['Clearance'], errors='coerce').fillna(1).astype(int)
        if 'Email' in registry.columns:
            registry['Email'] = registry['Email'].astype(str).str.lower().str.strip()
        return registry
    except Exception as e:
        st.error(f"Registry Access Denied: {e}")
        return pd.DataFrame()

# --- MISSION LOGIC METHODS ---

def update_granular_progress(email, mission_id, node_id, column_to_flip, value):
    try:
        all_progress = get_data("Node_Analytics")

        bool_cols = ['Blog_Read', 'Code_Done', 'Quiz_Done']
        for col in bool_cols:
            if col in all_progress.columns:
                # This converts numbers/NaNs into True/False so Pandas is happy
                all_progress[col] = all_progress[col].astype(bool)
        
        all_progress['Node_ID'] = all_progress['Node_ID'].astype(str)
        mask = (all_progress['Email'] == email) & (all_progress['Node_ID'] == str(node_id))
        
        if mask.any():
            all_progress.loc[mask, column_to_flip] = value
            
        else:
            new_data = {"Email": email, "Mission_ID": mission_id, "Node_ID": str(node_id), 
                        "Blog_Read": False, "Code_Done": False, "Quiz_Done": False}
            new_data[column_to_flip] = value
            all_progress = pd.concat([all_progress, pd.DataFrame([new_data])], ignore_index=True)
        
        conn.update(worksheet="Node_Analytics", data=all_progress)
        st.cache_data.clear()
        st.success(f"Synced {column_to_flip}!")
    except Exception as e:
        st.error(f"Data Sync Error: {e}")

def reset_granular_progress(email, node_id, column_to_reset):
    try:
        all_progress = get_data("Node_Analytics")

        cols_to_fix = ['Blog_Read', 'Code_Done', 'Quiz_Done']
        for col in cols_to_fix:
            if col in all_progress.columns:
                all_progress[col] = all_progress[col].astype(bool)

        all_progress['Node_ID'] = all_progress['Node_ID'].astype(str)
        mask = (all_progress['Email'] == email) & (all_progress['Node_ID'] == str(node_id))
        
        if mask.any():
            all_progress.loc[mask, column_to_reset] = False
            conn.update(worksheet="Node_Analytics", data=all_progress)
            st.cache_data.clear()
            st.toast(f"Reset {column_to_reset} status.", icon="🔄")
    except Exception as e:
        st.error(f"Reset Error: {e}")

def complete_current_node(email, current_node, mission_id, total_nodes=5):
    try:
        all_missions = get_data("User_Missions")
        mask = (all_missions['Email'] == email) & (all_missions['Mission_ID'] == mission_id)
        if mask.any():
            new_node = int(current_node) + 1
            if new_node <= total_nodes:
                all_missions.loc[mask, 'Current_Node'] = new_node
                all_missions.loc[mask, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                all_missions.loc[mask, 'Status'] = "Completed"
                st.balloons()
            conn.update(worksheet="User_Missions", data=all_missions)
            st.cache_data.clear()
            st.rerun()
    except Exception as e:
        st.error(f"Sync Error: {e}")

# --- RENDER METHODS ---

def render_active_mission(user_state):
    email = user_state['Email'].values[0]
    m_id = user_state['Mission_ID'].values[0]
    curr_node = int(user_state['Current_Node'].values[0])
    
    st.markdown(f"### 🛰️ Active Mission: {m_id}")
    total_nodes = 5
    st.progress(curr_node / total_nodes)
    st.write(f"**Current Status:** Node {curr_node} of {total_nodes} Complete.")
    
    # Action Button
    if st.button("✅ Mark Node as Complete & Sync Progress", use_container_width=True):
        complete_current_node(email, curr_node, m_id, total_nodes)

def render_dynamic_navigator(email):
    manifest = get_data("Mission_Manifest")
    analytics = get_data("Node_Analytics")
    missions = manifest['Mission_ID'].unique()
    
    st.subheader("📂 Mission Navigator")
    for m_id in missions:
        with st.expander(f"🎯 Protocol: {m_id}"):
            nodes = manifest[manifest['Mission_ID'] == m_id]
            for _, node in nodes.iterrows():
                n_id = node['Node_ID']
                unique_key = f"{m_id}_{n_id}"

                user_node_data = analytics[(analytics['Email'] == email) & (analytics['Node_ID'] == str(n_id))]
                
                has_read = user_node_data['Blog_Read'].values[0] if not user_node_data.empty else False
                has_code = user_node_data['Code_Done'].values[0] if not user_node_data.empty else False
                has_quiz = user_node_data['Quiz_Done'].values[0] if not user_node_data.empty else False

                c1, c2, c3, c4 = st.columns([0.5, 0.16, 0.16, 0.16])
                c1.markdown(f"""
                    <div style="margin-top: 5px;">
                        <a href="{node['URL']}" target="_blank" style="text-decoration: none; color: #00f2ff; font-weight: 600; display: flex; align-items: center; gap: 5px;">
                            {node['Title']} <span style="font-size: 14px;">↗️</span>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
                
                # --- READ BUTTON ---
                with c2:
                    if has_read:
                        # Visual cue for completion: A green-bordered disabled button
                        st.button("📖 Read", key=f"r_{unique_key}", disabled=True, help="Already marked as complete", type="secondary")
                        #st.markdown('<style>div[data-testid="stButton"] button[disabled] { border: 2px solid #00FF00 !important; }</style>', unsafe_allow_html=True)
                        if st.button("Undo", key=f"un_r_{unique_key}", type="tertiary", help="Click to reset this status"):
                            reset_granular_progress(email, n_id, "Blog_Read")
                            st.rerun()
                    else:
                        if st.button("📖 Read", key=f"r_{unique_key}"):
                            update_granular_progress(email, m_id, n_id, "Blog_Read", True)
                            st.rerun()

                # --- CODE BUTTON ---
                with c3:
                    if has_code:
                        st.button("💻 Code", key=f"c_{unique_key}", disabled=True, help="Already marked as complete")
                        #st.markdown('<style>div[data-testid="stButton"] button[disabled] { border: 2px solid #00FF00 !important; }</style>', unsafe_allow_html=True)
                        if st.button("Undo", key=f"un_c_{unique_key}", type="tertiary", help="Click to reset this status"):
                            reset_granular_progress(email, n_id, "Code_Done")
                            st.rerun()
                    else:
                        if st.button("💻 Code", key=f"c_{unique_key}"):
                            update_granular_progress(email, m_id, n_id, "Code_Done", True)
                            st.rerun()

                # --- QUIZ BUTTON ---
                with c4:
                    if has_quiz:
                        st.button("❓ Quiz", key=f"q_{unique_key}", disabled=True, help="Already marked as complete")
                        #st.markdown('<style>div[data-testid="stButton"] button[disabled] { border: 2px solid #00FF00 !important; }</style>', unsafe_allow_html=True)
                        if st.button("Undo", key=f"un_q_{unique_key}", type="tertiary", help="Click to reset this status"):
                            reset_granular_progress(email, n_id, "Quiz_Done")
                            st.rerun()
                    else:
                        if st.button("❓ Quiz", key=f"q_{n_id}"):
                            update_granular_progress(email, m_id, n_id, "Quiz_Done", True)
                            st.rerun()

# --- MAIN APP LOGIC ---

if not st.session_state.authenticated:
    # Auth page layout
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        logo_c, title_c = st.columns([0.2, 1])
        logo_c.image("https://projectaiml.com/wp-content/uploads/2025/05/Gemini_Generated_Image_mg3y4pmg3y4pmg3y.jpg", width=60)
        title_c.title("Pilot Authorization")
        
        auth_mode = st.radio("Access Level", ["Login", "Register New Pilot"], horizontal=True)
        input_email = st.text_input("Email").strip().lower()
        input_pass = st.text_input("Password", type='password')
        
        if auth_mode == "Login":
            if st.button("Authorize Entry", type="primary", use_container_width=True):
                registry = get_cleaned_registry()
                user_row = registry[registry['Email'] == input_email]
                if not user_row.empty and hash_password(input_pass) == user_row.iloc[0]['Password_Hash']:
                    st.session_state.authenticated = True
                    st.session_state.user_email = input_email
                    st.session_state.user_name = user_row.iloc[0]['Full_Name']
                    st.session_state.user_clearance = user_row.iloc[0]['Clearance']
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
        else:
            name = st.text_input("Full Name")
            if st.button("Initialize Protocol", type="primary", use_container_width=True):
                # ... [Your Registration logic here] ...
                pass
else:
    # --- GLOBAL CSS INJECTION ---
    st.markdown("""
        <style>
        /* Target the specific column container for Undo buttons */
        div[data-testid="stVerticalBlock"] > div:has(button[key*="un_"]) {
            gap: 0rem !important;
        }

        /* The Undo link styling */
        button[key*="un_"] {
            font-size: 11px !important;
            padding: 0px !important;
            height: 20px !important;
            line-height: 1 !important;
            color: #ff4b4b !important;
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            margin-top: -15px !important;
            text-align: left !important;
            width: auto !important;
        }

        button[key*="un_"]:hover {
            text-decoration: underline !important;
            color: #ff3333 !important;
            background: transparent !important;
        }

        /* Ensure the 'Already marked' tooltip/disabled button stays green */
        button[disabled] {
            border: 1px solid #28a745 !important;
            color: #28a745 !important;
            background-color: rgba(40, 167, 69, 0.05) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # 1. FETCH ALL DATA ONCE (This uses the cache)
    mission_data = get_data("User_Missions")
    manifest = get_data("Mission_Manifest")
    analytics = get_data("Node_Analytics")
    
    # 2. RENDER THE QUANTUM HERO (Step 4)
    user_name = st.session_state.get('user_name', 'Pilot')
    user_email = st.session_state.get('user_email', 'unknown')

    st.markdown(f"""
    <div style="background: linear-gradient(90deg, #0176D3 0%, #00A1E0 100%); padding: 40px; border-radius: 20px; color: white; margin-bottom: 20px;">
        <h1 style="margin:0;">Welcome Back, {user_name}</h1>
        <p style="opacity:0.9;">Status: <b>Level {st.session_state.user_clearance} Cadet</b> | Secure Connection: {user_email}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # --- HEADER AREA ---
    h1, h2, h3 = st.columns([0.1, 1.3, 0.4])
    with h1:
        st.image("https://projectaiml.com/wp-content/uploads/2025/05/Gemini_Generated_Image_mg3y4pmg3y4pmg3y.jpg", width=50)
    with h2:
        st.title("🚀 ProjectAIML Launchpad")
    with h3:
        # Puts the profile button next to the title
        with st.popover(f"👤 {user_name}"):
            st.write(f"**Email:** {user_email}")
            if st.button("Secure Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.rerun()

    # --- ACTIVE MISSION PROMPT ---
    user_state = mission_data[mission_data['Email'] == user_email]

    if not user_state.empty and user_state['Status'].values[0] == "Active":
        render_active_mission(user_state)
    else:
        st.info("💡 Select a mission from the navigator below to begin your flight plan.")

    st.divider()

    # --- MISSION NAVIGATOR ---
    render_dynamic_navigator(user_email)

    st.caption("© 2026 ProjectAIML | Mission Control v1.0.4")