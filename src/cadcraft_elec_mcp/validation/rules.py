"""Validation rules (rule-object pattern). Each rule is independent and reports :class:`Issue` s.

Add a rule = add a class with ``id``/``description`` and ``check`` and list it in ``ALL_RULES``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from ..domain.designation import split_terminal_ref
from ..domain.model import DeviceKind, Project
from ..domain.potentials import infer_potential_kind
from ..generators.context import Wire
from ..generators.crossref import CrossRefRegistry
from ..layout import CabinetPlan
from ..standards import StandardProfile


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: Severity
    message: str
    ref: str = ""


@dataclass
class ValidationContext:
    project: Project
    profile: StandardProfile
    wires: list[Wire] = field(default_factory=list)
    xrefs: CrossRefRegistry | None = None
    plan: CabinetPlan | None = None
    sized_from_default: list[str] = field(default_factory=list)


class Rule:
    id: ClassVar[str]
    description: ClassVar[str]

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:  # pragma: no cover - interface
        raise NotImplementedError

    def issue(self, severity: Severity, message: str, ref: str = "") -> Issue:
        return Issue(self.id, severity, message, ref)


class UniqueTags(Rule):
    id = "unique_tags"
    description = "Every device designation is unique (IEC 81346-1)."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        for tag, count in Counter(d.tag for d in ctx.project.devices).items():
            if count > 1:
                yield self.issue(Severity.ERROR, f"Designation {tag} used by {count} devices.", tag)


class DesignationCodes(Rule):
    id = "designation_codes"
    description = "Designation letter code matches the device class of the active profile."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        for device in ctx.project.devices:
            prefix = ctx.profile.tag_prefix(device.kind)
            rest = device.tag[len(prefix) :]
            if not device.tag.startswith(prefix) or (rest and not rest[0].isdigit()):
                yield self.issue(
                    Severity.WARNING,
                    f"{device.tag} ({device.kind.value}) should use the code '{prefix}' "
                    f"({ctx.profile.tag.scheme}).",
                    device.tag,
                )


class References(Rule):
    id = "references"
    description = "Sheets, I/O channels, network links and strips only reference existing devices."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        project = ctx.project
        known = {d.tag for d in project.devices}
        for sheet in project.sheets:
            for path in sheet.paths:
                for element in path.elements:
                    if element.device not in known:
                        yield self.issue(
                            Severity.ERROR, f"Sheet {sheet.id}: unknown device {element.device}.", sheet.id
                        )
            if sheet.plc and sheet.plc not in known:
                yield self.issue(Severity.ERROR, f"Sheet {sheet.id}: unknown PLC {sheet.plc}.", sheet.id)
        for channel in project.plc_io:
            for tag in filter(None, [channel.plc, channel.device]):
                if tag not in known:
                    yield self.issue(
                        Severity.ERROR, f"I/O {channel.address}: unknown device {tag}.", channel.address
                    )
            if channel.strip_terminal:
                strip, _ = split_terminal_ref(channel.strip_terminal)
                if strip not in known:
                    yield self.issue(
                        Severity.ERROR,
                        f"I/O {channel.address}: terminal strip {strip} is not a device.",
                        strip,
                    )
        for link in project.network:
            for tag in (link.a_device, link.b_device):
                if tag not in known:
                    yield self.issue(Severity.ERROR, f"Network link: unknown device {tag}.", tag)


class PlcIoConflicts(Rule):
    id = "plc_io_conflicts"
    description = "No PLC address or module terminal is assigned twice."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        addresses: Counter[tuple[str, str]] = Counter()
        terminals: Counter[tuple[str, str]] = Counter()
        for ch in ctx.project.plc_io:
            addresses[(ch.plc, ch.address.upper())] += 1
            terminals[(ch.plc, ch.terminal)] += 1
        for (plc, address), count in addresses.items():
            if count > 1:
                yield self.issue(Severity.ERROR, f"{plc}: address {address} assigned {count} times.", address)
        for (plc, terminal), count in terminals.items():
            if count > 1:
                yield self.issue(
                    Severity.ERROR, f"{plc}: terminal {terminal} assigned {count} times.", terminal
                )


class NetworkPorts(Rule):
    id = "network_ports"
    description = "Each network port carries one link and exists on the device."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        used: Counter[tuple[str, str]] = Counter()
        for link in ctx.project.network:
            for tag, port in ((link.a_device, link.a_port), (link.b_device, link.b_port)):
                if not port:
                    continue
                used[(tag, port)] += 1
                if ctx.project.has_device(tag):
                    ports = ctx.project.device(tag).ports
                    if ports and port not in ports:
                        yield self.issue(
                            Severity.WARNING,
                            f"{tag} has no port {port} (known: {', '.join(ports)}).",
                            f"{tag}:{port}",
                        )
        for (tag, port), count in used.items():
            if count > 1:
                yield self.issue(Severity.ERROR, f"Port {tag}:{port} used by {count} links.", f"{tag}:{port}")


class TerminalStrips(Rule):
    id = "terminal_strips"
    description = "Terminal numbers are unique per strip."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        for strip in ctx.project.terminal_strips:
            for number, count in Counter(t.number for t in strip.terminals).items():
                if count > 1:
                    yield self.issue(
                        Severity.ERROR,
                        f"{strip.tag}:{number} defined {count} times.",
                        f"{strip.tag}:{number}",
                    )


class TextHeights(Rule):
    id = "text_heights"
    description = "Profile text heights respect the minimum (ISO 3098: 2.5 mm)."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        text = ctx.profile.text
        for name in ("general", "terminal", "wire_number", "designation"):
            value = getattr(text, name)
            if value < text.minimum:
                yield self.issue(
                    Severity.ERROR, f"Text height '{name}' = {value} mm < minimum {text.minimum} mm."
                )


class CabinetFit(Rule):
    id = "cabinet_fit"
    description = "All cabinet devices fit on the plate without overlaps and with spare space."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        plan = ctx.plan
        if plan is None:
            return
        for box in plan.unplaced:
            yield self.issue(Severity.ERROR, f"{box.tag} could not be placed on the plate.", box.tag)
        devices = plan.devices
        for i, a in enumerate(devices):
            if not a.rect.inside(plan.plate):
                yield self.issue(Severity.ERROR, f"{a.box.tag} is outside the plate.", a.box.tag)
            for b in devices[i + 1 :]:
                if a.rect.overlaps(b.rect):
                    yield self.issue(Severity.ERROR, f"{a.box.tag} overlaps {b.box.tag}.", a.box.tag)
            for duct in plan.ducts:
                if a.rect.overlaps(duct):
                    yield self.issue(Severity.ERROR, f"{a.box.tag} overlaps a wire duct.", a.box.tag)
        for warning in plan.warnings:
            yield self.issue(Severity.WARNING, warning)
        for tag in ctx.sized_from_default:
            yield self.issue(Severity.WARNING, f"{tag} has no dimensions; a default size was used.", tag)


class CrossReferences(Rule):
    id = "cross_references"
    description = "Every drawn contact has its coil drawn somewhere (and vice versa)."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        if ctx.xrefs is None:
            return
        masters, slaves = ctx.xrefs.masters(), ctx.xrefs.slaves()
        coil_kinds = {DeviceKind.CONTACTOR, DeviceKind.RELAY, DeviceKind.TIMER_RELAY}
        for device, items in slaves.items():
            if device in masters or not ctx.project.has_device(device):
                continue
            if ctx.project.device(device).kind in coil_kinds:
                yield self.issue(
                    Severity.WARNING,
                    f"Contacts of {device} are drawn ({items[0].ref}) but its coil is not.",
                    device,
                )
        for device, items in masters.items():
            if device not in slaves and ctx.project.device(device).kind in coil_kinds:
                yield self.issue(
                    Severity.INFO, f"Coil {device} ({items[0].ref}) has no contacts drawn.", device
                )


class Potentials(Rule):
    id = "potentials"
    description = "Rails used on sheets are declared potentials (otherwise their kind is guessed)."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        declared = {p.name for p in ctx.project.potentials}
        used = {
            rail for s in ctx.project.sheets for p in s.paths for rail in [*p.supply, p.return_rail] if rail
        }
        for rail in sorted(used - declared):
            yield self.issue(
                Severity.INFO,
                f"Rail {rail} is not declared; assumed {infer_potential_kind(rail).value}.",
                rail,
            )


class UnusedDevices(Rule):
    id = "unused_devices"
    description = "Devices appear on at least one sheet, I/O list, network or cabinet."

    def check(self, ctx: ValidationContext) -> Iterable[Issue]:
        used: set[str] = set()
        for sheet in ctx.project.sheets:
            used.update(e.device for p in sheet.paths for e in p.elements)
            if sheet.plc:
                used.add(sheet.plc)
        for ch in ctx.project.plc_io:
            used.update(filter(None, [ch.plc, ch.device]))
        for link in ctx.project.network:
            used.update([link.a_device, link.b_device])
        used.update(s.tag for s in ctx.project.terminal_strips)
        if ctx.plan:
            used.update(d.box.tag for d in ctx.plan.devices)
        for device in ctx.project.devices:
            if device.tag not in used:
                yield self.issue(Severity.INFO, f"{device.tag} is not used in any drawing.", device.tag)


ALL_RULES: list[Rule] = [
    UniqueTags(),
    DesignationCodes(),
    References(),
    PlcIoConflicts(),
    NetworkPorts(),
    TerminalStrips(),
    TextHeights(),
    CabinetFit(),
    CrossReferences(),
    Potentials(),
    UnusedDevices(),
]
