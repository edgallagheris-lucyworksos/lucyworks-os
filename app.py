import json
from datetime import datetime
import streamlit as st

from lucyworks.models import CaseInput
from lucyworks.triage import run_triage
from lucyworks.ethics import run_ethics
from lucyworks.rota import rota_assign
from lucyworks.rota_store import load_staff, append_assignment
from lucyworks.discharge import build_discharge
from lucyworks.severity import assess_severity
from lucyworks.audit import audit_event
from lucyworks.trace import trace_event
from lucyworks.policies import show_policies
from lucyworks.pulse import pulse_dashboard, rota_dashboard
from lucyworks.dashboard_map import dashboard_map_table
from lucyworks.room_state import default_room_state_table
from lucyworks.staff import default_staff_type_table
from lucyworks.intake import intake_status_table
from lucyworks.alerts import default_alert_table

st.set_page_config(page_title='LucyWorks OS', layout='wide')
st.title('LucyWorks OS — Full Model Pack')
st.caption('Prototype shell + full model scaffold')

page = st.sidebar.radio('Page', ['Intake Prototype','Master Rota','Pulse Dashboard','Full Model Map','Policies'], index=0)
mode = st.sidebar.selectbox('Mode', ['TRAINING', 'LIVE'], index=0)
reviewer_name = st.sidebar.text_input('Reviewer / clinician name')
override_reason = st.sidebar.text_area('Override / acknowledgement reason')

def export_case_bundle(case_obj, triage_out, ethics_out, rota_out, severity_out, discharge_out):
    bundle = {
        'case': case_obj.to_dict(),
        'triage': triage_out.to_dict(),
        'ethics': ethics_out.to_dict(),
        'rota': rota_out.to_dict(),
        'severity': severity_out.to_dict(),
        'discharge': discharge_out.to_dict(),
        'exported_at': datetime.utcnow().isoformat() + 'Z',
    }
    return json.dumps(bundle, indent=2)

if page == 'Intake Prototype':
    st.info('Root file uploaded. Next upload lucyworks/, assets/, exports/, docs/, and .github/workflows/.')
elif page == 'Master Rota':
    rota_dashboard(st)
elif page == 'Pulse Dashboard':
    pulse_dashboard(st)
elif page == 'Full Model Map':
    st.subheader('Full model map')
    st.dataframe(default_staff_type_table(), use_container_width=True)
    st.dataframe(intake_status_table(), use_container_width=True)
    st.dataframe(default_room_state_table(), use_container_width=True)
    st.dataframe(default_alert_table(), use_container_width=True)
    st.dataframe(dashboard_map_table(), use_container_width=True)
else:
    show_policies(st)
