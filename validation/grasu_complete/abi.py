"""Review production XOs against frozen routed search/token-cache interfaces."""

import xml.etree.ElementTree as ET
from zipfile import ZipFile

from spine_cycle_sim.experiments.evaluation_impact.common_g.search_binding import abi as search
from spine_cycle_sim.experiments.evaluation_impact.common_g.cache_probe import binding_abi as cache


def members(path, top):
    with ZipFile(path) as archive:
        names = search.exported_members(archive, top)
        if archive.testzip() is not None or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError("corrupt or duplicate XO archive members")
        return {name: archive.read(member) for name, member in names.items()}


def plain(contents, token_kernel, token_component):
    """The plain control removes only the completion port, not memory/registers."""
    root = ET.fromstring(contents["kernel.xml"])
    nodes = root.findall("kernel")
    if len(nodes) != 1 or nodes[0].get("name") != "process_cache":
        raise ValueError("expected one plain process_cache kernel")
    node = nodes[0]
    arguments = [{key: (search.number(arg.get(key)) if key in
        ("id", "addressQualifier", "offset", "size", "hostSize") else arg.get(key))
        for key in ("id", "name", "port", "addressQualifier", "offset", "size", "hostSize")}
        for arg in node.findall("args/arg")]
    ports = search.unique([{key: (search.number(port.get(key)) if key == "dataWidth" else port.get(key))
        for key in ("name", "portType", "mode", "dataWidth")}
        for port in node.findall("ports/port")], "name")
    expected_ports = {name: port for name, port in token_kernel["ports"].items()
                      if name != "COMPLETION_TOKEN"}
    if (node.get("hwControlProtocol") != "ap_ctrl_chain" or
            arguments != token_kernel["arguments"][:2] or ports != expected_ports):
        raise ValueError("plain cache changed more than the completion port")
    ip = ET.fromstring(contents["component.xml"])
    registers = search.unique([{"name": reg.findtext("s:name", namespaces=search.NS),
        "offset": search.number(reg.findtext("s:addressOffset", namespaces=search.NS)),
        "size": search.number(reg.findtext("s:size", namespaces=search.NS))}
        for reg in ip.findall("s:memoryMaps/s:memoryMap/s:addressBlock/s:register", search.NS)], "name")
    physical = search.unique([{"name": port.findtext("s:name", namespaces=search.NS),
        "direction": port.findtext("s:wire/s:direction", namespaces=search.NS),
        "width": abs(search.number(port.findtext("s:wire/s:vector/s:left", "0", search.NS)) -
                     search.number(port.findtext("s:wire/s:vector/s:right", "0", search.NS))) + 1}
        for port in ip.findall("s:model/s:ports/s:port", search.NS)], "name")
    buses = [bus for bus in ip.findall("s:busInterfaces/s:busInterface", search.NS)
             if bus.find("s:busType", search.NS) is not None]
    axes = [bus for bus in buses if bus.find("s:busType", search.NS).get(
        "{" + search.NS["s"] + "}name") == "axis"]
    if (len(axes) != 1 or axes[0].findtext("s:name", namespaces=search.NS) != "update_stream"
            or axes[0].find("s:slave", search.NS) is None):
        raise ValueError("plain cache must have only the input AXIS slave")
    signals = search.unique([{"name": mapping.findtext("s:logicalPort/s:name", namespaces=search.NS),
        **{key: physical[mapping.findtext("s:physicalPort/s:name", namespaces=search.NS)][key]
           for key in ("direction", "width")}}
        for mapping in axes[0].findall("s:portMaps/s:portMap", search.NS)], "name")
    if registers != token_component["registers"] or signals != token_component["axis"]["update_stream"]:
        raise ValueError("plain cache register map or input AXIS changed")
    return {"kernel": {"protocol": "ap_ctrl_chain", "arguments": arguments, "ports": ports},
            "component": {"registers": registers, "axis": {"update_stream": signals}},
            "derived_plain_contract_pass": True, "matches_routed_cache_abi": False,
            "board_execution_admitted": False}


def review(xo, variant, reference):
    top = "bin_search" if variant == "search" else "process_cache"
    actual = members(xo, top)
    reference_contents = {name: (reference / name).read_bytes()
                          for name in ("kernel.xml", "component.xml")}
    if variant == "search":
        return search.compare(actual["kernel.xml"], actual["component.xml"],
                              reference_contents["kernel.xml"], reference_contents["component.xml"])
    if variant == "cache-token":
        return cache.compare(actual["kernel.xml"], actual["component.xml"],
                             reference_contents["kernel.xml"], reference_contents["component.xml"])
    if variant == "cache-plain":
        return plain(actual, cache.kernel(reference_contents["kernel.xml"]),
                     cache.component(reference_contents["component.xml"]))
    raise ValueError("unknown production ABI variant")
