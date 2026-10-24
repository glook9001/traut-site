// Created by iWeb 3.0.4 local-build-20130428

setTransparentGifURL("Media/transparent.gif");
function applyEffects() {
  var registry = IWCreateEffectRegistry();
  registry.registerEffects({ shadow_9: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_8: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_1: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_0: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_2: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_4: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_3: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_5: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_6: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_11: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_10: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }), shadow_7: new IWShadow({ blurRadius: 10, offset: new IWPoint(4.2426, 4.2426), color: "#000000", opacity: 0.75 }) });
  registry.applyEffects();
}
function hostedOnDM() {
  return false;
}
function onPageLoad() {
  loadMozillaCSS("Around_The_World_files/Around_The_WorldMoz.css");
  adjustLineHeightIfTooBig("id1");
  adjustFontSizeIfTooBig("id1");
  adjustLineHeightIfTooBig("id2");
  adjustFontSizeIfTooBig("id2");
  adjustLineHeightIfTooBig("id3");
  adjustFontSizeIfTooBig("id3");
  adjustLineHeightIfTooBig("id4");
  adjustFontSizeIfTooBig("id4");
  adjustLineHeightIfTooBig("id5");
  adjustFontSizeIfTooBig("id5");
  Widget.onload();
  applyEffects();
}
function onPageUnload() {
  Widget.onunload();
}
