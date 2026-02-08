FeatureScript 2878;
import(path : "onshape/std/common.fs", version : "2878.0");

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

export const TEXTURE_DEPTH_BOUNDS =
{
    (meter)      : [1e-5, 0.0005, 0.5],
    (centimeter) : 0.05,
    (millimeter) : 0.5,
    (inch)       : 0.02,
    (foot)       : 0.002,
    (yard)       : 0.0006
} as LengthBoundSpec;

export const TEXTURE_SIZE_BOUNDS =
{
    (meter)      : [1e-5, 0.01, 500],
    (centimeter) : 1.0,
    (millimeter) : 10.0,
    (inch)       : 0.4,
    (foot)       : 0.033,
    (yard)       : 0.011
} as LengthBoundSpec;

export const TILE_COUNT_BOUNDS =
{
    (unitless) : [1, 2, 2500]
} as IntegerBoundSpec;

export const MAX_ENTITIES_BOUNDS =
{
    (unitless) : [10, 2500, 100000]
} as IntegerBoundSpec;

const MY_PI = 3.14159265358979323846;

// ============================================================================
// Section 2: String / Math Utilities
// ============================================================================

function findChar(chars is array, ch is string, startPos is number) returns number
{
    for (var i = startPos; i < size(chars); i += 1)
    {
        if (chars[i] == ch)
            return i;
    }
    return -1;
}

function findSubstr(chars is array, target is string, startPos is number) returns number
{
    var tChars = splitIntoCharacters(target);
    var tLen = size(tChars);
    if (tLen == 0)
        return startPos;
    for (var i = startPos; i <= size(chars) - tLen; i += 1)
    {
        var found = true;
        for (var j = 0; j < tLen; j += 1)
        {
            if (chars[i + j] != tChars[j])
            {
                found = false;
                break;
            }
        }
        if (found)
            return i;
    }
    return -1;
}

function charsToString(chars is array, from is number, to is number) returns string
{
    var s = "";
    for (var i = from; i < to && i < size(chars); i += 1)
        s = s ~ chars[i];
    return s;
}

function isWS(ch is string) returns boolean
{
    return ch == " " || ch == "\t" || ch == "\n" || ch == "\r";
}

function isDigit(ch is string) returns boolean
{
    return ch == "0" || ch == "1" || ch == "2" || ch == "3" || ch == "4" ||
           ch == "5" || ch == "6" || ch == "7" || ch == "8" || ch == "9";
}

function isPathCmd(ch is string) returns boolean
{
    return ch == "M" || ch == "m" || ch == "L" || ch == "l" ||
           ch == "H" || ch == "h" || ch == "V" || ch == "v" ||
           ch == "C" || ch == "c" || ch == "S" || ch == "s" ||
           ch == "Q" || ch == "q" || ch == "T" || ch == "t" ||
           ch == "A" || ch == "a" || ch == "Z" || ch == "z";
}

function skipWS(chars is array, pos is number) returns number
{
    while (pos < size(chars) && isWS(chars[pos]))
        pos += 1;
    return pos;
}

function charToDigit(ch is string) returns number
{
    if (ch == "0") return 0; if (ch == "1") return 1; if (ch == "2") return 2;
    if (ch == "3") return 3; if (ch == "4") return 4; if (ch == "5") return 5;
    if (ch == "6") return 6; if (ch == "7") return 7; if (ch == "8") return 8;
    if (ch == "9") return 9; return -1;
}

function parseNum(chars is array, startPos is number) returns map
{
    var pos = startPos;
    var n = size(chars);
    if (pos >= n)
        return { "val" : 0, "pos" : pos };

    var negative = false;
    if (pos < n && (chars[pos] == "-" || chars[pos] == "+"))
    {
        negative = (chars[pos] == "-");
        pos += 1;
    }

    var intPart = 0;
    while (pos < n && isDigit(chars[pos]))
    {
        intPart = intPart * 10 + charToDigit(chars[pos]);
        pos += 1;
    }

    var fracPart = 0.0;
    var fracDiv = 1.0;
    if (pos < n && chars[pos] == ".")
    {
        pos += 1;
        while (pos < n && isDigit(chars[pos]))
        {
            fracDiv *= 10;
            fracPart = fracPart * 10 + charToDigit(chars[pos]);
            pos += 1;
        }
    }

    var result = intPart + fracPart / fracDiv;

    // Exponent
    if (pos < n && (chars[pos] == "e" || chars[pos] == "E"))
    {
        pos += 1;
        var expNeg = false;
        if (pos < n && (chars[pos] == "+" || chars[pos] == "-"))
        {
            expNeg = (chars[pos] == "-");
            pos += 1;
        }
        var exp = 0;
        while (pos < n && isDigit(chars[pos]))
        {
            exp = exp * 10 + charToDigit(chars[pos]);
            pos += 1;
        }
        var mult = 1.0;
        for (var e = 0; e < exp; e += 1)
            mult *= 10;
        if (expNeg)
            result = result / mult;
        else
            result = result * mult;
    }

    if (negative)
        result = -result;
    return { "val" : result, "pos" : pos };
}

function sqrtNum(x is number) returns number
{
    if (x <= 0)
        return 0;
    return sqrt(x * meter * meter) / meter;
}

function atan2Num(y is number, x is number) returns number
{
    return atan2(y * meter, x * meter) / radian;
}

function cosNum(a is number) returns number
{
    return cos(a * radian);
}

function sinNum(a is number) returns number
{
    return sin(a * radian);
}

// ============================================================================
// Section 3: XML Tag Scanner
// ============================================================================

function findTagEnd(chars is array, startPos is number) returns number
{
    var inQ = "";
    for (var i = startPos; i < size(chars); i += 1)
    {
        if (inQ != "")
        {
            if (chars[i] == inQ)
                inQ = "";
        }
        else
        {
            if (chars[i] == "\"" || chars[i] == "'")
                inQ = chars[i];
            else if (chars[i] == ">")
                return i;
        }
    }
    return -1;
}

function scanTags(chars is array) returns array
{
    var tags = [];
    var pos = 0;
    var n = size(chars);

    while (pos < n)
    {
        pos = findChar(chars, "<", pos);
        if (pos < 0)
            break;

        // Comment <!-- ... -->
        if (pos + 3 < n && chars[pos + 1] == "!" && chars[pos + 2] == "-" && chars[pos + 3] == "-")
        {
            var ec = findSubstr(chars, "-->", pos + 4);
            pos = (ec >= 0) ? ec + 3 : n;
            continue;
        }
        // Processing instruction <? ... ?>
        if (pos + 1 < n && chars[pos + 1] == "?")
        {
            var ep = findSubstr(chars, "?>", pos + 2);
            pos = (ep >= 0) ? ep + 2 : n;
            continue;
        }
        // DOCTYPE or CDATA <!...>
        if (pos + 1 < n && chars[pos + 1] == "!")
        {
            // CDATA: <![CDATA[ ... ]]>
            if (pos + 8 < n && charsToString(chars, pos + 2, pos + 9) == "[CDATA[")
            {
                var ec = findSubstr(chars, "]]>", pos + 9);
                pos = (ec >= 0) ? ec + 3 : n;
            }
            else
            {
                var ed = findChar(chars, ">", pos + 2);
                pos = (ed >= 0) ? ed + 1 : n;
            }
            continue;
        }

        var tagStart = pos + 1;
        var tagEnd = findTagEnd(chars, tagStart);
        if (tagEnd < 0)
            break;

        // Capture text after tag until next '<'
        var textEnd = findChar(chars, "<", tagEnd + 1);
        if (textEnd < 0)
            textEnd = n;

        tags = append(tags, {
            "tagStr" : charsToString(chars, tagStart, tagEnd),
            "textAfter" : charsToString(chars, tagEnd + 1, textEnd)
        });

        pos = tagEnd + 1;
    }
    return tags;
}

// ============================================================================
// Section 4: Tag & Attribute Parser
// ============================================================================

function stripNS(name is string) returns string
{
    var nc = splitIntoCharacters(name);
    for (var i = 0; i < size(nc); i += 1)
    {
        if (nc[i] == ":")
            return charsToString(nc, i + 1, size(nc));
    }
    return name;
}

function toLower(ch is string) returns string
{
    if (ch == "A") return "a"; if (ch == "B") return "b"; if (ch == "C") return "c";
    if (ch == "D") return "d"; if (ch == "E") return "e"; if (ch == "F") return "f";
    if (ch == "G") return "g"; if (ch == "H") return "h"; if (ch == "I") return "i";
    if (ch == "J") return "j"; if (ch == "K") return "k"; if (ch == "L") return "l";
    if (ch == "M") return "m"; if (ch == "N") return "n"; if (ch == "O") return "o";
    if (ch == "P") return "p"; if (ch == "Q") return "q"; if (ch == "R") return "r";
    if (ch == "S") return "s"; if (ch == "T") return "t"; if (ch == "U") return "u";
    if (ch == "V") return "v"; if (ch == "W") return "w"; if (ch == "X") return "x";
    if (ch == "Y") return "y"; if (ch == "Z") return "z";
    return ch;
}

function toLowerStr(s is string) returns string
{
    var r = "";
    for (var ch in splitIntoCharacters(s))
        r = r ~ toLower(ch);
    return r;
}

function parseTag(tagStr is string) returns map
{
    var ch = splitIntoCharacters(tagStr);
    var n = size(ch);
    var result = { "name" : "", "attrs" : {}, "isClose" : false, "selfClose" : false };
    var pos = 0;
    pos = skipWS(ch, pos);
    if (pos >= n)
        return result;

    if (ch[pos] == "/")
    {
        result.isClose = true;
        pos += 1;
    }

    // Tag name
    var ns = pos;
    while (pos < n && !isWS(ch[pos]) && ch[pos] != "/" && ch[pos] != ">")
        pos += 1;
    result.name = stripNS(toLowerStr(charsToString(ch, ns, pos)));

    // Self-closing?
    if (n > 0 && ch[n - 1] == "/")
        result.selfClose = true;

    // Attributes
    while (pos < n)
    {
        pos = skipWS(ch, pos);
        if (pos >= n || ch[pos] == "/" || ch[pos] == ">")
            break;

        var aStart = pos;
        while (pos < n && ch[pos] != "=" && !isWS(ch[pos]) && ch[pos] != "/" && ch[pos] != ">")
            pos += 1;
        var aName = stripNS(toLowerStr(charsToString(ch, aStart, pos)));

        pos = skipWS(ch, pos);
        if (pos >= n || ch[pos] != "=")
            continue;
        pos += 1;
        pos = skipWS(ch, pos);
        if (pos >= n)
            break;

        var quote = ch[pos];
        if (quote != "\"" && quote != "'")
            continue;
        pos += 1;

        var vs = pos;
        while (pos < n && ch[pos] != quote)
            pos += 1;
        var aVal = charsToString(ch, vs, pos);
        if (pos < n)
            pos += 1;

        result.attrs[aName] = aVal;
    }
    return result;
}

// Decode basic XML entities
function decodeXml(s is string) returns string
{
    var r = s;
    r = replace(r, "&amp;", "&");
    r = replace(r, "&lt;", "<");
    r = replace(r, "&gt;", ">");
    r = replace(r, "&quot;", "\"");
    r = replace(r, "&apos;", "'");
    return r;
}

// ============================================================================
// Section 5: CSS Style Block Parser
// ============================================================================

function parseCssBlocks(tags is array) returns map
{
    // Collect text inside <style> ... </style>
    var cssText = "";
    var inStyle = false;
    for (var i = 0; i < size(tags); i += 1)
    {
        var tag = parseTag(tags[i].tagStr);
        if (tag.name == "style" && !tag.isClose)
        {
            inStyle = true;
            cssText = cssText ~ tags[i].textAfter;
        }
        else if (tag.name == "style" && tag.isClose)
        {
            inStyle = false;
        }
        else if (inStyle)
        {
            cssText = cssText ~ tags[i].textAfter;
        }
    }

    // Strip CDATA wrappers
    cssText = replace(cssText, "/\\*.*?\\*/", ""); // remove CSS comments
    cssText = replace(cssText, "<!\\[CDATA\\[", "");
    cssText = replace(cssText, "\\]\\]>", "");

    // Parse rules: selector { prop: val; ... }
    var rules = {}; // className/id -> { fill, stroke, etc }
    // Split by }
    var blocks = splitByChar(cssText, "}");
    for (var i = 0; i < size(blocks); i += 1)
    {
        var block = blocks[i];
        var parts = splitByChar(block, "{");
        if (size(parts) < 2)
            continue;
        var selector = trimStr(parts[0]);
        var decls = trimStr(parts[1]);
        if (selector == "" || decls == "")
            continue;

        // Parse declarations
        var props = {};
        var declList = splitByChar(decls, ";");
        for (var d = 0; d < size(declList); d += 1)
        {
            var pv = splitByChar(declList[d], ":");
            if (size(pv) >= 2)
            {
                var pName = trimStr(pv[0]);
                var pVal = trimStr(pv[1]);
                if (pName != "")
                    props[pName] = pVal;
            }
        }

        // Handle comma-separated selectors
        var sels = splitByChar(selector, ",");
        for (var s = 0; s < size(sels); s += 1)
        {
            var sel = trimStr(sels[s]);
            if (sel != "")
                rules[sel] = props;
        }
    }
    return rules;
}

function splitByChar(s is string, delim is string) returns array
{
    var result = [];
    var current = "";
    for (var ch in splitIntoCharacters(s))
    {
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

function trimStr(s is string) returns string
{
    var ch = splitIntoCharacters(s);
    var a = 0;
    var b = size(ch);
    while (a < b && isWS(ch[a]))
        a += 1;
    while (b > a && isWS(ch[b - 1]))
        b -= 1;
    return charsToString(ch, a, b);
}

// Resolve CSS class/id styles for an element
function applyCssRules(attrs is map, cssRules is map) returns map
{
    var merged = attrs;
    // Look up by class
    if (attrs["class"] != undefined)
    {
        var classes = splitByChar(attrs["class"], " ");
        for (var c = 0; c < size(classes); c += 1)
        {
            var cls = trimStr(classes[c]);
            if (cls == "")
                continue;
            var ruleKey = "." ~ cls;
            if (cssRules[ruleKey] != undefined)
            {
                var props = cssRules[ruleKey];
                for (var key, val in props)
                {
                    if (merged[key] == undefined) // element attrs take precedence
                        merged[key] = val;
                }
            }
        }
    }
    // Look up by id
    if (attrs["id"] != undefined)
    {
        var ruleKey = "#" ~ attrs["id"];
        if (cssRules[ruleKey] != undefined)
        {
            var props = cssRules[ruleKey];
            for (var key, val in props)
            {
                if (merged[key] == undefined)
                    merged[key] = val;
            }
        }
    }
    return merged;
}

// Parse inline style="..." into individual attributes
function parseInlineStyle(attrs is map) returns map
{
    if (attrs["style"] == undefined)
        return attrs;
    var merged = attrs;
    var decls = splitByChar(attrs["style"], ";");
    for (var d = 0; d < size(decls); d += 1)
    {
        var pv = splitByChar(decls[d], ":");
        if (size(pv) >= 2)
        {
            var pName = trimStr(pv[0]);
            var pVal = trimStr(pv[1]);
            if (pName != "" && merged[pName] == undefined) // explicit attrs win
                merged[pName] = pVal;
        }
    }
    return merged;
}

// ============================================================================
// Section 6: SVG Path D Tokenizer & Parser
// ============================================================================

function tokenizePathD(d is string) returns array
{
    var tokens = [];
    var ch = splitIntoCharacters(d);
    var n = size(ch);
    var pos = 0;

    while (pos < n)
    {
        if (isWS(ch[pos]) || ch[pos] == ",")
        {
            pos += 1;
            continue;
        }
        if (isPathCmd(ch[pos]))
        {
            tokens = append(tokens, { "t" : "c", "v" : ch[pos] });
            pos += 1;
            continue;
        }
        if (ch[pos] == "-" || ch[pos] == "+" || ch[pos] == "." || isDigit(ch[pos]))
        {
            var r = parseNum(ch, pos);
            tokens = append(tokens, { "t" : "n", "v" : r.val });
            pos = r.pos;
            continue;
        }
        pos += 1;
    }
    return tokens;
}

function getParamCount(cmd is string) returns number
{
    if (cmd == "M" || cmd == "m" || cmd == "L" || cmd == "l") return 2;
    if (cmd == "H" || cmd == "h" || cmd == "V" || cmd == "v") return 1;
    if (cmd == "C" || cmd == "c") return 6;
    if (cmd == "S" || cmd == "s" || cmd == "Q" || cmd == "q") return 4;
    if (cmd == "T" || cmd == "t") return 2;
    if (cmd == "A" || cmd == "a") return 7;
    return 0;
}

function parsePathD(d is string) returns array
{
    var tokens = tokenizePathD(d);
    var cmds = [];
    var i = 0;
    var cur = "";

    while (i < size(tokens))
    {
        if (tokens[i].t == "c")
        {
            cur = tokens[i].v;
            i += 1;
            if (cur == "Z" || cur == "z")
            {
                cmds = append(cmds, { "cmd" : cur, "params" : [] });
                continue;
            }
        }

        if (cur == "" || cur == "Z" || cur == "z")
        {
            i += 1;
            continue;
        }

        var pc = getParamCount(cur);
        var params = [];
        for (var j = 0; j < pc && i < size(tokens); j += 1)
        {
            if (tokens[i].t == "n")
            {
                params = append(params, tokens[i].v);
                i += 1;
            }
            else
                break;
        }

        if (size(params) == pc)
        {
            cmds = append(cmds, { "cmd" : cur, "params" : params });
            if (cur == "M") cur = "L";
            else if (cur == "m") cur = "l";
        }
    }
    return cmds;
}

// ============================================================================
// Section 7: Arc Converter
// ============================================================================

function endpointToCenter(x1 is number, y1 is number, rx is number, ry is number,
    phiDeg is number, fA is number, fS is number, x2 is number, y2 is number) returns map
{
    if (abs(x1 - x2) < 1e-10 && abs(y1 - y2) < 1e-10)
        return { "cx" : x1, "cy" : y1, "r" : rx, "startDeg" : 0, "sweepDeg" : 0 };

    var phi = phiDeg * MY_PI / 180;
    var cosPhi = cosNum(phi);
    var sinPhi = sinNum(phi);

    var dx2 = (x1 - x2) / 2;
    var dy2 = (y1 - y2) / 2;
    var x1p = cosPhi * dx2 + sinPhi * dy2;
    var y1p = -sinPhi * dx2 + cosPhi * dy2;

    var rxSq = rx * rx;
    var rySq = ry * ry;
    var x1pSq = x1p * x1p;
    var y1pSq = y1p * y1p;

    // Ensure radii are large enough
    var lambda = x1pSq / rxSq + y1pSq / rySq;
    if (lambda > 1)
    {
        var sl = sqrtNum(lambda);
        rx = rx * sl;
        ry = ry * sl;
        rxSq = rx * rx;
        rySq = ry * ry;
    }

    var den = rxSq * y1pSq + rySq * x1pSq;
    if (den == 0)
        return { "cx" : (x1 + x2) / 2, "cy" : (y1 + y2) / 2, "r" : rx, "startDeg" : 0, "sweepDeg" : 0 };

    var num = rxSq * rySq - rxSq * y1pSq - rySq * x1pSq;
    if (num < 0)
        num = 0;
    var sq = sqrtNum(num / den);
    if (fA == fS)
        sq = -sq;

    var cxp = sq * rx * y1p / ry;
    var cyp = -sq * ry * x1p / rx;

    var cx = cosPhi * cxp - sinPhi * cyp + (x1 + x2) / 2;
    var cy = sinPhi * cxp + cosPhi * cyp + (y1 + y2) / 2;

    var startAngle = atan2Num((y1p - cyp) / ry, (x1p - cxp) / rx);
    var endAngle = atan2Num((-y1p - cyp) / ry, (-x1p - cxp) / rx);

    var sweep = endAngle - startAngle;
    if (fS == 1 && sweep < 0)
        sweep += 2 * MY_PI;
    else if (fS == 0 && sweep > 0)
        sweep -= 2 * MY_PI;

    return {
        "cx" : cx, "cy" : cy, "r" : (rx + ry) / 2,
        "startDeg" : startAngle * 180 / MY_PI,
        "sweepDeg" : sweep * 180 / MY_PI
    };
}

function arcToBeziers(x1 is number, y1 is number, rx is number, ry is number,
    phiDeg is number, fA is number, fS is number, x2 is number, y2 is number) returns array
{
    if (abs(x1 - x2) < 1e-10 && abs(y1 - y2) < 1e-10)
        return [];

    var phi = phiDeg * MY_PI / 180;
    var cosPhi = cosNum(phi);
    var sinPhi = sinNum(phi);

    var dx2 = (x1 - x2) / 2;
    var dy2 = (y1 - y2) / 2;
    var x1p = cosPhi * dx2 + sinPhi * dy2;
    var y1p = -sinPhi * dx2 + cosPhi * dy2;

    var rxSq = rx * rx;
    var rySq = ry * ry;
    var x1pSq = x1p * x1p;
    var y1pSq = y1p * y1p;

    var lambda = x1pSq / rxSq + y1pSq / rySq;
    if (lambda > 1)
    {
        var sl = sqrtNum(lambda);
        rx *= sl;
        ry *= sl;
        rxSq = rx * rx;
        rySq = ry * ry;
    }

    var den = rxSq * y1pSq + rySq * x1pSq;
    var sq = 0.0;
    if (den > 0)
    {
        var num = rxSq * rySq - rxSq * y1pSq - rySq * x1pSq;
        if (num < 0) num = 0;
        sq = sqrtNum(num / den);
        if (fA == fS) sq = -sq;
    }

    var cxp = sq * rx * y1p / ry;
    var cyp = -sq * ry * x1p / rx;

    var theta1 = atan2Num((y1p - cyp) / ry, (x1p - cxp) / rx);
    var dTheta = atan2Num((-y1p - cyp) / ry, (-x1p - cxp) / rx) - theta1;

    if (fS == 1 && dTheta < 0)
        dTheta += 2 * MY_PI;
    else if (fS == 0 && dTheta > 0)
        dTheta -= 2 * MY_PI;

    // Split into segments of <= PI/2
    var numSegs = ceil(abs(dTheta) / (MY_PI / 2));
    if (numSegs < 1)
        numSegs = 1;
    var segAngle = dTheta / numSegs;

    var result = [];
    var t = theta1;
    for (var i = 0; i < numSegs; i += 1)
    {
        var t2 = t + segAngle;
        var alpha = 4.0 * (1 - cosNum(segAngle)) / sinNum(segAngle) / 3.0;
        if (abs(sinNum(segAngle)) < 1e-10)
            alpha = 0;

        var p1x = cosNum(t);
        var p1y = sinNum(t);
        var p2x = cosNum(t2);
        var p2y = sinNum(t2);

        var cp1x = p1x - alpha * p1y;
        var cp1y = p1y + alpha * p1x;
        var cp2x = p2x + alpha * p2y;
        var cp2y = p2y - alpha * p2x;

        // Transform from unit circle back to original space
        var tc1x = cosPhi * rx * cp1x - sinPhi * ry * cp1y + (x1 + x2) / 2 + cosPhi * cxp - sinPhi * cyp;
        var tc1y = sinPhi * rx * cp1x + cosPhi * ry * cp1y + (y1 + y2) / 2 + sinPhi * cxp + cosPhi * cyp;
        var tc2x = cosPhi * rx * cp2x - sinPhi * ry * cp2y + (x1 + x2) / 2 + cosPhi * cxp - sinPhi * cyp;
        var tc2y = sinPhi * rx * cp2x + cosPhi * ry * cp2y + (y1 + y2) / 2 + sinPhi * cxp + cosPhi * cyp;
        var tex = cosPhi * rx * p2x - sinPhi * ry * p2y + (x1 + x2) / 2 + cosPhi * cxp - sinPhi * cyp;
        var tey = sinPhi * rx * p2x + cosPhi * ry * p2y + (y1 + y2) / 2 + sinPhi * cxp + cosPhi * cyp;

        result = append(result, { "cmd" : "C", "params" : [tc1x, tc1y, tc2x, tc2y, tex, tey] });
        t = t2;
    }
    return result;
}

// ============================================================================
// Section 8: Path Normalizer
// ============================================================================

function normalizePath(raw is array) returns array
{
    var res = [];
    var cx = 0.0;
    var cy = 0.0;
    var sx = 0.0;
    var sy = 0.0;
    var lcx = 0.0;
    var lcy = 0.0;
    var lastCmd = "";

    for (var i = 0; i < size(raw); i += 1)
    {
        var cmd = raw[i].cmd;
        var p = raw[i].params;
        var rel = (cmd == "m" || cmd == "l" || cmd == "h" || cmd == "v" ||
                   cmd == "c" || cmd == "s" || cmd == "q" || cmd == "t" || cmd == "a");
        var uc = rel ? { "m":"M","l":"L","h":"H","v":"V","c":"C","s":"S","q":"Q","t":"T","a":"A" }[cmd] : cmd;
        if (uc == undefined)
            uc = cmd;

        if (uc == "M")
        {
            var x = p[0] + (rel ? cx : 0);
            var y = p[1] + (rel ? cy : 0);
            res = append(res, { "cmd" : "M", "params" : [x, y] });
            cx = x; cy = y; sx = x; sy = y;
            lastCmd = "M";
        }
        else if (uc == "L")
        {
            var x = p[0] + (rel ? cx : 0);
            var y = p[1] + (rel ? cy : 0);
            res = append(res, { "cmd" : "L", "params" : [x, y] });
            cx = x; cy = y; lastCmd = "L";
        }
        else if (uc == "H")
        {
            var x = p[0] + (rel ? cx : 0);
            res = append(res, { "cmd" : "L", "params" : [x, cy] });
            cx = x; lastCmd = "H";
        }
        else if (uc == "V")
        {
            var y = p[0] + (rel ? cy : 0);
            res = append(res, { "cmd" : "L", "params" : [cx, y] });
            cy = y; lastCmd = "V";
        }
        else if (uc == "C")
        {
            var o = rel ? cx : 0;
            var oy = rel ? cy : 0;
            var x1 = p[0]+o; var y1 = p[1]+oy;
            var x2 = p[2]+o; var y2 = p[3]+oy;
            var x = p[4]+o;  var y = p[5]+oy;
            res = append(res, { "cmd" : "C", "params" : [x1,y1,x2,y2,x,y] });
            lcx = x2; lcy = y2; cx = x; cy = y; lastCmd = "C";
        }
        else if (uc == "S")
        {
            var c1x = cx; var c1y = cy;
            if (lastCmd == "C" || lastCmd == "S")
            { c1x = 2*cx - lcx; c1y = 2*cy - lcy; }
            var o = rel ? cx : 0; var oy = rel ? cy : 0;
            var x2 = p[0]+o; var y2 = p[1]+oy;
            var x = p[2]+o;  var y = p[3]+oy;
            res = append(res, { "cmd" : "C", "params" : [c1x,c1y,x2,y2,x,y] });
            lcx = x2; lcy = y2; cx = x; cy = y; lastCmd = "S";
        }
        else if (uc == "Q")
        {
            var o = rel ? cx : 0; var oy = rel ? cy : 0;
            var qx = p[0]+o; var qy = p[1]+oy;
            var x = p[2]+o;  var y = p[3]+oy;
            var c1x = cx + 2.0/3.0*(qx-cx); var c1y = cy + 2.0/3.0*(qy-cy);
            var c2x = x + 2.0/3.0*(qx-x);   var c2y = y + 2.0/3.0*(qy-y);
            res = append(res, { "cmd" : "C", "params" : [c1x,c1y,c2x,c2y,x,y] });
            lcx = qx; lcy = qy; cx = x; cy = y; lastCmd = "Q";
        }
        else if (uc == "T")
        {
            var qx = cx; var qy = cy;
            if (lastCmd == "Q" || lastCmd == "T")
            { qx = 2*cx - lcx; qy = 2*cy - lcy; }
            var o = rel ? cx : 0; var oy = rel ? cy : 0;
            var x = p[0]+o; var y = p[1]+oy;
            var c1x = cx + 2.0/3.0*(qx-cx); var c1y = cy + 2.0/3.0*(qy-cy);
            var c2x = x + 2.0/3.0*(qx-x);   var c2y = y + 2.0/3.0*(qy-y);
            res = append(res, { "cmd" : "C", "params" : [c1x,c1y,c2x,c2y,x,y] });
            lcx = qx; lcy = qy; cx = x; cy = y; lastCmd = "T";
        }
        else if (uc == "A")
        {
            var arx = abs(p[0]); var ary = abs(p[1]);
            var rot = p[2]; var fa = p[3]; var fs = p[4];
            var o = rel ? cx : 0; var oy = rel ? cy : 0;
            var x = p[5]+o; var y = p[6]+oy;
            if (arx == 0 || ary == 0)
            {
                res = append(res, { "cmd" : "L", "params" : [x, y] });
            }
            else if (abs(arx - ary) < 0.01 * max(arx, ary))
            {
                var ac = endpointToCenter(cx, cy, arx, ary, rot, fa, fs, x, y);
                res = append(res, { "cmd" : "A", "params" : [ac.cx, ac.cy, ac.r, ac.startDeg, ac.sweepDeg] });
            }
            else
            {
                var bezs = arcToBeziers(cx, cy, arx, ary, rot, fa, fs, x, y);
                for (var b = 0; b < size(bezs); b += 1)
                    res = append(res, bezs[b]);
            }
            cx = x; cy = y; lastCmd = "A";
        }
        else if (uc == "Z")
        {
            res = append(res, { "cmd" : "Z", "params" : [] });
            cx = sx; cy = sy; lastCmd = "Z";
        }
    }
    return res;
}

// ============================================================================
// Section 9: Transform Parser
// ============================================================================

function identityMtx() returns array
{
    return [1, 0, 0, 1, 0, 0]; // [a, b, c, d, e, f]
}

function multiplyMtx(m1 is array, m2 is array) returns array
{
    return [
        m1[0]*m2[0] + m1[2]*m2[1],
        m1[1]*m2[0] + m1[3]*m2[1],
        m1[0]*m2[2] + m1[2]*m2[3],
        m1[1]*m2[2] + m1[3]*m2[3],
        m1[0]*m2[4] + m1[2]*m2[5] + m1[4],
        m1[1]*m2[4] + m1[3]*m2[5] + m1[5]
    ];
}

function parseTransformAttr(s is string) returns array
{
    var mtx = identityMtx();
    var ch = splitIntoCharacters(s);
    var n = size(ch);
    var pos = 0;

    while (pos < n)
    {
        pos = skipWS(ch, pos);
        if (pos >= n)
            break;

        // Read function name
        var ns = pos;
        while (pos < n && ch[pos] != "(" && !isWS(ch[pos]))
            pos += 1;
        var fname = toLowerStr(charsToString(ch, ns, pos));

        pos = skipWS(ch, pos);
        if (pos >= n || ch[pos] != "(")
            break;
        pos += 1;

        // Read parameters
        var params = [];
        while (pos < n && ch[pos] != ")")
        {
            pos = skipWS(ch, pos);
            if (pos < n && ch[pos] == ",")
            { pos += 1; continue; }
            if (pos < n && ch[pos] == ")")
                break;
            if (pos < n && (isDigit(ch[pos]) || ch[pos] == "-" || ch[pos] == "+" || ch[pos] == "."))
            {
                var r = parseNum(ch, pos);
                params = append(params, r.val);
                pos = r.pos;
            }
            else
                pos += 1;
        }
        if (pos < n)
            pos += 1; // skip )

        var t = identityMtx();
        if (fname == "translate")
        {
            var tx = size(params) > 0 ? params[0] : 0;
            var ty = size(params) > 1 ? params[1] : 0;
            t = [1, 0, 0, 1, tx, ty];
        }
        else if (fname == "scale")
        {
            var sx = size(params) > 0 ? params[0] : 1;
            var sy = size(params) > 1 ? params[1] : sx;
            t = [sx, 0, 0, sy, 0, 0];
        }
        else if (fname == "rotate")
        {
            var deg = size(params) > 0 ? params[0] : 0;
            var rad = deg * MY_PI / 180;
            var c = cosNum(rad); var s2 = sinNum(rad);
            if (size(params) >= 3)
            {
                var px = params[1]; var py = params[2];
                t = multiplyMtx([1,0,0,1,px,py], multiplyMtx([c,s2,-s2,c,0,0], [1,0,0,1,-px,-py]));
            }
            else
            {
                t = [c, s2, -s2, c, 0, 0];
            }
        }
        else if (fname == "skewx")
        {
            var rad = (size(params) > 0 ? params[0] : 0) * MY_PI / 180;
            t = [1, 0, sinNum(rad)/cosNum(rad), 1, 0, 0];
        }
        else if (fname == "skewy")
        {
            var rad = (size(params) > 0 ? params[0] : 0) * MY_PI / 180;
            t = [1, sinNum(rad)/cosNum(rad), 0, 1, 0, 0];
        }
        else if (fname == "matrix" && size(params) >= 6)
        {
            t = [params[0], params[1], params[2], params[3], params[4], params[5]];
        }

        mtx = multiplyMtx(mtx, t);
    }
    return mtx;
}

function applyMtxToPath(commands is array, mtx is array) returns array
{
    if (mtx[0] == 1 && mtx[1] == 0 && mtx[2] == 0 && mtx[3] == 1 && mtx[4] == 0 && mtx[5] == 0)
        return commands; // identity

    var a = mtx[0]; var b = mtx[1]; var c = mtx[2]; var d = mtx[3]; var e = mtx[4]; var f = mtx[5];
    var result = [];

    for (var i = 0; i < size(commands); i += 1)
    {
        var cmd = commands[i].cmd;
        var p = commands[i].params;

        if (cmd == "M" || cmd == "L")
        {
            var nx = a*p[0] + c*p[1] + e;
            var ny = b*p[0] + d*p[1] + f;
            result = append(result, { "cmd" : cmd, "params" : [nx, ny] });
        }
        else if (cmd == "C")
        {
            result = append(result, { "cmd" : "C", "params" : [
                a*p[0]+c*p[1]+e, b*p[0]+d*p[1]+f,
                a*p[2]+c*p[3]+e, b*p[2]+d*p[3]+f,
                a*p[4]+c*p[5]+e, b*p[4]+d*p[5]+f
            ] });
        }
        else if (cmd == "A")
        {
            var ocx = p[0]; var ocy = p[1]; var r = p[2];
            var ncx = a*ocx + c*ocy + e;
            var ncy = b*ocx + d*ocy + f;
            var sx2 = sqrtNum(a*a + b*b);
            var sy2 = sqrtNum(c*c + d*d);
            var nr = r * (sx2 + sy2) / 2;
            var rotAngle = atan2Num(b, a) * 180 / MY_PI;
            var det = a*d - b*c;
            var startDeg = p[3] - rotAngle;
            var sweepDeg = (det >= 0) ? p[4] : -p[4];
            result = append(result, { "cmd" : "A", "params" : [ncx, ncy, nr, startDeg, sweepDeg] });
        }
        else if (cmd == "Z")
        {
            result = append(result, { "cmd" : "Z", "params" : [] });
        }
    }
    return result;
}

// ============================================================================
// Section 10: Shape Converters
// ============================================================================

function ga(attrs is map, name is string, def is number) returns number
{
    if (attrs[name] == undefined)
        return def;
    var ch = splitIntoCharacters(attrs[name]);
    // Strip non-numeric suffixes (px, em, etc.)
    var r = parseNum(ch, 0);
    return r.val;
}

function shapeToPathD(tag is string, attrs is map) returns string
{
    if (tag == "rect")
    {
        var x = ga(attrs, "x", 0); var y = ga(attrs, "y", 0);
        var w = ga(attrs, "width", 0); var h = ga(attrs, "height", 0);
        var rx = ga(attrs, "rx", 0); var ry = ga(attrs, "ry", 0);
        if (rx == 0 && ry > 0) rx = ry;
        if (ry == 0 && rx > 0) ry = rx;
        if (rx > w/2) rx = w/2;
        if (ry > h/2) ry = h/2;
        if (w <= 0 || h <= 0) return "";
        if (rx > 0 && ry > 0)
        {
            return "M" ~ toString(x+rx) ~ "," ~ toString(y) ~
                   "L" ~ toString(x+w-rx) ~ "," ~ toString(y) ~
                   "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,0,1," ~ toString(x+w) ~ "," ~ toString(y+ry) ~
                   "L" ~ toString(x+w) ~ "," ~ toString(y+h-ry) ~
                   "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,0,1," ~ toString(x+w-rx) ~ "," ~ toString(y+h) ~
                   "L" ~ toString(x+rx) ~ "," ~ toString(y+h) ~
                   "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,0,1," ~ toString(x) ~ "," ~ toString(y+h-ry) ~
                   "L" ~ toString(x) ~ "," ~ toString(y+ry) ~
                   "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,0,1," ~ toString(x+rx) ~ "," ~ toString(y) ~ "Z";
        }
        return "M" ~ toString(x) ~ "," ~ toString(y) ~
               "L" ~ toString(x+w) ~ "," ~ toString(y) ~
               "L" ~ toString(x+w) ~ "," ~ toString(y+h) ~
               "L" ~ toString(x) ~ "," ~ toString(y+h) ~ "Z";
    }
    else if (tag == "circle")
    {
        var cx = ga(attrs, "cx", 0); var cy = ga(attrs, "cy", 0);
        var r = ga(attrs, "r", 0);
        if (r <= 0) return "";
        return "M" ~ toString(cx+r) ~ "," ~ toString(cy) ~
               "A" ~ toString(r) ~ "," ~ toString(r) ~ ",0,1,1," ~ toString(cx-r) ~ "," ~ toString(cy) ~
               "A" ~ toString(r) ~ "," ~ toString(r) ~ ",0,1,1," ~ toString(cx+r) ~ "," ~ toString(cy) ~ "Z";
    }
    else if (tag == "ellipse")
    {
        var cx = ga(attrs, "cx", 0); var cy = ga(attrs, "cy", 0);
        var rx = ga(attrs, "rx", 0); var ry = ga(attrs, "ry", 0);
        if (rx <= 0 || ry <= 0) return "";
        return "M" ~ toString(cx+rx) ~ "," ~ toString(cy) ~
               "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,1,1," ~ toString(cx-rx) ~ "," ~ toString(cy) ~
               "A" ~ toString(rx) ~ "," ~ toString(ry) ~ ",0,1,1," ~ toString(cx+rx) ~ "," ~ toString(cy) ~ "Z";
    }
    else if (tag == "line")
    {
        return "M" ~ toString(ga(attrs,"x1",0)) ~ "," ~ toString(ga(attrs,"y1",0)) ~
               "L" ~ toString(ga(attrs,"x2",0)) ~ "," ~ toString(ga(attrs,"y2",0));
    }
    else if (tag == "polyline" || tag == "polygon")
    {
        var pts = attrs["points"];
        if (pts == undefined || pts == "") return "";
        // Points is a list of numbers separated by commas/whitespace
        var pch = splitIntoCharacters(pts);
        var nums = [];
        var pos = 0;
        while (pos < size(pch))
        {
            pos = skipWS(pch, pos);
            if (pos < size(pch) && pch[pos] == ",")
            { pos += 1; continue; }
            if (pos < size(pch) && (isDigit(pch[pos]) || pch[pos] == "-" || pch[pos] == "+" || pch[pos] == "."))
            {
                var r = parseNum(pch, pos);
                nums = append(nums, r.val);
                pos = r.pos;
            }
            else
                pos += 1;
        }
        if (size(nums) < 4) return "";
        var d = "M" ~ toString(nums[0]) ~ "," ~ toString(nums[1]);
        for (var j = 2; j + 1 < size(nums); j += 2)
            d = d ~ "L" ~ toString(nums[j]) ~ "," ~ toString(nums[j+1]);
        if (tag == "polygon")
            d = d ~ "Z";
        return d;
    }
    return "";
}

// ============================================================================
// Section 10b: Hershey Simplex Font (text-to-path)
// ============================================================================

// 95 ASCII printable characters (space=32 through tilde=126)
// Format: glyphs separated by ";", each glyph = "width,x1,y1,x2,y2,..." with -1,-1 for pen-up
// Hershey coordinate system: Y goes up, cap height = 21, baseline = 0
const HERSHEY_FONT = "16;10,5,21,5,7,-1,-1,5,2,4,1,5,0,6,1,5,2;16,4,21,4,14,-1,-1,12,21,12,14;21,11,25,4,-7,-1,-1,17,25,10,-7,-1,-1,4,12,18,12,-1,-1,3,6,17,6;20,8,25,8,-4,-1,-1,12,25,12,-4,-1,-1,17,18,15,20,12,21,8,21,5,20,3,18,3,16,4,14,5,13,7,12,13,10,15,9,16,8,17,6,17,3,15,1,12,0,8,0,5,1,3,3;24,21,21,3,0,-1,-1,8,21,10,19,10,17,9,15,7,14,5,14,3,16,3,18,4,20,6,21,8,21,10,20,13,19,16,19,19,20,21,21,-1,-1,17,7,15,6,14,4,14,2,16,0,18,0,20,1,21,3,21,5,19,7,17,7;26,23,12,23,13,22,14,21,14,20,13,19,11,17,6,15,3,13,1,11,0,7,0,5,1,4,2,3,4,3,6,4,8,5,9,12,13,13,14,14,16,14,18,13,20,11,21,9,20,8,18,8,16,9,13,11,10,16,3,18,1,20,0,22,0,23,1,23,2;10,5,19,4,20,5,21,6,20,6,18,5,16,4,15;14,11,25,9,23,7,20,5,16,4,11,4,7,5,2,7,-2,9,-5,11,-7;14,3,25,5,23,7,20,9,16,10,11,10,7,9,2,7,-2,5,-5,3,-7;16,8,21,8,9,-1,-1,3,18,13,12,-1,-1,13,18,3,12;26,13,18,13,0,-1,-1,4,9,22,9;10,6,1,5,0,4,1,5,2,6,1,6,-1,5,-3,4,-4;26,4,9,22,9;10,5,2,4,1,5,0,6,1,5,2;22,20,25,2,-7;20,9,21,6,20,4,17,3,12,3,9,4,4,6,1,9,0,11,0,14,1,16,4,17,9,17,12,16,17,14,20,11,21,9,21;20,6,17,8,18,11,21,11,0;20,4,16,4,17,5,19,6,20,8,21,12,21,14,20,15,19,16,17,16,15,15,13,13,10,3,0,17,0;20,5,21,16,21,10,13,13,13,15,12,16,11,17,8,17,6,16,3,14,1,11,0,8,0,5,1,4,2,3,4;20,13,21,3,7,18,7,-1,-1,13,21,13,0;20,15,21,5,21,4,12,5,13,8,14,11,14,14,13,16,11,17,8,17,6,16,3,14,1,11,0,8,0,5,1,4,2,3,4;20,16,18,15,20,12,21,10,21,7,20,5,17,4,12,4,7,5,3,7,1,10,0,11,0,14,1,16,3,17,6,17,7,16,10,14,12,11,13,10,13,7,12,5,10,4,7;20,17,21,7,0,-1,-1,3,21,17,21;20,8,21,5,20,4,18,4,16,5,14,7,13,11,12,14,11,16,9,17,7,17,4,16,2,15,1,12,0,8,0,5,1,4,2,3,4,3,7,4,9,6,11,9,12,13,13,15,14,16,16,16,18,15,20,12,21,8,21;20,16,14,15,11,13,9,10,8,9,8,6,9,4,11,3,14,3,15,4,18,6,20,9,21,10,21,13,20,15,18,16,14,16,9,15,4,13,1,10,0,8,0,5,1,4,3;10,5,14,4,13,5,12,6,13,5,14,-1,-1,5,2,4,1,5,0,6,1,5,2;10,5,14,4,13,5,12,6,13,5,14,-1,-1,6,1,5,0,4,1,5,2,6,1,6,-1,5,-3,4,-4;24,20,18,4,9,20,0;26,4,12,22,12,-1,-1,4,6,22,6;24,4,18,20,9,4,0;18,3,16,3,17,4,19,5,20,7,21,11,21,13,20,14,19,15,17,15,15,14,13,13,12,9,10,9,7,-1,-1,9,2,8,1,9,0,10,1,9,2;27,18,13,17,15,15,16,12,16,10,15,9,14,8,11,8,8,9,6,11,5,14,5,16,6,17,8,-1,-1,12,16,10,14,9,11,9,8,10,6,11,5,-1,-1,18,16,17,8,17,6,19,5,21,5,23,7,24,10,24,12,23,15,22,17,20,19,18,20,15,21,12,21,9,20,7,19,5,17,4,15,3,12,3,9,4,6,5,4,7,2,9,1,12,0,15,0,18,1,20,2,21,3,-1,-1,19,16,18,8,18,6,19,5;18,9,21,1,0,-1,-1,9,21,17,0,-1,-1,4,7,14,7;21,4,21,4,0,-1,-1,4,21,13,21,16,20,17,19,18,17,18,15,17,13,16,12,13,11,-1,-1,4,11,13,11,16,10,17,9,18,7,18,4,17,2,16,1,13,0,4,0;21,18,16,17,18,15,20,13,21,9,21,7,20,5,18,4,16,3,13,3,8,4,5,5,3,7,1,9,0,13,0,15,1,17,3,18,5;21,4,21,4,0,-1,-1,4,21,11,21,14,20,16,18,17,16,18,13,18,8,17,5,16,3,14,1,11,0,4,0;19,4,21,4,0,-1,-1,4,21,17,21,-1,-1,4,11,12,11,-1,-1,4,0,17,0;18,4,21,4,0,-1,-1,4,21,17,21,-1,-1,4,11,12,11;21,18,16,17,18,15,20,13,21,9,21,7,20,5,18,4,16,3,13,3,8,4,5,5,3,7,1,9,0,13,0,15,1,17,3,18,5,18,8,-1,-1,13,8,18,8;22,4,21,4,0,-1,-1,18,21,18,0,-1,-1,4,11,18,11;8,4,21,4,0;16,12,21,12,5,11,2,10,1,8,0,6,0,4,1,3,2,2,5,2,7;21,4,21,4,0,-1,-1,18,21,4,7,-1,-1,9,12,18,0;17,4,21,4,0,-1,-1,4,0,16,0;24,4,21,4,0,-1,-1,4,21,12,0,-1,-1,20,21,12,0,-1,-1,20,21,20,0;22,4,21,4,0,-1,-1,4,21,18,0,-1,-1,18,21,18,0;22,9,21,7,20,5,18,4,16,3,13,3,8,4,5,5,3,7,1,9,0,13,0,15,1,17,3,18,5,19,8,19,13,18,16,17,18,15,20,13,21,9,21;21,4,21,4,0,-1,-1,4,21,13,21,16,20,17,19,18,17,18,14,17,12,16,11,13,10,4,10;22,9,21,7,20,5,18,4,16,3,13,3,8,4,5,5,3,7,1,9,0,13,0,15,1,17,3,18,5,19,8,19,13,18,16,17,18,15,20,13,21,9,21,-1,-1,12,4,18,-2;21,4,21,4,0,-1,-1,4,21,13,21,16,20,17,19,18,17,18,15,17,13,16,12,13,11,4,11,-1,-1,11,11,18,0;20,17,18,15,20,12,21,8,21,5,20,3,18,3,16,4,14,5,13,7,12,13,10,15,9,16,8,17,6,17,3,15,1,12,0,8,0,5,1,3,3;16,8,21,8,0,-1,-1,1,21,15,21;22,4,21,4,6,5,3,7,1,10,0,12,0,15,1,17,3,18,6,18,21;18,1,21,9,0,-1,-1,17,21,9,0;24,2,21,7,0,-1,-1,12,21,7,0,-1,-1,12,21,17,0,-1,-1,22,21,17,0;20,3,21,17,0,-1,-1,17,21,3,0;18,1,21,9,11,9,0,-1,-1,17,21,9,11;20,17,21,3,0,-1,-1,3,21,17,21,-1,-1,3,0,17,0;14,4,25,4,-7,-1,-1,5,25,5,-7,-1,-1,4,25,11,25,-1,-1,4,-7,11,-7;14,0,21,14,-3;14,9,25,9,-7,-1,-1,10,25,10,-7,-1,-1,3,25,10,25,-1,-1,3,-7,10,-7;16,6,15,8,18,10,15,-1,-1,3,12,8,17,13,12,-1,-1,8,17,8,0;16,0,-2,16,-2;10,6,21,5,20,4,18,4,16,5,15,6,16,5,17;19,15,14,15,0,-1,-1,15,11,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;19,4,21,4,0,-1,-1,4,11,6,13,8,14,11,14,13,13,15,11,16,8,16,6,15,3,13,1,11,0,8,0,6,1,4,3;18,15,11,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;19,15,21,15,0,-1,-1,15,11,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;18,3,8,15,8,15,10,14,12,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;12,10,21,8,21,6,20,5,17,5,0,-1,-1,2,14,9,14;19,15,14,15,-2,14,-5,13,-6,11,-7,8,-7,6,-6,-1,-1,15,11,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;19,4,21,4,0,-1,-1,4,10,7,13,9,14,12,14,14,13,15,10,15,0;8,3,21,4,20,5,21,4,22,3,21,-1,-1,4,14,4,0;10,5,21,6,20,7,21,6,22,5,21,-1,-1,6,14,6,-3,5,-6,3,-7,1,-7;17,4,21,4,0,-1,-1,14,14,4,4,-1,-1,8,8,15,0;8,4,21,4,0;30,4,14,4,0,-1,-1,4,10,7,13,9,14,12,14,14,13,15,10,15,0,-1,-1,15,10,18,13,20,14,23,14,25,13,26,10,26,0;19,4,14,4,0,-1,-1,4,10,7,13,9,14,12,14,14,13,15,10,15,0;19,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3,16,6,16,8,15,11,13,13,11,14,8,14;19,4,14,4,-7,-1,-1,4,11,6,13,8,14,11,14,13,13,15,11,16,8,16,6,15,3,13,1,11,0,8,0,6,1,4,3;19,15,14,15,-7,-1,-1,15,11,13,13,11,14,8,14,6,13,4,11,3,8,3,6,4,3,6,1,8,0,11,0,13,1,15,3;13,4,14,4,0,-1,-1,4,8,5,11,7,13,9,14,12,14;17,14,11,13,13,10,14,7,14,4,13,3,11,4,9,6,8,11,7,13,6,14,4,14,3,13,1,10,0,7,0,4,1,3,3;12,5,21,5,4,6,1,8,0,10,0,-1,-1,2,14,9,14;19,4,14,4,4,5,1,7,0,10,0,12,1,15,4,-1,-1,15,14,15,0;16,2,14,8,0,-1,-1,14,14,8,0;22,3,14,7,0,-1,-1,11,14,7,0,-1,-1,11,14,15,0,-1,-1,19,14,15,0;17,3,14,14,0,-1,-1,14,14,3,0;16,2,14,8,0,-1,-1,14,14,8,0,6,-4,4,-6,2,-7,1,-7;17,14,14,3,0,-1,-1,3,14,14,14,-1,-1,3,0,14,0;14,9,25,7,24,6,23,5,21,5,19,6,17,7,16,8,14,8,12,6,10,-1,-1,7,24,6,22,6,20,7,18,8,17,9,15,9,13,8,11,4,9,8,7,9,5,9,3,8,1,7,0,6,-2,6,-4,7,-6,-1,-1,6,-2,8,-4,8,-6,9,-8;8,4,25,4,-7;14,5,25,7,24,8,23,9,21,9,19,8,17,7,16,6,14,6,12,8,10,-1,-1,7,24,8,22,8,20,7,18,6,17,5,15,5,13,6,11,10,9,6,7,5,5,5,3,6,1,7,0,8,-2,8,-4,7,-6,-1,-1,8,-2,6,-4,6,-6,5,-8;24,3,6,3,8,4,11,6,12,8,12,10,11,14,8,16,7,18,7,20,8,21,10,-1,-1,3,8,4,10,6,11,8,11,10,10,14,7,16,6,18,6,20,7,21,10,21,12";

const HERSHEY_CAP_HEIGHT = 21;

// Parse a number string using parseNum
function strToNum(s is string) returns number
{
    var ch = splitIntoCharacters(s);
    return parseNum(ch, 0).val;
}

// Parse Hershey font data into array of 95 glyph maps
// Each glyph: { "width" : number, "strokes" : [[x,y,x,y,...], ...] }
function parseHersheyFont() returns array
{
    var glyphs = splitByChar(HERSHEY_FONT, ";");
    var result = [];
    for (var g = 0; g < size(glyphs); g += 1)
    {
        var nums = splitByChar(glyphs[g], ",");
        if (size(nums) == 0)
        {
            result = append(result, { "width" : 10, "strokes" : [] });
            continue;
        }
        var width = strToNum(nums[0]);
        var strokes = [];
        var currentStroke = [];
        var i = 1;
        while (i + 1 < size(nums))
        {
            var x = strToNum(nums[i]);
            var y = strToNum(nums[i + 1]);
            if (x == -1 && y == -1)
            {
                // Pen-up: save current stroke and start new one
                if (size(currentStroke) >= 4)
                    strokes = append(strokes, currentStroke);
                currentStroke = [];
            }
            else
            {
                currentStroke = append(currentStroke, x);
                currentStroke = append(currentStroke, y);
            }
            i += 2;
        }
        if (size(currentStroke) >= 4)
            strokes = append(strokes, currentStroke);
        result = append(result, { "width" : width, "strokes" : strokes });
    }
    return result;
}

// Render a text string using Hershey font, producing stroke-type path commands
// Returns array of path maps (source="stroke") ready for strokeToOutlines()
// x, y: position in SVG coordinates (y increases downward)
// fontSize: desired font size in SVG units
// textAnchor: "start", "middle", or "end"
function renderHersheyText(text is string, x is number, y is number,
    fontSize is number, textAnchor is string) returns array
{
    var hersheyGlyphs = parseHersheyFont();
    var scale = fontSize / HERSHEY_CAP_HEIGHT;
    var strokeWidth = fontSize / 10; // Reasonable stroke width for outlined text
    var chars = splitIntoCharacters(text);

    // Compute total width for text-anchor alignment
    var totalWidth = 0;
    for (var c = 0; c < size(chars); c += 1)
    {
        var code = charToAscii(chars[c]);
        if (code >= 32 && code <= 126)
            totalWidth += hersheyGlyphs[code - 32].width * scale;
        else
            totalWidth += 10 * scale; // fallback width for unsupported chars
    }

    var offsetX = 0;
    if (textAnchor == "middle")
        offsetX = -totalWidth / 2;
    else if (textAnchor == "end")
        offsetX = -totalWidth;

    var paths = [];
    var cursorX = x + offsetX;

    for (var c = 0; c < size(chars); c += 1)
    {
        var code = charToAscii(chars[c]);
        if (code < 32 || code > 126)
        {
            cursorX += 10 * scale;
            continue;
        }
        var glyph = hersheyGlyphs[code - 32];
        // Each stroke becomes a separate path
        for (var s = 0; s < size(glyph.strokes); s += 1)
        {
            var stroke = glyph.strokes[s];
            var cmds = [];
            for (var p = 0; p < size(stroke); p += 2)
            {
                var gx = stroke[p] * scale + cursorX;
                // Hershey Y=0 is baseline, Y goes up; SVG Y goes down
                // Flip: svgY = y - (hersheyY * scale)
                var gy = y - (stroke[p + 1] * scale);
                if (p == 0)
                    cmds = append(cmds, { "cmd" : "M", "params" : [gx, gy] });
                else
                    cmds = append(cmds, { "cmd" : "L", "params" : [gx, gy] });
            }
            if (size(cmds) >= 2)
            {
                paths = append(paths, {
                    "commands" : cmds,
                    "fillRule" : "nonzero",
                    "source" : "stroke",
                    "strokeWidth" : strokeWidth
                });
            }
        }
        cursorX += glyph.width * scale;
    }
    return paths;
}

// Convert a single character to its ASCII code
function charToAscii(ch is string) returns number
{
    // Map printable ASCII characters to their codes
    var asciiChars = splitIntoCharacters(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~");
    for (var i = 0; i < size(asciiChars); i += 1)
    {
        if (asciiChars[i] == ch)
            return 32 + i;
    }
    return -1; // unsupported character
}

// ============================================================================
// Section 11: SVG Document Parser
// ============================================================================

function getFillInfo(attrs is map) returns map
{
    var fill = attrs["fill"];
    var hasFill = true;
    var fillRule = "nonzero";

    if (fill != undefined)
    {
        var fl = trimStr(fill);
        if (fl == "none" || fl == "transparent")
            hasFill = false;
    }
    // fill-rule
    if (attrs["fill-rule"] != undefined)
        fillRule = trimStr(attrs["fill-rule"]);

    return { "hasFill" : hasFill, "fillRule" : fillRule, "fill" : fill };
}

function getStrokeInfo(attrs is map) returns map
{
    var stroke = attrs["stroke"];
    var hasStroke = false;
    var strokeWidth = 1.0;

    if (stroke != undefined)
    {
        var sl = trimStr(stroke);
        if (sl != "none" && sl != "" && sl != "transparent")
            hasStroke = true;
    }
    if (attrs["stroke-width"] != undefined)
    {
        var sw = splitIntoCharacters(trimStr(attrs["stroke-width"]));
        var r = parseNum(sw, 0);
        strokeWidth = r.val;
    }
    return { "hasStroke" : hasStroke, "strokeWidth" : strokeWidth };
}

function isUrlFill(fill) returns boolean
{
    if (fill == undefined)
        return false;
    // Check if fill starts with "url("
    var ch = splitIntoCharacters(trimStr(fill));
    return size(ch) >= 4 && ch[0] == "u" && ch[1] == "r" && ch[2] == "l" && ch[3] == "(";
}

function parseSvgDocument(content is string) returns map
{
    var chars = splitIntoCharacters(content);
    var tags = scanTags(chars);
    var cssRules = parseCssBlocks(tags);

    var viewBox = { "minX" : 0, "minY" : 0, "width" : 100, "height" : 100 };
    var paths = [];
    var warnings = [];
    var transformStack = [identityMtx()];
    var inDefs = false;
    var skipDepth = 0;
    var skipTag = "";

    // Collect defs by id for <use> resolution
    var defsById = {}; // id -> { tag, attrs, pathD }

    var pathElements = { "path" : true, "rect" : true, "circle" : true,
                         "ellipse" : true, "line" : true, "polyline" : true, "polygon" : true };
    var groupElements = { "g" : true, "svg" : true, "a" : true, "switch" : true };
    var skipElements = { "clippath" : true, "mask" : true, "filter" : true, "image" : true,
                         "metadata" : true, "desc" : true, "title" : true };

    var hasUrlFills = false;
    var hasTextElements = false;
    var hasCssStyles = (size(cssRules) > 0);

    for (var i = 0; i < size(tags); i += 1)
    {
        var tag = parseTag(tags[i].tagStr);
        var name = tag.name;

        // Handle closing tags
        if (tag.isClose)
        {
            if (name == "defs" || name == "symbol")
            {
                inDefs = false;
            }
            if (skipDepth > 0 && name == skipTag)
            {
                skipDepth -= 1;
                if (skipDepth == 0)
                    skipTag = "";
                continue;
            }
            if (groupElements[name] == true && size(transformStack) > 1)
                transformStack = subArray(transformStack, 0, size(transformStack) - 1);
            continue;
        }

        // Skip elements in skip mode
        if (skipDepth > 0)
        {
            if (!tag.selfClose)
                skipDepth += 1;
            continue;
        }

        // <defs> / <symbol>
        if (name == "defs" || name == "symbol")
        {
            inDefs = true;
            continue;
        }

        // Skip certain elements entirely
        if (skipElements[name] == true)
        {
            if (!tag.selfClose)
            { skipDepth = 1; skipTag = name; }
            continue;
        }

        // <style> is handled by CSS parser, skip
        if (name == "style")
        {
            if (!tag.selfClose)
            { skipDepth = 1; skipTag = "style"; }
            continue;
        }

        // Handle <text> elements — render with Hershey font
        if (name == "text")
        {
            hasTextElements = true;
            if (tag.selfClose)
                continue;
            // Collect text content from this tag and all child tags until </text>
            var textAttrs = applyCssRules(tag.attrs, cssRules);
            textAttrs = parseInlineStyle(textAttrs);
            var textX = ga(textAttrs, "x", 0);
            var textY = ga(textAttrs, "y", 0);
            var textFontSize = ga(textAttrs, "font-size", 16);
            var textAnchor = "start";
            if (textAttrs["text-anchor"] != undefined)
                textAnchor = trimStr(textAttrs["text-anchor"]);
            // Collect text content: textAfter of <text> + textAfter of children
            var collectedText = trimStr(tags[i].textAfter);
            // Scan forward to collect tspan contents until </text>
            var textDepth = 1;
            while (i + 1 < size(tags) && textDepth > 0)
            {
                i += 1;
                var childTag = parseTag(tags[i].tagStr);
                if (childTag.isClose)
                {
                    if (childTag.name == "text")
                        textDepth -= 1;
                }
                else if (childTag.name == "tspan")
                {
                    // tspan can override x/y but we collect its text
                    var tspanText = trimStr(tags[i].textAfter);
                    if (length(tspanText) > 0)
                    {
                        if (length(collectedText) > 0)
                            collectedText = collectedText ~ " ";
                        collectedText = collectedText ~ tspanText;
                    }
                }
                else if (!childTag.isClose)
                {
                    // Other child elements — collect their textAfter too
                    var childText = trimStr(tags[i].textAfter);
                    if (length(childText) > 0)
                    {
                        if (length(collectedText) > 0)
                            collectedText = collectedText ~ " ";
                        collectedText = collectedText ~ childText;
                    }
                    if (!childTag.selfClose)
                        textDepth += 1;
                }
            }
            // Render collected text with Hershey font
            if (length(collectedText) > 0)
            {
                var curMtx = transformStack[size(transformStack)-1];
                // Apply text element transform if any
                var textMtx = identityMtx();
                if (textAttrs["transform"] != undefined)
                    textMtx = parseTransformAttr(textAttrs["transform"]);
                var fullMtx = multiplyMtx(curMtx, textMtx);

                var textPaths = renderHersheyText(collectedText, textX, textY,
                    textFontSize, textAnchor);
                // Apply transform to all text paths
                for (var tp = 0; tp < size(textPaths); tp += 1)
                {
                    var xformed = applyMtxToPath(textPaths[tp].commands, fullMtx);
                    paths = append(paths, {
                        "commands" : xformed,
                        "fillRule" : textPaths[tp].fillRule,
                        "source" : textPaths[tp].source,
                        "strokeWidth" : textPaths[tp].strokeWidth
                    });
                }
            }
            continue;
        }
        if (name == "tspan")
        {
            // tspan outside of text context — skip
            if (!tag.selfClose)
            { skipDepth = 1; skipTag = "tspan"; }
            continue;
        }

        // Merge CSS + inline styles
        var attrs = applyCssRules(tag.attrs, cssRules);
        attrs = parseInlineStyle(attrs);

        // Check visibility
        if (attrs["display"] != undefined && trimStr(attrs["display"]) == "none")
        {
            if (!tag.selfClose)
            { skipDepth = 1; skipTag = name; }
            continue;
        }
        if (attrs["visibility"] != undefined && trimStr(attrs["visibility"]) == "hidden")
        {
            if (!tag.selfClose)
            { skipDepth = 1; skipTag = name; }
            continue;
        }

        // <svg> root: extract viewBox
        if (name == "svg")
        {
            if (attrs["viewbox"] != undefined)
            {
                var vb = attrs["viewbox"];
                var vch = splitIntoCharacters(replace(vb, ",", " "));
                var nums = [];
                var vpos = 0;
                while (vpos < size(vch) && size(nums) < 4)
                {
                    vpos = skipWS(vch, vpos);
                    if (vpos < size(vch) && (isDigit(vch[vpos]) || vch[vpos] == "-" || vch[vpos] == "+" || vch[vpos] == "."))
                    {
                        var r = parseNum(vch, vpos);
                        nums = append(nums, r.val);
                        vpos = r.pos;
                    }
                    else
                        vpos += 1;
                }
                if (size(nums) >= 4)
                    viewBox = { "minX" : nums[0], "minY" : nums[1], "width" : nums[2], "height" : nums[3] };
            }
            else
            {
                // Try width/height
                var w = ga(attrs, "width", 100);
                var h = ga(attrs, "height", 100);
                viewBox = { "minX" : 0, "minY" : 0, "width" : w, "height" : h };
            }

            if (!tag.selfClose)
            {
                var mtx = identityMtx();
                if (attrs["transform"] != undefined)
                    mtx = parseTransformAttr(attrs["transform"]);
                transformStack = append(transformStack, multiplyMtx(transformStack[size(transformStack)-1], mtx));
            }
            continue;
        }

        // <use> resolution
        if (name == "use")
        {
            var href = attrs["href"];
            if (href == undefined)
                href = attrs["xlink:href"];
            if (href != undefined)
            {
                var hch = splitIntoCharacters(href);
                if (size(hch) > 1 && hch[0] == "#")
                {
                    var refId = charsToString(hch, 1, size(hch));
                    if (defsById[refId] != undefined)
                    {
                        var def = defsById[refId];
                        var useMtx = identityMtx();
                        var ux = ga(attrs, "x", 0);
                        var uy = ga(attrs, "y", 0);
                        if (ux != 0 || uy != 0)
                            useMtx = [1, 0, 0, 1, ux, uy];
                        if (attrs["transform"] != undefined)
                            useMtx = multiplyMtx(parseTransformAttr(attrs["transform"]), useMtx);
                        var curMtx = transformStack[size(transformStack)-1];
                        var fullMtx = multiplyMtx(curMtx, useMtx);

                        for (var p = 0; p < size(def.paths); p += 1)
                        {
                            var xformed = applyMtxToPath(def.paths[p].commands, fullMtx);
                            paths = append(paths, {
                                "commands" : xformed,
                                "fillRule" : def.paths[p].fillRule,
                                "source" : def.paths[p].source,
                                "strokeWidth" : def.paths[p].strokeWidth
                            });
                        }
                    }
                }
            }
            continue;
        }

        // Groups
        if (groupElements[name] == true)
        {
            if (!tag.selfClose)
            {
                var mtx = identityMtx();
                if (attrs["transform"] != undefined)
                    mtx = parseTransformAttr(attrs["transform"]);
                transformStack = append(transformStack, multiplyMtx(transformStack[size(transformStack)-1], mtx));
            }
            continue;
        }

        // Path & shape elements
        if (pathElements[name] == true)
        {
            var d = "";
            if (name == "path")
                d = (attrs["d"] != undefined) ? decodeXml(attrs["d"]) : "";
            else
                d = shapeToPathD(name, attrs);

            if (d == "")
                continue;

            var rawCmds = parsePathD(d);
            var normCmds = normalizePath(rawCmds);

            // Apply element transform
            var elemMtx = identityMtx();
            if (attrs["transform"] != undefined)
                elemMtx = parseTransformAttr(attrs["transform"]);
            var curMtx = transformStack[size(transformStack)-1];
            var fullMtx = multiplyMtx(curMtx, elemMtx);
            normCmds = applyMtxToPath(normCmds, fullMtx);

            var fillInfo = getFillInfo(attrs);
            var strokeInfo = getStrokeInfo(attrs);

            if (isUrlFill(fillInfo.fill))
                hasUrlFills = true;

            // Store in defs if inside <defs>
            if (inDefs)
            {
                if (attrs["id"] != undefined)
                {
                    var defPaths = [];
                    if (fillInfo.hasFill && !isUrlFill(fillInfo.fill))
                    {
                        defPaths = append(defPaths, {
                            "commands" : normCmds,
                            "fillRule" : fillInfo.fillRule,
                            "source" : "fill",
                            "strokeWidth" : 0
                        });
                    }
                    if (strokeInfo.hasStroke)
                    {
                        defPaths = append(defPaths, {
                            "commands" : normCmds,
                            "fillRule" : "nonzero",
                            "source" : "stroke",
                            "strokeWidth" : strokeInfo.strokeWidth
                        });
                    }
                    defsById[attrs["id"]] = { "paths" : defPaths };
                }
                continue;
            }

            // Add filled path
            if (fillInfo.hasFill && !isUrlFill(fillInfo.fill))
            {
                paths = append(paths, {
                    "commands" : normCmds,
                    "fillRule" : fillInfo.fillRule,
                    "source" : "fill",
                    "strokeWidth" : 0
                });
            }

            // Add stroke path
            if (strokeInfo.hasStroke)
            {
                paths = append(paths, {
                    "commands" : normCmds,
                    "fillRule" : "nonzero",
                    "source" : "stroke",
                    "strokeWidth" : strokeInfo.strokeWidth
                });
            }
        }
    }

    // Build warnings
    if (hasTextElements)
        warnings = append(warnings, "Text elements rendered with built-in Hershey simplex font.");
    if (hasUrlFills)
        warnings = append(warnings, "SVG uses gradient or pattern fills (url references). These elements use solid fill as fallback.");
    if (hasCssStyles)
        warnings = append(warnings, "SVG uses CSS styles (parsed automatically).");

    return { "viewBox" : viewBox, "paths" : paths, "warnings" : warnings };
}

// ============================================================================
// Section 12: Stroke Outliner
// ============================================================================

function flattenCubic(x0 is number, y0 is number, x1 is number, y1 is number,
    x2 is number, y2 is number, x3 is number, y3 is number, numSeg is number) returns array
{
    var pts = [];
    for (var i = 1; i <= numSeg; i += 1)
    {
        var t = i / numSeg;
        var u = 1 - t;
        var px = u*u*u*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t*t*t*x3;
        var py = u*u*u*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t*t*t*y3;
        pts = append(pts, [px, py]);
    }
    return pts;
}

function flattenArc(cx is number, cy is number, r is number,
    startDeg is number, sweepDeg is number, numSeg is number) returns array
{
    var pts = [];
    for (var i = 1; i <= numSeg; i += 1)
    {
        var angle = (startDeg + sweepDeg * i / numSeg) * MY_PI / 180;
        pts = append(pts, [cx + r * cosNum(angle), cy + r * sinNum(angle)]);
    }
    return pts;
}

function splitSubpaths(commands is array) returns array
{
    var subpaths = [];
    var points = [];
    var curX = 0.0;
    var curY = 0.0;
    var startX = 0.0;
    var startY = 0.0;
    var isClosed = false;

    for (var i = 0; i < size(commands); i += 1)
    {
        var cmd = commands[i].cmd;
        var p = commands[i].params;

        if (cmd == "M")
        {
            if (size(points) >= 2)
                subpaths = append(subpaths, { "points" : points, "closed" : isClosed });
            points = [[p[0], p[1]]];
            curX = p[0]; curY = p[1];
            startX = curX; startY = curY;
            isClosed = false;
        }
        else if (cmd == "L")
        {
            points = append(points, [p[0], p[1]]);
            curX = p[0]; curY = p[1];
        }
        else if (cmd == "C")
        {
            var flat = flattenCubic(curX, curY, p[0], p[1], p[2], p[3], p[4], p[5], 12);
            for (var f = 0; f < size(flat); f += 1)
                points = append(points, flat[f]);
            curX = p[4]; curY = p[5];
        }
        else if (cmd == "A")
        {
            var flat = flattenArc(p[0], p[1], p[2], p[3], p[4], 12);
            for (var f = 0; f < size(flat); f += 1)
                points = append(points, flat[f]);
            if (size(flat) > 0)
            {
                curX = flat[size(flat)-1][0];
                curY = flat[size(flat)-1][1];
            }
        }
        else if (cmd == "Z")
        {
            if (abs(curX - startX) > 1e-6 || abs(curY - startY) > 1e-6)
                points = append(points, [startX, startY]);
            isClosed = true;
            curX = startX; curY = startY;
        }
    }
    if (size(points) >= 2)
        subpaths = append(subpaths, { "points" : points, "closed" : isClosed });
    return subpaths;
}

function offsetSegment(p0 is array, p1 is array, offset is number) returns array
{
    var dx = p1[0] - p0[0];
    var dy = p1[1] - p0[1];
    var len = sqrtNum(dx * dx + dy * dy);
    if (len < 1e-10)
        return [p0, p1];
    var nx = -dy / len * offset;
    var ny = dx / len * offset;
    return [[p0[0]+nx, p0[1]+ny], [p1[0]+nx, p1[1]+ny]];
}

function lineIntersect(p1 is array, p2 is array, p3 is array, p4 is array) returns array
{
    var x1 = p1[0]; var y1 = p1[1]; var x2 = p2[0]; var y2 = p2[1];
    var x3 = p3[0]; var y3 = p3[1]; var x4 = p4[0]; var y4 = p4[1];
    var denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4);
    if (abs(denom) < 1e-10)
        return [(p2[0]+p3[0])/2, (p2[1]+p3[1])/2];
    var t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom;
    return [x1 + t*(x2-x1), y1 + t*(y2-y1)];
}

function offsetPolyline(points is array, offset is number, miterLimit is number) returns array
{
    if (size(points) < 2)
        return [];
    // Compute offset segments
    var segs = [];
    for (var i = 0; i < size(points) - 1; i += 1)
        segs = append(segs, offsetSegment(points[i], points[i+1], offset));

    var result = [segs[0][0]];
    for (var i = 0; i < size(segs) - 1; i += 1)
    {
        var inter = lineIntersect(segs[i][0], segs[i][1], segs[i+1][0], segs[i+1][1]);
        // Miter limit check
        var mx = inter[0] - segs[i][1][0];
        var my = inter[1] - segs[i][1][1];
        var miterLen = sqrtNum(mx*mx + my*my);
        if (abs(offset) > 1e-10 && miterLen / abs(offset) > miterLimit)
        {
            result = append(result, segs[i][1]);
            result = append(result, segs[i+1][0]);
        }
        else
        {
            result = append(result, inter);
        }
    }
    result = append(result, segs[size(segs)-1][1]);
    return result;
}

function outlineOpenSubpath(points is array, halfW is number) returns array
{
    var miterLimit = 4.0;
    var outer = offsetPolyline(points, halfW, miterLimit);
    var inner = offsetPolyline(points, -halfW, miterLimit);
    if (size(outer) == 0 || size(inner) == 0)
        return [];

    var cmds = [];
    // Start cap (square)
    var dx = points[1][0] - points[0][0];
    var dy = points[1][1] - points[0][1];
    var len = sqrtNum(dx*dx + dy*dy);
    if (len > 1e-10)
    {
        var capDx = -dx / len * halfW;
        var capDy = -dy / len * halfW;
        cmds = append(cmds, { "cmd" : "M", "params" : [outer[0][0]+capDx, outer[0][1]+capDy] });
        cmds = append(cmds, { "cmd" : "L", "params" : [inner[0][0]+capDx, inner[0][1]+capDy] });
    }
    else
    {
        cmds = append(cmds, { "cmd" : "M", "params" : [outer[0][0], outer[0][1]] });
    }

    // Inner side (reversed)
    for (var i = 0; i < size(inner); i += 1)
        cmds = append(cmds, { "cmd" : "L", "params" : [inner[i][0], inner[i][1]] });

    // End cap (square)
    var last = size(points) - 1;
    dx = points[last][0] - points[last-1][0];
    dy = points[last][1] - points[last-1][1];
    len = sqrtNum(dx*dx + dy*dy);
    if (len > 1e-10)
    {
        var capDx = dx / len * halfW;
        var capDy = dy / len * halfW;
        cmds = append(cmds, { "cmd" : "L", "params" : [inner[size(inner)-1][0]+capDx, inner[size(inner)-1][1]+capDy] });
        cmds = append(cmds, { "cmd" : "L", "params" : [outer[size(outer)-1][0]+capDx, outer[size(outer)-1][1]+capDy] });
    }

    // Outer side (reversed)
    for (var i = size(outer) - 1; i >= 0; i -= 1)
        cmds = append(cmds, { "cmd" : "L", "params" : [outer[i][0], outer[i][1]] });

    cmds = append(cmds, { "cmd" : "Z", "params" : [] });
    return cmds;
}

function outlineClosedSubpath(points is array, halfW is number) returns array
{
    var miterLimit = 4.0;
    // Ensure closed
    var pts = points;
    if (size(pts) >= 2)
    {
        var f = pts[0]; var l = pts[size(pts)-1];
        if (abs(f[0]-l[0]) > 1e-6 || abs(f[1]-l[1]) > 1e-6)
            pts = append(pts, f);
    }

    var outer = offsetPolyline(pts, halfW, miterLimit);
    var inner = offsetPolyline(pts, -halfW, miterLimit);
    if (size(outer) == 0 || size(inner) == 0)
        return [];

    var cmds = [];
    cmds = append(cmds, { "cmd" : "M", "params" : [outer[0][0], outer[0][1]] });
    for (var i = 1; i < size(outer); i += 1)
        cmds = append(cmds, { "cmd" : "L", "params" : [outer[i][0], outer[i][1]] });
    cmds = append(cmds, { "cmd" : "Z", "params" : [] });

    cmds = append(cmds, { "cmd" : "M", "params" : [inner[0][0], inner[0][1]] });
    for (var i = 1; i < size(inner); i += 1)
        cmds = append(cmds, { "cmd" : "L", "params" : [inner[i][0], inner[i][1]] });
    cmds = append(cmds, { "cmd" : "Z", "params" : [] });

    return cmds;
}

function strokeToOutlines(svgPaths is array) returns array
{
    var result = [];
    for (var i = 0; i < size(svgPaths); i += 1)
    {
        var path = svgPaths[i];
        if (path.source != "stroke")
        {
            result = append(result, path);
            continue;
        }
        var sw = path.strokeWidth;
        if (sw == undefined || sw <= 0)
            sw = 1.0;
        var halfW = sw / 2;
        if (halfW < 1e-10)
            continue;

        var subpaths = splitSubpaths(path.commands);
        for (var s = 0; s < size(subpaths); s += 1)
        {
            var pts = subpaths[s].points;
            if (size(pts) < 2)
                continue;
            var outlineCmds = [];
            var fr = "nonzero";
            if (subpaths[s].closed)
            {
                outlineCmds = outlineClosedSubpath(pts, halfW);
                fr = "evenodd";
            }
            else
            {
                outlineCmds = outlineOpenSubpath(pts, halfW);
            }
            if (size(outlineCmds) > 0)
            {
                result = append(result, {
                    "commands" : outlineCmds,
                    "fillRule" : fr,
                    "source" : "fill",
                    "strokeWidth" : 0
                });
            }
        }
    }
    return result;
}

// ============================================================================
// Section 13: Auto-close, Filter, Entity Count
// ============================================================================

function autoCloseSubpaths(commands is array) returns array
{
    if (size(commands) == 0)
        return commands;
    var result = [];
    var spX = 0.0; var spY = 0.0;
    var cx = 0.0; var cy = 0.0;
    var hasSubpath = false;

    for (var i = 0; i < size(commands); i += 1)
    {
        var cmd = commands[i].cmd;
        var p = commands[i].params;
        if (cmd == "M")
        {
            if (hasSubpath && (abs(cx - spX) > 1e-6 || abs(cy - spY) > 1e-6))
                result = append(result, { "cmd" : "Z", "params" : [] });
            spX = p[0]; spY = p[1]; cx = p[0]; cy = p[1];
            hasSubpath = true;
        }
        else if (cmd == "L")
        { cx = p[0]; cy = p[1]; }
        else if (cmd == "C")
        { cx = p[4]; cy = p[5]; }
        else if (cmd == "A")
        {
            var startRad = p[3] * MY_PI / 180;
            var sweepRad = p[4] * MY_PI / 180;
            cx = p[0] + p[2] * cosNum(startRad + sweepRad);
            cy = p[1] + p[2] * sinNum(startRad + sweepRad);
        }
        else if (cmd == "Z")
        { cx = spX; cy = spY; }
        result = append(result, commands[i]);
    }
    if (hasSubpath && (abs(cx - spX) > 1e-6 || abs(cy - spY) > 1e-6))
        result = append(result, { "cmd" : "Z", "params" : [] });
    return result;
}

function filterFilledPaths(svgPaths is array) returns array
{
    var result = [];
    for (var i = 0; i < size(svgPaths); i += 1)
    {
        if (svgPaths[i].source == "stroke")
            continue;
        var cmds = svgPaths[i].commands;
        if (size(cmds) == 0)
            continue;
        cmds = autoCloseSubpaths(cmds);
        if (size(cmds) > 0)
        {
            result = append(result, {
                "commands" : cmds,
                "fillRule" : svgPaths[i].fillRule
            });
        }
    }
    return result;
}

function countEntities(paths is array) returns number
{
    var count = 0;
    for (var i = 0; i < size(paths); i += 1)
    {
        for (var j = 0; j < size(paths[i].commands); j += 1)
        {
            var c = paths[i].commands[j].cmd;
            if (c == "L" || c == "C" || c == "A")
                count += 1;
        }
    }
    return count;
}

function truncatePaths(paths is array, maxEntities is number) returns array
{
    if (countEntities(paths) <= maxEntities)
        return paths;

    // Sort by entity count descending, drop largest paths first
    // Simple approach: keep adding paths until we hit the limit
    var result = [];
    var total = 0;
    for (var i = 0; i < size(paths); i += 1)
    {
        var pathEntities = 0;
        for (var j = 0; j < size(paths[i].commands); j += 1)
        {
            var c = paths[i].commands[j].cmd;
            if (c == "L" || c == "C" || c == "A")
                pathEntities += 1;
        }
        if (total + pathEntities <= maxEntities)
        {
            result = append(result, paths[i]);
            total += pathEntities;
        }
    }
    return result;
}

// ============================================================================
// Section 14: SVGTEX Parser (backward compatibility)
// ============================================================================

function parseSvgTex(data is string) returns map
{
    var lines = splitByChar(data, "|");
    var viewBox = { "minX" : 0, "minY" : 0, "width" : 100, "height" : 100 };
    var paths = [];

    for (var i = 0; i < size(lines); i += 1)
    {
        var line = trimStr(lines[i]);
        if (length(line) == 0)
            continue;

        var firstChar = substring(line, 0, 1);
        if (firstChar == "#")
            continue;

        if (firstChar == "V")
        {
            var numStr = substring(line, 1, length(line));
            var parts = splitByChar(numStr, ",");
            if (size(parts) >= 4)
            {
                var pch0 = splitIntoCharacters(parts[0]);
                var pch1 = splitIntoCharacters(parts[1]);
                var pch2 = splitIntoCharacters(parts[2]);
                var pch3 = splitIntoCharacters(parts[3]);
                viewBox = {
                    "minX" : parseNum(pch0, 0).val,
                    "minY" : parseNum(pch1, 0).val,
                    "width" : parseNum(pch2, 0).val,
                    "height" : parseNum(pch3, 0).val
                };
            }
        }
        else if (firstChar == "E" || firstChar == "N")
        {
            var fillRule = (firstChar == "E") ? "evenodd" : "nonzero";
            var cmdStr = substring(line, 1, length(line));
            var tokens = splitByChar(cmdStr, " ");
            var commands = [];
            for (var t = 0; t < size(tokens); t += 1)
            {
                var tk = trimStr(tokens[t]);
                if (length(tk) == 0)
                    continue;
                var cc = substring(tk, 0, 1);
                if (cc == "Z")
                {
                    commands = append(commands, { "cmd" : "Z", "params" : [] });
                }
                else
                {
                    var pStr = substring(tk, 1, length(tk));
                    var pp = splitByChar(pStr, ",");
                    var params = [];
                    for (var pi = 0; pi < size(pp); pi += 1)
                    {
                        var ppc = splitIntoCharacters(pp[pi]);
                        params = append(params, parseNum(ppc, 0).val);
                    }
                    commands = append(commands, { "cmd" : cc, "params" : params });
                }
            }
            paths = append(paths, { "commands" : commands, "fillRule" : fillRule });
        }
    }
    return { "viewBox" : viewBox, "paths" : paths, "warnings" : [] };
}

// Detect format: SVG or SVGTEX
function detectAndParse(content is string) returns map
{
    var trimmed = trimStr(content);
    if (length(trimmed) == 0)
        return { "viewBox" : { "minX":0,"minY":0,"width":100,"height":100 }, "paths" : [], "warnings" : ["Empty file."] };

    // Check for SVGTEX format (starts with V followed by digit or minus)
    var fc = substring(trimmed, 0, 1);
    if (fc == "V")
    {
        if (length(trimmed) > 1)
        {
            var sc = substring(trimmed, 1, 2);
            if (isDigit(sc) || sc == "-")
                return parseSvgTex(trimmed);
        }
    }

    // Otherwise treat as SVG
    return parseSvgDocument(content);
}

// ============================================================================
// Section 15: Sketch Generator
// ============================================================================

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
                if (offsetAlternate && (ty % 2 == 1))
                    tileOffsetX += (patternWidth + spacingX) / 2;
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

    skSolve(sketch);
}

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
                curX = (params[0] - viewBox.minX) * scaleX * millimeter;
                curY = -(params[1] - viewBox.minY) * scaleY * millimeter;
                subpathStartX = curX;
                subpathStartY = curY;
            }
            else if (cmd == "L")
            {
                var x = (params[0] - viewBox.minX) * scaleX * millimeter;
                var y = -(params[1] - viewBox.minY) * scaleY * millimeter;
                var p1 = rotOff(curX, curY, cosR, sinR, offsetX, offsetY);
                var p2 = rotOff(x, y, cosR, sinR, offsetX, offsetY);
                skLineSegment(sketch, "line_" ~ toString(entityIdx), {
                    "start" : vector(p1[0], p1[1]),
                    "end" : vector(p2[0], p2[1])
                });
                entityIdx += 1;
                curX = x; curY = y;
            }
            else if (cmd == "C")
            {
                var x1 = (params[0] - viewBox.minX) * scaleX * millimeter;
                var y1 = -(params[1] - viewBox.minY) * scaleY * millimeter;
                var x2 = (params[2] - viewBox.minX) * scaleX * millimeter;
                var y2 = -(params[3] - viewBox.minY) * scaleY * millimeter;
                var x = (params[4] - viewBox.minX) * scaleX * millimeter;
                var y = -(params[5] - viewBox.minY) * scaleY * millimeter;
                var ps = rotOff(curX, curY, cosR, sinR, offsetX, offsetY);
                var pc1 = rotOff(x1, y1, cosR, sinR, offsetX, offsetY);
                var pc2 = rotOff(x2, y2, cosR, sinR, offsetX, offsetY);
                var pe = rotOff(x, y, cosR, sinR, offsetX, offsetY);
                skBezier(sketch, "bezier_" ~ toString(entityIdx), {
                    "points" : [vector(ps[0], ps[1]), vector(pc1[0], pc1[1]), vector(pc2[0], pc2[1]), vector(pe[0], pe[1])]
                });
                entityIdx += 1;
                curX = x; curY = y;
            }
            else if (cmd == "A")
            {
                var cx2 = (params[0] - viewBox.minX) * scaleX * millimeter;
                var cy2 = -(params[1] - viewBox.minY) * scaleY * millimeter;
                var r = params[2] * ((scaleX + scaleY) / 2) * millimeter;
                var startDeg = -params[3];
                var sweepDeg = -params[4];
                var startRad = startDeg * PI / 180;
                var midRad = startRad + (sweepDeg * PI / 180) / 2;
                var endRad = startRad + sweepDeg * PI / 180;
                var arcStart = vector(cx2 + r * cos(startRad * radian), cy2 + r * sin(startRad * radian));
                var arcMid = vector(cx2 + r * cos(midRad * radian), cy2 + r * sin(midRad * radian));
                var arcEnd = vector(cx2 + r * cos(endRad * radian), cy2 + r * sin(endRad * radian));
                var as1 = rotOff2D(arcStart, cosR, sinR, offsetX, offsetY);
                var am = rotOff2D(arcMid, cosR, sinR, offsetX, offsetY);
                var ae = rotOff2D(arcEnd, cosR, sinR, offsetX, offsetY);
                skArc(sketch, "arc_" ~ toString(entityIdx), {
                    "start" : as1, "mid" : am, "end" : ae
                });
                entityIdx += 1;
                curX = cx2 + r * cos(endRad * radian) / millimeter * millimeter;
                curY = cy2 + r * sin(endRad * radian) / millimeter * millimeter;
            }
            else if (cmd == "Z")
            {
                if (abs(curX - subpathStartX) > 0.001 * millimeter ||
                    abs(curY - subpathStartY) > 0.001 * millimeter)
                {
                    var p1 = rotOff(curX, curY, cosR, sinR, offsetX, offsetY);
                    var p2 = rotOff(subpathStartX, subpathStartY, cosR, sinR, offsetX, offsetY);
                    skLineSegment(sketch, "close_" ~ toString(entityIdx), {
                        "start" : vector(p1[0], p1[1]),
                        "end" : vector(p2[0], p2[1])
                    });
                    entityIdx += 1;
                }
                curX = subpathStartX; curY = subpathStartY;
            }
        }
    }
    return entityIdx;
}

function rotOff(x is ValueWithUnits, y is ValueWithUnits,
    cosR is number, sinR is number,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits) returns array
{
    return [x * cosR - y * sinR + offsetX, x * sinR + y * cosR + offsetY];
}

function rotOff2D(pt is Vector, cosR is number, sinR is number,
    offsetX is ValueWithUnits, offsetY is ValueWithUnits) returns Vector
{
    return vector(pt[0] * cosR - pt[1] * sinR + offsetX,
                  pt[0] * sinR + pt[1] * cosR + offsetY);
}

// ============================================================================
// Section 16: Surface Mapper
// ============================================================================

function detectSurfaceType(context is Context, face is Query) returns MappingMode
{
    var surfDef = evSurfaceDefinition(context, { "face" : face });
    if (surfDef is Plane) return MappingMode.PLANAR;
    else if (surfDef is Cylinder) return MappingMode.CYLINDRICAL;
    return MappingMode.PLANAR;
}

function getFacePlane(context is Context, face is Query) returns Plane
{
    return evPlane(context, { "face" : face });
}

function getCylinderInfo(context is Context, face is Query) returns map
{
    var surfDef = evSurfaceDefinition(context, { "face" : face });
    return {
        "axis" : surfDef.coordSystem.zAxis,
        "origin" : surfDef.coordSystem.origin,
        "radius" : surfDef.radius,
        "coordSystem" : surfDef.coordSystem
    };
}

// ============================================================================
// Section 17: Extrusion & Boolean
// ============================================================================

function handlePlanarFace(context is Context, id is Id, face is Query,
    svgData is map, definition is map)
{
    var facePlane = getFacePlane(context, face);
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
    var sketchRegions = qSketchRegion(sketchId);

    if (size(evaluateQuery(context, sketchRegions)) == 0)
    {
        reportFeatureWarning(context, id, "No closed regions found in sketch. The SVG may not have suitable geometry.");
        return;
    }

    var extrudeDir = (definition.direction == TextureDirection.RAISED) ? 1 : -1;
    var extrudeId = id + "extrude";
    opExtrude(context, extrudeId, {
        "entities" : sketchRegions,
        "direction" : facePlane.normal * extrudeDir,
        "endBound" : BoundingType.BLIND,
        "endDepth" : definition.depth
    });

    var targetBody = qOwnerBody(face);
    var extrudedBodies = qCreatedBy(extrudeId, EntityType.BODY);

    var boolId = id + "boolean";
    opBoolean(context, boolId, {
        "tools" : extrudedBodies,
        "targets" : targetBody,
        "operationType" : (definition.direction == TextureDirection.RAISED) ?
            BooleanOperationType.UNION : BooleanOperationType.SUBTRACTION
    });

    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(sketchId, EntityType.BODY) });
}

function handleCylindricalFace(context is Context, id is Id, face is Query,
    svgData is map, definition is map)
{
    var cylInfo = getCylinderInfo(context, face);
    var tangentPlane = evFaceTangentPlane(context, {
        "face" : face,
        "parameter" : vector(0.5, 0.5)
    });

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
        reportFeatureWarning(context, id, "No closed regions found in sketch.");
        return;
    }

    var targetBody = qOwnerBody(face);

    if (definition.direction == TextureDirection.RAISED)
    {
        var extrudeId = id + "extrudeOut";
        opExtrude(context, extrudeId, {
            "entities" : sketchRegions,
            "direction" : tangentPlane.normal,
            "endBound" : BoundingType.BLIND,
            "endDepth" : definition.depth
        });
        var boolId = id + "boolean";
        opBoolean(context, boolId, {
            "tools" : qCreatedBy(extrudeId, EntityType.BODY),
            "targets" : targetBody,
            "operationType" : BooleanOperationType.UNION
        });
    }
    else
    {
        var extrudeId = id + "extrude";
        opExtrude(context, extrudeId, {
            "entities" : sketchRegions,
            "direction" : -tangentPlane.normal,
            "endBound" : BoundingType.BLIND,
            "endDepth" : cylInfo.radius + definition.depth
        });
        var extrudedBodies = qCreatedBy(extrudeId, EntityType.BODY);
        try
        {
            var intersectId = id + "intersect";
            opBoolean(context, intersectId, {
                "tools" : targetBody,
                "targets" : extrudedBodies,
                "operationType" : BooleanOperationType.INTERSECTION,
                "keepTools" : true
            });
            var subtractId = id + "subtract";
            opBoolean(context, subtractId, {
                "tools" : qCreatedBy(intersectId, EntityType.BODY),
                "targets" : targetBody,
                "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
        catch
        {
            var boolId = id + "booleanFallback";
            opBoolean(context, boolId, {
                "tools" : extrudedBodies,
                "targets" : targetBody,
                "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
    }

    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(sketchId, EntityType.BODY) });
}

// ============================================================================
// Section 18: Edit Logic & Main Feature
// ============================================================================

export function svgTextureEditLogic(context is Context, id is Id,
    oldDefinition is map, definition is map, isCreating is boolean) returns map
{
    if (oldDefinition.targetFace != definition.targetFace &&
        definition.mappingMode == MappingMode.AUTO)
    {
        var faces = evaluateQuery(context, definition.targetFace);
        if (size(faces) > 0)
        {
            try silent
            {
                evSurfaceDefinition(context, { "face" : definition.targetFace });
            }
        }
    }
    return definition;
}

annotation { "Feature Type Name" : "SVG Texture",
             "Feature Type Description" : "Apply SVG patterns as 3D raised/recessed textures. Upload raw SVG files directly.",
             "Editing Logic Function" : "svgTextureEditLogic" }
export const svgTexture = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Direction",
                     "UIHint" : UIHint.HORIZONTAL_ENUM }
        definition.direction is TextureDirection;

        annotation { "Name" : "Target face",
                     "Filter" : EntityType.FACE,
                     "MaxNumberOfPicks" : 1 }
        definition.targetFace is Query;

        annotation { "Name" : "SVG file" }
        definition.svgFile is TextData;

        annotation { "Group Name" : "Pattern Size", "Collapsed By Default" : false }
        {
            annotation { "Name" : "Width" }
            isLength(definition.patternWidth, TEXTURE_SIZE_BOUNDS);

            annotation { "Name" : "Height" }
            isLength(definition.patternHeight, TEXTURE_SIZE_BOUNDS);

            annotation { "Name" : "Depth" }
            isLength(definition.depth, TEXTURE_DEPTH_BOUNDS);
        }

        annotation { "Name" : "Mapping",
                     "UIHint" : UIHint.HORIZONTAL_ENUM }
        definition.mappingMode is MappingMode;

        annotation { "Group Name" : "Position", "Collapsed By Default" : true }
        {
            annotation { "Name" : "X offset" }
            isLength(definition.offsetX, ZERO_DEFAULT_LENGTH_BOUNDS);

            annotation { "Name" : "Y offset" }
            isLength(definition.offsetY, ZERO_DEFAULT_LENGTH_BOUNDS);

            annotation { "Name" : "Rotation" }
            isAngle(definition.rotation, ANGLE_360_ZERO_DEFAULT_BOUNDS);
        }

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

        annotation { "Group Name" : "Advanced", "Collapsed By Default" : true }
        {
            annotation { "Name" : "Max sketch entities" }
            isInteger(definition.maxEntities, MAX_ENTITIES_BOUNDS);
        }
    }
    {
        // Validate face selection
        if (size(evaluateQuery(context, definition.targetFace)) == 0)
        {
            reportFeatureError(context, id, "Please select a target face.");
            return;
        }

        // Validate file
        if (definition.svgFile == undefined || definition.svgFile.textData == undefined ||
            length(definition.svgFile.textData) == 0)
        {
            reportFeatureError(context, id, "Please upload an SVG file (or SVGTEX .txt file).");
            return;
        }

        // Parse SVG or SVGTEX
        var svgData = detectAndParse(definition.svgFile.textData);

        // Report warnings
        for (var w = 0; w < size(svgData.warnings); w += 1)
            reportFeatureInfo(context, id, svgData.warnings[w]);

        if (size(svgData.paths) == 0)
        {
            reportFeatureError(context, id, "No geometry found in SVG. The file may use unsupported features, or contain only text/images.");
            return;
        }

        // Convert strokes to outlines
        svgData.paths = strokeToOutlines(svgData.paths);

        // Filter to filled paths only
        svgData.paths = filterFilledPaths(svgData.paths);

        if (size(svgData.paths) == 0)
        {
            reportFeatureError(context, id, "No filled regions found after processing. Check that the SVG has filled shapes.");
            return;
        }

        // Entity count management
        var entityCount = countEntities(svgData.paths);
        var tileMultiplier = 1;
        if (definition.tilingEnabled)
            tileMultiplier = definition.tilesX * definition.tilesY;
        var totalEntities = entityCount * tileMultiplier;

        if (totalEntities > definition.maxEntities)
        {
            var maxPerTile = floor(definition.maxEntities / tileMultiplier);
            if (maxPerTile < 10)
            {
                reportFeatureError(context, id, "Too many entities (" ~ toString(totalEntities) ~
                    ") for the current tiling. Reduce tiles or increase max entities limit.");
                return;
            }
            svgData.paths = truncatePaths(svgData.paths, maxPerTile);
            var newCount = countEntities(svgData.paths) * tileMultiplier;
            reportFeatureWarning(context, id, "Truncated to " ~ toString(newCount) ~
                " entities (from " ~ toString(totalEntities) ~ "). Some paths were dropped to stay within the limit of " ~
                toString(definition.maxEntities) ~ ".");
        }
        else
        {
            reportFeatureInfo(context, id, "SVG parsed: " ~ toString(entityCount) ~ " entities per tile, " ~
                toString(totalEntities) ~ " total.");
        }

        // Detect mapping mode
        var mappingMode = definition.mappingMode;
        if (mappingMode == MappingMode.AUTO)
            mappingMode = detectSurfaceType(context, definition.targetFace);

        // Dispatch
        if (mappingMode == MappingMode.CYLINDRICAL)
            handleCylindricalFace(context, id, definition.targetFace, svgData, definition);
        else
            handlePlanarFace(context, id, definition.targetFace, svgData, definition);
    });
