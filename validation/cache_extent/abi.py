"""Check the single scalar ABI extension against an existing cache XO."""

import xml.etree.ElementTree as ET

from validation.grasu_complete.abi import members

NS = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}


def snapshot(contents):
    kernel = ET.fromstring(contents["kernel.xml"]).find("kernel")
    ip = ET.fromstring(contents["component.xml"])
    if kernel is None or kernel.get("name") != "process_cache":
        raise ValueError("one process_cache kernel required")
    registers = {}
    for node in ip.findall("s:memoryMaps/s:memoryMap/s:addressBlock/s:register", NS):
        name = node.findtext("s:name", namespaces=NS)
        if name in registers:
            raise ValueError("duplicate register")
        registers[name] = {key: node.findtext("s:" + key, namespaces=NS)
                           for key in ("addressOffset", "size", "access")}
    wires = {}
    for node in ip.findall("s:model/s:ports/s:port", NS):
        name = node.findtext("s:name", namespaces=NS)
        if name in wires:
            raise ValueError("duplicate wire")
        wires[name] = {key: node.findtext("s:wire/" + path, namespaces=NS)
                       for key, path in (("direction", "s:direction"),
                                         ("left", "s:vector/s:left"),
                                         ("right", "s:vector/s:right"))}
    buses = {node.findtext("s:name", namespaces=NS):
             [(item.findtext("s:logicalPort/s:name", namespaces=NS),
               item.findtext("s:physicalPort/s:name", namespaces=NS))
              for item in node.findall("s:portMaps/s:portMap", NS)]
             for node in ip.findall("s:busInterfaces/s:busInterface", NS)}
    return {"protocol": kernel.get("hwControlProtocol"),
            "arguments": [dict(node.attrib) for node in kernel.findall("args/arg")],
            "ports": {node.get("name"): dict(node.attrib) for node in kernel.findall("ports/port")},
            "registers": registers, "wires": wires, "buses": buses}


def compare(candidate, reference):
    actual, expected = snapshot(candidate), snapshot(reference)
    count = len(expected["arguments"])
    if count not in (2, 3) or actual["protocol"] != "ap_ctrl_chain":
        raise ValueError("plain/token legacy ABI required")
    scalar = {"name": "valid_segments", "addressQualifier": "0", "id": str(count),
              "port": "S_AXI_CONTROL", "size": "0x4", "offset": "0x1C",
              "hostOffset": "0x0", "hostSize": "0x4", "type": "unsigned int"}
    if actual["arguments"] != expected["arguments"] + [scalar]:
        raise ValueError("unexpected cache argument change")
    expected["arguments"].append(scalar)
    if expected["ports"]["S_AXI_CONTROL"]["range"] != "0x1C":
        raise ValueError("unexpected legacy control aperture")
    expected["ports"]["S_AXI_CONTROL"]["range"] = "0x24"
    expected["registers"]["valid_segments"] = {
        "addressOffset": "28", "size": "32", "access": "write-only"}
    for name in ("s_axi_control_ARADDR", "s_axi_control_AWADDR"):
        if expected["wires"][name]["left"] != "4":
            raise ValueError("unexpected legacy control address width")
        expected["wires"][name]["left"] = "5"
    if actual != expected:
        changed = [key for key in expected if actual[key] != expected[key]]
        raise ValueError("unexpected physical ABI change: " + repr(changed))
    return {"status": "CACHE_EXTENT_ABI_PASS", "legacy_arguments": count,
            "added_argument": scalar, "unchanged_axi_masters_streams_and_existing_registers": True,
            "board_tested": False}


def review(candidate, reference):
    return compare(members(candidate, "process_cache"), members(reference, "process_cache"))
