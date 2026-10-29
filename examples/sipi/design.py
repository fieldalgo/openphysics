"""Save a cross-section and design a stripline width for 50 ohms."""

from sipi import CrossSectionDocument, microstrip, seek_impedance, stripline

section = microstrip(width=1e-3, substrate_height=1e-3, eps_r=4.3, thickness=35e-6)
document = CrossSectionDocument(section, mesh=section.mesh_settings())
restored = CrossSectionDocument.loads(document.dumps())
print(f"Microstrip: {restored.analyze().z0:.3f} ohm")

design = seek_impedance(
    lambda w: stripline(width=w, plane_spacing=1e-3, eps_r=4),
    (0.3e-3, 0.8e-3), 50.0,
    mesh=dict(edge_size=0.5e-6, far_size=0.125e-3, grade=0.075),
    tolerance=0.1, max_evaluations=20)
print(f"Width: {design.parameter * 1e3:.6f} mm")
print(f"Requested/refined: {design.impedance:.6f} / {design.refined_impedance:.6f} ohm")
print(f"Mesh change: {design.mesh_change:+.6f} ohm; {len(design.history)} solves")
