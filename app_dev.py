import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import hashlib

# --- 1. INITIALIZATION & CONFIG ---
# MUST be the first Streamlit command
st.set_page_config(page_title="ProjectAIML Launchpad", page_icon="🚀", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_clearance = 1

# --- 2. DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if worksheet_name == "Node_Analytics":
            bool_cols = ['Blog_Read', 'Code_Done', 'Quiz_Done']
            for col in bool_cols:
                if col in df.columns:
                    # fillna(False) prevents NaN being treated as True
                    df[col] = df[col].fillna(False).astype(bool)
        return df
    except Exception as e:
        st.error(f"Error connecting to {worksheet_name}: {e}")
        return pd.DataFrame()

# --- 3. UTILITIES ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_cleaned_registry():
    registry = get_data("User_Registry")
    if not registry.empty:
        if 'Clearance' in registry.columns:
            registry['Clearance'] = pd.to_numeric(registry['Clearance'], errors='coerce').fillna(1).astype(int)
        if 'Email' in registry.columns:
            registry['Email'] = registry['Email'].astype(str).str.lower().str.strip()
    return registry

# --- 4. DATA SYNC LOGIC ---
def update_granular_progress(email, mission_id, node_id, column_to_flip, value):
    try:
        all_progress = get_data("Node_Analytics")
        all_progress['Node_ID'] = all_progress['Node_ID'].astype(str)
        
        mask = (all_progress['Email'] == email) & (all_progress['Node_ID'] == str(node_id))
        
        if mask.any():
            all_progress.loc[mask, column_to_flip] = value
        else:
            new_row = {
                "Email": email, "Mission_ID": mission_id, "Node_ID": str(node_id), 
                "Blog_Read": False, "Code_Done": False, "Quiz_Done": False
            }
            new_row[column_to_flip] = value
            all_progress = pd.concat([all_progress, pd.DataFrame([new_row])], ignore_index=True)
        
        conn.update(worksheet="Node_Analytics", data=all_progress)
        st.cache_data.clear()
        st.toast(f"✅ {column_to_flip} synced!", icon="🛰️")
        st.rerun()
    except Exception as e:
        st.error(f"Sync Error: {e}")

def reset_granular_progress(email, node_id, column_to_reset):
    try:
        all_progress = get_data("Node_Analytics")
        all_progress['Node_ID'] = all_progress['Node_ID'].astype(str)
        mask = (all_progress['Email'] == email) & (all_progress['Node_ID'] == str(node_id))
        
        if mask.any():
            all_progress.loc[mask, column_to_reset] = False
            conn.update(worksheet="Node_Analytics", data=all_progress)
            st.cache_data.clear()
            st.toast(f"Reset {column_to_reset}", icon="🔄")
            st.rerun()
    except Exception as e:
        st.error(f"Reset Error: {e}")

# --- 5. RENDER FUNCTIONS ---
def render_dynamic_navigator(email):
    """
    Optimized renderer using a lookup dictionary to avoid repeated DF filtering.
    """
    manifest = get_data("Mission_Manifest")
    analytics = get_data("Node_Analytics")
    
    if manifest.empty:
        st.warning("Mission Manifest is empty.")
        return

    # PERFORMANCE BOOST: Create a lookup dictionary {(email, node_id): {status_dict}}
    # This turns O(N^2) search into O(1) lookup
    user_progress_map = (
        analytics[analytics['Email'] == email]
        .set_index('Node_ID')[['Blog_Read', 'Code_Done', 'Quiz_Done']]
        .to_dict('index')
    )

    st.subheader("📂 Mission Navigator")
    missions = manifest['Mission_ID'].unique()
    
    for m_id in missions:
        with st.expander(f"🎯 Protocol: {m_id}"):
            nodes = manifest[manifest['Mission_ID'] == m_id].sort_values('Order')
            
            for _, node in nodes.iterrows():
                n_id = str(node['Node_ID'])
                unique_key = f"{m_id}_{n_id}"
                
                # Retrieve status from our pre-built map
                status = user_progress_map.get(n_id, {"Blog_Read": False, "Code_Done": False, "Quiz_Done": False})
                
                c1, c2, c3, c4 = st.columns([0.5, 0.16, 0.16, 0.16])
                
                # Title Link
                c1.markdown(f"""
                    <div style="margin-top: 5px;">
                        <a href="{node['URL']}" target="_blank" style="text-decoration: none; color: #00f2ff; font-weight: 600;">
                            {node['Node_Title']} <span style="font-size: 14px;">↗️</span>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
                
                # Action Buttons Helper
                actions = [
                    ("📖 Read", "Blog_Read", "r_", "un_r_"),
                    ("💻 Code", "Code_Done", "c_", "un_c_"),
                    ("❓ Quiz", "Quiz_Done", "q_", "un_q_")
                ]
                
                for label, col_name, btn_pfx, undo_pfx in actions:
                    col_idx = {"Blog_Read": c2, "Code_Done": c3, "Quiz_Done": c4}[col_name]
                    is_done = status.get(col_name, False)
                    
                    with col_idx:
                        if is_done:
                            st.button(label, key=f"{btn_pfx}{unique_key}", disabled=True)
                            if st.button("Undo", key=f"{undo_pfx}{unique_key}", type="tertiary"):
                                reset_granular_progress(email, n_id, col_name)
                        else:
                            if st.button(label, key=f"{btn_pfx}{unique_key}"):
                                update_granular_progress(email, m_id, n_id, col_name, True)

# --- 6. AUTHENTICATION HANDLER ---
def handle_authentication():
    query_params = st.query_params
    url_token = query_params.get("pilot_token", "").lower().strip()
    
    if url_token and (not st.session_state.authenticated or st.session_state.user_email != url_token):
        registry = get_cleaned_registry()
        user_match = registry[registry['Email'] == url_token]
        
        if not user_match.empty:
            st.session_state.authenticated = True
            st.session_state.user_email = url_token
            st.session_state.user_name = user_match.iloc[0]['Full_Name']
            st.session_state.user_clearance = user_match.iloc[0]['Clearance']
            
            # Clean URL but keep mission context
            current_mission = query_params.get("mission_id")
            st.query_params.clear()
            if current_mission:
                st.query_params["mission_id"] = current_mission
            return True
    return st.session_state.authenticated

# --- 7. MAIN ROUTER ---
is_logged_in = handle_authentication()
target_mission = st.query_params.get("mission_id")

if target_mission:
    # --- BLOG MODE ---
    # (Optional: Add show_lms_roadmap function here if needed)
    st.title(f"Mission: {target_mission}")
    if not is_logged_in:
        st.info("👋 Please log in to track your progress.")
    st.stop()

else:
    # --- DASHBOARD MODE ---
    if not st.session_state.authenticated:
        # Render Login UI
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.title("Pilot Authorization")
            input_email = st.text_input("Email").strip().lower()
            input_pass = st.text_input("Password", type='password')
            if st.button("Authorize", type="primary", use_container_width=True):
                reg = get_cleaned_registry()
                user = reg[reg['Email'] == input_email]
                if not user.empty and hash_password(input_pass) == user.iloc[0]['Password_Hash']:
                    st.session_state.authenticated = True
                    st.session_state.user_email = input_email
                    st.session_state.user_name = user.iloc[0]['Full_Name']
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
    else:
        # Full Dashboard
        st.markdown(f"## Welcome Back, {st.session_state.user_name}")
        render_dynamic_navigator(st.session_state.user_email)