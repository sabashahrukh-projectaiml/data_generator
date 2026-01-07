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
    """Creates a new record in the User_Missions worksheet to track progress."""
    try:
        # 1. Fetch current mission table
        all_missions = conn.read(worksheet="User_Missions", ttl=0)
        
        # 2. Create the new mission record
        new_entry = pd.DataFrame([{
            "Email": email,
            "Mission_ID": mission_id,
            "Current_Node": 1,  # Always start at Node 1
            "Status": "Active",
            "Last_Update": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        
        # 3. Concatenate and Update Google Sheets
        updated_missions = pd.concat([all_missions, new_entry], ignore_index=True)
        conn.update(worksheet="User_Missions", data=updated_missions)
        
        # 4. Clear cache to reflect the new state and refresh UI
        st.cache_data.clear()
        st.success(f"Protocol {mission_id} Initialized. Good luck, Pilot!")
        st.rerun()
        
    except Exception as e:
        st.error(f"Mission Control Error: {e}")

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

# --- MAIN LAUNCHPAD INTERFACE ---
if st.session_state.authenticated:
    st.title("🚀 ProjectAIML Launchpad")
    
    # 1. Fetch User Progress from 'User_Missions'
    mission_data = conn.read(worksheet="User_Missions", ttl=0)
    user_state = mission_data[mission_data['Email'] == st.session_state.user_email]

    if user_state.empty:
        st.subheader("Welcome, Pilot. Select your first Flight Plan to begin.")
        
        col1, col2 = st.columns(2)

        with col1:
            st.info("### 🛠️ The Foundation Protocol")
            st.write("Master the core data science stack: Python, Pandas, and Data Visualization.")
            if st.button("Initialize Foundation"):
                # Call the backend function we're about to write
                start_mission(st.session_state.user_email, "FOUNDATION")

        with col2:
            st.success("### 🧠 The Model Architect")
            st.write("Advance to predictive modeling, optimization, and architectural decisions.")
            if st.button("Initialize Architect"):
                start_mission(st.session_state.user_email, "ARCHITECT")
    
    else:
        # This is where we will render the progress bar in the next step
        st.write("### Active Mission Detected. Resuming Flight...")
        # render_active_mission(user_state)

        # 2. Extract current mission details
        status = user_state['Status'].values[0]
        curr_node = int(user_state['Current_Node'].values[0])
        m_id = user_state['Mission_ID'].values[0] # <--- CRITICAL NEW VARIABLE

        if status == "Active":
            # 3. Render the UI
            render_active_mission(user_state) 
            
            # 4. The Action Button (if not already inside render_active_mission)
            # If you are calling the function directly:
            #if st.button("Complete Node"):
            #    complete_current_node(
            #        st.session_state.user_email, 
            #        curr_node, 
            #        m_id,           # <--- NEW PARAMETER ADDED
            #        total_nodes=5
            #    )

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