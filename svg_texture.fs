// SVG Texture FeatureScript
// Applies SVGTEX pattern data as 3D raised/recessed textures on Onshape parts.
//
// SVGTEX format (paste from Python preprocessor output):
//   V<minX>,<minY>,<width>,<height>
//   <fillRule><commands>
//   Fill rule: E (evenodd) or N (nonzero)
//   Commands: M x,y | L x,y | C x1,y1,x2,y2,x,y | A cx,cy,r,startDeg,sweepDeg | Z

FeatureScript 2268;
import(path : "onshape/std/common.fs", version : "2268.0");
import(path : "onshape/std/geometry.fs", version : "2268.0");

// ============================================================================
// Section 1: Enums & Constants
// ============================================================================

export enum TextureDirection
{
    annotation { "Name" : "Add" }
    RAISED,
    annotation { "Name" : "Remove" }
    RECESSED
}

export enum MappingMode
{
    annotation { "Name" : "Auto" }
    AUTO,
    annotation { "Name" : "Planar" }
    PLANAR,
    annotation { "Name" : "Cylindrical" }
    CYLINDRICAL
}

// Custom bounds for texture depth (similar to SHELL_OFFSET_BOUNDS)
export const TEXTURE_DEPTH_BOUNDS =
{
    (meter)      : [1e-5, 0.0005, 0.5],
    (centimeter) : 0.05,
    (millimeter) : 0.5,
    (inch)       : 0.02,
    (foot)       : 0.002,
    (yard)       : 0.0006
} as LengthBoundSpec;

// Custom bounds for pattern size
export const TEXTURE_SIZE_BOUNDS =
{
    (meter)      : [1e-5, 0.01, 500],
    (centimeter) : 1.0,
    (millimeter) : 10.0,
    (inch)       : 0.4,
    (foot)       : 0.033,
    (yard)       : 0.011
} as LengthBoundSpec;

// Tile count bounds (matching Onshape's PRIMARY_PATTERN_BOUNDS range)
export const TILE_COUNT_BOUNDS =
{
    (unitless) : [1, 2, 2500]
} as IntegerBoundSpec;

// Maximum sketch entities before warning
const MAX_ENTITIES = 3000;
const ENTITY_WARNING_THRESHOLD = 2500;

/**
 * Editing logic: auto-detect mapping mode when face selection changes.
 */
export function svgTextureEditLogic(context is Context, id is Id,
    oldDefinition is map, definition is map, isCreating is boolean) returns map
{
    // When face selection changes, update mapping mode if set to Auto
    if (oldDefinition.targetFace != definition.targetFace &&
        definition.mappingMode == MappingMode.AUTO)
    {
        var faces = evaluateQuery(context, definition.targetFace);
        if (size(faces) > 0)
        {
            try silent
            {
                var surfDef = evSurfaceDefinition(context, { "face" : definition.targetFace });
                if (surfDef is Cylinder)
                {
                    // Keep Auto — it will resolve at build time
                }
            }
        }
    }
    return definition;
}

// ============================================================================
// Section 2: SVGTEX Parser
// ============================================================================

// Parsed representation of SVGTEX data
type SvgTexData typecheck canBeSvgTexData;
predicate canBeSvgTexData(value)
{
    value is map;
    value.viewBox is map;
    value.paths is array;
}

// A single parsed path
type SvgTexPath typecheck canBeSvgTexPath;
predicate canBeSvgTexPath(value)
{
    value is map;
    value.fillRule is string;
    value.commands is array;
}

// A single command
type SvgTexCommand typecheck canBeSvgTexCommand;
predicate canBeSvgTexCommand(value)
{
    value is map;
    value.cmd is string;
    value.params is array;
}

/**
 * Parse a complete SVGTEX string into structured data.
 */
function parseSvgTex(data is string) returns map
{
    var lines = splitString(data, "\n");
    var viewBox = { "minX" : 0, "minY" : 0, "width" : 100, "height" : 100 };
    var paths = [];

    for (var i = 0; i < size(lines); i += 1)
    {
        var line = trim(lines[i]);
        if (size(line) == 0)
            continue;

        var firstChar = substring(line, 0, 1);

        // Skip comments
        if (firstChar == "#")
            continue;

        // ViewBox header
        if (firstChar == "V")
        {
            viewBox = parseViewBox(line);
        }
        // Path line (E or N prefix)
        else if (firstChar == "E" || firstChar == "N")
        {
            var fillRule = (firstChar == "E") ? "evenodd" : "nonzero";
            var cmdStr = substring(line, 1, size(line));
            var commands = parseCommands(cmdStr);
            paths = append(paths, {
                "fillRule" : fillRule,
                "commands" : commands
            });
        }
    }

    return {
        "viewBox" : viewBox,
        "paths" : paths
    };
}

/**
 * Parse ViewBox header line: V<minX>,<minY>,<width>,<height>
 */
function parseViewBox(line is string) returns map
{
    var numStr = substring(line, 1, size(line));
    var parts = splitString(numStr, ",");
    return {
        "minX" : stringToNumber(parts[0]),
        "minY" : stringToNumber(parts[1]),
        "width" : stringToNumber(parts[2]),
        "height" : stringToNumber(parts[3])
    };
}

/**
 * Parse command string into array of command maps.
 * Commands are separated by spaces, each starting with M/L/C/A/Z.
 */
function parseCommands(cmdStr is string) returns array
{
    var commands = [];
    var tokens = splitString(cmdStr, " ");

    for (var i = 0; i < size(tokens); i += 1)
    {
        var token = trim(tokens[i]);
        if (size(token) == 0)
            continue;

        var cmdChar = substring(token, 0, 1);
        var command = { "cmd" : cmdChar, "params" : [] };

        if (cmdChar == "Z")
        {
            // No params
        }
        else
        {
            var paramStr = substring(token, 1, size(token));
            var paramParts = splitString(paramStr, ",");
            var params = [];
            for (var j = 0; j < size(paramParts); j += 1)
            {
                params = append(params, stringToNumber(paramParts[j]));
            }
            command.params = params;
        }

        commands = append(commands, command);
    }

    return commands;
}

/**
 * Convert string to number. Handles integers and decimals.
 */
function stringToNumber(s is string) returns number
{
    // FeatureScript has built-in string-to-number
    return evaluate(s) as number;
}

/**
 * Split string by delimiter.
 */
function splitString(s is string, delim is string) returns array
{
    var result = [];
    var current = "";
    for (var i = 0; i < size(s); i += 1)
    {
        var ch = substring(s, i, i + 1);
        if (ch == delim)
        {
            result = append(result, current);
            current = "";
        }
        else
        {
            current = current ~ ch;
        }
    }
    result = append(result, current);
    return result;
}

/**
 * Trim whitespace from string.
 */
function trim(s is string) returns string
{
    var start = 0;
    var end = size(s);
    while (start < end && (substring(s, start, start + 1) == " " ||
                           substring(s, start, start + 1) == "\t" ||
                           substring(s, start, start + 1) == "\r"))
    {
        start += 1;
    }
    while (end > start && (substring(s, end - 1, end) == " " ||
                           substring(s, end - 1, end) == "\t" ||
                           substring(s, end - 1, end) == "\r"))
    {
        end -= 1;
    }
    return substring(s, start, end);
}

/**
 * Parse a number from a string using character-by-character parsing.
 * FeatureScript doesn't have a built-in parseFloat, so we implement one.
 */
function evaluate(s is string) returns number
{
    if (size(s) == 0)
        return 0;

    var negative = false;
    var idx = 0;

    // Check sign
    if (substring(s, 0, 1) == "-")
    {
        negative = true;
        idx = 1;
    }
    else if (substring(s, 0, 1) == "+")
    {
        idx = 1;
    }

    var intPart = 0;
    var fracPart = 0;
    var fracDiv = 1;
    var inFrac = false;

    while (idx < size(s))
    {
        var ch = substring(s, idx, idx + 1);
        if (ch == ".")
        {
            inFrac = true;
        }
        else
        {
            var digit = charToDigit(ch);
            if (digit >= 0)
            {
                if (inFrac)
                {
                    fracDiv *= 10;
                    fracPart = fracPart * 10 + digit;
                }
                else
                {
                    intPart = intPart * 10 + digit;
                }
            }
        }
        idx += 1;
    }

    var result = intPart + fracPart / fracDiv;
    return negative ? -result : result;
}

function charToDigit(ch is string) returns number
{
    if (ch == "0") return 0;
    if (ch == "1") return 1;
    if (ch == "2") return 2;
    if (ch == "3") return 3;
    if (ch == "4") return 4;
    if (ch == "5") return 5;
    if (ch == "6") return 6;
    if (ch == "7") return 7;
    if (ch == "8") return 8;
    if (ch == "9") return 9;
    return -1;
}

// ============================================================================
// Section 3: Sketch Generator
// ============================================================================

/**
 * Create texture sketch on a plane with SVG path data.
 */
function createTextureSketch(context is Context, id is Id, plane is Plane,
    svgData is map, patternWidth is ValueWithUnits, patternHeight is ValueWithUnits,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits, rotation is ValueWithUnits,
    tilingEnabled is boolean, tilesX is number, tilesY is number,
    spacingX is ValueWithUnits, spacingY is ValueWithUnits, offsetAlternate is boolean)
{
    var sketchId = id + "textureSketch";
    var sketch = newSketchOnPlane(context, sketchId, { "sketchPlane" : plane });

    var viewBox = svgData.viewBox;
    var scaleX = patternWidth / (viewBox.width * millimeter);
    var scaleY = patternHeight / (viewBox.height * millimeter);

    var entityIdx = 0;

    if (tilingEnabled)
    {
        for (var tx = 0; tx < tilesX; tx += 1)
        {
            for (var ty = 0; ty < tilesY; ty += 1)
            {
                var tileOffsetX = tx * (patternWidth + spacingX) + offsetX;
                var tileOffsetY = ty * (patternHeight + spacingY) + offsetY;

                // Brick pattern: offset alternate rows by half width
                if (offsetAlternate && (ty % 2 == 1))
                {
                    tileOffsetX += (patternWidth + spacingX) / 2;
                }

                entityIdx = drawPaths(sketch, sketchId, svgData.paths,
                    viewBox, scaleX, scaleY,
                    tileOffsetX, tileOffsetY, rotation, entityIdx);
            }
        }
    }
    else
    {
        entityIdx = drawPaths(sketch, sketchId, svgData.paths,
            viewBox, scaleX, scaleY,
            offsetX, offsetY, rotation, entityIdx);
    }

    if (entityIdx > ENTITY_WARNING_THRESHOLD)
    {
        reportFeatureWarning(context, id, "High entity count (" ~ toString(entityIdx) ~
            "). Performance may be affected.");
    }

    skSolve(sketch);
}

/**
 * Draw all paths with given offset and scale.
 */
function drawPaths(sketch is Sketch, sketchId is Id, paths is array,
    viewBox is map, scaleX is number, scaleY is number,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits,
    rotation is ValueWithUnits, startIdx is number) returns number
{
    var entityIdx = startIdx;
    var cosR = cos(rotation);
    var sinR = sin(rotation);

    for (var p = 0; p < size(paths); p += 1)
    {
        var path = paths[p];
        var commands = path.commands;
        var curX = 0 * millimeter;
        var curY = 0 * millimeter;
        var subpathStartX = 0 * millimeter;
        var subpathStartY = 0 * millimeter;

        for (var c = 0; c < size(commands); c += 1)
        {
            var command = commands[c];
            var cmd = command.cmd;
            var params = command.params;

            if (cmd == "M")
            {
                // Move to: transform SVG coords to sketch coords
                curX = (params[0] - viewBox.minX) * scaleX * millimeter;
                curY = -(params[1] - viewBox.minY) * scaleY * millimeter; // Flip Y
                subpathStartX = curX;
                subpathStartY = curY;
            }
            else if (cmd == "L")
            {
                var x = (params[0] - viewBox.minX) * scaleX * millimeter;
                var y = -(params[1] - viewBox.minY) * scaleY * millimeter;

                var p1 = applyRotationAndOffset(curX, curY, cosR, sinR, offsetX, offsetY);
                var p2 = applyRotationAndOffset(x, y, cosR, sinR, offsetX, offsetY);

                skLineSegment(sketch, "line_" ~ toString(entityIdx), {
                    "start" : vector(p1[0], p1[1]),
                    "end" : vector(p2[0], p2[1])
                });
                entityIdx += 1;

                curX = x;
                curY = y;
            }
            else if (cmd == "C")
            {
                var x1 = (params[0] - viewBox.minX) * scaleX * millimeter;
                var y1 = -(params[1] - viewBox.minY) * scaleY * millimeter;
                var x2 = (params[2] - viewBox.minX) * scaleX * millimeter;
                var y2 = -(params[3] - viewBox.minY) * scaleY * millimeter;
                var x = (params[4] - viewBox.minX) * scaleX * millimeter;
                var y = -(params[5] - viewBox.minY) * scaleY * millimeter;

                var ps = applyRotationAndOffset(curX, curY, cosR, sinR, offsetX, offsetY);
                var pc1 = applyRotationAndOffset(x1, y1, cosR, sinR, offsetX, offsetY);
                var pc2 = applyRotationAndOffset(x2, y2, cosR, sinR, offsetX, offsetY);
                var pe = applyRotationAndOffset(x, y, cosR, sinR, offsetX, offsetY);

                skBezier(sketch, "bezier_" ~ toString(entityIdx), {
                    "start" : vector(ps[0], ps[1]),
                    "controlPoint1" : vector(pc1[0], pc1[1]),
                    "controlPoint2" : vector(pc2[0], pc2[1]),
                    "end" : vector(pe[0], pe[1])
                });
                entityIdx += 1;

                curX = x;
                curY = y;
            }
            else if (cmd == "A")
            {
                // Arc: cx, cy, r, startDeg, sweepDeg
                var cx = (params[0] - viewBox.minX) * scaleX * millimeter;
                var cy = -(params[1] - viewBox.minY) * scaleY * millimeter;
                var r = params[2] * ((scaleX + scaleY) / 2) * millimeter;
                var startDeg = -params[3]; // Negate for Y flip
                var sweepDeg = -params[4]; // Negate for Y flip

                // Convert center-param arc to 3-point arc (start, mid, end)
                var startRad = startDeg * PI / 180;
                var midRad = startRad + (sweepDeg * PI / 180) / 2;
                var endRad = startRad + sweepDeg * PI / 180;

                var arcStart = vector(cx + r * cos(startRad * radian),
                                       cy + r * sin(startRad * radian));
                var arcMid = vector(cx + r * cos(midRad * radian),
                                     cy + r * sin(midRad * radian));
                var arcEnd = vector(cx + r * cos(endRad * radian),
                                     cy + r * sin(endRad * radian));

                // Apply rotation and offset to all three points
                var as1 = applyRotationAndOffset2D(arcStart, cosR, sinR, offsetX, offsetY);
                var am = applyRotationAndOffset2D(arcMid, cosR, sinR, offsetX, offsetY);
                var ae = applyRotationAndOffset2D(arcEnd, cosR, sinR, offsetX, offsetY);

                skArc(sketch, "arc_" ~ toString(entityIdx), {
                    "start" : as1,
                    "mid" : am,
                    "end" : ae
                });
                entityIdx += 1;

                // Update current position to arc end
                curX = cx + r * cos(endRad * radian) / millimeter * millimeter;
                curY = cy + r * sin(endRad * radian) / millimeter * millimeter;
            }
            else if (cmd == "Z")
            {
                // Close path: draw line back to subpath start if not already there
                if (abs(curX - subpathStartX) > 0.001 * millimeter ||
                    abs(curY - subpathStartY) > 0.001 * millimeter)
                {
                    var p1 = applyRotationAndOffset(curX, curY, cosR, sinR, offsetX, offsetY);
                    var p2 = applyRotationAndOffset(subpathStartX, subpathStartY,
                        cosR, sinR, offsetX, offsetY);

                    skLineSegment(sketch, "close_" ~ toString(entityIdx), {
                        "start" : vector(p1[0], p1[1]),
                        "end" : vector(p2[0], p2[1])
                    });
                    entityIdx += 1;
                }
                curX = subpathStartX;
                curY = subpathStartY;
            }
        }
    }

    return entityIdx;
}

/**
 * Apply rotation and offset to a point. Returns [x, y] array.
 */
function applyRotationAndOffset(x is ValueWithUnits, y is ValueWithUnits,
    cosR is number, sinR is number,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits) returns array
{
    var rx = x * cosR - y * sinR + offsetX;
    var ry = x * sinR + y * cosR + offsetY;
    return [rx, ry];
}

/**
 * Apply rotation and offset to a 2D vector. Returns 2D vector.
 */
function applyRotationAndOffset2D(pt is Vector, cosR is number, sinR is number,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits) returns Vector
{
    return vector(pt[0] * cosR - pt[1] * sinR + offsetX,
                  pt[0] * sinR + pt[1] * cosR + offsetY);
}

// ============================================================================
// Section 4: Surface Mapper
// ============================================================================

/**
 * Detect whether a face is planar, cylindrical, or other.
 */
function detectSurfaceType(context is Context, face is Query) returns MappingMode
{
    var surfDef = evSurfaceDefinition(context, { "face" : face });

    if (surfDef is Plane)
        return MappingMode.PLANAR;
    else if (surfDef is Cylinder)
        return MappingMode.CYLINDRICAL;
    else
        return MappingMode.PLANAR; // Fallback to planar for other surface types
}

/**
 * Get the plane of a planar face.
 */
function getFacePlane(context is Context, face is Query) returns Plane
{
    return evPlane(context, { "face" : face });
}

/**
 * Get cylinder parameters for a cylindrical face.
 */
function getCylinderInfo(context is Context, face is Query) returns map
{
    var surfDef = evSurfaceDefinition(context, { "face" : face });
    // surfDef is a Cylinder with .coordSystem and .radius
    return {
        "axis" : surfDef.coordSystem.zAxis,
        "origin" : surfDef.coordSystem.origin,
        "radius" : surfDef.radius,
        "coordSystem" : surfDef.coordSystem
    };
}

// ============================================================================
// Section 5: Extrusion & Boolean
// ============================================================================

/**
 * Handle planar face: sketch on face -> extrude -> boolean.
 */
function handlePlanarFace(context is Context, id is Id, face is Query,
    svgData is map, definition is map)
{
    var facePlane = getFacePlane(context, face);

    // Create sketch on the face plane
    createTextureSketch(context, id, facePlane, svgData,
        definition.patternWidth, definition.patternHeight,
        definition.offsetX, definition.offsetY, definition.rotation,
        definition.tilingEnabled,
        definition.tilingEnabled ? definition.tilesX : 1,
        definition.tilingEnabled ? definition.tilesY : 1,
        definition.tilingEnabled ? definition.spacingX : 0 * millimeter,
        definition.tilingEnabled ? definition.spacingY : 0 * millimeter,
        definition.tilingEnabled ? definition.offsetAlternate : false);

    var sketchId = id + "textureSketch";

    // Get sketch regions
    var sketchRegions = qSketchRegion(sketchId);

    if (size(evaluateQuery(context, sketchRegions)) == 0)
    {
        reportFeatureWarning(context, id, "No closed regions found in sketch. Check SVG data.");
        return;
    }

    // Determine extrusion direction
    var extrudeDir = (definition.direction == TextureDirection.RAISED) ? 1 : -1;
    var depth = definition.depth;

    // Extrude sketch regions
    var extrudeId = id + "extrude";
    opExtrude(context, extrudeId, {
        "entities" : sketchRegions,
        "direction" : facePlane.normal * extrudeDir,
        "endBound" : BoundingType.BLIND,
        "endDepth" : depth
    });

    // Boolean with target body
    var targetBody = qOwnerBody(face);
    var extrudedBodies = qCreatedBy(extrudeId, EntityType.BODY);

    if (definition.direction == TextureDirection.RAISED)
    {
        var boolId = id + "boolean";
        opBoolean(context, boolId, {
            "tools" : extrudedBodies,
            "targets" : targetBody,
            "operationType" : BooleanOperationType.UNION
        });
    }
    else
    {
        var boolId = id + "boolean";
        opBoolean(context, boolId, {
            "tools" : extrudedBodies,
            "targets" : targetBody,
            "operationType" : BooleanOperationType.SUBTRACTION
        });
    }

    // Clean up sketch
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(sketchId, EntityType.BODY) });
}

/**
 * Handle cylindrical face: tangent plane sketch -> extrude toward center -> boolean.
 */
function handleCylindricalFace(context is Context, id is Id, face is Query,
    svgData is map, definition is map)
{
    var cylInfo = getCylinderInfo(context, face);

    // Get tangent plane at UV midpoint
    var tangentResult = evFaceTangentPlane(context, {
        "face" : face,
        "parameter" : vector(0.5, 0.5)
    });
    var tangentPlane = tangentResult;

    // Create sketch on tangent plane
    createTextureSketch(context, id, tangentPlane, svgData,
        definition.patternWidth, definition.patternHeight,
        definition.offsetX, definition.offsetY, definition.rotation,
        definition.tilingEnabled,
        definition.tilingEnabled ? definition.tilesX : 1,
        definition.tilingEnabled ? definition.tilesY : 1,
        definition.tilingEnabled ? definition.spacingX : 0 * millimeter,
        definition.tilingEnabled ? definition.spacingY : 0 * millimeter,
        definition.tilingEnabled ? definition.offsetAlternate : false);

    var sketchId = id + "textureSketch";
    var sketchRegions = qSketchRegion(sketchId);

    if (size(evaluateQuery(context, sketchRegions)) == 0)
    {
        reportFeatureWarning(context, id, "No closed regions found in sketch. Check SVG data.");
        return;
    }

    // Extrude toward cylinder center (inward direction from tangent plane)
    var extrudeDir = -tangentPlane.normal; // Toward center
    var extrudeDepth = cylInfo.radius + definition.depth; // Ensure we penetrate through

    var extrudeId = id + "extrude";
    opExtrude(context, extrudeId, {
        "entities" : sketchRegions,
        "direction" : extrudeDir,
        "endBound" : BoundingType.BLIND,
        "endDepth" : extrudeDepth
    });

    // Make a copy of the target body for intersection
    var targetBody = qOwnerBody(face);

    if (definition.direction == TextureDirection.RAISED)
    {
        // For raised: offset the cylinder surface outward, intersect extrusion with offset
        // Simplified: extrude outward from face, then union
        var extrudeOutId = id + "extrudeOut";
        opExtrude(context, extrudeOutId, {
            "entities" : sketchRegions,
            "direction" : tangentPlane.normal,
            "endBound" : BoundingType.BLIND,
            "endDepth" : definition.depth
        });

        var extrudedBodies = qCreatedBy(extrudeOutId, EntityType.BODY);

        // Intersect extruded bodies with a thickened version of the cylinder
        // For simplicity, just boolean union the extrusion with the body
        var boolId = id + "boolean";
        opBoolean(context, boolId, {
            "tools" : extrudedBodies,
            "targets" : targetBody,
            "operationType" : BooleanOperationType.UNION
        });

        // Clean up the inward extrusion
        opDeleteBodies(context, id + "deleteInward", {
            "entities" : qCreatedBy(extrudeId, EntityType.BODY)
        });
    }
    else
    {
        // For recessed: intersect extrusion with body, then subtract
        var extrudedBodies = qCreatedBy(extrudeId, EntityType.BODY);

        // Boolean intersection to clip to body shape
        var intersectId = id + "intersect";
        try
        {
            opBoolean(context, intersectId, {
                "tools" : targetBody,
                "targets" : extrudedBodies,
                "operationType" : BooleanOperationType.INTERSECTION,
                "keepTools" : true
            });

            // Now subtract the intersection result from original body
            var intersectedBodies = qCreatedBy(intersectId, EntityType.BODY);
            var subtractId = id + "subtract";
            opBoolean(context, subtractId, {
                "tools" : intersectedBodies,
                "targets" : targetBody,
                "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
        catch
        {
            // Fallback: direct subtraction
            var boolId = id + "booleanFallback";
            opBoolean(context, boolId, {
                "tools" : extrudedBodies,
                "targets" : targetBody,
                "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
    }

    // Clean up sketch
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(sketchId, EntityType.BODY) });
}

// ============================================================================
// Section 6: Main Feature
// ============================================================================

annotation { "Feature Type Name" : "SVG Texture",
             "Feature Type Description" : "Apply SVG patterns as 3D raised/recessed textures",
             "Editing Logic Function" : "svgTextureEditLogic" }
export const svgTexture = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        // -- Operation type (Onshape convention: boolean op at top) --
        annotation { "Name" : "Direction",
                     "UIHint" : UIHint.HORIZONTAL_ENUM }
        definition.direction is TextureDirection;

        // -- Geometry selection --
        annotation { "Name" : "Target face",
                     "Filter" : EntityType.FACE,
                     "MaxNumberOfPicks" : 1 }
        definition.targetFace is Query;

        // -- SVG data input --
        annotation { "Name" : "SVG data",
                     "UIHint" : UIHint.REMEMBER_PREVIOUS_VALUE,
                     "MaxLength" : 10000 }
        definition.svgData is string;

        // -- Dimensions --
        annotation { "Group Name" : "Pattern Size", "Collapsed By Default" : false }
        {
            annotation { "Name" : "Width" }
            isLength(definition.patternWidth, TEXTURE_SIZE_BOUNDS);

            annotation { "Name" : "Height" }
            isLength(definition.patternHeight, TEXTURE_SIZE_BOUNDS);

            annotation { "Name" : "Depth" }
            isLength(definition.depth, TEXTURE_DEPTH_BOUNDS);
        }

        // -- Mapping --
        annotation { "Name" : "Mapping",
                     "UIHint" : UIHint.HORIZONTAL_ENUM }
        definition.mappingMode is MappingMode;

        // -- Positioning --
        annotation { "Group Name" : "Position", "Collapsed By Default" : true }
        {
            annotation { "Name" : "X offset" }
            isLength(definition.offsetX, ZERO_DEFAULT_LENGTH_BOUNDS);

            annotation { "Name" : "Y offset" }
            isLength(definition.offsetY, ZERO_DEFAULT_LENGTH_BOUNDS);

            annotation { "Name" : "Rotation" }
            isAngle(definition.rotation, ANGLE_360_ZERO_DEFAULT_BOUNDS);
        }

        // -- Tiling --
        annotation { "Name" : "Tiling" }
        definition.tilingEnabled is boolean;

        if (definition.tilingEnabled)
        {
            annotation { "Group Name" : "Tiling",
                         "Collapsed By Default" : false,
                         "Driving Parameter" : "tilingEnabled" }
            {
                annotation { "Name" : "Columns" }
                isInteger(definition.tilesX, TILE_COUNT_BOUNDS);

                annotation { "Name" : "Rows" }
                isInteger(definition.tilesY, TILE_COUNT_BOUNDS);

                annotation { "Name" : "Column spacing" }
                isLength(definition.spacingX, NONNEGATIVE_ZERO_DEFAULT_LENGTH_BOUNDS);

                annotation { "Name" : "Row spacing" }
                isLength(definition.spacingY, NONNEGATIVE_ZERO_DEFAULT_LENGTH_BOUNDS);

                annotation { "Name" : "Stagger rows",
                             "Default" : false }
                definition.offsetAlternate is boolean;
            }
        }
    }
    {
        // Validate face selection
        var faces = evaluateQuery(context, definition.targetFace);
        if (size(faces) == 0)
        {
            reportFeatureError(context, id, "Please select a target face.");
            return;
        }

        // Parse SVGTEX data
        if (size(definition.svgData) == 0)
        {
            reportFeatureError(context, id, "Please paste SVGTEX data.");
            return;
        }

        var svgData = parseSvgTex(definition.svgData);

        if (size(svgData.paths) == 0)
        {
            reportFeatureError(context, id, "No valid paths found in SVGTEX data.");
            return;
        }

        // Detect or use specified mapping mode
        var mappingMode = definition.mappingMode;
        if (mappingMode == MappingMode.AUTO)
        {
            mappingMode = detectSurfaceType(context, definition.targetFace);
        }

        // Dispatch to handler
        if (mappingMode == MappingMode.PLANAR)
        {
            handlePlanarFace(context, id, definition.targetFace, svgData, definition);
        }
        else if (mappingMode == MappingMode.CYLINDRICAL)
        {
            handleCylindricalFace(context, id, definition.targetFace, svgData, definition);
        }
        else
        {
            // Fallback to planar
            handlePlanarFace(context, id, definition.targetFace, svgData, definition);
        }
    });
