import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from faker import Faker
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="ProjectAIML Data Studio", layout="wide")
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
            conn = st.connection("gsheets", type=GSheetsConnection)
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