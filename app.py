import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from faker import Faker
import hashlib
import random

# MISSION_MAP acts as our Content Delivery Router
MISSION_CONTENT = {
    "FOUNDATION": {
        1: "https://projectaiml.com/node-01-python-basics",
        2: "https://projectaiml.com/node-02-pandas-intro",
        3: "https://projectaiml.com/node-03-data-viz",
        4: "https://projectaiml.com/node-04-eda",
        5: "https://projectaiml.com/node-05-foundation-exam"
    },
    "ARCHITECT": {
        1: "https://projectaiml.com/node-01-linear-regression",
        # ... add more nodes as you build them
    }
}

# --- ARCHITECT'S UTILITIES ---
def hash_password(password):
    """Securely hashes passwords before storage."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_auth(email, password, df):
    """Verifies credentials against the Registry."""
    hashed = hash_password(password)
    user_record = df[(df['Email'] == email) & (df['Password_Hash'] == hashed)]
    return not user_record.empty

# --- HIDE ALL PLATFORM BRANDING & WIDGETS ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            /* This targets the status/manage widget in the bottom right */
            [data-testid="stStatusWidget"] {display:none;}
            .viewerBadge_container__1QSob {display:none !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- MISSION CONTROL INITIALIZATION ---
st.set_page_config(page_title="ProjectAIML Launchpad", page_icon="🚀")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def start_mission(email, mission_id):
    """Starts or switches the user's active mission."""
    try:
        all_missions = conn.read(worksheet="User_Missions", ttl=0)
        
        # Check if user already has a record
        mask = (all_missions['Email'] == email)
        
        if mask.any():
            # UPDATE existing record
            all_missions.loc[mask, 'Mission_ID'] = mission_id
            all_missions.loc[mask, 'Current_Node'] = 1
            all_missions.loc[mask, 'Status'] = "Active"
            all_missions.loc[mask, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # CREATE new record (Concat as before)
            new_entry = pd.DataFrame([{
                "Email": email,
                "Mission_ID": mission_id,
                "Current_Node": 1,
                "Status": "Active",
                "Last_Update": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            all_missions = pd.concat([all_missions, new_entry], ignore_index=True)
        
        conn.update(worksheet="User_Missions", data=all_missions)
        st.cache_data.clear()
        st.success(f"Switching Protocol to {mission_id}...")
        st.rerun()
    except Exception as e:
        st.error(f"Navigation Error: {e}")

def render_active_mission(user_state):
    """Visualizes the user's progress and provides navigation to lessons."""
    # Extract data from the user_state row
    email = user_state['Email'].values[0]
    m_id = user_state['Mission_ID'].values[0]
    curr_node = int(user_state['Current_Node'].values[0])
    
    st.markdown(f"## 🛰️ Active Mission: {m_id}")
    
    # Progress Calculation
    total_nodes = 5
    progress_val = curr_node / total_nodes
    
    # UI Elements
    st.progress(progress_val)
    st.write(f"**Current Status:** Node {curr_node} of {total_nodes} Complete.")
    
    # Dynamic Link Generation
    try:
        current_url = MISSION_CONTENT[m_id][curr_node]
        st.info(f"👉 **Your Current Briefing:** [Access Node {curr_node} Lesson]({current_url})")
    except KeyError:
        st.warning("Flight Plan URL not found. Contact Command Center.")

    st.divider()
    
    # Action Button
    if st.button("✅ Mark Node as Complete & Sync Progress"):
        with st.spinner("Syncing data with Global Registry..."):
            complete_current_node(email, curr_node, m_id, total_nodes)

def render_mission_navigator(email, mission_id):
    # 1. Load Manifest (The Map) and Analytics (The User's Path)
    manifest = conn.read(worksheet="Mission_Manifest", ttl=0)
    progress = conn.read(worksheet="Node_Analytics", ttl=0)
    
    # Filter for this specific user and mission
    mission_nodes = manifest[manifest['Mission_ID'] == mission_id]
    user_progress = progress[progress['Email'] == email]

    st.subheader(f"🗺️ {mission_id} Roadmap")
    
    for _, node in mission_nodes.iterrows():
        node_id = node['Node_ID']
        # Check if user has progress for this node
        status = user_progress[user_progress['Node_ID'] == node_id]
        
        with st.expander(f"Node {node_id}: {node['Title']}"):
            col1, col2, col3 = st.columns(3)
            
            # --- Column 1: Blog Reading ---
            is_read = not status.empty and status.iloc[0]['Blog_Read']
            if col1.checkbox("📖 Blog Read", value=is_read, key=f"read_{node_id}"):
                update_granular_progress(email, node_id, "Blog_Read", True)
                
            # --- Column 2: Code Execution ---
            if node['Has_Code']:
                is_code = not status.empty and status.iloc[0]['Code_Done']
                if col2.checkbox("💻 Code Verified", value=is_code, key=f"code_{node_id}"):
                    update_granular_progress(email, node_id, "Code_Done", True)
            
            # --- Column 3: Quiz/Questions ---
            if node['Has_Quiz']:
                is_quiz = not status.empty and status.iloc[0]['Quiz_Done']
                if col3.checkbox("❓ Quiz Mastered", value=is_quiz, key=f"quiz_{node_id}"):
                    update_granular_progress(email, node_id, "Quiz_Done", True)
            
            st.link_button("Open Briefing", node['URL'])

def update_granular_progress(email, mission_id, node_id, column_to_flip, value):
    """Updates specific progress and auto-calculates 'Complete' status."""
    try:
        all_progress = conn.read(worksheet="Node_Analytics", ttl=0)
        
        # Ensure correct data types
        all_progress['Node_ID'] = all_progress['Node_ID'].astype(str)
        
        mask = (all_progress['Email'] == email) & (all_progress['Node_ID'] == str(node_id))
        
        if mask.any():
            all_progress.loc[mask, column_to_flip] = value
            # Fetch current state of the row to check for Auto-Complete
            row = all_progress.loc[mask].iloc[0]
            if row['Blog_Read'] and row['Code_Done'] and row['Quiz_Done']:
                all_progress.loc[mask, 'Complete'] = True
        else:
            # Create new entry with defaults
            new_data = {
                "Email": email, "Mission_ID": mission_id, "Node_ID": node_id,
                "Blog_Read": False, "Code_Done": False, "Quiz_Done": False, "Complete": False
            }
            new_data[column_to_flip] = value
            # Check if this single update completed it (unlikely but safe)
            if new_data["Blog_Read"] and new_data["Code_Done"] and new_data["Quiz_Done"]:
                new_data["Complete"] = True
                
            all_progress = pd.concat([all_progress, pd.DataFrame([new_data])], ignore_index=True)
        
        conn.update(worksheet="Node_Analytics", data=all_progress)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Data Sync Error: {e}")

def render_dynamic_navigator(email):
    """Dynamically renders missions and nodes from the Manifest."""
    manifest = conn.read(worksheet="Mission_Manifest", ttl=0)
    analytics = conn.read(worksheet="Node_Analytics", ttl=0)
    
    # Get unique missions from the manifest
    missions = manifest['Mission_ID'].unique()
    
    with st.expander("📂 Mission Navigator - View All Flight Plans"):
        for m_id in missions:
            st.markdown(f"### 🎯 Protocol: {m_id}")
            nodes = manifest[manifest['Mission_ID'] == m_id]
            
            for _, node in nodes.iterrows():
                n_id = node['Node_ID']
                title = node['Title']
                
                # Get user progress for this node
                user_node_data = analytics[(analytics['Email'] == email) & (analytics['Node_ID'] == n_id)]
                
                # Default states if no record exists yet
                has_read = user_node_data['Blog_Read'].values[0] if not user_node_data.empty else False
                has_code = user_node_data['Code_Done'].values[0] if not user_node_data.empty else False
                has_quiz = user_node_data['Quiz_Done'].values[0] if not user_node_data.empty else False
                is_complete = user_node_data['Complete'].values[0] if not user_node_data.empty else False

                # UI Layout for the Node
                c1, c2, c3, c4, c5 = st.columns([0.1, 0.2, 0.2, 0.2, 0.3])
                
                # Column 1: Overall Status (The Green/Grey Tick)
                c1.write("✅" if is_complete else "⚪")
                
                # Column 2: Blog Read
                if has_read:
                    c2.button("📖 Read", key=f"r_{n_id}", disabled=True, help="Already marked as complete")
                else:
                    if c2.button("📖 Mark Read", key=f"r_{n_id}"):
                        update_granular_progress(email, m_id, n_id, "Blog_Read", True)
                        st.rerun()

                # Column 3: Code Done
                if has_code:
                    c3.button("💻 Coded", key=f"c_{n_id}", disabled=True)
                else:
                    if c3.button("💻 Code Done", key=f"c_{n_id}"):
                        update_granular_progress(email, m_id, n_id, "Code_Done", True)
                        st.rerun()

                # Column 4: Quiz Done
                if has_quiz:
                    c4.button("❓ Quiz", key=f"q_{n_id}", disabled=True)
                else:
                    if c4.button("❓ Quiz Done", key=f"q_{n_id}"):
                        update_granular_progress(email, m_id, n_id, "Quiz_Done", True)
                        st.rerun()
                
                # Column 5: Title and Link
                c5.markdown(f"**{title}** [🔗]({node['URL']})")
            st.divider()

def complete_current_node(email, current_node, mission_id, total_nodes=5):
    """Update Layer: Increments progress for the specific Mission_ID."""
    try:
        all_missions = conn.read(worksheet="User_Missions", ttl=0)
        
        # We look for the row matching BOTH Email and Mission_ID
        mask = (all_missions['Email'] == email) & (all_missions['Mission_ID'] == mission_id)
        
        if mask.any():
            new_node = int(current_node) + 1
            
            if new_node <= total_nodes:
                all_missions.loc[mask, 'Current_Node'] = new_node
                all_missions.loc[mask, 'Last_Update'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"Advancing to Node {new_node}...")
            else:
                all_missions.loc[mask, 'Status'] = "Completed"
                st.balloons()
            
            conn.update(worksheet="User_Missions", data=all_missions)
            st.cache_data.clear()
            st.rerun()
            
    except Exception as e:
        st.error(f"Sync Error: {e}")

# --- SIDEBAR: AUTHENTICATION INTERFACE ---
with st.sidebar:
    st.title("🛰️ Mission Control")
    
    if not st.session_state.authenticated:
        choice = st.radio("Access Level", ["Login", "Register New Pilot"])
        
        email = st.text_input("Email")
        password = st.text_input("Password", type='password')
        
        if choice == "Login":
            if st.button("Authorize Entry"):
                # 1. Fetch the latest registry (bypass cache)
                registry = conn.read(worksheet="User_Registry", ttl=0)
                
                # 2. Standardize inputs
                input_email = email.strip().lower()
                input_hash = hash_password(password)
                
                # 3. Search for the user
                user_row = registry[registry['Email'].str.lower() == input_email]
                
                if not user_row.empty:
                    db_hash = user_row.iloc[0]['Password_Hash']
                    
                    if input_hash == db_hash:
                        # SUCCESS: Update Session State
                        st.session_state.authenticated = True
                        st.session_state.user_email = input_email
                        st.session_state.user_name = user_row.iloc[0]['Full_Name']
                        
                        st.success(f"Welcome back, Pilot {st.session_state.user_name}!")
                        st.rerun() # Refresh to show the Launchpad
                    else:
                        st.error("Access Denied: Incorrect Password.")
                else:
                    st.error("Access Denied: Email not found in Registry.")
        else: # Register
            name = st.text_input("Full Name")
            if st.button("Initialize Protocol"):
                if email.strip() and password.strip() and name.strip():
                    # 1. Fetch existing registry to check for duplicates
                    registry = conn.read(worksheet="User_Registry", ttl=0) # ttl=0 forces a fresh read
                    
                    if email in registry['Email'].values:
                        st.error("This Email is already registered in the Launchpad.")
                    else:
                        # 2. Create the new user row
                        new_user_data = pd.DataFrame([{
                            "Full_Name": name,
                            "Email": email,
                            "Password_Hash": hash_password(password),
                            "Clearance": 1,
                            "Join_Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        
                        # 3. Append and Update
                        updated_registry = pd.concat([registry, new_user_data], ignore_index=True)
                        conn.update(worksheet="User_Registry", data=updated_registry)
                        
                        # 4. CRITICAL: Clear cache so the next Login attempt sees this user
                        st.cache_data.clear()
                        
                        st.success("Protocol Initialized! Pilot Registered. You can now Login.")
                else:
                    st.error("Please fill in all fields to register.")
    else:
        st.write(f"Logged in as: **{st.session_state.user_email}**")
        if st.button("Log Out"):
            st.session_state.authenticated = False
            st.rerun()

    # Push the footer to the bottom
    st.markdown("---")
    st.caption("© 2026 ProjectAIML. All rights reserved.")
    st.caption("Mission Control v1.0.4")

# --- MAIN LAUNCHPAD INTERFACE ---
if st.session_state.authenticated:
    st.title("🚀 ProjectAIML Launchpad")
    
    # 1. THE GLOBAL NAVIGATOR CALL
    # This renders the dynamic accordion list of all missions/nodes
    render_dynamic_navigator(st.session_state.user_email)

    st.divider()

    # 2. CURRENT ACTIVE MISSION FOCUS
    # Fetch User Progress to see if they have a 'Primary' active mission
    mission_data = conn.read(worksheet="User_Missions", ttl=0)
    user_state = mission_data[mission_data['Email'] == st.session_state.user_email]

    if not user_state.empty:
        status = user_state['Status'].values[0]
        if status == "Active":
            # This shows the specific progress bar for the mission they are currently 'on'
            render_active_mission(user_state)

# --- CONFIGURATION ---
# st.set_page_config(page_title="ProjectAIML Data Studio", layout="wide")
fake = Faker()

# --- BACKEND: DATA GENERATION ENGINE ---
def generate_domain_data(domain, num_rows):
    data = []
    for _ in range(num_rows):
        entry = {
            "ID": fake.uuid4()[:8],
            "Date": fake.date_this_year().strftime("%Y-%m-%d"),
            "Client": fake.company()
        }
        if domain == "Insurance":
            entry.update({
                "Policy_Type": random.choice(["Life", "Auto", "Health", "Property"]),
                "Claim_Amount": f"${random.randint(500, 50000)}",
                "Status": random.choice(["Approved", "Pending", "Denied"])
            })
        elif domain == "Legal":
            entry.update({
                "Case_Type": random.choice(["Litigation", "Corporate", "Patent", "Family"]),
                "Attorney": f"Esq. {fake.last_name()}",
                "Filing_Status": random.choice(["Filed", "Discovery", "Settled", "Closed"])
            })
        # Add Healthcare/Retail blocks here as needed...
        data.append(entry)
    return pd.DataFrame(data)

# --- UI & SUBMISSION LOGIC ---
st.title("🚀 ProjectAIML.com | Data Studio")
st.write("Generate high-precision synthetic data for your AI models.")

# 1. Sidebar Settings
with st.sidebar:
    st.header("Settings")
    industry = st.selectbox("Select Industry", ["Insurance", "Legal"])
    rows = st.slider("Number of Rows", 10, 500, 50)

# 2. Lead Capture Form
with st.form("email_capture"):
    st.subheader("🔑 Unlock Download")
    user_email = st.text_input("Enter your business email to generate & download:")
    submitted = st.form_submit_button("Generate Data")


if submitted:
    if "@" in user_email and "." in user_email:
        # A. Save to Google Sheets
        try:
            #conn = st.connection("gsheets", type=GSheetsConnection)
            # Read existing to append
            existing_data = conn.read(ttl=0) 
            new_lead = pd.DataFrame([{
                "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Email": user_email,
                "Industry": industry
            }])
            updated_df = pd.concat([existing_data, new_lead], ignore_index=True)
            conn.update(data=updated_df)
            
            # B. Generate the actual data
            df_result = generate_domain_data(industry, rows)
            
            st.success(f"Verified! Your {industry} dataset is ready.")
            st.dataframe(df_result)
            
            # C. Provide Download Button
            csv = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"projectaiml_{industry.lower()}_data.csv",
                mime='text/csv',
            )
        except Exception as e:
            st.error(f"Connection Error: {e}. Check your secrets.toml!")
    else:
        st.warning("Please enter a valid email address to proceed.")


# --- PERSISTENCE ---
# This ensures that even if the page refreshes, the data stays if they've already unlocked it.
if 'unlocked' not in st.session_state:
    st.info("Form submission is required to access the Data Engine.")