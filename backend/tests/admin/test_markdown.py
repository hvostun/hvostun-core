from app.admin.markdown import markdown_filter, render_markdown


def test_markdown_renders_emphasis_lists_and_fenced_code() -> None:
    html = render_markdown("**жирный**\n\n- пункт\n\n```\nкод\n```")
    assert "<strong>жирный</strong>" in html
    assert "<li>пункт</li>" in html
    assert "<pre><code>код" in html


def test_markdown_strips_script_and_javascript_links() -> None:
    html = render_markdown(
        "<script>alert(1)</script>\n\n[ссылка](javascript:alert(1))\n\n"
        "[сайт](https://example.com)"
    )
    assert "<script" not in html
    assert "javascript:" not in html
    assert 'href="https://example.com"' in html
    assert "noopener" in html


def test_markdown_filter_marks_html_safe_and_skips_blank() -> None:
    rendered = markdown_filter("# Заголовок")
    assert "<h1>Заголовок</h1>" in str(rendered)
    assert rendered.__html__() == str(rendered)
    assert str(markdown_filter("  ")) == ""
    assert str(markdown_filter(None)) == ""
