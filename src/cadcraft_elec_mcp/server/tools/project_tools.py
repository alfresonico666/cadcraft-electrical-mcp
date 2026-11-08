"""MCP tools: projects, potentials, standards."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ...application import projects
from ...application.session import Session
from ...domain.model import DeviceKind, Potential, PotentialKind, TitleBlockInfo
from ...standards import available_profiles, load_profile
from ...symbols import symbols_for_style
from ...validation import describe_rules
from ..annotations import READ, WRITE
from ..errors import tool_errors


def register(server: MCPServer, session: Session) -> None:
    @server.tool(annotations=WRITE)
    @tool_errors
    def project_create(
        project_code: str,
        project_title: str = "",
        profile: str = "iec",
        machine: str = "",
        client: str = "",
        plant: str = "",
        company: str = "",
        author: str = "",
        reviewer: str = "",
        revision: str = "A",
        description: str = "",
        directory: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Create a new electrical project and make it the active one.

        profile: 'iec' (IEC 81346-2:2019 two-letter codes, vertical paths, A3), 'iec_legacy'
        (single-letter -K/-F/-Q codes) or 'nfpa' (NFPA 79 ladder, ANSI B). Standard potentials
        L1 L2 L3 N PE 24V 0V are pre-declared. The project is saved as <code>.elec.yaml in the workspace
        (or in `directory`).
        """
        info = TitleBlockInfo(
            project_code=project_code,
            project_title=project_title,
            machine=machine,
            client=client,
            plant=plant,
            company=company,
            author=author,
            reviewer=reviewer,
            revision=revision,
            description=description,
        )
        return projects.create_project(session, info, profile, directory, overwrite)

    @server.tool(annotations=WRITE)
    @tool_errors
    def project_open(code_or_path: str) -> dict[str, Any]:
        """Open an existing project by code (from the workspace) or by the full path of its .elec.yaml."""
        return projects.open_project(session, code_or_path)

    @server.tool(annotations=READ)
    @tool_errors
    def project_list() -> list[dict[str, str]]:
        """List the projects found in the workspace folder."""
        return session.store.list_projects()

    @server.tool(annotations=READ)
    @tool_errors
    def project_info() -> dict[str, Any]:
        """Summary of the active project: title-block data, counts, potentials, sheets, cabinet."""
        return projects.describe(session)

    @server.tool(annotations=WRITE)
    @tool_errors
    def project_update(
        project_title: str | None = None,
        machine: str | None = None,
        client: str | None = None,
        plant: str | None = None,
        company: str | None = None,
        author: str | None = None,
        reviewer: str | None = None,
        revision: str | None = None,
        date: str | None = None,
        description: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Update title-block fields and/or switch the standards profile (iec / iec_legacy / nfpa)."""
        if profile:
            projects.set_profile(session, profile)
        projects.update_info(
            session,
            {
                "project_title": project_title,
                "machine": machine,
                "client": client,
                "plant": plant,
                "company": company,
                "author": author,
                "reviewer": reviewer,
                "revision": revision,
                "date": date,
                "description": description,
            },
        )
        return projects.describe(session)

    @server.tool(annotations=WRITE)
    @tool_errors
    def potential_set(
        name: str,
        kind: PotentialKind,
        voltage: str = "",
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Declare a potential (rail): e.g. name='24V' kind='dc_plus', or 'L1_CTRL' kind='ac_control'.

        The kind decides the conductor colour on drawings and lists.
        """
        return projects.set_potential(
            session, Potential(name=name, kind=kind, voltage=voltage, source=source)
        )

    @server.tool(annotations=READ)
    @tool_errors
    def standards_info(profile: str | None = None) -> dict[str, Any]:
        """Rules of a standards profile: letter codes per device kind, wire colours, sheet format, text
        heights, terminal marking, available profiles and validation rules."""
        prof = load_profile(profile or (session.project.profile if session.has_project else "iec"))
        return {
            "available_profiles": available_profiles(),
            "name": prof.name,
            "title": prof.title,
            "orientation": prof.orientation,
            "numbering": prof.numbering.value,
            "designation_scheme": prof.tag.scheme,
            "codes": {k.value: prof.tag_prefix(k) for k in DeviceKind},
            "wire_colors": {k.value: v.model_dump() for k, v in prof.wire_colors.items()},
            "cross_sections_mm2": {k.value: v for k, v in prof.cross_sections_mm2.items()},
            "sheet": prof.sheet.model_dump(),
            "text_heights": prof.text.model_dump(),
            "terminal_marking": prof.terminal_marking,
            "validation_rules": describe_rules(),
        }

    @server.tool(annotations=READ)
    @tool_errors
    def symbols_list(style: str = "iec") -> list[dict[str, Any]]:
        """Symbols available for current-path elements (use the id in PathElement.symbol)."""
        return [
            {
                "id": s.id,
                "title": s.title,
                "category": s.category,
                "multi_pole_body": s.spans_poles,
                "ends_path": s.terminal_end,
            }
            for s in symbols_for_style(style).values()
        ]
