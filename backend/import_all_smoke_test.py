"""LucyWorksOS backend module import smoke test.

Ensures core route modules and app entrypoint import without ModuleNotFoundError
or model import crashes.
"""

from importlib import import_module

MODULES = [
    "app.main",
    "app.main_fixed",
    "app.v3_operational_routes",
    "app.dashboard_routes",
    "app.ops_engine_routes",
    "app.input_routes",
    "app.department_routes",
    "app.forecast_routes",
    "app.readiness_routes",
    "app.hr_routes",
    "app.catalogue_routes",
    "app.workspace_routes",
    "app.clinical_director_routes",
    "app.domain_routes",
    "app.episode_state_routes",
    "app.flow_state_routes",
    "app.inpatient_routes",
    "app.live_action_routes",
    "app.mail_ops_routes",
    "app.operating_routes",
    "app.safety_routes",
    "app.startup_routes",
]


def main() -> None:
    for module_name in MODULES:
        import_module(module_name)
        print(f"OK import {module_name}")


if __name__ == "__main__":
    main()
