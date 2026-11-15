from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_in_safe_local_prototype_mode():
    app = AppTest.from_file("app.py").run()
    assert not app.exception
    assert any("Autonomous AI Agent" in item.value for item in app.title)
    assert any("Local prototype mode" in item.value for item in app.warning)
    assert any("External API: Disabled" in item.value for item in app.markdown)
