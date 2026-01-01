# Arrow Detection Logic - Exit Side + Arrowhead Direction

## Overview

This document describes the new arrow detection approach using two simple, unambiguous parameters:
1. **exit_side** - Which side of the cell the arrow exits from
2. **arrowhead_direction** - Which direction the arrowhead points

This approach is more reliable because it asks the model two simple, independent questions instead of asking it to identify complex L-shaped patterns.

---

## Input Parameters

### 1. exit_side (Required)
Which side/edge of the cell does the arrow EXIT from?

| Value | Description |
|-------|-------------|
| `"top"` | Arrow exits from the top edge |
| `"bottom"` | Arrow exits from the bottom edge |
| `"left"` | Arrow exits from the left edge |
| `"right"` | Arrow exits from the right edge |

### 2. arrowhead_direction (Required)
Which direction does the ARROWHEAD point?

| Value | Description |
|-------|-------------|
| `"up"` | Arrowhead points upward |
| `"down"` | Arrowhead points downward |
| `"left"` | Arrowhead points left |
| `"right"` | Arrowhead points right |

### 3. position_in_side (Optional - for split cells)
Where along the exit side is the arrow located?

| Value | Description |
|-------|-------------|
| `"start"` | Beginning of the side (top/left depending on orientation) |
| `"middle"` | Center of the side |
| `"end"` | End of the side (bottom/right depending on orientation) |

This is used to associate arrows with the correct clue in split cells (cells containing two clues).

---

## Calculation Logic

### Rule: Determining Arrow Type

```
IF exit_side direction == arrowhead_direction:
    -> STRAIGHT arrow (offset = writing = that direction)
ELSE:
    -> L-SHAPED arrow:
       - offset_direction = exit_side (converted to direction)
       - writing_direction = arrowhead_direction
```

### Exit Side to Direction Mapping

| exit_side | Equivalent Direction |
|-----------|---------------------|
| `"top"` | `"up"` |
| `"bottom"` | `"down"` |
| `"left"` | `"left"` |
| `"right"` | `"right"` |

---

## Complete Truth Table

| exit_side | arrowhead_direction | Arrow Type | offset_direction | writing_direction | Internal Format |
|-----------|---------------------|------------|------------------|-------------------|-----------------|
| bottom | down | STRAIGHT | down | down | `straight-down` |
| bottom | right | L-SHAPED | down | right | `start-down-turn-right` |
| bottom | left | L-SHAPED | down | left | `start-down-turn-left` |
| bottom | up | INVALID* | - | - | - |
| top | up | STRAIGHT | up | up | `straight-up` |
| top | right | L-SHAPED | up | right | `start-up-turn-right` |
| top | left | L-SHAPED | up | left | `start-up-turn-left` |
| top | down | INVALID* | - | - | - |
| right | right | STRAIGHT | right | right | `straight-right` |
| right | down | L-SHAPED | right | down | `start-right-turn-down` |
| right | up | L-SHAPED | right | up | `start-right-turn-up` |
| right | left | INVALID* | - | - | - |
| left | left | STRAIGHT | left | left | `straight-left` |
| left | down | L-SHAPED | left | down | `start-left-turn-down` |
| left | up | L-SHAPED | left | up | `start-left-turn-up` |
| left | right | INVALID* | - | - | - |

*INVALID combinations (arrow pointing back into the cell) should not occur in valid crossword puzzles.

---

## Visual Examples

### Straight Arrows

```
STRAIGHT DOWN (exit_side=bottom, arrowhead=down):
+-------+
|  clue |
|   |   |
+---|---+
    v

STRAIGHT RIGHT (exit_side=right, arrowhead=right):
+-------+
|  clue |-->
+-------+
```

### L-Shaped Arrows

```
L-SHAPE: exit_side=right, arrowhead=down
+-------+
|  clue |---+
+-------+   |
            v
Result: offset=right, writing=down

L-SHAPE: exit_side=bottom, arrowhead=right
+-------+
|  clue |
+---|---+
    |
    +---->
Result: offset=down, writing=right

L-SHAPE: exit_side=left, arrowhead=down
    +-------+
+---|  clue |
|   +-------+
v
Result: offset=left, writing=down
```

---

## Split Cell Handling

For cells with two clues (split cells), the `position_in_side` parameter indicates which clue the arrow belongs to:

```
+---------------+
| clue1 | clue2 |
+-------|-------+
     |      |
     v      v

Arrow 1: exit_side=bottom, position_in_side=start -> belongs to clue1
Arrow 2: exit_side=bottom, position_in_side=end -> belongs to clue2
```

### Position Mapping by Side

| exit_side | position_in_side=start | position_in_side=end |
|-----------|------------------------|----------------------|
| top | Left portion | Right portion |
| bottom | Left portion | Right portion |
| left | Top portion | Bottom portion |
| right | Top portion | Bottom portion |

---

## JSON Response Format

### Single Arrow
```json
{
  "arrows": [
    {
      "exit_side": "right",
      "arrowhead_direction": "down",
      "position_in_side": "middle",
      "confidence": 0.95
    }
  ]
}
```

### Multiple Arrows (Split Cell)
```json
{
  "arrows": [
    {
      "exit_side": "bottom",
      "arrowhead_direction": "down",
      "position_in_side": "start",
      "confidence": 0.9
    },
    {
      "exit_side": "right",
      "arrowhead_direction": "right",
      "position_in_side": "end",
      "confidence": 0.85
    }
  ]
}
```

### No Arrows
```json
{
  "arrows": []
}
```

---

## Implementation Notes

### Parser Logic (Pseudo-code)

```python
def parse_arrow(arrow_data):
    exit_side = arrow_data['exit_side']
    arrowhead = arrow_data['arrowhead_direction']

    # Convert exit_side to direction
    side_to_direction = {
        'top': 'up',
        'bottom': 'down',
        'left': 'left',
        'right': 'right'
    }
    offset_direction = side_to_direction[exit_side]
    writing_direction = arrowhead

    # Determine arrow type
    if offset_direction == writing_direction:
        # Straight arrow
        return f"straight-{offset_direction}"
    else:
        # L-shaped arrow
        return f"start-{offset_direction}-turn-{writing_direction}"
```

### Validation

Invalid combinations to reject:
- `exit_side=top` + `arrowhead_direction=down` (pointing back into cell)
- `exit_side=bottom` + `arrowhead_direction=up`
- `exit_side=left` + `arrowhead_direction=right`
- `exit_side=right` + `arrowhead_direction=left`

---

## Advantages of This Approach

1. **Unambiguous** - Two independent, simple questions
2. **Easier for AI** - No need to identify complex L-shapes
3. **Supports Split Cells** - position_in_side links arrows to clues
4. **Validation** - Can detect invalid/impossible combinations
5. **Consistent** - Same logic for all arrow types
