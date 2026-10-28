# 02 · Onshape assembly setup (the conventions that make joints)

`onshape-to-robot` reads the assembly with strict rules. This document explains
what applies to **this** document and what was already done.

## The document has two important assembly tabs

| Tab | Element id | Role |
|---|---|---|
| **UR10** | `38aaf680dcf8908fc89106f1` | ✅ **the robot** — 13 instances + the 6 revolute mates → **this is what we export** |
| **Whole setup** | `cc7de4642507bd78d72d7b5e` | table + stand + tube extender + glory machine, all `FASTENED` (0 movable mates) → static scene, *not* exported |

`export/config.json` → `"url"` must point at the **UR10** tab
(https://cad.onshape.com/documents/bffb4cd2fd50e50786659d67/w/3349bfe1f84bd89ee3f7e342/e/38aaf680dcf8908fc89106f1).

## Naming rules (how CAD becomes a robot)

| Onshape feature name | Meaning for the exporter |
|---|---|
| `dof_<name>` | **→ a joint.** Revolute/Cylindrical mate ⇒ revolute joint, Slider ⇒ prismatic, Fastened ⇒ fixed joint. The exported joint is `<name>`. |
| `<name>_inv` suffix (e.g. `dof_elbow_inv`) | invert the joint axis direction |
| `fix_<name>` | merge two bodies into one link |
| `frame_<name>` | add a TF frame (dummy link, e.g. tool tip) |
| `link_<name>` (mate **connector**) | rename the link it is attached to |
| any other mate | **ignored** (bodies stay separate → orphans get fixed to the base with a warning) |
| mate **group** | all its occurrences are merged into one rigid link |

Additional rules:

* The **first instance** in the assembly tree becomes the **base link**
  (currently `Base <2>` — correct for the UR10).
* Joint axes are always the mate's **Z axis**.
* Joint limits defined on the mate (limits enabled checkbox) are exported into
  the URDF `<limit>` tag. Without them the exporter uses ±π and the values from
  `joint_properties` in `export/config.json`.

## Renaming the mates — do it in the Onshape UI ✅

> ⚠️ **Never rename mates through the API.** `POST .../features/featureid/{fid}`
> regenerates the mate's implicit connector IDs while its queries still point
> at the old ones → the mate goes into **ERROR** state, the assembly API then
> reports `matedEntities: []`, and onshape-to-robot exports **0 joints**.
> (This actually happened during setup — recovery: see `docs/05_troubleshooting.md`.)
> A UI rename only changes the name field, nothing else — it is always safe.

In the **UR10** tab, double-click each revolute mate, edit the name, confirm:

| Rename to | Resulting URDF joint |
|---|---|
| `dof_Revolute_base` | `Revolute_base` |
| `dof_shoulder` | `shoulder` |
| `dof_elbow` | `elbow` |
| `dof_Revolute_2` | `Revolute_2` |
| `dof_Revolute_3` | `Revolute_3` |
| `dof_Revolute_4` | `Revolute_4` |

Rules: prefix `dof_`, **no spaces** (use `_`), suffix `_inv` to invert an axis.
~15 seconds per mate. `scripts/rename_mates.py` (API version) is intentionally
disabled.

## Verify before every export

```bash
make inspect
```

Must end with:

```
 Joints that WILL be exported : 6
   - Revolute_base
   - shoulder
   - elbow
   - Revolute_2
   - Revolute_3
   - Revolute_4
[OK] All expected DOFs present — ready for export.
```

## If something is missing

* **0 joints / "no revolute mates at the ROOT"** → the mates live inside a
  subassembly. Joints must be mates of the *top-level* assembly whose
  instances are the robot links.
* **Only some joints** → check for suppressed mates or missing `dof_` prefix
  (`make inspect` prints the exact renames needed).
* **Wrong rotation direction** → add the `_inv` suffix in Onshape
  (`dof_Revolute_2_inv`) and re-export, or ignore it in RViz for the demo.
* **`table`/`glory` geometry visible in RViz** → adjust the `ignore`
  wildcards in `export/config.json` (part names are listed by `make inspect`
  and in `export/inspect/*.json`).
