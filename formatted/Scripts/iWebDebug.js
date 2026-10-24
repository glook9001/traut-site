//
//  iWeb - iWebDebug.js
//  Copyright (c) 2007-2008 Apple Inc. All rights reserved.
//

var debugTabString = "  ";
var cEscapeMap = { "\n": "\\n", "	": "\\t", "'": "\\''", "\b": "\\b", "\r": "\\r", "\f": "\\f", "\\": "\\\\" };
var gPendingOutput = "";
function cEscape(s) {
  var r = "";
  for (var i = 0; i < s.length; ++i) {
    var ch = s.charAt(i);
    var cc = s.charCodeAt(i);
    var cr = cEscapeMap[ch];
    if (cr !== void 0) {
      ch = cr;
    } else if (cc < 32) {
      r += "\\" + cc.toString(8);
    } else if (cc > 126) {
      r += "\\u" + ("0000" + cc.toString(16)).slice(-4);
    } else {
      r += ch;
    }
  }
  return r;
}
function cUnescape(s) {
  throw Unimplemented;
}
function convertTextForHTML(s) {
  s = s.replace(/&/g, "&amp;");
  s = s.replace(/</g, "&lt;");
  s = s.replace(/\n/g, "<br/>");
  s = s.replace(/ /g, "&nbsp;");
  return s;
}
function debugPrintDiv() {
  var debugDiv = $("debugDiv");
  if (debugDiv === null) {
    if (document.body !== null) {
      debugDiv = $(document.createElement("div"));
      if (debugDiv) {
        var debugDivWrapper = document.createElement("div");
        debugDivWrapper.id = "debugDivWrapper";
        debugDiv.id = "debugDiv";
        var debugDivClearButton = document.createElement("input");
        debugDivClearButton.title = "Clear Debug Area";
        debugDivClearButton.value = "Clear";
        debugDivClearButton.type = "button";
        debugDivClearButton.onclick = debugClear;
        debugDiv.innerHTML = gPendingOutput;
        debugDivWrapper.appendChild(debugDivClearButton);
        debugDivWrapper.appendChild(debugDiv);
        document.body.appendChild(debugDivWrapper);
      }
    }
  }
  if (debugDiv && debugDiv.initialized != true) {
    debugDiv.setStyle({ textAlign: "left", zOrder: 0, backgroundColor: "#ffff99", marginTop: "10px", opacity: "1.0", fontFamily: "Courier", fontSize: "10pt", border: "2px solid red" });
    debugDiv.initialized = true;
  }
  return debugDiv;
}
function debugRelocateDiv() {
  var debugDiv = $("debugDiv");
  if (debugDiv != null) {
    debugDiv.parentNode.removeChild(debugDiv);
    document.body.appendChild(debugDiv);
  }
}
function debugClear() {
  var debugDiv = $("debugDiv");
  if (debugDiv) {
    debugDiv.innerHTML = "";
  }
}
function debugPrintHtml(s) {
  var debugDiv = debugPrintDiv();
  if (debugDiv) {
    debugDiv.innerHTML = debugDiv.innerHTML + s;
  } else {
    gPendingOutput += s + "<br/>";
  }
}
var debugPrintUsesNSLog = true;
function debugPrint(s) {
  if (debugPrintUsesNSLog && window.console && window.console.NSLog) {
    window.console.NSLog(s);
  } else {
    s = convertTextForHTML(String(s));
    var debugDiv = debugPrintDiv();
    if (debugDiv) {
      debugDiv.innerHTML = debugDiv.innerHTML + s + "<br/>";
    } else {
      gPendingOutput += s + "<br/>";
    }
  }
}
function Undefined() {
}
Undefined.prototype.toString = function() {
  return "undefined";
};
function asObject(v2) {
  if (typeof v2 == "number") {
    return Number(v2);
  }
  if (typeof v2 == "object") {
    return v2;
  }
  if (typeof v2 == "string") {
    return v2;
  }
  if (typeof v2 == "boolean") {
    return Boolean(v2);
  }
  if (typeof v2 == "undefined") {
    return new Undefined();
  }
  debugPrint("### didn't wrap value of type " + typeof v2);
  return null;
}
function stringWithFormat() {
  var result = "";
  for (var i = 0; i < arguments.length; ++i) {
    var arg = asObject(arguments[i]);
    var argString = "null";
    if (arg !== null) {
      if (arg === void 0) {
        argString = "<arg " + i + " undefined>";
      } else {
        if (arg.toString !== void 0) {
          argString = arg.toString();
        } else {
          argString = "<arg " + i + " does not define toString()>";
        }
      }
    }
    var pos = result.indexOf("%s");
    if (pos >= 0) {
      result = result.substr(0, pos) + argString + result.substr(pos + "%s".length);
    } else {
      if (i > 0) {
        result += " ";
      }
      result += argString;
    }
  }
  return result;
}
var trace = function() {
};
function print() {
  debugPrint(stringWithFormat.apply(this, arguments));
}
function valueTypeString(value) {
  if (value === null) {
    return "null";
  }
  var valueType = typeof value;
  if (valueType == "object") {
    if (value.constructor == Array) {
      return "Array";
    }
    if (value.constructor == Number) {
      return "Number";
    }
    if (value.constructor == String) {
      return "String";
    }
    return "Object";
  }
  return valueType;
}
function isObject(obj) {
  return obj && typeof obj == "object";
}
function isArray(obj) {
  return isObject(obj) && obj.constructor == Array;
}
function isArrayLike(obj) {
  return isObject(obj) && obj.constructor === void 0 && obj.length !== void 0 && obj.item !== void 0;
}
function debugObjectToString(name, obj) {
  var resultString = "";
  if (arguments.length == 1) {
    obj = arguments[0];
    name = "";
  } else {
    name += " = ";
  }
  if (obj === void 0) {
    resultString += stringWithFormat("%s(undefined)\n", name);
  } else if (obj === null) {
    resultString += stringWithFormat("%snull\n", name);
  } else if (obj.constructor && obj.constructor == Function) {
    resultString += stringWithFormat("%s(function)\n", name);
  } else if (isArray(obj)) {
    resultString += stringWithFormat("%sarray of %s %s [\n", name, obj.length, obj.length == 1 ? "item" : "items");
    for (var i = 0; i < obj.length; ++i) {
      resultString += stringWithFormat("  %s : %s,\n", i, debugValueToString(obj[i]));
    }
    resultString += stringWithFormat("]\n");
  } else if (isArrayLike(obj)) {
    resultString += stringWithFormat("%s'array' of %s %s [\n", name, obj.length, obj.length == 1 ? "item" : "items");
    for (var i = 0; i < obj.length; ++i) {
      resultString += stringWithFormat("  %s : %s,\n", i, debugValueToString(obj[i]));
    }
    resultString += stringWithFormat("]\n");
  } else if (isObject(obj)) {
    resultString += stringWithFormat("%sobject {\n", name);
    try {
      var fieldWidth = 0;
      var keys = $H(obj).keys().sort();
      $A(keys).each(function(key) {
        fieldWidth = Math.max(fieldWidth, key.length);
      });
      $A(keys).each(function(key) {
        var attr = key;
        attrStr = (attr + "                               ").substring(0, fieldWidth);
        try {
          resultString += stringWithFormat("  %s : %s\n", attrStr, debugValueToString(obj[attr]));
        } catch (e2) {
          print(e2);
          print("  !!!attr=", attr, "(type is %s)", typeof obj[attr]);
        }
      });
    } catch (e2) {
      debugPrintException(e2);
      print("  ## can't enumerate object contents. Might be IE 7.");
    }
    resultString += stringWithFormat("}\n");
  } else {
    resultString += stringWithFormat("%s%s(%s)\n", name, valueTypeString(obj), debugValueToString(obj));
  }
  return resultString;
}
function debugPrintObject(name, obj) {
  if (arguments.length == 1) {
    obj = arguments[0];
    name = "";
  } else {
    name += " = ";
  }
  if (obj === void 0) {
    print("%s(undefined)", name);
  } else if (obj === null) {
    print("%snull", name);
  } else if (obj.constructor && obj.constructor == Function) {
    print("%s(function)", name);
  } else if (isArray(obj)) {
    print("%sarray of %s %s [", name, obj.length, obj.length == 1 ? "item" : "items");
    for (var i = 0; i < obj.length; ++i) {
      print("  %s : %s,", i, debugValueToString(obj[i]));
    }
    print("]");
  } else if (isArrayLike(obj)) {
    print("%s'array' of %s %s [", name, obj.length, obj.length == 1 ? "item" : "items");
    for (var i = 0; i < obj.length; ++i) {
      print("  %s : %s,", i, debugValueToString(obj[i]));
    }
    print("]");
  } else if (isObject(obj)) {
    print("%sobject {", name);
    try {
      var fieldWidth = 0;
      var keys = $H(obj).keys().sort();
      $A(keys).each(function(key) {
        fieldWidth = Math.max(fieldWidth, key.length);
      });
      $A(keys).each(function(key) {
        var attr = key;
        attrStr = (attr + "                               ").substring(0, fieldWidth);
        try {
          print("  %s : %s", attrStr, debugValueToString(obj[attr]));
        } catch (e2) {
          print(e2);
          print("  !!!attr=", attr, "(type is %s)", typeof obj[attr]);
        }
      });
    } catch (e2) {
      debugPrintException(e2);
      print("  ## can't enumerate object contents. Might be IE 7.");
    }
    print("}");
  } else {
    print("%s%s(%s)", name, valueTypeString(obj), debugValueToString(obj));
  }
}
var printObject = debugPrintObject;
function debugPrintException(e2) {
  print("# Exception: %s", e2.name);
  print("# Message  : %s", e2.message);
  if (e2.sourceURL) {
    var file = e2.sourceURL.match(/[^\/]*$/);
    if (file !== null) {
      print("# File     : %s, Line:%s", file[0], e2.line);
    }
  }
}
function indentHtmlString(s) {
  var r = debugTabString + s;
  r = r.replace(/<br\/>/g, "<br/>" + debugTabString);
  return r;
}
function indentString(s) {
  var r = debugTabString + s;
  r = r.replace(/\n/g, "\n" + debugTabString);
  return r;
}
function debugValueToString(value, maxLength, parentStack, attributeStack, refs) {
  var result = "";
  var valueType = valueTypeString(value);
  if (arguments.length == 1) {
    maxLength = 800;
  }
  if (parentStack === void 0) {
    parentStack = [];
  }
  if (attributeStack === void 0) {
    attributeStack = ["this"];
  }
  if (refs === void 0) {
    refs = { value: "this" };
  }
  if (valueType == "null") {
    result = "null";
  } else if (valueType == "function") {
    result = "(function)";
  } else if (valueType == "undefined") {
    result = "(undefined)";
  } else if (valueType == "Object") {
    if (parentStack.length > 2) {
      result = "...";
    } else {
      var first = true;
      var fieldWidth = 0;
      var attrs = $H(value).keys().sort();
      $A(attrs).each(function(attr) {
        fieldWidth = Math.max(fieldWidth, attr.length);
      });
      var newParentStack = parentStack.concat(value);
      $A(attrs).each(function(attr) {
        var nextMaxLength2 = maxLength - result.length - 2 - (attr.length + 2);
        var valueAttrString;
        var subValue = value[attr];
        if (typeof subValue != "function") {
          if (!first) {
            result = result + ", ";
          }
          first = false;
          if (typeof subValue == "object" && newParentStack.contains(subValue)) {
            var index2 = $A(newParentStack).indexOf(value[attr]);
            valueAttrString = "#cycle(" + attributeStack[index2] + ")";
          } else if (typeof subValue == "object" && refs[subValue] !== void 0) {
            valueAttrString = "#ref(" + refs[subValue] + ")";
          } else {
            try {
              var newAttributePath = attributeStack[attributeStack.length - 1] + "." + attr;
              var newAttributeStack = attributeStack.concat(newAttributePath);
              refs[value[attr]] = newAttributePath;
              valueAttrString = debugValueToString(value[attr], nextMaxLength2, newParentStack, newAttributeStack, refs);
            } catch (e2) {
              valueAttrString = "#exception";
            }
          }
          var newResult2 = result + attr + ": " + valueAttrString;
          if (newResult2.length > maxLength) {
            result += "...";
          } else {
            result = newResult2;
          }
        }
      });
    }
    result = "{" + result + "}";
  } else if (valueType == "Array") {
    var arrayLength = value.length;
    for (var i = 0; i < arrayLength; ++i) {
      if (i !== 0) {
        result = result + ", ";
      }
      var nextMaxLength = maxLength - result.length;
      var newResult = result + debugValueToString(value[i], nextMaxLength);
      if (newResult.length > maxLength) {
        result += "...";
        break;
      }
      result = newResult;
    }
    result = "[" + result + "]";
  } else if (valueType == "number") {
    result = value.toString();
  } else if (valueType == "boolean") {
    result = value.toString();
  } else if (valueType == "string") {
    result = '"' + value.toString() + '"';
  } else {
    result = "(UNKNOWN TYPE: " + valueType + ")";
  }
  return result;
}
var gFadeElement;
var gFadeDelta = 0;
var gFadeTimeout = 0;
function nextFadeStep() {
  var oldOpacity = gFadeElement.style.opacity - 0;
  if (gFadeDelta > 0 && oldOpacity < gFadeTarget || gFadeDelta < 0 && oldOpacity > gFadeTarget) {
    var newOpacity = gFadeDelta + oldOpacity;
    gFadeElement.style.opacity = newOpacity;
    setTimeout(nextFadeStep, gFadeTimeout);
  } else {
    gFadeDelta = 0;
  }
}
function startFadeIn(element) {
  if (gFadeDelta === 0) {
    setTimeout(nextFadeStep, gFadeTimeout);
  }
  gFadeElement = element;
  gFadeTimeout = 20;
  gFadeTarget = 1;
  gFadeDelta = 0.1;
}
function startFadeOut(element) {
  if (gFadeDelta === 0) {
    setTimeout(nextFadeStep, gFadeTimeout);
  }
  gFadeElement = element;
  gFadeTimeout = 20;
  gFadeTarget = 0;
  gFadeDelta = -0.1;
}
function onMouseOverDebugMenu() {
  if (window.event.shiftKey) {
    var debugMenu2 = $("debugMenu");
    debugMenu2.setStyle({ height: "", width: "" });
    startFadeIn(debugMenu2);
  }
}
function documentResourceURL(ext) {
  resourceUrl = "";
  htmlUrl = document.URL;
  while (htmlUrl.length > 0 && htmlUrl.slice(-5) != ".html") {
    htmlUrl = htmlUrl.slice(0, -1);
  }
  if (htmlUrl.length > 0) {
    var components = htmlUrl.split("/");
    var filename = components.pop();
    filename = filename.slice(0, -5);
    var folderName = filename + "_files";
    components.push(folderName);
    components.push(filename + ext);
    resourceUrl = components.join("/");
  }
  return resourceUrl;
}
function showCSS() {
  cssUrl = documentResourceURL(".css");
  if (cssUrl.length > 0) {
    window.open(cssUrl, "CSS");
  }
}
function showJavaScript() {
  cssUrl = documentResourceURL(".js");
  if (cssUrl.length > 0) {
    window.open(cssUrl, "JavaScript");
  }
}
function closeDebugMenu() {
  var debugMenu2 = $("debugMenu");
  debugMenu2.setStyle({ height: "10px", width: "10px" });
  startFadeOut(debugMenu2);
}
function dumpEntryData() {
  var myEntryData = "not defined";
  try {
    myEntryData = entryData;
  } catch (e2) {
  }
  debugPrintObject(myEntryData);
}
function dumpEntryURLs() {
  var myEntryURLs = "not defined";
  try {
    myEntryURLs = entryURLs;
  } catch (e2) {
  }
  debugPrintObject(myEntryURLs);
}
function jsEvalClick() {
  try {
    var text = $("jstext").value;
    debugPrint(text);
    eval(text);
  } catch (e2) {
    debugPrint("** Exception **");
    debugPrintObject(e2);
  }
}
function scriptNodes() {
  var result = [];
  var body = document.body;
  debugPrint(body.tagName);
  var html = body.parentNode;
  debugPrint(html.tagName);
  var head = $$("head");
  for (var i = 0; i < head.childNodes.length; ++i) {
    var node = head.childNodes[i];
    if (node.nodeName == "SCRIPT") {
      result.push(node);
    }
  }
  return result;
}
function showAllScripts() {
  var scripts = scriptNodes();
  var scriptUrls = [];
  for (var i = 0; i < scripts.length; ++i) {
    if (scripts[i].src !== "") {
      scriptUrls.push(scripts[i].src);
    }
  }
  debugPrintHtml("<br/><b>Scripts used on this page:</b><br/>");
  for (i = 0; i < scriptUrls.length; ++i) {
    url = scriptUrls[i];
    var s = '<a href="%url%" target="code">%url%</a><br/>';
    s = s.replace(/%url%/g, url);
    debugPrintHtml(s);
  }
}
var gVariables = {};
var gVariableCount = 0;
var gRenderItemCount = 0;
var gRootVariables = [];
function addInspectorVariable(varName) {
  gRootVariables.push(varName);
  renderInspector();
}
function inspect(varName) {
  addInspectorVariable(varName);
}
function getVariableId(variable) {
  for (v in gVariables) {
    if (gVariables[v].object === variable) {
      return v;
    }
  }
  var vid = "vid" + gVariableCount++;
  record = {};
  record.object = variable;
  record.id = vid;
  record.open = false;
  record.showFunctions = false;
  gVariables[vid] = record;
  return vid;
}
function clickItem(vid) {
  gVariables[vid].open = !gVariables[vid].open;
  renderInspector();
}
function toggleFuncs(vid) {
  gVariables[vid].showFunctions = !gVariables[vid].showFunctions;
  renderInspector();
}
function clickDelete(vid) {
  for (var index2 in gRootVariables) {
    if (gRootVariables[index2] == vid) {
      gRootVariables.splice(index2, 1);
      renderInspector();
      return;
    }
  }
}
function makeControlSpan(vid, functionName, flag, onString, offString) {
  var span = document.createElement("span");
  span.setAttribute("onclick", functionName + "('" + vid + "');");
  span.innerText = flag ? onString : offString;
  return span;
}
function renderInspectorItem(name, thing2, parent, parentStack) {
  gRenderItemCount++;
  var div = $(document.createElement("div"));
  div.setStyle({ left: "30px", position: "relative" });
  var span = document.createElement("span");
  var text2 = " " + name + " = ";
  var vid;
  if (typeof thing2 == "object") {
    if (thing2.constructor == Array) {
      text2 += "array[" + thing2.length + "] " + debugValueToString(thing2);
    } else {
      text2 += "object " + debugValueToString(thing2);
    }
    vid = getVariableId(thing2);
    span = makeControlSpan(vid, "clickItem", gVariables[vid].open, "-", "+");
  } else {
    span.innerText = "-";
    text2 += debugValueToString(thing2);
  }
  var textNode = document.createTextNode(text2);
  div.appendChild(span);
  div.appendChild(textNode);
  var closeSpan = null;
  if (gRootVariables.contains(name)) {
    closeSpan = makeControlSpan(name, "clickDelete", true, "[X]", "[X]");
    div.appendChild(closeSpan);
  }
  if (typeof thing2 == "object") {
    if (gVariables[vid].open && !parentStack.contains(thing2)) {
      var funcSpan = makeControlSpan(vid, "toggleFuncs", gVariables[vid].showFunctions, "[F]", "[f]");
      div.insertBefore(funcSpan, closeSpan);
      try {
        $H(thing2).keys().sort().each(function(item) {
          if (typeof thing2[item] != "function" || gVariables[vid].showFunctions) {
            renderInspectorItem(item, thing2[item], div, parentStack.concat(thing2[item]));
          }
        });
      } catch (e2) {
      }
    }
  }
  parent.appendChild(div);
}
function renderInspector() {
  gRenderItemCount = 0;
  var inspectorDiv = $("inspect");
  if (inspectorDiv === null) {
    inspectorDiv = $(document.createElement("div"));
    inspectorDiv.id = "inspect";
    inspectorDiv.setStyle({ backgroundColor: "#d8d8d8", fontFamily: "Courier", fontSize: "10pt" });
    document.body.appendChild(inspectorDiv);
  }
  while (inspectorDiv.childNodes.length > 0) {
    inspectorDiv.removeChild(inspectorDiv.childNodes[0]);
  }
  var emptyArray = [];
  for (var index in gRootVariables) {
    if (emptyArray[index] === void 0) {
      var thing = eval(gRootVariables[index]);
      renderInspectorItem(gRootVariables[index], eval(gRootVariables[index]), inspectorDiv, []);
    }
  }
}
function evalOnKeyUp(e2) {
  if (e2.keyIdentifier == "Enter") {
    jsEvalClick();
  }
}
function iWebDebugPanelInit() {
  var headerLayer = document.body;
  var debugMenu = $(document.createElement("div"));
  debugMenu.id = "debugMenu";
  debugMenu.setStyle({ backgroundColor: "#ffff99", position: "fixed", left: 0, top: 0, width: "10px", height: "10px", padding: "10px", opacity: 0, fontFamily: "Lucida Grande", fontSize: "10px", zIndex: 100, overflow: "hidden", border: "1px solid black" });
  debugMenu.onmouseover = onMouseOverDebugMenu;
  headerLayer.appendChild(debugMenu);
  var myCommentsVersion = "not defined";
  try {
    myCommentsVersion = commentJavascriptVersion;
  } catch (e2) {
  }
  debugMenu.innerHTML = "<b><u>JavaScript Debug Options</u></b><div style='float:right'><a href='#' onclick='closeDebugMenu();'>Close</a></div><br/><br/><a href='#' onclick='showCSS();'>Show Page CSS</a><br/><a href='#' onclick='showJavaScript();'>Show Page JavaScript</a><br/><a href='#' onclick='showAllScripts();'>List all scripts</a><br/><br/><a href='#' onclick='dumpEntryData();'>Show comment entryData</a><br/><a href='#' onclick='dumpEntryURLs();'>Show comment summaryData</a><br/><a href='#' onclick='debugClear();'>Clear debug output</a><br/><br/><textarea id='jstext' cols='40' rows='4'/>inspect(window);</textarea><br/><br/><hr/>Comment js version: " + myCommentsVersion;
  var textArea = $("jstext");
  if (textArea) {
    textArea.onkeyup = function(e) {
      if (e.keyIdentifier == "Enter") {
        try {
          var text = $("jstext").value;
          debugPrintHtml(text.bold() + "<br/>");
          eval(text);
        } catch (e2) {
          debugPrint("** Exception **");
          debugPrintObject(e2);
        }
        if (textArea.setSelectionRange) {
          textArea.setSelectionRange(0, textArea.value.length);
        }
        e.cancelBubble = true;
      }
    };
  }
  renderInspector();
}
