"""Generates a draw.io diagram (relational tables) from app/models.py.

Usage (from the project root):
    python tools/generate_erd.py

It reads the models with the standard `ast` module, so it does not need SQLAlchemy
or a database. If you change a model, run it again and the diagram stays in sync.
Output: docs/cargaexpress_erd.drawio  (open it in https://app.diagrams.net)
"""

import ast
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "app" / "models.py"
OUTPUT = ROOT / "docs" / "cargaexpress_erd.drawio"

# Layout: each inner list is one row of tables in the diagram.
WMS_LAYOUT = [
    ["brand", "distribution_center", "shipping_type", "region", "carrier"],
    ["orders", "recipient", "order_line", "picking_task", "picking_line"],
    ["shipping_label", "dispatch", "label_line"],
]
TOWER_LAYOUT = [
    ["carrier_status_map", "calendar_day", "sla_rule", "penalty_rule"],
    ["raw_event", "tracking_event", "shipment_status", "unmatched_event"],
    ["shipment_sla", "penalty", "settlement", "carrier_compliance"],
]

TABLE_WIDTH, ROW_HEIGHT, HEADER_HEIGHT = 270, 22, 28
X_STEP, Y_GAP = 320, 70
WMS_COLOR, TOWER_COLOR = "#dae8fc", "#d5e8d4"


def sql_type(node) -> str:
    text = ast.unparse(node)
    simple = {
        "Integer": "INTEGER", "Boolean": "BOOLEAN", "Date": "DATE", "Time": "TIME",
        "UTC_DATETIME": "TIMESTAMPTZ", "JSON_TYPE": "JSONB",
    }
    if text in simple:
        return simple[text]
    if text.startswith("String("):
        return "VARCHAR(" + text[len("String("):-1] + ")"
    if text.startswith("Numeric("):
        return "NUMERIC(" + text[len("Numeric("):-1] + ")"
    return text.upper()


def read_models() -> dict:
    tables = {}
    for node in ast.parse(MODELS.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.ClassDef):
            continue
        name, columns, composite_unique = None, [], set()
        for item in node.body:
            if isinstance(item, ast.Assign) and getattr(item.targets[0], "id", "") == "__tablename__":
                name = item.value.value
            if isinstance(item, ast.Assign) and getattr(item.targets[0], "id", "") == "__table_args__":
                for arg in item.value.elts:
                    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "UniqueConstraint":
                        composite_unique |= {a.value for a in arg.args if isinstance(a, ast.Constant)}
            if isinstance(item, ast.AnnAssign) and isinstance(item.value, ast.Call):
                call, keywords = item.value, {k.arg: k.value for k in item.value.keywords}
                fk, col_type = None, "INTEGER"
                for arg in call.args:
                    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "ForeignKey":
                        fk = arg.args[0].value               # "table.column"
                    else:
                        col_type = sql_type(arg)
                flag = lambda key: isinstance(keywords.get(key), ast.Constant) and keywords[key].value is True
                columns.append({
                    "name": item.target.id, "type": col_type, "fk": fk,
                    "pk": flag("primary_key"), "unique": flag("unique"),
                    "nullable": not (isinstance(keywords.get("nullable"), ast.Constant) and keywords["nullable"].value is False)
                                and not flag("primary_key"),
                })
        if name:
            for column in columns:
                column["unique_alone"] = column["unique"]   # UNIQUE on this column only (1:1)
                column["unique"] = column["unique"] or column["name"] in composite_unique
            tables[name] = columns
    return tables


def row_label(column) -> str:
    tags = [t for t, on in (("PK", column["pk"]), ("FK", column["fk"]), ("UK", column["unique"] and not column["pk"])) if on]
    return f"{', '.join(tags) or '':<9}{column['name']} : {column['type']}" if tags else f"{'':<9}{column['name']} : {column['type']}"


def build_xml(tables: dict) -> str:
    cells, positions, y = [], {}, 90

    def add_section(title, layout, color, y):
        cells.append(
            f'<mxCell id="title_{title}" value={quoteattr(title)} style="text;fontSize=20;fontStyle=1;html=0;" '
            f'vertex="1" parent="1"><mxGeometry x="20" y="{y - 60}" width="600" height="30" as="geometry"/></mxCell>'
        )
        for row in layout:
            tallest = 0
            for index, name in enumerate(row):
                x = 20 + index * X_STEP
                height = HEADER_HEIGHT + ROW_HEIGHT * len(tables[name])
                positions[name] = (x, y)
                tallest = max(tallest, height)
                cells.append(
                    f'<mxCell id="t_{name}" value={quoteattr(name)} style="swimlane;fontStyle=1;childLayout=stackLayout;'
                    f'horizontal=1;startSize={HEADER_HEIGHT};fillColor={color};horizontalStack=0;resizeParent=1;'
                    f'resizeLast=0;collapsible=1;marginBottom=0;swimlaneFillColor=#ffffff;align=center;" '
                    f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{TABLE_WIDTH}" height="{height}" as="geometry"/></mxCell>'
                )
                for position, column in enumerate(tables[name]):
                    bold = "fontStyle=1;" if column["pk"] else ""
                    cells.append(
                        f'<mxCell id="c_{name}_{column["name"]}" value={quoteattr(row_label(column))} '
                        f'style="text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=4;'
                        f'spacingRight=4;overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                        f'fontFamily=Courier New;fontSize=11;{bold}" vertex="1" parent="t_{name}">'
                        f'<mxGeometry y="{HEADER_HEIGHT + ROW_HEIGHT * position}" width="{TABLE_WIDTH}" height="{ROW_HEIGHT}" as="geometry"/></mxCell>'
                    )
            y += tallest + Y_GAP
        return y

    y = add_section("WMS (operational model)", WMS_LAYOUT, WMS_COLOR, y)
    y = add_section("Control tower (tracking, SLA, penalties, settlements)", TOWER_LAYOUT, TOWER_COLOR, y + 60)

    placed = {name for row in WMS_LAYOUT + TOWER_LAYOUT for name in row}
    assert placed == set(tables), f"tables missing in the layout: {set(tables) ^ placed}"

    # Relationships: parent PK row -> child FK row.
    edge_count = 0
    for child, columns in tables.items():
        pk_names = [c["name"] for c in columns if c["pk"]]
        for column in columns:
            if not column["fk"]:
                continue
            parent, parent_column = column["fk"].split(".")
            one_to_one = (column["pk"] and len(pk_names) == 1) or (column["unique_alone"] and not column["pk"])
            end = "ERone" if one_to_one else ("ERzeroToMany" if column["nullable"] else "ERmany")
            edge_count += 1
            cells.append(
                f'<mxCell id="e_{child}_{column["name"]}" value="" style="edgeStyle=entityRelationEdgeStyle;fontSize=12;'
                f'html=1;endArrow={end};startArrow=ERmandOne;endFill=0;startFill=0;strokeColor=#666666;" edge="1" '
                f'parent="1" source="c_{parent}_{parent_column}" target="c_{child}_{column["name"]}">'
                f'<mxGeometry relative="1" as="geometry"/></mxCell>'
            )

    legend = (
        "Legend: PK = primary key, FK = foreign key, UK = unique. "
        "Crow's foot = many, single bar = one (1:1 when the FK is also PK or unique). "
        "unmatched_event.carrier_id has no FK on purpose."
    )
    cells.append(
        f'<mxCell id="legend" value={quoteattr(legend)} style="text;whiteSpace=wrap;html=0;fontSize=12;" vertex="1" parent="1">'
        f'<mxGeometry x="20" y="{y}" width="1400" height="40" as="geometry"/></mxCell>'
    )
    xml = (
        '<mxfile host="app.diagrams.net"><diagram name="CargaExpress ERD" id="cargaexpress-erd">'
        '<mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
        'fold="1" page="0" pageScale="1" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>"
    )
    print(f"{len(tables)} tables, {edge_count} relationships")
    return xml


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(build_xml(read_models()), encoding="utf-8")
    print(f"Written: {OUTPUT.relative_to(ROOT)}")
