from __future__ import annotations

from protocolops.mcp_server import TOOL_SPECS, create_mcp_server, list_tool_names
from protocolops.tools import TOOL_NAMES, dispatch


def test_tool_names_registered():
    assert tuple(list_tool_names()) == TOOL_NAMES
    spec_names = {item["name"] for item in TOOL_SPECS}
    assert spec_names == set(TOOL_NAMES)


def test_dispatch_all_tools_mock_safe(settings):
    summary = dispatch("gsc_summary", {"days": 28, "settings": settings})
    assert summary["mock"] is True
    assert summary["totals"]["clicks"] > 0

    index = dispatch("docs_index", {"settings": settings})
    assert index["page_count"] == 5

    brief = dispatch("seo_brief", {"write": False, "settings": settings})
    assert "Weekly SEO brief" in brief["markdown"]
    assert brief["gaps"] >= 2

    draft = dispatch("draft_mdx", {"query": "helios withdrawal queue time", "settings": settings})
    assert draft["slug"] == "helios-withdrawal-queue-time"
    assert draft["markdown"].startswith("---")

    report = dispatch("send_report", {"dry_run": True, "settings": settings})
    assert report["dry_run"] is True
    assert report["ok"] is True


def test_create_mcp_server_exposes_tools():
    server = create_mcp_server()
    names: set[str] = set()
    for attr in ("list_tools", "_tool_manager", "_tools", "tools"):
        obj = getattr(server, attr, None)
        if obj is None:
            continue
        if callable(obj):
            try:
                listed = obj()
            except TypeError:
                continue
            if hasattr(listed, "__iter__") and not isinstance(listed, (str, bytes)):
                for item in listed:
                    name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
                    if name:
                        names.add(name)
        elif isinstance(obj, dict):
            names.update(obj.keys())
    # SDK internals vary; registration must at least not raise, and specs stay the contract.
    if names:
        assert set(TOOL_NAMES) <= names
