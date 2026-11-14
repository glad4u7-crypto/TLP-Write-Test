import io
import stat
import unicodedata
import zipfile

import pytest

from core.repository_inspector import InspectionError, inspect_zip


def make_zip(items):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in items:
            archive.writestr(name, content)
    return buffer.getvalue()


def test_inspects_text_files_without_returning_source_content():
    report = inspect_zip(make_zip([("src/app.py", "print('hello')\n")]))
    assert report.total_files == 1
    assert report.text_files == 1
    assert report.files[0].path == "src/app.py"
    assert report.files[0].line_count == 1
    assert "hello" not in str(report.to_dict())


def test_rejects_empty_and_invalid_archives():
    with pytest.raises(InspectionError, match="non-empty"):
        inspect_zip(b"")
    with pytest.raises(InspectionError, match="valid ZIP"):
        inspect_zip(b"not a zip")


@pytest.mark.parametrize("name", ["../outside.py", "/absolute.py", "C:/outside.py", "folder\\outside.py"])
def test_rejects_unsafe_paths(name):
    with pytest.raises(InspectionError, match="unsafe file path"):
        inspect_zip(make_zip([(name, "print('x')")]))


def test_skips_sensitive_files_without_reading_them():
    report = inspect_zip(make_zip([(".env", "SECRET_TOKEN=do-not-show-this-value")]))
    assert report.skipped_files == 1
    assert "do-not-show-this-value" not in str(report.to_dict())
    assert "sensitive configuration file skipped" in report.findings[0]


def test_detects_possible_secrets_but_hides_values():
    report = inspect_zip(make_zip([("settings.py", 'api_key = "abcdefghijklmnop"\n')]))
    assert any("possible credential value detected" in item for item in report.findings)
    assert "abcdefghijklmnop" not in str(report.to_dict())


def test_flags_risky_code_patterns_without_executing_them():
    report = inspect_zip(make_zip([("runner.py", "import subprocess\nsubprocess.run(['echo', 'x'])\n")]))
    assert any("Process execution pattern found" in item for item in report.findings)


def test_skips_binary_and_non_text_files():
    report = inspect_zip(make_zip([("image.png", b"\x89PNG\x00"), ("data.bin", b"\x00\x01")]))
    assert report.skipped_files == 2
    assert report.text_files == 0


def test_rejects_too_many_entries():
    items = [(f"f{i}.txt", "x") for i in range(501)]
    with pytest.raises(InspectionError, match="too many"):
        inspect_zip(make_zip(items))


def test_rejects_archive_over_upload_limit():
    with pytest.raises(InspectionError, match="10 MB"):
        inspect_zip(b"x" * (10 * 1024 * 1024 + 1))



def make_zip_with_info(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for info, content in entries:
            archive.writestr(info, content)
    return buffer.getvalue()


def test_rejects_symbolic_link_entries():
    link = zipfile.ZipInfo("src/link.py")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(InspectionError, match="symbolic link"):
        inspect_zip(make_zip_with_info([(link, "target.py")]))


@pytest.mark.parametrize(
    "names",
    [
        ["src/app.py", "src/app.py"],
        ["src/App.py", "src/app.py"],
        ["caf\u00e9.py", unicodedata.normalize("NFD", "caf\u00e9.py")],
    ],
)
def test_rejects_duplicate_or_portable_path_collisions(names):
    with pytest.raises(InspectionError, match="duplicate or colliding"):
        inspect_zip(make_zip([(name, "x") for name in names]))


@pytest.mark.parametrize("name", ["src//app.py", "src/./app.py", "src/../app.py", ""])
def test_rejects_empty_and_dot_path_segments(name):
    info = zipfile.ZipInfo(name)
    with pytest.raises(InspectionError, match="unsafe file path"):
        inspect_zip(make_zip_with_info([(info, "x")]))
