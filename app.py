import streamlit as st
from modules.model import load_model, mask_text
from modules.redaction import redact_pdf, redact_txt_file
import os
import torch

# Base directory and upload folder
base_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(base_dir, "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Load NER model
pipe = load_model(base_dir)

# Streamlit UI
st.title("PIIs Redaction Tool")

# Main Content
tab1, tab2 = st.tabs(["Text Input", "File Upload"])

# Text Input Tab
with tab1:
    st.subheader("Redact Text")

    text = """
Dear Team,

I wanted to share the contact details for our new hires starting next week:

Sarah Johnson will be joining our marketing team. Her email is sarah.johnson@techcorp.com and her phone number is (415) 555-2847. She lives at 742 Evergreen Terrace, San Francisco, CA 94102. For payroll setup, her SSN is 123-45-6789 and her date of birth is March 15, 1985.

Michael Chen from engineering can be reached at m.chen@techcorp.com or 650-555-9832. His home address is 1856 Oak Boulevard, Palo Alto, CA 94301. His driver's license number is D1234567 for parking access, and his employee ID will be EMP-2024-0892.

For security badge access, we'll need Robert Williams' information. His personal email is robwilliams1990@gmail.com, work email will be r.williams@techcorp.com. His credit card ending in 4532 is on file for travel expenses. Rob's passport number A2345678 has been verified for international travel.

Please ensure all onboarding paperwork is complete by Friday. Their bank account details for direct deposit are: Sarah uses account 987654321 at Wells Fargo, Michael's account is 456789012 at Chase, and Robert banks with account 234567890 at Bank of America.

Best regards,
HR Team
    """

    input_text = st.text_area("Enter text to mask PII",
                              text,
                              height=150)
    
    if st.button("Mask Text"):
        if not input_text:
            st.error("Please enter some text to mask.")
        else:
            with st.spinner("Processing..."):
                try:
                    redacted_text = mask_text(pipe, input_text)
                    st.text_area("Redacted Output", redacted_text, height=150, disabled=True)
                    # Add download button for the processed text
                    st.download_button(
                        label="Download Redacted Text",
                        data=redacted_text,
                        file_name="redacted_text.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Processing failed: {str(e)}")

# File Upload Tab
with tab2:
    st.subheader("Redact File")
    uploaded_file = st.file_uploader("Upload a file (PDF, TXT)", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        # Use session state to cache results and avoid reprocessing
        if 'processed_file' not in st.session_state or st.session_state.processed_file != uploaded_file.name:
            with st.spinner("Processing file..."):
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                try:
                    if file_ext == '.pdf':
                        # Read file bytes once and cache
                        file_bytes = uploaded_file.read()
                        uploaded_file.seek(0)  # Reset for potential re-read
                        
                        # Create BytesIO object for processing
                        from io import BytesIO
                        file_copy = BytesIO(file_bytes)
                        pdf_output, redacted_text = redact_pdf(pipe, file_copy)
                        
                        # Store in session state
                        st.session_state.processed_file = uploaded_file.name
                        st.session_state.pdf_output = pdf_output
                        st.session_state.redacted_text = redacted_text
                    
                    elif file_ext == '.txt':
                        redacted_text = redact_txt_file(pipe, uploaded_file)
                        st.session_state.processed_file = uploaded_file.name
                        st.session_state.redacted_text = redacted_text
                        
                except Exception as e:
                    st.error(f"Processing failed: {str(e)}")
        
        # Display cached results
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext == '.pdf' and 'pdf_output' in st.session_state:
            st.text_area("Redacted PDF Text", st.session_state.redacted_text, height=150, disabled=True)
            st.download_button("Download Redacted PDF", st.session_state.pdf_output, file_name=f"redacted_{uploaded_file.name}", mime="application/pdf")
        elif file_ext == '.txt' and 'redacted_text' in st.session_state:
            st.text_area("Redacted TXT", st.session_state.redacted_text, height=150, disabled=True)
            st.download_button("Download Redacted TXT", st.session_state.redacted_text, file_name=f"redacted_{uploaded_file.name}", mime="text/plain")